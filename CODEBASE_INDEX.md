# CODEBASE_INDEX — models-utils

Navigation index for the `database-utils` library (v1.14.0, Python >= 3.11).
Not a running service: no endpoints, no ports. Consumed as a pip dependency by
`backend-erp`, `auth-erp`, and `cron-erp`; also built as the one-shot `migrate`
docker-compose service. May drift — verify against actual files.

## Top Level

| Path | Purpose |
|---|---|
| `setup.cfg` | Package metadata (`database-utils`, version), install_requires, `[options.package_data]` for email templates |
| `pyproject.toml` | Build-system config only |
| `Dockerfile` | python:3.12-slim, `pip install .`, CMD `alembic upgrade head` — used only by the repo-root compose `migrate` service |
| `alembic.ini` / `alembic/` | Migration config + 47 revisions (`alembic/versions/`) |
| `database_utils/` | The library package (see below) |
| `tests/` | 18 test files, ~130 tests (`pytest.ini`: `asyncio_mode = auto`; in-memory SQLite) — incl. `test_attested_adoption.py` (ba1 migration/seed/schema guardrails) and `test_client_install_field_drop.py` (cf1 guardrails + single-head file scan) |
| `scripts/resync_billing_cents.sql` | Ad-hoc billing cents resync helper |
| `.github/workflows/ci.yml` | PR/push CI: migration guard, ruff (advisory), pytest on 3.12 |
| `.github/workflows/migrate.yml` | Prod migration on push to `main` (`alembic/**` path filter, `DB_URL` secret) |
| `docs/` | Documentation wiki ([docs/README.md](docs/README.md)) |

## `database_utils/` Package

### Core

| Path | Contents |
|---|---|
| `database.py` | Engine bootstrap: `DATABASE_URL` or `DB_URL` or composed `POSTGRES_*` (raises at import if none); `pool_pre_ping`, `pool_recycle=3600`; exports `SessionLocal`, `Base` |
| `dependencies/db.py` | `get_db` FastAPI session dependency (rollback + close) |
| `dependencies/audit.py` | `AuditContext`, `get_client_ip` (proxy-aware), `get_audit_context[_optional]` |
| `middleware/logging_middleware.py` | `create_logging_middleware` — request-ID + JWT-context + duration ASGI middleware |
| `constants/roles.py` | `Roles`: ADMIN / MANAGER / SALES / USER |
| `services/email_service.py` | Abstract `EmailService` + Mock + SMTP impl (aiosmtplib); 7 transactional email kinds; the 4 auth kinds (confirmation, invitation, password_reset, welcome) take `locale: str = "es"` as last keyword param with localized Uplink subjects (`_UPLINK_SUBJECTS` es/en dict); selected via `EMAIL_PROVIDER`, `SMTP_USE_TLS` |
| `templates/email/*.html` | 13 Jinja2 templates: `base_uplink` (Uplink-branded shell) + es/en pairs for confirmation/invitation/password_reset/welcome; legacy `base_layout`, join_request_decision, payment_failed, payment_receipt. `render_email(name, locale)` resolves `{stem}.{locale}.html` → `{stem}.es.html` → `{stem}.html` |

### Models (`models/` — all UUID v4 PKs, created_at/updated_at; registered in `models/__init__.py` for Alembic autogenerate)

| Module | Models (table names) |
|---|---|
| `auth.py` | Tier (tier), Company (company), Permission (permission), Role (role), User (user), Notification (notification), AuditLog (audit_log), UserInvitation (user_invitation), EmailVerificationToken (email_verification_token), PasswordResetToken (password_reset_token), Subscription (subscription), PaymentMethod (payment_method), BillingInvoice (billing_invoice), TierChangeRequest (tier_change_request), BillingWebhookEvent (billing_webhook_event — rb1, `svix_id` string PK + `event_type`/`created_at`, Recurrente webhook delivery idempotency log); **Recurrente billing (rb1)**: `Tier.recurrente_product_id`/`recurrente_price_id`/`recurrente_price_yearly_id` (NULL price id = not purchasable online), `Company.recurrente_customer_id` (lazy, first checkout), `Subscription.recurrente_subscription_id` (unique)/`recurrente_checkout_id`/`card_last4`/`card_brand`, `BillingInvoice.recurrente_intent_id` (unique — webhook charge idempotency) |
| `crm.py` | Client (client — `installation_status`/`installation_date` + the `InstallationStatus` enum DROPPED by `cf1_drop_client_install_fields`; install truth is `client_service.install_state`, lists derive `services_total`/`services_installed` rollups in backend-erp), Product (product — legacy, absorbed by catalog merge), Order (order), OrderItem (order_item), RecurringOrder (recurring_order) + RecurringOrderItem (legacy billing, dual-written; consumed by cron-erp), Invoice (invoice), Payment (payment — Cycle 1 ledger), CustomFieldDefinition / ClientCustomFieldValue, TaskState (task_state), Task (task, `task_assignee` M2M), TaskTemplate (task_template), Integration (integration) |
| `isp.py` | ServicePlan (service_plan), ClientService (client_service), ServiceSuspension (service_suspension), DeviceCategory (device_category — global SaaS-admin table), DeviceType (device_type), Warehouse (warehouse), InventoryItem (inventory_item), EquipmentEvent (equipment_event), Topology (topology), TopologyDeviceType (topology_device_type), TopologyPlaybook (topology_playbook — purpose-keyed), Playbook (playbook), ProvisioningJob (provisioning_job); **Cycle 4 insights**: InsightDashboard (insight_dashboard), InsightChart (insight_chart); **Cycle 5 network config**: NetworkAccess (network_access), DeviceCredential (device_credential), AcsDeviceRegistration (acs_device_registration), ProvisioningSettings (provisioning_settings), DeviceActionLog (device_action_log); **Cycle 7 core config (nc2a)**: no new tables — new columns on existing ones: `device_category.tier` (CORE/EDGE), `device_type.cli_platform`, `inventory_item` mgmt surface (`mgmt_host`/`mgmt_port`/`cli_protocol`/`mgmt_last_check_at`/`mgmt_last_check_ok`), `topology_device_type.inventory_item_id` (pinned shared-core device), `client_service.install_state` + `installed_at`; **Cycle 8 topology-owned playbooks (c8a)**: `Playbook` drops `target_vendor`/`target_category_id` (+ FK) and gains `topology_id` (nullable FK → topology, ON DELETE CASCADE, indexed — NULL = system/global playbook, non-NULL = inline playbook owned by that topology); **Brownfield adoption (ba1)**: `ClientService` gains `adopted_at`/`adopted_by_user_id` (FK → user, SET NULL)/`adoption_note` + partial index `ix_client_service_adopted`, plus `ACTIVATION_EVIDENCE_*` constants for the backend-computed `activation_evidence` field — see [docs/network-models.md](docs/network-models.md) |
| `workflow.py` | WorkflowTemplate (workflow_template), Workflow (workflow), WorkflowTrigger (workflow_trigger), WorkflowStep (workflow_step), WorkflowStepEdge (workflow_step_edge), WorkflowExecution / WorkflowStepExecution |

Key enums: `OrderStatus`, `OrderType`, `PaymentStatus`, `PaymentKind`, `PaymentMethodType`, `RecurrenceEnum`, `ServiceAvailability` (`InstallationStatus` removed by cf1), `TaskStateColor`, `TaskLinkedObjectType`, `IntegrationAuthType`, `ServicePlanType`, `CatalogKind`, `ClientServiceStatus`, `SuspensionReason`, `ProvisioningJobStatus` (incl. Cycle-5 `PENDING_INFORM`), `ProvisioningTrigger`, `TriggerEventType`, `StepActionType`, `ExecutionStatus`, `InsightChartType`. Cycle-5/7 driver-bounded value sets are CHECK-constrained strings, not PG enums: `CREDENTIAL_KINDS`, `NETWORK_ACCESS_KINDS`, `NETWORK_ACCESS_MODES`; Cycle 7 adds `DEVICE_CATEGORY_TIERS` (CORE/EDGE), `CLI_PROTOCOLS` (ssh/telnet), `INSTALL_STATES` (NOT_INSTALLED/IN_PROGRESS/INSTALLED).

### Schemas (`schemas/` — 42 modules, Pydantic v2; `__init__.py` star-imports + `model_rebuild()`)

client, company, custom_field, invoice, notification, order, order_item, payment,
permission, product, recurring_order, requests (Login + flat company-only Signup), role, task,
task_state, task_template, user, workflow, integration, service_plan,
client_service, inventory, topology, playbook, workflow_template, tier,
subscription, payment_method, billing_invoice, tier_change_request, invitation,
audit_log, device_category, email_verification, password_reset, pagination
(`PaginatedResponse[T]`); **Cycle 4**: insight; **Cycle 5**: acs_registration,
device_credential, network_access, provisioning_settings. (`schemas/network.py`
— the old graph schema — was deleted with the graph removal (c2d); unrelated to
the Cycle-5 network-config schemas above.) **Cycle 7** adds no modules — it
extends `device_category` (tier), `inventory` (cli_platform + mgmt surface),
`topology` (`TopologyChainEntryIn` pinned-chain write shape), `playbook`
(`target_item_id`, `ping` driver), `client_service` (read-only install state).
**Cycle 8** (c8a) further edits `playbook`: drops `target_vendor`/`target_category`
(`PlaybookBase`) and `target_category_id` (`PlaybookOut`); adds `topology_id` to
`PlaybookOut` and a 1-based `target_position` to `PlaybookStep`.
**Brownfield adoption** (ba1) adds no modules — `client_service` gains the
read-only adoption fields (`adopted_at`/`adopted_by_user_id`/`adoption_note` +
backend-computed `activation_evidence`) and the `ClientServiceAdoptIn` /
`ClientServiceAdoptBulk*` request/response shapes.
**Recurrente billing** (rb1) adds no modules — `SubscriptionOut` gains
`recurrente_subscription_id`/`card_last4`/`card_brand`; `TierOut` gains the three
`recurrente_*` ids; `TierPublic` gains a stamped `purchasable: bool` (endpoint-computed
from `recurrente_price_id` presence — never exposes the raw price id).
**Auth overhaul** (no migration): `requests.SignupCompanyRequest` flattened to
`{company_name, name, email, password (min 8), locale}` and `SignupUserRequest`
**deleted** (users are invitation-only); `locale: Literal["es","en"] = "es"`
added to `ResendConfirmationRequest`, `PasswordResetRequestSchema`, and
`InvitationCreate`; `InvitationAccept` is `{token, name, password (min 8)}`
(`age` removed); `PasswordResetConfirmSchema.new_password` min raised 6 → 8 —
see [docs/schemas.md](docs/schemas.md) + [docs/email-service.md](docs/email-service.md).

### Utilities (`utils/` — 21 modules)

| Module | Role |
|---|---|
| `workflow_engine.py` (57.7 KB, largest file) | Trigger matching + async DAG execution (`check_workflow_triggers`, `execute_workflow`, `execute_step`) |
| `provisioning_resolution.py` | Topology → purpose → playbook + per-chain-position device resolution (moved down from backend-erp); Cycle 7: pinned positions resolve to the topology's pinned item (`PINNED_DEVICE_UNAVAILABLE` on failure) + `device{i}_category_tier` variable |
| `jwt_utils.py` | HS256 create/decode; `SECRET_KEY`, `ACCESS_TOKEN_EXPIRE`, `REFRESH_TOKEN_EXPIRE`; fails fast in production if `SECRET_KEY` unset |
| `permission_utils.py` | `PermissionChecker` / require-permission dependencies |
| `audit_utils.py` | log_create/update/delete/custom operation helpers |
| `ssrf.py` | `validate_url_no_ssrf` blocklist (integrations + workflow HTTP_REQUEST) |
| `crypto.py` | AES-256-GCM envelope encryption for device credentials (Cycle 5): `CREDENTIALS_KEKS`, `CREDENTIALS_ACTIVE_KEK_ID`; wrap/unwrap DEKs, KEK rotation |
| `workflow_fields.py` | Trigger-context variable/field handling |
| `tier_limits.py`, `pagination_utils.py`, `timezone_utils.py`, `token_utils.py`, `password.py`, `order_typing.py`, `json_utils.py`, `email_templates.py`, `error_handling.py`, `exception_handlers.py`, `logging_utils.py`, `telemetry_utils.py`, `router_factory.py` | Supporting helpers (see [docs/utilities.md](docs/utilities.md)) |

## Alembic (`alembic/`)

`env.py` imports all four model modules; after `upgrade` it runs `_run_seeds(connection)`:
`alembic/seeds/rbac_seed.py`, `alembic/seeds/tier_seed.py`, `alembic/seeds/isp_seed.py` — all idempotent (importable as `seeds.*` because `env.py` adds the alembic dir to `sys.path`).

Notable revision chains (base: `f612571eaad0_initial_schema_with_uuid`):

- **Cycle 1 billing**: `c1a_billing_ddl` → `c1b_backfill` → `c1c_payment_ledger` → `c1e_install_actions` (**irreversible** ALTER TYPE) → `c1f_verify_grandfather`
- **Cycle 2 merge/topology**: `c2a_catalog_merge` → `c2b_service_billing` → `c2c_topology_device_chain_playbook` → `c2d_graph_removal` → `c2e_step_exec_snapshot`
- **Cycle 3**: `c3a_topology_purpose_playbooks`, `c3b_device_categories_global_table`
- **Cycle 4 insights**: insight dashboard/chart tables
- **Cycle 5 network config**: `nc1a` (five network tables + `ProvisioningJob` columns + `PENDING_INFORM` via `ALTER TYPE … ADD VALUE` + 17 permissions) → `nc1b` (append-only `device_action_log` trigger)
- **Cycle 7 core config**: `nc2a_core_config` (hand-written, additive, guarded/idempotent: `device_category.tier` + backfill, `device_type.cli_platform`, `inventory_item` mgmt surface, `topology_device_type.inventory_item_id` FK SET NULL, `client_service.install_state`/`installed_at`; three new CHECK constraints)
- **Grandfathered verification**: `t2_grandfather_email_verified` — backfills `user.email_verified = TRUE` for all pre-overhaul users (login-gate lockout guard)
- **Brownfield adoption**: `ba1_attested_adoption` — additive `client_service` adoption columns + FK + partial index `ix_client_service_adopted` + ADMIN-only `client_services.adopt` permission (MANAGER excluded at both seed auto-grant sites: `isp_seed.ADMIN_ONLY_PERMISSIONS` / `rbac_seed.MANAGER_EXCLUDED_PERMISSIONS`)
- **Client install-field removal**: `cf1_drop_client_install_fields` — data cleanup BEFORE DDL (deletes installed `UPDATE_FIELD` workflow steps writing the dropped fields with edge rerouting; deletes clients insight charts using the `installation_status` dimension/filter), then drops `client.installation_status`/`installation_date` and the `installationstatus` PG enum; downgrade recreates structure only (data not restorable)
- **Free/Trial unlimited**: `t1_free_trial_unlimited` — data migration setting Free/Trial tier features to unlimited (-1) and modules to the full set; paired with the updated `tier_seed.py` (fresh installs seed the same, `modules` column now seeded)
- **Recurrente tenant billing**: `rb1_recurrente_billing` (parent `cf1`, **head**) — additive only: `recurrente_*` gateway columns on tier/company/subscription/billing_invoice (unique on `subscription.recurrente_subscription_id` and `billing_invoice.recurrente_intent_id`) + new `billing_webhook_event` table (svix-id PK webhook delivery idempotency log)
- **Cycle 8 topology-owned playbooks**: `c8a_playbook_topology` (hand-written, guarded/idempotent with in-migration assertions) — drops `playbook.target_vendor` + `playbook.target_category_id` (+ its FK), adds `playbook.topology_id` (FK → topology ON DELETE CASCADE, nullable, indexed `ix_playbook_topology_id`); no backfill (topology_id NULL until the topology editor re-saves)
- **ISP core**: `cd2f0076c709_isp_platform_core_service_plans_`; plus tenant indexes (`a1f2b3c4d5e6`), timezone fixes, task/workflow/integration modules

## Relationships

- `backend-erp` — pins by SHA; uses models, schemas, `get_db`, permission/audit utils, workflow engine, provisioning models/resolution
- `auth-erp` — pins by SHA; uses auth models/schemas, jwt_utils, email service + templates, SaaS billing models
- `cron-erp` — pip dependency; RecurringOrder models
- `frontend-erp` — no direct dependency; consumes JSON shaped by these schemas via backend proxies
- Repo-root `docker-compose.yml` — `migrate` service builds this repo's Dockerfile
