# Email Service

## Description

Transactional email for the platform, shipped as part of this library so any
consumer (primarily `auth-erp`) sends identical, branded emails.

- `database_utils/services/email_service.py` — abstract `EmailService` base +
  an SMTP implementation using `aiosmtplib`
- `database_utils/utils/email_templates.py` — Jinja2 template rendering helper
- `database_utils/templates/email/*.html` — 8 Jinja2 HTML templates

## Email kinds

The abstract `EmailService` defines seven transactional email kinds:

1. Invitation
2. Welcome
3. Payment receipt
4. Confirmation (email verification)
5. Password reset
6. Payment failed
7. Join-request decision

## Templates (`database_utils/templates/email/`)

| Template | Used for |
|---|---|
| `base_layout.html` | Shared layout wrapper |
| `confirmation.html` | Email verification |
| `invitation.html` | User invitation |
| `join_request_decision.html` | Join-request accept/reject notice |
| `password_reset.html` | Password reset link |
| `payment_failed.html` | Failed payment notice |
| `payment_receipt.html` | Payment receipt |
| `welcome.html` | Welcome email |

Templates are packaged with the wheel via `[options.package_data]` in
`setup.cfg` — if you add a template, confirm it ships in the built package.

## Configuration

| Env var | Purpose |
|---|---|
| `EMAIL_PROVIDER` | Selects the provider implementation (SMTP) |
| `SMTP_USE_TLS` | TLS toggle for the SMTP transport |
| SMTP host / credentials | Supplied via the consuming service's environment |

## Connections to Other Components

- **auth-erp**: primary consumer — invitation, verification
  (`EmailVerificationToken`), and password reset (`PasswordResetToken`) flows;
  see [auth-models.md](auth-models.md)
- **Schemas**: `schemas/email_verification.py`, `schemas/password_reset.py`
- **Token helpers**: `utils/token_utils.py`

## Tests

Email schemas, service, templates, SMTP behavior, and model tokens are covered
by ~20 tests in `tests/`.
