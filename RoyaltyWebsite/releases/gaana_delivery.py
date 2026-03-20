"""
Gaana delivery: build DDEX ERN 4.3 for Gaana, upload to S3 (your bucket), and optionally to Gaana SFTP.
"""
import errno
import logging
import os
import time
from datetime import datetime, timezone
from io import BytesIO
from typing import Any, Dict, List, Tuple

from django.conf import settings

from releases.audiomack_delivery import (
    _assign_upc_isrc_if_needed,
    _copy_assets_to_delivery_folder,
    _s3_bucket_key_from_url,
    _upload_xml_to_s3,
)
from releases.ddex_builder import build_new_release_message
from releases.models import Release, Track
from releases.upc_utils import normalize_upc_to_13

logger = logging.getLogger(__name__)


def _batch_complete_xml(batch_number: str) -> str:
    """Minimal BatchComplete marker for Gaana."""
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<BatchComplete BatchNumber="{batch_number}" xmlns="http://ddex.net/xml/ern/43">
  <BatchId>{batch_number}</BatchId>
  <CompletedDateTime>{datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")}</CompletedDateTime>
</BatchComplete>
"""


def _scp_send_file(chan, content: bytes, mode: str, filename: str) -> None:
    """Send one file over SCP protocol. chan is an open session that already ran 'scp -t dir'."""
    chan.sendall(f"C{mode} {len(content)} {filename}\n".encode("utf-8"))
    chan.sendall(content)
    chan.sendall(b"\x00")
    # OpenSSH scp server sends \x00 to ack; consume it so channel stays in sync
    try:
        chan.recv(1)
    except Exception:
        pass


def _upload_gaana_package_via_scp(
    our_bucket: str,
    delivery_prefix: str,
    upc: str,
    xml_content: str,
    batch_number: str,
    resource_keys: list,
    host: str,
    port: int,
    username: str,
    password: str,
    base_path: str,
) -> Tuple[bool, str]:
    """Upload batch via SCP (exec channel) when SFTP subsystem fails. Same folder structure."""
    try:
        from .processor import processor
        s3 = processor.get_s3_client()
    except Exception as e:
        return (False, f"S3: {e}")
    import paramiko
    time.sleep(2)  # brief pause so server is ready for a new connection
    transport = paramiko.Transport((host, port))
    transport.connect(username=username, password=password)
    try:
        chan = transport.open_session()
    except (EOFError, IOError, OSError) as e:
        transport.close()
        return (False, f"Channel open failed: {e}")
    remote_start = base_path if base_path else "."
    chan.exec_command(f"scp -t -r {remote_start}")
    chan.settimeout(10)
    # SCP protocol: D mode 0 name for dir, C mode size name for file, E for end dir
    def send_dir(name: str) -> None:
        chan.sendall(f"D0755 0 {name}\n".encode("utf-8"))
    def end_dir() -> None:
        chan.sendall(b"E\n")
    send_dir(batch_number)
    send_dir(upc)
    _scp_send_file(chan, xml_content.encode("utf-8"), "0644", f"{upc}.xml")
    send_dir("resources")
    for key in resource_keys:
        filename = key.split("/")[-1]
        if not filename:
            continue
        obj = s3.get_object(Bucket=our_bucket, Key=key)
        body = obj["Body"].read()
        _scp_send_file(chan, body, "0644", filename)
    end_dir()  # resources
    end_dir()  # upc
    batch_complete = _batch_complete_xml(batch_number)
    _scp_send_file(chan, batch_complete.encode("utf-8"), "0644", f"BatchComplete_{batch_number}.xml")
    end_dir()  # batch_number
    chan.close()
    transport.close()
    return (True, None)


def _upload_gaana_to_sftp_direct_from_release(
    release: Release,
    upc: str,
    xml_content: str,
    batch_number: str,
    default_bucket: str,
) -> Tuple[bool, str]:
    """
    Upload Gaana package to SFTP by reading cover + audio from release's current S3 URLs (GetObject).
    Use when S3 PutObject is denied (e.g. EC2 has read but not write on the bucket).
    """
    host = (os.getenv("GAANA_SFTP_HOST") or "").strip()
    if not host:
        return (False, "GAANA_SFTP_HOST not set")
    port = int((os.getenv("GAANA_SFTP_PORT") or "22").strip())
    username = (os.getenv("GAANA_SFTP_USERNAME") or "").strip()
    password = (os.getenv("GAANA_SFTP_PASSWORD") or "").strip()
    if not username or not password:
        return (False, "GAANA_SFTP_USERNAME and GAANA_SFTP_PASSWORD required")
    try:
        import paramiko
    except ImportError:
        return (False, "paramiko not installed")
    try:
        from .processor import processor
        s3 = processor.get_s3_client()
    except Exception as e:
        return (False, f"S3 client: {e}")

    # Build list of (remote_filename, bucket, key) for cover + tracks
    files_to_upload: List[Tuple[str, str, str]] = []
    cover_url = getattr(release, "cover_art_url", None) or ""
    if cover_url:
        b, k = _s3_bucket_key_from_url(cover_url, default_bucket)
        if k:
            files_to_upload.append(("coverart.jpg", b, k))
    for idx, track in enumerate(Track.objects.filter(release=release).order_by("id")):
        audio_url = getattr(track, "audio_track_url", None) or ""
        if not audio_url:
            continue
        b, k = _s3_bucket_key_from_url(audio_url, default_bucket)
        if k:
            files_to_upload.append((f"1_{idx + 1}.flac", b, k))

    transport = None
    try:
        transport = paramiko.Transport((host, port))
        transport.connect(username=username, password=password)
        sftp = paramiko.SFTPClient.from_transport(transport)
        base_path = (os.getenv("GAANA_SFTP_REMOTE_PATH") or "upload").strip().rstrip("/")
        remote_batch = f"{base_path}/{batch_number}"
        remote_upc_dir = f"{remote_batch}/{upc}"
        remote_resources = f"{remote_upc_dir}/resources"

        def mkdir_p(path: str) -> None:
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

        mkdir_p(remote_upc_dir)
        mkdir_p(remote_resources)

        sftp.putfo(BytesIO(xml_content.encode("utf-8")), f"{remote_upc_dir}/{upc}.xml")
        logger.info("Gaana SFTP (direct): uploaded %s.xml", upc)

        for remote_name, bucket, key in files_to_upload:
            obj = s3.get_object(Bucket=bucket, Key=key)
            body = obj["Body"].read()
            sftp.putfo(BytesIO(body), f"{remote_resources}/{remote_name}")
            logger.info("Gaana SFTP (direct): uploaded resources/%s", remote_name)

        batch_complete = _batch_complete_xml(batch_number)
        sftp.putfo(BytesIO(batch_complete.encode("utf-8")), f"{remote_batch}/BatchComplete_{batch_number}.xml")
        sftp.close()
        return (True, None)
    except Exception as e:
        logger.warning("Gaana SFTP direct upload failed: %s", e)
        return (False, str(e))
    finally:
        if transport:
            try:
                transport.close()
            except Exception:
                pass


def _upload_gaana_package_to_sftp(
    our_bucket: str,
    delivery_prefix: str,
    s3_key_xml: str,
    upc: str,
    xml_content: str,
    batch_number: str,
) -> Tuple[bool, str]:
    """
    Upload Gaana batch from S3 to Gaana SFTP. Structure: BatchNumber/upc/upc.xml, upc/resources/*, BatchComplete_*.xml.
    Returns (True, None) or (False, error_message).
    """
    host = (os.getenv("GAANA_SFTP_HOST") or "").strip()
    if not host:
        return (False, "GAANA_SFTP_HOST not set")
    port = int((os.getenv("GAANA_SFTP_PORT") or "22").strip())
    username = (os.getenv("GAANA_SFTP_USERNAME") or "").strip()
    password = (os.getenv("GAANA_SFTP_PASSWORD") or "").strip()
    if not username or not password:
        return (False, "GAANA_SFTP_USERNAME and GAANA_SFTP_PASSWORD required")

    try:
        import paramiko
    except ImportError:
        return (False, "paramiko not installed. pip install paramiko")

    try:
        from .processor import processor
        s3 = processor.get_s3_client()
    except Exception as e:
        return (False, f"S3 client: {e}")

    resources_prefix = delivery_prefix.rstrip("/") + "/resources/"
    try:
        list_resp = s3.list_objects_v2(Bucket=our_bucket, Prefix=resources_prefix, MaxKeys=100)
        resource_keys = [obj["Key"] for obj in list_resp.get("Contents", []) if obj.get("Key") and obj["Key"] != resources_prefix]
    except Exception as e:
        return (False, f"S3 list resources: {e}")

    transport = None
    sftp = None
    try:
        # Try SFTP first (Gaana confirmed issue fixed)
        transport = paramiko.Transport((host, port))
        transport.connect(username=username, password=password)
        # Use standard SFTP subsystem (Gaana confirmed fix)
        sftp = paramiko.SFTPClient.from_transport(transport)

        base_path = (os.getenv("GAANA_SFTP_REMOTE_PATH") or "").strip().rstrip("/")
        if base_path:
            remote_batch = f"{base_path}/{batch_number}"
        else:
            remote_batch = batch_number
        remote_upc_dir = f"{remote_batch}/{upc}"
        remote_resources = f"{remote_upc_dir}/resources"

        def mkdir_p(path: str) -> None:
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

        mkdir_p(remote_upc_dir)
        mkdir_p(remote_resources)

        remote_xml_path = f"{remote_upc_dir}/{upc}.xml"
        sftp.putfo(BytesIO(xml_content.encode("utf-8")), remote_xml_path)
        logger.info("Gaana SFTP: uploaded %s.xml", upc)

        for key in resource_keys:
            filename = key.split("/")[-1]
            if not filename:
                continue
            obj = s3.get_object(Bucket=our_bucket, Key=key)
            body = obj["Body"].read()
            sftp.putfo(BytesIO(body), f"{remote_resources}/{filename}")
            logger.info("Gaana SFTP: uploaded resources/%s", filename)

        batch_complete = _batch_complete_xml(batch_number)
        sftp.putfo(BytesIO(batch_complete.encode("utf-8")), f"{remote_batch}/BatchComplete_{batch_number}.xml")
        logger.info("Gaana SFTP: uploaded BatchComplete_%s.xml", batch_number)

        sftp.close()
        return (True, None)
    except (EOFError, IOError, OSError) as e:
        logger.warning("Gaana SFTP failed (%s), trying SCP fallback", e)
        base_path = (os.getenv("GAANA_SFTP_REMOTE_PATH") or "").strip().rstrip("/")
        scp_ok, scp_err = _upload_gaana_package_via_scp(
            our_bucket, delivery_prefix, upc, xml_content, batch_number, resource_keys,
            host, port, username, password, base_path or ".",
        )
        if scp_ok:
            return (True, None)
        return (False, f"SFTP failed: {e}. SCP fallback: {scp_err or 'failed'}")
    except Exception as e:
        logger.exception("Gaana SFTP upload failed: %s", e)
        err_msg = str(e)
        if "Permission denied" in err_msg or getattr(e, "errno", None) == errno.EACCES:
            err_msg += " Set GAANA_SFTP_REMOTE_PATH to the exact folder path Gaana gave you (e.g. CoinDigital or upload/CoinDigital)."
        return (False, err_msg)
    finally:
        if transport:
            try:
                transport.close()
            except Exception:
                pass


def deliver_release_to_gaana(release: Release) -> Tuple[bool, str, Dict[str, Any]]:
    """
    Build DDEX ERN 4.3 for Gaana and upload to your S3 (same bucket as Audiomack flow).
    Assigns UPC/ISRC if needed. Returns (success, error_message, detail_dict).
    """
    ok, err = _assign_upc_isrc_if_needed(release)
    if not ok:
        return (False, err or "UPC/ISRC assignment failed", {})

    upc = (release.upc or "").strip() or str(release.id)
    upc = normalize_upc_to_13(upc) or upc

    try:
        xml = build_new_release_message(release, store="gaana")
    except Exception as e:
        logger.exception("Gaana DDEX build failed for release %s: %s", release.id, e)
        return (False, f"Gaana DDEX build failed: {e}", {"xml_built": False})

    our_bucket = (getattr(settings, "AWS_STORAGE_BUCKET_NAME", None) or "").strip() or "coindigital-media"
    delivery_id = datetime.now(timezone.utc).strftime("%Y%m%d")
    delivery_prefix = f"ddex/gaana/{delivery_id}/"
    s3_key = f"{delivery_prefix}{upc}.xml"
    batch_number = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S") + "001"

    # When Gaana SFTP is configured, use SFTP-only (no S3 write). Avoids AccessDenied when server can't write to our bucket.
    gaana_sftp_host = (os.getenv("GAANA_SFTP_HOST") or "").strip()
    if gaana_sftp_host:
        sftp_ok, sftp_err = _upload_gaana_to_sftp_direct_from_release(
            release, upc, xml, batch_number, our_bucket
        )
        if sftp_ok:
            return (True, None, {
                "message": f"DDEX for Gaana delivered to SFTP. UPC: {upc}.",
                "upc": upc,
                "xml_built": True,
                "gaana_sftp_uploaded": True,
                "gaana_sftp_batch": batch_number,
            })
        # SFTP-only: do not try S3 (server may not have PutObject). Return SFTP error so it's visible.
        return (False, sftp_err or "Gaana SFTP upload failed", {
            "message": f"Gaana: {sftp_err or 'SFTP upload failed'}",
            "upc": upc,
            "xml_built": True,
            "gaana_sftp_uploaded": False,
            "gaana_sftp_error": sftp_err,
        })

    upload_ok, upload_err = _upload_xml_to_s3(xml, our_bucket, s3_key)
    err_lower = (upload_err or "").lower()
    s3_denied = bool(upload_err and ("access" in err_lower and "denied" in err_lower))

    if not upload_ok and s3_denied:
        # EC2 often has read but not write on the bucket. Try Gaana SFTP only (read assets from release URLs).
        logger.info("Gaana S3 upload denied; trying SFTP delivery using release assets (GetObject).")
        sftp_ok, sftp_err = _upload_gaana_to_sftp_direct_from_release(
            release, upc, xml, batch_number, our_bucket
        )
        if sftp_ok:
            return (True, None, {
                "message": f"DDEX for Gaana delivered to SFTP (no S3 write; used release assets). UPC: {upc}.",
                "upc": upc,
                "xml_built": True,
                "gaana_sftp_uploaded": True,
                "gaana_sftp_batch": batch_number,
            })
        err_show = f"S3 upload denied; SFTP fallback failed: {sftp_err or 'unknown'}"
        return (False, err_show, {
            "message": f"Gaana: {err_show}",
            "upc": upc,
            "xml_built": True,
            "gaana_sftp_error": sftp_err,
        })

    if not upload_ok:
        return (False, upload_err or "Gaana S3 upload failed", {
            "message": "Gaana DDEX built but upload failed. " + (upload_err or ""),
            "upc": upc,
            "xml_built": True,
            "s3_key": s3_key,
        })

    assets_copied, asset_errors = _copy_assets_to_delivery_folder(
        release, our_bucket, delivery_prefix, our_bucket
    )
    msg = (
        f"DDEX for Gaana saved to your S3. UPC: {upc}. "
        f"XML: s3://{our_bucket}/{s3_key}. "
        f"Resources: {assets_copied} file(s) (cover + audio) in resources/."
    )
    if asset_errors:
        msg += " Warnings: " + "; ".join(asset_errors[:3])

    detail = {
        "message": msg,
        "upc": upc,
        "s3_bucket": our_bucket,
        "s3_key": s3_key,
        "xml_built": True,
        "assets_copied": assets_copied,
        "asset_errors": asset_errors,
    }

    sftp_ok, sftp_err = _upload_gaana_package_to_sftp(
        our_bucket, delivery_prefix, s3_key, upc, xml, batch_number
    )
    detail["gaana_sftp_uploaded"] = sftp_ok
    if sftp_ok:
        msg += " Delivered to Gaana SFTP."
        detail["message"] = msg
        detail["gaana_sftp_batch"] = batch_number
    else:
        detail["gaana_sftp_error"] = sftp_err
        msg += " Gaana SFTP: " + (sftp_err or "upload failed")
        detail["message"] = msg

    return (True, None, detail)


def _upload_gaana_takedown_xml_to_sftp(upc: str, xml_content: str) -> Tuple[bool, str]:
    """
    Upload a single takedown XML to Gaana SFTP. Path: upload/takedown/{batch}/{upc}_takedown.xml.
    Returns (True, None) or (False, error_message).
    """
    host = (os.getenv("GAANA_SFTP_HOST") or "").strip()
    if not host:
        return (False, "GAANA_SFTP_HOST not set")
    port = int((os.getenv("GAANA_SFTP_PORT") or "22").strip())
    username = (os.getenv("GAANA_SFTP_USERNAME") or "").strip()
    password = (os.getenv("GAANA_SFTP_PASSWORD") or "").strip()
    if not username or not password:
        return (False, "GAANA_SFTP_USERNAME and GAANA_SFTP_PASSWORD required")
    try:
        import paramiko
    except ImportError:
        return (False, "paramiko not installed")

    base_path = (os.getenv("GAANA_SFTP_REMOTE_PATH") or "upload").strip().rstrip("/")
    batch = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S") + "_takedown"
    remote_dir = f"{base_path}/takedown/{batch}"
    remote_file = f"{remote_dir}/{upc}_takedown.xml"

    transport = None
    try:
        transport = paramiko.Transport((host, port))
        transport.connect(username=username, password=password)
        sftp = paramiko.SFTPClient.from_transport(transport)
        parts = [p for p in remote_dir.split("/") if p]
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
        sftp.putfo(BytesIO(xml_content.encode("utf-8")), remote_file)
        sftp.close()
        logger.info("Gaana SFTP: uploaded takedown %s", remote_file)
        return (True, None)
    except Exception as e:
        logger.warning("Gaana SFTP takedown upload failed: %s", e)
        return (False, str(e))
    finally:
        if transport:
            try:
                transport.close()
            except Exception:
                pass


def deliver_takedown_to_gaana(release: Release) -> Tuple[bool, str, Dict[str, Any]]:
    """
    Build DDEX takedown (NewReleaseMessage with TakeDown) for Gaana and upload to your S3 and Gaana SFTP.
    Returns (success, error_message, detail_dict). Use when a takedown is requested for this release.
    """
    upc = (getattr(release, "upc", None) or "").strip() or str(release.id)
    upc = normalize_upc_to_13(upc) or upc
    try:
        xml = build_new_release_message(release, store="gaana", takedown_immediate=True, takedown_end_date=None)
    except Exception as e:
        logger.exception("Gaana takedown DDEX build failed for release %s: %s", release.id, e)
        return (False, f"Gaana takedown DDEX build failed: {e}", {"xml_built": False, "upc": upc})

    our_bucket = (getattr(settings, "AWS_STORAGE_BUCKET_NAME", None) or "").strip()
    delivery_id = datetime.now(timezone.utc).strftime("%Y%m%d")
    s3_key = f"ddex/gaana/takedown/{delivery_id}/{upc}_takedown.xml"
    detail = {"upc": upc, "xml_built": True}

    if our_bucket:
        upload_ok, upload_err = _upload_xml_to_s3(xml, our_bucket, s3_key)
        if upload_ok:
            detail["message"] = f"Gaana takedown saved to S3. UPC: {upc}."
            detail["s3_bucket"] = our_bucket
            detail["s3_key"] = s3_key
        else:
            detail["s3_upload_failed"] = upload_err

    sftp_ok, sftp_err = _upload_gaana_takedown_xml_to_sftp(upc, xml)
    detail["gaana_sftp_uploaded"] = sftp_ok
    if sftp_ok:
        detail["message"] = (detail.get("message") or "") + " Delivered to Gaana SFTP."
    else:
        detail["gaana_sftp_error"] = sftp_err

    return (True, None, detail)
