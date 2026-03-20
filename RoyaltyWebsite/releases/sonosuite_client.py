"""
Sonosuite API client: call Sonosuite's Distribution API using admin credentials.
Used when admin approves a release — we send the release to Sonosuite (login + delivery).
"""
import json
import logging
import os
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

import requests

logger = logging.getLogger(__name__)

# Coin Digital Sonosuite API (confirmed: https://coin.sonosuite.com)
DEFAULT_SONOSUITE_BASE = "https://coin.sonosuite.com"


def _ensure_sonosuite_env_loaded() -> None:
    """If Sonosuite vars are missing, try loading coin.env / .env from project root or /app (Docker)."""
    if os.getenv("SONOSUITE_ADMIN_EMAIL") and os.getenv("SONOSUITE_ADMIN_PASSWORD"):
        return
    try:
        from dotenv import load_dotenv
        # In Docker: /app/releases/sonosuite_client.py -> parent.parent = /app. In local: parent.parent.parent = django-docker-compose
        roots = [
            Path(__file__).resolve().parent.parent,  # /app (Docker) or RoyaltyWebsite (local)
            Path(__file__).resolve().parent.parent.parent,  # django-docker-compose (local)
            Path("/app"),  # Docker app root (mount point for .env)
        ]
        for root in roots:
            for name in ("coin.env", ".env"):
                p = root / name
                if p.exists():
                    load_dotenv(p, override=True)
                    if os.getenv("SONOSUITE_ADMIN_EMAIL") and os.getenv("SONOSUITE_ADMIN_PASSWORD"):
                        return
    except Exception as e:
        logger.debug("Could not load Sonosuite env from file: %s", e)


def get_sonosuite_config() -> Dict[str, str]:
    """Get Sonosuite API config from environment (admin credentials)."""
    _ensure_sonosuite_env_loaded()
    return {
        "base_url": (os.getenv("SONOSUITE_API_BASE_URL") or DEFAULT_SONOSUITE_BASE).strip().rstrip("/"),
        "admin_username": (os.getenv("SONOSUITE_ADMIN_EMAIL") or "").strip(),
        "admin_password": (os.getenv("SONOSUITE_ADMIN_PASSWORD") or "").strip(),
    }


def is_sonosuite_configured() -> bool:
    """Return True if admin credentials are set for Sonosuite."""
    cfg = get_sonosuite_config()
    return bool(cfg["admin_username"] and cfg["admin_password"] and cfg["base_url"])


def sonosuite_login(username: str, password: str, base_url: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Login to Sonosuite Distribution API.
    Returns (token, None) on success, or (None, error_message) on failure.
    """
    url = f"{base_url}/distribution/api/login"
    try:
        r = requests.post(
            url,
            json={"username": username, "password": password},
            headers={"Content-Type": "application/json"},
            timeout=30,
        )
        if r.status_code == 200:
            try:
                data = r.json()
            except json.JSONDecodeError:
                preview = (r.text or "")[:150].replace("\n", " ")
                logger.warning("Sonosuite login returned non-JSON (HTTP 200): %s", preview)
                return (
                    None,
                    "Sonosuite returned a non-JSON response (e.g. HTML). "
                    "Set SONOSUITE_API_BASE_URL to the base only, e.g. https://coin.sonosuite.com (no /distribution/api).",
                )
            token = data.get("token")
            return (token, None) if token else (None, "No token in response")
        if r.status_code == 401:
            msg = "Invalid email or password (HTTP 401). Check SONOSUITE_ADMIN_EMAIL and SONOSUITE_ADMIN_PASSWORD."
        elif r.status_code == 403:
            msg = "Sonosuite account disabled or forbidden (HTTP 403)."
        elif r.status_code == 400:
            msg = "Bad request to Sonosuite (HTTP 400). Check API base URL and credentials."
        else:
            msg = f"Sonosuite login failed (HTTP {r.status_code}). Check API.env and network."
        logger.warning("Sonosuite login failed: %s %s", r.status_code, r.text[:200] if r.text else "")
        return None, msg
    except requests.exceptions.Timeout:
        logger.warning("Sonosuite login timeout: %s", url)
        return None, "Sonosuite login timed out. Check network and SONOSUITE_API_BASE_URL."
    except requests.exceptions.RequestException as e:
        logger.exception("Sonosuite login error: %s", e)
        return None, f"Cannot reach Sonosuite: {type(e).__name__}. Check SONOSUITE_API_BASE_URL and network."
    except Exception as e:
        logger.exception("Sonosuite login error: %s", e)
        return None, str(e)


def _normalize_upcs_to_13(upcs: List[str]) -> List[str]:
    """Ensure all UPCs are 13-digit (EAN-13) for Sonosuite API. 12-digit gets leading 0."""
    from releases.upc_utils import normalize_upc_to_13
    return [normalize_upc_to_13(u) or u for u in upcs if (u or "").strip()]


def sonosuite_delivery(
    token: str,
    dsp_code: str,
    upcs: List[str],
    base_url: str,
    deliver_taken_down: bool = False,
    verbose: bool = False,
) -> Dict[str, Any]:
    """
    POST delivery to Sonosuite. Returns {"success": bool, "operation_id": str?, "error": str?, "raw_response": str?}.
    Accepts 200 OK or 201 Created as success.
    Sonosuite expects 13-digit EAN-13 (12-digit UPCs get leading 0).
    """
    upcs = _normalize_upcs_to_13(upcs)
    url = f"{base_url}/distribution/api/delivery"
    payload = {
        "dsp_code": dsp_code,
        "upcs": upcs,
        "deliver_taken_down": deliver_taken_down,
    }
    try:
        r = requests.post(
            url,
            json=payload,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            timeout=60,
        )
        if r.status_code in (200, 201):
            try:
                data = r.json() if r.text else {}
            except json.JSONDecodeError:
                logger.warning("Sonosuite delivery: success status but invalid JSON: %s", (r.text or "")[:300])
                return {"success": False, "error": "Invalid JSON in response", "raw_response": r.text}
            op_id = data.get("operation_id") or (data.get("data") or {}).get("operation_id")
            if verbose:
                logger.info("Sonosuite delivery %s: %s -> %s", dsp_code, upcs, data)
            return {"success": True, "operation_id": op_id}
        try:
            err_body = r.json()
            msg = err_body.get("error") or err_body.get("message") or str(err_body)
        except Exception:
            msg = r.text or f"HTTP {r.status_code}"
        full_msg = f"HTTP {r.status_code}: {msg}"
        if r.text and len(r.text) < 500:
            full_msg += f" | body: {r.text}"
        logger.warning("Sonosuite delivery failed %s %s: %s", dsp_code, upcs, full_msg)
        return {"success": False, "error": full_msg, "raw_response": r.text}
    except Exception as e:
        logger.exception("Sonosuite delivery error: %s", e)
        return {"success": False, "error": str(e)}


def sonosuite_get_releases(token: str, upcs: List[str], base_url: str) -> Tuple[Optional[List[Dict[str, Any]]], Optional[str]]:
    """GET /distribution/api/releases?upcs=UPC1,UPC2. UPCs are normalized to 13-digit for Sonosuite."""
    if not upcs:
        return [], None
    upcs = _normalize_upcs_to_13(upcs)
    url = f"{base_url}/distribution/api/releases"
    params = {"upcs": ",".join(upcs)}
    try:
        r = requests.get(
            url,
            params=params,
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            timeout=30,
        )
        if r.status_code == 200:
            try:
                data = r.json()
                return (data if isinstance(data, list) else [], None)
            except json.JSONDecodeError:
                return None, "Invalid JSON in response"
        return None, f"HTTP {r.status_code}: {r.text[:200] if r.text else ''}"
    except requests.exceptions.RequestException as e:
        logger.exception("Sonosuite get releases error: %s", e)
        return None, str(e)


def sonosuite_get_dsps(token: str, base_url: str) -> List[Dict[str, str]]:
    """GET list of DSPs from Sonosuite. Returns list of {dsp_code, dsp_name}."""
    url = f"{base_url}/distribution/api/dsp"
    try:
        r = requests.get(
            url,
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            timeout=30,
        )
        if r.status_code != 200:
            return []
        data = r.json()
        return data if isinstance(data, list) else []
    except Exception as e:
        logger.exception("Sonosuite get DSPs error: %s", e)
        return []


def sonosuite_upload_metadata_csv(
    token: str,
    base_url: str,
    csv_file_path: str,
    timeout: int = 120,
    upload_path: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Upload a metadata CSV file to Sonosuite (coin.sonosuite.com).
    Uses multipart/form-data POST. Returns {"success": bool, "error": str?, "raw_response": str?}.
    """
    import os as _os
    path = upload_path or os.getenv("SONOSUITE_UPLOAD_PATH", "/distribution/api/upload")
    url = f"{base_url.rstrip('/')}{path}" if path.startswith("/") else f"{base_url}/{path}"
    if not _os.path.isfile(csv_file_path):
        return {"success": False, "error": f"CSV file not found: {csv_file_path}"}
    try:
        with open(csv_file_path, "rb") as f:
            files = {"file": (_os.path.basename(csv_file_path), f, "text/csv")}
            headers = {"Authorization": f"Bearer {token}"}
            r = requests.post(url, files=files, headers=headers, timeout=timeout)
        if r.status_code in (200, 201):
            return {"success": True}
        try:
            err_body = r.json()
            msg = err_body.get("error") or err_body.get("message") or str(err_body)
        except Exception:
            msg = r.text or f"HTTP {r.status_code}"
        # Avoid sending full HTML error pages to the UI
        if msg and ("<!DOCTYPE" in msg or "<html" in msg.lower()):
            msg = "Something went wrong. Please contact admin for more information."
        elif msg and len(msg) > 400:
            msg = msg[:400] + "..."
        logger.warning("Sonosuite upload failed: %s %s", r.status_code, msg[:200] if msg else "")
        return {"success": False, "error": f"HTTP {r.status_code}: {msg}", "raw_response": r.text}
    except requests.exceptions.Timeout:
        logger.warning("Sonosuite upload timeout: %s", url)
        return {"success": False, "error": "Upload timed out"}
    except Exception as e:
        logger.exception("Sonosuite upload error: %s", e)
        return {"success": False, "error": str(e)}


def upload_release_metadata_to_sonosuite(
    primary_uuid: str,
    csv_file_path: str,
) -> Dict[str, Any]:
    """
    Login to Sonosuite and upload the metadata CSV for the given release.
    Returns {"success": bool, "error": str?}. Same credentials as delivery (coin.sonosuite.com).
    """
    cfg = get_sonosuite_config()
    if not cfg["admin_username"] or not cfg["admin_password"]:
        return {"success": False, "error": "Sonosuite admin credentials not configured"}
    token, login_error = sonosuite_login(cfg["admin_username"], cfg["admin_password"], cfg["base_url"])
    if not token:
        return {"success": False, "error": login_error or "Sonosuite login failed"}
    result = sonosuite_upload_metadata_csv(token, cfg["base_url"], csv_file_path)
    return result


def send_release_to_sonosuite(
    upc: str,
    dsp_codes: Optional[List[str]] = None,
    verbose: bool = False,
) -> Dict[str, Any]:
    """
    Login with admin credentials and send delivery to Sonosuite for the given UPC.
    Returns {"success": bool, "operation_ids": list, "error": str?, "per_dsp_errors": list?}.
    """
    cfg = get_sonosuite_config()
    if not cfg["admin_username"] or not cfg["admin_password"]:
        return {"success": False, "operation_ids": [], "error": "Sonosuite admin credentials not configured"}
    if not upc:
        return {"success": False, "operation_ids": [], "error": "Release UPC is required"}

    from releases.upc_utils import normalize_upc_to_13
    upc = normalize_upc_to_13(upc) or upc  # Sonosuite expects 13-digit EAN-13 (leading 0 if 12 digits)

    token, login_error = sonosuite_login(cfg["admin_username"], cfg["admin_password"], cfg["base_url"])
    if not token:
        return {"success": False, "operation_ids": [], "error": login_error or "Sonosuite login failed"}

    if dsp_codes:
        codes_to_use = dsp_codes
    else:
        dsps = sonosuite_get_dsps(token, cfg["base_url"])
        codes_to_use = [d.get("dsp_code") or d.get("code") for d in dsps if (d.get("dsp_code") or d.get("code"))]
        if not codes_to_use:
            return {"success": False, "operation_ids": [], "error": "No DSPs returned from Sonosuite"}

    operation_ids = []
    per_dsp_errors = []
    for dsp_code in codes_to_use:
        result = sonosuite_delivery(token, dsp_code, [upc], cfg["base_url"], verbose=verbose)
        if result.get("success") and result.get("operation_id"):
            operation_ids.append(result["operation_id"])
        else:
            err = result.get("error", "Unknown")
            per_dsp_errors.append(f"{dsp_code}: {err}")
            if result.get("raw_response"):
                per_dsp_errors.append(f"  raw: {result['raw_response'][:300]}")
            logger.warning("Sonosuite delivery to %s failed: %s", dsp_code, err)

    return {
        "success": len(operation_ids) > 0,
        "operation_ids": operation_ids,
        "error": None if operation_ids else ("No delivery succeeded. " + "; ".join(per_dsp_errors[:3])),
        "per_dsp_errors": per_dsp_errors if per_dsp_errors else None,
    }
