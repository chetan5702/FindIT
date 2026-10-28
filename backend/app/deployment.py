"""Read-only deployment preflight. Output never includes connection secrets."""

import smtplib
import ssl
import tempfile
from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import select, text

from app.config import get_settings
from app.database import SessionLocal


def check_deployment(args):
    settings = get_settings()
    if settings.environment not in {"staging", "production"}:
        raise SystemExit("Preflight requires staging/production settings")
    try:
        with SessionLocal() as db:
            db.execute(select(1))
            deployed = set(db.scalars(text("SELECT version_num FROM alembic_version")))
            config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
            config.set_main_option(
                "script_location", str(Path(__file__).resolve().parents[1] / "alembic")
            )
            expected = set(ScriptDirectory.from_config(config).get_heads())
            if deployed != expected:
                raise ValueError("schema revision differs from release")
        settings.media_root.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryFile(dir=settings.media_root) as handle:
            handle.write(b"findit-preflight")
            handle.flush()
        factory = smtplib.SMTP_SSL if settings.smtp_security == "tls" else smtplib.SMTP
        options = {"timeout": settings.smtp_timeout_seconds}
        if settings.smtp_security == "tls":
            options["context"] = ssl.create_default_context()
        with factory(settings.smtp_host, settings.smtp_port, **options) as client:
            if settings.smtp_security == "starttls":
                client.starttls(context=ssl.create_default_context())
            if settings.smtp_username:
                client.login(settings.smtp_username, settings.smtp_password.get_secret_value())
            code, _ = client.noop()
            if code != 250:
                raise ValueError("SMTP relay is not healthy")
        print(
            "PASS: configuration, schema revision, database, media write and encrypted SMTP authentication"
        )
        print(
            "No email sent. Verify delivery and public HTTPS with synthetic accounts before opening registration."
        )
        return 0
    except Exception:
        # Exception details may contain DB URLs, SMTP credentials or infrastructure names.
        print(
            "FAIL: preflight could not validate database/schema, media permissions or SMTP. Inspect protected service diagnostics."
        )
        return 1
