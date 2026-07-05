"""
ISP module seed: permissions, base roles, tier modules, default topology node
types, and installable workflow templates (ADR-007/008).

Idempotent — every insert is ON CONFLICT DO NOTHING / DO UPDATE (workflow
templates upsert so blueprint revisions propagate) or existence-checked, so it
is safe on both fresh databases (called after rbac_seed) and existing tenants
(called from the isp-platform Alembic revision).
"""
import json
import logging
import os
import sys

from sqlalchemy import text
from sqlalchemy.engine import Connection

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
from database_utils.utils.timezone_utils import now_gt

logger = logging.getLogger(__name__)


ISP_PERMISSIONS = [
    # Service plans
    {"name": "service_plans.create", "resource": "service_plans", "action": "create", "description": "Create service plans"},
    {"name": "service_plans.read", "resource": "service_plans", "action": "read", "description": "View service plans"},
    {"name": "service_plans.update", "resource": "service_plans", "action": "update", "description": "Update service plans"},
    {"name": "service_plans.delete", "resource": "service_plans", "action": "delete", "description": "Delete service plans"},
    # Client services (subscriptions)
    {"name": "client_services.create", "resource": "client_services", "action": "create", "description": "Create subscriber services"},
    {"name": "client_services.read", "resource": "client_services", "action": "read", "description": "View subscriber services"},
    {"name": "client_services.update", "resource": "client_services", "action": "update", "description": "Update subscriber services"},
    {"name": "client_services.delete", "resource": "client_services", "action": "delete", "description": "Delete subscriber services"},
    {"name": "client_services.suspend", "resource": "client_services", "action": "suspend", "description": "Suspend a subscriber service"},
    {"name": "client_services.reactivate", "resource": "client_services", "action": "reactivate", "description": "Reactivate a suspended service"},
    # Inventory
    {"name": "device_types.create", "resource": "device_types", "action": "create", "description": "Create device catalog entries"},
    {"name": "device_types.read", "resource": "device_types", "action": "read", "description": "View device catalog"},
    {"name": "device_types.update", "resource": "device_types", "action": "update", "description": "Update device catalog entries"},
    {"name": "device_types.delete", "resource": "device_types", "action": "delete", "description": "Delete device catalog entries"},
    {"name": "warehouses.create", "resource": "warehouses", "action": "create", "description": "Create warehouses"},
    {"name": "warehouses.read", "resource": "warehouses", "action": "read", "description": "View warehouses"},
    {"name": "warehouses.update", "resource": "warehouses", "action": "update", "description": "Update warehouses"},
    {"name": "warehouses.delete", "resource": "warehouses", "action": "delete", "description": "Delete warehouses"},
    {"name": "inventory_items.create", "resource": "inventory_items", "action": "create", "description": "Register inventory items"},
    {"name": "inventory_items.read", "resource": "inventory_items", "action": "read", "description": "View inventory items"},
    {"name": "inventory_items.update", "resource": "inventory_items", "action": "update", "description": "Update inventory items"},
    {"name": "inventory_items.delete", "resource": "inventory_items", "action": "delete", "description": "Delete inventory items"},
    {"name": "equipment_events.create", "resource": "equipment_events", "action": "create", "description": "Record equipment lifecycle events"},
    {"name": "equipment_events.read", "resource": "equipment_events", "action": "read", "description": "View equipment history"},
    # Network / topology
    {"name": "network_node_types.create", "resource": "network_node_types", "action": "create", "description": "Define topology node types"},
    {"name": "network_node_types.read", "resource": "network_node_types", "action": "read", "description": "View topology node types"},
    {"name": "network_node_types.update", "resource": "network_node_types", "action": "update", "description": "Update topology node types"},
    {"name": "network_node_types.delete", "resource": "network_node_types", "action": "delete", "description": "Delete topology node types"},
    {"name": "network_nodes.create", "resource": "network_nodes", "action": "create", "description": "Create network nodes"},
    {"name": "network_nodes.read", "resource": "network_nodes", "action": "read", "description": "View network topology"},
    {"name": "network_nodes.update", "resource": "network_nodes", "action": "update", "description": "Update network nodes"},
    {"name": "network_nodes.delete", "resource": "network_nodes", "action": "delete", "description": "Delete network nodes"},
    {"name": "network_links.create", "resource": "network_links", "action": "create", "description": "Create network links"},
    {"name": "network_links.read", "resource": "network_links", "action": "read", "description": "View network links"},
    {"name": "network_links.delete", "resource": "network_links", "action": "delete", "description": "Delete network links"},
    # Provisioning automation
    {"name": "playbooks.create", "resource": "playbooks", "action": "create", "description": "Upload provisioning playbooks"},
    {"name": "playbooks.read", "resource": "playbooks", "action": "read", "description": "View provisioning playbooks"},
    {"name": "playbooks.update", "resource": "playbooks", "action": "update", "description": "Update provisioning playbooks"},
    {"name": "playbooks.delete", "resource": "playbooks", "action": "delete", "description": "Delete provisioning playbooks"},
    {"name": "provisioning.read", "resource": "provisioning", "action": "read", "description": "View provisioning jobs"},
    {"name": "provisioning.create", "resource": "provisioning", "action": "create", "description": "Enqueue provisioning jobs"},
    {"name": "provisioning.execute", "resource": "provisioning", "action": "execute", "description": "Execute/retry provisioning jobs"},
    {"name": "provisioning.cancel", "resource": "provisioning", "action": "cancel", "description": "Cancel provisioning jobs"},
    # Workflow templates
    {"name": "workflow_templates.read", "resource": "workflow_templates", "action": "read", "description": "Browse workflow template catalog"},
    {"name": "workflow_templates.install", "resource": "workflow_templates", "action": "install", "description": "Install a workflow template"},
]

# New ISP base roles (global: company_id NULL) and their permission grants.
ISP_ROLES = {
    "TECHNICIAN": {
        "description": "Field technician: installations, equipment handling, dispatch board",
        "permissions": [
            "tasks.create", "tasks.read", "tasks.update",
            "task_states.read",
            "clients.read", "clients.update",
            "client_services.read", "client_services.update",
            "inventory_items.read", "inventory_items.update",
            "equipment_events.create", "equipment_events.read",
            "warehouses.read", "device_types.read",
            "network_nodes.read", "network_node_types.read", "network_links.read",
            "provisioning.read",
            "dashboard.read",
        ],
    },
    "NOC": {
        "description": "Network operations: topology, playbooks, provisioning jobs",
        "permissions": [
            "network_node_types.create", "network_node_types.read", "network_node_types.update", "network_node_types.delete",
            "network_nodes.create", "network_nodes.read", "network_nodes.update", "network_nodes.delete",
            "network_links.create", "network_links.read", "network_links.delete",
            "playbooks.create", "playbooks.read", "playbooks.update", "playbooks.delete",
            "provisioning.read", "provisioning.create", "provisioning.execute", "provisioning.cancel",
            "client_services.read",
            "inventory_items.read", "device_types.read",
            "workflow_templates.read",
            "tasks.create", "tasks.read", "tasks.update",
            "task_states.read",
            "dashboard.read",
        ],
    },
    "WAREHOUSE": {
        "description": "Warehouse custody: device catalog, stock, transfers",
        "permissions": [
            "device_types.create", "device_types.read", "device_types.update", "device_types.delete",
            "warehouses.create", "warehouses.read", "warehouses.update", "warehouses.delete",
            "inventory_items.create", "inventory_items.read", "inventory_items.update", "inventory_items.delete",
            "equipment_events.create", "equipment_events.read",
            "dashboard.read",
        ],
    },
    "SUPPORT": {
        "description": "Subscriber care: client data, services, suspensions, tickets",
        "permissions": [
            "clients.create", "clients.read", "clients.update",
            "client_services.create", "client_services.read", "client_services.update",
            "client_services.suspend", "client_services.reactivate",
            "service_plans.read",
            "orders.read", "recurring_orders.read",
            "tasks.create", "tasks.read", "tasks.update",
            "task_states.read",
            "provisioning.read",
            "dashboard.read",
        ],
    },
    "BILLING": {
        "description": "Billing operations: orders, recurring billing, plans",
        "permissions": [
            "clients.read",
            "orders.create", "orders.read", "orders.update",
            "recurring_orders.create", "recurring_orders.read", "recurring_orders.update",
            "products.read",
            "service_plans.read", "client_services.read",
            "dashboard.read",
        ],
    },
}

ISP_TIER_MODULES = ["inventory", "network", "provisioning"]

# Default per-company topology node types (config rows, ADR-003).
DEFAULT_NODE_TYPES = [
    {"key": "headend", "name": "Headend / POP", "category": None, "icon": "building", "allowed_parent_keys": []},
    {"key": "olt", "name": "OLT", "category": "OLT", "icon": "server", "allowed_parent_keys": ["headend"]},
    {"key": "pon_port", "name": "PON Port", "category": None, "icon": "plug", "allowed_parent_keys": ["olt"]},
    {"key": "splitter", "name": "Splitter", "category": "SPLITTER", "icon": "git-branch", "allowed_parent_keys": ["pon_port", "splitter"]},
    {"key": "splice_closure", "name": "Splice Closure (MUFA)", "category": "SPLICE_CLOSURE", "icon": "box", "allowed_parent_keys": ["pon_port", "splitter", "splice_closure"]},
    {"key": "onu", "name": "ONU / ONT", "category": "ONU", "icon": "radio-receiver", "allowed_parent_keys": ["splitter", "splice_closure", "pon_port"]},
    {"key": "cpe_router", "name": "Customer Router", "category": "CPE_ROUTER", "icon": "router", "allowed_parent_keys": ["onu"]},
]


def _wt(key, name, description, category, parameters, triggers, steps, edges):
    return {
        "key": key, "name": name, "description": description, "category": category,
        "definition": {
            "parameters": parameters, "triggers": triggers, "steps": steps, "edges": edges,
        },
    }


# Installable workflow templates (ADR-007). "{{param:KEY}}" placeholders are
# resolved at install time; "{{trigger.*}}" placeholders stay for runtime.
WORKFLOW_TEMPLATES = [
    # v2 (doc 16 §5.4, installation-flow): PENDING_INSTALL-gated trigger so
    # imports/backfills creating ACTIVE services never spawn install orders;
    # s1 bills the installation fee (CREATE_ORDER), s2 opens the dispatch task
    # (CREATE_TASK, linked CLIENT_SERVICE — the Cycle-3 join key; ORDER linkage
    # is forbidden), s3 syncs the client's installation_status display cache.
    # Free installs = a Q0 fee product; the order still exists as history and
    # is settled via settle-zero. Tenants must reinstall to pick up v2.
    _wt(
        "new-installation", "New Installation",
        "When a subscriber service is created pending installation, bill the installation fee, "
        "open an installation task on the dispatch board and mark the client as scheduled.",
        "installation",
        [
            {"key": "install_state_id", "label": "Board column for new installations", "type": "task_state", "required": True},
            {"key": "installation_fee_product_id", "label": "Installation fee product (use a Q0 product for free installs)", "type": "product", "required": True},
            {"key": "fixed_assignee_ids", "label": "Fallback technicians when the client has no assigned technician", "type": "users", "required": False},
        ],
        [{"resource_type": "client_service", "event_type": "CREATED",
          "field_conditions": {"field": "status", "operator": "equals", "value": "PENDING_INSTALL"}}],
        [
            {"ref": "s1", "name": "Create installation order", "action_type": "CREATE_ORDER",
             "action_config": {
                 "order_type": "INSTALLATION",
                 "client_id": "{{trigger.after.client_id}}",
                 "client_service_id": "{{trigger.resource_id}}",
                 "items": [{"product_id": "{{param:installation_fee_product_id}}", "quantity": 1}],
                 "due_date_offset_days": 0,
                 "idempotency_key": "install-order-{{trigger.resource_id}}"}},
            {"ref": "s2", "name": "Create installation task", "action_type": "CREATE_TASK",
             "action_config": {
                 "name": "New installation — service {{trigger.resource_id}}",
                 "description": "Install subscriber service. Client: {{trigger.after.client_id}}. "
                                "Installation order: {{steps.s1.resource_id}}",
                 "task_state_id": "{{param:install_state_id}}",
                 "linked_object_type": "CLIENT_SERVICE",
                 "linked_object_id": "{{trigger.resource_id}}",
                 "assignee_source": "client_technician",
                 "assignee_ids": "{{param:fixed_assignee_ids}}",
                 "client_id": "{{trigger.after.client_id}}"}},
            {"ref": "s3", "name": "Mark client install scheduled", "action_type": "UPDATE_FIELD",
             "action_config": {
                 "resource_type": "client",
                 "resource_id_source": "custom",
                 "resource_id": "{{trigger.after.client_id}}",
                 "updates": {"installation_status": "INSTALL_SCHEDULED"}}},
        ],
        [{"from": "s1", "to": "s2"}, {"from": "s2", "to": "s3"}],
    ),
    _wt(
        "installation-provisioning", "Installation → Provisioning",
        "When an installation task is moved to the 'installed' column, run the activation playbook for the linked service.",
        "installation",
        [
            {"key": "installed_state_id", "label": "Board column meaning 'installation done'", "type": "task_state", "required": True},
            {"key": "activation_playbook_id", "label": "Activation playbook", "type": "playbook", "required": True},
        ],
        [{"resource_type": "task", "event_type": "UPDATED",
          "field_conditions": {"field": "task_state_id", "operator": "changed_to", "value": "{{param:installed_state_id}}"}}],
        [{"ref": "provision", "name": "Run activation playbook", "action_type": "ENQUEUE_PROVISIONING",
          "action_config": {"playbook_id": "{{param:activation_playbook_id}}",
                            "client_service_id": "{{trigger.after.linked_object_id}}",
                            "idempotency_key": "activate-{{trigger.after.linked_object_id}}",
                            "variables": {"client_service_id": "{{trigger.after.linked_object_id}}"}}}],
        [],
    ),
    _wt(
        "service-activation", "Service Activation on Provisioning Success",
        "When a provisioning job succeeds, mark the linked service ACTIVE (billing starts via the plan's recurring order).",
        "installation",
        [],
        [{"resource_type": "provisioning_job", "event_type": "UPDATED",
          "field_conditions": {"field": "status", "operator": "changed_to", "value": "SUCCEEDED"}}],
        [{"ref": "activate", "name": "Activate service", "action_type": "UPDATE_FIELD",
          "action_config": {"resource_type": "client_service", "resource_id_source": "custom",
                            "resource_id": "{{trigger.after.client_service_id}}",
                            "updates": {"status": "ACTIVE"}}}],
        [],
    ),
    _wt(
        "suspension", "Service Suspension",
        "When a service is suspended, record history, pause its billing and run the suspend playbook.",
        "billing",
        [{"key": "suspend_playbook_id", "label": "Suspension playbook", "type": "playbook", "required": True}],
        [{"resource_type": "client_service", "event_type": "UPDATED",
          "field_conditions": {"field": "status", "operator": "changed_to", "value": "SUSPENDED"}}],
        [
            {"ref": "pause_billing", "name": "Pause recurring billing", "action_type": "UPDATE_FIELD",
             "action_config": {"resource_type": "recurring_order", "resource_id_source": "custom",
                               "resource_id": "{{trigger.after.recurring_order_id}}",
                               "updates": {"status": "PAUSED"}}},
            {"ref": "provision", "name": "Run suspend playbook", "action_type": "ENQUEUE_PROVISIONING",
             "action_config": {"playbook_id": "{{param:suspend_playbook_id}}",
                               "client_service_id": "{{trigger.resource_id}}",
                               "idempotency_key": "suspend-{{trigger.resource_id}}",
                               "variables": {"client_service_id": "{{trigger.resource_id}}"}}},
        ],
        [{"from": "pause_billing", "to": "provision"}],
    ),
    _wt(
        "reactivation", "Service Reactivation",
        "When a suspended service is reactivated, resume billing and run the reactivation playbook.",
        "billing",
        [{"key": "reactivate_playbook_id", "label": "Reactivation playbook", "type": "playbook", "required": True}],
        [{"resource_type": "client_service", "event_type": "UPDATED",
          "field_conditions": {"field": "status", "operator": "changed_from", "value": "SUSPENDED"}}],
        [
            {"ref": "resume_billing", "name": "Resume recurring billing", "action_type": "UPDATE_FIELD",
             "action_config": {"resource_type": "recurring_order", "resource_id_source": "custom",
                               "resource_id": "{{trigger.after.recurring_order_id}}",
                               "updates": {"status": "ACTIVE"}}},
            {"ref": "provision", "name": "Run reactivation playbook", "action_type": "ENQUEUE_PROVISIONING",
             "action_config": {"playbook_id": "{{param:reactivate_playbook_id}}",
                               "client_service_id": "{{trigger.resource_id}}",
                               "idempotency_key": "reactivate-{{trigger.resource_id}}",
                               "variables": {"client_service_id": "{{trigger.resource_id}}"}}},
        ],
        [{"from": "resume_billing", "to": "provision"}],
    ),
    _wt(
        "plan-change", "Plan Upgrade / Downgrade",
        "When a service's plan changes, run the plan-change playbook with the new plan id.",
        "billing",
        [{"key": "plan_change_playbook_id", "label": "Plan change playbook", "type": "playbook", "required": True}],
        [{"resource_type": "client_service", "event_type": "UPDATED",
          "field_conditions": {"field": "service_plan_id", "operator": "changed"}}],
        [{"ref": "provision", "name": "Apply new plan on the network", "action_type": "ENQUEUE_PROVISIONING",
          "action_config": {"playbook_id": "{{param:plan_change_playbook_id}}",
                            "client_service_id": "{{trigger.resource_id}}",
                            "variables": {"client_service_id": "{{trigger.resource_id}}",
                                          "service_plan_id": "{{trigger.after.service_plan_id}}"}}}],
        [],
    ),
    _wt(
        "service-removal", "Service Removal",
        "When a service is cancelled, cancel billing and run the deprovision playbook.",
        "billing",
        [{"key": "deprovision_playbook_id", "label": "Deprovision playbook", "type": "playbook", "required": True}],
        [{"resource_type": "client_service", "event_type": "UPDATED",
          "field_conditions": {"field": "status", "operator": "changed_to", "value": "CANCELLED"}}],
        [
            {"ref": "cancel_billing", "name": "Cancel recurring billing", "action_type": "UPDATE_FIELD",
             "action_config": {"resource_type": "recurring_order", "resource_id_source": "custom",
                               "resource_id": "{{trigger.after.recurring_order_id}}",
                               "updates": {"status": "CANCELLED"}}},
            {"ref": "provision", "name": "Run deprovision playbook", "action_type": "ENQUEUE_PROVISIONING",
             "action_config": {"playbook_id": "{{param:deprovision_playbook_id}}",
                               "client_service_id": "{{trigger.resource_id}}",
                               "variables": {"client_service_id": "{{trigger.resource_id}}"}}},
        ],
        [{"from": "cancel_billing", "to": "provision"}],
    ),
    _wt(
        "onu-replacement", "ONU / Equipment Replacement",
        "When customer equipment is reassigned to a service, run the equipment provisioning playbook with its serial.",
        "network",
        [{"key": "equipment_playbook_id", "label": "Equipment provisioning playbook", "type": "playbook", "required": True}],
        [{"resource_type": "inventory_item", "event_type": "UPDATED",
          "field_conditions": {"field": "client_service_id", "operator": "changed"}}],
        [{"ref": "provision", "name": "Provision replacement equipment", "action_type": "ENQUEUE_PROVISIONING",
          "action_config": {"playbook_id": "{{param:equipment_playbook_id}}",
                            "inventory_item_id": "{{trigger.resource_id}}",
                            "client_service_id": "{{trigger.after.client_service_id}}",
                            "variables": {"serial_number": "{{trigger.after.serial_number}}",
                                          "mac_address": "{{trigger.after.mac_address}}"}}}],
        [],
    ),
    _wt(
        "fiber-cut", "Fiber Cut Response",
        "When a network node goes DOWN, open a NOC incident task.",
        "network",
        [{"key": "noc_state_id", "label": "Board column for network incidents", "type": "task_state", "required": True}],
        [{"resource_type": "network_node", "event_type": "UPDATED",
          "field_conditions": {"field": "status", "operator": "changed_to", "value": "DOWN"}}],
        [{"ref": "incident", "name": "Open incident task", "action_type": "CREATE_ENTITY",
          "action_config": {"resource_type": "task", "data": {
              "name": "NETWORK DOWN: {{trigger.after.name}}",
              "description": "Node {{trigger.after.name}} reported DOWN. Check impacted subscribers behind this node.",
              "task_state_id": "{{param:noc_state_id}}",
              "linked_object_type": "NETWORK_NODE",
              "linked_object_id": "{{trigger.resource_id}}"}}}],
        [],
    ),
    _wt(
        "maintenance", "Scheduled Maintenance",
        "When a network node enters MAINTENANCE, open a maintenance task.",
        "network",
        [{"key": "maintenance_state_id", "label": "Board column for maintenance", "type": "task_state", "required": True}],
        [{"resource_type": "network_node", "event_type": "UPDATED",
          "field_conditions": {"field": "status", "operator": "changed_to", "value": "MAINTENANCE"}}],
        [{"ref": "task", "name": "Open maintenance task", "action_type": "CREATE_ENTITY",
          "action_config": {"resource_type": "task", "data": {
              "name": "Maintenance: {{trigger.after.name}}",
              "task_state_id": "{{param:maintenance_state_id}}",
              "linked_object_type": "NETWORK_NODE",
              "linked_object_id": "{{trigger.resource_id}}"}}}],
        [],
    ),
]


def seed_isp_data(connection: Connection) -> None:
    """Seed ISP permissions, roles, tier modules, node types and templates."""
    _seed_permissions(connection)
    _seed_roles(connection)
    _seed_tier_modules(connection)
    _seed_default_node_types(connection)
    _seed_workflow_templates(connection)
    logger.info("ISP seed completed")


def _seed_permissions(connection: Connection) -> None:
    for perm in ISP_PERMISSIONS:
        connection.execute(
            text(
                "INSERT INTO permission (id, created_at, name, resource, action, description) "
                "VALUES (gen_random_uuid(), :created_at, :name, :resource, :action, :description) "
                "ON CONFLICT (name) DO NOTHING"
            ),
            {"created_at": now_gt(), **perm},
        )
    # ADMIN and MANAGER inherit all new permissions (matching rbac_seed policy).
    for role_name in ("ADMIN", "MANAGER"):
        connection.execute(
            text(
                "INSERT INTO role_permission (role_id, permission_id) "
                "SELECT r.id, p.id FROM role r, permission p "
                "WHERE r.name = :role AND r.company_id IS NULL AND p.name = ANY(:names) "
                "ON CONFLICT DO NOTHING"
            ),
            {"role": role_name, "names": [p["name"] for p in ISP_PERMISSIONS]},
        )
    logger.info(f"Seeded {len(ISP_PERMISSIONS)} ISP permissions")


def _seed_roles(connection: Connection) -> None:
    for role_name, spec in ISP_ROLES.items():
        row = connection.execute(
            text("SELECT id FROM role WHERE name = :name AND company_id IS NULL"),
            {"name": role_name},
        ).fetchone()
        if row:
            role_id = row[0]
        else:
            role_id = connection.execute(
                text(
                    "INSERT INTO role (id, created_at, name, description, is_system) "
                    "VALUES (gen_random_uuid(), :created_at, :name, :description, TRUE) "
                    "RETURNING id"
                ),
                {"created_at": now_gt(), "name": role_name, "description": spec["description"]},
            ).fetchone()[0]
        connection.execute(
            text(
                "INSERT INTO role_permission (role_id, permission_id) "
                "SELECT :role_id, p.id FROM permission p WHERE p.name = ANY(:names) "
                "ON CONFLICT DO NOTHING"
            ),
            {"role_id": role_id, "names": spec["permissions"]},
        )
    logger.info(f"Seeded {len(ISP_ROLES)} ISP roles")


def _seed_tier_modules(connection: Connection) -> None:
    """Append the ISP module keys to every tier's modules JSON list."""
    rows = connection.execute(text("SELECT id, modules FROM tier")).fetchall()
    for tier_id, modules in rows:
        current = modules or []
        if isinstance(current, str):
            current = json.loads(current)
        merged = list(dict.fromkeys([*current, *ISP_TIER_MODULES]))
        if merged != current:
            connection.execute(
                text("UPDATE tier SET modules = :modules WHERE id = :id"),
                {"modules": json.dumps(merged), "id": tier_id},
            )
    logger.info("Tier modules updated with ISP modules")


def _seed_default_node_types(connection: Connection) -> None:
    """Give every existing company the default GPON node-type set."""
    companies = connection.execute(text("SELECT id FROM company")).fetchall()
    for (company_id,) in companies:
        for nt in DEFAULT_NODE_TYPES:
            connection.execute(
                text(
                    "INSERT INTO network_node_type "
                    "(id, created_at, key, name, category, icon, allowed_parent_keys, attribute_schema, company_id) "
                    "VALUES (gen_random_uuid(), :created_at, :key, :name, :category, :icon, :parents, NULL, :company_id) "
                    "ON CONFLICT (company_id, key) DO NOTHING"
                ),
                {
                    "created_at": now_gt(),
                    "key": nt["key"],
                    "name": nt["name"],
                    "category": nt["category"],
                    "icon": nt["icon"],
                    "parents": json.dumps(nt["allowed_parent_keys"]),
                    "company_id": company_id,
                },
            )
    logger.info(f"Seeded default node types for {len(companies)} companies")


def _seed_workflow_templates(connection: Connection) -> None:
    # Upsert (doc 16 §5.4): templates are global blueprints; installed
    # workflows are materialized copies, so DO UPDATE is safe and lets template
    # revisions (e.g. new-installation v2) ship without a new key. Release
    # note: tenants reinstall to pick up a new version.
    for tpl in WORKFLOW_TEMPLATES:
        connection.execute(
            text(
                "INSERT INTO workflow_template (id, created_at, key, name, description, category, definition, is_active) "
                "VALUES (gen_random_uuid(), :created_at, :key, :name, :description, :category, :definition, TRUE) "
                "ON CONFLICT (key) DO UPDATE SET "
                "name = EXCLUDED.name, description = EXCLUDED.description, "
                "category = EXCLUDED.category, definition = EXCLUDED.definition, "
                "is_active = TRUE"
            ),
            {
                "created_at": now_gt(),
                "key": tpl["key"],
                "name": tpl["name"],
                "description": tpl["description"],
                "category": tpl["category"],
                "definition": json.dumps(tpl["definition"]),
            },
        )
    logger.info(f"Seeded {len(WORKFLOW_TEMPLATES)} workflow templates")
