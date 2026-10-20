from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from loguru import logger


class SchedulerService:
    def __init__(self) -> None:
        self.scheduler = AsyncIOScheduler()

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
