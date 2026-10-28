# FindIt Next 2.0 — Campus Recovery Network

FindIt Next is a mobile-first campus lost-and-found application. Students submit lost and found reports, receive explainable match suggestions, provide private ownership evidence, and follow claims through a staff-verified handover. Campus staff manage custody and claim decisions; administrators manage reference data, permissions, moderation, and operational history.

This repository is a modular monolith with implemented application workflows. See verification notes before treating it as production-ready:

- React, TypeScript, Vite, Tailwind CSS, React Router, TanStack Query, React Hook Form, Zod
- Python 3.12, FastAPI, Pydantic, SQLAlchemy, Alembic
- PostgreSQL 16 and persistent local media storage
- pytest, Vitest/React Testing Library, and Playwright
- Docker Compose for the local development topology

See [Architecture](docs/architecture.md), [Security and threat model](docs/security.md), [API conventions](docs/api-conventions.md), and the honest [Verification record](docs/verification.md).

## Prerequisites

The recommended setup needs Docker Desktop with Docker Compose v2, Git, and roughly 4 GB of free memory. PowerShell 7 is recommended on Windows. A native setup is possible with Python 3.12, Node.js 20 LTS, and PostgreSQL 16, but Docker Compose is the supported baseline.

## Quick start

From the repository root in PowerShell:

```powershell
./scripts/dev.ps1 setup
./scripts/dev.ps1 up
```

The setup command creates an ignored `.env` file and fills its development secrets with cryptographically random values. It never overwrites an existing `.env`.

Once all three health checks pass:

- Application: <http://localhost:5173>
- API documentation: <http://localhost:8000/docs>
- API health: <http://localhost:8000/api/v1/health>

On macOS/Linux, copy `.env.example` to `.env`, replace every `CHANGE_ME` value with independent random values, and run `docker compose up --build`. The provided `Makefile` exposes equivalent short commands for environments with `make`.

The backend container waits for PostgreSQL and runs `alembic upgrade head` before starting FastAPI. Source is bind-mounted for hot reload. The `postgres_data` and `media_data` named volumes preserve database records and uploads across ordinary restarts and `docker compose down`.

Do not use `docker compose down --volumes` unless intentionally deleting all local database and uploaded-media data.

## First administrator

Public registration always creates a student. It cannot create staff or administrators. After the services are running, create the first administrator through the interactive backend command:

```powershell
./scripts/dev.ps1 create-admin
```

Equivalent direct command:

```sh
docker compose exec backend python -m app.cli create-admin
```

The command prompts for account details and a password without storing credentials in source control or shell history. Use the administrator UI to grant the minimum required staff role to existing accounts. Role changes are enforced server-side and recorded in the audit trail.

## Demo data

Load development-only categories, locations, reports, claims, and clearly marked sample accounts with:

```powershell
./scripts/dev.ps1 seed
```

Equivalent direct command: `docker compose exec backend python -m app.seed`.

The seed command is intended to be repeatable and refuses to run in a production environment. Its terminal output identifies the sample accounts and development-only credentials created by the current seed implementation. Never reuse demo passwords or seed data for a deployed campus environment.

## Common commands

```powershell
./scripts/dev.ps1 up-detached   # build and start in the background
./scripts/dev.ps1 ps            # inspect service health
./scripts/dev.ps1 logs          # follow recent logs
./scripts/dev.ps1 migrate       # apply migrations explicitly
./scripts/dev.ps1 test          # backend then frontend tests
./scripts/dev.ps1 install-e2e   # one-time host Chromium/dependency install
./scripts/dev.ps1 test-e2e      # host-side Playwright; services must be running
./scripts/dev.ps1 down          # stop without deleting volumes
```

Pass a service name to logs (`./scripts/dev.ps1 logs backend`) or test selectors after a test command. Run `./scripts/dev.ps1 help` for the complete list.

## Native development

Docker is still required for PostgreSQL unless a compatible local database already exists.

Backend:

```powershell
docker compose up -d db
cd backend
python -m venv .venv
./.venv/Scripts/Activate.ps1
python -m pip install -r requirements-dev.txt
$env:FINDIT_DATABASE_URL = "postgresql+psycopg://findit:YOUR_PASSWORD@localhost:5432/findit"
alembic upgrade head
python -m uvicorn app.main:app --reload
```

Frontend, in another terminal:

```powershell
cd frontend
npm ci
npm run dev
```

When running the API natively, set the remaining values documented in `.env.example` and use a writable native `FINDIT_MEDIA_ROOT`. Do not load `.env` into a production shell.

## Test and validation workflows

Backend unit/integration tests:

```powershell
./scripts/dev.ps1 test-backend
```

Frontend unit/component tests:

```powershell
./scripts/dev.ps1 test-frontend
```

Browser tests run on the host because the small Alpine development image does not include compatible browser binaries. They require Node.js 20.19 or newer, a one-time dependency/browser install, and healthy running services:

```powershell
./scripts/dev.ps1 install-e2e
./scripts/dev.ps1 up-detached
./scripts/dev.ps1 test-e2e
```

For a clean migration check without deleting a developer's current data, use a separate Compose project/volume set rather than removing the normal volumes. Actual results for this checkout belong in `docs/verification.md`; no workflow should be described as passing unless its command was executed successfully.

## Product workflows

1. A student registers, signs in, and creates a lost report with public description and optional private ownership details.
2. Another student creates a complementary found report. Images are validated and stored through the media abstraction.
3. The deterministic matcher scores all eligible complementary reports and returns ranked reasons. Scores are heuristic relevance values, not calibrated probabilities.
4. A student submits a claim with private evidence. Self-claims and duplicate/conflicting active claims are rejected by the backend.
5. Authorized staff record custody, review evidence, and approve or reject the claim through a server-enforced state machine.
6. Staff complete a handover. The handover, claimant, staff member, timestamp, state updates, notification, and audit event are recorded atomically. A completed handover cannot be reopened through ordinary student controls.

QR codes generated for campus locations only preselect the reporting location. They are never treated as proof that the reporter was present or that an item is authentic.

## Configuration

`.env.example` documents every required local value. Important settings include:

| Variable | Purpose |
|---|---|
| `FINDIT_DATABASE_URL` | SQLAlchemy PostgreSQL connection URL used inside Compose |
| `FINDIT_SECRET_KEY` | High-entropy session/application signing secret |
| `FINDIT_ALLOWED_ORIGINS` | Exact JSON array of browser origins permitted by CORS |
| `FINDIT_COOKIE_SECURE` | Must be `true` behind production HTTPS |
| `FINDIT_MEDIA_ROOT` | Storage adapter root inside the backend container |
| `FINDIT_MAX_UPLOAD_BYTES` | Server-side byte limit for each uploaded image |
| `VITE_API_URL` | Browser-visible API URL; empty locally to use the Vite proxy |

Compose interpolates `.env` before containers start and also passes appropriate settings to each application. After changing database credentials on an existing PostgreSQL volume, recreate credentials intentionally or start with a new development volume; PostgreSQL initialization variables do not modify an already initialized database.

## Security posture

Passwords use Argon2id. Authentication uses expiring, revocable server-side sessions in HTTP-only cookies, with CSRF protection for state changes. Authorization and object ownership are enforced in FastAPI. Report public/private projections are separated; claim evidence is restricted to its owner and authorized staff. Image uploads are limited by bytes and decoded MIME signature, assigned generated names, and served without trusting user paths.

Claim approvals and handovers use database transactions and conflict controls. Staff/admin creation is not exposed through public registration. Authentication admission limits use atomic shared database buckets for account and IP controls; deployment edge protection is still recommended. Review `docs/security.md` before using real student data.

No secrets belong in Git. `.env`, private keys, media, logs, coverage, and local database files are ignored. Rotate any credential that is ever committed or pasted into a public log.

## Persistence and backups

Local database and upload data live in separate named Docker volumes. Restarting or rebuilding containers preserves both. A production backup must capture PostgreSQL and its referenced media consistently; restoring only one side can leave missing or orphaned images. The local filesystem adapter is a development choice, not a production durability promise.

## Known MVP limitations

- No university SSO, staff MFA, multi-university tenancy, or native mobile app; institutional email verification and password recovery are implemented
- In-app notifications poll; workflow notifications have no WebSockets, push, email, or SMS delivery (authentication email is implemented)
- Matching is deterministic text/category/location/time heuristics; the optional image-embedding adapter is inactive
- Local media storage has no antivirus scanning, CDN, lifecycle policy, or managed cross-zone durability
- Shared fixed-window authentication limits require trusted proxy configuration and deployment edge protection against distributed abuse
- QR codes are convenience links, not trustworthy presence or authenticity signals
- Operational metrics are intentionally basic, and data-retention policy must be established with campus stakeholders
- Accessibility and browser behavior still require verification on the campus-supported device/browser matrix

## Prioritized follow-up work

1. Run a campus privacy/security review; define retention, subject-access, deletion, incident, and evidence-handling policies.
2. Add university SSO and staff MFA while preserving verified institutional email flows.
3. Move media to malware-scanned object storage and validate shared database capacity for multi-instance deployment.
4. Add email/push notification adapters with user preferences and delivery auditing.
5. Measure matching quality on consented, anonymized outcomes before changing weights or enabling optional image embeddings.
6. Add production observability, scheduled off-host backups and recurring restore drills, dependency scanning, and a supported-browser accessibility matrix.

## Contributing principles

Keep the system a modular monolith. Prefer explicit domain invariants and narrow schemas over generic CRUD or mass assignment. Add an Alembic migration for every schema change. Add regression tests for authorization boundaries, state transitions, concurrency conflicts, private-field projection, uploads, and matching behavior. Never weaken a failing check to make a pipeline green; fix the underlying behavior or document a genuine environment limitation in the verification record.


## Production-hardening candidate

A separate production topology is provided in [`docker-compose.prod.yml`](docker-compose.prod.yml), with Caddy HTTPS termination, compiled frontend assets, non-public database/API networking, secure production configuration validation, and updated upload sanitization. This is **not** a claim of production approval. Before deploying with real student records or to multiple institutions, follow **[the complete production release runbook](docs/production-release.md)**. For a real deployment, do not use the development Compose file.


## Verified institutional identity and deployment update

Self-registration is restricted to the exact `suh.edu.in` email domain by default. Production requires email verification through an encrypted SMTP relay, and registration no longer establishes a session when verification is enabled. Verification asks the mailbox owner to choose a password; recovery/password changes revoke other devices. The profile page includes session controls. See [authentication](docs/authentication.md) for configuration and upgrade behavior.

Production now uses a separate migration service, bounded proxy trust, read-only API storage, a Host-aware readiness probe and a deployment preflight command. Consistent backup/restore and repeatable PostgreSQL/container verification tools are included. See the [release runbook](docs/production-release.md) and [actual verification results](docs/postgres-auth-deployment-verification.md).
