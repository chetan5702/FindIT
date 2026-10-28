# Institutional authentication

FindIt accepts self-registration only from the exact `suh.edu.in` domain by default. Subdomains and look-alike suffixes do not match. `FINDIT_ALLOWED_EMAIL_DOMAINS` is configurable, but production/staging refuse an empty list or disabled email verification.

Registration returns a generic pending response and creates no session until the mailbox owner follows a verification link and chooses a password. Choosing the password at verification prevents an attacker from retaining a password set while pre-registering somebody else's email. Existing unverified accounts cannot sign in when verification is required.

Verification links expire after 60 minutes; password-reset links expire after 20 minutes by default. Tokens are random, stored only as hashes, scoped to one purpose, replaced on resend, and consumed once under PostgreSQL locks. The link token is in a URL fragment, not a query string. The frontend removes it from browser history and waits for explicit confirmation. Pages do not fetch third-party fonts.

Password recovery always returns the same eligibility message. Inactive or unverified users do not receive reset links. Reset and authenticated password change invalidate every session and outstanding recovery token. Password change requires the current password. Account-role and activation changes revoke sessions; disabled accounts cannot use old links. The profile page lists active devices and allows scoped revocation or signing out everywhere. Successful sign-in clears cached data from the previous account.

## Email configuration

Development/test can write private `.eml` files using `FINDIT_MAIL_BACKEND=file`. In development Compose these live in the `mail_data` volume at `/data/mail`; copy the folder to a private local directory with `docker compose cp backend:/data/mail ./work/mail` to inspect synthetic links. For native development choose a writable `FINDIT_MAIL_DIRECTORY`. Do not serve or commit these files.

Production/staging require `FINDIT_MAIL_BACKEND=smtp`, an actual `FINDIT_SMTP_HOST`, a verified sender (`FINDIT_MAIL_FROM`), and `starttls` or `tls` security. Configure the SMTP port, username and password according to the institution's mail provider. TLS certificates and hostnames are verified before SMTP authentication; plaintext delivery and template placeholders are rejected. SMTP secrets are never printed by application delivery-error logging.

No institutional SMTP provider or credentials were supplied during this task. The application has a configurable adapter; live institutional delivery must be configured and tested by the deployment owner. Tests deliver only to an isolated local SMTP sink. Sender verification, SPF/DKIM/DMARC and institutional SSO depend on the provider and institution.

Email delivery runs after the account/token transaction commits. A delivery failure is logged without recipient or token; the user can request another link. This does not promise a durable email retry queue or guaranteed delivery. Monitor delivery failures and relay health. The deployment preflight verifies the encrypted relay connection without sending mail.

## Upgrade and console access

Migration `b94e13d052c8` adds `users.email_verified` and hashed action tokens, and revokes old sessions. Existing users start unverified; they must verify their institutional inbox and choose a password. Coordinate this sign-in interruption before upgrade.

New administrators created using `python -m app.cli create-admin` are explicitly trusted through deployment-console access. An active pre-upgrade administrator can run `python -m app.cli verify-admin --email their-address` and enter the existing password at the hidden prompt. This console-only operation checks the active administrator role/password and records an audit event; it is not an API bypass for students.

Run `python -m app.cli purge-auth` from a controlled operations schedule to remove expired sessions, action tokens and stale admission buckets.

## API additions

| Endpoint | Purpose |
|---|---|
| POST `/api/v1/auth/verification/request` | Generic resend request |
| POST `/api/v1/auth/verification/confirm` | Consume verification token and set mailbox-owner password |
| POST `/api/v1/auth/password/forgot` | Generic recovery request |
| POST `/api/v1/auth/password/reset` | Consume reset token, replace password, revoke sessions |
| POST `/api/v1/auth/password/change` | Current-password checked change |
| GET `/api/v1/auth/sessions` | Current user's active sessions without token material |
| DELETE `/api/v1/auth/sessions/{id}` | Revoke an owned session |
| POST `/api/v1/auth/logout-all` | Revoke every session |

All mutation endpoints require CSRF protection. Public token/request routes have shared admission limits. Verification confirmation and reset accept `{token, password}`. Registration returns `user: null` and `verification_required: true` when verification is enabled; clients must not assume registration establishes a session.

This implements institutional email assurance. University SSO and staff MFA are separate integrations and are not claimed as implemented.
