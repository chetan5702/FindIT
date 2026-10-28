"""Institutional verification, recovery, token privacy and session regression tests."""

from datetime import UTC, datetime, timedelta
from email import policy
from email.parser import BytesParser
from threading import Barrier
from concurrent.futures import ThreadPoolExecutor
import re
import uuid

import pytest
from sqlalchemy import select
from app.models import AuthActionToken, AuthSession, User
from app.security import digest_token

PASSWORD = "ValidPassword123!"
NEW_PASSWORD = "NewSecurePassword456!"


def identity_mode(scenario):
    settings = scenario["settings"]
    settings.allowed_email_domains = ["suh.edu.in"]
    settings.require_email_verification = True
    settings.identity_request_limit = 50
    settings.identity_ip_request_limit = 100
    return settings


def client(scenario):
    c = scenario["client"]()
    assert c.get("/api/v1/auth/csrf").status_code == 200
    return c


def register(scenario, c, email="student@suh.edu.in"):
    return scenario["write"](
        c,
        "POST",
        "/api/v1/auth/register",
        json={"email": email, "full_name": "Student User", "password": PASSWORD},
    )


def token_from_mail(settings, purpose):
    files = sorted(settings.mail_directory.glob("*.eml"), reverse=True)
    assert files
    route = "verify-email" if purpose == "verify" else "reset-password"
    for file in files:
        message = BytesParser(policy=policy.default).parsebytes(file.read_bytes())
        body = message.get_content()
        if route not in body:
            continue
        return re.search(r"#token=([A-Za-z0-9_-]+)", body).group(1), body
    raise AssertionError("Expected an identity email for the requested purpose")


def verified(scenario):
    settings = identity_mode(scenario)
    c = client(scenario)
    assert register(scenario, c).status_code == 201
    token, _ = token_from_mail(settings, "verify")
    response = scenario["write"](
        c, "POST", "/api/v1/auth/verification/confirm", json={"token": token, "password": PASSWORD}
    )
    assert response.status_code == 200, response.text
    return c, settings


def login(scenario, c, password=PASSWORD):
    return scenario["write"](
        c, "POST", "/api/v1/auth/login", json={"email": "student@suh.edu.in", "password": password}
    )


def test_institution_domain_and_no_session_before_email_verification(scenario):
    settings = identity_mode(scenario)
    c = client(scenario)
    for email in [
        "student@example.com",
        "student@evil-suh.edu.in",
        "student@suh.edu.in.evil.com",
        "student@sub.suh.edu.in",
    ]:
        assert register(scenario, c, email).status_code == 422
    response = register(scenario, c, "Student@SUH.EDU.IN")
    assert response.status_code == 201
    assert response.json()["verification_required"] and response.json()["user"] is None
    assert "findit_session" not in c.cookies
    assert c.get("/api/v1/reports").status_code == 401
    assert login(scenario, c).json()["error"]["code"] == "email_verification_required"
    token, body = token_from_mail(settings, "verify")
    assert "?token=" not in body and "#token=" in body
    with scenario["session"]() as db:
        action = db.scalar(select(AuthActionToken))
        assert action.token_hash == digest_token(token)
        assert token.encode() != action.token_hash
        assert list(db.scalars(select(AuthSession))) == []
    assert (
        scenario["write"](
            c,
            "POST",
            "/api/v1/auth/verification/confirm",
            json={"token": token, "password": PASSWORD},
        ).status_code
        == 200
    )
    assert (
        scenario["write"](
            c,
            "POST",
            "/api/v1/auth/verification/confirm",
            json={"token": token, "password": PASSWORD},
        ).status_code
        == 400
    )
    assert login(scenario, c).status_code == 200
    assert c.get("/api/v1/auth/me").json()["email_verified"] is True


def test_duplicate_registration_never_overwrites_password_or_exposes_account(scenario):
    c, settings = verified(scenario)
    duplicate = register(scenario, c)
    assert duplicate.status_code == 201
    assert duplicate.json()["user"] is None
    assert duplicate.json()["verification_required"]
    assert login(scenario, c).status_code == 200


def test_expired_wrong_purpose_and_replaced_tokens_are_rejected(scenario):
    settings = identity_mode(scenario)
    c = client(scenario)
    register(scenario, c)
    old, _ = token_from_mail(settings, "verify")
    assert (
        scenario["write"](
            c, "POST", "/api/v1/auth/password/reset", json={"token": old, "password": NEW_PASSWORD}
        ).status_code
        == 400
    )
    scenario["write"](
        c, "POST", "/api/v1/auth/verification/request", json={"email": "student@suh.edu.in"}
    )
    new, _ = token_from_mail(settings, "verify")
    assert new != old
    assert (
        scenario["write"](
            c,
            "POST",
            "/api/v1/auth/verification/confirm",
            json={"token": old, "password": PASSWORD},
        ).status_code
        == 400
    )
    with scenario["session"]() as db:
        action = db.scalar(select(AuthActionToken))
        action.expires_at = datetime.now(UTC) - timedelta(seconds=1)
        db.commit()
    assert (
        scenario["write"](
            c,
            "POST",
            "/api/v1/auth/verification/confirm",
            json={"token": new, "password": PASSWORD},
        ).status_code
        == 400
    )


def test_reset_is_generic_one_use_and_revokes_all_sessions(scenario):
    c, settings = verified(scenario)
    assert login(scenario, c).status_code == 200
    other = client(scenario)
    assert login(scenario, other).status_code == 200
    attacker = client(scenario)
    known = scenario["write"](
        attacker, "POST", "/api/v1/auth/password/forgot", json={"email": "student@suh.edu.in"}
    )
    missing = scenario["write"](
        attacker, "POST", "/api/v1/auth/password/forgot", json={"email": "missing@suh.edu.in"}
    )
    assert known.status_code == missing.status_code == 200
    assert known.json() == missing.json()
    token, _ = token_from_mail(settings, "reset")
    response = scenario["write"](
        attacker,
        "POST",
        "/api/v1/auth/password/reset",
        json={"token": token, "password": NEW_PASSWORD},
    )
    assert response.status_code == 200
    assert c.get("/api/v1/auth/me").status_code == other.get("/api/v1/auth/me").status_code == 401
    attacker.get("/api/v1/auth/csrf")
    assert (
        scenario["write"](
            attacker,
            "POST",
            "/api/v1/auth/password/reset",
            json={"token": token, "password": NEW_PASSWORD},
        ).status_code
        == 400
    )
    assert login(scenario, attacker).status_code == 401
    assert login(scenario, attacker, NEW_PASSWORD).status_code == 200


def test_unverified_and_disabled_users_cannot_reset(scenario):
    settings = identity_mode(scenario)
    c = client(scenario)
    register(scenario, c)
    before = len(list(settings.mail_directory.glob("*.eml")))
    assert (
        scenario["write"](
            c, "POST", "/api/v1/auth/password/forgot", json={"email": "student@suh.edu.in"}
        ).status_code
        == 200
    )
    assert len(list(settings.mail_directory.glob("*.eml"))) == before
    token, _ = token_from_mail(settings, "verify")
    with scenario["session"]() as db:
        user = db.scalar(select(User).where(User.email == "student@suh.edu.in"))
        user.is_active = False
        db.commit()
    assert (
        scenario["write"](
            c,
            "POST",
            "/api/v1/auth/verification/confirm",
            json={"token": token, "password": PASSWORD},
        ).status_code
        == 400
    )


def test_password_change_reauthenticates_and_clears_all_devices(scenario):
    c, _ = verified(scenario)
    login(scenario, c)
    other = client(scenario)
    login(scenario, other)
    wrong = scenario["write"](
        c,
        "POST",
        "/api/v1/auth/password/change",
        json={"current_password": "incorrect", "password": NEW_PASSWORD},
    )
    assert wrong.status_code == 401
    assert c.get("/api/v1/auth/me").status_code == 200
    response = scenario["write"](
        c,
        "POST",
        "/api/v1/auth/password/change",
        json={"current_password": PASSWORD, "password": NEW_PASSWORD},
    )
    assert response.status_code == 200 and "findit_session" not in c.cookies
    assert other.get("/api/v1/auth/me").status_code == 401
    c.get("/api/v1/auth/csrf")
    assert login(scenario, c, NEW_PASSWORD).status_code == 200


def test_session_revocation_is_scoped_and_logout_all(scenario):
    c, _ = verified(scenario)
    login(scenario, c)
    other = client(scenario)
    login(scenario, other)
    sessions = c.get("/api/v1/auth/sessions").json()
    assert len(sessions) == 2 and sum(item["current"] for item in sessions) == 1
    assert all("token_hash" not in item and "csrf_hash" not in item for item in sessions)
    other_id = next(item["id"] for item in sessions if not item["current"])
    assert (
        scenario["write"](c, "DELETE", f"/api/v1/auth/sessions/{uuid.uuid4()}").status_code == 404
    )
    assert scenario["write"](c, "DELETE", f"/api/v1/auth/sessions/{other_id}").status_code == 204
    assert other.get("/api/v1/auth/me").status_code == 401
    assert scenario["write"](c, "POST", "/api/v1/auth/logout-all").status_code == 204
    assert c.get("/api/v1/auth/me").status_code == 401


def test_identity_requests_are_rate_limited_without_issuing_extra_tokens(scenario):
    settings = identity_mode(scenario)
    settings.identity_request_limit = 1
    c = client(scenario)
    register(scenario, c)
    response = scenario["write"](
        c, "POST", "/api/v1/auth/verification/request", json={"email": "student@suh.edu.in"}
    )
    assert response.status_code == 200
    response = scenario["write"](
        c, "POST", "/api/v1/auth/verification/request", json={"email": "student@suh.edu.in"}
    )
    assert response.status_code == 429


def test_smtp_failure_does_not_expose_token_or_credentials(scenario, monkeypatch, caplog):
    from app.services.mail import deliver

    settings = scenario["settings"]
    settings.mail_backend = "smtp"
    settings.smtp_host = "invalid"

    def fail(*args, **kwargs):
        raise RuntimeError("secret token must not appear")

    monkeypatch.setattr("app.services.mail.smtplib.SMTP", fail)
    deliver(settings, "student@suh.edu.in", "Reset", "secret token must not appear")
    assert "delivery failed" in caplog.text and "secret token must not appear" not in caplog.text


def test_postgres_reset_token_can_only_be_consumed_once_concurrently(scenario):
    with scenario["session"]() as db:
        if db.bind.dialect.name != "postgresql":
            pytest.skip("requires PostgreSQL user/token row locks")
    c, settings = verified(scenario)
    login(scenario, c)
    scenario["write"](
        c, "POST", "/api/v1/auth/password/forgot", json={"email": "student@suh.edu.in"}
    )
    token, _ = token_from_mail(settings, "reset")
    a, b = client(scenario), client(scenario)
    barrier = Barrier(2)

    def reset(c):
        barrier.wait(timeout=10)
        return scenario["write"](
            c,
            "POST",
            "/api/v1/auth/password/reset",
            json={"token": token, "password": NEW_PASSWORD},
        ).status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(reset, [a, b])) == [200, 400]


def test_mailbox_owner_selects_password_instead_of_trusting_preregistration(scenario):
    settings = identity_mode(scenario)
    c = client(scenario)
    register(scenario, c)
    token, _ = token_from_mail(settings, "verify")
    response = scenario["write"](
        c,
        "POST",
        "/api/v1/auth/verification/confirm",
        json={"token": token, "password": NEW_PASSWORD},
    )
    assert response.status_code == 200
    assert login(scenario, c).status_code == 401
    assert login(scenario, c, NEW_PASSWORD).status_code == 200


def test_console_verification_only_trusts_active_admin_with_current_password(scenario, monkeypatch):
    from app import cli
    from types import SimpleNamespace
    c = scenario['client']()
    account = scenario['auth'](c, 'console@suh.edu.in')
    with scenario['session']() as db:
        user = db.get(User, uuid.UUID(account['id']))
        user.role = 'admin'
        assert not user.email_verified
        db.commit()
    monkeypatch.setattr(cli, 'SessionLocal', scenario['session'])
    monkeypatch.setattr(cli.getpass, 'getpass', lambda _: PASSWORD)
    assert cli.verify_admin(SimpleNamespace(email='console@suh.edu.in')) == 0
    with scenario['session']() as db:
        assert db.get(User, uuid.UUID(account['id'])).email_verified


def test_console_verification_rejects_student_and_wrong_password(scenario, monkeypatch):
    from app import cli
    from types import SimpleNamespace
    c = scenario['client']()
    account = scenario['auth'](c, 'console@suh.edu.in')
    monkeypatch.setattr(cli, 'SessionLocal', scenario['session'])
    monkeypatch.setattr(cli.getpass, 'getpass', lambda _: PASSWORD)
    assert cli.verify_admin(SimpleNamespace(email='console@suh.edu.in')) == 1
    with scenario['session']() as db:
        user = db.get(User, uuid.UUID(account['id'])); user.role='admin'; db.commit()
    monkeypatch.setattr(cli.getpass, 'getpass', lambda _: 'wrong')
    assert cli.verify_admin(SimpleNamespace(email='console@suh.edu.in')) == 1
    with scenario['session']() as db:
        assert not db.get(User, uuid.UUID(account['id'])).email_verified
