# Celery — Async DDEX Generation

DDEX generation (one release × all DSPs, or batch) can run in the background via **Celery** so the UI is not blocked. Optional **Celery Beat** runs a daily batch (e.g. approved releases updated in last 24h).

---

## 1. Prerequisites

- **Redis** running (broker and result backend). Default: `redis://localhost:6379/0`.
- Install deps: `pip install -r requirements.txt` (includes `celery[redis]`, `redis`).

Configure via environment (optional):

- `CELERY_BROKER_URL` — default `redis://localhost:6379/0`
- `CELERY_RESULT_BACKEND` — default `redis://localhost:6379/0`

---

## 2. Run Celery worker

From the **RoyaltyWebsite** directory (where `manage.py` is):

```bash
celery -A RoyaltyWebsite worker -l info
```

On Windows (if needed): `celery -A RoyaltyWebsite worker -l info -P solo`

The worker runs DDEX tasks when they are enqueued (from code/API or from Beat).

---

## 3. Trigger DDEX tasks from code

### One release, all DSPs

```python
from releases.tasks import build_ddex_all_task

# By release ID
result = build_ddex_all_task.delay(release_id=123, output_base="ddex_output")
# Or by UPC
result = build_ddex_all_task.delay(upc="8905285127614", output_base="ddex_output")
# Optional: test message (e.g. JioSaavn)
result = build_ddex_all_task.delay(release_id=123, use_test_message=True)

# Check result (async)
task_id = result.id
# Later:
outcome = result.get(timeout=60)  # {"ok": True, "files_written": 4, ...}
```

### Batch (many releases × all DSPs)

```python
from releases.tasks import build_ddex_batch_task

# Last 24h, all statuses
result = build_ddex_batch_task.delay()

# Since a date, approved only, max 50 releases
result = build_ddex_batch_task.delay(
    since_date="2026-01-27",
    status_filter="approved",
    limit=50,
    output_base="ddex_output",
)

outcome = result.get(timeout=300)  # {"ok": True, "files_written": 120, "release_count": 30, ...}
```

---

## 4. Optional: Celery Beat (scheduled batch)

To run a **daily** DDEX batch (e.g. approved releases updated in last 24h), start **Beat** in addition to the worker:

```bash
celery -A RoyaltyWebsite beat -l info
```

Default schedule (in `settings.py`): every day at **2:00 AM** (server timezone), runs `build_ddex_batch_task` with `since_date=None` (last 24h), `status_filter="approved"`, output `ddex_output`.

To disable the scheduled batch: in `RoyaltyWebsite/settings.py`, remove or comment out the `CELERY_BEAT_SCHEDULE` entry `"ddex-batch-daily"`.

---

## 5. Summary

| What | How |
|------|-----|
| **Broker / backend** | Redis (`CELERY_BROKER_URL`, `CELERY_RESULT_BACKEND`) |
| **Run worker** | `celery -A RoyaltyWebsite worker -l info` |
| **Run beat (scheduled)** | `celery -A RoyaltyWebsite beat -l info` |
| **One release, all DSPs** | `build_ddex_all_task.delay(release_id=123)` or `delay(upc="...")` |
| **Batch** | `build_ddex_batch_task.delay(since_date="YYYY-MM-DD", status_filter="approved")` |
| **Daily batch** | Beat runs at 2:00 AM (configure in `CELERY_BEAT_SCHEDULE`) |

Output layout (same as CLI): `<output_base>/<dsp_code>/<upc>/<upc>.xml`.
