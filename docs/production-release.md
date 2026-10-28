# Production deployment and upgrade

This is a single-institution application configured for verified `suh.edu.in` email identities. It does not implement multi-institution tenancy. The institution must still approve retention, evidence handling, access administration and incident procedures before processing real student data.

## Required deployment settings

Copy `.env.production.example` to a protected local `.env.production`. Replace every placeholder, including independent random database/application secrets and URL-encoded database credentials. Set the actual public HTTPS hostname and exact matching `FINDIT_PUBLIC_BASE_URL`, `FINDIT_ALLOWED_ORIGINS` and `FINDIT_TRUSTED_HOSTS`. An email domain does not automatically establish public DNS or a web hostname.

Configure the actual SMTP host, verified sender, port, TLS mode, username and password locally or through a secret manager. No SMTP provider/credentials or deployment hostname were supplied in this task. Do not paste credentials into a chat or publish the environment file. Production refuses disabled verification, empty institutional domain restrictions, plaintext/file email delivery, placeholder secrets and inconsistent origins.

Docker Engine and Compose v2 are required on the deployment host. Only Caddy publishes ports 80/443. PostgreSQL, API and frontend remain unpublished; separate networks isolate the database and bound the API's forwarded-header trust to the Nginx proxy subnet. Choose an unused `FINDIT_PROXY_SUBNET` before initial installation. Never expose the API or reuse proxy trust settings in a different topology without review.

## Install or upgrade

From the repository root:

```sh
# Validate without dumping secrets to terminal output.
docker compose --env-file .env.production -f docker-compose.prod.yml config --quiet
# For an upgrade, take a consistent maintenance-window backup first (see below).
docker compose --env-file .env.production -f docker-compose.prod.yml up -d --build
docker compose --env-file .env.production -f docker-compose.prod.yml ps -a
docker compose --env-file .env.production -f docker-compose.prod.yml exec -T backend python -m app.cli check-deployment
```

A one-shot migration service waits for PostgreSQL and must succeed before the API starts. The production API has automatic startup migrations disabled, a read-only root filesystem, a writable media volume and bounded temporary storage. Its readiness probe sends the public Host header so TrustedHost validation stays enabled. This deployment is a coordinated upgrade, not a promise of zero-downtime migrations.

The identity migration intentionally revokes old sessions and requires existing users to verify their mailbox and choose a password. Notify users before rollout. First-time administrators use the interactive `create-admin` CLI; active pre-upgrade administrators can use the password-checked `verify-admin` console command described in [authentication.md](authentication.md).

Preflight checks production settings, database reachability, the exact Alembic revision, media write access and encrypted SMTP authentication. It sends no mail. Then verify the actual public TLS certificate, student verification delivery, password recovery, uploads, private evidence, staff approval and handover using synthetic accounts. Public `/docs`, `/redoc` and `/openapi.json` return 404.

## Consistent backups and empty-target restore

The scripts quiesce API writes during backup. Schedule a maintenance window; PostgreSQL/media must be captured together. Docker volumes alone are not backups. The backup folder contains private data: encrypt it and copy it off-host with restricted access.

```sh
python scripts/backup_restore.py --env-file .env.production backup /secure/backups/findit-YYYYMMDD --maintenance-window
```

The script stops the running API, captures a custom PostgreSQL dump and media archive, records schema/checksums, and restarts the API even if backup fails. It does not implement a cloud backup destination or retention service.

Restore only into a newly provisioned isolated destination with the API stopped and database/media empty:

```sh
python scripts/backup_restore.py --env-file .env.restore --project-name findit-restore restore /secure/backups/findit-YYYYMMDD --confirm-empty-target
```

Provision that destination's database service and backend image first. Restore refuses populated targets, unsafe archive paths and checksum mismatches. It leaves the destination API stopped for migration, preflight and workflow checks. A failed restore may leave the isolated target partially populated; do not retry over it. Provision a fresh target and investigate. The tool never automatically wipes an existing database/media volume.

For rollback, retain compatible application images and a tested restore point. Redeploying old code does not reverse a schema migration. Run `purge-auth` through the controlled operations scheduler, monitor readiness and delivery failures, and test restores regularly.

## Repeatable verification

- `scripts/verify_postgres.py --confirm-disposable-database`: requires `FINDIT_TEST_DATABASE_URL` pointing to an EMPTY disposable PostgreSQL database, installed backend/frontend dependencies and Playwright Chromium. Runs migrations, drift detection, the complete API suite, production frontend build, unit tests and verified-identity desktop/mobile workflows. Logs stay under ignored `work/`.
- `scripts/verify_containers.py`: Linux-only synthetic verification of the actual production Compose topology, HTTPS, STARTTLS mail, browser workflows and consistent Docker backup/restore. Requires Docker Compose 2.24.4+, OpenSSL, Node and Playwright. It generates unique Compose project names, test certificates and secrets, sends mail only to its test sink, and removes only its disposable containers/volumes. Real deployment files are never used.
- GitHub Actions includes PostgreSQL/API, frontend and production-container jobs. CI configuration is provided; a remote passing run must be observed before treating it as verified.

See [postgres-auth-deployment-verification.md](postgres-auth-deployment-verification.md) for actual local results and remaining environment-specific checks. Public DNS/certificate issuance, the institution's SMTP relay, container networking on the intended Linux host, off-host backup storage, privacy approval and supported-device testing remain deployment-owner responsibilities.
