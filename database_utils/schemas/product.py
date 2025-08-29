from pydantic import BaseModel
from typing import Optional


class ProductBase(BaseModel):
    name: str
    price: int
    description: str
    stock: int


class ProductCreate(ProductBase):
    pass


class ProductUpdate(BaseModel):
    name: Optional[str] = None
    price: Optional[int] = None
    description: Optional[str] = None
    stock: Optional[int] = None


class ProductOut(ProductBase):
    id: int
    company_id: int

    class ConfigDict:
        from_attributes = True
