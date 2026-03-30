"""
Write in-progress Merlin / Apple delivery steps onto DistributionJob.store_results['_live']
so the Preview → Delivery Operations tab can poll and show status for large S3 downloads.
"""
from __future__ import annotations

import logging
import time
from typing import Optional

from django.utils import timezone

logger = logging.getLogger(__name__)

# Avoid hammering the DB on every S3 read chunk
_THROTTLE_SEC = 2.0
_last_write: dict[int, float] = {}


def is_distribution_job_cancel_requested(job_id: Optional[int]) -> bool:
    """True if admin requested cancel or job is no longer active (e.g. manually failed)."""
    if not job_id:
        return False
    from releases.models import DistributionJob

    try:
        j = DistributionJob.objects.only("cancel_requested", "status").get(pk=job_id)
    except DistributionJob.DoesNotExist:
        return True
    if j.cancel_requested:
        return True
    if j.status not in (DistributionJob.STATUS.RUNNING, DistributionJob.STATUS.QUEUED):
        return True
    return False


def update_distribution_job_merlin_progress(job_id: Optional[int], message: str) -> None:
    if not job_id or not (message or "").strip():
        return
    from releases.models import DistributionJob

    now = time.monotonic()
    prev = _last_write.get(job_id, 0.0)
    if now - prev < _THROTTLE_SEC:
        return
    _last_write[job_id] = now

    try:
        job = DistributionJob.objects.get(pk=job_id)
    except DistributionJob.DoesNotExist:
        return
    if job.status != DistributionJob.STATUS.RUNNING:
        return
    if job.cancel_requested:
        return

    data = dict(job.store_results or {})
    data["_live"] = {
        "store": "apple_music",
        "step": (message or "")[:1900],
        "updated_at": timezone.now().isoformat(),
    }
    job.store_results = data
    job.save(update_fields=["store_results"])
