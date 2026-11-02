"""Durable SQL greeting queue with Redis wake-ups; no cluster actions."""

import logging
import signal
import time
from types import FrameType

from redis.exceptions import RedisError
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from kubesentinel_api.config import get_settings
from kubesentinel_api.database import SessionLocal, redis_client
from kubesentinel_api.models import GreetingJob
from kubesentinel_api.observability import configure_logging

logger = logging.getLogger("kubesentinel.worker")


def process_one(session: Session) -> bool:
    job = session.scalar(
        select(GreetingJob)
        .where(GreetingJob.status == "queued")
        .order_by(GreetingJob.created_at)
        .with_for_update(skip_locked=True)
        .limit(1)
    )
    if job is None:
        session.rollback()
        return False
    job.message = f"Hello, {job.name}! KubeSentinel AI is connected."
    job.status = "completed"
    session.commit()
    logger.info("greeting_completed", extra={"correlation_id": job.id})
    return True


def main() -> None:
    configure_logging(get_settings().log_level)
    running = True

    def stop(signum: int, frame: FrameType | None) -> None:
        nonlocal running
        running = False

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    while running:
        try:
            with SessionLocal() as session:
                if process_one(session):
                    continue
            try:
                redis_client.blpop(["sentinel:jobs"], timeout=2)
            except RedisError:
                logger.warning("queue_hint_unavailable")
                time.sleep(2)
        except SQLAlchemyError:
            logger.error("database_unavailable")
            time.sleep(2)


if __name__ == "__main__":
    main()
