import asyncio
import json
from datetime import datetime, timezone

import aiofiles
from fastapi import APIRouter, Request

from app.models.dashboard import DashboardConfig

router = APIRouter(tags=["system"])


async def read_dashboard_config(path) -> dict:
    if not path.exists():
        return DashboardConfig().model_dump(mode="json")
    async with aiofiles.open(path, "r", encoding="utf-8") as handle:
        content = await handle.read()
    return DashboardConfig.model_validate(json.loads(content)).model_dump(mode="json")


@router.get("/api/config/dashboard")
async def get_dashboard_config(request: Request):
    return await read_dashboard_config(request.app.state.config.server.dashboard_config_path)


@router.get("/api/balances")
async def get_balances(request: Request):
    cache = request.app.state.balance_service.get_cached()
    return {key: value.model_dump(mode="json") for key, value in cache.items()}


@router.post("/api/refresh/{service_name}")
async def refresh_service(service_name: str, request: Request):
    if service_name == "balances":
        await request.app.state.refresh_balances()
        return {"status": "ok"}
    return {"status": "unknown_service", "service": service_name}


@router.post("/api/login/mimo")
async def mimo_login(request: Request):
    """打开浏览器让用户手动登录 MiMo 平台"""
    cookie_refresher = request.app.state.cookie_refresher
    if not cookie_refresher:
        return {"status": "error", "message": "Cookie refresher not available"}

    try:
        state_file = await cookie_refresher.open_login_page()
        if state_file:
            # 重新加载余额数据
            await request.app.state.refresh_balances()
            return {"status": "ok", "message": "Login successful, cookie updated"}
        else:
            return {"status": "error", "message": "Login failed or timed out"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@router.get("/api/bootstrap")
async def bootstrap(request: Request):
    """返回全部初始数据，减少前端并发请求数"""
    data_service = request.app.state.data_service
    tasks = [data_service.read_all(dt) for dt in data_service.list_types()]
    results = await asyncio.gather(*tasks)
    data = dict(zip(data_service.list_types(), results))
    return {
        "config": await read_dashboard_config(request.app.state.config.server.dashboard_config_path),
        "data": data,
        "balances": {k: v.model_dump(mode="json") for k, v in request.app.state.balance_service.get_cached().items()},
        "sitting": request.app.state.sitting_service.get_state().model_dump(mode="json"),
    }


@router.get("/health")
async def health_check(request: Request):
    watcher = request.app.state.file_watcher
    scheduler = request.app.state.scheduler_service
    return {
        "status": "healthy" if watcher.observer.is_alive() and scheduler.scheduler.running else "degraded",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "details": {
            "websocket_connections": len(request.app.state.ws_manager.active_connections),
            "file_watcher": watcher.observer.is_alive(),
            "scheduler": scheduler.scheduler.running,
            "balance_sources": list(request.app.state.balance_service.get_cached().keys()),
        },
    }
