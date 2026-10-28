from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
from threading import Barrier
import uuid

import pytest
from PIL import Image
from pydantic import ValidationError
from sqlalchemy import select

from app.models import AuthRateBucket, ClaimEvidence, ReportImage, User
from app.schemas import AdminUserUpdate, CategoryUpdate, CustodyUpdate, LocationUpdate, ReportUpdate
from app.services.rate_limits import admit
from app.errors import APIError


def admin_client(scenario, email="admin@example.com"):
    client = scenario["client"]()
    user = scenario["auth"](client, email)
    with scenario["session"]() as db:
        db.get(User, uuid.UUID(user["id"])).role = "admin"
        db.commit()
    return client, user


def image():
    buffer = BytesIO()
    Image.new("RGB", (8, 8), "blue").save(buffer, format="PNG")
    return buffer.getvalue()


def test_authenticated_csrf_bootstrap_and_missing_cookie_recovery(scenario):
    client = scenario["client"]()
    scenario["auth"](client, "csrf@example.com")
    original = client.cookies["findit_csrf"]
    assert client.get("/api/v1/auth/csrf").json()["csrf_token"] == original
    assert (
        scenario["write"](
            client, "PATCH", "/api/v1/profile", json={"full_name": "Still Works"}
        ).status_code
        == 200
    )
    client.cookies.delete("findit_csrf")
    recovered = client.get("/api/v1/auth/csrf").json()["csrf_token"]
    assert recovered != original
    assert (
        scenario["write"](
            client, "PATCH", "/api/v1/profile", json={"full_name": "Recovered User"}
        ).status_code
        == 200
    )
    assert scenario["write"](client, "POST", "/api/v1/auth/logout").status_code == 204


@pytest.mark.parametrize(
    "schema,field",
    [
        (ReportUpdate, "occurred_at"),
        (ReportUpdate, "item_name"),
        (ReportUpdate, "description"),
        (ReportUpdate, "category_id"),
        (CustodyUpdate, "storage_location"),
        (CategoryUpdate, "name"),
        (CategoryUpdate, "is_active"),
        (LocationUpdate, "name"),
        (LocationUpdate, "is_active"),
        (AdminUserUpdate, "role"),
        (AdminUserUpdate, "is_active"),
    ],
)
def test_patch_rejects_explicit_null_but_allows_omission(schema, field):
    with pytest.raises(ValidationError):
        schema.model_validate({field: None})
    assert schema().model_dump(exclude_unset=True) == {}


def test_nullable_patch_fields_can_still_be_cleared():
    assert ReportUpdate(location_id=None).model_dump(exclude_unset=True) == {"location_id": None}
    assert CustodyUpdate(notes=None).model_dump(exclude_unset=True) == {"notes": None}
    assert CategoryUpdate(description=None).model_dump(exclude_unset=True) == {"description": None}


def test_moderation_cannot_replace_custody_or_handover(scenario):
    admin, _ = admin_client(scenario)
    finder = scenario["client"]()
    scenario["auth"](finder, "finder@example.com")
    report = scenario["write"](
        finder, "POST", "/api/v1/reports", json=scenario["report"]("found")
    ).json()
    endpoint = f"/api/v1/admin/reports/{report['id']}/status"
    for status in ["matched", "in_custody", "returned"]:
        response = scenario["write"](
            admin, "PATCH", endpoint, json={"status": status, "reason": "Moderation test"}
        )
        assert response.status_code == 409, response.text
    assert (
        scenario["write"](
            admin, "PATCH", endpoint, json={"status": "archived", "reason": "Duplicate report"}
        ).status_code
        == 204
    )
    assert (
        scenario["write"](
            admin, "PATCH", endpoint, json={"status": "open", "reason": "Restore report"}
        ).status_code
        == 204
    )
    custody = scenario["write"](
        admin,
        "POST",
        "/api/v1/staff/custody",
        json={"report_id": report["id"], "storage_location": "Locker A"},
    )
    assert custody.status_code == 201, custody.text
    for status in ["open", "archived", "returned"]:
        assert (
            scenario["write"](
                admin, "PATCH", endpoint, json={"status": status, "reason": "Bypass attempt"}
            ).status_code
            == 409
        )
    assert scenario["write"](finder, "DELETE", f"/api/v1/reports/{report['id']}").status_code == 409
    assert finder.get(f"/api/v1/reports/{report['id']}").json()["status"] == "in_custody"


def test_moderation_protects_claim_history(scenario):
    admin, _ = admin_client(scenario)
    owner, finder = scenario["client"](), scenario["client"]()
    scenario["auth"](owner, "owner@example.com")
    scenario["auth"](finder, "finder@example.com")
    found = scenario["write"](
        finder, "POST", "/api/v1/reports", json=scenario["report"]("found")
    ).json()
    assert (
        scenario["write"](
            owner,
            "POST",
            f"/api/v1/reports/{found['id']}/claims",
            json={"proof_text": "I own these headphones and know their serial number."},
        ).status_code
        == 201
    )
    response = scenario["write"](
        admin,
        "PATCH",
        f"/api/v1/admin/reports/{found['id']}/status",
        json={"status": "archived", "reason": "Hide claimed item"},
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "claim_history_exists"


def test_required_null_patch_returns_validation_errors(scenario):
    admin, user = admin_client(scenario)
    report = scenario["write"](
        admin, "POST", "/api/v1/reports", json=scenario["report"]("found")
    ).json()
    custody = scenario["write"](
        admin,
        "POST",
        "/api/v1/staff/custody",
        json={"report_id": report["id"], "storage_location": "Locker A"},
    ).json()
    for path, patch in [
        (f"/api/v1/reports/{report['id']}", {"occurred_at": None}),
        (f"/api/v1/staff/custody/{custody['id']}", {"storage_location": None}),
        (f"/api/v1/admin/users/{user['id']}", {"role": None}),
        (f"/api/v1/admin/users/{user['id']}", {"is_active": None}),
        (f"/api/v1/admin/categories/{scenario['category_id']}", {"name": None}),
        (f"/api/v1/admin/locations/{scenario['location_id']}", {"is_active": None}),
    ]:
        response = scenario["write"](admin, "PATCH", path, json=patch)
        assert response.status_code == 422, response.text


def test_last_administrator_cannot_be_demoted(scenario):
    admin, user = admin_client(scenario)
    response = scenario["write"](
        admin, "PATCH", f"/api/v1/admin/users/{user['id']}", json={"role": "student"}
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "last_admin"


def test_postgresql_concurrent_admin_demotions(scenario):
    with scenario["session"]() as db:
        if db.bind.dialect.name != "postgresql":
            pytest.skip("requires PostgreSQL transaction locks")
    first = admin_client(scenario, "firstadmin@example.com")
    second = admin_client(scenario, "secondadmin@example.com")
    barrier = Barrier(2)

    def demote(pair):
        client, user = pair
        barrier.wait(timeout=10)
        return scenario["write"](
            client, "PATCH", f"/api/v1/admin/users/{user['id']}", json={"role": "student"}
        ).status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(demote, [first, second]))
    assert sorted(results) == [200, 409]
    with scenario["session"]() as db:
        assert (
            len(
                list(db.scalars(select(User).where(User.role == "admin", User.is_active.is_(True))))
            )
            == 1
        )


def test_login_ip_limit_cannot_be_bypassed_by_rotating_accounts(scenario, monkeypatch):
    from types import SimpleNamespace
    from app.services import rate_limits

    # Keep this admission test within one fixed window even at a wall-clock boundary.
    monkeypatch.setattr(rate_limits, "time", SimpleNamespace(time=lambda: 1_000_000))
    scenario["settings"].login_ip_attempt_limit = 2
    client = scenario["client"]()
    client.get("/api/v1/auth/csrf")
    for index in range(3):
        response = scenario["write"](
            client,
            "POST",
            "/api/v1/auth/login",
            json={"email": f"unknown{index}@example.com", "password": "WrongPassword123"},
        )
        assert response.status_code == (401 if index < 2 else 429)
    assert int(response.headers["Retry-After"]) > 0


def test_registration_is_rate_limited_before_account_creation(scenario):
    scenario["settings"].registration_attempt_limit = 1
    client = scenario["client"]()
    scenario["auth"](client, "first@example.com")
    response = scenario["write"](
        client,
        "POST",
        "/api/v1/auth/register",
        json={
            "email": "second@example.com",
            "full_name": "Second User",
            "password": "ValidPassword123!",
        },
    )
    assert response.status_code == 429
    with scenario["session"]() as db:
        assert db.scalar(select(User).where(User.email == "second@example.com")) is None


def test_rate_buckets_are_shared_and_expire(scenario, monkeypatch):
    from app.services import rate_limits

    monkeypatch.setattr(rate_limits.time, "time", lambda: 1000)
    with scenario["session"]() as db:
        admit(db, [("identity@example.com", 1)], 100)
    with scenario["session"]() as db:
        with pytest.raises(APIError) as error:
            admit(db, [("identity@example.com", 1)], 100)
        assert error.value.status_code == 429
        assert db.scalar(select(AuthRateBucket.key)) != "identity@example.com"
    monkeypatch.setattr(rate_limits.time, "time", lambda: 1400)
    with scenario["session"]() as db:
        admit(db, [("new identity", 1)], 100)
        assert len(list(db.scalars(select(AuthRateBucket)))) == 1


def test_evidence_count_and_total_storage_quota(scenario):
    owner, finder = scenario["client"](), scenario["client"]()
    scenario["auth"](owner, "owner@example.com")
    scenario["auth"](finder, "finder@example.com")
    found = scenario["write"](
        finder, "POST", "/api/v1/reports", json=scenario["report"]("found")
    ).json()
    claim = scenario["write"](
        owner,
        "POST",
        f"/api/v1/reports/{found['id']}/claims",
        json={"proof_text": "I own the headphones and can identify the serial."},
    ).json()
    scenario["settings"].max_claim_evidence_images = 1
    path = f"/api/v1/claims/{claim['id']}/evidence"
    upload = lambda: scenario["write"](
        owner, "POST", path, files={"file": ("proof.png", image(), "image/png")}
    )
    assert upload().status_code == 201
    assert upload().json()["error"]["code"] == "evidence_limit"
    scenario["settings"].max_claim_evidence_images = 5
    scenario["settings"].max_user_upload_bytes = 1
    response = upload()
    assert response.status_code == 413
    assert response.json()["error"]["code"] == "upload_quota"
    with scenario["session"]() as db:
        assert (
            len(
                list(
                    db.scalars(select(ClaimEvidence).where(ClaimEvidence.evidence_type == "image"))
                )
            )
            == 1
        )
    assert len(list(scenario["media_root"].rglob("*.png"))) == 1


def test_report_upload_quota_also_applies_to_admin_uploads(scenario):
    admin, _ = admin_client(scenario)
    finder = scenario["client"]()
    scenario["auth"](finder, "finder@example.com")
    found = scenario["write"](
        finder, "POST", "/api/v1/reports", json=scenario["report"]("found")
    ).json()
    path = f"/api/v1/reports/{found['id']}/images"
    response = scenario["write"](
        finder, "POST", path, files={"file": ("item.png", image(), "image/png")}
    )
    assert response.status_code == 201
    scenario["settings"].max_user_upload_bytes = response.json()["byte_size"]
    response = scenario["write"](
        admin, "POST", path, files={"file": ("another.png", image(), "image/png")}
    )
    assert response.status_code == 413
    with scenario["session"]() as db:
        assert len(list(db.scalars(select(ReportImage)))) == 1


def test_postgresql_concurrent_uploads_cannot_exceed_user_quota(scenario):
    from app.storage import validate_image

    with scenario["session"]() as db:
        if db.bind.dialect.name != "postgresql":
            pytest.skip("requires PostgreSQL quota admission locks")
    first, second = scenario["client"](), scenario["client"]()
    scenario["auth"](first, "quota@example.com")
    second.cookies.update(first.cookies)
    reports = [
        scenario["write"](first, "POST", "/api/v1/reports", json=scenario["report"]("lost")).json()
        for _ in range(2)
    ]
    content = image()
    size = validate_image(content, "image/png", 1024).byte_size
    scenario["settings"].max_user_upload_bytes = size
    barrier = Barrier(2)

    def upload(pair):
        client, report = pair
        barrier.wait(timeout=10)
        return scenario["write"](
            client,
            "POST",
            f"/api/v1/reports/{report['id']}/images",
            files={"file": ("item.png", content, "image/png")},
        ).status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(upload, zip([first, second], reports)))
    assert sorted(results) == [201, 413]
    with scenario["session"]() as db:
        assert len(list(db.scalars(select(ReportImage)))) == 1


def test_postgresql_rate_admission_is_atomic_across_sessions(scenario):
    with scenario["session"]() as db:
        if db.bind.dialect.name != "postgresql":
            pytest.skip("requires PostgreSQL upsert concurrency")
    barrier = Barrier(2)

    def request(_):
        with scenario["session"]() as db:
            barrier.wait(timeout=10)
            try:
                admit(db, [("shared account", 1)], 300)
                return 200
            except APIError as error:
                return error.status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(request, range(2))) == [200, 429]
