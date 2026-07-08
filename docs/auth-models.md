# Auth Models

## Description

SQLAlchemy ORM models for authentication, authorization, tenancy, email/password
token flows, and the SaaS billing plane (`database_utils/models/auth.py`).

## Goal

Provide a single shared definition for auth-related database tables consumed by
both auth-erp (primary) and backend-erp (token/permission validation).

## Models (in `database_utils/models/auth.py`; table names in parens)

| Model | Purpose |
|-------|---------|
| `Tier` (tier) | SaaS subscription plans (features/modules JSON) |
| `Company` (company) | Multi-tenant ISP company |
| `User` (user) | Authenticated user (incl. super-admin flag) |
| `Role` (role) | Permission group |
| `Permission` (permission) | Single access right (resource + action) |
| `Notification` (notification) | In-app notification |
| `AuditLog` (audit_log) | Immutable audit trail (see `utils/audit_utils.py`) |
| `UserInvitation` (user_invitation) | Invitation flow |
| `EmailVerificationToken` (email_verification_token) | Email verification flow — existing users were grandfathered by the `c1f_verify_grandfather` migration |
| `PasswordResetToken` (password_reset_token) | Password reset flow |
| `Subscription` (subscription) | Company's SaaS subscription |
| `PaymentMethod` (payment_method) | SaaS billing payment method |
| `BillingInvoice` (billing_invoice) | SaaS subscription invoice |
| `TierChangeRequest` (tier_change_request) | Tier change approval workflow |

Note the two billing domains: these SaaS-billing models cover ISP companies
paying Uplink; **subscriber** billing (ISP end-customers) lives in the CRM/ISP
models ([crm-models.md](crm-models.md), [isp-models.md](isp-models.md)).

## Connections to Other Components

- **auth-erp**: primary consumer of all auth models; drives the email flows
  via the shared [email service](email-service.md)
- **backend-erp**: reads User, Company, Role, Permission for auth validation
  (`utils/jwt_utils.py`, `utils/permission_utils.py`)
- **cron-erp**: hits auth-erp's billing endpoints that operate on
  Subscription/BillingInvoice
- **Seeds**: `alembic/seeds/rbac_seed.py` (permissions/roles), `alembic/seeds/tier_seed.py` (importable as `seeds.*` because `env.py` adds the alembic dir to `sys.path`)
- **Auth schemas** ([schemas.md](schemas.md)): Pydantic representations

## Key Implementation Details

- All models use UUID v4 `id` primary keys with `created_at` /
  `updated_at` timestamps
- Foreign keys use `ondelete="CASCADE"` or `SET NULL` as appropriate
- Many-to-many: User ↔ Role and Role ↔ Permission via association tables
- Billing/status fields are **not** Python enums — they are plain
  `Column(String)` fields whose allowed values are documented in inline comments:
  `Subscription.status` (ACTIVE/PAST_DUE/CANCELED/TRIALING),
  `Subscription.billing_type` (AUTOMATIC/MANUAL),
  `Subscription.billing_cycle` (MONTHLY/YEARLY),
  `BillingInvoice.status` (PENDING/PAID/FAILED/REFUNDED),
  `TierChangeRequest.status` (PENDING/APPROVED/REJECTED). The only enum in this
  area, `NotificationStatus`, is defined in `schemas/notification.py` (a schema),
  not in the auth model.
- System role names live in `constants/roles.py` (`Roles`:
  ADMIN/MANAGER/SALES/USER)

## Environment Variables

- `POSTGRES_*` / `DATABASE_URL` / `DB_URL` — database connection (via `database.py`)
