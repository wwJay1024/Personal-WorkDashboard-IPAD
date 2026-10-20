import asyncio
from pathlib import Path

import yaml
from loguru import logger
from playwright.async_api import async_playwright


class CookieRefresher:

    def __init__(self, config_path: str = "config.yaml", data_dir: str = "data"):
        self.config_path = Path(config_path)
        self.state_dir = Path(data_dir) / "browser_state"
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self._lock = asyncio.Lock()

    def _state_file(self) -> Path:
        return self.state_dir / "mimo_state.json"

    async def refresh_mimo_cookie(self) -> str | None:
        """自动刷新 cookie：用保存的登录态访问页面，从浏览器上下文获取 cookie"""
        async with self._lock:
            playwright = None
            browser = None

            try:
                playwright = await async_playwright().start()

                state_file = self._state_file()
                use_state = state_file.exists()

                browser = await playwright.chromium.launch(
                    headless=use_state,
                    channel="chrome",
                )
                context = await browser.new_context(
                    storage_state=str(state_file) if use_state else None,
                    user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36",
                )
                page = await context.new_page()

                await page.goto(
                    "https://platform.xiaomimimo.com/console/plan-manage",
                    wait_until="networkidle",
                    timeout=60000,
                )

                # 检查是否需要登录
                if "login" in page.url or "passport" in page.url:
                    if use_state:
                        logger.info("Login state expired, need re-login")
                        return None

                    print("请在浏览器中登录 MiMo 平台...")
                    await page.wait_for_url("**/console/plan-manage**", timeout=300000)
                    await page.wait_for_load_state("networkidle")
                    await asyncio.sleep(3)

                    await page.reload(wait_until="networkidle")
                    await asyncio.sleep(3)

                    await context.storage_state(path=str(state_file))
                    logger.info("Login state saved")

                # 从浏览器上下文获取 cookie（包括 HttpOnly 的 serviceToken）
                all_cookies = await context.cookies()
                target = {"api-platform_serviceToken", "userId", "api-platform_slh", "api-platform_ph"}
                cookie_map = {}
                for c in all_cookies:
                    if c["name"] in target:
                        cookie_map[c["name"]] = c["value"].strip('"')

                if cookie_map:
                    cookie_str = "; ".join(f'{k}="{v}"' for k, v in cookie_map.items())
                    self._save_cookie(cookie_str)
                    logger.info("Cookie refreshed from context: {}...", cookie_str[:80])
                    return cookie_str

                # 备选：从 document.cookie 获取
                doc = await page.evaluate("document.cookie")
                cookie_str = self._extract_from_doc_cookie(doc)

                if cookie_str:
                    self._save_cookie(cookie_str)
                    logger.info("Cookie refreshed from document: {}...", cookie_str[:80])
                    return cookie_str

                logger.error("Failed to capture cookie from any source")
                return None

            except Exception as e:
                logger.error("Cookie refresh failed: {}", e)
                return None
            finally:
                if browser:
                    await browser.close()
                if playwright:
                    await playwright.stop()

    def _parse_cookie_header(self, cookie_header: str) -> str:
        """解析 Cookie 请求头，提取需要的字段"""
        target = {"api-platform_serviceToken", "userId", "api-platform_slh", "api-platform_ph"}
        parts = cookie_header.split("; ")
        result = []
        for part in parts:
            part = part.strip()
            if "=" in part:
                name, value = part.split("=", 1)
                value = value.strip().strip('"')
                if name in target:
                    result.append(f'{name}="{value}"')
        return "; ".join(result)

    def _extract_from_doc_cookie(self, doc_cookies: str) -> str:
        """从 document.cookie 提取"""
        if not doc_cookies:
            return ""
        target = {"api-platform_serviceToken", "userId", "api-platform_slh", "api-platform_ph"}
        parts = doc_cookies.split("; ")
        result = []
        for part in parts:
            if "=" in part:
                name, value = part.split("=", 1)
                value = value.strip().strip('"')
                if name in target:
                    result.append(f'{name}="{value}"')
        return "; ".join(result)

    def _save_cookie(self, cookie_str: str):
        config = self._load_config()
        for provider in config.get("balance", {}).get("providers", []):
            if provider.get("type") == "mimo":
                provider["cookie"] = cookie_str
                break
        with open(self.config_path, "w", encoding="utf-8") as f:
            yaml.dump(config, f, allow_unicode=True, default_flow_style=False)

    def _load_config(self) -> dict:
        if self.config_path.exists():
            with open(self.config_path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
        return {}

    async def close(self):
        pass
