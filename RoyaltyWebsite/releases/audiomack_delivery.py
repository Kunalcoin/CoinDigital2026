"""
Audiomack delivery: build DDEX ERN 4.3 for Audiomack and upload to S3.
- If AUDIOMACK_S3_BUCKET is set: upload full package (XML + cover + audio) to their bucket at prefix/delivery_id/.
- Else: upload to your bucket (ddex/audiomack/date/) with XML + resources/.
"""
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple
from urllib.parse import urlparse

from django.conf import settings

from releases.ddex_audiomack_takedown import build_audiomack_takedown_message
from releases.ddex_builder import build_new_release_message
from releases.models import Release, Track, UniqueCode
from releases.upc_utils import normalize_upc_to_13

logger = logging.getLogger(__name__)


def _s3_bucket_key_from_url(url: str, default_bucket: str) -> Tuple[str, str]:
    """Parse S3 URL to (bucket, key). If not a URL or parse fails, return (default_bucket, url as key)."""
    if not url or not isinstance(url, str):
        return (default_bucket, "")
    url = url.strip()
    if not url.startswith("http"):
        return (default_bucket, url.lstrip("/"))
    try:
        parsed = urlparse(url)
        path = (parsed.path or "").lstrip("/")
        host = (parsed.hostname or "").lower()
        if "s3.amazonaws.com" in host or ".s3." in host:
            if ".s3." in host:
                bucket = host.split(".s3.")[0]
                key = path
            else:
                parts = path.split("/", 1)
                bucket = parts[0] if len(parts) > 1 else default_bucket
                key = parts[1] if len(parts) > 1 else path
            if bucket and key:
                return (bucket, key)
        return (default_bucket, path or url)
    except Exception:
        return (default_bucket, url.lstrip("/"))


def _copy_assets_to_delivery_folder(
    release: Release, target_bucket: str, delivery_prefix: str, default_bucket: str
) -> Tuple[int, List[str]]:
    """Copy cover art and track audio from their current S3 paths to delivery_prefix/resources/. Returns (copied_count, list of errors)."""
    from .processor import processor
    s3 = processor.get_s3_client()
    resources_prefix = delivery_prefix.rstrip("/") + "/resources/"
    copied = 0
    errors = []

    cover_url = getattr(release, "cover_art_url", None) or ""
    if cover_url:
        src_bucket, src_key = _s3_bucket_key_from_url(cover_url, default_bucket)
        if src_key:
            try:
                s3.copy_object(
                    CopySource={"Bucket": src_bucket, "Key": src_key},
                    Bucket=target_bucket,
                    Key=resources_prefix + "coverart.jpg",
                )
                copied += 1
                logger.info("Copied cover to s3://%s/%scoverart.jpg", target_bucket, resources_prefix)
            except Exception as e:
                errors.append(f"Cover: {e}")
                logger.warning("Could not copy cover %s: %s", cover_url[:80], e)

    for idx, track in enumerate(Track.objects.filter(release=release).order_by("id")):
        audio_url = getattr(track, "audio_track_url", None) or ""
        if not audio_url:
            continue
        src_bucket, src_key = _s3_bucket_key_from_url(audio_url, default_bucket)
        if not src_key:
            continue
        dest_name = f"1_{idx + 1}.flac"
        try:
            s3.copy_object(
                CopySource={"Bucket": src_bucket, "Key": src_key},
                Bucket=target_bucket,
                Key=resources_prefix + dest_name,
            )
            copied += 1
            logger.info("Copied audio to s3://%s/%s%s", target_bucket, resources_prefix, dest_name)
        except Exception as e:
            errors.append(f"Track {idx + 1}: {e}")
            logger.warning("Could not copy audio %s: %s", audio_url[:80], e)

    return (copied, errors)


def is_deliver_only_audiomack() -> bool:
    """Return True if Approve should deliver only to Audiomack (no Sonosuite)."""
    v = (os.getenv("DELIVER_ONLY_AUDIOMACK") or "").strip().lower()
    return v in ("true", "1", "yes", "on")


def _assign_upc_isrc_if_needed(release: Release) -> Tuple[bool, str]:
    """
    Assign UPC to release and ISRC to tracks if missing.
    Returns (True, None) on success, (False, error_message) on failure.
    """
    if not release.upc:
        upc_to_assign = UniqueCode.objects.filter(type=UniqueCode.TYPE.UPC, assigned=False).first()
        if not upc_to_assign:
            return (False, "No UPC codes available. Contact admin.")
        release.upc = normalize_upc_to_13(upc_to_assign.code) or upc_to_assign.code
        upc_to_assign.assigned = True
        upc_to_assign.save()
        release.save(update_fields=["upc"])
    tracks = Track.objects.filter(release=release)
    for track in tracks:
        if not track.isrc:
            isrc_to_assign = UniqueCode.objects.filter(type=UniqueCode.TYPE.ISRC, assigned=False).first()
            if not isrc_to_assign:
                return (False, f"Track '{track.title}' needs ISRC; no codes available.")
            track.isrc = isrc_to_assign.code
            isrc_to_assign.assigned = True
            track.save()
            isrc_to_assign.save()
    return (True, None)


def _upload_xml_to_s3(xml_content: str, bucket: str, s3_key: str) -> Tuple[bool, str]:
    """Upload XML string to the given S3 bucket. Returns (True, None) or (False, error_message)."""
    if not bucket:
        return (False, "No bucket specified.")
    if not getattr(settings, "AWS_ACCESS_KEY_ID", None) or not getattr(settings, "AWS_SECRET_ACCESS_KEY", None):
        return (False, "AWS credentials not configured. Set AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY.")
    try:
        from .processor import processor
        s3 = processor.get_s3_client()
        s3.put_object(
            Bucket=bucket,
            Key=s3_key,
            Body=xml_content.encode("utf-8"),
            ContentType="application/xml",
        )
        logger.info("DDEX XML uploaded to s3://%s/%s", bucket, s3_key)
        return (True, None)
    except Exception as e:
        logger.exception("S3 upload failed: %s", e)
        return (False, str(e))


def _save_audiomack_xml_local(xml_content: str, upc: str) -> str:
    """Save XML to local folder out_audiomack (create if needed). Returns path or empty string."""
    try:
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        out_dir = os.path.join(base_dir, "out_audiomack")
        os.makedirs(out_dir, exist_ok=True)
        path = os.path.join(out_dir, f"{upc}.xml")
        with open(path, "w", encoding="utf-8") as f:
            f.write(xml_content)
        logger.info("Audiomack DDEX saved to %s", path)
        return path
    except Exception as e:
        logger.warning("Could not save Audiomack DDEX locally: %s", e)
        return ""


def deliver_release_to_audiomack(release: Release) -> Tuple[bool, str, Dict[str, Any]]:
    """
    Build DDEX ERN 4.3 for Audiomack and upload to S3 (if configured).
    Assigns UPC/ISRC if needed. Does not change approval_status or published; caller must save.
    Returns (success, error_message, detail_dict).
    detail_dict may include: message, s3_bucket, s3_key, upc, xml_built.
    """
    ok, err = _assign_upc_isrc_if_needed(release)
    if not ok:
        return (False, err or "UPC/ISRC assignment failed", {})

    upc = (release.upc or "").strip() or str(release.id)
    upc = normalize_upc_to_13(upc) or upc

    try:
        xml = build_new_release_message(release, store="audiomack")
    except Exception as e:
        logger.exception("Audiomack DDEX build failed for release %s: %s", release.id, e)
        return (False, f"DDEX build failed: {e}", {"xml_built": False})

    # Prefer our own S3 bucket (same as WAV and poster) – no Audiomack bucket needed
    our_bucket = (getattr(settings, "AWS_STORAGE_BUCKET_NAME", None) or "").strip()
    audiomack_bucket = (os.getenv("AUDIOMACK_S3_BUCKET") or "").strip()

    if audiomack_bucket:
        # Upload full package (XML + cover + audio) to Audiomack's bucket
        prefix = (os.getenv("AUDIOMACK_S3_PREFIX") or "coin-digital").strip().rstrip("/")
        delivery_id = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
        delivery_prefix = f"{prefix}/{delivery_id}/"
        s3_key = f"{delivery_prefix}{upc}.xml"
        upload_ok, upload_err = _upload_xml_to_s3(xml, audiomack_bucket, s3_key)
        if not upload_ok:
            local_path = _save_audiomack_xml_local(xml, upc)
            return (False, upload_err or "S3 upload failed", {
                "message": "DDEX built but upload failed. " + (upload_err or "") + (" XML saved to " + local_path if local_path else ""),
                "upc": upc,
                "xml_built": True,
                "s3_key": s3_key,
                "local_path": local_path,
            })
        our_bucket = (getattr(settings, "AWS_STORAGE_BUCKET_NAME", None) or "").strip() or audiomack_bucket
        assets_copied, asset_errors = _copy_assets_to_delivery_folder(
            release, audiomack_bucket, delivery_prefix, our_bucket
        )
        msg = f"DDEX for Audiomack uploaded to Audiomack S3. UPC: {upc}. XML + {assets_copied} resource(s) (cover + audio) in resources/."
        if asset_errors:
            msg += " Warnings: " + "; ".join(asset_errors[:3])
        return (True, None, {
            "message": msg,
            "upc": upc,
            "s3_bucket": audiomack_bucket,
            "s3_key": s3_key,
            "xml_built": True,
            "assets_copied": assets_copied,
            "asset_errors": asset_errors,
        })

    # Default: save to your S3 (same bucket as your WAV and poster) and copy audio + poster into resources/
    if our_bucket:
        delivery_id = datetime.now(timezone.utc).strftime("%Y%m%d")
        delivery_prefix = f"ddex/audiomack/{delivery_id}/"
        s3_key = f"{delivery_prefix}{upc}.xml"
        upload_ok, upload_err = _upload_xml_to_s3(xml, our_bucket, s3_key)
        if upload_ok:
            assets_copied, asset_errors = _copy_assets_to_delivery_folder(
                release, our_bucket, delivery_prefix, our_bucket
            )
            msg = f"DDEX for Audiomack saved to your S3. UPC: {upc}. XML: s3://{our_bucket}/{s3_key}. Resources: {assets_copied} file(s) (cover + audio) copied to resources/."
            if asset_errors:
                msg += " Warnings: " + "; ".join(asset_errors[:3])
            return (True, None, {
                "message": msg,
                "upc": upc,
                "s3_bucket": our_bucket,
                "s3_key": s3_key,
                "xml_built": True,
                "assets_copied": assets_copied,
                "asset_errors": asset_errors,
            })
        local_path = _save_audiomack_xml_local(xml, upc)
        return (False, upload_err or "S3 upload failed", {
            "message": "DDEX built but upload to your S3 failed. " + (upload_err or "") + (" XML saved to " + local_path if local_path else ""),
            "upc": upc,
            "xml_built": True,
            "s3_key": s3_key,
            "local_path": local_path,
        })

    # No bucket configured: save locally
    local_path = _save_audiomack_xml_local(xml, upc)
    msg = f"DDEX built for Audiomack (UPC {upc})."
    if local_path:
        msg += f" XML saved to {local_path}. Set AWS_STORAGE_BUCKET_NAME in .env to upload to your S3."
    else:
        msg += " Set AWS_STORAGE_BUCKET_NAME in .env to upload to your S3."
    return (True, None, {
        "message": msg,
        "upc": upc,
        "s3_key": "",
        "xml_built": True,
        "local_path": local_path,
    })


def deliver_takedown_to_audiomack(release: Release) -> Tuple[bool, str, Dict[str, Any]]:
    """
    Build DDEX PurgeReleaseMessage for Audiomack and upload to S3 (Audiomack bucket or your bucket).
    Returns (success, error_message, detail_dict). Use when a takedown is requested for this release.
    """
    upc = (getattr(release, "upc", None) or "").strip() or str(release.id)
    upc = normalize_upc_to_13(upc) or upc
    try:
        xml = build_audiomack_takedown_message(release)
    except Exception as e:
        logger.exception("Audiomack takedown DDEX build failed for release %s: %s", release.id, e)
        return (False, f"Takedown DDEX build failed: {e}", {"xml_built": False, "upc": upc})

    our_bucket = (getattr(settings, "AWS_STORAGE_BUCKET_NAME", None) or "").strip()
    audiomack_bucket = (os.getenv("AUDIOMACK_S3_BUCKET") or "").strip()
    delivery_id = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")

    if audiomack_bucket:
        prefix = (os.getenv("AUDIOMACK_S3_PREFIX") or "coin-digital").strip().rstrip("/")
        s3_key = f"{prefix}/takedown/{delivery_id}/{upc}_PurgeRelease.xml"
        upload_ok, upload_err = _upload_xml_to_s3(xml, audiomack_bucket, s3_key)
        if upload_ok:
            return (True, None, {
                "message": f"Audiomack takedown (PurgeRelease) uploaded. UPC: {upc}.",
                "upc": upc,
                "s3_bucket": audiomack_bucket,
                "s3_key": s3_key,
            })
        return (False, upload_err or "S3 upload failed", {"upc": upc, "s3_key": s3_key})

    if our_bucket:
        s3_key = f"ddex/audiomack/takedown/{delivery_id}/{upc}_PurgeRelease.xml"
        upload_ok, upload_err = _upload_xml_to_s3(xml, our_bucket, s3_key)
        if upload_ok:
            return (True, None, {
                "message": f"Audiomack takedown saved to your S3. UPC: {upc}.",
                "upc": upc,
                "s3_bucket": our_bucket,
                "s3_key": s3_key,
            })
        return (False, upload_err or "S3 upload failed", {"upc": upc, "s3_key": s3_key})

    local_path = _save_audiomack_xml_local(xml, f"{upc}_PurgeRelease")
    return (True, None, {
        "message": f"Audiomack takedown built (UPC {upc}). No S3; saved locally." + (f" Path: {local_path}" if local_path else ""),
        "upc": upc,
        "local_path": local_path,
    })
