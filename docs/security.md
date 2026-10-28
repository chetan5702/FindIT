# Security and threat model

This document records the security boundary and required controls for the MVP. It is not a claim of formal certification or an independent security audit.

## Protected assets

- Account credentials, active sessions, and CSRF secrets
- Private ownership descriptions and claim evidence
- Student identity/profile data
- Exact custody and storage information
- Uploaded image content
- Claim decisions, handover records, and append-only audit history
- Administrator and staff privileges

## Trust boundaries

The browser and all client-supplied data are untrusted. FastAPI is the authorization boundary. PostgreSQL and the media volume are private application dependencies and must not be exposed directly in production. Campus staff are trusted to review evidence for assigned operational duties, but are not implicitly administrators. A scanned location QR code only preselects a location; it does not establish presence, custody, or authenticity.

## Threats and controls

| Threat | Primary controls |
|---|---|
| Credential theft and brute force | Argon2id hashing, generic login failures, bounded request bodies, login throttling, no credential logging |
| Session theft/fixation | Opaque server-side sessions, regenerated identifier on login, expiration and revocation, `HttpOnly`, `SameSite`, production `Secure` cookies |
| Cross-site request forgery | Origin checks plus a per-session CSRF token on every state-changing cookie-authenticated request |
| Broken access control / IDOR | Object-level authorization in services, role dependencies in backend routes, explicit response schemas |
| Staff privilege escalation | Public registration hardcodes student role; staff/admin grants require admin authorization and are audited |
| Sensitive-data disclosure | Separate public/private schemas, evidence endpoints limited to assigned staff/admin, no raw ORM serialization |
| Malicious upload | Allowlisted extensions and decoded MIME signatures, byte limits, generated filenames, path containment, content-disposition and safe serving headers |
| Stored XSS | React text escaping, no untrusted raw HTML, strict image handling, recommended production CSP |
| SQL injection | SQLAlchemy parameter binding; allowlisted sort/filter fields rather than raw SQL fragments |
| Claim race / double release | Database constraints and row locks; approval/handover workflows run in transactions |
| Workflow tampering | Server-enforced state machine, immutable report identity fields, completed handovers terminal to ordinary controls |
| Audit erasure | No mutation API for audit events; administrative actions record actor, action, target, and timestamp |
| Location/QR spoofing | UI and API treat QR values as a convenience/default only, never verification evidence |
| Denial of service | Pagination caps, file/body limits, bounded search inputs, auth rate limiting; production edge limits still required |

## Cookie and CSRF model

Authentication uses an opaque session identifier in an HTTP-only cookie. The server stores only the session representation needed to revoke and expire it; it never places roles or trust decisions solely in client-controlled data. Unsafe methods require a CSRF token bound to the authenticated session and validated by the backend. CORS is an additional browser boundary, not the CSRF defense.

Local HTTP development sets `FINDIT_COOKIE_SECURE=false`. Every HTTPS deployment must set it to `true`, use a narrow host-only cookie, and configure explicit origins and trusted hosts.

## Authorization matrix

| Capability | Student | Staff | Administrator |
|---|:---:|:---:|:---:|
| Create own lost/found report | Yes | Yes | Yes |
| Edit/delete eligible own report | Yes | Yes | Yes |
| View private claim evidence | Own submitted evidence only | Yes, for review duties | Yes |
| Record custody and review claims | No | Yes | Yes |
| Complete a handover | No | Yes | Yes |
| Manage categories/locations | No | No | Yes |
| Grant/revoke staff permissions | No | No | Yes |
| View complete audit history | No | Limited operational history | Yes |

Backend checks are authoritative even if the frontend hides controls.

## Operational checklist

- Generate a unique `FINDIT_SECRET_KEY` and database credentials; never commit `.env`. Session and CSRF tokens are generated independently, and only their digests are persisted server-side.
- Terminate TLS and enable secure cookies before accepting real data.
- Restrict database and media access to the application network and service account.
- Back up database and media as a consistent set; test restoration.
- Set log retention and redact credentials, cookies, CSRF tokens, and evidence bodies.
- Review administrator/staff membership and audit events regularly.
- Apply dependency and container security updates deliberately after test runs.
- Configure edge rate/body limits and centralized throttling for multi-instance deployment.
- Define retention/deletion policy with campus privacy and legal stakeholders before production.

## MVP residual risks

Authentication admission uses atomic database-backed fixed-window account and IP buckets, shared across workers. Registration is also limited by IP. These limits complement deployment edge protection; client IPs must come from a trusted proxy boundary. Local volume media lacks malware scanning and managed durability. Institutional email verification, recovery and session management are implemented; university SSO, staff MFA, automated abuse detection and formal evidence-retention policy still require institutional work. These limits must be addressed before a campus-wide production rollout.



The verified-identity update uses hashed, expiring, purpose-scoped action tokens, mailbox-owner password selection, generic recovery requests and session revocation. Production fails closed without institutional verification and encrypted SMTP configuration. See authentication.md and postgres-auth-deployment-verification.md for precise guarantees and executed checks. Configuration errors suppress input values to avoid echoing credentials in startup logs. Email delivery is observable and resendable, not a durable retry queue.
