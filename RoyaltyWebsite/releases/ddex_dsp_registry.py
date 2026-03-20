"""
DSP registry for DDEX feeds (ERN 4.3).
Single source of truth for all DSPs: Party ID, name, deal profile.
Add new DSPs in releases/data/ddex_dsps.json — no code change needed.
"""
import json
import os
from typing import Dict, List, Optional, Tuple

# Path to registry JSON (relative to this file)
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_REGISTRY_PATH = os.path.join(_THIS_DIR, "data", "ddex_dsps.json")

_CACHE: Optional[Dict] = None


def _load_registry() -> Dict:
    """Load and cache the DSP registry from JSON."""
    global _CACHE
    if _CACHE is not None:
        return _CACHE
    if not os.path.isfile(_REGISTRY_PATH):
        _CACHE = {"version": "1.0", "deal_profiles": {}, "dsps": []}
        return _CACHE
    with open(_REGISTRY_PATH, "r", encoding="utf-8") as f:
        _CACHE = json.load(f)
    return _CACHE


def get_dsp(code: str) -> Optional[Dict]:
    """
    Return DSP config dict for the given code, or None.
    Keys: code, party_id, party_name, deal_profile, is_active.
    """
    code = (code or "").strip().lower()
    if not code:
        return None
    data = _load_registry()
    for dsp in data.get("dsps", []):
        if (dsp.get("code") or "").strip().lower() == code:
            return dsp
    return None


def list_dsp_codes(active_only: bool = True) -> List[str]:
    """Return list of DSP codes. If active_only=True, only is_active DSPs."""
    data = _load_registry()
    codes = []
    for dsp in data.get("dsps", []):
        c = (dsp.get("code") or "").strip().lower()
        if not c:
            continue
        if active_only and not dsp.get("is_active", True):
            continue
        codes.append(c)
    return codes


def get_recipient(code: str) -> Optional[Tuple[str, str]]:
    """Return (party_id, party_name) for MessageRecipient, or None if DSP not in registry."""
    dsp = get_dsp(code)
    if not dsp:
        return None
    pid = (dsp.get("party_id") or "").strip()
    name = (dsp.get("party_name") or "").strip()
    if not pid or not name:
        return None
    return (pid, name)


def get_deal_profile(code: str) -> Optional[str]:
    """Return deal_profile for the DSP (e.g. 'streaming', 'ugc'), or None."""
    dsp = get_dsp(code)
    if not dsp:
        return None
    return (dsp.get("deal_profile") or "").strip().lower() or None


def reload_registry() -> None:
    """Clear cache so next access reloads from disk (e.g. after editing JSON)."""
    global _CACHE
    _CACHE = None
