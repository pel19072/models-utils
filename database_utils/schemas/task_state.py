from pydantic import BaseModel, ConfigDict
from typing import Optional, List
from uuid import UUID
from datetime import datetime
from enum import Enum


class TaskStateColor(str, Enum):
    GRAY = "GRAY"
    RED = "RED"
    ORANGE = "ORANGE"
    YELLOW = "YELLOW"
    GREEN = "GREEN"
    BLUE = "BLUE"
    PURPLE = "PURPLE"
    PINK = "PINK"


class TaskStateBase(BaseModel):
    name: str
    color: TaskStateColor = TaskStateColor.GRAY
    position: int = 0


class TaskStateCreate(TaskStateBase):
    pass


class TaskStateUpdate(BaseModel):
    name: Optional[str] = None
    color: Optional[TaskStateColor] = None
    position: Optional[int] = None


class TaskStateOut(TaskStateBase):
    id: UUID
    company_id: UUID
    created_at: datetime
    updated_at: datetime
    task_count: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)


class TaskStateReorder(BaseModel):
    ordered_ids: List[UUID]
