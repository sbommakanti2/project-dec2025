"""Pydantic schemas used for request validation and response serialization."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class ItemBase(BaseModel):
    """Shared attributes between create/read operations."""

    name: str
    description: Optional[str] = None


class ItemCreate(ItemBase):
    """Payload for POST /items."""


class ItemUpdate(BaseModel):
    """PATCH-style payload for PUT /items/{id}."""

    name: Optional[str] = None
    description: Optional[str] = None


class ItemRead(ItemBase):
    """Response shape returned to clients."""

    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True
