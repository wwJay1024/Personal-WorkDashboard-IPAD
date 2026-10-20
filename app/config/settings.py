from pathlib import Path

import yaml
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class BalanceProviderConfig(BaseSettings):
    name: str
    type: str = "api_key"  # mimo | deepseek | api_key
    endpoint: str = ""
    api_key: str | None = None
    cookie: str | None = None
    username: str | None = None
    password: str | None = None
    unit: str = "$"


class BalanceConfig(BaseSettings):
    update_interval_minutes: int = 15
    alert_threshold: float = 5.0
    providers: list[BalanceProviderConfig] = []


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
    balance: BalanceConfig = Field(default_factory=BalanceConfig)
    reminder: ReminderConfig = Field(default_factory=ReminderConfig)

    _config_path: Path = Path("config.yaml")

    @classmethod
    def from_yaml(cls, path: str | Path = "config.yaml") -> "AppConfig":
        config_path = Path(path)
        if not config_path.exists():
            return cls()
        with config_path.open("r", encoding="utf-8") as handle:
            loaded = yaml.safe_load(handle) or {}
        config = cls(**loaded)
        config._config_path = config_path
        return config

    def update_provider_cookie(self, provider_name: str, new_cookie: str):
        """更新指定 provider 的 cookie 并写回 config.yaml"""
        for provider in self.balance.providers:
            if provider.name.lower() == provider_name.lower():
                provider.cookie = new_cookie
                break
        self._save_to_yaml()

    def _save_to_yaml(self):
        """将当前配置写回 config.yaml"""
        config_data = {
            "server": {
                "host": self.server.host,
                "port": self.server.port,
                "data_dir": str(self.server.data_dir),
                "dashboard_config_path": str(self.server.dashboard_config_path),
                "static_dir": str(self.server.static_dir),
            },
            "balance": {
                "update_interval_minutes": self.balance.update_interval_minutes,
                "providers": [
                    {
                        "name": p.name,
                        "type": p.type,
                        "endpoint": p.endpoint,
                        "api_key": p.api_key,
                        "cookie": p.cookie,
                        "username": p.username,
                        "password": p.password,
                        "unit": p.unit,
                    }
                    for p in self.balance.providers
                ],
            },
            "reminder": {
                "enabled": self.reminder.enabled,
                "times": self.reminder.times,
                "weekdays_only": self.reminder.weekdays_only,
                "message": self.reminder.message,
                "break_duration_seconds": self.reminder.break_duration_seconds,
            },
        }
        with open(self._config_path, "w", encoding="utf-8") as f:
            yaml.dump(config_data, f, allow_unicode=True, default_flow_style=False)
