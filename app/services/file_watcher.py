import asyncio
from pathlib import Path
from typing import Awaitable, Callable

from loguru import logger
from watchdog.events import FileSystemEventHandler
from watchdog.observers.polling import PollingObserver

from app.services.data_service import DataService


class DataFileHandler(FileSystemEventHandler):
    def __init__(
        self,
        loop: asyncio.AbstractEventLoop,
        data_service: DataService,
        dashboard_config_path: Path,
        push_data_update: Callable[[str], Awaitable[None]],
        push_config_update: Callable[[], Awaitable[None]],
        debounce_seconds: float = 0.8,
    ) -> None:
        self.loop = loop
        self.data_service = data_service
        self.dashboard_config_path = dashboard_config_path.resolve()
        self.push_data_update = push_data_update
        self.push_config_update = push_config_update
        self.debounce_seconds = debounce_seconds
        self.pending: dict[str, asyncio.TimerHandle] = {}

    def on_modified(self, event) -> None:
        if event.is_directory:
            return
        file_path = Path(event.src_path).resolve()
        if file_path == self.dashboard_config_path:
            self._debounce("dashboard_config", self.push_config_update)
            return
        for data_type, (registered_path, _) in self.data_service.registry.items():
            if file_path == registered_path.resolve():
                self._debounce(data_type, lambda dt=data_type: self.push_data_update(dt))
                return

    def _debounce(self, key: str, callback) -> None:
        def schedule() -> None:
            existing = self.pending.pop(key, None)
            if existing:
                existing.cancel()

            def run_callback() -> None:
                self.pending.pop(key, None)
                asyncio.run_coroutine_threadsafe(callback(), self.loop)

            self.pending[key] = self.loop.call_later(self.debounce_seconds, run_callback)

        self.loop.call_soon_threadsafe(schedule)


class FileWatcherService:
    def __init__(
        self,
        data_dir: Path,
        dashboard_config_path: Path,
        handler: DataFileHandler,
    ) -> None:
        self.data_dir = data_dir
        self.dashboard_config_path = dashboard_config_path
        self.handler = handler
        self.observer = PollingObserver()

    def start(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.observer.schedule(self.handler, str(self.data_dir), recursive=False)
        config_parent = self.dashboard_config_path.parent
        if config_parent.resolve() != self.data_dir.resolve():
            self.observer.schedule(self.handler, str(config_parent), recursive=False)
        self.observer.start()
        logger.info("file watcher started")

    def stop(self) -> None:
        self.observer.stop()
        self.observer.join(timeout=3)
        logger.info("file watcher stopped")
