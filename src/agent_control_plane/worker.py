from __future__ import annotations

import logging
import time

from .db import Base, build_engine, build_session_factory
from .repository import DatabaseRepository
from .services import ControlPlaneService
from .settings import Settings, get_settings


def process_next_job(settings: Settings | None = None) -> bool:
    settings = settings or get_settings()
    engine = build_engine(settings)
    if settings.app_env == "test" or settings.database_url.startswith("sqlite"):
        Base.metadata.create_all(bind=engine)
    repository = DatabaseRepository(build_session_factory(engine))
    repository.seed_if_empty()
    service = ControlPlaneService(repository)

    job = service.claim_next_replay_job()
    if job is None:
        return False
    try:
        service.complete_replay_job(job.id)
    except Exception as exc:  # pragma: no cover
        repository.fail_job(job.id, str(exc))
    return True


def run_forever(poll_interval: float = 1.0) -> None:
    logger = logging.getLogger("agent-control-plane.worker")
    while True:
        processed = process_next_job()
        if not processed:
            logger.info("No queued replay jobs. Sleeping.")
            time.sleep(poll_interval)


if __name__ == "__main__":
    run_forever()
