from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class SittingState(BaseModel):
    status: Literal["idle", "sitting", "away"] = "idle"
    is_sitting: bool = False
    is_away: bool = False
    is_meeting: bool = False
    current_session_start: str | None = None
    accumulated_seconds: int = 0
    last_away_start: str | None = None
    away_elapsed_seconds: int = 0
    next_reminder_at: str | None = None
    reminder_count: int = 0
    show_reminder: bool = False
    today_date: str | None = None
    today_sitting_seconds: int = 0
    today_break_seconds: int = 0


class SittingReminderResponse(BaseModel):
    action: Literal["take_break", "keep_working"]
