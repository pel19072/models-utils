# Workflow Models

## Description
SQLAlchemy ORM models for the business automation workflow engine: workflows, triggers, steps, edges, and execution history.

## Goal
Store workflow definitions and execution state for the automation engine used by backend-erp.

## Models (in `database_utils/models/workflow.py`)

| Model | Key Fields | Purpose |
|-------|-----------|---------|
| `Workflow` | name, is_active, company_id | Automation definition |
| `WorkflowTrigger` | resource_type, event_type (CREATED/UPDATED/DELETED), field_conditions (JSON), workflow_id | Event trigger |
| `WorkflowStep` | name, action_type (UPDATE_FIELD/CREATE_ENTITY/HTTP_REQUEST), action_config (JSON), position_x, position_y, workflow_id | Action to perform |
| `WorkflowStepEdge` | source_step_id, target_step_id, workflow_id | Step connection in graph |
| `WorkflowExecution` | status (PENDING/RUNNING/COMPLETED/FAILED/SKIPPED), trigger_object_id, triggered_by_user_id, started_at, completed_at, workflow_id | Execution instance |
| `WorkflowStepExecution` | status, started_at, completed_at, error_message, output (JSON), workflow_execution_id, step_id | Per-step result |

## Connections to Other Components
- **backend-erp** `utils/workflow_engine.py`: Reads these models to evaluate triggers and execute steps
- **CRM models**: Triggers fire on CRM entity events (resource_type maps to CRM model names)
- **Integrations** (`Integration` model): HTTP_REQUEST steps reference integration credentials
- **Workflow schemas** (`schemas/workflow.py`): Pydantic representations

## Key Implementation Details
- `field_conditions` JSON: per-field value conditions for trigger matching (e.g., `{"status": "CANCELLED"}`)
- `action_config` JSON: step-specific configuration (field name+value for UPDATE_FIELD, entity type+data for CREATE_ENTITY, url+method for HTTP_REQUEST)
- Step graph: steps form a DAG connected by edges; execution follows topological order
- Execution status lifecycle: PENDING → RUNNING → COMPLETED/FAILED; SKIPPED if trigger conditions not met
- `trigger_object_id`: UUID of the CRM entity that triggered the workflow
- Execution history retained for debugging; no automatic purge

## Environment Variables
- `POSTGRES_*` — Database connection string components
