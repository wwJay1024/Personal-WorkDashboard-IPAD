from datetime import datetime

from pydantic import BaseModel, Field

from app.models.common import new_id, utc_now


class CalendarItem(BaseModel):
    id: str = Field(default_factory=new_id)
    text: str
    date: str  # YYYY-MM-DD
    done: bool = False
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
