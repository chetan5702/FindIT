"""Bounded SMTP delivery; file sink is development/test only. Never log tokens."""

import logging
import os
import smtplib
import ssl
import uuid
import time
from email.message import EmailMessage

from app.config import Settings

logger = logging.getLogger("findit.mail")


def deliver(settings: Settings, recipient: str, subject: str, content: str) -> None:
    message = EmailMessage()
    message["From"] = settings.mail_from
    message["To"] = recipient
    message["Subject"] = subject
    message.set_content(content)
    try:
        if settings.mail_backend == "file":
            if settings.environment not in {"development", "test"}:
                raise ValueError("File mail is forbidden outside development/test")
            settings.mail_directory.mkdir(parents=True, exist_ok=True)
            target = settings.mail_directory / f"{time.time_ns():020d}-{uuid.uuid4().hex}.eml"
            fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "wb") as output:
                output.write(message.as_bytes())
            return
        factory = smtplib.SMTP_SSL if settings.smtp_security == "tls" else smtplib.SMTP
        options = {"timeout": settings.smtp_timeout_seconds}
        if settings.smtp_security == "tls":
            options["context"] = ssl.create_default_context()
        with factory(settings.smtp_host, settings.smtp_port, **options) as client:
            if settings.smtp_security == "starttls":
                client.starttls(context=ssl.create_default_context())
            if settings.smtp_username:
                client.login(settings.smtp_username, settings.smtp_password.get_secret_value())
            client.send_message(message)
    except Exception:
        # User can request another link; never leak SMTP credentials, recipient or link.
        logger.error("Authentication email delivery failed; inspect SMTP health and retry delivery")
