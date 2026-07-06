# schemas/service_plan.py
"""
Cycle 2 D1/D2/D5: ServicePlan absorbs Product (kind/stock) and gains
default_topology_id (D5, pre-fills a new service's topology). `migration_source`
is a dedicated marker column (doc 18 amendment 1/2) and is NEVER exposed on
any schema here — it is internal audit state, not user-editable data.
"""
from pydantic import BaseModel, ConfigDict
from typing import Optional, Dict, Any
from uuid import UUID
from datetime import datetime

from database_utils.models.isp import ServicePlanType, CatalogKind


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
    # Cycle 2 D1/D2: what this plan bills for (drives Order.order_type
    # derivation). Absorbed-from-Product: stock (NULL = not stock-tracked).
    kind: CatalogKind = CatalogKind.SERVICE
    stock: Optional[int] = None
    # D5: pre-fills a new client_service's topology_id on create.
    default_topology_id: Optional[UUID] = None


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
    kind: Optional[CatalogKind] = None
    stock: Optional[int] = None
    default_topology_id: Optional[UUID] = None


class ServicePlanOut(ServicePlanBase):
    id: UUID
    company_id: UUID
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
