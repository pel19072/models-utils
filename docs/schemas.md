# Pydantic Schemas

## Description

Pydantic v2 request/response schemas for all models — 42 modules in
`database_utils/schemas/`, shared between auth-erp and backend-erp to keep API
contracts consistent (frontend-erp consumes the resulting JSON shapes via the
backend proxies).

## Goal

Validate API inputs and serialize API outputs with a single shared schema
definition across services.

## Schema Modules (in `database_utils/schemas/`)

One module per entity. `schemas/__init__.py` star-imports all modules and runs
`model_rebuild()` to resolve circular Order/RecurringOrder references.

| Domain | Modules |
|---|---|
| Auth / tenancy | `user`, `company`, `role`, `permission`, `invitation`, `notification`, `audit_log`, `requests` (Login + flat company-only Signup), `email_verification`, `password_reset` |
| SaaS billing | `tier`, `subscription`, `payment_method`, `billing_invoice`, `tier_change_request` |
| CRM | `client`, `custom_field`, `order`, `order_item`, `payment`, `invoice`, `product` (legacy), `recurring_order` (legacy), `task`, `task_state`, `task_template`, `integration` |
| ISP | `service_plan`, `client_service`, `inventory`, `topology`, `playbook`, `device_category`, `insight` (Cycle 4) |
| Network config (Cycle 5) | `acs_registration`, `device_credential`, `network_access`, `provisioning_settings` |
| Workflow | `workflow`, `workflow_template` |
| Generic | `pagination` — `PaginatedResponse[T]` wrapper |

`schemas/network.py` was **deleted** with the network-graph removal (Cycle 2
`c2d_graph_removal`) — a comment in `__init__.py` records this.

## Connections to Other Components

- **auth-erp** and **backend-erp** import schemas directly from this package
- **Models** ([auth-models.md](auth-models.md), [crm-models.md](crm-models.md),
  [isp-models.md](isp-models.md), [workflow-models.md](workflow-models.md)):
  schemas mirror model fields
- **frontend-erp**: no direct dependency; its API responses are shaped by
  these schemas via the backends

## Key Implementation Details

- `Out` schemas use `from_attributes=True` for ORM compatibility
- Sensitive fields are excluded from `Out` schemas (e.g. `password_hash`,
  integration `credentials`)
- `PaginatedResponse[T]`: generic paginated wrapper
- `order_item.product_id` is deprecated but still honored (catalog-merge
  rollback window — see [limitations.md](limitations.md))
- UUID fields serialize as strings in JSON responses

### Cycle 7 (core config, doc 25) — extensions to existing modules

- `device_category`: `tier` on Base/Update with a normalizing validator
  (strip/upper, must be in `DEVICE_CATEGORY_TIERS`, empty → None) so the DB
  CHECK never fires as a raw 500
- `inventory`: `DeviceType*.cli_platform` (free string); `InventoryItem*`
  mgmt surface — `mgmt_host`/`mgmt_port`/`cli_protocol` (normalizing validator
  against `CLI_PROTOCOLS`) PATCHable via the existing inventory update; the
  worker-stamped `mgmt_last_check_at`/`mgmt_last_check_ok` appear **only** on
  `InventoryItemOut` (read-only)
- `topology`: `TopologyChainEntryIn` — richer per-position write shape carrying
  `inventory_item_id` (pinned shared device). `TopologyCreate` requires exactly
  one of `device_type_ids`/`chain`; `TopologyUpdate` at most one; both expose a
  normalized `chain_entries()` helper. `TopologyChainEntryOut` gains
  `inventory_item_id`/`inventory_item_serial`/`category_tier` (router-populated)
- `playbook`: `PLAYBOOK_DRIVERS` gains `ping`; `PlaybookStep.target_item_id`
  (and the same on `PlaybookPrecondition`) — an inventory_item id or a
  `{{variable}}` rendered by the executor, declared so it round-trips through
  `model_dump()` instead of being silently dropped
- `client_service`: `ClientServiceOut.install_state`/`installed_at` — read-only
  (deliberately absent from `ClientServiceUpdate`; written only by backend-erp's
  `recompute_install_state`)

### Cycle 8 (network UX, doc 26) — `playbook` schema changes

Playbooks are now topology-owned, so `schemas/playbook.py` changes:

- `PlaybookBase` drops `target_vendor` and `target_category`; `PlaybookCreate`
  drops them from its optional overrides too
- `PlaybookOut` drops `target_category_id` and gains `topology_id: Optional[UUID]`
  (NULL = a system/global playbook; non-NULL = an inline playbook owned by that
  topology, cascaded on topology delete)
- `PlaybookStep` gains `target_position: Optional[int]` — the 1-based topology
  chain position the step configures. A `field_validator` rejects `< 1`. When
  set and `target_item_id` is unset, the renderer derives
  `target_item_id = "{{device<N>_item_id}}"` (N = target_position) at render
  time, so provisioning-resolution keeps emitting `device{i}_*` unchanged;
  `target_item_id` still wins for power users / system playbooks
- `PlaybookDefinition` is otherwise unchanged (steps still carry `target_item_id`)

### Auth overhaul — request-schema changes (no DB migration)

Company-only signup with locale-aware transactional email:

- `requests.py`: `SignupCompanyRequest` is now **flat and minimal** —
  `company_name` (2..255), `name` (2..255), `email` (EmailStr), `password`
  (min 8), `locale` (`Literal["es","en"]`, default `"es"`). The old nested
  `{company: CompanyCreate, user: UserCreate}` shape and **`SignupUserRequest`
  are deleted** (users are invitation-only; no self-serve user signup).
- `email_verification.py`: `ResendConfirmationRequest` gains `locale`
  (es/en, default es).
- `password_reset.py`: `PasswordResetRequestSchema` gains `locale`;
  `PasswordResetConfirmSchema.new_password` min length raised 6 → 8 (all
  password minimums aligned at 8).
- `invitation.py`: `InvitationCreate` gains `locale` (used for the invitation
  email language); `InvitationAccept` is now `{token, name, password}` with
  `password` min length 8 — the `age` field was **removed** (the accept
  handler passes `age=0` explicitly; no model change).

The `locale` values feed the localized email templates/subjects — see
[email-service.md](email-service.md).

## Environment Variables

None — schemas are pure Python/Pydantic.
