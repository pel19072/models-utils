# Network Configuration Models

## Description
SQLAlchemy models for Uplink's network configuration layer. Cycle 5 Phase 1
(TR-069 / GenieACS CPE management) added revisions **nc1a** (five tables +
`ProvisioningJob` extensions + `PENDING_INFORM` status) and **nc1b** (the append-only
trigger on `device_action_log`). Cycle 7 Phase 2 (core-device CLI config, doc 25)
added revision **nc2a_core_config** — no new tables, only columns on existing ones
(see the Cycle 7 section below). All live in `database_utils/models/isp.py`.

## Goal
Persist per-tenant device secrets, transport config, the serial→tenant mapping that
makes a shared multi-tenant-blind GenieACS safe, the provisioning enable gate, and an
immutable device audit trail — plus the durable-job columns for resumable, per-device,
idempotent execution.

## New Models (in `database_utils/models/isp.py`)

| Model | Table | Key Fields | Purpose |
|-------|-------|-----------|---------|
| `DeviceCredential` | `device_credential` | name, kind (CHECK: CREDENTIAL_KINDS), username, `secret_ciphertext`/`dek_wrapped`/`kek_id`, fingerprint, binding FKs (inventory_item/device_type/network_access) | Envelope-encrypted per-tenant device secret (canon C1/C19). Secret never round-trips — Out schema exposes only `has_secret` + fingerprint |
| `NetworkAccess` | `network_access` | name, kind (CHECK: acs\|olt), mode (CHECK: direct\|vpn\|tunnel), is_default, mgmt_subnets (JSON CIDRs), acs_base_url | Per-tenant transport config (canon C9); the resolver longest-prefix-matches mgmt address, else the default row |
| `AcsDeviceRegistration` | `acs_device_registration` | serial_number, oui, company_id (**nullable** = QUARANTINED), genieacs_device_id, first/last_inform_at, cwmp_cr_* connection-request creds | Serial/OUI→tenant mapping — the tenant-stamping keystone (canon C13); global `(oui, serial)` unique so two tenants can't claim one CPE |
| `ProvisioningSettings` | `provisioning_settings` | company_id (unique), enabled (default **false**), default_inform_interval | Tenant provisioning enable gate — a per-tenant singleton (canon C6). Absence of a row = DISABLED (fail-safe) |
| `DeviceActionLog` | `device_action_log` | actor_kind, actor_user_id, device_kind, device_identity, action, before_data/after_data (secret-redacted JSON), provisioning_job_id | Append-only device audit trail (canon C14). No `updated_at`; immutability enforced by a Postgres `BEFORE UPDATE OR DELETE` trigger (nc1b) |

## `ProvisioningJob` extensions (nc1a)

- `status` gains **`PENDING_INFORM`** (`ProvisioningJobStatus`): the job parks when a
  TR-069 connection-request task returns 202; the worker slot is released and a poller
  settles it once the inform arrives. Added via `ALTER TYPE … ADD VALUE` in an
  autocommit block.
- `dry_run` (bool, default false) — canon C7; a SUCCEEDED dry-run stamps
  `playbook.last_dry_run_version`.
- `pending_step_index` (int) — the parked step to settle on inform.
- `pending_task_ids` (JSON) — GenieACS NBI task ids being polled.
- `heartbeat_at` (datetime) — the lease reaper re-queues stale RUNNING jobs.
- `device_lock_key` (str) — per-device serialization key.
- **Indexes**: the idempotency partial-unique index now includes PENDING_INFORM in the
  in-flight set; a new `uq_provisioning_job_device_lock` partial-unique index enforces
  at most one live job per `device_lock_key` (canon C11).

## Other additive changes (nc1a)

- `playbook.last_dry_run_version` (int) — gates live jobs behind a matching dry-run.
- `device_type.provisioning_enabled` (bool, default true) — per-device-type opt-out gate.
- `inventory_item.oui` (str) — matched against informing CPEs by `acs_sync`.
- `client_service.provisioning_state` (JSON) — learned network identifiers written at
  job settlement, read back by suspension/reactivation/deprovision playbooks.
- **17 new permissions** for the network-config endpoints.

## Cycle 7 (nc2a_core_config) — core-config additions (doc 25 §2)

Phase 2 targets CORE-tier devices (OLTs, routers, switches) over generic
netmiko CLI drivers. All additive columns on existing tables:

| Table | New columns | Purpose |
|---|---|---|
| `device_category` | `tier` (CHECK: `DEVICE_CATEGORY_TIERS` CORE\|EDGE, nullable) | CORE = shared infrastructure (one device serves many subscribers, pinned per topology position); EDGE = per-subscriber CPE; NULL = passives/unclassified. SaaS-admin editable (key stays immutable). nc2a backfills CORE ← ROUTER/SWITCH/OLT, EDGE ← ONU/CPE_ROUTER/ACCESS_POINT by key |
| `device_type` | `cli_platform` (free string, deliberately no CHECK) | netmiko platform id (`huawei_smartax`, `cisco_ios`, ...); NULL → drivers fall back to `generic` / `generic_telnet` |
| `inventory_item` | `mgmt_host`, `mgmt_port`, `cli_protocol` (CHECK: `CLI_PROTOCOLS` ssh\|telnet), `mgmt_last_check_at`, `mgmt_last_check_ok` | Management surface: how CLI drivers reach a CORE device. `mgmt_port` NULL → driver default (22/23). The `mgmt_last_check_*` stamps are worker-owned (written when a `core_connectivity_check` job reaches terminal state), read-only in the API |
| `topology_device_type` | `inventory_item_id` (FK → inventory_item, **ON DELETE SET NULL**, indexed) | Pins the concrete SHARED device serving a chain position (e.g. this topology's OLT). Pinned items are exempt from client/service candidate matching in provisioning resolution. SET NULL: retiring the item never blocks — resolution then fails visibly with MISSING_DEVICE. Same-company / device-type-match / CORE-tier are router validation, not DB constraints |
| `client_service` | `install_state` (NOT NULL default `NOT_INSTALLED`, CHECK: `INSTALL_STATES`), `installed_at`; index `ix_client_service_company_install_state` | Subscriber install state machine (NOT_INSTALLED / IN_PROGRESS / INSTALLED), deliberately **separate** from billing `status`. Written exclusively by backend-erp's `recompute_install_state` (not on Update schemas); `installed_at` stamps the FIRST transition to INSTALLED and is never cleared |

Also in Cycle 7 (same revision cycle, no DDL):
- `PLAYBOOK_DRIVERS` (schemas/playbook.py) gains **`ping`** — backend-erp's
  connectivity-probe driver, used by the per-company `core_connectivity_check`
  system playbooks (doc 25 §4.3/§5.1).
- `PlaybookStep.target_item_id` (+ same field on `PlaybookPrecondition`) — step
  targeting for the CLI/ping drivers: an inventory_item id or a `{{variable}}`
  the executor renders (e.g. `{{device1_item_id}}`).
- Workflow-engine dedupe fix: the `ENQUEUE_PROVISIONING` in-flight pre-check now
  includes `PENDING_INFORM` (matching nc1a's idempotency-index predicate) — see
  [workflow-engine.md](workflow-engine.md).
- `isp_seed.py`: `DEVICE_CATEGORIES` entries carry the tier (ONU display name →
  'ONU / ONT' for fresh inserts); a gated backfill classifies pre-nc2a rows only
  while NO row has a tier yet, so super-admin tier edits (including clear-to-NULL)
  survive every re-seed.

## Open value sets (CHECK-constrained strings, not PG enums)

Following the c3a/c3b precedent, driver-bounded value sets are CHECK-constrained
strings so adding a value is a plain transactional `ALTER` of the CHECK, never the
`ALTER TYPE … ADD VALUE` autocommit dance:

- `CREDENTIAL_KINDS`: SSH, TELNET, SNMP_COMMUNITY, TR069_CONNECTION_REQUEST, HTTP_BASIC,
  HTTP_BEARER, WIREGUARD, AGENT
- `NETWORK_ACCESS_KINDS`: acs, olt · `NETWORK_ACCESS_MODES`: direct, vpn, tunnel
- **Cycle 7**: `DEVICE_CATEGORY_TIERS`: CORE, EDGE · `CLI_PROTOCOLS`: ssh, telnet ·
  `INSTALL_STATES`: NOT_INSTALLED, IN_PROGRESS, INSTALLED (SQL CHECK fragments kept
  byte-identical between `models/isp.py` and the nc2a migration, guarded by
  `tests/test_core_config_constants.py`)

## Connections to Other Components
- **backend-erp** — the `genieacs` driver, worker loops (`acs_sync`, PENDING_INFORM
  poller, lease reaper), blast-radius gates, and the network-config routers consume all
  of these. Credentials are decrypted via `database_utils/utils/crypto.py`.
- **auth-erp `Company`** — back-populates `device_credentials`, `network_accesses`,
  `acs_device_registrations`, `provisioning_settings`, `device_action_logs` (all
  `ondelete=CASCADE`).
- **acs-erp / GenieACS** — `acs_device_registration` maps informing CPEs to tenants.

## Key Implementation Details
- All tables: UUID PK + `created_at` (+ `updated_at` except the append-only
  `device_action_log`).
- `AcsDeviceRegistration.state` is a **derived** property (no enum column):
  QUARANTINED (NULL company) / PRE_REGISTERED / STALE / ONLINE (informed within
  `ACS_STALE_AFTER_SECONDS` = 900).
- Credential binding FKs live **on** the credential row (canon C19); no other table
  carries an FK pointing at a credential. Resolution order: inventory_item >
  device_type > network_access default.

## Environment Variables
- `CREDENTIALS_KEKS`, `CREDENTIALS_ACTIVE_KEK_ID` — envelope-encryption keys (see
  [utilities.md](utilities.md), `crypto.py`).
- `POSTGRES_*` — Database connection.
</content>
