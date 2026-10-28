"""Production configuration and untrusted upload regression tests."""
from io import BytesIO

import pytest
from PIL import Image
from pydantic import ValidationError

from app.config import Settings
from app.errors import APIError
from app.storage import validate_image


def prod(**overrides):
    """No production env-file secrets in tests; explicit defaults override env."""
    args = dict(
        environment="production",
        database_url="postgresql+psycopg://test:test@localhost/test",
        require_email_verification=True,
        mail_backend="smtp",
        smtp_host="smtp.example.edu",
        secret_key="test-only-key-with-more-than-32-characters-123456",
        cookie_secure=True,
        public_base_url="https://findit.example.edu",
        allowed_origins=["https://findit.example.edu"],
        trusted_hosts=["findit.example.edu"],
    )
    args.update(overrides)
    return Settings(**args)


def test_production_accepts_secure_configuration():
    assert prod().environment == "production"


@pytest.mark.parametrize(
    "overrides",
    [
        {"secret_key": "development-only-change-me"},
        {"secret_key": "short"},
        {"cookie_secure": False},
        {"public_base_url": "http://findit.example.edu"},
        {"allowed_origins": ["http://findit.example.edu"]},
        {"allowed_origins": ["*"]},
        {"trusted_hosts": ["*"]},
        {"trusted_hosts": []},
        {"trusted_hosts": ["*.example.edu"]},
        {"require_email_verification": False},
        {"allowed_email_domains": []},
        {"mail_backend": "file"},
        {"smtp_security": "none"},
        {"smtp_host": "REPLACE_WITH_SMTP_HOST"},
        {"database_url": "sqlite:///production.db"},
        {"allowed_origins": ["https://different.example.edu"]},
        {"public_base_url": "https://findit.example.edu/path"},
        {"public_base_url": "https://user:pass@findit.example.edu"},
    ],
)
def test_production_rejects_insecure_defaults(overrides):
    with pytest.raises(ValidationError):
        prod(**overrides)


def test_invalid_environment_rejected():
    with pytest.raises(ValidationError):
        Settings(environment="typo")


def test_image_upload_strips_exif_metadata():
    photo = Image.new("RGB", (8, 8), "red")
    exif = Image.Exif()
    exif[270] = "Sensitive original metadata must not survive"
    buffer = BytesIO()
    photo.save(buffer, format="JPEG", exif=exif)
    validated = validate_image(buffer.getvalue(), "image/jpeg", 2_000_000)
    with Image.open(BytesIO(validated.content)) as reloaded:
        assert reloaded.size == (8, 8)
        assert not reloaded.getexif()
    assert validated.byte_size == len(validated.content)


def test_upload_rejects_fake_image():
    with pytest.raises(APIError) as error:
        validate_image(b"not an image", "image/jpeg", 2_000_000)
    assert error.value.status_code == 422


def test_live_and_health_routes(scenario):
    client = scenario["client"]()
    live = client.get("/api/v1/live")
    assert live.status_code == 200
    assert live.json() == {"status": "ok"}
    health = client.get("/api/v1/health")
    assert health.status_code == 200
    assert health.json()["database"] == "ok"
    assert live.headers["X-Content-Type-Options"] == "nosniff"



def test_invalid_deployment_errors_do_not_echo_credentials():
    secret = "synthetic-credential-that-must-not-appear-in-errors-123"
    with pytest.raises(ValidationError) as error:
        prod(secret_key=secret, cookie_secure=False)
    assert secret not in str(error.value)
    assert secret not in repr(prod(secret_key=secret))
