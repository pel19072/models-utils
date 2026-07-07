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


@dataclass
class ResolvedProvisioning:
    playbook_id: Any
    variables: Dict[str, Any]
    resolved_items: List[ResolvedItem] = field(default_factory=list)


def get_topology_playbook(topology: Topology, purpose: str) -> Optional[TopologyPlaybook]:
    """Look up the topology_playbook row bound to `purpose`, or None if the
    topology has no entry for it. Extracted as a tiny module-level helper
    (doc 20a D-E1.4) so resolve_provisioning and any other caller needing the
    same purpose-map lookup (e.g. the engine, if it ever needs it directly)
    share one lookup semantics — never two implementations that could drift."""
    return next((tp for tp in topology.playbooks if tp.purpose == purpose), None)


# Amendment 4: a device-derived variable is either a positional
# device{i}_item_id/_serial/_mac/_type or a unique-category alias like
# cpe_router_serial/onu_mac (category keys are open-ended super-admin data,
# so the suffix is what's matched — no ordinary business variable name ends
# in _serial or _mac).
_DEVICE_VARIABLE_PATTERN = re.compile(
    r'\{\{\s*(device\d+_(?:item_id|serial|mac|type)|[a-z0-9_]+_(?:serial|mac))\s*\}\}'
)


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
    4. Per chain position, match candidates by device_type_id. Preference:
       service-assigned beats client-only; within a tier, >1 candidate ->
       AMBIGUOUS_DEVICE (never auto-pick); 0 -> MISSING_DEVICE.
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
       _mac/_type, plus a category-alias (e.g. cpe_router_serial) only when
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

    variables: Dict[str, Any] = {
        "client_service_id": str(client_service.id),
    }
    plan = client_service.service_plan
    if plan is not None:
        variables["service_plan_id"] = str(plan.id)
        if plan.download_mbps is not None:
            variables["download_mbps"] = plan.download_mbps
        if plan.upload_mbps is not None:
            variables["upload_mbps"] = plan.upload_mbps
        if plan.provisioning_params:
            variables.update(plan.provisioning_params)

    # Category alias only when unique within the chain (per doc 18a §5).
    category_counts: Dict[str, int] = {}
    for ri in resolved_items:
        if ri.category:
            key = ri.category.lower()
            category_counts[key] = category_counts.get(key, 0) + 1

    for ri in resolved_items:
        i = ri.position + 1  # 1-based, per doc 18a §5
        variables[f"device{i}_item_id"] = str(ri.inventory_item_id)
        variables[f"device{i}_serial"] = ri.serial_number or ""
        variables[f"device{i}_mac"] = ri.mac_address or ""
        variables[f"device{i}_type"] = ri.device_type_name
        if ri.category:
            key = ri.category.lower()
            if category_counts.get(key) == 1:
                variables[f"{key}_serial"] = ri.serial_number or ""
                variables[f"{key}_mac"] = ri.mac_address or ""

    return ResolvedProvisioning(
        playbook_id=playbook.id,
        variables=variables,
        resolved_items=resolved_items,
    )
