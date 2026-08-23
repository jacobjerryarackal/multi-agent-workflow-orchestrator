"""Common generic schemas for pagination and standard responses."""

from typing import Generic, List, TypeVar
from pydantic import BaseModel, Field

T = TypeVar("T")


class PaginatedResponse(BaseModel, Generic[T]):
    """Standard generic envelope for paginated resource lists."""
    items: List[T]
    total_count: int
    page: int = Field(ge=1, description="1-indexed current page number")
    page_size: int = Field(ge=1, description="Number of items per page")
    has_more: bool
