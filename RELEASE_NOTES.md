# PostgreSQL, authentication and deployment update � October 26, 2026

- Added exact `suh.edu.in` registration restrictions, mailbox verification with owner-selected password, one-use password recovery, password changes, device/session revocation, and trusted-console verification for existing administrators.
- Added migration `b94e13d052c8`; upgrading invalidates existing sessions and requires account verification. Review `docs/authentication.md` before upgrading.
- Added production configuration checks, encrypted SMTP, deployment preflight, separate migration service, proxy/header hardening, and maintenance-window backup/empty-target restore tools.
- Added PostgreSQL and production-container verification workflows. See `docs/postgres-auth-deployment-verification.md` for observed results and remaining release prerequisites.

The earlier release notes below describe historical verification only; the current verification report supersedes their test counts and lockfile limitations.

---

# FindIt Next 2.0 — Repair edition (October 24, 2026)

**Basis:** user's uploaded `FindIT (2).zip`, improved in place. This is NOT a redesign or a completely different project.

## Fixed or added

- Added complete initial Alembic schema revision (12 application tables, constraints, indexes and partial unique claim indexes). Fresh SQLite migration and metadata comparison passed. PostgreSQL remains to be verified.
- Repaired stale post-auth CSRF tokens: cache follows the rotated CSRF cookie; login and registration explicitly reset cached values.
- Introduced an anonymous, privacy-minimized public Browse API and wired its React page to that endpoint. Anonymous users cannot retrieve private ownership details or report images from the public catalog.
- Stopped cross-student discovery of archived reports via list filtering, counting and search.
- Enforced post-whitespace-trim field constraints for item names, descriptions, claim proof, student names and custody storage locations.
- Fixed error serialization of validation exceptions (previously could trigger a 500 rather than 422).
- Corrected deep links in student/staff notifications, QR image URLs and administrative location reporting URLs.
- Closed the claimant's linked lost report on successful handover, preventing already-returned items from remaining in active matching.
- Locked linked lost reports against identity changes, deletion/archiving and image changes during an ongoing claim.
- Added backend pytest scenarios for privacy, claims, staff custody, approval, handover, audit logging and input validation; verified 8 passing tests.
- Added Vitest setup and API regression tests (not executable in current offline npm environment).
- Added a safe source-only ZIP packaging script that never includes `.env`, Git internals, dependencies, media or databases.

## Important limits

- The backend was tested against temporary SQLite; the intended PostgreSQL + Docker stack and frontend build were not verifiable in this environment.
- npm registry access was unavailable, so this ZIP does not include a `package-lock.json`; use `npm install` once on your machine to generate it. Build/commit the lockfile before production deployment.
- The project is suitable for continued development and campus-demo validation, **not certified production deployment**.
- No user's uploaded application data was migrated or changed; working copy built from the supplied source archive.

## Issue fixes — 2026-10-25

Protected report moderation and administrator membership changes; repaired authenticated CSRF bootstrap and PATCH null validation; added shared database authentication admission limits and serialized upload quotas. Added a schema migration, reproducible frontend lockfile and npm ci workflows, PostgreSQL concurrency CI, and complete desktop/mobile browser recovery tests. Fixed build configuration and mobile dialog scrolling. See docs/issue-fixes-verification.md for upgrade instructions, limits and actual checks.
