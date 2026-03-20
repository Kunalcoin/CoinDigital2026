"""
Celery tasks for DDEX generation (Phase 3).
Run build_ddex_all or build_ddex_batch in the background so the UI is not blocked.
"""
import os
from datetime import datetime, timedelta
from celery import shared_task
from django.utils import timezone


@shared_task(bind=True, name="releases.tasks.build_ddex_all_task")
def build_ddex_all_task(
    self,
    release_id=None,
    upc=None,
    output_base="ddex_output",
    use_test_message=False,
):
    """
    Generate DDEX for one release for all active DSPs (async).
    Pass either release_id (int) or upc (str). Output: <output_base>/<dsp_code>/<upc>/<upc>.xml
    """
    from releases.models import Release
    from releases.ddex_builder import build_new_release_message
    from releases.ddex_dsp_registry import list_dsp_codes

    if not release_id and not upc:
        return {"ok": False, "error": "Provide release_id or upc"}

    try:
        if release_id:
            release = Release.objects.get(id=release_id)
        else:
            release = Release.objects.get(upc=upc.strip())
    except Release.DoesNotExist:
        return {"ok": False, "error": f"Release not found (id={release_id}, upc={upc})"}

    upc_val = (release.upc or "").strip() or str(release.id)
    dsp_codes = list_dsp_codes(active_only=True)
    if not dsp_codes:
        return {"ok": False, "error": "No active DSPs in registry", "release_id": release.id}

    message_control_type = "TestMessage" if use_test_message else "LiveMessage"
    written = 0
    for dsp_code in dsp_codes:
        out_dir = os.path.join(output_base, dsp_code, upc_val)
        os.makedirs(out_dir, exist_ok=True)
        path = os.path.join(out_dir, f"{upc_val}.xml")
        xml = build_new_release_message(
            release, store=dsp_code, message_control_type=message_control_type
        )
        with open(path, "w", encoding="utf-8") as f:
            f.write(xml)
        written += 1

    return {
        "ok": True,
        "release_id": release.id,
        "upc": upc_val,
        "release_title": release.title,
        "files_written": written,
        "dsp_codes": dsp_codes,
        "output_base": output_base,
    }


@shared_task(bind=True, name="releases.tasks.build_ddex_batch_task")
def build_ddex_batch_task(
    self,
    since_date=None,
    status_filter="",
    limit=0,
    output_base="ddex_output",
):
    """
    Generate DDEX for many releases × all active DSPs (async).
    since_date: YYYY-MM-DD string or None (None = last 24 hours).
    status_filter: e.g. "approved" or "" for all.
    limit: max releases (0 = no limit).
    Output: <output_base>/<dsp_code>/<upc>/<upc>.xml
    """
    from releases.models import Release
    from releases.ddex_builder import build_new_release_message
    from releases.ddex_dsp_registry import list_dsp_codes

    if since_date:
        try:
            since_dt = timezone.make_aware(
                datetime.strptime(since_date.strip()[:10], "%Y-%m-%d").replace(
                    hour=0, minute=0, second=0, microsecond=0
                )
            )
        except (ValueError, TypeError):
            since_dt = timezone.now() - timedelta(hours=24)
    else:
        since_dt = timezone.now() - timedelta(hours=24)

    queryset = Release.objects.filter(updated_at__gte=since_dt).order_by("updated_at")
    if status_filter:
        queryset = queryset.filter(approval_status=status_filter)
    if limit > 0:
        queryset = queryset[:limit]
    releases = list(queryset)

    dsp_codes = list_dsp_codes(active_only=True)
    if not dsp_codes:
        return {"ok": False, "error": "No active DSPs", "release_count": 0}

    total = 0
    for release in releases:
        upc_val = (release.upc or "").strip() or str(release.id)
        for dsp_code in dsp_codes:
            out_dir = os.path.join(output_base, dsp_code, upc_val)
            os.makedirs(out_dir, exist_ok=True)
            path = os.path.join(out_dir, f"{upc_val}.xml")
            xml = build_new_release_message(release, store=dsp_code)
            with open(path, "w", encoding="utf-8") as f:
                f.write(xml)
            total += 1

    return {
        "ok": True,
        "release_count": len(releases),
        "dsp_count": len(dsp_codes),
        "files_written": total,
        "since": str(since_dt.date()),
        "status_filter": status_filter or "(all)",
        "output_base": output_base,
    }
