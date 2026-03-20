"""
TikTok DDEX delivery: build DDEX ERN 4.3 for TikTok (UGC deal profile) and upload to TikTok S3.
Uses env: TIKTOK_S3_BUCKET, TIKTOK_S3_PREFIX, TIKTOK_AWS_ACCESS_KEY_ID, TIKTOK_AWS_SECRET_ACCESS_KEY.
Layout: prefix/{batch_id}/{upc}.xml and prefix/{batch_id}/resources/ (cover + audio).
ByteDance sample requires MD5 HashSum for each file; we compute and inject them when building the XML.
"""
import hashlib
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple

from releases.audiomack_delivery import (
    _assign_upc_isrc_if_needed,
    _s3_bucket_key_from_url,
)
from releases.ddex_builder import build_new_release_message, build_takedown_message
from releases.models import Release, Track
from releases.upc_utils import normalize_upc_to_13

logger = logging.getLogger(__name__)


def _get_tiktok_s3_client():
    """Return boto3 S3 client using TikTok credentials (TIKTOK_AWS_ACCESS_KEY_ID, TIKTOK_AWS_SECRET_ACCESS_KEY)."""
    import boto3
    ak = (os.getenv("TIKTOK_AWS_ACCESS_KEY_ID") or "").strip()
    sk = (os.getenv("TIKTOK_AWS_SECRET_ACCESS_KEY") or "").strip()
    if not ak or not sk:
        raise ValueError("TIKTOK_AWS_ACCESS_KEY_ID and TIKTOK_AWS_SECRET_ACCESS_KEY must be set in .env")
    return boto3.client(
        "s3",
        aws_access_key_id=ak,
        aws_secret_access_key=sk,
    )


def _upload_tiktok_to_s3(
    release: Release,
    upc: str,
    xml_content: str,
    batch_id: str,
    tiktok_bucket: str,
    tiktok_prefix: str,
    default_bucket: str,
) -> Tuple[bool, str]:
    """
    Upload TikTok package to TikTok S3: XML at prefix/{batch_id}/{upc}.xml,
    resources at prefix/{batch_id}/resources/ (coverart.jpg, 1_1.flac, ...).
    Reads assets from release's current S3 URLs (our bucket); writes to TikTok bucket with TikTok credentials.
    """
    try:
        s3_tiktok = _get_tiktok_s3_client()
    except ValueError as e:
        return (False, str(e))
    try:
        from .processor import processor
        s3_ours = processor.get_s3_client()
    except Exception as e:
        return (False, f"Our S3 client: {e}")

    base = (tiktok_prefix or "").strip().rstrip("/")
    delivery_prefix = f"{base}/{batch_id}/" if base else f"{batch_id}/"
    resources_prefix = delivery_prefix + "resources/"

    # Upload XML
    xml_key = f"{delivery_prefix}{upc}.xml"
    try:
        s3_tiktok.put_object(
            Bucket=tiktok_bucket,
            Key=xml_key,
            Body=xml_content.encode("utf-8"),
            ContentType="application/xml",
        )
        logger.info("TikTok S3: uploaded %s", xml_key)
    except Exception as e:
        return (False, f"TikTok S3 XML upload failed: {e}")

    # Upload cover + audio (read from our bucket, write to TikTok bucket)
    files: List[Tuple[str, str, str]] = []
    cover_url = getattr(release, "cover_art_url", None) or ""
    if cover_url:
        b, k = _s3_bucket_key_from_url(cover_url, default_bucket)
        if k:
            files.append(("coverart.jpg", b, k))
    for idx, track in enumerate(Track.objects.filter(release=release).order_by("id")):
        audio_url = getattr(track, "audio_track_url", None) or ""
        if not audio_url:
            continue
        b, k = _s3_bucket_key_from_url(audio_url, default_bucket)
        if k:
            files.append((f"1_{idx + 1}.flac", b, k))

    for remote_name, src_bucket, src_key in files:
        try:
            obj = s3_ours.get_object(Bucket=src_bucket, Key=src_key)
            body = obj["Body"].read()
            s3_tiktok.put_object(
                Bucket=tiktok_bucket,
                Key=resources_prefix + remote_name,
                Body=body,
            )
            logger.info("TikTok S3: uploaded resources/%s", remote_name)
        except Exception as e:
            logger.warning("TikTok S3: failed to upload resources/%s: %s", remote_name, e)
            return (False, f"Resources upload failed: {e}")

    return (True, None)


def _compute_resource_md5_map(release: Release, default_bucket: str) -> Tuple[Dict[str, str], str]:
    """
    Build resource_md5_map for ByteDance: keys are 'resources/coverart.jpg', 'resources/1_1.flac', ...
    Values are MD5 hex digests. Returns (map, error). If error non-empty, map may be partial.
    """
    try:
        from .processor import processor
        s3 = processor.get_s3_client()
    except Exception as e:
        return ({}, f"S3 client: {e}")

    resource_md5_map: Dict[str, str] = {}
    files: List[Tuple[str, str, str]] = []  # (resources/name, bucket, key)
    cover_url = getattr(release, "cover_art_url", None) or ""
    if cover_url:
        b, k = _s3_bucket_key_from_url(cover_url, default_bucket)
        if k:
            files.append(("resources/coverart.jpg", b, k))
    for idx, track in enumerate(Track.objects.filter(release=release).order_by("id")):
        audio_url = getattr(track, "audio_track_url", None) or ""
        if not audio_url:
            continue
        b, k = _s3_bucket_key_from_url(audio_url, default_bucket)
        if k:
            files.append((f"resources/1_{idx + 1}.flac", b, k))

    for uri_key, bucket, key in files:
        try:
            obj = s3.get_object(Bucket=bucket, Key=key)
            body = obj["Body"].read()
            resource_md5_map[uri_key] = hashlib.md5(body).hexdigest().lower()
        except Exception as e:
            logger.warning("TikTok MD5: failed to read %s: %s", uri_key, e)
            return (resource_md5_map, f"Could not read {uri_key}: {e}")
    return (resource_md5_map, "")


def deliver_release_to_tiktok(release: Release) -> Tuple[bool, str, Dict[str, Any]]:
    """
    Build DDEX ERN 4.3 for TikTok (UGC deal profile) and upload to TikTok S3.
    ByteDance sample requires MD5 HashSum per file; we compute and add them to the XML.
    Assigns UPC/ISRC if needed. Returns (success, error_message, detail_dict).
    detail_dict includes batch_id and upc so you can report them to TikTok.
    """
    ok, err = _assign_upc_isrc_if_needed(release)
    if not ok:
        return (False, err or "UPC/ISRC assignment failed", {})

    upc = (release.upc or "").strip() or str(release.id)
    upc = normalize_upc_to_13(upc) or upc

    our_bucket = (os.getenv("AWS_STORAGE_BUCKET_NAME") or "").strip() or "coindigital-media"
    resource_md5_map, md5_err = _compute_resource_md5_map(release, our_bucket)
    if md5_err and not resource_md5_map:
        return (False, f"TikTok: could not compute MD5 for resources: {md5_err}", {"xml_built": False})
    if md5_err:
        logger.warning("TikTok: partial MD5 map: %s", md5_err)

    try:
        xml = build_new_release_message(release, store="tiktok", resource_md5_map=resource_md5_map or None)
    except Exception as e:
        logger.exception("TikTok DDEX build failed for release %s: %s", release.id, e)
        return (False, f"TikTok DDEX build failed: {e}", {"xml_built": False})

    tiktok_bucket = (os.getenv("TIKTOK_S3_BUCKET") or "").strip()
    tiktok_prefix = (os.getenv("TIKTOK_S3_PREFIX") or "").strip().rstrip("/")
    if not tiktok_bucket:
        return (False, "TikTok S3 not configured. Set TIKTOK_S3_BUCKET (and TIKTOK_S3_PREFIX, TIKTOK_AWS_ACCESS_KEY_ID, TIKTOK_AWS_SECRET_ACCESS_KEY) in .env.", {
            "message": "TikTok DDEX built but delivery skipped (no TIKTOK_S3_BUCKET).",
            "upc": upc,
            "xml_built": True,
        })

    batch_id = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")

    s3_ok, s3_err = _upload_tiktok_to_s3(
        release, upc, xml, batch_id, tiktok_bucket, tiktok_prefix, our_bucket
    )
    if s3_ok:
        return (True, None, {
            "message": f"DDEX for TikTok delivered to S3. Batch ID: {batch_id}, UPC: {upc}.",
            "upc": upc,
            "batch_id": batch_id,
            "xml_built": True,
            "tiktok_s3_uploaded": True,
        })
    return (False, s3_err or "TikTok S3 upload failed", {
        "message": f"TikTok: {s3_err or 'upload failed'}",
        "upc": upc,
        "batch_id": batch_id,
        "xml_built": True,
        "tiktok_s3_uploaded": False,
        "tiktok_s3_error": s3_err,
    })


def deliver_takedown_to_tiktok(release: Release) -> Tuple[bool, str, Dict[str, Any]]:
    """
    Build ERN 4.3 PurgeReleaseMessage (takedown) for TikTok and upload to TikTok S3.
    Path: {prefix}/takedown/{batch_id}/{upc}_PurgeRelease.xml.
    Returns (success, error_message, detail_dict). Use when a takedown is requested for this release.
    """
    from releases.audiomack_delivery import _assign_upc_isrc_if_needed

    ok, err = _assign_upc_isrc_if_needed(release)
    if not ok:
        return (False, err or "UPC/ISRC assignment failed", {})

    upc = (release.upc or "").strip() or str(release.id)
    upc = normalize_upc_to_13(upc) or upc

    try:
        xml = build_takedown_message(release, store="tiktok")
    except Exception as e:
        logger.exception("TikTok takedown DDEX build failed for release %s: %s", release.id, e)
        return (False, f"TikTok takedown XML build failed: {e}", {"upc": upc, "tiktok_takedown_uploaded": False})

    tiktok_bucket = (os.getenv("TIKTOK_S3_BUCKET") or "").strip()
    tiktok_prefix = (os.getenv("TIKTOK_S3_PREFIX") or "").strip().rstrip("/")
    if not tiktok_bucket:
        return (False, "TikTok S3 not configured. Set TIKTOK_S3_BUCKET for takedown.", {
            "message": f"TikTok takedown XML built (UPC {upc}). Upload skipped (no TIKTOK_S3_BUCKET).",
            "upc": upc,
            "tiktok_takedown_uploaded": False,
        })

    batch_id = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    base = (tiktok_prefix or "").strip().rstrip("/")
    takedown_prefix = f"{base}/takedown/{batch_id}/" if base else f"takedown/{batch_id}/"
    xml_key = f"{takedown_prefix}{upc}_PurgeRelease.xml"

    try:
        s3_tiktok = _get_tiktok_s3_client()
        s3_tiktok.put_object(
            Bucket=tiktok_bucket,
            Key=xml_key,
            Body=xml.encode("utf-8"),
            ContentType="application/xml",
        )
        logger.info("TikTok S3: uploaded takedown %s", xml_key)
        return (True, None, {
            "message": f"TikTok takedown sent to S3. UPC: {upc}. Path: {xml_key}",
            "upc": upc,
            "batch_id": batch_id,
            "tiktok_takedown_uploaded": True,
        })
    except Exception as e:
        logger.warning("TikTok S3 takedown upload failed: %s", e)
        return (False, str(e), {
            "message": f"TikTok takedown upload failed: {e}",
            "upc": upc,
            "tiktok_takedown_uploaded": False,
            "tiktok_takedown_error": str(e),
        })
