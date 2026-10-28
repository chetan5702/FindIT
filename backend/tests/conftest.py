"""Isolated API integration fixtures: no developer database is modified."""

import os

# Importing app.database constructs the global engine; ensure tests never target a real DB.
os.environ["FINDIT_DATABASE_URL"] = "sqlite+pysqlite:///:memory:"

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
import uuid
from sqlalchemy import text

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import Settings, get_settings
from app.database import Base, get_db
from app.main import app
from app.models import Category, Location, User
from app.security import hash_password
from app import models  # noqa: F401; ensure all models registered


@pytest.fixture
def scenario(tmp_path: Path) -> Iterator[dict]:
    """Each test gets a completely separate database and media directory."""
    test_url = os.environ.get("FINDIT_TEST_DATABASE_URL")
    schema = "test_" + uuid.uuid4().hex
    maintenance = None
    if test_url:
        if not test_url.startswith("postgresql"):
            raise ValueError("FINDIT_TEST_DATABASE_URL must be a disposable PostgreSQL database")
        maintenance = create_engine(test_url)
        with maintenance.begin() as connection:
            connection.execute(text(f'CREATE SCHEMA "{schema}"'))
        engine = create_engine(test_url, connect_args={"options": f"-csearch_path={schema}"})
    else:
        engine = create_engine(
            f"sqlite+pysqlite:///{tmp_path / 'findit-test.sqlite'}",
            connect_args={"check_same_thread": False},
        )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)

    def override_db():
        with factory() as db:
            yield db

    settings = Settings(
        media_root=tmp_path / "media",
        allowed_email_domains=[],
        require_email_verification=False,
        mail_directory=tmp_path / "mail",
    )
    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_settings] = lambda: settings
    with factory() as db:
        category = Category(name="Electronics", slug="electronics")
        location = Location(name="Library", slug="library")
        staff = User(
            email="staff@example.com",
            full_name="Campus Staff",
            role="staff",
            password_hash=hash_password("ValidPassword123!"),
        )
        db.add_all([category, location, staff])
        db.commit()
        category_id, location_id = str(category.id), str(location.id)
    clients = []

    def client():
        instance = TestClient(app)
        clients.append(instance)
        return instance

    def authenticate(instance: TestClient, email: str):
        csrf = instance.get("/api/v1/auth/csrf")
        assert csrf.status_code == 200, csrf.text
        response = instance.post(
            "/api/v1/auth/register",
            headers={"X-CSRF-Token": csrf.json()["csrf_token"]},
            json={"email": email, "full_name": "Test Student", "password": "ValidPassword123!"},
        )
        assert response.status_code == 201, response.text
        return response.json()["user"]

    def login_staff(instance: TestClient):
        csrf = instance.get("/api/v1/auth/csrf")
        response = instance.post(
            "/api/v1/auth/login",
            headers={"X-CSRF-Token": csrf.json()["csrf_token"]},
            json={"email": "staff@example.com", "password": "ValidPassword123!"},
        )
        assert response.status_code == 200, response.text

    def write(instance: TestClient, method: str, url: str, **kwargs):
        return instance.request(
            method,
            url,
            headers={**kwargs.pop("headers", {}), "X-CSRF-Token": instance.cookies["findit_csrf"]},
            **kwargs,
        )

    def report_payload(report_type: str, **extra):
        return {
            "report_type": report_type,
            "item_name": "Blue wireless headphones",
            "description": "Wireless over-ear headphones in a black case.",
            "category_id": category_id,
            "location_id": location_id,
            "occurred_at": (datetime.now(UTC) - timedelta(days=1)).isoformat(),
            "private_details": "Serial number ends in 1934",
            **extra,
        }

    yield {
        "client": client,
        "auth": authenticate,
        "staff": login_staff,
        "write": write,
        "report": report_payload,
        "category_id": category_id,
        "location_id": location_id,
        "session": factory,
        "media_root": settings.media_root,
        "settings": settings,
    }
    for instance in clients:
        instance.close()
    app.dependency_overrides.clear()
    engine.dispose()
    if maintenance is not None:
        with maintenance.begin() as connection:
            connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        maintenance.dispose()
