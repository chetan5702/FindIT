# FindIt — Windows startup and professor demo

## Requirements
Install Docker Desktop and start it directly from the Windows Start menu. Wait for Engine running. Internet access is needed for the first image build. Extract the ZIP before running commands.

Open PowerShell in the extracted FindIT folder (the folder containing docker-compose.yml).

## First run
```powershell
.\scripts\dev.ps1 setup
```
This creates a private .env with random development secrets. Existing .env files are preserved.

For real verification emails, configure a sender before starting:
```powershell
.\scripts\Configure-FindIt-Gmail.ps1 -ProjectPath "."
```
Sign into the sending Gmail account at https://myaccount.google.com/apppasswords, enable 2-Step Verification if necessary, and generate a FindIt App Password. Enter it only into the helper's hidden prompt. The configured Gmail account sends messages to each registering student's institutional inbox. The helper accepts suh.edu.in and aiml.suh.edu.in recipients. Without SMTP configuration, the default development backend saves messages locally rather than delivering them to inboxes.

Build/start the application and load repeatable sample data:
```powershell
docker compose up -d --build --wait --wait-timeout 300
docker compose exec backend python -m app.seed
docker compose ps
```
Open http://localhost:5173 on the laptop. The first build can take several minutes.

## Demo logins
These are synthetic demonstration accounts only, created by the seed command on a fresh database. They are preverified and do not need email delivery.

| Role | Email | Password |
| --- | --- | --- |
| Student | alex.student@findit.local | DemoStudent1! |
| Student | jordan.student@findit.local | DemoStudent2! |
| Staff | sam.staff@findit.local | DemoStaff2026! |
| Admin | admin@findit.local | DemoAdmin2026! |

Seed data includes seven categories, four campus locations, and a complementary lost/found headphones pair. Claims and handovers are demonstrated interactively, not preloaded.

Suggested demo: sign in as Alex, view the lost report and matching found report, submit ownership proof, then sign in as Sam to record custody, review/approve the claim, and complete the handover. Sign in as admin to show categories, locations, users, and audit history.

The seed preserves existing accounts and reports. It does not reset passwords or verification status for accounts already present in an older database. Never delete existing volumes merely to reload demo data.

## Later starts and shutdown
```powershell
docker compose up -d --wait
docker compose down
```
Ordinary down preserves database/media volumes. Do not add --volumes unless intentionally deleting local data.

## After changing Gmail credentials
```powershell
.\scripts\Configure-FindIt-Gmail.ps1 -ProjectPath "."
docker compose up -d --force-recreate --wait --wait-timeout 180 backend
```
Request a fresh link at http://localhost:5173/verify-email for the registered student email. Check that recipient inbox and spam folder. Open localhost verification links on the laptop running FindIt; they will not reach the laptop when opened directly on a phone.

## Troubleshooting and checks
```powershell
docker compose ps
docker compose logs --tail 100 backend frontend
docker compose exec backend pytest -q
docker compose exec frontend npm run build
docker compose exec frontend npm run test:run
```
If PowerShell blocks a script, invoke that trusted local script using powershell -ExecutionPolicy Bypass -File followed by its path and arguments.
If Docker fails with sailor-ingest.sock, quit Docker, restart Windows, then open Docker directly from Start. Avoid factory reset because it can delete Docker data.

## Package contents and privacy
This source ZIP includes code, migrations, dependency lockfile, tests, deployment files, and documentation. It excludes .env, Gmail App Passwords, existing accounts/database contents, uploads, private mail, installed dependencies, and generated builds. The seed recreates synthetic data; it does not transfer your real account.

For fresh installs, do not share/reuse another person's .env. On the same laptop, an existing Compose project may reuse its existing database volumes; keep its matching original database credentials. Use the current working project for an already-configured demo.

This is a local development/demo setup. See docs/production-release.md before deploying publicly. Previously recorded test results are in docs/postgres-auth-deployment-verification.md; packaging does not rerun those tests.
