"""Provisioning resolution against the traversed network path (doc 35 §3.2).

Built on a real in-memory SQLite graph rather than fakes: the resolver now runs
recursive CTEs and two binding lookups, and a hand-rolled fake DB would be
asserting the shape of the mock rather than the behaviour of the query.

The seeded plant is one company's chain, root-first:

    CORE-1 (router) -> OLT-1 (olt) -> SPL-1 (splitter) -> SPL-2 (splitter)
                                                       -> ONT-1 (onu)

Both splitters are passive. ACTIVATION and SUSPENSION playbooks are bound to
the router, olt and onu device TYPES.
"""

import uuid
from types import SimpleNamespace

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import Session

from database_utils.database import Base
from database_utils.models.isp import (
    ClientService,
    DeviceCategory,
    DeviceType,
    DeviceTypePlaybook,
    InventoryItem,
    InventoryItemPlaybook,
    Playbook,
    PURPOSE_ACTIVATION,
    ServicePlan,
)
from database_utils.utils.provisioning_resolution import (
    DEVICE_ATTRIBUTES,
    ResolutionError,
    _DEVICE_VARIABLE_PATTERN,
    build_device_frame,
    iter_client_custom_fields,
    resolve_playbook_for,
    resolve_provisioning,
)

CO_A = uuid.uuid4()
CO_B = uuid.uuid4()

# A definition that reads a device variable, so amendment-4 fatality applies.
_DEF = {"steps": [{"name": "s", "driver": "simulator",
                   "template": "sn {{ cpe.serial }}"}]}
# A definition that reads no device variable at all.
_DEF_DEVICE_FREE = {"steps": [{"name": "s", "driver": "simulator",
                               "template": "noop"}]}


@pytest.fixture()
def db():
    engine = sa.create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


class Plant:
    """The seeded graph, exposed as attributes the tests can poke at."""

    def __init__(self, db, company_id=CO_A):
        self.db = db
        self.company_id = company_id
        self.categories = {}
        self.types = {}

        for key, tier, passive in (
            ("ROUTER", "CORE", False),
            ("OLT", "CORE", False),
            ("SPLITTER", None, True),
            ("ONU", "EDGE", False),
        ):
            cat = DeviceCategory(id=uuid.uuid4(), key=key, name=key.title(),
                                 tier=tier, is_passive=passive)
            db.add(cat)
            self.categories[key] = cat
        db.flush()

        for key in self.categories:
            dt = DeviceType(id=uuid.uuid4(), company_id=company_id,
                            name=f"{key} model", category_id=self.categories[key].id)
            db.add(dt)
            self.types[key] = dt
        db.flush()

        self.core = self._item("CORE-1", "ROUTER", None)
        self.olt = self._item("OLT-1", "OLT", self.core)
        self.spl1 = self._item("SPL-1", "SPLITTER", self.olt)
        self.spl2 = self._item("SPL-2", "SPLITTER", self.spl1)
        self.cpe = self._item("ONT-1", "ONU", self.spl2)

        self.plan = ServicePlan(id=uuid.uuid4(), company_id=company_id,
                                name="Fibra 100", download_mbps=100, upload_mbps=20)
        db.add(self.plan)
        db.flush()

        self.service = ClientService(
            id=uuid.uuid4(), company_id=company_id, client_id=uuid.uuid4(),
            service_plan_id=self.plan.id, cpe_item_id=self.cpe.id,
        )
        db.add(self.service)
        db.flush()
        self.cpe.client_service_id = self.service.id
        db.flush()

        self.playbooks = {}
        for key in ("ROUTER", "OLT", "ONU"):
            for purpose in (PURPOSE_ACTIVATION, "SUSPENSION"):
                self.bind_type(self.types[key], purpose,
                               self._playbook(f"{key.lower()}-{purpose.lower()}"))

    def _item(self, serial, category_key, parent):
        item = InventoryItem(
            id=uuid.uuid4(), company_id=self.company_id,
            device_type_id=self.types[category_key].id, serial_number=serial,
            mac_address=f"AA:BB:{serial}", mgmt_host=f"10.0.0.{len(serial)}",
            network_attached=True,
            parent_id=parent.id if parent is not None else None,
        )
        self.db.add(item)
        self.db.flush()
        return item

    def _playbook(self, name, definition=None):
        pb = Playbook(id=uuid.uuid4(), company_id=self.company_id, name=name,
                      is_active=True, definition=definition or _DEF)
        self.db.add(pb)
        self.db.flush()
        self.playbooks[name] = pb
        return pb

    def bind_type(self, device_type, purpose, playbook):
        self.db.add(DeviceTypePlaybook(
            id=uuid.uuid4(), company_id=self.company_id,
            device_type_id=device_type.id, purpose=purpose, playbook_id=playbook.id,
        ))
        self.db.flush()

    def bind_node(self, item, purpose, playbook):
        self.db.add(InventoryItemPlaybook(
            id=uuid.uuid4(), company_id=self.company_id,
            inventory_item_id=item.id, purpose=purpose, playbook_id=playbook.id,
        ))
        self.db.flush()

    def unbind_type(self, device_type, purpose):
        self.db.execute(sa.delete(DeviceTypePlaybook.__table__).where(
            DeviceTypePlaybook.__table__.c.device_type_id == device_type.id,
            DeviceTypePlaybook.__table__.c.purpose == purpose,
        ))
        self.db.flush()


@pytest.fixture()
def plant(db):
    return Plant(db)


# --------------------------------------------------------------- path shape

def test_path_is_leaf_to_root(db, plant):
    res = resolve_provisioning(db, plant.service, PURPOSE_ACTIVATION)
    assert [n.serial_number for n in res.path] == [
        "ONT-1", "SPL-2", "SPL-1", "OLT-1", "CORE-1"]


def test_passives_are_on_the_path_but_are_not_steps(db, plant):
    res = resolve_provisioning(db, plant.service, PURPOSE_ACTIVATION)
    assert [n.category_key for n in res.steps] == ["ONU", "OLT", "ROUTER"]
    assert all(n.is_passive for n in res.path if n.category_key == "SPLITTER")
    assert not any(n.is_passive for n in res.steps)


def test_position_counts_hops_from_the_cpe(db, plant):
    res = resolve_provisioning(db, plant.service)
    assert [n.position for n in res.path] == [0, 1, 2, 3, 4]


# ------------------------------------------------------- playbook resolution

def test_device_type_default_is_used_when_there_is_no_override(db, plant):
    res = resolve_provisioning(db, plant.service)
    olt = next(n for n in res.steps if n.category_key == "OLT")
    assert olt.playbook_source == "device_type"


def test_node_override_beats_the_device_type_default(db, plant):
    special = plant._playbook("olt-special")
    plant.bind_node(plant.olt, PURPOSE_ACTIVATION, special)
    res = resolve_provisioning(db, plant.service)
    olt = next(n for n in res.steps if n.category_key == "OLT")
    assert olt.playbook_id == special.id
    assert olt.playbook_source == "node"


def test_resolve_playbook_for_returns_none_when_nothing_is_bound(db, plant):
    plant.unbind_type(plant.types["OLT"], PURPOSE_ACTIVATION)
    assert resolve_playbook_for(db, plant.olt, PURPOSE_ACTIVATION) == (None, None)


def test_an_active_node_with_no_playbook_is_fatal_for_activation(db, plant):
    plant.unbind_type(plant.types["OLT"], PURPOSE_ACTIVATION)
    with pytest.raises(ResolutionError) as exc:
        resolve_provisioning(db, plant.service, PURPOSE_ACTIVATION)
    assert exc.value.code == "RESOLUTION_FAILED"
    assert exc.value.errors[0]["code"] == "PLAYBOOK_NOT_BOUND"
    assert exc.value.errors[0]["category"] == "olt"


def test_a_missing_playbook_is_not_fatal_for_a_device_free_suspension(db, plant):
    """A suspend that never templates a device variable must not be blocked by
    an OLT with no suspend playbook."""
    plant.unbind_type(plant.types["OLT"], "SUSPENSION")
    for name in ("router-suspension", "onu-suspension"):
        plant.playbooks[name].definition = _DEF_DEVICE_FREE
    db.flush()
    res = resolve_provisioning(db, plant.service, "SUSPENSION")
    assert [n.category_key for n in res.steps] == ["ONU", "ROUTER"]


def test_a_missing_playbook_is_fatal_for_a_device_reading_suspension(db, plant):
    plant.unbind_type(plant.types["OLT"], "SUSPENSION")
    with pytest.raises(ResolutionError) as exc:
        resolve_provisioning(db, plant.service, "SUSPENSION")
    assert exc.value.code == "RESOLUTION_FAILED"


def test_an_inactive_playbook_is_never_silently_skipped(db, plant):
    plant.playbooks["olt-activation"].is_active = False
    db.flush()
    with pytest.raises(ResolutionError) as exc:
        resolve_provisioning(db, plant.service)
    assert exc.value.code == "PLAYBOOK_INACTIVE"


def test_a_playbook_owned_by_another_company_is_refused(db, plant):
    plant.playbooks["olt-activation"].company_id = CO_B
    db.flush()
    with pytest.raises(ResolutionError) as exc:
        resolve_provisioning(db, plant.service)
    assert exc.value.code == "PLAYBOOK_INACTIVE"


# ------------------------------------------------------------- preconditions

def test_unset_cpe_is_reported(db, plant):
    plant.service.cpe_item_id = None
    db.flush()
    with pytest.raises(ResolutionError) as exc:
        resolve_provisioning(db, plant.service)
    assert exc.value.code == "CPE_NOT_SET"


def test_detached_cpe_is_reported(db, plant):
    plant.cpe.parent_id = None
    plant.cpe.network_attached = False
    db.flush()
    with pytest.raises(ResolutionError) as exc:
        resolve_provisioning(db, plant.service)
    assert exc.value.code == "CPE_NOT_ATTACHED"


def test_a_cpe_belonging_to_another_company_resolves_to_nothing(db, plant):
    plant.service.company_id = CO_B
    db.flush()
    with pytest.raises(ResolutionError) as exc:
        resolve_provisioning(db, plant.service)
    assert exc.value.code == "CPE_NOT_ATTACHED"


# ----------------------------------------------------------------- variables

def test_shared_variables_expose_the_path_by_category(db, plant):
    v = resolve_provisioning(db, plant.service).shared_variables
    assert v["cpe.serial"] == "ONT-1"
    assert v["path.olt.serial"] == "OLT-1"
    assert v["path.router.serial"] == "CORE-1"
    assert v["path.splitter.serial"] == "SPL-2"
    assert v["cpe.depth"] == 0
    assert v["path.olt.depth"] == 3


def test_path_category_picks_the_node_nearest_the_cpe(db, plant):
    """Two OLTs stacked: the one closest to the subscriber wins, with no
    tie-break needed because the path is already ordered leaf -> root."""
    second = plant._item("OLT-2", "OLT", plant.core)
    plant.olt.parent_id = second.id
    db.flush()
    v = resolve_provisioning(db, plant.service).shared_variables
    assert v["path.olt.serial"] == "OLT-1"


def test_device_frame_is_per_node(db, plant):
    res = resolve_provisioning(db, plant.service)
    olt = next(n for n in res.steps if n.category_key == "OLT")
    assert res.device_variables[olt.item_id]["device.serial"] == "OLT-1"
    assert res.device_variables[plant.cpe.id]["device.serial"] == "ONT-1"


def test_passive_nodes_get_no_device_frame(db, plant):
    res = resolve_provisioning(db, plant.service)
    assert plant.spl1.id not in res.device_variables


def test_no_positional_namespace_survives(db, plant):
    v = resolve_provisioning(db, plant.service).shared_variables
    assert not any(
        k.startswith(("chain[", "edge_devices[", "core_devices[")) for k in v)
    assert not any(k.endswith(".position") for k in v)


def test_plan_fields_are_unchanged(db, plant):
    v = resolve_provisioning(db, plant.service).shared_variables
    assert v["service_plan.name"] == "Fibra 100"
    assert v["service_plan.download_mbps"] == 100
    assert v["service.id"] == str(plant.service.id)


def test_build_device_frame_emits_every_declared_attribute(db, plant):
    node = resolve_provisioning(db, plant.service).path[0]
    frame = build_device_frame(node, "cpe")
    assert set(frame) == {f"cpe.{a}" for a in DEVICE_ATTRIBUTES}


def test_device_variable_pattern_matches_the_new_namespaces():
    """This pattern FAILS OPEN. A namespace missing from it silently downgrades
    a fatal resolution error into a half-configured customer."""
    for token in ("{{device.serial}}", "{{cpe.serial}}", "{{path.olt.mgmt_host}}",
                  "{{ cpe.serial | upper }}", "{{path.cpe_router.mac}}"):
        assert _DEVICE_VARIABLE_PATTERN.search(token), token
    for token in ("{{chain[1].serial}}", "{{edge_devices[0].serial}}",
                  "{{core_devices[0].serial}}"):
        assert not _DEVICE_VARIABLE_PATTERN.search(token), token


# ------------------------------------------- client custom fields (unchanged)

def _detached_service(plant, client):
    """A ClientService stand-in.

    resolve_provisioning reads its inputs with getattr precisely so it survives
    detached and partial objects — the workflow engine hands it exactly this
    shape. Using one here also lets a test vary `client` freely, which the ORM
    relationship would refuse.
    """
    return SimpleNamespace(
        id=plant.service.id,
        company_id=plant.company_id,
        cpe_item_id=plant.cpe.id,
        client=client,
        service_plan=plant.plan,
        provisioning_params=None,
    )


def test_client_custom_fields_are_namespaced_under_client(db, plant):
    client = SimpleNamespace(
        id=uuid.uuid4(), name="Ana", email="a@x.gt", phone="", address="",
        custom_field_values=[SimpleNamespace(
            value="42", field_definition=SimpleNamespace(
                field_key="nodo", field_type="NUMBER"))],
    )
    v = resolve_provisioning(db, _detached_service(plant, client)).shared_variables
    assert v["client.nodo"] == 42


def test_a_builtin_client_field_wins_a_collision(db, plant):
    client = SimpleNamespace(
        id=uuid.uuid4(), name="Ana", email="", phone="", address="",
        custom_field_values=[SimpleNamespace(
            value="shadow", field_definition=SimpleNamespace(
                field_key="name", field_type="TEXT"))],
    )
    v = resolve_provisioning(db, _detached_service(plant, client)).shared_variables
    assert v["client.name"] == "Ana"


def test_an_ungrammatical_custom_key_is_skipped(db):
    client = SimpleNamespace(custom_field_values=[SimpleNamespace(
        value="x", field_definition=SimpleNamespace(
            field_key="5g_profile", field_type="TEXT"))])
    assert list(iter_client_custom_fields(client)) == []


def test_a_missing_client_relationship_does_not_crash(db, plant):
    v = resolve_provisioning(db, _detached_service(plant, None)).shared_variables
    assert "client.id" not in v
