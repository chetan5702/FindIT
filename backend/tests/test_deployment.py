from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
import yaml

from app.services.mail import deliver
from app.config import Settings

ROOT = Path(__file__).resolve().parents[2]


def test_production_topology_keeps_api_and_database_private():
    config = yaml.safe_load((ROOT / "docker-compose.prod.yml").read_text())
    services = config["services"]
    assert all("ports" not in services[name] for name in ["db", "backend", "frontend", "migrate"])
    assert services["backend"]["environment"]["FINDIT_AUTO_MIGRATE"] == "false"
    assert (
        services["backend"]["depends_on"]["migrate"]["condition"]
        == "service_completed_successfully"
    )
    assert services["backend"]["read_only"] and services["migrate"]["read_only"]
    assert services["backend"]["environment"]["FORWARDED_ALLOW_IPS"] != "*"
    assert config["networks"]["proxy"]["internal"]
    assert config["networks"]["database"]["internal"]
    assert "database" not in services["gateway"]["networks"]
    assert services["backend"]["healthcheck"]["test"][-1] == "app.healthcheck"


def test_container_healthcheck_uses_public_host_and_ignores_host_proxy(monkeypatch):
    from app import healthcheck

    settings = Settings(public_base_url="https://findit.suh.edu.in")
    monkeypatch.setattr(healthcheck, "get_settings", lambda: settings)
    opener = MagicMock()
    response = opener.open.return_value.__enter__.return_value
    response.status = 200
    monkeypatch.setattr(healthcheck.urllib.request, "build_opener", lambda handler: opener)
    healthcheck.main()
    request = opener.open.call_args.args[0]
    assert request.full_url == "http://127.0.0.1:8000/api/v1/health"
    assert request.get_header("Host") == "findit.suh.edu.in"


def test_smtp_transport_requires_verified_tls_before_authentication(monkeypatch):
    settings = Settings(
        mail_backend="smtp",
        smtp_host="smtp.example.edu",
        smtp_username="sender",
        smtp_password="test-secret",
    )
    client = MagicMock()
    client.__enter__.return_value = client
    monkeypatch.setattr("app.services.mail.smtplib.SMTP", lambda *a, **k: client)
    deliver(settings, "student@suh.edu.in", "Verify", "test token")
    assert client.starttls.called
    import ssl

    assert client.starttls.call_args.kwargs["context"].verify_mode == ssl.CERT_REQUIRED
    assert client.starttls.call_args.kwargs["context"].check_hostname
    assert [call[0] for call in client.method_calls][:3] == ["starttls", "login", "send_message"]


def test_backup_restore_refuses_checksum_mismatch_before_docker(tmp_path, monkeypatch):
    import importlib.util, json

    spec = importlib.util.spec_from_file_location(
        "backup_restore", ROOT / "scripts/backup_restore.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    (tmp_path / "database.dump").write_bytes(b"original")
    (tmp_path / "media.tar.gz").write_bytes(b"not a real archive")
    (tmp_path / "manifest.json").write_text(
        json.dumps({"files": {"database.dump": "wrong", "media.tar.gz": "wrong"}, "schema": "test"})
    )
    monkeypatch.setattr(
        module,
        "compose",
        lambda *a, **k: pytest.fail("Docker must not be called for a corrupt backup"),
    )
    with pytest.raises(ValueError, match="checksum"):
        module.restore(SimpleNamespace(directory=tmp_path, confirm_empty_target=True))
