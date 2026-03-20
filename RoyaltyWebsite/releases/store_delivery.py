"""
Delivery to all stores via DDEX.
After admin approval, the system builds DDEX ERN 4.3 per store and delivers using each store's
method (Audiomack → S3; others can be added here).
Audio and cover art are already in S3; the DDEX XML references them (or relative paths in the delivery package).
"""
import logging
import os
from typing import Any, Dict, List, Tuple

from releases.models import Release, Track, UniqueCode
from releases.upc_utils import normalize_upc_to_13

logger = logging.getLogger(__name__)

# Stores we can deliver to via our DDEX pipeline (build XML + store-specific upload).
# Add more as we implement: e.g. "spotify" -> API, etc.
# apple_music = Merlin Bridge SFTP (SSH key auth). See MERLIN_BRIDGE_APPLE_MUSIC.md.
DELIVERY_IMPLEMENTED = {"audiomack", "gaana", "tiktok", "apple_music"}


def get_delivery_stores() -> List[str]:
    """
    Return list of store codes to deliver to when admin approves.
    From env DELIVERY_STORES (comma-separated), e.g. DELIVERY_STORES=audiomack.
    Only returns stores we have a delivery implementation for.
    """
    raw = (os.getenv("DELIVERY_STORES") or os.getenv("DELIVER_ONLY_AUDIOMACK") and "audiomack" or "").strip()
    if not raw and os.getenv("DELIVER_ONLY_AUDIOMACK", "").strip().lower() in ("true", "1", "yes", "on"):
        raw = "audiomack"
    if not raw:
        return []
    codes = [s.strip().lower() for s in raw.split(",") if s.strip()]
    return [c for c in codes if c in DELIVERY_IMPLEMENTED]


def use_ddex_delivery() -> bool:
    """True if we should use our DDEX delivery pipeline (not Sonosuite) when admin approves."""
    return len(get_delivery_stores()) > 0


def _assign_upc_isrc_if_needed(release: Release) -> Tuple[bool, str]:
    """Assign UPC to release and ISRC to tracks if missing. Returns (True, None) or (False, error)."""
    if not release.upc:
        upc_to_assign = UniqueCode.objects.filter(type=UniqueCode.TYPE.UPC, assigned=False).first()
        if not upc_to_assign:
            return (False, "No UPC codes available. Contact admin.")
        release.upc = normalize_upc_to_13(upc_to_assign.code) or upc_to_assign.code
        upc_to_assign.assigned = True
        upc_to_assign.save()
        release.save(update_fields=["upc"])
    for track in Track.objects.filter(release=release):
        if not track.isrc:
            isrc_to_assign = UniqueCode.objects.filter(type=UniqueCode.TYPE.ISRC, assigned=False).first()
            if not isrc_to_assign:
                return (False, f"Track '{track.title}' needs ISRC; no codes available.")
            track.isrc = isrc_to_assign.code
            isrc_to_assign.assigned = True
            track.save()
            isrc_to_assign.save()
    return (True, None)


def _deliver_to_audiomack(release: Release) -> Tuple[bool, str, Dict[str, Any]]:
    """Build DDEX for Audiomack and upload to S3. UPC/ISRC already assigned by deliver_release_to_all_stores."""
    from releases.audiomack_delivery import deliver_release_to_audiomack
    return deliver_release_to_audiomack(release)


def _deliver_to_gaana(release: Release) -> Tuple[bool, str, Dict[str, Any]]:
    """Build DDEX for Gaana and upload via SFTP (or S3)."""
    from releases.gaana_delivery import deliver_release_to_gaana
    return deliver_release_to_gaana(release)


def _deliver_to_tiktok(release: Release) -> Tuple[bool, str, Dict[str, Any]]:
    """Build DDEX for TikTok (UGC) and upload to TikTok S3."""
    from releases.tiktok_delivery import deliver_release_to_tiktok
    return deliver_release_to_tiktok(release)


def _deliver_to_apple_music(release: Release) -> Tuple[bool, str, Dict[str, Any]]:
    """Build DDEX for Apple Music and upload via Merlin Bridge SFTP (SSH key auth)."""
    from releases.merlin_bridge_delivery import deliver_release_to_merlin_bridge
    return deliver_release_to_merlin_bridge(release)


def deliver_release_to_store(release: Release, store_code: str) -> Tuple[bool, str, Dict[str, Any]]:
    """
    Deliver one release to one store: build DDEX for that store and run store-specific delivery.
    Returns (success, error_message, detail_dict).
    """
    store_code = (store_code or "").strip().lower()
    if store_code == "audiomack":
        return _deliver_to_audiomack(release)
    if store_code == "gaana":
        return _deliver_to_gaana(release)
    if store_code == "tiktok":
        return _deliver_to_tiktok(release)
    if store_code == "apple_music":
        return _deliver_to_apple_music(release)
    return (False, f"Delivery not implemented for store: {store_code}", {})


def deliver_release_to_all_stores(release: Release) -> Tuple[bool, str, Dict[str, Any]]:
    """
    Assign UPC/ISRC if needed, then deliver to every store in get_delivery_stores().
    Returns (success, error_message, detail_dict).
    detail_dict: per_store_results (list of {store, success, message}), operation_ids (for DB), summary message.
    """
    ok, err = _assign_upc_isrc_if_needed(release)
    if not ok:
        return (False, err or "UPC/ISRC assignment failed", {})

    stores = get_delivery_stores()
    if not stores:
        return (False, "No delivery stores configured. Set DELIVERY_STORES=audiomack,gaana,tiktok in .env.", {})

    per_store_results = []
    operation_ids = []
    any_ok = False
    for store_code in stores:
        success, err, detail = deliver_release_to_store(release, store_code)
        msg = detail.get("message") or (None if success else err)
        if success and detail.get("s3_key"):
            operation_ids.append(f"{store_code}:{detail['s3_key']}")
        if success and detail.get("local_path"):
            operation_ids.append(f"{store_code}:{detail['local_path']}")
        if success:
            any_ok = True
        per_store_results.append({"store": store_code, "success": success, "message": msg or (err or "")})

    if not any_ok:
        first_err = next((r["message"] for r in per_store_results if not r["success"]), "Delivery failed")
        return (False, first_err, {"per_store_results": per_store_results, "operation_ids": operation_ids})

    summary = "; ".join(
        f"{r['store']}: ok" if r["success"] else f"{r['store']}: {r['message']}"
        for r in per_store_results
    )
    return (True, None, {
        "per_store_results": per_store_results,
        "operation_ids": operation_ids,
        "message": f"Delivered to: {summary}",
        "operation_ids_str": "|".join(operation_ids),
    })
