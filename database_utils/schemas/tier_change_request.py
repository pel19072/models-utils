from pydantic import BaseModel, ConfigDict
from typing import Optional
from datetime import datetime
from uuid import UUID


class _TierSummary(BaseModel):
    id: UUID
    name: str
    model_config = ConfigDict(from_attributes=True)


class _UserSummary(BaseModel):
    id: UUID
    name: str
    email: str
    model_config = ConfigDict(from_attributes=True)


class _CompanySummary(BaseModel):
    id: UUID
    name: str
    model_config = ConfigDict(from_attributes=True)


class TierChangeRequestCreate(BaseModel):
    """Used by company admins to submit a tier change request."""
    requested_tier_id: UUID
    reason: Optional[str] = None


class TierChangeRequestReview(BaseModel):
    """Used by superadmins to approve or reject a request."""
    status: str  # APPROVED or REJECTED
    note: Optional[str] = None


class TierChangeRequestOut(BaseModel):
    id: UUID
    created_at: datetime
    company_id: UUID
    requested_by_user_id: UUID
    current_tier_id: UUID
    requested_tier_id: UUID
    reason: Optional[str]
    status: str
    reviewed_by_user_id: Optional[UUID]
    reviewed_at: Optional[datetime]
    note: Optional[str]

    # Nested relationship objects
    company: Optional[_CompanySummary] = None
    requested_by: Optional[_UserSummary] = None
    current_tier: Optional[_TierSummary] = None
    requested_tier: Optional[_TierSummary] = None

    model_config = ConfigDict(from_attributes=True)
