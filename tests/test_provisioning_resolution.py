"""Unit tests for the pure-Python helpers in the Cycle 3 E2 provisioning
resolution module (moved from backend-erp services/provisioning_resolution.py,
doc 20a workflow-provisioning §0). `resolve_provisioning` itself needs a live
SQLAlchemy Session (DB-backed candidate queries) and is covered by
backend-erp's test suite (doc 20a D-E1.9); these tests exercise the two
helpers that operate on plain Python objects: get_topology_playbook (purpose
lookup) and _playbook_references_device_variables (amendment 4)."""
from types import SimpleNamespace

from database_utils.utils.provisioning_resolution import (
    get_topology_playbook,
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
            "request": {"method": "POST", "path": "/api", "body": "{{client_service_id}}"},
        }]
    }
    assert _playbook_references_device_variables(_playbook(definition)) is False


def test_positional_device_variable_reference_is_fatal():
    definition = {
        "steps": [{"name": "s", "driver": "simulator", "template": "serial={{device1_serial}}"}]
    }
    assert _playbook_references_device_variables(_playbook(definition)) is True


def test_category_alias_reference_is_fatal():
    definition = {
        "steps": [{"name": "s", "driver": "simulator", "template": "serial={{cpe_router_serial}}"}]
    }
    assert _playbook_references_device_variables(_playbook(definition)) is True


def test_unserializable_definition_fails_safe_as_device_referencing():
    class Unserializable:
        pass

    assert _playbook_references_device_variables(_playbook(Unserializable())) is True
