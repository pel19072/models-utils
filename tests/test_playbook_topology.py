"""Cycle 8 (doc 26 §2) guardrails: playbooks are topology-owned. The old
vendor/category targeting is gone from the schemas; PlaybookOut carries
topology_id; PlaybookStep gains a 1-based target_position. Plus a sanity check
on the hand-written c8a_playbook_topology migration (chain position + the
constant naming the dropped columns), mirroring test_core_config_constants."""
import importlib.util
import os

import pytest
from pydantic import ValidationError

from database_utils.schemas.playbook import (
    PlaybookBase,
    PlaybookOut,
    PlaybookStep,
    PlaybookUpdate,
)

_MIGRATION_PATH = os.path.join(
    os.path.dirname(__file__), "..", "alembic", "versions", "c8a_playbook_topology.py"
)


def _load_c8a():
    spec = importlib.util.spec_from_file_location("c8a_playbook_topology", _MIGRATION_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# --- schema shape (doc 26 §2) ---

def test_playbook_schemas_dropped_targeting_fields():
    for model in (PlaybookBase, PlaybookOut, PlaybookUpdate):
        assert "target_vendor" not in model.model_fields
        assert "target_category" not in model.model_fields
        assert "target_category_id" not in model.model_fields


def test_playbook_out_has_topology_id():
    assert "topology_id" in PlaybookOut.model_fields
    # NULL = system/global playbook; must be optional.
    assert PlaybookOut.model_fields["topology_id"].is_required() is False


# --- PlaybookStep.target_position validation (doc 26 §2) ---

def _step(**overrides):
    base = {"name": "configure", "driver": "simulator", "template": "cmd {{x}}"}
    base.update(overrides)
    return PlaybookStep(**base)


def test_step_target_position_defaults_none():
    assert _step().target_position is None


def test_step_target_position_accepts_positive():
    assert _step(target_position=1).target_position == 1
    assert _step(target_position=3).target_position == 3


def test_step_target_position_rejects_zero_and_negative():
    for bad in (0, -1):
        with pytest.raises(ValidationError):
            _step(target_position=bad)


def test_step_target_item_id_still_accepted():
    # power users / system playbooks keep the raw target_item_id surface.
    assert _step(target_item_id="{{device1_item_id}}").target_item_id == "{{device1_item_id}}"


# --- migration sanity (hand-written c8a) ---

def test_c8a_chain_position():
    c8a = _load_c8a()
    assert c8a.revision == "c8a_playbook_topology"
    assert c8a.down_revision == "nc2a_core_config"


def test_c8a_dropped_columns_constant():
    c8a = _load_c8a()
    assert c8a._DROPPED_COLUMNS == ("target_vendor", "target_category_id")
