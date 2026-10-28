# FindIt Next 2.0 — Verification record (repair release 2026-10-24)

This document distinguishes actual execution in the repair environment from checks that remain necessary on a machine with Docker and npm registry access.

## Completed checks

| Check | Environment and command | Result |
|---|---|---|
| API integration regression suite | Python 3.13, `cd backend && python -m pytest -q` | **8 passed** |
| Backend statement coverage | `cd backend && python -m pytest -q --cov=app --cov-report=term-missing:skip-covered` | **8 passed; 73% statements** (includes CLI and seed modules with 0% coverage) |
| Fresh database schema migration | SQLite temporary database, `FINDIT_DATABASE_URL=sqlite:////tmp/findit_repaired_validate_20261024.db alembic upgrade head` | **Passed**, applied revision `f312b10f7098` |
| Migration metadata comparison | `alembic check` against the same upgraded SQLite database | **Passed:** no pending ORM/schema changes |
| Schema objects | SQLAlchemy inspector after migration | **12 application tables** plus `alembic_version` |
| Python compilation | `python -m compileall -q app alembic tests` | **Passed** |
| Archive credentials | Clean ZIP content scan after packaging | **Passed** (no `.env`, Git metadata, Python caches, installed packages, or media) |

Regression tests use isolated, ephemeral SQLite databases and FastAPI TestClient. They cover fresh registration and CSRF, public discovery, archived-list privacy, empty input validation, staff permissions, claim conflicts, evidence authorization, custody, approvals, handover, notifications, report lifecycle, and audit logging. These tests do **not** prove the same behavior under concurrent PostgreSQL transactions.

## Not verified here

| Check | Reason and action |
|---|---|
| PostgreSQL-backed migration and concurrency | Docker and PostgreSQL executables unavailable. Run fresh Compose on your development machine; then execute API integration tests against PostgreSQL or add a dedicated PostgreSQL fixture. |
| Frontend dependency resolution, TypeScript/Vite build | npm registry DNS unavailable; dependencies and `package-lock.json` could not be generated. On a machine with npm access, run `cd frontend`, `npm install`, `npm run build`, `npm run test:run`. Commit resulting `package-lock.json` before production use. |
| Vitest UI/API tests | Test source and setup created, but tests could not execute here without frontend dependencies. |
| Playwright mobile/desktop browser flows | No browser/container stack could be launched here. Install Playwright Chromium on the host and run against a healthy Compose stack. |
| Container startup and service health | Docker unavailable here; run `docker compose up --build -d` and `docker compose ps` on Windows. |
| Production security/readiness | Not audited. Requires institutional privacy policy, SSO/email verification, backup and restore, scale controls, and deployment-specific testing. |

## First-run verification on Windows

```powershell
# From the extracted FindIT folder; Docker Desktop must be running
powershell -ExecutionPolicy Bypass -File .\scripts\dev.ps1 setup
powershell -ExecutionPolicy Bypass -File .\scripts\dev.ps1 up-detached
docker compose ps
docker compose exec backend python -m app.seed
# Student/frontend at http://localhost:5173
# API docs at http://localhost:8000/docs
# Check backend tests and frontend tests
docker compose run --rm backend pytest -q
docker compose run --rm frontend npm run test:run
# Frontend build using Compose's installed dependencies
docker compose run --rm frontend npm run build
```

If a command fails, read the service logs (`docker compose logs --tail=150 backend frontend db`) and fix the actual error. Do not delete volumes to fix an unrelated application issue.


## Updated hardening verification (2026-10-25)

This is a new run against the updated candidate; the older October 24 table above is retained as the original record.

- **21 backend tests passed:** `cd backend && pytest -q`. Includes the original eight workflow tests plus production setting rejection, image metadata sanitization, and health endpoints.
- **Python compilation succeeded:** `python -m compileall -q app alembic tests`.
- **Production Compose parsed as YAML:** db, backend, frontend, gateway. **Docker was not available**, so no container images or TLS route have been launched.
- **Frontend build and Vitest are not verified:** npm dependencies could not be obtained from the registry, and the original project has no committed lockfile.
- **PostgreSQL tests and browser E2E remain unverified**; backend integration tests use isolated SQLite fixtures.
- **Single-college installation only:** no cross-college tenant isolation yet. See `docs/production-release.md`.
