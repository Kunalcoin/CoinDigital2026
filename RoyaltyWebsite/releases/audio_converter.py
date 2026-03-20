"""
Convert WAV to FLAC and MP3 using FFmpeg (best quality; preserves bit depth and sample rate).
Requires FFmpeg installed on the server: apt-get install ffmpeg / brew install ffmpeg.
"""
import logging
import os
import subprocess
import tempfile
from typing import Optional, Tuple

logger = logging.getLogger(__name__)


def _get_wav_info(wav_path: str) -> Tuple[Optional[int], Optional[int]]:
    """Return (sample_rate_hz, bits_per_sample) from WAV, or (None, None)."""
    try:
        import wave
        with wave.open(wav_path, "rb") as w:
            return (w.getframerate(), w.getsampwidth() * 8)
    except Exception as e:
        logger.warning("Could not read WAV info from %s: %s", wav_path, e)
        return (None, None)


def wav_to_flac(wav_path: str, out_path: Optional[str] = None) -> Optional[str]:
    """
    Convert WAV to FLAC (lossless). Uses same sample rate and bit depth as source.
    Returns path to created FLAC file, or None on failure.
    """
    if not os.path.isfile(wav_path):
        logger.error("WAV file not found: %s", wav_path)
        return None
    out_path = out_path or (wav_path.rsplit(".", 1)[0] + ".flac")
    try:
        subprocess.run(
            ["ffmpeg", "-y", "-i", wav_path, "-c:a", "flac", out_path],
            check=True,
            capture_output=True,
            timeout=300,
        )
        return out_path if os.path.isfile(out_path) else None
    except subprocess.CalledProcessError as e:
        logger.exception("FFmpeg FLAC conversion failed: %s", e.stderr)
        return None
    except FileNotFoundError:
        logger.error("FFmpeg not found. Install with: apt-get install ffmpeg or brew install ffmpeg")
        return None
    except Exception as e:
        logger.exception("wav_to_flac failed: %s", e)
        return None


def wav_to_mp3(
    wav_path: str,
    out_path: Optional[str] = None,
    sample_rate: Optional[int] = None,
    bitrate_kbps: int = 320,
) -> Optional[str]:
    """
    Convert WAV to MP3 preserving quality: same sample rate as WAV (or 48000),
    320 kbps CBR for high quality. Returns path to created MP3 file, or None on failure.
    """
    if not os.path.isfile(wav_path):
        logger.error("WAV file not found: %s", wav_path)
        return None
    out_path = out_path or (wav_path.rsplit(".", 1)[0] + ".mp3")
    rate_hz, _ = _get_wav_info(wav_path)
    ar = sample_rate or rate_hz or 48000
    try:
        cmd = [
            "ffmpeg", "-y", "-i", wav_path,
            "-c:a", "libmp3lame",
            "-b:a", f"{bitrate_kbps}k",
            "-ar", str(ar),
            out_path,
        ]
        subprocess.run(cmd, check=True, capture_output=True, timeout=300)
        return out_path if os.path.isfile(out_path) else None
    except subprocess.CalledProcessError as e:
        logger.exception("FFmpeg MP3 conversion failed: %s", e.stderr)
        return None
    except FileNotFoundError:
        logger.error("FFmpeg not found. Install with: apt-get install ffmpeg or brew install ffmpeg")
        return None
    except Exception as e:
        logger.exception("wav_to_mp3 failed: %s", e)
        return None
