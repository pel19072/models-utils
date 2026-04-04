# Auth Models

## Description
SQLAlchemy ORM models for all authentication, authorization, and company management entities.

## Goal
Provide a single shared definition for auth-related database tables consumed by both auth-erp and backend-erp.

## Models (in `database_utils/models/auth.py`)

| Model | Key Fields | Purpose |
|-------|-----------|---------|
| `Tier` | name, price, price_yearly, features (JSON), modules (JSON), is_active | Subscription plans |
| `Company` | name, tax_id, address, phone, active, tier_id, start_date | Multi-tenant company |
| `User` | name, email, password_hash, active, is_super_admin, company_id | Authenticated user |
| `Role` | name, is_system, company_id | Permission group |
| `Permission` | name, resource, action | Single access right |
| `Notification` | status (PENDING/ACCEPTED/REJECTED), user_id, company_id | In-app notification |
| `AuditLog` | action, resource_type, resource_id, details (JSON), user_id, ip_address | Immutable audit trail |
| `UserInvitation` | email, token (UUID), status, expires_at, company_id, invited_by | Invitation flow |
| `Subscription` | status, billing_type, billing_cycle, period dates, trial_end, cancel_at_period_end, tier_id | Company subscription |
| `PaymentMethod` | type, last_four, is_default, company_id | Billing payment method |
| `BillingInvoice` | invoice_number, status, due_date, paid_at, subtotal, tax, total, stripe fields | Subscription invoice |
| `TierChangeRequest` | current_tier_id, requested_tier_id, status (PENDING/APPROVED/REJECTED), approval_note | Tier change workflow |

## Connections to Other Components
- **auth-erp**: Primary consumer of all auth models
- **backend-erp**: Reads User, Company, Role, Permission for auth validation
- **Alembic migrations**: All table DDL managed here
- **Auth schemas** (`schemas/`): Pydantic representations of these models

## Key Implementation Details
- All models use `id` (UUID, server_default=uuid4)
- All models have `created_at` (timestamp, server_default=now)
- Most models have `updated_at` (timestamp, onupdate=now)
- Foreign keys use `ondelete="CASCADE"` or `SET NULL` as appropriate
- Many-to-many: User ↔ Role via association table; Role ↔ Permission via association table
- Enums: `SubscriptionStatus`, `BillingType`, `BillingCycle`, `InvoiceStatus`, `TierChangeStatus`, `NotificationStatus`

## Environment Variables
- `POSTGRES_*` — Database connection string components
