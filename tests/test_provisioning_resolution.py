"""Unit tests for the pure-Python helpers in the Cycle 3 E2 provisioning
resolution module (moved from backend-erp services/provisioning_resolution.py,
doc 20a workflow-provisioning §0). `resolve_provisioning` itself needs a live
SQLAlchemy Session (DB-backed candidate queries) and is covered by
backend-erp's test suite (doc 20a D-E1.9); these tests exercise the two
helpers that operate on plain Python objects: get_topology_playbook (purpose
lookup) and _playbook_references_device_variables (amendment 4).

Cycle 7 (doc 25 §3): the pinned-position paths of resolve_provisioning are
covered here too, via a minimal fake Session (query -> prepared candidate
list, get -> item-by-id) — the pinned logic itself is pure Python over model
attributes, so no live DB is needed (the DB-backed candidate SQL stays
covered by backend-erp's suite)."""
import uuid
from types import SimpleNamespace

import pytest

from database_utils.models.isp import InventoryItemStatus
from database_utils.utils.provisioning_resolution import (
    ResolutionError,
    get_topology_playbook,
    resolve_provisioning,
    _playbook_references_device_variables,
)


def _topology(entries):
    return SimpleNamespace(playbooks=[SimpleNamespace(purpose=p, playbook=pb) for p, pb in entries])


# --- get_topology_playbook ---

def test_get_topology_playbook_finds_matching_purpose():
    activation_pb = object()
    topology = _topology([("ACTIVATION", activation_pb), ("SUSPENSION", object())])
    entry = get_topology_playbook(topology, "ACTIVATION")
    assert entry.playbook is activation_pb


def test_get_topology_playbook_returns_none_when_purpose_missing():
    topology = _topology([("ACTIVATION", object())])
    assert get_topology_playbook(topology, "DEPROVISION") is None


def test_get_topology_playbook_empty_topology():
    topology = _topology([])
    assert get_topology_playbook(topology, "ACTIVATION") is None


# --- _playbook_references_device_variables (amendment 4) ---

def _playbook(definition):
    return SimpleNamespace(definition=definition)


def test_device_free_playbook_is_not_fatal():
    """A suspend/deprovision playbook that never templates a device variable
    (e.g. only uses client_service_id/service_plan_id) is 'device-free' —
    resolution should not require the device chain for it."""
    definition = {
        "steps": [{
            "name": "flip-vlan",
            "driver": "http",
            "request": {"method": "POST", "path": "/api", "body": "{{service.id}}"},
        }]
    }
    assert _playbook_references_device_variables(_playbook(definition)) is False


def test_positional_device_variable_reference_is_fatal():
    definition = {
        "steps": [{"name": "s", "driver": "simulator", "template": "serial={{edge_devices[0].serial}}"}]
    }
    assert _playbook_references_device_variables(_playbook(definition)) is True


def test_chain_position_reference_is_fatal():
    """The hidden absolute-position namespace is device-derived too — it is
    what `target_position` step targeting compiles to."""
    definition = {
        "steps": [{"name": "s", "driver": "simulator", "template": "serial={{chain[1].serial}}"}]
    }
    assert _playbook_references_device_variables(_playbook(definition)) is True


def test_retired_category_alias_is_not_device_referencing():
    """Unique-category aliases (cpe_router_serial, onu_mac, ...) are GONE
    (doc 33). The name is now just an unresolvable token, not a device
    reference — the executor's unresolved-token guard is what catches it."""
    definition = {
        "steps": [{"name": "s", "driver": "simulator", "template": "serial={{cpe_router_serial}}"}]
    }
    assert _playbook_references_device_variables(_playbook(definition)) is False


def test_unserializable_definition_fails_safe_as_device_referencing():
    class Unserializable:
        pass

    assert _playbook_references_device_variables(_playbook(Unserializable())) is True


def test_category_tier_variable_reference_is_fatal():
    """Cycle 7 (doc 25 §3): a device's category_tier is device-derived — a
    playbook templating it needs the chain resolved."""
    definition = {
        "steps": [{"name": "s", "driver": "ssh", "template": "tier={{core_devices[0].category_tier}}"}]
    }
    assert _playbook_references_device_variables(_playbook(definition)) is True


# --- resolve_provisioning pinned paths (Cycle 7, doc 25 §3) ---

class _FakeQuery:
    """Stands in for db.query(InventoryItem).filter(...).all() — filters are
    real SQLAlchemy expressions but never evaluated; the prepared candidate
    list IS the post-filter result (candidate SQL semantics are covered by
    backend-erp's DB-backed suite)."""

    def __init__(self, items):
        self._items = items

    def filter(self, *args, **kwargs):
        return self

    def all(self):
        return list(self._items)


class _FakeDb:
    def __init__(self, candidates=(), items_by_id=None):
        self._candidates = list(candidates)
        self._items_by_id = items_by_id or {}

    def query(self, model):
        return _FakeQuery(self._candidates)

    def get(self, model, pk):
        return self._items_by_id.get(pk)


def _item(company_id, device_type_id, status=InventoryItemStatus.INSTALLED,
          serial="SN-1", mac="AA:BB", client_service_id=None):
    return SimpleNamespace(
        id=uuid.uuid4(), company_id=company_id, device_type_id=device_type_id,
        status=status, serial_number=serial, mac_address=mac,
        client_service_id=client_service_id,
    )


def _device_type(name, category_key, tier):
    return SimpleNamespace(
        name=name, category=category_key,
        category_ref=SimpleNamespace(key=category_key, tier=tier),
    )


def _tdt(position, device_type, inventory_item_id=None):
    return SimpleNamespace(
        position=position, device_type_id=uuid.uuid4(),
        device_type=device_type, inventory_item_id=inventory_item_id,
    )


def _service(topology, company_id=None):
    return SimpleNamespace(
        id=uuid.uuid4(), company_id=company_id or uuid.uuid4(),
        client_id=uuid.uuid4(), topology=topology, service_plan=None,
    )


def _activation_topology(chain):
    playbook = SimpleNamespace(
        id=uuid.uuid4(), is_active=True,
        definition={"steps": [{"driver": "ssh", "template": "sn={{device1_serial}}"}]},
    )
    return SimpleNamespace(
        name="FTTH", is_active=True,
        playbooks=[SimpleNamespace(purpose="ACTIVATION", playbook=playbook)],
        device_types=chain,
    )


def test_pinned_position_resolves_without_client_matching():
    """A pinned CORE position resolves to the pinned shared item even though
    the client/service candidate pool is EMPTY — pinned devices are exempt
    from assignment matching (doc 25 §3 step 1)."""
    olt_type = _device_type("MA5800", "OLT", "CORE")
    tdt = _tdt(0, olt_type)
    topology = _activation_topology([tdt])
    svc = _service(topology)
    pinned = _item(svc.company_id, tdt.device_type_id, serial="OLT-001")
    tdt.inventory_item_id = pinned.id
    db = _FakeDb(candidates=[], items_by_id={pinned.id: pinned})

    resolved = resolve_provisioning(db, svc)

    assert resolved.resolved_items[0].pinned is True
    # Tier-indexed (what the operator sees) and absolute-position (what step
    # targeting compiles to) both address the same device — doc 33.
    assert resolved.variables["core_devices[0].item_id"] == str(pinned.id)
    assert resolved.variables["chain[1].item_id"] == str(pinned.id)
    assert resolved.variables["core_devices[0].serial"] == "OLT-001"
    assert resolved.variables["core_devices[0].category_tier"] == "CORE"
    assert "olt_serial" not in resolved.variables  # unique-category alias retired


def test_pinned_item_wrong_status_is_pinned_device_unavailable():
    olt_type = _device_type("MA5800", "OLT", "CORE")
    tdt = _tdt(0, olt_type)
    topology = _activation_topology([tdt])
    svc = _service(topology)
    pinned = _item(svc.company_id, tdt.device_type_id, status=InventoryItemStatus.RETIRED)
    tdt.inventory_item_id = pinned.id
    db = _FakeDb(candidates=[], items_by_id={pinned.id: pinned})

    with pytest.raises(ResolutionError) as exc:
        resolve_provisioning(db, svc)
    assert exc.value.code == "RESOLUTION_FAILED"
    assert exc.value.errors[0]["code"] == "PINNED_DEVICE_UNAVAILABLE"
    assert exc.value.errors[0]["inventory_item_id"] == str(pinned.id)


def test_pinned_item_foreign_company_is_pinned_device_unavailable():
    olt_type = _device_type("MA5800", "OLT", "CORE")
    tdt = _tdt(0, olt_type)
    topology = _activation_topology([tdt])
    svc = _service(topology)
    foreign = _item(uuid.uuid4(), tdt.device_type_id)  # other tenant's item
    tdt.inventory_item_id = foreign.id
    db = _FakeDb(candidates=[], items_by_id={foreign.id: foreign})

    with pytest.raises(ResolutionError) as exc:
        resolve_provisioning(db, svc)
    assert exc.value.errors[0]["code"] == "PINNED_DEVICE_UNAVAILABLE"


def test_pinned_item_deleted_is_pinned_device_unavailable():
    olt_type = _device_type("MA5800", "OLT", "CORE")
    tdt = _tdt(0, olt_type, inventory_item_id=uuid.uuid4())  # dangling pin
    topology = _activation_topology([tdt])
    svc = _service(topology)
    db = _FakeDb(candidates=[], items_by_id={})

    with pytest.raises(ResolutionError) as exc:
        resolve_provisioning(db, svc)
    assert exc.value.errors[0]["code"] == "PINNED_DEVICE_UNAVAILABLE"


def test_pinned_core_plus_client_matched_edge_mix():
    """Founder chain (doc 25 §1): position 0 = pinned shared OLT (CORE),
    position 1 = subscriber ONU resolved from the client's assigned inventory
    — both resolve, each with its tier variable."""
    olt_type = _device_type("MA5800", "OLT", "CORE")
    onu_type = _device_type("F660", "ONU", "EDGE")
    tdt_olt = _tdt(0, olt_type)
    tdt_onu = _tdt(1, onu_type)
    topology = _activation_topology([tdt_olt, tdt_onu])
    svc = _service(topology)
    pinned = _item(svc.company_id, tdt_olt.device_type_id, serial="OLT-001")
    tdt_olt.inventory_item_id = pinned.id
    onu = _item(svc.company_id, tdt_onu.device_type_id, serial="ONU-042",
                client_service_id=svc.id)
    db = _FakeDb(candidates=[onu], items_by_id={pinned.id: pinned})

    resolved = resolve_provisioning(db, svc)

    assert [ri.pinned for ri in resolved.resolved_items] == [True, False]
    # Indexes are 0-based WITHIN a tier, so the CORE OLT and the EDGE ONT are
    # both [0] — that is the whole point of the tier namespaces (doc 33).
    assert resolved.variables["core_devices[0].serial"] == "OLT-001"
    assert resolved.variables["core_devices[0].category_tier"] == "CORE"
    assert resolved.variables["edge_devices[0].serial"] == "ONU-042"
    assert resolved.variables["edge_devices[0].category_tier"] == "EDGE"
    # Absolute chain positions stay 1-based and distinct.
    assert resolved.variables["chain[1].serial"] == "OLT-001"
    assert resolved.variables["chain[2].serial"] == "ONU-042"
    # The unique-category alias is retired, not renamed.
    assert "onu_serial" not in resolved.variables


# --- client custom attributes as variables (doc 33 follow-up) ---

def _custom_value(key, value, field_type="TEXT"):
    return SimpleNamespace(
        value=value,
        field_definition=SimpleNamespace(field_key=key, field_type=field_type),
    )


def _client(name="Ada Lovelace", custom=None):
    return SimpleNamespace(
        id=uuid.uuid4(), name=name, email="ada@example.com",
        phone="+502 5555 0100", address="1 Analytical Way",
        custom_field_values=custom or [],
    )


def _service_with_client(topology, client):
    svc = _service(topology)
    svc.client = client
    return svc


def _resolve_vars(custom):
    """Resolve a minimal single-position service and return its variables."""
    onu_type = _device_type("HG8245", "ONU", "EDGE")
    tdt = _tdt(0, onu_type)
    topology = _activation_topology([tdt])
    svc = _service_with_client(topology, _client(custom=custom))
    onu = _item(svc.company_id, tdt.device_type_id, serial="ONU-1",
                client_service_id=svc.id)
    db = _FakeDb(candidates=[onu], items_by_id={})
    return resolve_provisioning(db, svc).variables


def test_client_custom_attributes_are_emitted():
    """A tenant's own client attributes reach playbooks under client.*, the
    same way a service plan's provisioning parameters reach service_plan.*."""
    variables = _resolve_vars([_custom_value("ip_address", "10.10.9.88")])

    assert variables["client.ip_address"] == "10.10.9.88"
    # Built-ins still present alongside them.
    assert variables["client.name"] == "Ada Lovelace"


def test_number_and_boolean_custom_fields_get_their_natural_type():
    """Values are stored as strings; a template should render 100, not 100.0,
    and a boolean should not read as the literal string 'true'."""
    variables = _resolve_vars([
        _custom_value("vlan", "100", "NUMBER"),
        _custom_value("ratio", "1.5", "NUMBER"),
        _custom_value("is_vip", "true", "BOOLEAN"),
        _custom_value("nope", "no", "BOOLEAN"),
    ])

    assert variables["client.vlan"] == 100
    assert variables["client.ratio"] == 1.5
    assert variables["client.is_vip"] is True
    assert variables["client.nope"] is False


def test_unparseable_number_falls_back_to_the_raw_string():
    variables = _resolve_vars([_custom_value("vlan", "not-a-number", "NUMBER")])
    assert variables["client.vlan"] == "not-a-number"


def test_custom_field_cannot_shadow_a_builtin_client_field():
    """A custom field keyed `name` must not replace the subscriber's actual
    name in a template that already reads {{client.name}}."""
    variables = _resolve_vars([_custom_value("name", "SHADOWED")])
    assert variables["client.name"] == "Ada Lovelace"


def test_key_the_token_grammar_cannot_express_is_skipped():
    """field_key permits a leading digit, which the renderer's grammar does
    not — emitting it would create a token nobody can reference."""
    variables = _resolve_vars([_custom_value("5g_profile", "x")])
    assert "client.5g_profile" not in variables


def test_null_custom_value_renders_as_empty_string():
    variables = _resolve_vars([_custom_value("note", None)])
    assert variables["client.note"] == ""


def test_missing_relationship_does_not_crash_resolution():
    """Resolution runs against detached/partial objects too."""
    onu_type = _device_type("HG8245", "ONU", "EDGE")
    tdt = _tdt(0, onu_type)
    topology = _activation_topology([tdt])
    svc = _service_with_client(topology, SimpleNamespace(
        id=uuid.uuid4(), name="No Rels", email=None, phone=None, address=None))
    onu = _item(svc.company_id, tdt.device_type_id, serial="ONU-1",
                client_service_id=svc.id)

    variables = resolve_provisioning(_FakeDb(candidates=[onu], items_by_id={}), svc).variables

    assert variables["client.name"] == "No Rels"
