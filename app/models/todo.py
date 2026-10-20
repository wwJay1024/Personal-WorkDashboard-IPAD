from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field

from app.models.common import new_id, utc_now


class Priority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class Todo(BaseModel):
    id: str = Field(default_factory=new_id)
    text: str
    priority: Priority = Priority.MEDIUM
    done: bool = False
    due_date: datetime | None = None
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
