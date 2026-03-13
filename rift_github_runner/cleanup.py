from __future__ import annotations

import logging

from .cloudrift_client import CloudRiftClient
from .state import StateStore

logger = logging.getLogger(__name__)


def cleanup_orphans(
    state: StateStore,
    cloudrift: CloudRiftClient,
    max_lifetime_minutes: int,
) -> int:
    stale = state.find_stale_jobs(max_lifetime_minutes)
    if not stale:
        logger.info("No stale jobs found")
        return 0

    logger.info("Found %d stale job(s) to clean up", len(stale))
    cleaned = 0
    for job in stale:
        try:
            cloudrift.terminate_instance(job.instance_id)
            state.mark_failed(job.job_id)
            cleaned += 1
            logger.info("Cleaned up orphan: job_id=%d instance_id=%s", job.job_id, job.instance_id)
        except Exception:
            logger.exception(
                "Failed to clean up job_id=%d instance_id=%s", job.job_id, job.instance_id
            )
    return cleaned
