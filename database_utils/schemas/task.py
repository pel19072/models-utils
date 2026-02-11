from pydantic import BaseModel
from typing import Optional, List
from uuid import UUID
from datetime import datetime


class TaskAssigneeSimple(BaseModel):
    id: UUID
    name: str
    email: str

    class ConfigDict:
        from_attributes = True


class TaskBase(BaseModel):
    name: str
    description: Optional[str] = None
    due_date: Optional[datetime] = None


class TaskCreate(TaskBase):
    task_state_id: UUID
    assignee_ids: Optional[List[UUID]] = []
    position: Optional[int] = None


class TaskUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    due_date: Optional[datetime] = None
    task_state_id: Optional[UUID] = None
    assignee_ids: Optional[List[UUID]] = None
    position: Optional[int] = None


class TaskOut(TaskBase):
    id: UUID
    company_id: UUID
    task_state_id: UUID
    position: int
    created_by: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime
    assignees: List[TaskAssigneeSimple] = []
    creator: Optional[TaskAssigneeSimple] = None

    class ConfigDict:
        from_attributes = True


class TaskMove(BaseModel):
    task_state_id: UUID
    position: int


class TaskBulkReorder(BaseModel):
    task_state_id: UUID
    ordered_task_ids: List[UUID]
