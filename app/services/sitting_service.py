from __future__ import annotations

import asyncio
import json
from contextlib import suppress
from datetime import datetime, timedelta, timezone
from pathlib import Path

from loguru import logger

from app.models.sitting import SittingState


class SittingService:
    BREAK_RESET_THRESHOLD = timedelta(minutes=5)

    def __init__(self, broadcast, data_dir: str = "data"):
        self.broadcast = broadcast
        self._history_path = Path(data_dir) / "sitting_history.json"
        self._state_path = Path(data_dir) / "sitting_state.json"
        self._task: asyncio.Task | None = None

        self._state = SittingState()
        self._load_state()
        self._ensure_today_rollover()

    # ------------------------------------------------------------------
    # persistence
    # ------------------------------------------------------------------
    def _load_state(self):
        if self._state_path.exists():
            try:
                data = json.loads(self._state_path.read_text("utf-8"))
                self._state = SittingState(**data)
            except Exception:
                pass

    def _save_state(self):
        self._state_path.write_text(
            json.dumps(self._state.model_dump(), ensure_ascii=False, indent=2),
            "utf-8",
        )

    def _ensure_today_rollover(self):
        today = self._today_str()
        if self._state.today_date != today:
            # 跨天：重置今日统计
            self._state.today_date = today
            self._state.today_sitting_seconds = 0
            self._state.today_break_seconds = 0

            # 如果会话是昨天的（忘记点结束），自动结束
            if self._state.is_sitting:
                self._state.status = "idle"
                self._state.is_sitting = False
                self._state.is_away = False
                self._state.is_meeting = False
                self._state.current_session_start = None
                self._state.accumulated_seconds = 0
                self._state.last_away_start = None
                self._state.reminder_count = 0
                self._state.show_reminder = False
                self._state.next_reminder_at = None

            self._save_state()

    def _today_str(self) -> str:
        return self._now().astimezone().strftime("%Y-%m-%d")

    # ------------------------------------------------------------------
    # computed helpers
    # ------------------------------------------------------------------
    def _now(self) -> datetime:
        return datetime.now(timezone.utc)

    def _current_accumulated_seconds(self) -> int:
        """实时计算当前累计秒数"""
        if not self._state.is_sitting:
            return self._state.accumulated_seconds
        if not self._state.current_session_start:
            return self._state.accumulated_seconds
        start = datetime.fromisoformat(self._state.current_session_start)
        if self._state.is_away and self._state.last_away_start:
            # 离开中，累计到离开开始时刻
            away_start = datetime.fromisoformat(self._state.last_away_start)
            return self._state.accumulated_seconds + int((away_start - start).total_seconds())
        return self._state.accumulated_seconds + int((self._now() - start).total_seconds())

    def _current_break_seconds(self) -> int:
        """实时计算当前已休息秒数（从 last_away_start 算起）"""
        if not (self._state.is_sitting and self._state.is_away and self._state.last_away_start):
            return self._state.today_break_seconds
        away_start = datetime.fromisoformat(self._state.last_away_start)
        return self._state.today_break_seconds + int((self._now() - away_start).total_seconds())

    def _current_away_elapsed_seconds(self) -> int:
        if not (self._state.is_sitting and self._state.is_away and self._state.last_away_start):
            return 0
        away_start = datetime.fromisoformat(self._state.last_away_start)
        return int((self._now() - away_start).total_seconds())

    def _build_state(self) -> SittingState:
        """返回实时状态快照"""
        return SittingState(
            status=self._state.status,
            is_sitting=self._state.is_sitting,
            is_away=self._state.is_away,
            is_meeting=self._state.is_meeting,
            current_session_start=self._state.current_session_start,
            accumulated_seconds=self._current_accumulated_seconds(),
            last_away_start=self._state.last_away_start,
            away_elapsed_seconds=self._current_away_elapsed_seconds(),
            next_reminder_at=self._state.next_reminder_at,
            reminder_count=self._state.reminder_count,
            show_reminder=self._state.show_reminder,
            today_date=self._state.today_date,
            today_sitting_seconds=self._current_sitting_today(),
            today_break_seconds=self._current_break_seconds(),
        )

    def _current_sitting_today(self) -> int:
        """实时计算今日已累计的久坐秒数"""
        return self._state.today_sitting_seconds + self._current_accumulated_seconds()

    def _reminder_message(self, accumulated_minutes: int) -> str:
        hours = accumulated_minutes // 60
        minutes = accumulated_minutes % 60
        if hours > 0 and minutes > 0:
            return f"你已经连续久坐 {hours} 小时 {minutes} 分钟，建议起身活动 5-10 分钟"
        if hours > 0:
            return f"你已经连续久坐 {hours} 小时，建议起身活动 5-10 分钟"
        return f"你已经连续久坐 {minutes} 分钟，建议起身活动 5-10 分钟"

    # ------------------------------------------------------------------
    # actions
    # ------------------------------------------------------------------
    async def start_sitting(self):
        self._ensure_today_rollover()
        now = self._now()
        self._state.status = "sitting"
        self._state.is_sitting = True
        self._state.is_away = False
        self._state.current_session_start = now.isoformat()
        self._state.accumulated_seconds = 0
        self._state.last_away_start = None
        self._state.is_meeting = False
        self._state.reminder_count = 0
        self._state.show_reminder = False
        self._state.next_reminder_at = None
        self._save_state()
        await self._push_update()

    async def stop_sitting(self):
        self._ensure_today_rollover()
        acc = self._current_accumulated_seconds()
        break_sec = self._current_break_seconds()
        if acc > 0:
            self._state.today_sitting_seconds += acc
        if self._state.is_away and self._state.last_away_start:
            # 已离开但在停止时还未"回来"，把离开期间计入休息
            self._state.today_break_seconds = break_sec
        self._state.status = "idle"
        self._state.is_sitting = False
        self._state.is_away = False
        self._state.is_meeting = False
        self._state.current_session_start = None
        self._state.accumulated_seconds = 0
        self._state.last_away_start = None
        self._state.next_reminder_at = None
        self._state.reminder_count = 0
        self._state.show_reminder = False
        self._save_history(acc)
        self._save_state()
        await self._push_update()

    async def mark_away(self):
        if not self._state.is_sitting or self._state.is_away:
            return

        self._ensure_today_rollover()
        now = self._now()
        start = datetime.fromisoformat(self._state.current_session_start)
        delta = int((now - start).total_seconds())
        self._state.accumulated_seconds += delta
        self._state.status = "away"
        self._state.is_away = True
        self._state.last_away_start = now.isoformat()
        self._state.current_session_start = None
        self._save_state()
        await self._push_update()

    async def mark_back(self):
        if not self._state.is_sitting or not self._state.is_away:
            return

        self._ensure_today_rollover()
        now = self._now()
        away_start = datetime.fromisoformat(self._state.last_away_start)
        away_duration = now - away_start
        away_seconds = int(away_duration.total_seconds())
        self._state.today_break_seconds += away_seconds

        if away_duration >= self.BREAK_RESET_THRESHOLD:
            self._save_history(self._state.accumulated_seconds)
            self._state.today_sitting_seconds += self._state.accumulated_seconds
            self._state.accumulated_seconds = 0
            self._state.reminder_count = 0
            self._state.show_reminder = False
            self._state.next_reminder_at = None

        self._state.status = "sitting"
        self._state.is_away = False
        self._state.current_session_start = now.isoformat()
        self._state.last_away_start = None
        self._save_state()
        await self._push_update()

    async def start_meeting(self):
        if not self._state.is_sitting or self._state.is_meeting:
            return

        self._ensure_today_rollover()
        self._state.is_meeting = True
        self._save_state()
        await self._push_update()

    async def stop_meeting(self):
        if not self._state.is_meeting:
            return

        self._ensure_today_rollover()
        self._state.is_meeting = False
        self._save_state()
        await self._push_update()

    async def handle_reminder_response(self, action: str):
        self._state.show_reminder = False

        if action == "take_break":
            await self.mark_away()
        elif action == "keep_working":
            self._state.reminder_count += 1
            self._state.next_reminder_at = (self._now() + timedelta(minutes=30)).isoformat()
            self._save_state()
            await self._push_update()

    def get_state(self) -> SittingState:
        self._ensure_today_rollover()
        return self._build_state()

    # ------------------------------------------------------------------
    # background loop
    # ------------------------------------------------------------------
    async def _loop(self):
        while True:
            try:
                self._ensure_today_rollover()

                if self._state.is_sitting and not self._state.is_away:
                    acc = self._current_accumulated_seconds()
                    acc_minutes = acc // 60
                    logger.debug(f"sitting loop: acc={acc}s ({acc_minutes}min), reminder_count={self._state.reminder_count}, show_reminder={self._state.show_reminder}")

                    if self._state.reminder_count == 0 and acc_minutes >= 60:
                        if not self._state.show_reminder:
                            logger.info(f"triggering first reminder at {acc_minutes}min")
                            await self._fire_reminder(acc_minutes)
                    elif self._state.reminder_count > 0 and not self._state.show_reminder:
                        base = 60 + self._state.reminder_count * 30
                        if acc_minutes >= base:
                            logger.info(f"triggering reminder #{self._state.reminder_count + 1} at {acc_minutes}min")
                            await self._fire_reminder(acc_minutes)

                await asyncio.sleep(30)
            except Exception:
                logger.exception("sitting loop error")
                await asyncio.sleep(30)

    async def _fire_reminder(self, acc_minutes: int):
        logger.info(f"_fire_reminder called: {acc_minutes}min, message={self._reminder_message(acc_minutes)}")
        self._state.show_reminder = True
        self._save_state()
        await self.broadcast({
            "type": "sitting_reminder",
            "data": {
                "accumulated_minutes": acc_minutes,
                "reminder_count": self._state.reminder_count + 1,
                "message": self._reminder_message(acc_minutes),
            },
        })
        await self._push_update()

    async def _push_update(self):
        state = self._build_state()
        await self.broadcast({
            "type": "sitting_update",
            "data": state.model_dump(mode="json"),
        })

    # ------------------------------------------------------------------
    # history
    # ------------------------------------------------------------------
    def _save_history(self, accumulated_seconds: int):
        entry = {
            "date": self._now().strftime("%Y-%m-%d"),
            "accumulated_seconds": accumulated_seconds,
            "ended_at": self._now().isoformat(),
            "reminder_count": self._state.reminder_count,
        }
        history = []
        if self._history_path.exists():
            try:
                history = json.loads(self._history_path.read_text("utf-8"))
            except Exception:
                history = []
        history.append(entry)
        history = history[-90:]
        self._history_path.write_text(
            json.dumps(history, ensure_ascii=False, indent=2),
            "utf-8",
        )

    # ------------------------------------------------------------------
    # lifecycle
    # ------------------------------------------------------------------
    def start(self):
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._loop())

    async def stop(self):
        if self._task:
            self._task.cancel()
            with suppress(asyncio.CancelledError):
                await self._task
