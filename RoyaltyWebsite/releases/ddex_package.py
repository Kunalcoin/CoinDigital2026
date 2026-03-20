"""
DDEX package: build once on submit-for-approval, distribute on admin approve.
Package is stored in our S3 at ddex/packages/<release_id>/<upc>/ (<upc>.xml, <upc>.json + resources/).
"""
import hashlib
import json
import logging
import os
from typing import Any, Dict, List, Tuple

from releases.ddex_builder import build_new_release_message
from releases.models import Release, Track
from releases.upc_utils import normalize_upc_to_13

logger = logging.getLogger(__name__)


def _get_our_bucket() -> str:
    from django.conf import settings
    return (getattr(settings, "AWS_STORAGE_BUCKET_NAME", None) or os.getenv("AWS_STORAGE_BUCKET_NAME") or "").strip() or "coindigital-media"


def get_package_s3_prefix(release: Release) -> str:
    """S3 prefix for this release's DDEX package: ddex/packages/<release_id>/<upc>/"""
    upc = (release.upc or "").strip() or str(release.id)
    upc = normalize_upc_to_13(upc) or upc
    return f"ddex/packages/{release.id}/{upc}/"


def _package_upc(release: Release) -> str:
    """Normalized 13-digit UPC for package paths and manifest filenames."""
    upc = (release.upc or "").strip() or str(release.id)
    return normalize_upc_to_13(upc) or upc


def get_manifest_xml_key(release: Release) -> str:
    """Full S3 key for the DDEX XML manifest: ddex/packages/<release_id>/<upc>/<upc>.xml"""
    prefix = get_package_s3_prefix(release)
    upc = _package_upc(release)
    return f"{prefix}{upc}.xml"


def get_manifest_json_key(release: Release) -> str:
    """Full S3 key for the package metadata JSON: ddex/packages/<release_id>/<upc>/<upc>.json"""
    prefix = get_package_s3_prefix(release)
    upc = _package_upc(release)
    return f"{prefix}{upc}.json"


def package_exists(release: Release) -> bool:
    """True if the DDEX package (<upc>.xml or legacy manifest.xml) already exists in our S3 for this release."""
    try:
        from .processor import processor
        s3 = processor.get_s3_client()
    except Exception:
        return False
    bucket = _get_our_bucket()
    prefix = get_package_s3_prefix(release).rstrip("/")
    # New naming: <upc>.xml
    key = get_manifest_xml_key(release)
    try:
        s3.head_object(Bucket=bucket, Key=key)
        return True
    except Exception:
        pass
    # Legacy naming: manifest.xml (for packages created before UPC-based filenames)
    legacy_key = f"{prefix}/manifest.xml"
    try:
        s3.head_object(Bucket=bucket, Key=legacy_key)
        return True
    except Exception:
        return False


def _s3_bucket_key_from_url(url: str, default_bucket: str) -> Tuple[str, str]:
    """Parse S3 URL to (bucket, key). Handles virtual-hosted and path-style URLs."""
    if not url or not isinstance(url, str):
        return (default_bucket, "")
    from urllib.parse import urlparse
    url = url.strip()
    if not url.startswith("http"):
        return (default_bucket, url.lstrip("/"))
    try:
        parsed = urlparse(url)
        path = (parsed.path or "").lstrip("/")
        host = (parsed.hostname or "").lower()
        # Path-style: https://s3.amazonaws.com/bucket/key or https://s3.region.amazonaws.com/bucket/key
        if host in ("s3.amazonaws.com",) or (host.startswith("s3.") and host.endswith(".amazonaws.com")):
            parts = path.split("/", 1)
            if len(parts) >= 2 and parts[0]:
                return (parts[0], parts[1])
            return (default_bucket, path or "")
        # Virtual-hosted: https://bucket.s3.region.amazonaws.com/key
        if ".s3." in host and "amazonaws.com" in host:
            bucket = host.split(".s3.")[0]
            key = path
            if bucket and bucket != "s3":
                return (bucket, key)
        # Fallback: path might be "bucket/key"
        if path:
            parts = path.split("/", 1)
            if len(parts) >= 2 and parts[0]:
                return (parts[0], parts[1])
        return (default_bucket, path or "")
    except Exception:
        return (default_bucket, url.lstrip("/"))


def build_ddex_package_and_save_to_s3(release: Release) -> Tuple[bool, str]:
    """
    Build canonical DDEX package (ERN 4.3 XML + cover + audio) and save to our S3.
    Call this when user submits for approval. Does not assign UPC/ISRC (caller must ensure they are set).
    Returns (True, None) or (False, error_message).
    """
    upc = (release.upc or "").strip() or str(release.id)
    upc = normalize_upc_to_13(upc) or upc
    bucket = _get_our_bucket()
    prefix = get_package_s3_prefix(release).rstrip("/")

    try:
        from .processor import processor
        s3 = processor.get_s3_client()
    except Exception as e:
        return (False, f"S3 client: {e}")

    # Build canonical XML (generic ERN 4.3; store="spotify" for default recipient)
    try:
        xml_content = build_new_release_message(release, store="spotify")
    except Exception as e:
        logger.exception("DDEX build failed for release %s: %s", release.id, e)
        return (False, f"DDEX build failed: {e}")

    # Upload <upc>.xml
    manifest_key = get_manifest_xml_key(release)
    try:
        s3.put_object(
            Bucket=bucket,
            Key=manifest_key,
            Body=xml_content.encode("utf-8"),
            ContentType="application/xml",
        )
        logger.info("Package: uploaded %s", manifest_key)
    except Exception as e:
        return (False, f"Failed to upload manifest: {e}")

    # Copy resources (cover + audio) to package prefix/resources/
    resources_prefix = f"{prefix}/resources/"
    resource_md5_map: Dict[str, str] = {}
    copied = 0
    errors: List[str] = []

    cover_url = getattr(release, "cover_art_url", None) or ""
    if cover_url:
        src_bucket, src_key = _s3_bucket_key_from_url(cover_url, bucket)
        if src_key:
            try:
                obj = s3.get_object(Bucket=src_bucket, Key=src_key)
                body = obj["Body"].read()
                s3.put_object(Bucket=bucket, Key=resources_prefix + "coverart.jpg", Body=body)
                resource_md5_map["resources/coverart.jpg"] = hashlib.md5(body).hexdigest().lower()
                copied += 1
            except Exception as e:
                errors.append(f"Cover: {e}")

    # Per track: copy FLAC (required for delivery), and WAV + MP3 when available (agreed: XML + Poster + WAV + FLAC + MP3 in package).
    tracks_ordered = list(Track.objects.filter(release=release).order_by("sequence", "id"))
    for idx, track in enumerate(tracks_ordered):
        base_name = f"1_{idx + 1}"
        # FLAC (primary for DDEX delivery)
        flac_url = getattr(track, "audio_flac_url", None) or getattr(track, "audio_track_url", None) or ""
        if flac_url:
            src_bucket, src_key = _s3_bucket_key_from_url(flac_url, bucket)
            if src_key:
                try:
                    obj = s3.get_object(Bucket=src_bucket, Key=src_key)
                    body = obj["Body"].read()
                    dest_name = f"{base_name}.flac"
                    s3.put_object(Bucket=bucket, Key=resources_prefix + dest_name, Body=body)
                    resource_md5_map[f"resources/{dest_name}"] = hashlib.md5(body).hexdigest().lower()
                    copied += 1
                except Exception as e:
                    errors.append(f"Track {idx + 1} FLAC: {e}")
        # WAV
        wav_url = getattr(track, "audio_wav_url", None) or ""
        if wav_url:
            src_bucket, src_key = _s3_bucket_key_from_url(wav_url, bucket)
            if src_key:
                try:
                    obj = s3.get_object(Bucket=src_bucket, Key=src_key)
                    body = obj["Body"].read()
                    dest_name = f"{base_name}.wav"
                    s3.put_object(Bucket=bucket, Key=resources_prefix + dest_name, Body=body)
                    resource_md5_map[f"resources/{dest_name}"] = hashlib.md5(body).hexdigest().lower()
                    copied += 1
                except Exception as e:
                    errors.append(f"Track {idx + 1} WAV: {e}")
        # MP3
        mp3_url = getattr(track, "audio_mp3_url", None) or ""
        if mp3_url:
            src_bucket, src_key = _s3_bucket_key_from_url(mp3_url, bucket)
            if src_key:
                try:
                    obj = s3.get_object(Bucket=src_bucket, Key=src_key)
                    body = obj["Body"].read()
                    dest_name = f"{base_name}.mp3"
                    s3.put_object(Bucket=bucket, Key=resources_prefix + dest_name, Body=body)
                    resource_md5_map[f"resources/{dest_name}"] = hashlib.md5(body).hexdigest().lower()
                    copied += 1
                except Exception as e:
                    errors.append(f"Track {idx + 1} MP3: {e}")

    if copied == 0:
        return (False, "No resources (cover or audio) could be copied. Check release has cover_art_url and each track has audio (FLAC/WAV/MP3).")

    # Optional: save <upc>.json with MD5 map for TikTok (and any store that needs it)
    try:
        meta = {
            "upc": upc,
            "release_id": release.id,
            "resource_md5_map": resource_md5_map,
        }
        metadata_key = get_manifest_json_key(release)
        s3.put_object(
            Bucket=bucket,
            Key=metadata_key,
            Body=json.dumps(meta, indent=2).encode("utf-8"),
            ContentType="application/json",
        )
    except Exception as e:
        logger.warning("Package: could not write %s: %s", get_manifest_json_key(release), e)

    if errors:
        logger.warning("Package: built with errors: %s", errors)
    return (True, None)
