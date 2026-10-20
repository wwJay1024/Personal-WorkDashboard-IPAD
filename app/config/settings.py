from pathlib import Path

import yaml
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class ReminderConfig(BaseSettings):
    enabled: bool = True
    times: list[str] = ["10:00", "11:00", "15:00", "16:30"]
    weekdays_only: bool = True
    message: str = "该休息一下了"
    break_duration_seconds: int = 300


class ServerConfig(BaseSettings):
    host: str = "0.0.0.0"
    port: int = 8080
    data_dir: Path = Path("data")
    dashboard_config_path: Path = Path("dashboard.json")
    static_dir: Path = Path("static")


class AppConfig(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="DASHBOARD_", extra="ignore")

    server: ServerConfig = Field(default_factory=ServerConfig)
    reminder: ReminderConfig = Field(default_factory=ReminderConfig)

    @classmethod
    def from_yaml(cls, path: str | Path = "config.yaml") -> "AppConfig":
        config_path = Path(path)
        if not config_path.exists():
            return cls()
        with config_path.open("r", encoding="utf-8") as handle:
            loaded = yaml.safe_load(handle) or {}
        return cls(**loaded)
