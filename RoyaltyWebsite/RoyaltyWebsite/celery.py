"""
Celery app for RoyaltyWebsite.
Used for async DDEX generation (build_ddex_all, build_ddex_batch) so the UI is not blocked.
Broker: Redis (set CELERY_BROKER_URL or use default redis://localhost:6379/0).
"""
import os
from celery import Celery
from celery.schedules import crontab

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "RoyaltyWebsite.settings")

app = Celery("RoyaltyWebsite")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()


@app.task(bind=True)
def debug_task(self):
    """Example task for testing Celery."""
    print(f"Request: {self.request!r}")
