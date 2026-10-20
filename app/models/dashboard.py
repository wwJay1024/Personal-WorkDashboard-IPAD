from pydantic import BaseModel, Field


class DashboardComponent(BaseModel):
    id: str
    type: str
    title: str
    size: str = "medium"
    enabled: bool = True
    data_type: str | None = None
    options: dict = Field(default_factory=dict)


class DashboardConfig(BaseModel):
    version: str = "1.0"
    title: str = "iPad 数据看板"
    subtitle: str = "Mac 本地同步"
    theme: str = "warm-ink"
    components: list[DashboardComponent] = Field(default_factory=list)
