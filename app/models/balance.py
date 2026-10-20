from datetime import datetime

from pydantic import BaseModel, Field

from app.models.common import new_id, utc_now


class BalanceData(BaseModel):
    provider: str
    label: str | None = None
    balance: float | None = None
    used: float | None = None
    limit: float | None = None
    currency: str = "USD"
    status: str = "unknown"
    message: str | None = None
    last_updated: datetime = Field(default_factory=utc_now)


class BalanceCache(BaseModel):
    id: str = Field(default_factory=new_id)
    provider: str
    label: str | None = None
    balance: float | None = None
    used: float | None = None
    limit: float | None = None
    currency: str = "USD"
    status: str = "unknown"
    message: str | None = None
    last_updated: datetime = Field(default_factory=utc_now)
