"""
Extract duration from audio files for DDEX (PT00H00M00S format).
Uses mutagen if available; otherwise returns None (caller can use PT00H00M00S).
"""
import logging
from typing import Optional

logger = logging.getLogger(__name__)


def _duration_seconds_from_mutagen(file_path_or_url: str) -> Optional[float]:
    """Use mutagen to get duration in seconds. Returns None on failure."""
    try:
        import mutagen
        from urllib.request import urlopen
        from urllib.parse import urlparse
    except ImportError:
        return None
    try:
        parsed = urlparse(file_path_or_url)
        if parsed.scheme in ("http", "https"):
            with urlopen(file_path_or_url, timeout=30) as f:
                audio = mutagen.File(f)
        else:
            audio = mutagen.File(file_path_or_url)
        if audio is not None and hasattr(audio, "info") and audio.info is not None:
            length = getattr(audio.info, "length", None)
            if length is not None:
                return float(length)
    except Exception as e:
        logger.warning("ddex_duration: could not get length: %s", e)
    return None


def duration_seconds(audio_path_or_url: str) -> Optional[float]:
    """
    Return duration in seconds for the given audio file path or URL.
    Returns None if extraction fails (use PT00H00M00S in DDEX when None).
    """
    if not audio_path_or_url:
        return None
    return _duration_seconds_from_mutagen(audio_path_or_url)


def duration_to_ddex(seconds: Optional[float]) -> str:
    """
    Format duration as DDEX Duration (ISO 8601 duration): PT00H00M00S.
    If seconds is None, returns PT00H00M00S (placeholder).
    """
    if seconds is None or seconds < 0:
        return "PT00H00M00S"
    total = int(round(seconds))
    hours = total // 3600
    minutes = (total % 3600) // 60
    secs = total % 60
    return f"PT{hours:02d}H{minutes:02d}M{secs:02d}S"
