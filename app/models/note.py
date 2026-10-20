from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.models.common import new_id, utc_now


class Note(BaseModel):
    id: str = Field(default_factory=new_id)
    content: str
    color: str = "#ffd166"
    position: dict[str, Any] | None = None
    pinned: bool = False
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
