"""
Pagination schemas for consistent paginated responses across the application.
"""
from typing import Generic, TypeVar, List
from pydantic import BaseModel, Field

# Generic type for the data model
T = TypeVar('T')


class PaginationParams(BaseModel):
    """Query parameters for pagination."""
    page: int = Field(default=1, ge=1, description="Page number (starting from 1)")
    page_size: int = Field(default=10, ge=1, le=100, description="Number of items per page")


class PaginatedResponse(BaseModel, Generic[T]):
    """Generic paginated response model."""
    items: List[T] = Field(description="List of items for the current page")
    total: int = Field(description="Total number of items across all pages")
    page: int = Field(description="Current page number")
    page_size: int = Field(description="Number of items per page")
    total_pages: int = Field(description="Total number of pages")

    model_config = {
        "from_attributes": True
    }
