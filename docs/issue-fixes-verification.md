# Issue fixes and verification — 25 October 2026

This update addresses the six issues identified in the project review.

## Changes

1. Admin moderation supports ordinary archive/restore operations, rejects direct workflow status changes, and protects claim/custody history. Student archiving also protects custody history.
2. Signed-in CSRF bootstrap preserves a valid token. If its cookie is missing or invalid, it updates the session hash in the same transaction before issuing a replacement.
3. PATCH schemas reject explicit null for every database-required field while preserving omission and intentional clearing of nullable fields. Catalog names and moderation reasons trim whitespace.
4. PostgreSQL administrator membership changes acquire a transaction-scoped advisory lock before user row locks, refresh the target account, and enforce at least one active administrator. SQLite remains a sequential development/test option, not a proof of concurrent locking.
5. Authentication admission now uses shared atomic database buckets: default 8 login attempts per account, 40 per IP and 20 registrations per IP per 300-second fixed window. All admitted requests count, including successful logins and duplicate registrations. Keys are hashed; expired identities are purged during admissions. Blocked requests return 429 and Retry-After. These limits complement edge protection. Caddy overwrites the client identity header, Nginx forwards that address, and the unpublished backend trusts this internal proxy chain. Do not publish the backend/frontend ports or reuse wildcard forwarded-header trust in another topology.
6. Uploads permit at most 5 image evidence attachments per claim and 100 MiB aggregate sanitized report/evidence storage per report owner/claimant by default. PostgreSQL user-row locks serialize quota admissions across both upload paths. Admin report uploads count toward the report owner's quota. Quota rejection occurs before saving files. Configure FINDIT_MAX_CLAIM_EVIDENCE_IMAGES and FINDIT_MAX_USER_UPLOAD_BYTES as needed.
7. Added a frontend package-lock.json; Docker and CI use npm ci. Fixed existing TypeScript build failures, separated Vite/Vitest configs, excluded browser tests from Vitest discovery, and pinned Playwright 1.64.1 for current browser tooling. Evidence upload UI now lists supported image formats.

## Database upgrade

Run the normal migration command before starting the updated API:

    cd backend
    python -m alembic upgrade head

New revision a83d02c941b7 adds auth_rate_buckets. Existing data is retained. No changes to existing application tables are required. Standard startup already applies migrations.

## Regression coverage

Backend tests cover CSRF bootstrap/recovery and logout, null validation, moderation and custody/history restrictions, last-admin protection, shared/expiring authentication buckets, IP rotation, registration limits, attachment limits, cross-path storage accounting and admin uploads. PostgreSQL-only tests exercise concurrent demotions, uploads and admission requests. Locked report/claim reads refresh identity-map objects after acquiring locks.

CI now includes a disposable PostgreSQL job, fresh migrations, Alembic drift detection, the API suite, and desktop/mobile browser workflows. A new Playwright recovery test covers student reporting, private claims, CSRF refresh, finder access denial, staff custody, approval and handover. Unit tests and browser tests are discovered separately.

## Running PostgreSQL checks

Set FINDIT_TEST_DATABASE_URL to a disposable PostgreSQL database, then run pytest from backend. Tests create and drop a separate random schema per case. Never point this variable at a real campus database. The ordinary fixture remains isolated SQLite when it is unset.

## Running browser workflows

Use a fresh migrated development/test database. Set FINDIT_E2E_STAFF_EMAIL and FINDIT_E2E_STAFF_PASSWORD to dedicated test credentials, then run python -m app.e2e_fixture from backend. The command refuses staging/production and refuses to overwrite an existing fixture account. Start the API and frontend; run npm run test:e2e. Set VITE_PROXY_TARGET when the API uses another port. PLAYWRIGHT_CHANNEL=chrome optionally uses installed Chrome; otherwise install Playwright Chromium. The recovery test skips when fixture credentials are absent. CI supplies them for its ephemeral database.

## Actual local results

- Isolated Python 3.12.14 dependency installation: passed.
- Backend regression suite: 43 passed, 3 PostgreSQL-only concurrency tests skipped locally.
- Fresh SQLite upgrade through both revisions and alembic check: passed; no schema drift.
- Python compilation and focused unused-import checks: passed. Production Compose parses successfully using its example environment.
- npm ci: passed. After updating Playwright, npm ci --dry-run --ignore-scripts --offline also verified the final manifest/lockfile resolution.
- TypeScript/Vite production build: passed. Vite reports a nonfatal bundle-size warning.
- Vitest: 3 passed.
- Playwright 1.64.1: 6 passed in 35.9 seconds, including desktop and Pixel 7 viewport recovery workflows, using installed Chrome 156 and Node 24.22.1 against a fresh migrated SQLite database. Both local servers were managed explicitly by the test harness to avoid Windows nested-process shutdown issues.
- PostgreSQL, production proxy/container startup and TLS: not executed locally; Docker Desktop engine is stopped. CI configuration is supplied, but its remote result is not claimed.

Earlier failures during dependency setup and TypeScript validation were repaired before the successful checks above. Historical verification.md records describe older source states and are not results for this update.

The added touch workflow also exposed mobile modal interaction problems. Dialogs now render in a body portal, keep their footer outside the scrolling content, use dynamic viewport height, and lock background scrolling while open. Browser tests disable unrelated external font loading and use touch activation on touch devices.

For tests against an already running stack, set PLAYWRIGHT_BASE_URL to its frontend URL. This skips Playwright-managed server startup/shutdown, which also avoids the local Windows nested-process shutdown limitation. The final mobile gesture is a native touch at a verified, visible viewport position; no forced or JavaScript-dispatched clicks are used.
