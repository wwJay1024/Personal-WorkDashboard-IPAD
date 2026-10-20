import asyncio
from contextlib import suppress
from datetime import datetime, timezone

from loguru import logger


class ReminderService:
    def __init__(
        self,
        times: list[str],
        message: str,
        duration_seconds: int,
        broadcast,
        weekdays_only: bool = True,
    ) -> None:
        self._targets = set(times)
        self.message = message
        self.duration_seconds = duration_seconds
        self.broadcast = broadcast
        self.weekdays_only = weekdays_only
        self._task: asyncio.Task | None = None
        self._fired_today: set[str] = set()
        self._today: str = ""

    async def _loop(self) -> None:
        while True:
            now = datetime.now()
            today = now.strftime("%Y-%m-%d")

            # 新的一天重置已触发记录
            if today != self._today:
                self._today = today
                self._fired_today.clear()

            time_key = now.strftime("%H:%M")
            is_weekday = now.weekday() < 5  # 0=Mon .. 4=Fri

            if (
                time_key in self._targets
                and time_key not in self._fired_today
                and (not self.weekdays_only or is_weekday)
            ):
                self._fired_today.add(time_key)
                await self.broadcast(
                    {
                        "type": "reminder",
                        "message": self.message,
                        "duration": self.duration_seconds,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    }
                )
                logger.info(f"reminder fired at {time_key}")

            await asyncio.sleep(30)

    def start(self) -> None:
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._loop())
            logger.info(f"reminder scheduled at {sorted(self._targets)}")

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            with suppress(asyncio.CancelledError):
                await self._task
            logger.info("reminder loop stopped")
