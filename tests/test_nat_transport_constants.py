"""NAT transport (spec §8) guardrails. The CHECK-fragment strings shared
between database_utils/models/isp.py and the hand-written nat1 migration are
duplicated on purpose (the nc1a/nc2a precedent — revisions are immutable,
models are not, so neither can import the other). These tests pin the two
copies byte-identical."""
import importlib.util
import os

from database_utils.models import isp

_MIGRATION_PATH = os.path.join(
    os.path.dirname(__file__), "..", "alembic", "versions", "nat1_gateway_transport.py"
)


def _load_nat1():
    spec = importlib.util.spec_from_file_location("nat1_gateway_transport", _MIGRATION_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_network_access_modes_constant():
    assert isp.NETWORK_ACCESS_MODES == (
        "direct", "vpn", "tunnel", "nat_zt", "nat_public",
    )


def test_nat_modes_constant_is_a_subset():
    assert isp.NAT_MODES == ("nat_zt", "nat_public")
    for value in isp.NAT_MODES:
        assert value in isp.NETWORK_ACCESS_MODES


def test_check_fragment_covers_every_mode():
    for value in isp.NETWORK_ACCESS_MODES:
        assert f"'{value}'" in isp._NETWORK_ACCESS_MODE_CHECK


def test_migration_fragments_match_model_fragments():
    nat1 = _load_nat1()
    assert nat1._NETWORK_ACCESS_MODE_CHECK == isp._NETWORK_ACCESS_MODE_CHECK
    assert nat1._NAT_PORT_CHECK == isp._NAT_PORT_CHECK
    assert nat1._MGMT_PORT_CHECK == isp._MGMT_PORT_CHECK


def test_migration_chain_position():
    nat1 = _load_nat1()
    assert nat1.revision == "nat1_gateway_transport"
    assert nat1.down_revision == "ng2_topology_drop"
    assert len(nat1.revision) <= 32
