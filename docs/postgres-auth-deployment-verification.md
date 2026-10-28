# FindIt PostgreSQL, authentication and deployment verification

Verified October 26, 2026. This report supersedes historical verification counts in earlier releases. Tests used synthetic accounts and a disposable local database; no campus records or real email recipients were used.

## Observed results

| Check | Result |
|---|---|
| PostgreSQL 16.15 fresh Alembic migration through `b94e13d052c8` | Passed |
| PostgreSQL metadata/schema drift check (`alembic check`) | Passed; no drift |
| Complete API regression suite against PostgreSQL | 74 passed, no skips |
| Frontend TypeScript and production Vite build | Passed |
| Frontend unit tests | 6 passed |
| Desktop/mobile Chromium browser tests through HTTPS | 8 passed, no skips |
| Nginx and Caddy configuration validation | Passed |
| Production preflight: DB, exact schema, media write, STARTTLS relay | Passed |
| Host-aware API readiness probe | Passed |
| TLS hostname/certificate validation, Secure/SameSite cookies, HSTS, CSP, nosniff | Passed using a private synthetic test certificate |
| PostgreSQL custom dump and restore into a fresh database | Passed; user/report/claim/handover/audit/token counts matched |
| Media snapshot restore | Passed; file SHA256 hashes matched |
| Python compilation and Ruff undefined/unused-name checks | Passed |
| Production Docker Compose configuration parsing | Passed |
| Actual Linux production containers and remote GitHub Actions | Configured; not executed here |

The browser tests exercise institutional signup, mailbox confirmation, password recovery, invalidation of an existing session, reporting/claiming an item, staff custody, approval and handover, plus landing and keyboard-login checks. Both desktop and mobile projects ran. The API suite also covers the original moderation/state, CSRF refresh, PATCH null, last-administrator concurrency, admission limits and upload regressions, plus identity and deployment guards.

## Changes delivered

- Exact `suh.edu.in` self-registration restriction; configurable institutional domain list.
- Pending registration without a session when verification is required. Mailbox owners choose their password at confirmation, preventing preregistration password takeover.
- Expiring, single-use verification/recovery tokens stored only as digests. Email links use fragments and are removed from browser history on the identity page.
- Generic recovery/resend responses, account/IP admission limits, encrypted SMTP with certificate validation, development-only private mail sink.
- Password change, owned-session/device revocation and logout-all. Recovery/password changes revoke existing sessions; administrator role/status changes also revoke sessions.
- Production guards for PostgreSQL, canonical HTTPS origin, trusted hosts, institutional verification, secure cookies, strong secrets and encrypted SMTP. Configuration errors suppress input secrets.
- Separate migration service, read-only API filesystem, private proxy trust, security headers, disabled public API documentation and deployment preflight.
- Maintenance-window consistent backup and empty-target restore commands with checksums and archive validation, repeatable PostgreSQL verification and a Linux production-container CI job.
- Frontend lockfile retained; private mail, keys, dumps, dependencies, databases and test runtime files are excluded from the delivery archive.

## Upgrade and operation

Migration `b94e13d052c8` adds verification/token storage and intentionally invalidates existing sessions. Existing users must verify their mailbox and choose a password before signing in when verification is enabled. Active pre-upgrade administrators have a password-checked trusted-console verification command. Back up database and media together before the coordinated upgrade.

Follow `docs/authentication.md` and `docs/production-release.md` in the source archive. `scripts/verify_postgres.py` repeats the full application checks against an explicitly confirmed empty disposable PostgreSQL database. `scripts/verify_containers.py` and the supplied CI job exercise the actual Linux Compose stack, synthetic SMTP, HTTPS, browser workflows and Docker backup/restore.

## Limits and remaining deployment inputs

Docker Desktop's engine could not start locally. The observed HTTPS/SMTP/browser/restore results used native PostgreSQL, Nginx, Caddy and API processes on loopback; proxy ports and filesystem paths were adapted for Windows. They do not establish that the Linux images, volumes or container networking have passed. Run the supplied container job on the deployment host or CI before rollout.

No SMTP provider/credentials or public hostname was supplied. Configure the institution's relay and verified sender, public DNS and production secrets, then run preflight and synthetic delivery/HTTPS checks there. No real email was sent and no public deployment was performed. The private test CA was never installed in the OS trust store. The Python HTTPS client validated it explicitly; Playwright ignored certificate errors only for this synthetic self-signed test stack.

Authentication email delivery runs as a bounded background task without a durable retry queue. Failed delivery is logged without tokens/recipients/credentials; users can request a replacement link. SSO, staff MFA, off-host backup scheduling/retention, institutional privacy review and the full supported-browser matrix remain follow-up work.

Non-failing output included a Starlette/AnyIO deprecation, React Router future flags and Vite's >500 kB chunk advisory. These were not hidden or treated as failed tests.
