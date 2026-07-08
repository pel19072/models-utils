"""Unit tests for Cycle 3 E1 topology purpose handling (doc 20a D-E1.9).

Covers: normalize_purpose (strip/upper/space+hyphen->underscore/regex
rejection), _validate_playbooks_map (duplicate-after-normalization rejection,
ACTIVATION requirement), exported constants, and the TopologyUpdate.playbooks
None-guard (verifier fix: an explicit `"playbooks": null` body must not 500).
"""
from uuid import uuid4

import pytest
from pydantic import ValidationError

from database_utils.models.isp import CANONICAL_TOPOLOGY_PURPOSES, PURPOSE_ACTIVATION
from database_utils.schemas.topology import (
    TopologyCreate,
    TopologyUpdate,
    _validate_playbooks_map,
    normalize_purpose,
)


# --- normalize_purpose ---

def test_normalize_purpose_strips_and_uppercases():
    assert normalize_purpose(" activation ") == "ACTIVATION"


def test_normalize_purpose_spaces_and_hyphens_become_underscores():
    assert normalize_purpose("firmware upgrade") == "FIRMWARE_UPGRADE"
    assert normalize_purpose("firmware-upgrade") == "FIRMWARE_UPGRADE"


def test_normalize_purpose_rejects_leading_digit():
    with pytest.raises(ValueError):
        normalize_purpose("1BAD")


def test_normalize_purpose_rejects_too_long():
    with pytest.raises(ValueError):
        normalize_purpose("A" * 51)


def test_normalize_purpose_accepts_max_length():
    assert normalize_purpose("A" * 50) == "A" * 50


def test_normalize_purpose_rejects_non_ascii():
    with pytest.raises(ValueError):
        normalize_purpose("café")


# --- _validate_playbooks_map ---

def test_validate_playbooks_map_requires_activation():
    with pytest.raises(ValueError, match="ACTIVATION"):
        _validate_playbooks_map({"SUSPENSION": uuid4()})


def test_validate_playbooks_map_rejects_duplicate_after_normalization():
    pid = uuid4()
    with pytest.raises(ValueError, match="duplicate"):
        _validate_playbooks_map({"ACTIVATION": pid, "activation": uuid4()})


def test_validate_playbooks_map_normalizes_keys():
    pid = uuid4()
    result = _validate_playbooks_map({"activation": pid})
    assert result == {"ACTIVATION": pid}


def test_validate_playbooks_map_accepts_custom_purpose_alongside_activation():
    result = _validate_playbooks_map({"ACTIVATION": uuid4(), "firmware-upgrade": uuid4()})
    assert set(result.keys()) == {"ACTIVATION", "FIRMWARE_UPGRADE"}


# --- constants ---

def test_canonical_purposes_exported():
    assert CANONICAL_TOPOLOGY_PURPOSES == ("ACTIVATION", "SUSPENSION", "REACTIVATION", "DEPROVISION")
    assert PURPOSE_ACTIVATION == "ACTIVATION"


# --- TopologyCreate / TopologyUpdate schema wiring ---

def test_topology_create_requires_activation():
    with pytest.raises(ValidationError):
        TopologyCreate(
            name="FTTH Basic",
            device_type_ids=[uuid4()],
            playbooks={"SUSPENSION": uuid4()},
        )


def test_topology_create_accepts_activation():
    topo = TopologyCreate(
        name="FTTH Basic",
        device_type_ids=[uuid4()],
        playbooks={"activation": uuid4()},
    )
    assert list(topo.playbooks.keys()) == ["ACTIVATION"]


def test_topology_update_playbooks_none_is_a_noop_not_a_500():
    """Verifier fix (doc 20a appendix D-E1.3 issue): Pydantic field
    validators DO run on an explicit `"playbooks": null` body — without the
    None-guard, _validate_playbooks_map's v.items() raises AttributeError,
    which Pydantic would surface as an internal error instead of a clean
    validation outcome."""
    update = TopologyUpdate.model_validate({"playbooks": None})
    assert update.playbooks is None


def test_topology_update_playbooks_omitted_is_also_a_noop():
    update = TopologyUpdate(name="Renamed")
    assert update.playbooks is None


def test_topology_update_playbooks_present_still_requires_activation():
    with pytest.raises(ValidationError):
        TopologyUpdate(playbooks={"SUSPENSION": uuid4()})
