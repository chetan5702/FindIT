from functools import lru_cache
from pathlib import Path
from urllib.parse import urlsplit
from typing import Literal
from pydantic import SecretStr

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="FINDIT_",
        case_sensitive=False,
        extra="ignore",
        hide_input_in_errors=True,
    )

    environment: str = "development"
    allowed_email_domains: list[str] = ["suh.edu.in"]
    require_email_verification: bool = False
    mail_backend: Literal["smtp", "file"] = "file"
    mail_directory: Path = Path("./work/mail")
    mail_from: str = "FindIt <noreply@suh.edu.in>"
    smtp_host: str = ""
    smtp_port: int = Field(default=587, ge=1, le=65535)
    smtp_username: str = ""
    smtp_password: SecretStr = SecretStr("")
    smtp_security: Literal["starttls", "tls", "none"] = "starttls"
    smtp_timeout_seconds: int = Field(default=10, ge=1, le=30)
    verification_ttl_minutes: int = Field(default=60, ge=5, le=1440)
    reset_ttl_minutes: int = Field(default=20, ge=5, le=60)
    identity_request_limit: int = Field(default=5, ge=1)
    identity_ip_request_limit: int = Field(default=20, ge=1)
    database_url: str = Field(default="postgresql+psycopg://findit:findit@db:5432/findit", repr=False)
    secret_key: str = Field(default="development-only-change-me", repr=False)
    allowed_origins: list[str] = ["http://localhost:5173"]
    media_root: Path = Path("/data/media")
    public_base_url: str = "http://localhost:5173"
    session_ttl_hours: int = Field(default=168, ge=1, le=720)
    cookie_secure: bool = False
    trusted_hosts: list[str] = ["localhost", "127.0.0.1", "testserver"]
    max_upload_bytes: int = Field(default=5 * 1024 * 1024, ge=1024)
    max_report_images: int = Field(default=5, ge=1, le=10)
    login_attempt_limit: int = Field(default=8, ge=1)
    login_ip_attempt_limit: int = Field(default=40, ge=1)
    registration_attempt_limit: int = Field(default=20, ge=1)
    max_claim_evidence_images: int = Field(default=5, ge=1, le=20)
    max_user_upload_bytes: int = Field(default=100 * 1024 * 1024, ge=1024)
    login_attempt_window_seconds: int = Field(default=300, ge=10)

    @field_validator("allowed_email_domains")
    @classmethod
    def domains(cls, values):
        import re

        normalized = sorted({value.strip().lower() for value in values})
        if any(
            not re.fullmatch(r"[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?\.[a-z]{2,}", value) or ".." in value
            for value in normalized
        ):
            raise ValueError("Email domains must be exact DNS names")
        return normalized

    @model_validator(mode="after")
    def validate_deployment_security(self) -> "Settings":
        if self.environment not in {"development", "test", "staging", "production"}:
            raise ValueError("FINDIT_ENVIRONMENT must be development, test, staging or production")
        if self.environment in {"staging", "production"}:
            public = urlsplit(self.public_base_url)
            if (
                public.scheme != "https"
                or not public.hostname
                or public.username
                or public.password
                or public.path not in {"", "/"}
                or public.query
                or public.fragment
            ):
                raise ValueError("PUBLIC_BASE_URL must be a canonical HTTPS origin")
            canonical = f"https://{public.netloc}"
            if self.allowed_origins != [canonical] or public.hostname not in self.trusted_hosts:
                raise ValueError(
                    "Use a same-origin frontend/API and include its hostname in trusted hosts"
                )
            if not self.database_url.startswith("postgresql+psycopg://"):
                raise ValueError("Staging/production requires PostgreSQL")
            if not self.allowed_email_domains or not self.require_email_verification:
                raise ValueError(
                    "Staging/production requires institutional domains and email verification"
                )
            if self.mail_backend != "smtp" or not self.smtp_host or self.smtp_security == "none":
                raise ValueError("Staging/production requires encrypted SMTP delivery")
            if self.smtp_username and not self.smtp_password.get_secret_value():
                raise ValueError("SMTP credentials are incomplete")
            if any(
                "REPLACE_" in value.upper() or "CHANGE_ME" in value.upper()
                for value in (
                    self.smtp_host,
                    self.smtp_username,
                    self.smtp_password.get_secret_value(),
                )
            ):
                raise ValueError("Replace SMTP placeholders before deployment")
            from email.utils import parseaddr
            from email_validator import validate_email

            validate_email(parseaddr(self.mail_from)[1], check_deliverability=False)
            if any("*" in hostname for hostname in self.trusted_hosts):
                raise ValueError("Trusted hosts must be exact names")
            if self.smtp_host.startswith(("http://", "https://")):
                raise ValueError("SMTP host must be a hostname, not a URL")
            if any(
                marker in self.secret_key.upper() for marker in ("REPLACE_", "CHANGE_ME", "EXAMPLE")
            ):
                raise ValueError("Replace the placeholder secret")
            if not self.cookie_secure:
                raise ValueError("FINDIT_COOKIE_SECURE must be true for staging/production")
            if not self.public_base_url.startswith("https://"):
                raise ValueError("FINDIT_PUBLIC_BASE_URL must use HTTPS for staging/production")
            if not self.allowed_origins or any(
                not origin.startswith("https://") or "*" in origin
                for origin in self.allowed_origins
            ):
                raise ValueError("FINDIT_ALLOWED_ORIGINS must contain only explicit HTTPS origins")
            if not self.trusted_hosts or "*" in self.trusted_hosts:
                raise ValueError("FINDIT_TRUSTED_HOSTS must list explicit hostnames")
            if self.secret_key == "development-only-change-me":
                raise ValueError("Replace the development default secret key")
        return self

    @field_validator("secret_key")
    @classmethod
    def validate_secret(cls, value: str, info):
        environment = info.data.get("environment", "development")
        if environment in {"production", "staging"} and len(value) < 32:
            raise ValueError("FINDIT_SECRET_KEY must be at least 32 characters outside development")
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
