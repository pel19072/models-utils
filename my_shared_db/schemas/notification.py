from pydantic import BaseModel
from typing import Optional
from enum import Enum

from schemas.user import UserCreate, UserOut

class NotificationStatus(str, Enum):
    PENDING = "PENDING"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"


class NotificationBase(UserCreate):
    pass


class NotificationCreate(NotificationBase):
    pass


class NotificationOut(UserOut):
    id: int
    status: NotificationStatus
    user_id: Optional[int]

    class Config:
        orm_mode = True


class NotificationUpdate(BaseModel):
    status: NotificationStatus
