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
        _MODEL_MAP = {
            "order": Order,
            "client": Client,
            "product": Product,
            "task": Task,
            "task_state": TaskState,
            "recurring_order": RecurringOrder,
            "invoice": Invoice,
            "order_item": OrderItem,
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
            asyncio.create_task(
                _execute_workflow_async(
                    workflow_id=workflow.id,
                    trigger_event=trigger_event,
                    company_id=company_id,
                    depth=depth,
                )
            )

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

    matched = []
    for workflow in workflows:
        for trigger in workflow.triggers:
            if (
                trigger.resource_type == resource_type
                and trigger.event_type.value == event_type
                and _matches_field_conditions(trigger.field_conditions, before_data, after_data)
            ):
                matched.append(workflow)
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

    if operator == "changed":
        if before_data and after_data:
            return str(before_data.get(field)) != str(after_data.get(field))
        return True

    elif operator == "changed_to":
        if after_data:
            return str(after_data.get(field)) == str(value)
        return False

    elif operator == "changed_from":
        if before_data:
            return str(before_data.get(field)) == str(value)
        return False

    elif operator == "equals":
        if after_data:
            return str(after_data.get(field)) == str(value)
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

    try:
        while queue:
            step_id = queue.popleft()
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
    config = step.action_config

    if step.action_type == StepActionType.UPDATE_FIELD:
        return _execute_update_field(db, config, context, company_id)
    elif step.action_type == StepActionType.CREATE_ENTITY:
        return _execute_create_entity(db, config, context, company_id)
    else:
        raise ValueError(f"Unsupported action type: {step.action_type}")


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

    model_class = model_map[resource_type]
    data = dict(config.get("data", {}))
    data["company_id"] = company_id

    entity = model_class(**data)
    db.add(entity)
    db.flush()

    return {"created_resource_type": resource_type, "resource_id": str(entity.id)}


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
