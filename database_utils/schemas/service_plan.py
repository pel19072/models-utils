# schemas/service_plan.py
from pydantic import BaseModel, ConfigDict
from typing import Optional, Dict, Any
from uuid import UUID
from datetime import datetime

from database_utils.models.isp import ServicePlanType


class ServicePlanBase(BaseModel):
    name: str
    description: Optional[str] = None
    plan_type: ServicePlanType = ServicePlanType.FIBER
    download_mbps: Optional[int] = None
    upload_mbps: Optional[int] = None
    data_cap_gb: Optional[int] = None
    price: float = 0.0
    is_active: bool = True
    provisioning_params: Optional[Dict[str, Any]] = None
    product_id: Optional[UUID] = None


class ServicePlanCreate(ServicePlanBase):
    pass


class ServicePlanUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    plan_type: Optional[ServicePlanType] = None
    download_mbps: Optional[int] = None
    upload_mbps: Optional[int] = None
    data_cap_gb: Optional[int] = None
    price: Optional[float] = None
    is_active: Optional[bool] = None
    provisioning_params: Optional[Dict[str, Any]] = None
    product_id: Optional[UUID] = None


class ServicePlanOut(ServicePlanBase):
    id: UUID
    company_id: UUID
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
