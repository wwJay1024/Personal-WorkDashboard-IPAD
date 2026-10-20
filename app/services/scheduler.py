from datetime import datetime, timedelta, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from loguru import logger


class SchedulerService:
    def __init__(self) -> None:
        self.scheduler = AsyncIOScheduler()

    def add_interval_job(self, func, minutes: int, job_id: str, **kwargs) -> None:
        next_run = datetime.now(timezone.utc) + timedelta(minutes=minutes)
        self.scheduler.add_job(
            func,
            IntervalTrigger(minutes=minutes),
            id=job_id,
            replace_existing=True,
            max_instances=1,
            coalesce=True,
            next_run_time=next_run,
            **kwargs,
        )
        logger.info("scheduled {} every {} minutes", job_id, minutes)

    def add_cron_job(self, func, job_id: str, **cron_kwargs) -> None:
        self.scheduler.add_job(
            func,
            CronTrigger(**cron_kwargs),
            id=job_id,
            replace_existing=True,
            max_instances=1,
            coalesce=True,
        )
        logger.info("scheduled {} cron {}", job_id, cron_kwargs)

    def start(self) -> None:
        if not self.scheduler.running:
            self.scheduler.start()
            logger.info("scheduler started")

    def shutdown(self) -> None:
        if self.scheduler.running:
            self.scheduler.shutdown()
            logger.info("scheduler stopped")
