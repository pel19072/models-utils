# utils/provisioning_resolution.py
"""
Provisioning resolution (Cycle 2 D5, doc 18a topology-networking §5). Moved
into models-utils in Cycle 3 E2 (doc 20a workflow-provisioning §0) from
backend-erp services/provisioning_resolution.py so the workflow engine's
ENQUEUE_PROVISIONING use_topology mode can call it directly: the engine
(models-utils) cannot import backend-erp, and backend-erp already imports
models-utils, so moving resolution down the stack is the only import
direction that compiles. backend-erp's manual POST /client-services/{id}/
provision endpoint now imports this module instead of its own deleted copy.

topology -> purpose -> playbook (topology_playbook, revision
c3a_topology_purpose) + per-chain-position concrete device, resolved from the
client's assigned inventory items matched BY TYPE (no coordinate/graph — the
free-form network graph was removed in c2d_graph_removal).

Founder decision: ambiguity is never auto-resolved — 0 matches fails
MISSING_DEVICE, >1 matches fails AMBIGUOUS_DEVICE with the candidate list.

Cycle 3 changes (doc 20/20a, E1/E2):
- `purpose` parameter (default ACTIVATION) selects the topology_playbook
  entry instead of the old single `topology.playbook`. New error codes
  PURPOSE_NOT_CONFIGURED (topology has no entry for `purpose`) and
  PLAYBOOK_INACTIVE (entry exists, playbook inactive) join TOPOLOGY_NOT_SET /
  TOPOLOGY_INACTIVE / RESOLUTION_FAILED.
- Amendment 2 (E2xE4 alias derivation, doc 20 normative amendments #2):
  device_type.category is now a `@property` reading a DeviceCategory FK
  relationship (revision c3b_device_categories), not a PG enum with
  `.value` — the alias key is `device_type.category` directly (already a
  plain string key or None), normalized `.lower()`, keeping aliases
  byte-identical across the enum->FK migration (cpe_router_serial,
  onu_serial, ...).
- Amendment 4 (doc 20 normative amendments #4, appendix workflow-provisioning
  §3 option (c)): for non-ACTIVATION purposes, a device-chain resolution
  error (MISSING_DEVICE/AMBIGUOUS_DEVICE) is fatal only when the resolved
  playbook's own template actually references a device-derived variable.
  ACTIVATION keeps the original founder hard-fail-visibly behavior
  unconditionally.

Namespaced variables (doc 33, revision pv1 — founder decision 2026-07-20):
every emitted variable now carries a namespace, replacing the flat
device{i}_* names and the unique-category aliases (onu_serial, ...), which
are GONE. Nothing bare survives, so a typo can never silently resolve to an
unrelated value:

  edge_devices[n].<attr> / core_devices[n].<attr>   n = 0-based WITHIN tier
  chain[n].<attr>                                   n = 1-based absolute
                                                    position; hidden from the
                                                    editor, backs step
                                                    targeting where only the
                                                    chain position is known
  service_plan.<field|param>                        plan fields + the plan's
                                                    tenant-authored rows
  client.<attr>                                     subscriber context: built-in
                                                    fields + the tenant's own
                                                    custom client attributes
                                                    (built-ins win a collision)
  service.<attr>                                    the client_service itself
  input.<key>                                       author-declared playbook
                                                    variables (applied at
                                                    reference; the declared
                                                    key itself stays bare)

`variables` remains a FLAT dict — the KEYS are the full dotted/indexed
strings. There is no nested structure to walk, which keeps the renderer a
pure dictionary lookup (ADR-006: no expressions, no attribute access).

Cycle 7 changes (doc 25 §3, revision nc2a_core_config):
- Pinned positions: a chain position with topology_device_type
  .inventory_item_id set resolves to THAT item — shared core infrastructure
  (e.g. the topology's OLT), exempt from client/service candidate matching.
  Company checked; status must be RESERVED/INSTALLED, else the position
  fails PINNED_DEVICE_UNAVAILABLE (collected like MISSING_DEVICE, same
  amendment-4 fatality rules).
- New emitted variable per resolved position: device{i}_category_tier
  (CORE/EDGE/empty) for template convenience.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from sqlalchemy import or_
from sqlalchemy.orm import Session

from database_utils.models.isp import (
    ClientService,
    InventoryItem,
    InventoryItemStatus,
    Playbook,
    PURPOSE_ACTIVATION,
    Topology,
    TopologyDeviceType,
    TopologyPlaybook,
)


class ResolutionError(Exception):
    """Raised when a client service's provisioning cannot be resolved.

    `errors` is a list of {code, position?, device_type_id?, device_type_name?,
    candidates?} dicts — collected across ALL chain positions so the caller
    (technician) sees the whole shopping list, not one error per retry.
    """

    def __init__(self, code: str, detail: str, errors: Optional[List[Dict[str, Any]]] = None):
        self.code = code
        self.detail = detail
        self.errors = errors or [{"code": code, "detail": detail}]
        super().__init__(detail)


@dataclass
class ResolvedItem:
    position: int
    device_type_id: Any
    device_type_name: str
    category: Optional[str]
    inventory_item_id: Any
    serial_number: Optional[str]
    mac_address: Optional[str]
    # Cycle 7 (doc 25 §3): the position category's CORE/EDGE tier (None =
    # passives/unclassified) and whether the item came from a topology pin
    # rather than client/service candidate matching. Defaulted so pre-Cycle-7
    # constructors stay valid.
    category_tier: Optional[str] = None
    pinned: bool = False


@dataclass
class ResolvedProvisioning:
    playbook_id: Any
    variables: Dict[str, Any]
    resolved_items: List[ResolvedItem] = field(default_factory=list)


INPUT_NAMESPACE = "input"


def input_key(key: str) -> str:
    """The token an author-declared variable is referenced by (doc 33).

    The declaration keeps its bare snake_case `key` — the authoring form and
    its validator are untouched — and the namespace is applied at REFERENCE
    time. Lives here, not in backend-erp's renderer, because the workflow
    engine also produces author variables and models-utils cannot import
    backend-erp (import direction is strictly downward)."""
    return key if key.startswith(f"{INPUT_NAMESPACE}.") else f"{INPUT_NAMESPACE}.{key}"


SCOPE_PLAN = "plan"
SCOPE_SERVICE = "service"


def iter_provisioning_params(params: Any):
    """Yield (key, value, scope) from a provisioning_params column.

    The stored shape is a LIST of {"key", "value", "description", "scope"} rows
    so the UI can carry a human explanation per parameter and mark which ones
    are valued per service. The pre-namespace shape was a bare {"vlan": 110}
    dict; the `pv1` revision converts every row, but this reader stays tolerant
    of both so a hand-written dict (or an xlsx import) never explodes at
    provisioning time. A row with no `scope` is plan-scoped, which is what
    every row written before this feature is."""
    if not params:
        return
    if isinstance(params, dict):
        for key, value in params.items():
            yield str(key), value, SCOPE_PLAN
        return
    if isinstance(params, list):
        for row in params:
            if isinstance(row, dict) and row.get("key"):
                scope = row.get("scope") or SCOPE_PLAN
                yield str(row["key"]), row.get("value"), str(scope)


def _service_param_values(client_service: Any) -> Dict[str, Any]:
    """The per-service VALUES, keyed. The service supplies only values — the
    plan owns the declaration — so anything here that the plan does not declare
    is ignored rather than emitted as a stray variable."""
    values: Dict[str, Any] = {}
    for key, value, _scope in iter_provisioning_params(
        getattr(client_service, "provisioning_params", None)
    ):
        values[key] = value
    return values


def _is_blank(value: Any) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


# A namespace segment the renderer can actually match. `field_key` is
# validated as alnum+underscore and lowercased, which still permits a leading
# digit ("5g_profile") — that would produce a token no one can reference, so
# such keys are skipped rather than emitted as dead weight.
_REFERENCEABLE_KEY = re.compile(r"^[a-z][a-z0-9_]*$")


def _coerce_custom_value(value: Optional[str], field_type: Any) -> Any:
    """Custom field values are all stored as strings; give NUMBER/BOOLEAN their
    natural type so a template renders `100` rather than `100.0`, and so a
    boolean reads as true/false instead of the literal string."""
    if value is None:
        return ""
    kind = getattr(field_type, "value", field_type)
    kind = str(kind).upper() if kind is not None else ""
    if kind == "NUMBER":
        try:
            number = float(value)
        except (TypeError, ValueError):
            return value
        return int(number) if number.is_integer() else number
    if kind == "BOOLEAN":
        return str(value).strip().lower() in ("true", "1", "yes", "y")
    return value


def iter_client_custom_fields(client: Any):
    """Yield (field_key, typed value) for a client's custom attributes.

    Reads the `client_custom_field_value` -> `custom_field_definition` join the
    Client model already exposes as `custom_field_values`. Degrades to nothing
    when the relationship is absent (detached/partial objects, tests) — a
    missing attribute must never crash a provisioning job."""
    for row in getattr(client, "custom_field_values", None) or []:
        definition = getattr(row, "field_definition", None)
        key = getattr(definition, "field_key", None)
        if not key or not _REFERENCEABLE_KEY.match(key):
            continue
        yield key, _coerce_custom_value(getattr(row, "value", None),
                                        getattr(definition, "field_type", None))


def get_topology_playbook(topology: Topology, purpose: str) -> Optional[TopologyPlaybook]:
    """Look up the topology_playbook row bound to `purpose`, or None if the
    topology has no entry for it. Extracted as a tiny module-level helper
    (doc 20a D-E1.4) so resolve_provisioning and any other caller needing the
    same purpose-map lookup (e.g. the engine, if it ever needs it directly)
    share one lookup semantics — never two implementations that could drift."""
    return next((tp for tp in topology.playbooks if tp.purpose == purpose), None)


# Amendment 4: a device-derived variable is any token in the tier-indexed
# device namespaces, or the hidden absolute-position `chain[n]` alias.
# (Pre-namespace this matched device{i}_* and unique-category aliases like
# onu_serial; both are gone — see the module docstring.)
# The optional `| filter ...` suffix (doc 34) must be tolerated here, or a
# token carrying a filter reads as NOT device-derived and amendment 4 silently
# downgrades a MISSING_DEVICE from fatal. Both of these patterns FAIL OPEN, so
# forgetting the suffix is a correctness bug, not a syntax error.
_FILTER_SUFFIX = r'(?:\s*\|[^{}\n]*)?'

_DEVICE_VARIABLE_PATTERN = re.compile(
    r'\{\{\s*(?:edge_devices|core_devices|chain)\[\d+\]\.[a-z][a-z0-9_]*'
    + _FILTER_SUFFIX + r'\s*\}\}'
)

# Attributes emitted for every resolved device, in all three device
# namespaces. Keep in sync with the editor catalog in frontend-erp
# (lib/playbookVariables.ts) — the editor is the only place an operator
# discovers these.
DEVICE_ATTRIBUTES = ("item_id", "serial", "mac", "type", "category_tier", "position")


def _playbook_references_token(playbook: Playbook, token: str) -> bool:
    """Whether the playbook's own definition templates this exact token.

    Used to decide whether a missing per-service parameter is fatal: declaring
    `pppoe_user` per-service must not block a SUSPENSION playbook that never
    reads it. Same posture as `_playbook_references_device_variables` — fail
    safe (treat as referenced) when the definition cannot be introspected."""
    try:
        blob = json.dumps(playbook.definition)
    except (TypeError, ValueError):
        return True
    return re.search(
        r"\{\{\s*" + re.escape(token) + _FILTER_SUFFIX + r"\s*\}\}", blob
    ) is not None


def _playbook_references_device_variables(playbook: Playbook) -> bool:
    """Amendment 4 (doc 20 normative amendments #4, appendix workflow-
    provisioning §3 option (c)): for non-ACTIVATION purposes, a device-chain
    resolution error is fatal only when the playbook's own template actually
    reads a device-derived variable. A suspend/reactivate/deprovision
    playbook that never templates a device variable (e.g. it only flips a
    VLAN via a stored integration) must not fail just because the chain is
    ambiguous or missing equipment — e.g. DEPROVISION fired after the tech
    already recovered the CPE, or SUSPENSION with two client-assigned CPEs
    and none service-bound."""
    try:
        blob = json.dumps(playbook.definition)
    except (TypeError, ValueError):
        return True  # cannot introspect -> fail safe, treat as device-referencing
    return bool(_DEVICE_VARIABLE_PATTERN.search(blob))


def resolve_provisioning(
    db: Session,
    client_service: ClientService,
    purpose: str = PURPOSE_ACTIVATION,
) -> ResolvedProvisioning:
    """Resolve a client_service's topology into a playbook_id + rendered
    variables + the concrete device chain, or raise ResolutionError.

    Algorithm (doc 18a §5, purpose lookup + amendment 4 per doc 20a D-E1.4/§3):
    1. topology = client_service.topology; None -> TOPOLOGY_NOT_SET.
       not topology.is_active -> TOPOLOGY_INACTIVE.
       no topology_playbook entry for `purpose` -> PURPOSE_NOT_CONFIGURED.
       entry's playbook missing/inactive -> PLAYBOOK_INACTIVE.
    2. chain = topology.device_types ordered by position.
    3. Candidate pool: InventoryItem WHERE company_id=svc.company_id AND
       status IN (RESERVED, INSTALLED) AND (client_service_id = svc.id OR
       (client_id = svc.client_id AND client_service_id IS NULL)).
    4. Per chain position (Cycle 7, doc 25 §3): a PINNED position
       (topology_device_type.inventory_item_id set) resolves to that item
       directly — company checked, status must be RESERVED/INSTALLED else
       PINNED_DEVICE_UNAVAILABLE; pinned items are exempt from the candidate
       pool of step 3. Otherwise match candidates by device_type_id.
       Preference: service-assigned beats client-only; within a tier, >1
       candidate -> AMBIGUOUS_DEVICE (never auto-pick); 0 -> MISSING_DEVICE.
    5. Errors collected across ALL positions. For purpose == ACTIVATION they
       are ALWAYS fatal (founder fail-visibly requirement for installs). For
       any other purpose, they are fatal only when the resolved playbook's
       template actually references a device-derived variable (amendment 4);
       otherwise resolution proceeds with whatever positions DID resolve
       (possibly none).
    6. Variables injected for the playbook renderer (snake_case only):
       client_service_id, service_plan_id, download_mbps, upload_mbps (from
       the plan, NULL-safe), service_plan.provisioning_params merged in,
       plus per resolved position i (1-based): device{i}_item_id/_serial/
       _mac/_type/_category_tier (Cycle 7), plus a category-alias (e.g.
       cpe_router_serial) only when
       that category is unique within the chain. Caller-passed variables (if
       any) override resolved ones (caller wins) — handled by the caller,
       not here.
    """
    topology: Optional[Topology] = client_service.topology
    if topology is None:
        raise ResolutionError("TOPOLOGY_NOT_SET", "Client service has no topology configured")
    if not topology.is_active:
        raise ResolutionError("TOPOLOGY_INACTIVE", f"Topology '{topology.name}' is not active")

    entry = get_topology_playbook(topology, purpose)
    if entry is None:
        raise ResolutionError(
            "PURPOSE_NOT_CONFIGURED",
            f"Topology '{topology.name}' has no playbook for purpose '{purpose}'",
        )
    playbook = entry.playbook
    if playbook is None or not playbook.is_active:
        raise ResolutionError("PLAYBOOK_INACTIVE", f"Topology's '{purpose}' playbook is not active")

    chain: List[TopologyDeviceType] = sorted(topology.device_types, key=lambda x: x.position)
    if not chain:
        raise ResolutionError("TOPOLOGY_NOT_SET", f"Topology '{topology.name}' has no device-type chain")

    candidates = (
        db.query(InventoryItem)
        .filter(
            InventoryItem.company_id == client_service.company_id,
            InventoryItem.status.in_([InventoryItemStatus.RESERVED, InventoryItemStatus.INSTALLED]),
            or_(
                InventoryItem.client_service_id == client_service.id,
                (InventoryItem.client_id == client_service.client_id)
                & (InventoryItem.client_service_id.is_(None)),
            ),
        )
        .all()
    )

    errors: List[Dict[str, Any]] = []
    resolved_items: List[ResolvedItem] = []

    for tdt in chain:
        device_type = tdt.device_type
        category_tier = (
            device_type.category_ref.tier
            if device_type is not None and device_type.category_ref is not None
            else None
        )

        # Cycle 7 (doc 25 §3 step 1): pinned shared device wins. Pinned items
        # are exempt from the client/service candidate pool above — they are
        # shared infrastructure (one OLT serves many subscribers), so they are
        # loaded directly (company checked) instead of matched by assignment.
        pinned_id = getattr(tdt, "inventory_item_id", None)
        if pinned_id is not None:
            item = db.get(InventoryItem, pinned_id)
            if (
                item is None
                or item.company_id != client_service.company_id
                or item.status not in (InventoryItemStatus.RESERVED, InventoryItemStatus.INSTALLED)
            ):
                errors.append({
                    "code": "PINNED_DEVICE_UNAVAILABLE",
                    "position": tdt.position,
                    "device_type_id": str(tdt.device_type_id),
                    "device_type_name": device_type.name if device_type else "",
                    "inventory_item_id": str(pinned_id),
                })
                continue
            resolved_items.append(ResolvedItem(
                position=tdt.position,
                device_type_id=tdt.device_type_id,
                device_type_name=device_type.name if device_type else "",
                category=device_type.category if device_type else None,
                inventory_item_id=item.id,
                serial_number=item.serial_number,
                mac_address=item.mac_address,
                category_tier=category_tier,
                pinned=True,
            ))
            continue

        type_candidates = [c for c in candidates if c.device_type_id == tdt.device_type_id]

        if not type_candidates:
            errors.append({
                "code": "MISSING_DEVICE",
                "position": tdt.position,
                "device_type_id": str(tdt.device_type_id),
                "device_type_name": device_type.name if device_type else "",
            })
            continue

        # Preference: service-assigned beats client-only.
        service_assigned = [c for c in type_candidates if c.client_service_id == client_service.id]
        tier = service_assigned if service_assigned else type_candidates

        if len(tier) > 1:
            errors.append({
                "code": "AMBIGUOUS_DEVICE",
                "position": tdt.position,
                "device_type_id": str(tdt.device_type_id),
                "device_type_name": device_type.name if device_type else "",
                "candidates": [
                    {
                        "inventory_item_id": str(c.id),
                        "serial_number": c.serial_number,
                        "mac_address": c.mac_address,
                    }
                    for c in tier
                ],
            })
            continue

        item = tier[0]
        resolved_items.append(ResolvedItem(
            position=tdt.position,
            device_type_id=tdt.device_type_id,
            device_type_name=device_type.name if device_type else "",
            # Amendment 2 (E2xE4 alias derivation): device_type.category is a
            # @property over the device_category FK relationship (revision
            # c3b_device_categories) — already a plain string key or None, no
            # `.value` (that was the enum-era access pattern; a plain str has
            # no `.value` attribute, which is exactly the silent-failure trap
            # the unconverted line would have been).
            category=device_type.category if device_type else None,
            inventory_item_id=item.id,
            serial_number=item.serial_number,
            mac_address=item.mac_address,
            category_tier=category_tier,
        ))

    if errors:
        device_errors_fatal = (
            purpose == PURPOSE_ACTIVATION or _playbook_references_device_variables(playbook)
        )
        if device_errors_fatal:
            raise ResolutionError(
                "RESOLUTION_FAILED",
                "One or more chain positions could not be resolved to a concrete device",
                errors=errors,
            )
        # Amendment 4: non-ACTIVATION purpose, device-free playbook — proceed
        # with whatever positions DID resolve (possibly zero). The operator
        # is not blocked from suspending/deprovisioning a service whose
        # equipment state doesn't matter to this playbook.

    missing_service_params: List[Dict[str, Any]] = []
    variables: Dict[str, Any] = {
        "service.id": str(client_service.id),
    }

    # getattr, not attribute access: resolution runs against detached/partial
    # ClientService objects too (the workflow engine, tests), and a missing
    # relationship must degrade to "no client variables", never crash a job.
    client = getattr(client_service, "client", None)
    if client is not None:
        variables["client.id"] = str(client.id)
        variables["client.name"] = client.name or ""
        variables["client.email"] = client.email or ""
        variables["client.phone"] = client.phone or ""
        variables["client.address"] = client.address or ""
        # The tenant's own client attributes, exactly as a service plan's
        # provisioning parameters work — a per-subscriber value an operator
        # defines in the CRM and templates in a playbook.
        for key, value in iter_client_custom_fields(client):
            token = f"client.{key}"
            # Built-in fields win: a custom field keyed `name` must not shadow
            # the subscriber's actual name in a template that already reads it.
            if token in variables:
                continue
            variables[token] = value

    plan = getattr(client_service, "service_plan", None)
    if plan is not None:
        variables["service_plan.id"] = str(plan.id)
        variables["service_plan.name"] = plan.name or ""
        if plan.download_mbps is not None:
            variables["service_plan.download_mbps"] = plan.download_mbps
        if plan.upload_mbps is not None:
            variables["service_plan.upload_mbps"] = plan.upload_mbps
        # Tenant-authored rows land under the plan's own namespace instead of
        # being flattened into the global one, so a plan parameter can never
        # collide with (or shadow) a system variable.
        #
        # A `service`-scoped row is DECLARED by the plan but VALUED by this
        # service, and still resolves under the plan's namespace: the playbook
        # author writes {{service_plan.<key>}} either way and never has to edit
        # a template when a parameter's scope changes.
        service_values = _service_param_values(client_service)
        for key, value, scope in iter_provisioning_params(plan.provisioning_params):
            if scope == SCOPE_SERVICE:
                value = service_values.get(key)
                if _is_blank(value):
                    # Recorded, not raised: whether this is fatal depends on
                    # the playbook actually referencing it (checked below),
                    # exactly as an unresolved device position does.
                    missing_service_params.append({
                        "code": "MISSING_SERVICE_PARAM",
                        "key": key,
                        "token": f"service_plan.{key}",
                        "service_plan_name": plan.name,
                        "detail": (
                            f"'{key}' is declared per-service on plan "
                            f"'{plan.name}' but this service has no value for it"
                        ),
                    })
                    continue
            variables[f"service_plan.{key}"] = value

    # Devices are addressed by their index WITHIN a tier (0-based), because
    # that is what an operator can actually see and reason about ("the second
    # ONT"), plus a hidden absolute-position `chain[n]` alias (1-based) that
    # backs step targeting, where only the chain position is in scope.
    tier_counters: Dict[str, int] = {}
    for ri in resolved_items:
        attrs = {
            "item_id": str(ri.inventory_item_id),
            "serial": ri.serial_number or "",
            "mac": ri.mac_address or "",
            "type": ri.device_type_name,
            "category_tier": ri.category_tier or "",
            "position": ri.position + 1,
        }
        namespaces = [f"chain[{ri.position + 1}]"]
        tier = (ri.category_tier or "").upper()
        if tier in ("EDGE", "CORE"):
            prefix = "edge_devices" if tier == "EDGE" else "core_devices"
            index = tier_counters.get(prefix, 0)
            tier_counters[prefix] = index + 1
            namespaces.append(f"{prefix}[{index}]")
        for namespace in namespaces:
            for attr, value in attrs.items():
                variables[f"{namespace}.{attr}"] = value

    # A per-service parameter with no value is fatal only when the playbook
    # actually reads it — the same rule that governs unresolved device
    # positions (amendment 4). A SUSPENSION playbook that never templates
    # {{service_plan.pppoe_user}} must not be blocked because some unrelated
    # parameter was left blank.
    referenced_missing = [
        err for err in missing_service_params
        if _playbook_references_token(playbook, err["token"])
    ]
    if referenced_missing:
        raise ResolutionError(
            "RESOLUTION_FAILED",
            "One or more per-service provisioning parameters have no value",
            errors=referenced_missing,
        )

    return ResolvedProvisioning(
        playbook_id=playbook.id,
        variables=variables,
        resolved_items=resolved_items,
    )
