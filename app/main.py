import asyncio
import json
import time
from contextlib import asynccontextmanager
from pathlib import Path

import aiofiles
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from loguru import logger

from app.api.routes_data import router as data_router
from app.api.routes_sitting import router as sitting_router
from app.api.routes_system import read_dashboard_config, router as system_router
from app.config import AppConfig
from app.models import CalendarItem, Note
from app.services.data_service import DataService
from app.services.file_watcher import DataFileHandler, FileWatcherService
from app.services.reminder_service import ReminderService
from app.services.scheduler import SchedulerService
from app.services.sitting_service import SittingService
from app.services.ws_manager import WSManager


def build_app() -> FastAPI:
    config = AppConfig.from_yaml()
    data_service = DataService()
    ws_manager = WSManager()
    sitting_service = SittingService(ws_manager.broadcast, data_dir=str(config.server.data_dir))
    scheduler_service = SchedulerService()

    async def push_data_update(data_type: str) -> None:
        records = await data_service.read_all(data_type)
        await ws_manager.broadcast({"type": "data_update", "data_type": data_type, "data": records})

    async def push_config_update() -> None:
        dashboard = await read_dashboard_config(config.server.dashboard_config_path)
        await ws_manager.broadcast({"type": "config_update", "data": dashboard})

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        logger.info("dashboard service starting")
        config.server.data_dir.mkdir(parents=True, exist_ok=True)
        config.server.static_dir.mkdir(parents=True, exist_ok=True)
        await ensure_dashboard_config(config.server.dashboard_config_path)

        data_service.register("notes", config.server.data_dir / "notes.json", Note)
        data_service.register("calendar", config.server.data_dir / "calendar.json", CalendarItem)

        loop = asyncio.get_running_loop()
        file_handler = DataFileHandler(
            loop=loop,
            data_service=data_service,
            dashboard_config_path=config.server.dashboard_config_path,
            push_data_update=push_data_update,
            push_config_update=push_config_update,
        )
        file_watcher = FileWatcherService(config.server.data_dir, config.server.dashboard_config_path, file_handler)
        reminder_service = ReminderService(
            config.reminder.times,
            config.reminder.message,
            config.reminder.break_duration_seconds,
            ws_manager.broadcast,
            config.reminder.weekdays_only,
        )

        app.state.config = config
        app.state.data_service = data_service
        app.state.ws_manager = ws_manager
        app.state.scheduler_service = scheduler_service
        app.state.file_watcher = file_watcher
        app.state.sitting_service = sitting_service
        app.state.push_data_update = push_data_update
        app.state.push_config_update = push_config_update

        file_watcher.start()
        scheduler_service.add_cron_job(sitting_service.stop_sitting, "sitting_auto_stop", hour=11, minute=45)
        scheduler_service.start()
        if config.reminder.enabled:
            reminder_service.start()

        sitting_service.start()

        logger.info("dashboard service ready")
        yield

        logger.info("dashboard service stopping")
        await sitting_service.stop()
        await reminder_service.stop()
        file_watcher.stop()
        scheduler_service.shutdown()

    app = FastAPI(title="iPad Dashboard", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def add_cache_headers(request: Request, call_next):
        response = await call_next(request)
        content_type = response.headers.get("content-type", "")
        if "text/html" in content_type:
            response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
        return response
    app.include_router(data_router)
    app.include_router(sitting_router)
    app.include_router(system_router)

    @app.websocket("/ws")
    async def websocket_endpoint(websocket: WebSocket):
        await ws_manager.connect(websocket)
        try:
            await ws_manager.send_personal(
                {
                    "type": "hello",
                    "data": {
                        "data_types": data_service.list_types(),
                        "dashboard": await read_dashboard_config(config.server.dashboard_config_path),
                    },
                },
                websocket,
            )
            for data_type in data_service.list_types():
                await ws_manager.send_personal(
                    {
                        "type": "data_update",
                        "data_type": data_type,
                        "data": await data_service.read_all(data_type),
                    },
                    websocket,
                )
            await ws_manager.send_personal(
                {
                    "type": "sitting_update",
                    "data": sitting_service.get_state().model_dump(mode="json"),
                },
                websocket,
            )
            while True:
                incoming = await websocket.receive_text()
                if incoming == "ping":
                    await ws_manager.send_personal({"type": "pong"}, websocket)
                elif incoming == "sitting_start":
                    await sitting_service.start_sitting()
                elif incoming == "sitting_stop":
                    await sitting_service.stop_sitting()
                elif incoming == "sitting_away":
                    await sitting_service.mark_away()
                elif incoming == "sitting_back":
                    await sitting_service.mark_back()
        except WebSocketDisconnect:
            ws_manager.disconnect(websocket)

    def _get_static_version() -> str:
        css_path = config.server.static_dir / "styles.css"
        js_path = config.server.static_dir / "app.js"
        css_mtime = str(int(css_path.stat().st_mtime)) if css_path.exists() else "0"
        js_mtime = str(int(js_path.stat().st_mtime)) if js_path.exists() else "0"
        return f"{css_mtime}-{js_mtime}"

    _no_cache = {"Cache-Control": "no-cache, no-store, must-revalidate"}

    @app.get("/")
    async def index():
        html_path = config.server.static_dir / "index.html"
        content = html_path.read_text(encoding="utf-8")
        static_version = _get_static_version()
        content = content.replace('href="/styles.css"', f'href="/styles.css?v={static_version}"')
        content = content.replace('src="/app.js"', f'src="/app.js?v={static_version}"')
        from fastapi.responses import HTMLResponse
        return HTMLResponse(content, headers=_no_cache)

    @app.get("/editor.html")
    async def editor():
        html_path = config.server.static_dir / "editor.html"
        content = html_path.read_text(encoding="utf-8")
        static_version = _get_static_version()
        content = content.replace('href="/styles.css"', f'href="/styles.css?v={static_version}"')
        content = content.replace('src="/editor.js"', f'src="/editor.js?v={static_version}"')
        from fastapi.responses import HTMLResponse
        return HTMLResponse(content, headers=_no_cache)

    if config.server.static_dir.exists():
        app.mount("/", StaticFiles(directory=config.server.static_dir, html=True), name="static")
    return app


async def ensure_dashboard_config(path: Path) -> None:
    if path.exists():
        return
    default = {
        "version": "1.0",
        "title": "iPad 数据看板",
        "subtitle": "Mac 本地同步",
        "theme": "warm-ink",
        "components": [
            {"id": "calendar", "type": "calendar", "title": "日历", "size": "large-tall", "data_type": "calendar"},
            {
                "id": "sitting",
                "type": "sitting",
                "title": "久坐计时",
                "size": "medium",
                "data_type": "sitting",
                "options": {"caption": "连续久坐提醒"},
            },
            {
                "id": "notes",
                "type": "notes",
                "title": "便签",
                "size": "medium",
                "data_type": "notes",
                "options": {"caption": "置顶优先", "limit": 6},
            },
        ],
    }
    async with aiofiles.open(path, "w", encoding="utf-8") as handle:
        await handle.write(json.dumps(default, ensure_ascii=False, indent=2))
        await handle.write("\n")


app = build_app()
