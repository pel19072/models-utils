from pydantic import BaseModel, ConfigDict
from typing import Optional
from uuid import UUID


class ProductBase(BaseModel):
    name: str
    price: float
    description: str
    stock: int


class ProductCreate(ProductBase):
    pass


class ProductUpdate(BaseModel):
    name: Optional[str] = None
    price: Optional[float] = None
    description: Optional[str] = None
    stock: Optional[int] = None


class ProductOut(ProductBase):
    id: UUID
    company_id: UUID

    model_config = ConfigDict(from_attributes=True)
