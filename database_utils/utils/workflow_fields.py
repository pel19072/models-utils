"""
Workflow field metadata: hardcoded allowlist of editable fields per resource type.

Used by the workflow UI to populate field dropdowns in triggers and steps,
and by the engine to validate field access.
"""
from typing import List, Dict, Any, Optional


# Each entry: {"name": "<column_name>", "type": "<field_type>", "fk_to": "<resource_type>" | None}
# type values: "string", "number", "boolean", "date", "uuid", "json"
RESOURCE_FIELDS: Dict[str, List[Dict[str, Any]]] = {
    # NOTE (doc 16 §2.2/§5.3): `paid` removed — payment state is written only by
    # backend-erp's PaymentService (single-writer invariant). payment_status and
    # order_type are exposed for TRIGGER CONDITIONS only; the engine's
    # UPDATE_FIELD denylist (workflow_engine.py) blocks writing them.
    "order": [
        {"name": "due_date", "type": "date", "fk_to": None},
        {"name": "total", "type": "number", "fk_to": None},
        {"name": "status", "type": "string", "fk_to": None},
        {"name": "payment_status", "type": "string", "fk_to": None},
        {"name": "order_type", "type": "string", "fk_to": None},
        {"name": "client_id", "type": "uuid", "fk_to": "client"},
        {"name": "recurring_order_id", "type": "uuid", "fk_to": "recurring_order"},
    ],
    "client": [
        {"name": "name", "type": "string", "fk_to": None},
        {"name": "tax_id", "type": "string", "fk_to": None},
        {"name": "address", "type": "string", "fk_to": None},
        {"name": "phone", "type": "string", "fk_to": None},
        {"name": "email", "type": "string", "fk_to": None},
        {"name": "contact", "type": "string", "fk_to": None},
        {"name": "observations", "type": "string", "fk_to": None},
        {"name": "advisor_id", "type": "uuid", "fk_to": None},
        {"name": "latitude", "type": "number", "fk_to": None},
        {"name": "longitude", "type": "number", "fk_to": None},
        {"name": "installation_address", "type": "string", "fk_to": None},
        {"name": "service_availability", "type": "string", "fk_to": None},
        {"name": "installation_status", "type": "string", "fk_to": None},
        {"name": "installation_date", "type": "date", "fk_to": None},
        {"name": "assigned_technician_id", "type": "uuid", "fk_to": None},
    ],
    "product": [
        {"name": "name", "type": "string", "fk_to": None},
        {"name": "price", "type": "number", "fk_to": None},
        {"name": "description", "type": "string", "fk_to": None},
        {"name": "stock", "type": "number", "fk_to": None},
    ],
    "task": [
        {"name": "name", "type": "string", "fk_to": None},
        {"name": "description", "type": "string", "fk_to": None},
        {"name": "position", "type": "number", "fk_to": None},
        {"name": "due_date", "type": "date", "fk_to": None},
        {"name": "task_state_id", "type": "uuid", "fk_to": "task_state"},
    ],
    "task_state": [
        {"name": "name", "type": "string", "fk_to": None},
        {"name": "color", "type": "string", "fk_to": None},
        {"name": "position", "type": "number", "fk_to": None},
    ],
    "recurring_order": [
        {"name": "recurrence", "type": "string", "fk_to": None},
        {"name": "recurrence_end", "type": "date", "fk_to": None},
        {"name": "status", "type": "string", "fk_to": None},
        {"name": "client_id", "type": "uuid", "fk_to": "client"},
    ],
    "invoice": [
        {"name": "issue_date", "type": "date", "fk_to": None},
        {"name": "subtotal", "type": "number", "fk_to": None},
        {"name": "tax", "type": "number", "fk_to": None},
        {"name": "total", "type": "number", "fk_to": None},
        {"name": "details", "type": "json", "fk_to": None},
        {"name": "is_valid", "type": "boolean", "fk_to": None},
        {"name": "order_id", "type": "uuid", "fk_to": "order"},
    ],
    "order_item": [
        {"name": "order_id", "type": "uuid", "fk_to": "order"},
        {"name": "product_id", "type": "uuid", "fk_to": "product"},
        {"name": "quantity", "type": "number", "fk_to": None},
    ],
    # --- ISP resources ---
    "service_plan": [
        {"name": "name", "type": "string", "fk_to": None},
        {"name": "plan_type", "type": "string", "fk_to": None},
        {"name": "download_mbps", "type": "number", "fk_to": None},
        {"name": "upload_mbps", "type": "number", "fk_to": None},
        {"name": "price", "type": "number", "fk_to": None},
        {"name": "is_active", "type": "boolean", "fk_to": None},
    ],
    "client_service": [
        {"name": "status", "type": "string", "fk_to": None},
        {"name": "activation_date", "type": "date", "fk_to": None},
        {"name": "notes", "type": "string", "fk_to": None},
        {"name": "client_id", "type": "uuid", "fk_to": "client"},
        {"name": "service_plan_id", "type": "uuid", "fk_to": "service_plan"},
        {"name": "network_node_id", "type": "uuid", "fk_to": "network_node"},
        {"name": "recurring_order_id", "type": "uuid", "fk_to": "recurring_order"},
    ],
    "service_suspension": [
        {"name": "reason", "type": "string", "fk_to": None},
        {"name": "note", "type": "string", "fk_to": None},
        {"name": "reactivated_at", "type": "date", "fk_to": None},
        {"name": "client_service_id", "type": "uuid", "fk_to": "client_service"},
    ],
    "inventory_item": [
        {"name": "serial_number", "type": "string", "fk_to": None},
        {"name": "mac_address", "type": "string", "fk_to": None},
        {"name": "status", "type": "string", "fk_to": None},
        {"name": "condition", "type": "string", "fk_to": None},
        {"name": "notes", "type": "string", "fk_to": None},
        {"name": "warehouse_id", "type": "uuid", "fk_to": None},
        {"name": "client_id", "type": "uuid", "fk_to": "client"},
        {"name": "client_service_id", "type": "uuid", "fk_to": "client_service"},
        {"name": "network_node_id", "type": "uuid", "fk_to": "network_node"},
    ],
    "network_node": [
        {"name": "name", "type": "string", "fk_to": None},
        {"name": "status", "type": "string", "fk_to": None},
        {"name": "latitude", "type": "number", "fk_to": None},
        {"name": "longitude", "type": "number", "fk_to": None},
        {"name": "capacity", "type": "number", "fk_to": None},
        {"name": "parent_id", "type": "uuid", "fk_to": "network_node"},
    ],
    "provisioning_job": [
        {"name": "status", "type": "string", "fk_to": None},
        {"name": "error", "type": "string", "fk_to": None},
        {"name": "client_service_id", "type": "uuid", "fk_to": "client_service"},
        {"name": "network_node_id", "type": "uuid", "fk_to": "network_node"},
    ],
}


def get_resource_fields(resource_type: str) -> List[Dict[str, Any]]:
    """Return all editable fields for a given resource type."""
    return RESOURCE_FIELDS.get(resource_type, [])


def get_fk_fields(resource_type: str) -> List[Dict[str, Any]]:
    """Return only FK fields for a resource type (for match_field dropdowns)."""
    return [f for f in get_resource_fields(resource_type) if f.get("fk_to")]


def get_resource_types() -> List[str]:
    """Return all known resource types."""
    return list(RESOURCE_FIELDS.keys())
