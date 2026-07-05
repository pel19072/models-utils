# utils/workflow_engine.py
"""
Workflow engine: trigger matching and asynchronous DAG execution.

Called from CRUD routers after audit logging to fire matching workflows.
Workflows execute asynchronously via asyncio.create_task().
"""
from __future__ import annotations

import asyncio
import contextvars
from collections import defaultdict, deque
from typing import Optional, List, Dict, Any
from uuid import UUID

from loguru import logger
from sqlalchemy.orm import Session, joinedload

from database_utils.database import SessionLocal
from database_utils.models.workflow import (
    Workflow,
    WorkflowTrigger,
    WorkflowStep,
    WorkflowStepEdge,
    WorkflowExecution,
    WorkflowStepExecution,
    StepActionType,
    ExecutionStatus,
)
from database_utils.utils.timezone_utils import now_gt


# Recursion guard to prevent infinite trigger chains
_workflow_execution_depth = contextvars.ContextVar('workflow_depth', default=0)
MAX_WORKFLOW_DEPTH = 3

# Strong references to fire-and-forget workflow tasks. The event loop only keeps
# a weak reference to a Task, so without this a scheduled workflow execution can
# be garbage-collected mid-run (WF-3). Tasks discard themselves on completion.
_background_tasks: set[asyncio.Task] = set()

# Map resource types to their SQLAlchemy model classes
_MODEL_MAP = None


def _get_model_map():
    """Lazy-load model map to avoid circular imports."""
    global _MODEL_MAP
    if _MODEL_MAP is None:
        from database_utils.models.crm import (
            Order, Client, Product, Task, TaskState,
            RecurringOrder, Invoice, OrderItem,
        )
        from database_utils.models.isp import (
            ServicePlan, ClientService, ServiceSuspension,
            InventoryItem, NetworkNode, ProvisioningJob,
        )
        _MODEL_MAP = {
            "order": Order,
            "client": Client,
            "product": Product,
            "task": Task,
            "task_state": TaskState,
            "recurring_order": RecurringOrder,
            "invoice": Invoice,
            "order_item": OrderItem,
            # ISP resources
            "service_plan": ServicePlan,
            "client_service": ClientService,
            "service_suspension": ServiceSuspension,
            "inventory_item": InventoryItem,
            "network_node": NetworkNode,
            "provisioning_job": ProvisioningJob,
        }
    return _MODEL_MAP


async def check_workflow_triggers(
    db: Session,
    company_id: UUID,
    resource_type: str,
    event_type: str,
    resource_id: UUID,
    before_data: Optional[dict] = None,
    after_data: Optional[dict] = None,
) -> None:
    """
    Called after each CRUD operation. Finds matching active workflows
    for this company and fires them asynchronously.

    Args:
        db: Current request's database session (used only for querying workflows)
        company_id: The company that owns the resource
        resource_type: e.g. "order", "client", "product", "task"
        event_type: "CREATED", "UPDATED", "DELETED"
        resource_id: The ID of the affected resource
        before_data: State before the change (for updates/deletes)
        after_data: State after the change (for creates/updates)
    """
    depth = _workflow_execution_depth.get()
    if depth >= MAX_WORKFLOW_DEPTH:
        logger.warning(
            f"Workflow recursion depth {depth} exceeded for {resource_type}.{event_type}, skipping"
        )
        return

    try:
        matched = find_matching_workflows(
            db, company_id, resource_type, event_type, before_data, after_data
        )

        if not matched:
            return

        logger.info(
            f"Found {len(matched)} matching workflow(s) for "
            f"{resource_type}.{event_type} on resource {resource_id}"
        )

        from database_utils.utils.audit_utils import serialize_for_audit

        trigger_event = serialize_for_audit({
            "resource_type": resource_type,
            "event_type": event_type,
            "resource_id": str(resource_id),
            "before": before_data,
            "after": after_data,
        })

        for workflow in matched:
            task = asyncio.create_task(
                _execute_workflow_async(
                    workflow_id=workflow.id,
                    trigger_event=trigger_event,
                    company_id=company_id,
                    depth=depth,
                )
            )
            _background_tasks.add(task)
            task.add_done_callback(_background_tasks.discard)

    except Exception as e:
        logger.error(f"Error checking workflow triggers: {e}")


def find_matching_workflows(
    db: Session,
    company_id: UUID,
    resource_type: str,
    event_type: str,
    before_data: Optional[dict],
    after_data: Optional[dict],
) -> List[Workflow]:
    """
    Query active workflows for this company that have triggers matching
    the resource_type + event_type + field_conditions.
    """
    workflows = (
        db.query(Workflow)
        .join(WorkflowTrigger)
        .filter(
            Workflow.company_id == company_id,
            Workflow.is_active == True,
            WorkflowTrigger.resource_type == resource_type,
            WorkflowTrigger.event_type == event_type,
        )
        .options(joinedload(Workflow.triggers))
        .all()
    )

    # The filter join on WorkflowTrigger fans out one row per matching trigger,
    # so `workflows` can contain the same Workflow multiple times. Dedupe by id
    # so a workflow with >1 matching trigger executes exactly once (WF-2).
    matched = []
    seen: set = set()
    for workflow in workflows:
        if workflow.id in seen:
            continue
        for trigger in workflow.triggers:
            if (
                trigger.resource_type == resource_type
                and trigger.event_type.value == event_type
                and _matches_field_conditions(trigger.field_conditions, before_data, after_data)
            ):
                matched.append(workflow)
                seen.add(workflow.id)
                break

    return matched


def _matches_field_conditions(
    conditions: Optional[dict],
    before_data: Optional[dict],
    after_data: Optional[dict],
) -> bool:
    """
    Evaluate whether the trigger's field_conditions match the actual change.
    If conditions is None, any event of the right type matches.
    """
    if conditions is None:
        return True

    field = conditions.get("field")
    operator = conditions.get("operator")
    value = conditions.get("value")

    if not field or not operator:
        return True

    def _norm(v) -> str:
        # Enum members stringify as "ClassName.MEMBER"; compare by value.
        import enum as _enum
        if isinstance(v, _enum.Enum):
            v = v.value
        return str(v)

    if operator == "changed":
        if before_data and after_data:
            return _norm(before_data.get(field)) != _norm(after_data.get(field))
        return True

    elif operator == "changed_to":
        # True only on the transition INTO `value` — the field must not have
        # already equalled `value` before (WF-1). Missing before_data (e.g. on
        # CREATE) counts as "did not equal it before".
        if not after_data:
            return False
        before_val = _norm(before_data.get(field)) if before_data else None
        return before_val != _norm(value) and _norm(after_data.get(field)) == _norm(value)

    elif operator == "changed_from":
        # True only on the transition AWAY from `value`.
        if not before_data:
            return False
        after_val = _norm(after_data.get(field)) if after_data else None
        return _norm(before_data.get(field)) == _norm(value) and after_val != _norm(value)

    elif operator == "equals":
        if after_data:
            return _norm(after_data.get(field)) == _norm(value)
        return False

    return True


async def _execute_workflow_async(
    workflow_id: UUID,
    trigger_event: dict,
    company_id: UUID,
    depth: int,
) -> None:
    """
    Async wrapper that creates its own DB session and executes the workflow.
    Runs as a fire-and-forget background task.
    """
    _workflow_execution_depth.set(depth + 1)
    db = SessionLocal()
    try:
        workflow = (
            db.query(Workflow)
            .options(
                joinedload(Workflow.steps),
                joinedload(Workflow.edges),
            )
            .filter(Workflow.id == workflow_id)
            .first()
        )

        if not workflow:
            logger.error(f"Workflow {workflow_id} not found for execution")
            return

        execute_workflow(db, workflow, trigger_event, company_id)

    except Exception as e:
        logger.error(f"Workflow {workflow_id} execution failed: {e}")
        db.rollback()
    finally:
        db.close()
        _workflow_execution_depth.set(depth)


def execute_workflow(
    db: Session,
    workflow: Workflow,
    trigger_event: dict,
    company_id: UUID,
) -> WorkflowExecution:
    """Execute all steps of a workflow in topological order (Kahn's algorithm)."""

    execution = WorkflowExecution(
        workflow_id=workflow.id,
        trigger_event=trigger_event,
        status=ExecutionStatus.RUNNING,
        started_at=now_gt(),
    )
    db.add(execution)
    db.flush()

    steps_by_id = {step.id: step for step in workflow.steps}

    if not steps_by_id:
        execution.status = ExecutionStatus.COMPLETED
        execution.completed_at = now_gt()
        db.commit()
        return execution

    # Build adjacency list and in-degree count
    in_degree: Dict[UUID, int] = {step_id: 0 for step_id in steps_by_id}
    adjacency: Dict[UUID, List[UUID]] = {step_id: [] for step_id in steps_by_id}

    for edge in workflow.edges:
        if edge.from_step_id in adjacency and edge.to_step_id in in_degree:
            adjacency[edge.from_step_id].append(edge.to_step_id)
            in_degree[edge.to_step_id] += 1

    # Kahn's algorithm: start with nodes that have no incoming edges
    queue = deque([sid for sid, deg in in_degree.items() if deg == 0])
    execution_context: Dict[str, Any] = {"trigger": trigger_event}
    processed_count = 0

    try:
        while queue:
            step_id = queue.popleft()
            processed_count += 1
            step = steps_by_id[step_id]

            step_execution = WorkflowStepExecution(
                execution_id=execution.id,
                step_id=step_id,
                status=ExecutionStatus.RUNNING,
                started_at=now_gt(),
            )
            db.add(step_execution)
            db.flush()

            try:
                result = execute_step(db, step, execution_context, company_id)
                step_execution.status = ExecutionStatus.COMPLETED
                step_execution.result = result
                step_execution.completed_at = now_gt()
                execution_context[str(step_id)] = result
            except Exception as e:
                step_execution.status = ExecutionStatus.FAILED
                step_execution.error = str(e)
                step_execution.completed_at = now_gt()
                raise

            # Reduce in-degree for neighbors
            for neighbor_id in adjacency[step_id]:
                in_degree[neighbor_id] -= 1
                if in_degree[neighbor_id] == 0:
                    queue.append(neighbor_id)

        # WF-4: if Kahn's algorithm didn't reach every step, the graph has a
        # cycle (or unreachable steps). Fail explicitly instead of falling
        # through to COMPLETED with a partially-executed graph.
        if processed_count < len(steps_by_id):
            raise ValueError(
                f"Workflow graph has a cycle or unreachable steps: "
                f"{processed_count}/{len(steps_by_id)} steps executed"
            )

        execution.status = ExecutionStatus.COMPLETED
        execution.completed_at = now_gt()

    except Exception as e:
        execution.status = ExecutionStatus.FAILED
        execution.error = str(e)
        execution.completed_at = now_gt()
        logger.error(f"Workflow execution {execution.id} failed: {e}")

    db.commit()
    return execution


def execute_step(
    db: Session,
    step: WorkflowStep,
    context: dict,
    company_id: UUID,
) -> dict:
    """Execute a single workflow step based on its action_type."""
    # Resolve {{trigger.*}} / {{steps.*}} templates across the whole config so
    # dynamic resource_ids and entity data work in every action type.
    # (HTTP_REQUEST re-resolves its body internally — idempotent.)
    config = _resolve_template(step.action_config, context)

    if step.action_type == StepActionType.UPDATE_FIELD:
        return _execute_update_field(db, config, context, company_id)
    elif step.action_type == StepActionType.CREATE_ENTITY:
        return _execute_create_entity(db, config, context, company_id)
    elif step.action_type == StepActionType.HTTP_REQUEST:
        return _execute_http_request(db, step, context, company_id)
    elif step.action_type == StepActionType.ENQUEUE_PROVISIONING:
        return _execute_enqueue_provisioning(db, config, context, company_id)
    else:
        raise ValueError(f"Unsupported action type: {step.action_type}")


# Single-writer invariant (doc 16 §5.3/§6.6, MAJOR fix): payment/money state on
# orders is written ONLY by backend-erp's PaymentService. Tenant automations
# must never mutate these via UPDATE_FIELD — the step fails with an explicit
# error instead of silently corrupting billing state. payment_status/order_type
# remain readable in trigger conditions (evaluation uses before/after dicts).
UPDATE_FIELD_DENYLIST: Dict[str, frozenset] = {
    "order": frozenset({"paid", "payment_status", "payment_date", "total", "total_cents"}),
    # Invoices are created/invalidated ONLY by PaymentService (doc 16 §1):
    # automations must not flip validity or rewrite invoice money.
    "invoice": frozenset(
        {"is_valid", "subtotal", "tax", "total",
         "subtotal_cents", "tax_cents", "total_cents"}
    ),
}

# CREATE_ENTITY guards for the same invariant: the engine must never create
# invoices at all, and orders it creates must never be born with payment/money
# state (that is PaymentService's exclusive domain).
CREATE_ENTITY_FORBIDDEN_TYPES: frozenset = frozenset({"invoice"})
CREATE_ENTITY_FIELD_DENYLIST: Dict[str, frozenset] = {
    "order": frozenset({"paid", "payment_status", "payment_date", "total", "total_cents"}),
}


def _execute_update_field(
    db: Session,
    config: dict,
    context: dict,
    company_id: UUID,
) -> dict:
    """Update fields on a target entity."""
    model_map = _get_model_map()
    resource_type = config.get("resource_type")
    if not resource_type or resource_type not in model_map:
        raise ValueError(f"Unknown resource_type: {resource_type}")

    model_class = model_map[resource_type]

    updates = config.get("updates", {})

    denied = sorted(set(updates) & UPDATE_FIELD_DENYLIST.get(resource_type, frozenset()))
    if denied:
        raise ValueError(
            f"UPDATE_FIELD may not write protected field(s) {', '.join(denied)} "
            f"on '{resource_type}': payment/money state has a single writer "
            f"(PaymentService)"
        )

    # Determine which resource(s) to update
    resource_id_source = config.get("resource_id_source", "trigger")

    if resource_id_source == "match_field":
        # Match by relationship: update ALL records where match_field == trigger resource_id
        match_field = config.get("match_field")
        if not match_field:
            raise ValueError("match_field is required when resource_id_source is 'match_field'")

        trigger_resource_id = context["trigger"]["resource_id"]
        if not hasattr(model_class, match_field):
            raise ValueError(f"{resource_type} has no field '{match_field}'")

        entities = db.query(model_class).filter(
            getattr(model_class, match_field) == trigger_resource_id,
            model_class.company_id == company_id,
        ).all()

        updated_ids = []
        updated_fields = []
        for entity in entities:
            for field, value in updates.items():
                if hasattr(entity, field):
                    setattr(entity, field, value)
                    if field not in updated_fields:
                        updated_fields.append(field)
            updated_ids.append(str(entity.id))

        db.flush()
        return {
            "updated_fields": updated_fields,
            "updated_count": len(entities),
            "updated_ids": updated_ids,
            "match_field": match_field,
        }

    else:
        # Single-record mode: trigger or custom resource_id
        if resource_id_source == "trigger":
            resource_id = context["trigger"]["resource_id"]
        else:
            resource_id = config.get("resource_id")

        if not resource_id:
            raise ValueError("No resource_id resolved for UPDATE_FIELD step")

        entity = db.query(model_class).filter(
            model_class.id == resource_id,
            model_class.company_id == company_id,
        ).first()

        if not entity:
            raise ValueError(f"{resource_type} {resource_id} not found")

        updated_fields = []
        for field, value in updates.items():
            if hasattr(entity, field):
                setattr(entity, field, value)
                updated_fields.append(field)

        db.flush()
        return {"updated_fields": updated_fields, "resource_id": str(resource_id)}


def _execute_create_entity(
    db: Session,
    config: dict,
    context: dict,
    company_id: UUID,
) -> dict:
    """Create a new entity."""
    model_map = _get_model_map()
    resource_type = config.get("resource_type")
    if not resource_type or resource_type not in model_map:
        raise ValueError(f"Unknown resource_type: {resource_type}")

    if resource_type in CREATE_ENTITY_FORBIDDEN_TYPES:
        raise ValueError(
            f"CREATE_ENTITY may not create '{resource_type}': invoices are "
            f"created/invalidated only by PaymentService (single-writer invariant)"
        )

    model_class = model_map[resource_type]
    data = dict(config.get("data", {}))

    denied = sorted(set(data) & CREATE_ENTITY_FIELD_DENYLIST.get(resource_type, frozenset()))
    if denied:
        raise ValueError(
            f"CREATE_ENTITY may not set protected field(s) {', '.join(denied)} "
            f"on '{resource_type}': payment/money state has a single writer "
            f"(PaymentService)"
        )

    data["company_id"] = company_id

    entity = model_class(**data)
    db.add(entity)
    db.flush()

    return {"created_resource_type": resource_type, "resource_id": str(entity.id)}


def _execute_enqueue_provisioning(
    db: Session,
    config: dict,
    context: dict,
    company_id: UUID,
) -> dict:
    """
    Insert a durable provisioning_job row (ADR-005). The workflow engine never
    talks to devices — the provisioning worker claims and executes the job.

    action_config format:
    {
      "playbook_id": "uuid",
      "variables": {"onu_serial": "{{trigger.after.serial_number}}"},  # template-enabled
      "client_service_id": "{{trigger.resource_id}}",   # optional target refs
      "network_node_id": null,
      "inventory_item_id": null,
      "integration_id": null,
      "idempotency_key": "install-{{trigger.resource_id}}",  # optional dedupe
      "max_attempts": 3
    }
    """
    from database_utils.models.isp import Playbook, ProvisioningJob, ProvisioningTrigger

    playbook_id = config.get("playbook_id")
    if not playbook_id:
        raise ValueError("ENQUEUE_PROVISIONING step requires 'playbook_id' in action_config")

    playbook = db.query(Playbook).filter(
        Playbook.id == playbook_id,
        Playbook.company_id == company_id,
        Playbook.is_active == True,
    ).first()
    if not playbook:
        raise ValueError(f"Active playbook {playbook_id} not found for company {company_id}")

    resolved = _resolve_template(
        {
            "variables": config.get("variables") or {},
            "client_service_id": config.get("client_service_id"),
            "network_node_id": config.get("network_node_id"),
            "inventory_item_id": config.get("inventory_item_id"),
            "idempotency_key": config.get("idempotency_key"),
        },
        context,
    )

    def _uuid_or_none(value):
        if not value:
            return None
        try:
            return UUID(str(value))
        except (ValueError, TypeError):
            return None

    idempotency_key = resolved.get("idempotency_key") or None
    if idempotency_key:
        # Duplicate enqueue (e.g. a retriggered workflow) is a no-op success.
        # Pre-check instead of catching the unique violation: a mid-workflow
        # rollback would discard this run's execution audit rows. A genuine
        # race still trips uq_provisioning_job_company_idem and fails the step.
        from database_utils.models.isp import ProvisioningJobStatus
        existing = db.query(ProvisioningJob).filter(
            ProvisioningJob.company_id == company_id,
            ProvisioningJob.idempotency_key == idempotency_key,
            ProvisioningJob.status.in_(
                [ProvisioningJobStatus.QUEUED, ProvisioningJobStatus.RUNNING]
            ),
        ).first()
        if existing:
            return {"enqueued": False, "deduped": True,
                    "job_id": str(existing.id), "idempotency_key": idempotency_key}

    # Every target FK must belong to THIS company. action_config is
    # tenant-editable (a crafted step could name another tenant's integration_id
    # to make the worker execute with their stored device credentials), so scope
    # each id to company_id and fail the step if a referenced row isn't ours.
    from database_utils.models.isp import ClientService, NetworkNode, InventoryItem
    from database_utils.models.crm import Integration

    def _owned_or_none(model, value):
        rid = _uuid_or_none(value)
        if rid is None:
            return None
        exists = db.query(model.id).filter(
            model.id == rid, model.company_id == company_id
        ).first()
        if not exists:
            raise ValueError(
                f"{model.__name__} {rid} does not belong to company {company_id}"
            )
        return rid

    job = ProvisioningJob(
        company_id=company_id,
        playbook_id=playbook.id,
        variables=resolved["variables"],
        client_service_id=_owned_or_none(ClientService, resolved.get("client_service_id")),
        network_node_id=_owned_or_none(NetworkNode, resolved.get("network_node_id")),
        inventory_item_id=_owned_or_none(InventoryItem, resolved.get("inventory_item_id")),
        integration_id=_owned_or_none(Integration, config.get("integration_id")),
        idempotency_key=idempotency_key,
        max_attempts=int(config.get("max_attempts", 3)),
        triggered_by=ProvisioningTrigger.WORKFLOW,
    )
    db.add(job)
    db.flush()

    return {"enqueued": True, "job_id": str(job.id), "playbook_id": str(playbook.id)}


def _resolve_template(value: Any, context: dict) -> Any:
    """
    Recursively resolve {{template}} variables in strings, lists, and dicts.

    Supported patterns:
      {{trigger.resource_id}}         — from context["trigger"]["resource_id"]
      {{trigger.after.FIELD}}         — from context["trigger"]["after"][FIELD]
      {{trigger.before.FIELD}}        — from context["trigger"]["before"][FIELD]
      {{steps.STEP_UUID.FIELD}}       — from context[STEP_UUID][FIELD]
    """
    import re
    if isinstance(value, str):
        def replacer(match: re.Match) -> str:
            expr = match.group(1).strip()
            parts = expr.split(".")
            try:
                if parts[0] == "trigger":
                    trigger = context.get("trigger", {})
                    if len(parts) == 2:
                        return str(trigger.get(parts[1], ""))
                    elif len(parts) >= 3 and parts[1] in ("after", "before"):
                        nested = trigger.get(parts[1]) or {}
                        return str(nested.get(parts[2], ""))
                elif parts[0] == "steps" and len(parts) >= 3:
                    step_result = context.get(parts[1], {}) or {}
                    return str(step_result.get(parts[2], ""))
            except Exception:
                pass
            return match.group(0)  # leave unresolved templates as-is
        return re.sub(r"\{\{(.+?)\}\}", replacer, value)
    elif isinstance(value, dict):
        return {k: _resolve_template(v, context) for k, v in value.items()}
    elif isinstance(value, list):
        return [_resolve_template(item, context) for item in value]
    return value


def _execute_http_request(
    db: Session,
    step: WorkflowStep,
    context: dict,
    company_id: UUID,
) -> dict:
    """
    Make an HTTP request to an external API using a registered Integration.

    action_config format:
    {
      "integration_id": "uuid",
      "method": "POST",
      "path": "/configure-router",
      "headers": {"Content-Type": "application/json"},  # optional extra headers
      "body": {"client_id": "{{trigger.resource_id}}"}  # template-enabled JSON body
    }

    Uses httpx.Client (sync) — execute_step is a regular def.
    Lazy-imports both httpx and Integration to avoid hard dependencies in models-utils.
    """
    import httpx  # lazy: httpx is in backend-erp, not models-utils
    from database_utils.models.crm import Integration

    config = step.action_config
    integration_id = config.get("integration_id")
    if not integration_id:
        raise ValueError("HTTP_REQUEST step requires 'integration_id' in action_config")

    integration = db.query(Integration).filter(
        Integration.id == integration_id,
        Integration.company_id == company_id,
    ).first()
    if not integration:
        raise ValueError(f"Integration {integration_id} not found for company {company_id}")

    # Build URL
    path = config.get("path", "")
    url = integration.base_url.rstrip("/") + path

    # SEC-6: block SSRF to internal / cloud-metadata / private addresses BEFORE
    # attaching stored credentials or making any request.
    from database_utils.utils.ssrf import validate_url_no_ssrf, SSRFValidationError
    try:
        validate_url_no_ssrf(url)
    except SSRFValidationError as e:
        raise ValueError(f"HTTP_REQUEST step blocked (SSRF guard): {e}")

    # Build headers: start with configured extra headers, then inject auth
    headers: dict = dict(config.get("headers", {}))
    creds: dict = integration.credentials or {}

    auth_type = integration.auth_type.value
    if auth_type == "API_KEY":
        header_name = creds.get("header_name", "X-API-Key")
        headers[header_name] = creds.get("api_key", "")
    elif auth_type == "BEARER_TOKEN":
        headers["Authorization"] = f"Bearer {creds.get('token', '')}"
    elif auth_type == "BASIC_AUTH":
        import base64
        raw = f"{creds.get('username', '')}:{creds.get('password', '')}"
        encoded = base64.b64encode(raw.encode()).decode()
        headers["Authorization"] = f"Basic {encoded}"
    # NONE: no auth headers added

    # Resolve template variables in the body
    body = _resolve_template(config.get("body"), context)

    method = config.get("method", "POST").upper()

    try:
        with httpx.Client(timeout=30) as client:
            response = client.request(method, url, headers=headers, json=body)
    except httpx.TimeoutException:
        raise ValueError(f"HTTP_REQUEST step timed out after 30s: {method} {url}")
    except httpx.RequestError as e:
        raise ValueError(f"HTTP_REQUEST step network error: {e}")

    return {
        "status_code": response.status_code,
        "response_body": response.text[:10_000],
        "success": response.is_success,
        "url": url,
        "method": method,
    }


def detect_cycle(steps_count: int, edges: List[tuple]) -> bool:
    """
    Detect cycles using Kahn's algorithm (topological sort).
    Returns True if a cycle is detected.
    """
    if steps_count == 0:
        return False

    adj = defaultdict(list)
    in_deg = [0] * steps_count
    for u, v in edges:
        adj[u].append(v)
        in_deg[v] += 1

    queue = deque([i for i in range(steps_count) if in_deg[i] == 0])
    visited = 0
    while queue:
        node = queue.popleft()
        visited += 1
        for neighbor in adj[node]:
            in_deg[neighbor] -= 1
            if in_deg[neighbor] == 0:
                queue.append(neighbor)

    return visited != steps_count
