from pydantic import BaseModel, ConfigDict
from typing import Optional
from enum import Enum
from uuid import UUID

from .user import UserCreate, UserOut

class NotificationStatus(str, Enum):
    PENDING = "PENDING"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"


class NotificationBase(UserCreate):
    pass


class NotificationCreate(NotificationBase):
    pass


class NotificationOut(UserOut):
    id: UUID
    status: NotificationStatus
    user_id: Optional[UUID]

    model_config = ConfigDict(from_attributes=True)


class NotificationUpdate(BaseModel):
    status: NotificationStatus
