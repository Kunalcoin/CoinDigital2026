"""
Apple Music delivery via Merlin Bridge: build Apple iTunes Importer (music5.3) XML and upload
to Merlin Bridge SFTP using SSH-RSA key authentication (no password).
Per Merlin Bridge: package must use extension .itmsp (e.g. {UPC}.itmsp). We build a zip-format package
(metadata.xml and assets at root) and upload it as {upc}.itmsp to apple/regular/.
See MERLIN_BRIDGE_APPLE_MUSIC.md for Bridge dashboard steps and env vars.
"""
import errno
import hashlib
import logging
import os
import re
import zipfile
import tempfile
from io import BytesIO, StringIO
from typing import Any, Dict, List, Optional, Tuple, Union

from django.conf import settings

from releases.apple_itunes_importer import build_apple_itunes_metadata, build_apple_itunes_takedown_metadata
from releases.audiomack_delivery import (
    _assign_upc_isrc_if_needed,
    _s3_bucket_key_from_url,
)
from releases.ddex_config import COIN_DIGITAL_PARTY_ID
from releases.models import Release, Track
from releases.upc_utils import normalize_upc_to_13

logger = logging.getLogger(__name__)

JPEG_MAGIC = b"\xFF\xD8\xFF"


class MerlinDownloadCancelled(Exception):
    """Raised when a distribution job is cancelled during a large S3 read (e.g. Dolby Atmos)."""




def _release_apple_atmos_enabled(release: Release) -> bool:
    """True when release owner may deliver Dolby Atmos (per-user admin flag on CDUser)."""
    u = getattr(release, "created_by", None)
    return bool(u and getattr(u, "apple_music_dolby_atmos_enabled", False))


def _validate_apple_preorder_vs_street(release: Release) -> Tuple[bool, str]:
    """
    Apple / Merlin: preorder_sales_start_date in XML must be strictly before the street date
    we send (digital_release_date, else original_release_date). Bridge "Release Date" follows
    those XML dates—not manual edits on the Bridge UI.
    """
    po = getattr(release, "apple_music_preorder_start_date", None)
    if not po:
        return (True, "")
    rel_date = release.digital_release_date or release.original_release_date
    if not rel_date:
        return (
            False,
            "Apple Music pre-order sales start date is set, but Digital release date and Original release date "
            "are both empty. Set Digital release date (street/on-sale date) in Django admin, then deliver again.",
        )
    if po >= rel_date:
        return (
            False,
            f"Apple requires pre-order start BEFORE street date. Pre-order is {po}, "
            f"but street date (Digital or Original release date) is {rel_date}. "
            f"Update Digital release date to a date AFTER {po}, save, then run deliver again. "
            "Changing the date only on the Merlin Bridge dashboard does not update the feed—Coin Digital must re-deliver.",
        )
    return (True, "")


def _validate_apple_preorder_vs_commercial_model(release: Release) -> Tuple[bool, str]:
    """
    Apple ITMS-4020: preorder_sales_start_date is rejected on retail/download-only offers.
    Do not combine Apple Music pre-order date with commercial model 'Retail / download only'.
    """
    po = getattr(release, "apple_music_preorder_start_date", None)
    if not po:
        return (True, "")
    mode = (getattr(release, "apple_music_commercial_model", None) or "both").strip().lower()
    if mode == "retail_only":
        return (
            False,
            "Apple ITMS-4020: pre-order is not allowed on the Retail/download-only offer. "
            "Clear 'Apple Music pre-order sales start date' for this UPC, or set "
            "'Apple Music commercial model' to 'Streaming + download (default)' (or Streaming only) "
            "for pre-order + instant grat. Keep retail-only checklist releases on a separate UPC without pre-order.",
        )
    return (True, "")


def _validate_apple_instant_grat_for_preorder(release: Release) -> Tuple[bool, str]:
    """
    With a pre-order, Apple allows up to half the tracks as instant gratification; more fails ingestion.
    metadata.xml emits <preorder_type> on each <track> (not inside <product>): instant-gratification vs standard.
    """
    po = getattr(release, "apple_music_preorder_start_date", None)
    if not po:
        return (True, "")
    mode = (getattr(release, "apple_music_commercial_model", None) or "both").strip().lower()
    if mode == "retail_only":
        return (True, "")
    tracks = list(Track.objects.filter(release=release).order_by("id"))
    n = len(tracks)
    if n == 0:
        return (True, "")
    ig = sum(1 for t in tracks if getattr(t, "apple_music_instant_grat", False))
    # Apple: at most 50% of tracks may be IG (e.g. 5 of 10). Singles (n==1) are treated as max 1 IG.
    max_ig = 1 if n == 1 else n // 2
    if ig > max_ig:
        return (
            False,
            f"Apple Music pre-order / instant grat: at most half the tracks may be IG ({max_ig} of {n}); "
            f"currently {ig} marked. Unmark some tracks or add more tracks to the release.",
        )
    if ig == 0:
        logger.warning(
            "Release id=%s: pre-order is set but no tracks are marked Apple Music instant gratification. "
            "Some Apple Music pre-order / pre-add flows expect at least one IG track (see Apple Music Spec).",
            release.id,
        )
    return (True, "")


PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


def _ensure_jpeg_bytes(cover_bytes: bytes, desired_jpeg_quality: int = 95) -> Tuple[bytes, bool]:
    """
    Ensure artwork bytes are valid JPEG bytes.
    Bridge validates artwork content as JPEG/PNG. We always deliver filename as .jpg,
    so we convert PNG/WebP/etc to JPEG if needed.

    Returns: (bytes, was_converted)
    """
    if cover_bytes.startswith(JPEG_MAGIC):
        return cover_bytes, False
    if not cover_bytes or len(cover_bytes) < 4:
        return cover_bytes, False

    try:
        from PIL import Image
    except Exception:
        # If Pillow isn't available, we can't reliably convert; keep original bytes.
        return cover_bytes, False

    try:
        img = Image.open(BytesIO(cover_bytes))
        # Convert to RGB to avoid alpha/channel issues when saving JPEG
        img = img.convert("RGB")
        out = BytesIO()
        img.save(out, format="JPEG", quality=desired_jpeg_quality, optimize=True)
        return out.getvalue(), True
    except Exception:
        # If it cannot be opened/converted, keep original bytes; later validation will tell us.
        return cover_bytes, False


def _load_merlin_bridge_pkey():
    """
    Load SSH private key for Merlin Bridge SFTP.
    Uses MERLIN_BRIDGE_SFTP_PRIVATE_KEY_PATH (file path) or MERLIN_BRIDGE_SFTP_PRIVATE_KEY (PEM string).
    Tries paramiko first; if OpenSSH key fails with checksum error, uses cryptography to load and convert to PEM.
    Returns (pkey, None) or (None, error_message).
    """
    try:
        import paramiko
    except ImportError:
        return (None, "paramiko not installed. pip install paramiko")

    key_path = (os.getenv("MERLIN_BRIDGE_SFTP_PRIVATE_KEY_PATH") or "").strip()
    key_content = (os.getenv("MERLIN_BRIDGE_SFTP_PRIVATE_KEY") or "").strip()
    raw_pass = (os.getenv("MERLIN_BRIDGE_SFTP_KEY_PASSPHRASE") or "").strip()
    passphrase = raw_pass.strip('"\'') if raw_pass else None

    if key_path and key_content:
        return (None, "Set either MERLIN_BRIDGE_SFTP_PRIVATE_KEY_PATH or MERLIN_BRIDGE_SFTP_PRIVATE_KEY, not both.")
    if not key_path and not key_content:
        return (None, "Set MERLIN_BRIDGE_SFTP_PRIVATE_KEY_PATH or MERLIN_BRIDGE_SFTP_PRIVATE_KEY for SSH key auth.")

    def try_paramiko():
        if key_path:
            if not os.path.isfile(key_path):
                return (None, f"Private key file not found: {key_path}")
            return (paramiko.RSAKey.from_private_key_file(key_path, password=passphrase), None)
        return (paramiko.RSAKey.from_private_key(StringIO(key_content), password=passphrase), None)

    try:
        pkey, _ = try_paramiko()
        return (pkey, None)
    except paramiko.ssh_exception.SSHException as e:
        err_msg = str(e)
        if "checkints do not match" in err_msg or "checksum" in err_msg.lower():
            try:
                from cryptography.hazmat.primitives.serialization import (
                    load_ssh_private_key,
                    Encoding,
                    PrivateFormat,
                    NoEncryption,
                )
                from cryptography.hazmat.backends import default_backend
            except ImportError:
                return (
                    None,
                    "Invalid SSH key or passphrase: OpenSSH key checksum failed. "
                    "Install cryptography for better OpenSSH support: pip install cryptography. "
                    "Or verify the key passphrase with: ssh-keygen -y -f \"{}\"".format(key_path or "key"),
                )
            try:
                if key_path:
                    key_data = open(key_path, "rb").read()
                else:
                    key_data = key_content.encode("utf-8")
                password_bytes = passphrase.encode("utf-8") if passphrase else None
                priv = load_ssh_private_key(key_data, password=password_bytes, backend=default_backend())
                if priv is None:
                    return (None, "Invalid SSH key or passphrase: could not load key.")
                from cryptography.hazmat.primitives.asymmetric import rsa
                if not isinstance(priv, rsa.RSAPrivateKey):
                    return (None, "Merlin Bridge requires an SSH-RSA key; this key is not RSA.")
                pem = priv.private_bytes(
                    encoding=Encoding.PEM,
                    format=PrivateFormat.TraditionalOpenSSL,
                    encryption_algorithm=NoEncryption(),
                )
                pkey = paramiko.RSAKey.from_private_key(StringIO(pem.decode("utf-8")))
                return (pkey, None)
            except Exception as cryp_e:
                return (
                    None,
                    "Invalid SSH key or passphrase: OpenSSH checksum failed and cryptography fallback failed ({}). "
                    "Verify passphrase with: ssh-keygen -y -f \"{}\"".format(cryp_e, key_path or "key"),
                )
        return (None, f"Invalid SSH key or passphrase: {e}")
    except Exception as e:
        return (None, f"Failed to load SSH key: {e}")


def open_merlin_bridge_sftp():
    """
    Connect to Merlin Bridge SFTP. Returns (sftp, transport, None) or (None, None, error_msg).
    Caller must close transport when done.
    """
    host = (os.getenv("MERLIN_BRIDGE_SFTP_HOST") or "").strip()
    if not host:
        return (None, None, "MERLIN_BRIDGE_SFTP_HOST not set")
    port = int((os.getenv("MERLIN_BRIDGE_SFTP_PORT") or "22").strip())
    username = (os.getenv("MERLIN_BRIDGE_SFTP_USERNAME") or "").strip()
    if not username:
        return (None, None, "MERLIN_BRIDGE_SFTP_USERNAME not set")
    pkey, key_err = _load_merlin_bridge_pkey()
    if key_err:
        return (None, None, key_err)
    try:
        import paramiko
        transport = paramiko.Transport((host, port))
        transport.connect(username=username, pkey=pkey)
        sftp = paramiko.SFTPClient.from_transport(transport)
        return (sftp, transport, None)
    except Exception as e:
        return (None, None, str(e))


def _gather_apple_assets_and_file_info(
    release: Release,
    upc: str,
    default_bucket: str,
    progress=None,
    distribution_job_id: Optional[int] = None,
) -> Tuple[Dict[str, Dict[str, Any]], List[Tuple[str, Union[bytes, str]]], str]:
    """
    Fetch artwork + audio from S3, compute size and MD5. Return (file_info, list of (remote_name, body), audio_ext).
    file_info is passed to build_apple_itunes_metadata; list is used for SFTP upload.
    """
    def prog(msg: str) -> None:
        if progress:
            progress(msg)

    try:
        import boto3

        s3 = boto3.client(
            "s3",
            aws_access_key_id=getattr(settings, "AWS_ACCESS_KEY_ID", None),
            aws_secret_access_key=getattr(settings, "AWS_SECRET_ACCESS_KEY", None),
            config=_merlin_bridge_s3_boto_config(),
        )
    except Exception as e:
        raise RuntimeError(f"S3 client: {e}") from e

    file_info: Dict[str, Dict[str, Any]] = {}
    to_upload: List[Tuple[str, Union[bytes, str]]] = []
    audio_ext = "wav"

    cover_url = getattr(release, "cover_art_url", None) or ""
    if cover_url:
        b, k = _s3_bucket_key_from_url(cover_url, default_bucket)
        if k:
            body = _s3_get_object_bytes_with_progress(
                s3,
                b,
                k,
                prog,
                "Cover art",
                report_every_bytes=5 * 1024 * 1024,
                distribution_job_id=distribution_job_id,
            )

            # Bridge validation expects actual JPEG/PNG bytes; our filename is always .jpg,
            # so convert any non-JPEG source (often PNG) into real JPEG bytes.
            body_converted, was_converted = _ensure_jpeg_bytes(body)
            md5 = hashlib.md5(body_converted).hexdigest().lower()
            file_info["artwork"] = {"size": len(body_converted), "md5": md5}
            to_upload.append((f"{upc}.jpg", body_converted))
            logger.info(
                "Artwork: %s bytes, md5=%s (converted=%s)",
                len(body_converted),
                md5,
                was_converted,
            )
        else:
            prog("Cover art URL could not be parsed to S3 key; skipping artwork.")
    else:
        prog("No cover art URL on release; skipping artwork.")

    tracks = list(Track.objects.filter(release=release).order_by("id"))
    tracks_with_audio = [(i, t) for i, t in enumerate(tracks) if (getattr(t, "audio_track_url", None) or getattr(t, "audio_wav_url", None))]
    prog("Found %s tracks with audio; fetching from S3..." % len(tracks_with_audio))
    for idx, track in tracks_with_audio:
        audio_url = getattr(track, "audio_track_url", None) or getattr(track, "audio_wav_url", None) or ""
        if not audio_url:
            continue
        b, k = _s3_bucket_key_from_url(audio_url, default_bucket)
        if not k:
            prog("Track %s: URL could not be parsed; skipping." % (idx + 1))
            continue
        remote_audio_name = f"{upc}_01_{idx + 1:03d}.{audio_ext}"
        if idx == 0 and "." in k:
            ext = k.rsplit(".", 1)[-1].lower()
            if ext in ("wav", "flac", "mp3", "aac"):
                audio_ext = ext
        remote_audio_name = f"{upc}_01_{idx + 1:03d}.{audio_ext}"

        if _s3_should_spill_to_disk(s3, b, k):
            tpath, tsz, tmd5 = _s3_stream_to_tempfile_with_md5(
                s3,
                b,
                k,
                prog,
                "Track %s/%s" % (idx + 1, len(tracks_with_audio)),
                distribution_job_id=distribution_job_id,
            )
            file_info[f"track_{idx}"] = {"size": tsz, "md5": tmd5}
            to_upload.append((remote_audio_name, tpath))
            logger.info("Track %s: %s bytes (disk), md5=%s", idx + 1, tsz, tmd5)
        else:
            body = _s3_get_object_bytes_with_progress(
                s3,
                b,
                k,
                prog,
                "Track %s/%s" % (idx + 1, len(tracks_with_audio)),
                distribution_job_id=distribution_job_id,
            )
            md5 = hashlib.md5(body).hexdigest().lower()
            file_info[f"track_{idx}"] = {"size": len(body), "md5": md5}
            to_upload.append((remote_audio_name, body))
            logger.info("Track %s: %s bytes, md5=%s", idx + 1, len(body), md5)

        if _release_apple_atmos_enabled(release):
            atmos_url = (getattr(track, "apple_music_dolby_atmos_url", None) or "").strip()
            atmos_isrc = (getattr(track, "apple_music_dolby_atmos_isrc", None) or "").strip()
            if atmos_url and atmos_isrc:
                ab, ak = _s3_bucket_key_from_url(atmos_url, default_bucket)
                if not ak:
                    prog("Track %s: Dolby Atmos URL could not be parsed; skipping Atmos file." % (idx + 1))
                else:
                    # Atmos masters are often 1GB+ — always stream to disk + incremental MD5 (avoids RAM blowups).
                    apath, asz, atmos_md5 = _s3_stream_to_tempfile_with_md5(
                        s3,
                        ab,
                        ak,
                        prog,
                        "Track %s Dolby Atmos" % (idx + 1),
                        distribution_job_id=distribution_job_id,
                    )
                    file_info[f"track_{idx}_atmos"] = {
                        "size": asz,
                        "md5": atmos_md5,
                    }
                    remote_atmos = f"{upc}_01_{idx + 1:03d}_atmos.wav"
                    to_upload.append((remote_atmos, apath))
                    logger.info(
                        "Track %s Dolby Atmos: %s bytes (disk), md5=%s",
                        idx + 1,
                        asz,
                        atmos_md5,
                    )

    return (file_info, to_upload, audio_ext)


def _etag_to_content_md5(etag_raw: str) -> str:
    """If S3 ETag is a simple object MD5, return lowercase hex; else empty (multipart)."""
    e = (etag_raw or "").strip().strip('"')
    if not e or "-" in e:
        return ""
    if len(e) == 32 and re.match(r"^[a-fA-F0-9]{32}$", e):
        return e.lower()
    return ""


def _merlin_bridge_s3_boto_config():
    """
    Timeouts for full-asset delivery: WAV/FLAC files can be hundreds of MB; default read timeout
    must be high enough for slow links between read chunks (botocore read_timeout is per recv, not total).

    Override with env: MERLIN_BRIDGE_S3_CONNECT_TIMEOUT (default 30), MERLIN_BRIDGE_S3_READ_TIMEOUT (default 600).
    """
    from botocore.config import Config

    connect = int((os.getenv("MERLIN_BRIDGE_S3_CONNECT_TIMEOUT") or "30").strip())
    read = int((os.getenv("MERLIN_BRIDGE_S3_READ_TIMEOUT") or "600").strip())
    return Config(
        connect_timeout=connect,
        read_timeout=read,
        retries={"max_attempts": 5, "mode": "standard"},
    )


def _s3_get_object_bytes_with_progress(
    s3,
    bucket: str,
    key: str,
    prog,
    label: str,
    *,
    report_every_bytes: int = 10 * 1024 * 1024,
    read_chunk_size: int = 8 * 1024 * 1024,
    distribution_job_id: Optional[int] = None,
) -> bytes:
    """
    Download full S3 object into memory with periodic progress (so long downloads do not look "stuck").
    """
    total = 0
    try:
        head = s3.head_object(Bucket=bucket, Key=key)
        total = int(head.get("ContentLength") or 0)
    except Exception as head_exc:
        logger.debug("HeadObject before GetObject %s/%s: %s", bucket, key, head_exc)

    key_disp = (key[:70] + "…") if len(key) > 70 else key
    if total > 0:
        prog("%s (~%.1f MB) bucket=%s key=%s — downloading..." % (label, total / (1024 * 1024), bucket, key_disp))
    else:
        prog("%s bucket=%s key=%s — downloading..." % (label, bucket, key_disp))

    obj = s3.get_object(Bucket=bucket, Key=key)
    body = obj["Body"]
    chunks: List[bytes] = []
    downloaded = 0
    next_report_at = report_every_bytes

    while True:
        if distribution_job_id:
            from releases.distribution_job_progress import is_distribution_job_cancel_requested

            if is_distribution_job_cancel_requested(distribution_job_id):
                prog("%s — cancelled (stop requested)." % label)
                raise MerlinDownloadCancelled(
                    "Distribution cancelled while downloading from S3 (large file)."
                )
        chunk = body.read(read_chunk_size)
        if not chunk:
            break
        chunks.append(chunk)
        downloaded += len(chunk)
        if total > 0 and downloaded >= next_report_at:
            pct = min(100.0, 100.0 * downloaded / total)
            prog(
                "  %s progress: %.1f / %.1f MB (%.0f%%)"
                % (label, downloaded / (1024 * 1024), total / (1024 * 1024), pct)
            )
            while next_report_at <= downloaded:
                next_report_at += report_every_bytes

    # Last ~2–5% in the UI often looks "stuck": network download is done but we still merge
    # ~1GB+ of chunk buffers into one bytes object (can take 1–5+ min) with no progress between
    # percentage lines. Tell the operator explicitly.
    nchunks = len(chunks)
    mb_dl = downloaded / (1024 * 1024)
    prog(
        "%s — S3 stream finished (~%.1f MB). Merging %d chunks in memory (can take 1–5 min; UI %% may pause here)…"
        % (label, mb_dl, nchunks)
    )
    data = b"".join(chunks)
    prog("%s done: %.1f MB total (merged)." % (label, len(data) / (1024 * 1024)))
    return data


def _spill_threshold_bytes() -> int:
    """Objects at or above this size use disk + streaming MD5 (avoids 2× RAM for join + hash)."""
    try:
        mb = int((os.getenv("MERLIN_BRIDGE_SPILL_TO_DISK_MB") or "500").strip())
    except ValueError:
        mb = 500
    mb = max(50, mb)
    return mb * 1024 * 1024


def _s3_should_spill_to_disk(s3, bucket: str, key: str) -> bool:
    try:
        head = s3.head_object(Bucket=bucket, Key=key)
        return int(head.get("ContentLength") or 0) >= _spill_threshold_bytes()
    except Exception:
        # If head fails, prefer disk path to avoid OOM on unknown huge objects
        return True


def _s3_stream_to_tempfile_with_md5(
    s3,
    bucket: str,
    key: str,
    prog,
    label: str,
    *,
    report_every_bytes: int = 10 * 1024 * 1024,
    read_chunk_size: int = 8 * 1024 * 1024,
    distribution_job_id: Optional[int] = None,
) -> Tuple[str, int, str]:
    """
    Stream S3 object to a temp file and compute MD5 incrementally.
    Avoids holding the full object in RAM (fixes long 'stuck at 98%' + OOM on ~1GB+ masters).

    Returns (temp_path, size_bytes, md5_hex). Caller must unlink temp_path when done.
    """
    total = 0
    try:
        head = s3.head_object(Bucket=bucket, Key=key)
        total = int(head.get("ContentLength") or 0)
    except Exception as head_exc:
        logger.debug("HeadObject before stream-to-disk %s/%s: %s", bucket, key, head_exc)

    key_disp = (key[:70] + "…") if len(key) > 70 else key
    if total > 0:
        prog(
            "%s (~%.1f MB) bucket=%s key=%s — streaming to disk (low memory)…"
            % (label, total / (1024 * 1024), bucket, key_disp)
        )
    else:
        prog("%s bucket=%s key=%s — streaming to disk…" % (label, bucket, key_disp))

    fd, path = tempfile.mkstemp(prefix="merlin_s3_", suffix=".bin")
    os.close(fd)
    h = hashlib.md5()
    downloaded = 0
    next_report_at = report_every_bytes

    try:
        obj = s3.get_object(Bucket=bucket, Key=key)
        body = obj["Body"]
        with open(path, "wb") as out:
            while True:
                if distribution_job_id:
                    from releases.distribution_job_progress import (
                        is_distribution_job_cancel_requested,
                    )

                    if is_distribution_job_cancel_requested(distribution_job_id):
                        prog("%s — cancelled (stop requested)." % label)
                        raise MerlinDownloadCancelled(
                            "Distribution cancelled while downloading from S3 (large file)."
                        )
                chunk = body.read(read_chunk_size)
                if not chunk:
                    break
                out.write(chunk)
                h.update(chunk)
                downloaded += len(chunk)
                if total > 0 and downloaded >= next_report_at:
                    pct = min(100.0, 100.0 * downloaded / total)
                    prog(
                        "  %s progress: %.1f / %.1f MB (%.0f%%)"
                        % (
                            label,
                            downloaded / (1024 * 1024),
                            total / (1024 * 1024),
                            pct,
                        )
                    )
                    while next_report_at <= downloaded:
                        next_report_at += report_every_bytes

        size = os.path.getsize(path)
        md5_hex = h.hexdigest().lower()
        prog(
            "%s done: %.1f MB on disk, md5=%s… (streaming)"
            % (label, size / (1024 * 1024), md5_hex[:12])
        )
        return (path, size, md5_hex)
    except Exception:
        try:
            os.unlink(path)
        except OSError:
            pass
        raise


def _gather_apple_metadata_update_file_info(
    release: Release,
    upc: str,
    default_bucket: str,
    progress=None,
    distribution_job_id: Optional[int] = None,
) -> Tuple[Dict[str, Dict[str, Any]], str]:
    """
    Build file_info for metadata.xml without downloading full audio files.
    Uses S3 HeadObject for size + ETag (MD5) when possible; falls back to GetObject for
    multipart ETags. Cover art still fetched and JPEG-normalized so size/MD5 match full delivery.
    Returns (file_info, audio_ext).
    """
    def prog(msg: str) -> None:
        if progress:
            progress(msg)

    try:
        import boto3

        s3 = boto3.client(
            "s3",
            aws_access_key_id=getattr(settings, "AWS_ACCESS_KEY_ID", None),
            aws_secret_access_key=getattr(settings, "AWS_SECRET_ACCESS_KEY", None),
            config=_merlin_bridge_s3_boto_config(),
        )
    except Exception as e:
        raise RuntimeError(f"S3 client: {e}") from e

    file_info: Dict[str, Dict[str, Any]] = {}
    audio_ext = "wav"

    cover_url = getattr(release, "cover_art_url", None) or ""
    if cover_url:
        b, k = _s3_bucket_key_from_url(cover_url, default_bucket)
        if k:
            prog("Metadata update: reading cover from S3 for size/MD5 (JPEG-normalized like full delivery)...")
            body = _s3_get_object_bytes_with_progress(
                s3,
                b,
                k,
                prog,
                "Cover art",
                report_every_bytes=5 * 1024 * 1024,
                distribution_job_id=distribution_job_id,
            )
            body_converted, _ = _ensure_jpeg_bytes(body)
            md5 = hashlib.md5(body_converted).hexdigest().lower()
            file_info["artwork"] = {"size": len(body_converted), "md5": md5}
        else:
            prog("Cover art URL could not be parsed to S3 key; skipping artwork in metadata.")
    else:
        prog("No cover art URL on release; artwork block in XML may be empty.")

    tracks = list(Track.objects.filter(release=release).order_by("id"))
    tracks_with_audio = [
        (i, t) for i, t in enumerate(tracks)
        if (getattr(t, "audio_track_url", None) or getattr(t, "audio_wav_url", None))
    ]
    prog("Metadata update: fetching size/MD5 per track (HeadObject; full download only if needed)...")
    for idx, track in tracks_with_audio:
        audio_url = getattr(track, "audio_track_url", None) or getattr(track, "audio_wav_url", None) or ""
        if not audio_url:
            continue
        b, k = _s3_bucket_key_from_url(audio_url, default_bucket)
        if not k:
            prog("Track %s: URL could not be parsed; skipping." % (idx + 1))
            continue
        if idx == 0 and "." in k:
            ext = k.rsplit(".", 1)[-1].lower()
            if ext in ("wav", "flac", "mp3", "aac"):
                audio_ext = ext
        try:
            head = s3.head_object(Bucket=b, Key=k)
            size = int(head.get("ContentLength") or 0)
            md5 = _etag_to_content_md5(head.get("ETag") or "")
            if not md5:
                prog("Track %s: multipart or non-MD5 ETag; downloading to compute MD5..." % (idx + 1))
                body = _s3_get_object_bytes_with_progress(
                    s3,
                    b,
                    k,
                    prog,
                    "Track %s (MD5)" % (idx + 1),
                    distribution_job_id=distribution_job_id,
                )
                size = len(body)
                md5 = hashlib.md5(body).hexdigest().lower()
            file_info[f"track_{idx}"] = {"size": size, "md5": md5}
        except Exception as e:
            logger.warning("Metadata update: track %s S3 error: %s", idx + 1, e)
            prog("Track %s: S3 error %s" % (idx + 1, e))

        if _release_apple_atmos_enabled(release):
            atmos_url = (getattr(track, "apple_music_dolby_atmos_url", None) or "").strip()
            atmos_isrc = (getattr(track, "apple_music_dolby_atmos_isrc", None) or "").strip()
            if atmos_url and atmos_isrc:
                ab, ak = _s3_bucket_key_from_url(atmos_url, default_bucket)
                if not ak:
                    prog("Track %s: Dolby Atmos URL could not be parsed (metadata-only pass)." % (idx + 1))
                else:
                    try:
                        ahead = s3.head_object(Bucket=ab, Key=ak)
                        asize = int(ahead.get("ContentLength") or 0)
                        amd5 = _etag_to_content_md5(ahead.get("ETag") or "")
                        if not amd5:
                            prog(
                                "Track %s: Atmos multipart or non-MD5 ETag; downloading for MD5..."
                                % (idx + 1)
                            )
                            abody = _s3_get_object_bytes_with_progress(
                                s3,
                                ab,
                                ak,
                                prog,
                                "Track %s Atmos (MD5)" % (idx + 1),
                                distribution_job_id=distribution_job_id,
                            )
                            asize = len(abody)
                            amd5 = hashlib.md5(abody).hexdigest().lower()
                        file_info[f"track_{idx}_atmos"] = {"size": asize, "md5": amd5}
                    except Exception as e:
                        logger.warning("Metadata update: track %s Atmos S3 error: %s", idx + 1, e)
                        prog("Track %s: Atmos S3 error %s" % (idx + 1, e))

    return (file_info, audio_ext)


def _upload_merlin_bridge_apple_to_sftp(
    release: Release,
    upc: str,
    default_bucket: str,
    progress=None,
    metadata_only: bool = False,
    distribution_job_id: Optional[int] = None,
) -> Tuple[bool, str, str]:
    """
    Upload Apple iTunes Importer package to Merlin Bridge SFTP.
    Merlin Bridge requires a final compressed file named [UPC].itmsp.zip.
    The archive is [UPC].itmsp.zip and contains a top-level directory [UPC].itmsp/
    with:
    - metadata.xml
    - {upc}.jpg
    - {upc}_01_###.<wav|flac|mp3|aac>
    If metadata_only=True: zip contains only metadata.xml — artwork and audio bytes are NOT included.
    Validators that require files named in metadata.xml will report missing binaries; use full delivery instead.
    Returns (success, error_message, sftp_path_used).
    """
    def prog(msg: str) -> None:
        if progress:
            progress(msg)

    host = (os.getenv("MERLIN_BRIDGE_SFTP_HOST") or "").strip()
    if not host:
        return (False, "MERLIN_BRIDGE_SFTP_HOST not set", "")
    port = int((os.getenv("MERLIN_BRIDGE_SFTP_PORT") or "22").strip())
    username = (os.getenv("MERLIN_BRIDGE_SFTP_USERNAME") or "").strip()
    if not username:
        return (False, "MERLIN_BRIDGE_SFTP_USERNAME not set", "")

    prog("Loading SSH key...")
    pkey, key_err = _load_merlin_bridge_pkey()
    if key_err:
        return (False, key_err, "")
    if metadata_only:
        prog("SSH key loaded. Building metadata-only package (sizes/MD5 from S3 HeadObject where possible)...")
    else:
        prog("SSH key loaded. Fetching artwork and audio from S3...")

    try:
        if metadata_only:
            file_info, audio_ext = _gather_apple_metadata_update_file_info(
                release,
                upc,
                default_bucket,
                progress=progress,
                distribution_job_id=distribution_job_id,
            )
            to_upload: List[Tuple[str, Union[bytes, str]]] = []
        else:
            file_info, to_upload, audio_ext = _gather_apple_assets_and_file_info(
                release,
                upc,
                default_bucket,
                progress=progress,
                distribution_job_id=distribution_job_id,
            )
    except MerlinDownloadCancelled as e:
        return (False, str(e), "")
    except Exception as e:
        return (False, str(e), "")
    if metadata_only:
        prog("S3 metadata gathered. Building .itmsp.zip with metadata.xml only...")
    else:
        prog(f"S3 done ({len(to_upload)} files). Building .itmsp.zip package...")

    xml_content = build_apple_itunes_metadata(release, upc, file_info=file_info, audio_extension=audio_ext)

    # Apple-style / Merlin parsing convention: the .itmsp is a *directory*.
    # The final delivery file is [UPC].itmsp.zip, which contains:
    #   [UPC].itmsp/metadata.xml
    #   [UPC].itmsp/{upc}.jpg
    #   [UPC].itmsp/{upc}_01_###.wav ...
    METADATA_FILENAME = "metadata.xml"
    PACKAGE_DIR = f"{upc}.itmsp/"
    zip_buffer = BytesIO()
    temp_paths_to_unlink: List[str] = []
    try:
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr(f"{PACKAGE_DIR}{METADATA_FILENAME}", xml_content.encode("utf-8"))
            for remote_name, body in to_upload:
                arc = f"{PACKAGE_DIR}{remote_name}"
                if isinstance(body, (bytes, bytearray)):
                    zf.writestr(arc, body)
                else:
                    p = str(body)
                    zf.write(p, arcname=arc)
                    temp_paths_to_unlink.append(p)
        zip_buffer.seek(0)
        zip_bytes = zip_buffer.getvalue()
    finally:
        for p in temp_paths_to_unlink:
            try:
                os.unlink(p)
            except OSError:
                pass
    prog(f"Package built ({len(zip_bytes) // 1024} KB). Connecting to Merlin Bridge SFTP...")

    base_path = (os.getenv("MERLIN_BRIDGE_SFTP_REMOTE_PATH") or "").strip().rstrip("/")
    if not base_path:
        prog("WARNING: MERLIN_BRIDGE_SFTP_REMOTE_PATH is not set. File will go to SFTP home; Bridge may not show it. Set to apple/regular for normal delivery.")
    else:
        prog(f"Upload path: {base_path}/ (from MERLIN_BRIDGE_SFTP_REMOTE_PATH)")
    # Upload only the final compressed file: [UPC].itmsp.zip
    remote_package = f"{base_path}/{upc}.itmsp.zip".lstrip("/") if base_path else f"{upc}.itmsp.zip"
    sftp_path_used = remote_package

    transport = None
    try:
        import paramiko
        transport = paramiko.Transport((host, port))
        transport.connect(username=username, pkey=pkey)
        prog("SFTP connected. Uploading .itmsp.zip...")
        sftp = paramiko.SFTPClient.from_transport(transport)

        # Ensure base directory exists (e.g. apple/regular)
        if base_path:
            parts = [p for p in base_path.split("/") if p]
            for i in range(1, len(parts) + 1):
                sub = "/".join(parts[:i])
                try:
                    sftp.stat(sub)
                except OSError as e:
                    if e.errno == errno.ENOENT:
                        try:
                            sftp.mkdir(sub)
                        except OSError as mkdir_e:
                            if mkdir_e.errno != errno.EEXIST:
                                raise

        sftp.putfo(BytesIO(zip_bytes), remote_package)
        logger.info("Merlin Bridge SFTP: uploaded %s (%s bytes)", remote_package, len(zip_bytes))
        prog(f"Uploaded: {remote_package}")

        try:
            stat = sftp.stat(remote_package)
            prog(f"Verified: {remote_package} ({stat.st_size} bytes)")
        except Exception as verify_err:
            logger.warning("Could not verify %s: %s", remote_package, verify_err)

        # List directory so we can confirm what Bridge might see
        if base_path:
            try:
                listing = sftp.listdir(base_path)
                prog(f"Contents of {base_path}/: {', '.join(sorted(listing)[:20])}{'...' if len(listing) > 20 else ''}")
            except Exception as list_err:
                logger.warning("Could not list %s: %s", base_path, list_err)

        sftp.close()
        prog("Upload complete. If Bridge still shows nothing, run: python manage.py list_merlin_bridge_sftp")
        return (True, None, sftp_path_used)
    except Exception as e:
        logger.warning("Merlin Bridge SFTP upload failed: %s", e)
        return (False, str(e), "")
    finally:
        if transport:
            try:
                transport.close()
            except Exception:
                pass


def deliver_release_to_merlin_bridge(
    release: Release,
    metadata_only: bool = False,
    distribution_job_id: Optional[int] = None,
) -> Tuple[bool, str, Dict[str, Any]]:
    """
    Build Apple iTunes Importer (music5.3) metadata and upload to Merlin Bridge SFTP (SSH key auth).
    Assigns UPC/ISRC if needed. Delivers a single final package file to {path}/{upc}.itmsp.zip
    (zip containing a top-level folder {upc}.itmsp/ with metadata.xml + assets).

    If metadata_only=True: zip contains only metadata.xml (no .jpg / audio in the package).
    Our XML still references those filenames; many validators then report missing binaries unless Apple
    already holds the assets and the partner allows a metadata-only package. Prefer full delivery
    (metadata_only=False) whenever Bridge/Apple expects binaries inside the .itmsp.zip.
    """
    def progress(msg: str) -> None:
        print(f"[Merlin Bridge] {msg}", flush=True)
        if distribution_job_id:
            try:
                from releases.distribution_job_progress import (
                    update_distribution_job_merlin_progress,
                )

                update_distribution_job_merlin_progress(distribution_job_id, msg)
            except Exception:
                logger.debug("distribution_job progress update skipped", exc_info=True)

    progress("Assigning UPC/ISRC if needed...")
    ok, err = _assign_upc_isrc_if_needed(release)
    if not ok:
        return (False, err or "UPC/ISRC assignment failed", {})

    upc = (release.upc or "").strip() or str(release.id)
    upc = normalize_upc_to_13(upc) or upc
    progress(f"UPC: {upc}.")
    ok_model, model_err = _validate_apple_preorder_vs_commercial_model(release)
    if not ok_model:
        return (False, model_err, {"message": model_err, "upc": upc, "merlin_bridge_sftp_uploaded": False})
    ok_dates, dates_err = _validate_apple_preorder_vs_street(release)
    if not ok_dates:
        return (False, dates_err, {"message": dates_err, "upc": upc, "merlin_bridge_sftp_uploaded": False})
    ok_ig, ig_err = _validate_apple_instant_grat_for_preorder(release)
    if not ok_ig:
        return (False, ig_err, {"message": ig_err, "upc": upc, "merlin_bridge_sftp_uploaded": False})
    progress(f"Album DPID (COIN_DIGITAL_PARTY_ID): {COIN_DIGITAL_PARTY_ID!r}")
    if metadata_only:
        progress("Mode: metadata-only update (XML + size/MD5 only; no binary re-upload).")

    our_bucket = (getattr(settings, "AWS_STORAGE_BUCKET_NAME", None) or "").strip() or "coindigital-media"

    sftp_ok, sftp_err, sftp_path = _upload_merlin_bridge_apple_to_sftp(
        release,
        upc,
        our_bucket,
        progress=progress,
        metadata_only=metadata_only,
        distribution_job_id=distribution_job_id,
    )
    if sftp_ok:
        if metadata_only:
            msg = f"Apple Music (Merlin Bridge) metadata-only update sent to SFTP. UPC: {upc}. Path: {sftp_path}"
        else:
            msg = f"Apple Music (Merlin Bridge) delivered to SFTP. UPC: {upc}. Path: {sftp_path}"
        return (True, None, {
            "message": msg,
            "upc": upc,
            "merlin_bridge_sftp_path": sftp_path,
            "merlin_bridge_sftp_uploaded": True,
            "metadata_only": metadata_only,
        })
    return (False, sftp_err or "Merlin Bridge SFTP upload failed", {
        "message": f"Apple Music (Merlin Bridge): {sftp_err or 'SFTP upload failed'}",
        "upc": upc,
        "merlin_bridge_sftp_uploaded": False,
        "merlin_bridge_sftp_error": sftp_err,
    })


def _upload_merlin_bridge_apple_takedown_to_sftp(release: Release, upc: str) -> Tuple[bool, str, str]:
    """
    Upload Apple iTunes Importer takedown package to Merlin Bridge SFTP.
    Path: {base_path}/takedown/{upc}.itmsp.zip (not the same as delivery) so Bridge
    ingests it as a takedown and shows status "Takedown" instead of treating it as a new delivery.
    Package contains only {upc}.itmsp/metadata.xml with cleared_for_sale/cleared_for_stream false.
    Returns (success, error_message, sftp_path_used).
    """
    host = (os.getenv("MERLIN_BRIDGE_SFTP_HOST") or "").strip()
    if not host:
        return (False, "MERLIN_BRIDGE_SFTP_HOST not set", "")
    port = int((os.getenv("MERLIN_BRIDGE_SFTP_PORT") or "22").strip())
    username = (os.getenv("MERLIN_BRIDGE_SFTP_USERNAME") or "").strip()
    if not username:
        return (False, "MERLIN_BRIDGE_SFTP_USERNAME not set", "")

    pkey, key_err = _load_merlin_bridge_pkey()
    if key_err:
        return (False, key_err, "")

    try:
        xml_content = build_apple_itunes_takedown_metadata(release, upc)
    except Exception as e:
        logger.exception("Apple iTunes takedown metadata build failed for release %s: %s", release.id, e)
        return (False, f"Takedown metadata build failed: {e}", "")

    METADATA_FILENAME = "metadata.xml"
    PACKAGE_DIR = f"{upc}.itmsp/"
    zip_buffer = BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(f"{PACKAGE_DIR}{METADATA_FILENAME}", xml_content.encode("utf-8"))
    zip_buffer.seek(0)
    zip_bytes = zip_buffer.getvalue()

    base_path = (os.getenv("MERLIN_BRIDGE_SFTP_REMOTE_PATH") or "").strip().rstrip("/")
    # Takedown in dedicated subfolder so Bridge does not treat it as a new delivery
    takedown_dir = f"{base_path}/takedown".lstrip("/") if base_path else "takedown"
    remote_package = f"{takedown_dir}/{upc}.itmsp.zip".lstrip("/")
    sftp_path_used = remote_package

    transport = None
    try:
        import paramiko
        transport = paramiko.Transport((host, port))
        transport.connect(username=username, pkey=pkey)
        sftp = paramiko.SFTPClient.from_transport(transport)

        # Ensure base_path and takedown subfolder exist
        for path in ([base_path, takedown_dir] if base_path else [takedown_dir]):
            if not path:
                continue
            parts = [p for p in path.split("/") if p]
            for i in range(1, len(parts) + 1):
                sub = "/".join(parts[:i])
                try:
                    sftp.stat(sub)
                except OSError as e:
                    if e.errno == errno.ENOENT:
                        try:
                            sftp.mkdir(sub)
                        except OSError as mkdir_e:
                            if mkdir_e.errno != errno.EEXIST:
                                raise

        sftp.putfo(BytesIO(zip_bytes), remote_package)
        logger.info("Merlin Bridge SFTP: uploaded takedown package %s (%s bytes)", remote_package, len(zip_bytes))
        sftp.close()
        return (True, None, sftp_path_used)
    except Exception as e:
        logger.warning("Merlin Bridge SFTP takedown upload failed: %s", e)
        return (False, str(e), "")
    finally:
        if transport:
            try:
                transport.close()
            except Exception:
                pass


def deliver_takedown_to_merlin_bridge(release: Release) -> Tuple[bool, str, Dict[str, Any]]:
    """
    Build Apple iTunes Importer (music5.3) takedown package and upload to Merlin Bridge SFTP.
    Package is {upc}.itmsp.zip (metadata.xml only, cleared_for_sale/cleared_for_stream false)
    uploaded to the same path as delivery (e.g. apple/regular/) so Bridge shows it as Takedown
    like Sonosuite-initiated takedowns.
    """
    upc = (getattr(release, "upc", None) or "").strip() or str(release.id)
    upc = normalize_upc_to_13(upc) or upc

    sftp_ok, sftp_err, sftp_path = _upload_merlin_bridge_apple_takedown_to_sftp(release, upc)
    if sftp_ok:
        return (True, None, {
            "message": f"Apple Music (Merlin Bridge) takedown sent to SFTP. UPC: {upc}. Path: {sftp_path}",
            "upc": upc,
            "merlin_bridge_sftp_path": sftp_path,
            "merlin_bridge_takedown_uploaded": True,
        })
    return (False, sftp_err or "Merlin Bridge SFTP takedown upload failed", {
        "message": f"Apple Music (Merlin Bridge) takedown: {sftp_err or 'SFTP upload failed'}",
        "upc": upc,
        "merlin_bridge_takedown_uploaded": False,
        "merlin_bridge_takedown_error": sftp_err,
    })
