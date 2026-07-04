# schemas/client_service.py
from pydantic import BaseModel, ConfigDict
from typing import Optional, Dict, Any
from uuid import UUID
from datetime import datetime

from database_utils.models.isp import ClientServiceStatus, SuspensionReason
from .service_plan import ServicePlanOut


class ClientServiceBase(BaseModel):
    client_id: UUID
    service_plan_id: UUID
    network_node_id: Optional[UUID] = None
    connection_params: Optional[Dict[str, Any]] = None
    notes: Optional[str] = None


class ClientServiceCreate(ClientServiceBase):
    # When true the backend creates/links a recurring order from the plan's product.
    create_recurring_order: bool = False


class ClientServiceUpdate(BaseModel):
    status: Optional[ClientServiceStatus] = None
    service_plan_id: Optional[UUID] = None
    network_node_id: Optional[UUID] = None
    recurring_order_id: Optional[UUID] = None
    activation_date: Optional[datetime] = None
    connection_params: Optional[Dict[str, Any]] = None
    notes: Optional[str] = None


class ClientServiceOut(ClientServiceBase):
    id: UUID
    company_id: UUID
    status: ClientServiceStatus
    activation_date: Optional[datetime] = None
    cancelled_at: Optional[datetime] = None
    recurring_order_id: Optional[UUID] = None
    created_at: datetime
    service_plan: Optional[ServicePlanOut] = None

    model_config = ConfigDict(from_attributes=True)


class ServiceSuspensionCreate(BaseModel):
    reason: SuspensionReason = SuspensionReason.OTHER
    note: Optional[str] = None


class ServiceSuspensionOut(BaseModel):
    id: UUID
    company_id: UUID
    client_service_id: UUID
    suspended_at: datetime
    reactivated_at: Optional[datetime] = None
    reason: SuspensionReason
    note: Optional[str] = None
    created_by: Optional[UUID] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
