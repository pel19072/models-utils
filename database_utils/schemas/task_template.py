from pydantic import BaseModel, ConfigDict
from typing import Optional, List
from uuid import UUID
from datetime import datetime

from .task import TaskAssigneeSimple, TaskLinkedObjectType


class TaskTemplateBase(BaseModel):
    name: str
    task_name: str
    description: Optional[str] = None
    due_date_offset_days: Optional[int] = None
    default_assignee_ids: Optional[List[UUID]] = None
    linked_object_type: Optional[TaskLinkedObjectType] = None


class TaskTemplateCreate(TaskTemplateBase):
    pass


class TaskTemplateUpdate(BaseModel):
    name: Optional[str] = None
    task_name: Optional[str] = None
    description: Optional[str] = None
    due_date_offset_days: Optional[int] = None
    default_assignee_ids: Optional[List[UUID]] = None
    linked_object_type: Optional[TaskLinkedObjectType] = None


class TaskTemplateOut(TaskTemplateBase):
    id: UUID
    company_id: UUID
    created_by: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime
    creator: Optional[TaskAssigneeSimple] = None

    model_config = ConfigDict(from_attributes=True)
