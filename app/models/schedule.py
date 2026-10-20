from datetime import datetime

from pydantic import BaseModel, Field

from app.models.common import new_id, utc_now


class Event(BaseModel):
    id: str = Field(default_factory=new_id)
    title: str
    start_time: datetime
    end_time: datetime | None = None
    location: str | None = None
    notes: str | None = None
    all_day: bool = False
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
