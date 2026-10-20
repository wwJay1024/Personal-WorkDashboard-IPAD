from datetime import datetime, timezone

import httpx
from loguru import logger

from app.config.settings import BalanceConfig, BalanceProviderConfig
from app.models.balance import BalanceData
from app.services.cookie_refresher import CookieRefresher


class BalanceService:
    def __init__(self, config: BalanceConfig, cookie_refresher: CookieRefresher | None = None) -> None:
        self.config = config
        self.cache: dict[str, BalanceData] = {}
        self.cookie_refresher = cookie_refresher
        self.last_fetch_time: datetime | None = None

    async def _fetch_mimo(self, provider: BalanceProviderConfig) -> BalanceData:
        headers = {
            "Cookie": provider.cookie or "",
            "User-Agent": "cc-switch/1.0",
            "Accept": "application/json",
        }
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(provider.endpoint, headers=headers)

        # 检测 401 错误并尝试刷新 cookie
        if resp.status_code == 401 and self.cookie_refresher:
            logger.warning("MiMo cookie expired, attempting refresh...")
            new_cookie = await self.cookie_refresher.refresh_mimo_cookie()
            if new_cookie:
                headers["Cookie"] = new_cookie
                async with httpx.AsyncClient(timeout=10.0) as client:
                    resp = await client.get(provider.endpoint, headers=headers)
            else:
                logger.error("Cookie refresh failed")

        resp.raise_for_status()
        data = resp.json()

        items = data.get("data", {}).get("usage", {}).get("items", [])
        percent = data.get("data", {}).get("usage", {}).get("percent", 0)
        item = next((i for i in items if i.get("name") == "plan_total_token"), None)

        used_raw = item.get("used", 0) if item else 0
        limit_raw = item.get("limit", 0) if item else 0
        to_yi = lambda v: round(v / 1_0000_0000, 2)

        return BalanceData(
            provider="mimo",
            label=provider.name,
            balance=to_yi(limit_raw - used_raw),
            used=to_yi(used_raw),
            limit=to_yi(limit_raw),
            currency=provider.unit,
            status="ok",
            message=f"{round(percent * 100, 1)}% 已用",
            last_updated=datetime.now(timezone.utc),
        )

    async def _fetch_deepseek(self, provider: BalanceProviderConfig) -> BalanceData:
        headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {provider.api_key}",
        }
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(provider.endpoint, headers=headers)
        resp.raise_for_status()
        data = resp.json()

        infos = data.get("balance_infos", [])
        info = infos[0] if infos else {}
        total = float(info.get("total_balance", 0))

        return BalanceData(
            provider="deepseek",
            label=provider.name,
            balance=total,
            currency=provider.unit,
            status="ok",
            last_updated=datetime.now(timezone.utc),
        )

    async def _fetch_api_key(self, provider: BalanceProviderConfig) -> BalanceData:
        headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {provider.api_key}",
        }
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(provider.endpoint, headers=headers)
        resp.raise_for_status()
        data = resp.json()

        balance = (
            data.get("balance")
            or data.get("remaining")
            or data.get("data", {}).get("balance")
            or data.get("data", {}).get("remaining")
            or 0
        )
        return BalanceData(
            provider=provider.name.lower(),
            label=provider.name,
            balance=float(balance),
            currency=provider.unit,
            status="ok",
            last_updated=datetime.now(timezone.utc),
        )

    async def _fetch_provider(self, provider: BalanceProviderConfig) -> BalanceData:
        fetchers = {
            "mimo": self._fetch_mimo,
            "deepseek": self._fetch_deepseek,
            "api_key": self._fetch_api_key,
        }
        fetcher = fetchers.get(provider.type)
        if not fetcher:
            return BalanceData(
                provider=provider.name.lower(),
                label=provider.name,
                status="error",
                message=f"未知类型: {provider.type}",
                last_updated=datetime.now(timezone.utc),
            )

        key = provider.name.lower()
        try:
            data = await fetcher(provider)
            self.cache[key] = data
            return data
        except Exception as exc:
            logger.error("balance fetch failed for {}: {}", provider.name, exc)
            previous = self.cache.get(key)
            if previous:
                previous.status = "stale"
                previous.message = "接口失败，显示缓存"
                return previous
            data = BalanceData(
                provider=key,
                label=provider.name,
                status="error",
                message=str(exc),
                last_updated=datetime.now(timezone.utc),
            )
            self.cache[key] = data
            return data

    async def fetch_all_balances(self) -> dict[str, BalanceData]:
        now = datetime.now(timezone.utc)
        if self.last_fetch_time and (now - self.last_fetch_time).total_seconds() < 300:
            logger.debug("balance cache still fresh, skipping fetch")
            return self.cache
        self.last_fetch_time = now

        for provider in self.config.providers:
            await self._fetch_provider(provider)
        return self.cache

    def get_cached(self) -> dict[str, BalanceData]:
        return self.cache
