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
| SaaS billing | `tier`, `subscription`, `payment_method`, `billing_invoice`, `tier_change_request` — rb1 extends `tier` and `subscription` (see below) |
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

### Brownfield adoption (doc 30) — `client_service` schema changes

- `ClientServiceOut` gains `adopted_at`/`adopted_by_user_id`/`adoption_note`
  (Out-only, never on Create/Update — `migration_source` precedent) and
  `activation_evidence` (Out-only, backend-COMPUTED — not a DB column; values
  from `isp.ACTIVATION_EVIDENCE_VALUES`: `'provisioned'` | `'attested'` |
  `None`; populated only on list/detail/adopt/un-adopt responses — `None`
  elsewhere means "not computed", not "no evidence")
- `ClientServiceAdoptIn` — `POST /client-services/{id}/adopt` body: `note`
  required non-empty (stripping validator), `installed_at` optional historical
  install date (applied only while the service's `installed_at` is NULL), and
  `topology_id: Optional[UUID]` (service-lifecycle cycle, doc 35) — the topology
  to assign DURING adoption. An adopted/brownfield service with no topology can
  resolve no lifecycle playbook at all, so it would be uncancellable except
  through the ADMIN force escape hatch. Inherited by
  `ClientServiceAdoptBulkItem`, so the bulk campaign path accepts it too
- `ClientServiceAdoptBulkItem` (AdoptIn + `client_service_id`) and
  `ClientServiceAdoptBulkIn` (`items`, 1–500) — `POST /client-services/adopt-bulk`
  body
- `ClientServiceAdoptBulkRowResult` (`status` `'adopted'`|`'error'`; `error`
  `'NOT_FOUND'`|`'ALREADY_ADOPTED'`) and `ClientServiceAdoptBulkOut`
  (`results` + `adopted_count`/`error_count`) — the bulk response (per-row,
  never all-or-nothing)

### Client install-field removal (doc 31) — `client` schema changes

- `ClientBase`/`ClientUpdate` (and thus `ClientCreate`/`ClientOut`) drop
  `installation_status`/`installation_date` — the columns and the
  `InstallationStatus` enum were removed by `cf1_drop_client_install_fields`
  (install truth is `client_service.install_state`)
- `ClientOut` gains `services_total`/`services_installed` (`int`, default
  `0`) — the services-summary rollup, Out-only and backend-COMPUTED by
  backend-erp's clients list/detail endpoints from `client_service` rows
  (`install_state='INSTALLED'` for the second count); never stored, never on
  Create/Update (`activation_evidence` precedent)

### Recurrente tenant billing (rb1) — `tier` / `subscription` schema changes

- `SubscriptionOut` gains `recurrente_subscription_id`/`card_last4`/`card_brand`
  (Optional, mirror the rb1 columns)
- `TierOut` gains `recurrente_product_id`/`recurrente_price_id`/
  `recurrente_price_yearly_id` (Optional — admin-facing)
- `TierPublic` gains `purchasable: bool = False` — stamped by the endpoint from
  `recurrente_price_id` presence; the raw price id is never exposed publicly

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
  time; doc 33: the derivation targets the absolute-position `chain[n]` namespace;
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
