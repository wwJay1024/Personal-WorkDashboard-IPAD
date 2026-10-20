#!/usr/bin/env python3
"""首次登录 MiMo —— 打开浏览器，手动登录后自动保存状态和 cookie"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.cookie_refresher import CookieRefresher


async def main():
    refresher = CookieRefresher(config_path="config.yaml", data_dir="data")

    print("正在打开浏览器...")
    print("请在浏览器中登录 MiMo 平台，登录成功后将自动保存。")

    cookie = await refresher.refresh_mimo_cookie()

    if cookie:
        print("Cookie 已自动保存，重启服务后生效")
    else:
        print("获取失败，请确认已登录成功")
        sys.exit(1)

    await refresher.close()


if __name__ == "__main__":
    asyncio.run(main())
