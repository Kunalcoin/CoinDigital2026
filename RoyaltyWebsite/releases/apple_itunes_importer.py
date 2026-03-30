"""
Build Apple iTunes Importer (music5.3) XML for Apple Music delivery via Merlin Bridge.
Format matches the provider samples: namespace http://apple.com/itunes/importer, version music5.3.
Used for single and multi-track releases; file names: metadata.xml (Merlin requirement), {upc}.jpg, {upc}_01_{NNN}.wav.
Aligns with Apple Music Style Guide (https://help.apple.com/itc/musicstyleguide/) and Merlin Bridge Member Onboarding Guide.
"""
import html
import logging
import os
import re
from typing import Any, Dict, List, Optional, Tuple

from django.conf import settings

from releases.ddex_config import COIN_DIGITAL_PARTY_ID
from releases.models import Release, Track, RelatedArtists

logger = logging.getLogger(__name__)

# Apple Music genre codes (subset; extend per Apple's genre code list)
# Format: our primary_genre string (lower, partial match) -> Apple code
GENRE_TO_APPLE_CODE = {
    "punjabi": "PUNJABI-POP-00",
    "punjabi pop": "PUNJABI-POP-00",
    "jazz": "JAZZ-00",
    "fusion": "FUSION-00",
    "jazz/fusion": "FUSION-00",
    "pop": "POP-00",
    "hip-hop": "HIP-HOP-00",
    "hip-hop/rap": "HIP-HOP-00",
    "r&b": "R&B-00",
    "rock": "ROCK-00",
    "electronic": "ELECTRONIC-00",
    "country": "COUNTRY-00",
    "latin": "LATIN-00",
    "world": "WORLD-00",
    "haryanvi": "WORLD-00",
    "bollywood": "WORLD-00",
    # Spiritual/devotional: use INDIAN-CLASSICAL-00 (per successful delivery 8905285305838_metadata.xml)
    "spiritual": "INDIAN-CLASSICAL-00",
    "devotional": "INDIAN-CLASSICAL-00",
    "classical": "CLASSICAL-00",
    "indian classical": "INDIAN-CLASSICAL-00",
}

def _genre_to_apple_code(genre: str) -> str:
    """Map our primary_genre to Apple genre code. Default POP-00 if no match."""
    g = (genre or "").strip().lower()
    if not g:
        return "POP-00"
    for key, code in GENRE_TO_APPLE_CODE.items():
        if key in g:
            return code
    return "POP-00"


# Language name -> Apple 2/3 letter code (ISO 639 or Apple-specific)
LANGUAGE_TO_APPLE_CODE = {
    "hindi": "hi",
    "punjabi": "pa",
    "haryanvi": "bgc",
    "bhojpuri": "bho",
    "english": "en",
    "bengali": "bn",
    "tamil": "ta",
    "telugu": "te",
    "marathi": "mr",
    "gujarati": "gu",
    "kannada": "kn",
    "malayalam": "ml",
    "urdu": "ur",
    "odia": "or",
    "rajasthani": "raj",
    "assamese": "as",
    "sanskrit": "sa",
}

def _language_to_apple_code(lang: str) -> str:
    """Map our language name to Apple language code."""
    l = (lang or "").strip().lower()
    if not l:
        return "en"
    for key, code in LANGUAGE_TO_APPLE_CODE.items():
        if key in l:
            return code
    return "en"


# Our price_category -> Apple wholesale_price_tier (from samples: 32, 34, 98, 100)
PRICE_TIER = {
    "mid": "32",
    "budget": "34",
    "full": "98",
    "premium": "100",
}

def _price_tier(release: Release) -> str:
    pc = (getattr(release, "price_category", None) or "").strip().lower()
    return PRICE_TIER.get(pc, "34")


def _preorder_xml_fragment(preorder_date_str: str) -> str:
    """
    Apple Music Package music5.3: pre-order sales start inside <product>.
    Element name is preorder_sales_start_date (not preorder_start_date); see Apple Music Specification 5.3.
    """
    s = (preorder_date_str or "").strip()
    if not s:
        return ""
    # YYYY-MM-DD from DateField only — no XML escaping needed
    return f"<preorder_sales_start_date>{s}</preorder_sales_start_date>"


def _apple_music_product_xml(
    release: Release,
    rel_date_str: str,
    track_rel_date: str,
    price_tier: str,
    for_track: bool,
    preorder_date_str: str = "",
) -> str:
    """
    Build single <product>...</product> inner XML for album or track per Apple commercial model.
    Merlin Bridge checklist: streaming_only (sale off, stream on) vs retail_only (sale on, stream off).
    Optional preorder_date_str: emitted as <preorder_sales_start_date> only where Apple allows it
    (album <product> only — not on track <product>; see ITMS-4020). Omitted entirely for retail_only
    (download-only offer: preorder date is not allowed on that offer).

    Note: <preorder_type> (instant-gratification / standard) belongs on the <track> element as a
    sibling of <products>, not inside <product> — placing it inside <product> triggers "element not
    expected" from the music5.3 schema. See Apple Music Specification (pre-orders / instant gratification).
    """
    mode = (getattr(release, "apple_music_commercial_model", None) or "both").strip().lower()
    wt = "98" if for_track else price_tier
    # ITMS-4020 "Preorder date is not allowed on this offer": no preorder_sales_start_date on track
    # products, and not on retail_only (sale on / stream off) products.
    po = ""
    if (preorder_date_str or "").strip() and not for_track and mode != "retail_only":
        po = _preorder_xml_fragment(preorder_date_str)
    if mode == "streaming_only":
        d = track_rel_date if for_track else rel_date_str
        return (
            f"<product><territory>WW</territory>{po}"
            f"<cleared_for_sale>false</cleared_for_sale>"
            f"<cleared_for_stream>true</cleared_for_stream>"
            f"<stream_start_date>{d}</stream_start_date></product>"
        )
    if mode == "retail_only":
        d = track_rel_date if for_track else rel_date_str
        return (
            f"<product><territory>WW</territory>{po}"
            f"<wholesale_price_tier>{wt}</wholesale_price_tier>"
            f"<sales_start_date>{d}</sales_start_date>"
            f"<cleared_for_sale>true</cleared_for_sale>"
            f"<cleared_for_stream>false</cleared_for_stream></product>"
        )
    # both (default): streaming + download
    if for_track:
        return (
            f"<product><territory>WW</territory>{po}<cleared_for_sale>true</cleared_for_sale>"
            f"<wholesale_price_tier>{wt}</wholesale_price_tier><cleared_for_stream>true</cleared_for_stream>"
            f"<stream_start_date>{track_rel_date}</stream_start_date></product>"
        )
    return (
        f"<product><territory>WW</territory>{po}<wholesale_price_tier>{price_tier}</wholesale_price_tier>"
        f"<sales_start_date>{rel_date_str}</sales_start_date><cleared_for_sale>true</cleared_for_sale>"
        f"<cleared_for_stream>true</cleared_for_stream><stream_start_date>{rel_date_str}</stream_start_date></product>"
    )


# Our artist role -> Apple role (Style Guide 2.13: Featuring/With for guests; Performer, Vocals, etc.)
OUR_ROLE_TO_APPLE = {
    "primary artist": "Performer",
    "performer": "Performer",
    "vocals": "Vocals",
    "featured artist": "Featuring",
    "featuring": "Featuring",
    "with": "With",
    "composer": "Composer",
    "songwriter": "Songwriter",
    "lyricist": "Songwriter",
    "producer": "Producer",
    "co-producer": "Producer",
}

def _apple_roles(role: str) -> List[str]:
    """Map our single role to one or more Apple roles."""
    r = (role or "").strip().lower()
    if r in OUR_ROLE_TO_APPLE:
        return [OUR_ROLE_TO_APPLE[r]]
    if r in ("primary artist", "performer", "vocals"):
        return ["Performer", "Vocals"]
    return ["Performer"]


def _escape(s: str) -> str:
    """Escape for XML text content."""
    if s is None:
        return ""
    return html.escape(str(s).strip(), quote=True)


# Emoji and symbols to strip per Apple Music Style Guide 1.10: do not use emoji in titles, artist names, or metadata
_EMOJI_PATTERN = re.compile(
    "["
    "\U0001F300-\U0001F9FF"  # Misc Symbols and Pictographs, Emoticons, etc.
    "\U0001FA00-\U0001FA6F"
    "\U0001FA70-\U0001FAFF"
    "\U00002702-\U000027B0"
    "\U000024C2-\U0001F251"
    "\U0001F600-\U0001F64F"
    "\U0001F680-\U0001F6FF"
    "\U00002600-\U000026FF"
    "\U00002700-\U000027BF"
    "]+",
    flags=re.UNICODE,
)


def _strip_emoji(s: str) -> str:
    """Remove emoji from string for Apple Music Style Guide compliance (1.10)."""
    if not s:
        return s
    return _EMOJI_PATTERN.sub("", str(s)).strip()


def _release_apple_atmos_delivery_allowed(release: Release) -> bool:
    """Dolby Atmos in metadata/package only when the release owner has the per-user flag."""
    u = getattr(release, "created_by", None)
    return bool(u and getattr(u, "apple_music_dolby_atmos_enabled", False))


def _isrc_alphanumeric(isrc: str) -> str:
    """Apple immersive ISRC: letters and digits only, no dashes."""
    return "".join(c for c in (isrc or "").strip().upper() if c.isalnum())


def _track_atmos_file_info(
    file_info: Dict[str, Dict[str, Any]], track_index: int
) -> Optional[Dict[str, Any]]:
    key = f"track_{track_index}_atmos"
    info = (file_info or {}).get(key) or {}
    if not info:
        return None
    if not (info.get("md5") or "").strip():
        return None
    return info


def _track_audio_xml_block(
    upc: str,
    track_num: int,
    audio_extension: str,
    stereo_info: Dict[str, Any],
    atmos_info: Optional[Dict[str, Any]],
) -> str:
    """
    Single-track audio: either legacy <audio_file> (stereo only) or <assets><asset type="full">
    with audio.2_0 + audio.object_based when Dolby Atmos is delivered. See Apple Music Spec 5.3
    (Immersive / Dolby Atmos).
    """
    ext = (audio_extension or "wav").strip().lstrip(".") or "wav"
    stereo_name = f"{upc}_01_{track_num:03d}.{ext}"
    t_size = int(stereo_info.get("size") or 0)
    t_md5 = (stereo_info.get("md5") or "").strip().lower()

    if not atmos_info:
        return (
            f"<audio_file><file_name>{_escape(stereo_name)}</file_name>"
            f"<size>{t_size}</size><checksum type=\"md5\">{_escape(t_md5)}</checksum></audio_file>"
        )

    atmos_name = f"{upc}_01_{track_num:03d}_atmos.wav"
    a_size = int(atmos_info.get("size") or 0)
    a_md5 = (atmos_info.get("md5") or "").strip().lower()
    atmos_isrc = _isrc_alphanumeric(atmos_info.get("isrc") or "")
    isrc_attr = f' external_identifier.isrc="{_escape(atmos_isrc)}"' if atmos_isrc else ""

    stereo_df = (
        f'<data_file role="audio.2_0"><file_name>{_escape(stereo_name)}</file_name>'
        f"<size>{t_size}</size><checksum type=\"md5\">{_escape(t_md5)}</checksum></data_file>"
    )
    atmos_df = (
        f'<data_file role="audio.object_based"{isrc_attr}><file_name>{_escape(atmos_name)}</file_name>'
        f"<size>{a_size}</size><checksum type=\"md5\">{_escape(a_md5)}</checksum></data_file>"
    )
    return f"<assets><asset type=\"full\">{stereo_df}{atmos_df}</asset></assets>"


def _track_preorder_type_element(release: Release, track: Track, preorder_date_str: str) -> str:
    """
    Apple Music Spec: during a pre-order, each track should include <preorder_type> under <track>
    (not inside <product>): instant-gratification for IG tracks, standard for others.
    Omitted when there is no pre-order date or when commercial model is retail_only (no album pre-order).
    """
    mode = (getattr(release, "apple_music_commercial_model", None) or "both").strip().lower()
    if mode == "retail_only":
        return ""
    if not (preorder_date_str or "").strip():
        return ""
    ig = bool(getattr(track, "apple_music_instant_grat", False))
    val = "instant-gratification" if ig else "standard"
    return f"<preorder_type>{val}</preorder_type>"


def build_apple_itunes_metadata(
    release: Release,
    upc: str,
    file_info: Optional[Dict[str, Dict[str, Any]]] = None,
    provider: str = "Merlin4",
    audio_extension: str = "wav",
) -> str:
    """
    Build Apple iTunes Importer (music5.3) metadata XML for the given release.
    file_info: optional dict mapping logical key to {size, md5, file_name}.
      Keys: "artwork" -> artwork file; "track_0", "track_1", ... -> audio files.
      If omitted, size/checksum are omitted (Apple may require them; delivery should pass them).
    provider: string for <provider> (e.g. Merlin4).
    Returns XML string (utf-8).
    """
    file_info = file_info or {}
    # Merlin expects an exact DPID value on the album level; strip hyphens/non-alphanumerics
    # to match the “without hyphens in XML” rule from our DDEX config.
    raw_dpid = (COIN_DIGITAL_PARTY_ID or "").strip()
    dpid = re.sub(r"[^A-Za-z0-9_]", "", raw_dpid) or "PADPIDA2023031502Y"
    vendor_id_release = f"{dpid}_{upc}"

    # Release dates
    rel_date = release.digital_release_date or release.original_release_date
    rel_date_str = rel_date.strftime("%Y-%m-%d") if rel_date else "2026-01-01"
    orig_date = getattr(release, "original_release_date", None) or rel_date
    orig_date_str = orig_date.strftime("%Y-%m-%d") if orig_date else rel_date_str

    po_field = getattr(release, "apple_music_preorder_start_date", None)
    preorder_date_str = po_field.strftime("%Y-%m-%d") if po_field else ""
    if po_field and rel_date and po_field >= rel_date:
        logger.warning(
            "apple_music_preorder_start_date / preorder_sales_start_date (%s) should be before street date (%s) for release id=%s",
            preorder_date_str,
            rel_date_str,
            release.id,
        )

    label_name = "Unknown"
    if getattr(release, "label_id", None) and release.label:
        label_name = (release.label.label or "").strip() or "Unknown"
    label_name = _escape(label_name)

    c_year = (getattr(release, "copyright_recording_year", None) or "").strip() or "2026"
    c_text = (getattr(release, "copyright_recording_text", None) or "").strip() or label_name or "Unknown"
    copyright_pline = _escape(f"{c_year} {c_text}")
    copyright_cline = copyright_pline

    lang_apple = _language_to_apple_code(getattr(release, "language", None) or "")
    genre_apple = _genre_to_apple_code(getattr(release, "primary_genre", None) or "")
    price_tier = _price_tier(release)

    # Artwork
    artwork_file_name = f"{upc}.jpg"
    artwork_el = ""
    art_info = file_info.get("artwork", {})
    if art_info:
        size = art_info.get("size", 0)
        md5 = (art_info.get("md5") or "").strip().lower()
        artwork_el = f'<artwork_files><file><file_name>{_escape(artwork_file_name)}</file_name><size>{size}</size><checksum type="md5">{_escape(md5)}</checksum></file></artwork_files>'
    else:
        artwork_el = f'<artwork_files><file><file_name>{_escape(artwork_file_name)}</file_name><size>0</size><checksum type="md5"></checksum></file></artwork_files>'

    # Release-level artists
    release_artists = list(
        RelatedArtists.objects.filter(release=release, relation_key="release").select_related("artist")
    )
    artists_el = _build_artists_xml(release_artists)

    tracks = list(Track.objects.filter(release=release).order_by("id"))
    track_count = len(tracks)

    # Products (release level) — streaming_only / retail_only / both per release.apple_music_commercial_model
    album_product = _apple_music_product_xml(
        release, rel_date_str, rel_date_str, price_tier, for_track=False, preorder_date_str=preorder_date_str
    )
    products_el = f"<products>{album_product}</products>"

    # Tracks
    tracks_el_parts = []
    for idx, track in enumerate(tracks):
        isrc = (track.isrc or "").strip().upper() or f"TMP{release.id:06d}{idx:02d}"
        vendor_id_track = f"{vendor_id_release}_{isrc}"
        track_artists = list(
            RelatedArtists.objects.filter(track=track, relation_key="track").select_related("artist")
        )
        if not track_artists:
            track_artists = release_artists
        track_artist_xml = _build_artists_xml(track_artists)
        track_genre = _genre_to_apple_code(getattr(track, "primary_genre", None) or release.primary_genre or "")
        track_title = _escape(_strip_emoji((track.title or "").strip()) or "Track")
        track_rel_date = rel_date_str
        track_label = label_name
        track_pline = copyright_pline
        # Style Guide 6.1/6.2: Explicit / Clean flagging; only flag Clean if there is a corresponding explicit version
        explicit_raw = (getattr(track, "explicit_lyrics", None) or "").strip().lower()
        explicit = "none"
        if explicit_raw in ("explicit", "cleaned"):
            explicit = "explicit"
        elif explicit_raw in ("clean", "clean version", "edited"):
            explicit = "clean"
        vol, track_num = 1, idx + 1
        ext = (audio_extension or "wav").strip().lstrip(".") or "wav"
        t_info = file_info.get(f"track_{idx}", {})
        t_size = t_info.get("size", 0)
        t_md5 = (t_info.get("md5") or "").strip().lower()
        atmos_info = None
        if _release_apple_atmos_delivery_allowed(release):
            raw_atmos_isrc = (getattr(track, "apple_music_dolby_atmos_isrc", None) or "").strip()
            raw_atmos_url = (getattr(track, "apple_music_dolby_atmos_url", None) or "").strip()
            fi_atmos = _track_atmos_file_info(file_info, idx)
            if fi_atmos and raw_atmos_url and _isrc_alphanumeric(raw_atmos_isrc):
                atmos_info = {**fi_atmos, "isrc": _isrc_alphanumeric(raw_atmos_isrc)}
            elif fi_atmos and raw_atmos_url and not _isrc_alphanumeric(raw_atmos_isrc):
                logger.warning(
                    "Track id=%s: Dolby Atmos file present in package but apple_music_dolby_atmos_isrc is missing; "
                    "emitting stereo-only audio in metadata.",
                    track.id,
                )
            elif raw_atmos_url or raw_atmos_isrc:
                logger.warning(
                    "Track id=%s: partial Dolby Atmos fields (need URL, secondary ISRC, and successful S3/file_info); "
                    "using stereo-only in metadata.",
                    track.id,
                )
        audio_block = _track_audio_xml_block(
            upc,
            track_num,
            ext,
            {"size": t_size, "md5": t_md5},
            atmos_info,
        )
        audio_lang = _language_to_apple_code(getattr(track, "language", None) or getattr(release, "language", None) or "")
        track_product_inner = _apple_music_product_xml(
            release,
            rel_date_str,
            track_rel_date,
            price_tier,
            for_track=True,
            preorder_date_str=preorder_date_str,
        )
        preorder_type_el = _track_preorder_type_element(release, track, preorder_date_str)
        track_xml = f'<track><vendor_id>{_escape(vendor_id_track)}</vendor_id><isrc>{_escape(isrc)}</isrc><title>{track_title}</title><original_release_date>{track_rel_date}</original_release_date><genres><genre code="{track_genre}"/></genres>{preorder_type_el}<products>{track_product_inner}</products><label_name>{track_label}</label_name><copyright_pline>{track_pline}</copyright_pline><explicit_content>{explicit}</explicit_content><volume_number>{vol}</volume_number><track_number>{track_num}</track_number>{audio_block}<artists>{track_artist_xml}</artists><audio_language>{audio_lang}</audio_language></track>'
        tracks_el_parts.append(track_xml)

    tracks_el = "".join(tracks_el_parts)
    title_el = _escape(_strip_emoji((release.title or "").strip()) or "Release")

    # Bridge parses UPC from XML; ensure digits-only so parsers don't fail (no whitespace/hidden chars)
    upc_clean = re.sub(r"\D", "", str(upc))[:13] if upc else ""
    if len(upc_clean) == 12:
        upc_clean = "0" + upc_clean
    xml = f'''<?xml version='1.0' encoding='UTF-8'?>
<package xmlns="http://apple.com/itunes/importer" version="music5.3"><language>{lang_apple}</language><provider>{_escape(provider)}</provider><album><vendor_id>{_escape(vendor_id_release)}</vendor_id><upc>{upc_clean}</upc><title>{title_el}</title><original_release_date>{orig_date_str}</original_release_date><label_name>{label_name}</label_name><genres><genre code="{genre_apple}"/></genres><copyright_pline>{copyright_pline}</copyright_pline><copyright_cline>{copyright_cline}</copyright_cline>{artwork_el}<track_count>{track_count}</track_count>{products_el}<artists>{artists_el}</artists><tracks>{tracks_el}</tracks></album></package>'''
    return xml


def build_apple_itunes_takedown_metadata(
    release: Release,
    upc: str,
    provider: str = "Merlin4",
) -> str:
    """
    Build Apple iTunes Importer (music5.3) metadata XML for a TAKEDOWN only.
    Matches Bridge/Sonosuite format: album-level metadata, no tracks, no artwork,
    and <product><cleared_for_sale>false</cleared_for_sale><cleared_for_stream>false</cleared_for_stream></product>
    so Bridge/Apple show the release as Takedown. Package as {upc}.itmsp.zip (metadata.xml only) and upload to same path as delivery (e.g. apple/regular/).
    """
    raw_dpid = (COIN_DIGITAL_PARTY_ID or "").strip()
    dpid = re.sub(r"[^A-Za-z0-9_]", "", raw_dpid) or "PADPIDA2023031502Y"
    vendor_id_release = f"{dpid}_{upc}"

    rel_date = release.digital_release_date or release.original_release_date
    rel_date_str = rel_date.strftime("%Y-%m-%d") if rel_date else "2026-01-01"
    orig_date = getattr(release, "original_release_date", None) or rel_date
    orig_date_str = orig_date.strftime("%Y-%m-%d") if orig_date else rel_date_str

    label_name = "Unknown"
    if getattr(release, "label_id", None) and release.label:
        label_name = (release.label.label or "").strip() or "Unknown"
    label_name = _escape(label_name)

    c_year = (getattr(release, "copyright_recording_year", None) or "").strip() or "2026"
    c_text = (getattr(release, "copyright_recording_text", None) or "").strip() or label_name or "Unknown"
    copyright_pline = _escape(f"{c_year} {c_text}")
    copyright_cline = copyright_pline

    lang_apple = _language_to_apple_code(getattr(release, "language", None) or "")
    genre_apple = _genre_to_apple_code(getattr(release, "primary_genre", None) or "")

    release_artists = list(
        RelatedArtists.objects.filter(release=release, relation_key="release").select_related("artist")
    )
    artists_el = _build_artists_xml(release_artists)

    # Takedown: product with cleared_for_sale and cleared_for_stream false (no price/dates)
    products_el = "<products><product><territory>WW</territory><cleared_for_sale>false</cleared_for_sale><cleared_for_stream>false</cleared_for_stream></product></products>"

    title_el = _escape(_strip_emoji((release.title or "").strip()) or "Release")
    upc_clean = re.sub(r"\D", "", str(upc))[:13] if upc else ""
    if len(upc_clean) == 12:
        upc_clean = "0" + upc_clean

    xml = f'''<?xml version='1.0' encoding='UTF-8'?>
<package xmlns="http://apple.com/itunes/importer" version="music5.3"><language>{lang_apple}</language><provider>{_escape(provider)}</provider><album><vendor_id>{_escape(vendor_id_release)}</vendor_id><upc>{upc_clean}</upc><title>{title_el}</title><original_release_date>{orig_date_str}</original_release_date><label_name>{label_name}</label_name><genres><genre code="{genre_apple}"/></genres><copyright_pline>{copyright_pline}</copyright_pline><copyright_cline>{copyright_cline}</copyright_cline>{products_el}<artists>{artists_el}</artists></album></package>'''
    return xml


def _build_artists_xml(artist_rels: List) -> str:
    """Build <artist>...</artist> fragments for album or track."""
    parts = []
    for ra in artist_rels:
        name = (getattr(ra.artist, "name", None) or "").strip()
        if not name:
            continue
        apple_id = getattr(ra.artist, "apple_music_id", None) or getattr(ra.artist, "apple_id", None)
        # Apple schema: apple_id must match [0-9]* (digits only); strip quotes/whitespace and take digits only
        apple_id_str = "".join(c for c in str(apple_id or "").strip() if c.isdigit())
        roles = []
        role_raw = (ra.role or "").strip().lower()
        for r in _apple_roles(role_raw):
            if r not in roles:
                roles.append(r)
        if not roles:
            roles = ["Performer"]
        # Style Guide 2.13: Artists with Featuring or With roles must not be marked Primary
        primary = "true" if role_raw in ("primary artist", "performer", "vocals") else "false"
        if role_raw in ("featuring", "featured artist", "with"):
            primary = "false"
        roles_xml = "".join(f"<role>{_escape(r)}</role>" for r in roles)
        apple_id_el = f"<apple_id>{_escape(apple_id_str)}</apple_id>" if apple_id_str else ""
        name_clean = _strip_emoji(name)
        if not name_clean:
            continue
        parts.append(f"<artist><artist_name>{_escape(name_clean)}</artist_name>{apple_id_el}<roles>{roles_xml}</roles><primary>{primary}</primary></artist>")
    return "".join(parts)
