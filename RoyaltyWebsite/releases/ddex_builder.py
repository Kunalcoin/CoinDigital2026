"""
Build DDEX ERN 4.3 NewReleaseMessage (Insert) for Spotify.
Matches Sonosuite/Dream Entertainment sample structure.
"""
import re
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional
import xml.etree.ElementTree as ET
from xml.dom import minidom

from releases.ddex_config import (
    COIN_DIGITAL_PARTY_ID,
    COIN_DIGITAL_PARTY_NAME,
    SPOTIFY_PARTY_ID,
    SPOTIFY_PARTY_NAME,
    TIKTOK_PARTY_ID,
    TIKTOK_PARTY_NAME,
    AUDIOMACK_PARTY_ID,
    AUDIOMACK_PARTY_NAME,
    META_FACEBOOK_SRP_PARTY_ID,
    META_FACEBOOK_SRP_PARTY_NAME,
    META_FACEBOOK_AAP_PARTY_ID,
    META_FACEBOOK_AAP_PARTY_NAME,
    DEFAULT_TERRITORY,
    ERN_NAMESPACE,
    ERN_SCHEMA_LOCATION,
    RELEASE_PROFILE,
    LANGUAGE_SCRIPT_CODE,
    AVS_VERSION,
    DEAL_SUBSCRIPTION,
    DEAL_ADVERTISEMENT,
    USE_CONDITIONAL_DOWNLOAD,
    USE_ON_DEMAND_STREAM,
    USE_NON_INTERACTIVE_STREAM,
    DEAL_RIGHTS_CLAIM_MODEL,
    USE_USER_MAKE_AVAILABLE_USER_PROVIDED,
    USE_USER_MAKE_AVAILABLE_LABEL_PROVIDED,
    RIGHTS_CLAIM_POLICY_MONETIZE,
    RIGHTS_CONTROLLER_ROLE,
    DEAL_PAY_AS_YOU_GO,
    USE_PERMANENT_DOWNLOAD,
)
from releases.ddex_dsp_registry import get_recipient, get_deal_profile
from releases.ddex_language_iso import language_to_iso
from releases.ddex_duration import duration_seconds, duration_to_ddex
from releases.models import Release, Track, RelatedArtists, Artist, Label


# XML namespaces
NS = {"ern": ERN_NAMESPACE}
NS_XSI = "http://www.w3.org/2001/XMLSchema-instance"


def _slug(s: str) -> str:
    """PartyReference-safe slug: alphanumeric + underscore."""
    s = (s or "").strip().lower()
    s = re.sub(r"[^a-z0-9]+", "_", s)
    return s.strip("_") or "unknown"


def _el(parent: ET.Element, tag: str, text: Optional[str] = None, **attrib) -> ET.Element:
    """Create child with ern namespace."""
    child = ET.SubElement(parent, f"{{{ERN_NAMESPACE}}}{tag}", **attrib)
    if text is not None:
        child.text = text
    return child


def _el_cdata(parent: ET.Element, tag: str, text: str, **attrib) -> ET.Element:
    """Create child with CDATA-safe text (we escape instead of CDATA for ElementTree)."""
    child = ET.SubElement(parent, f"{{{ERN_NAMESPACE}}}{tag}", **attrib)
    child.text = text
    return child


def _release_type_ddex(album_format: str) -> str:
    """Map Release.ALBUM_FORMAT to DDEX ReleaseType."""
    return {"single": "Single", "ep": "EP", "album": "Album"}.get(
        (album_format or "").lower(), "Single"
    )


def _release_profile_version(album_format: str) -> str:
    """Use ERN 4.3 schema-allowed ReleaseProfileVersionId. Audio = Album/EP only."""
    fmt = (album_format or "").strip().lower()
    if fmt in ("ep", "album"):
        return "Audio"
    return "SimpleAudioSingle"  # Single, default, or unknown


def _parental_warning(explicit_lyrics: str) -> str:
    """Map explicit_lyrics to DDEX ParentalWarningType."""
    if (explicit_lyrics or "").lower() in ("explicit", "cleaned"):
        return "Explicit"
    return "NotExplicit"


def _get_display_artist_names(related: List) -> str:
    """Primary Artist names for display, comma-separated."""
    names = []
    for ra in related:
        if ra.role == "Primary Artist" and ra.artist:
            names.append(ra.artist.name)
    return ", ".join(names) if names else "Unknown"


def _get_track_duration(
    track: Track,
    track_index: int,
    audio_paths_by_index: Optional[Dict[int, str]] = None,
) -> str:
    """Return DDEX duration for track: from audio file or PT00H00M00S."""
    path_or_url = None
    if audio_paths_by_index and track_index in audio_paths_by_index:
        path_or_url = audio_paths_by_index[track_index]
    if not path_or_url and getattr(track, "audio_track_url", None):
        path_or_url = track.audio_track_url
    secs = duration_seconds(path_or_url) if path_or_url else None
    return duration_to_ddex(secs)


def _role_to_ddex_display_artist_role(role: str) -> Optional[str]:
    """Map our role to DDEX DisplayArtistRole (MainArtist, Composer, etc.)."""
    r = (role or "").strip()
    if r in ("Primary Artist", "Performer", "Featured Artist"):
        return "MainArtist"
    if r == "Composer":
        return "Composer"
    return None


def _role_to_ddex_contributor_role(role: str) -> Optional[str]:
    """Map our role to DDEX Contributor Role (Lyricist, Arranger, etc.)."""
    r = (role or "").strip()
    if r == "Lyricist":
        return "Lyricist"
    if r in ("Producer", "Co-Producer", "Arranger", "Programming"):
        return "Arranger"
    return None


def _recipient_for_store(store: str) -> tuple:
    """Return (PartyId, PartyName) for the given DSP. Uses registry first, then fallback to config."""
    store = (store or "spotify").strip().lower()
    recipient = get_recipient(store)
    if recipient:
        return recipient
    if store == "tiktok":
        return (TIKTOK_PARTY_ID, TIKTOK_PARTY_NAME)
    if store == "audiomack":
        return (AUDIOMACK_PARTY_ID, AUDIOMACK_PARTY_NAME)
    if store == "meta":
        return (META_FACEBOOK_SRP_PARTY_ID, META_FACEBOOK_SRP_PARTY_NAME)
    return (SPOTIFY_PARTY_ID, SPOTIFY_PARTY_NAME)


def _recipients_for_store(store: str) -> List[tuple]:
    """Return list of (PartyId, PartyName) for MessageRecipient(s). Meta requires two recipients (SRP + AAP)."""
    store = (store or "spotify").strip().lower()
    if store == "meta":
        return [
            (META_FACEBOOK_SRP_PARTY_ID, META_FACEBOOK_SRP_PARTY_NAME),
            (META_FACEBOOK_AAP_PARTY_ID, META_FACEBOOK_AAP_PARTY_NAME),
        ]
    return [_recipient_for_store(store)]


def build_new_release_message(
    release: Release,
    audio_paths_by_index: Optional[Dict[int, str]] = None,
    message_thread_id: Optional[str] = None,
    store: str = "spotify",
    message_control_type: str = "LiveMessage",
    linked_message_id: Optional[str] = None,
    takedown_immediate: Optional[bool] = None,
    takedown_end_date: Optional[str] = None,
    resource_md5_map: Optional[Dict[str, str]] = None,
) -> str:
    """
    Build ERN 4.3 NewReleaseMessage XML for the given Release.
    Supports Single, EP, and Album (via release.album_format).
    audio_paths_by_index: optional map {track_index: local path or URL} for duration extraction.
    store: DSP code from registry (e.g. spotify, tiktok, jiosaavn, gaana). We use DDEX 4.3 for all.
    message_control_type: "LiveMessage" (production), "TestMessage" (testing), or "UpdateMessage" (update).
    linked_message_id: for UpdateMessage, the MessageId of the original Insert message.
    takedown_immediate: for Gaana, set True to send immediate takedown (TakeDown tag in DealTerms).
    takedown_end_date: for Gaana, set YYYY-MM-DD for time-based takedown (ValidityPeriod EndDate).
    resource_md5_map: optional map { "resources/coverart.jpg": "hex", "resources/1_1.flac": "hex", ... } for ByteDance/TikTok (adds HashSum MD5 per their sample).
    Returns XML string (utf-8).
    """
    root = ET.Element(
        f"{{{ERN_NAMESPACE}}}NewReleaseMessage",
        attrib={
            "ReleaseProfileVersionId": _release_profile_version(release.album_format),
            "LanguageAndScriptCode": LANGUAGE_SCRIPT_CODE,
            "AvsVersionId": AVS_VERSION,
        },
    )
    root.set(f"{{{NS_XSI}}}schemaLocation", ERN_SCHEMA_LOCATION)

    # ----- MessageHeader -----
    thread_id = message_thread_id or uuid.uuid4().hex
    message_id = uuid.uuid4().hex
    msg_created = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00")

    header = ET.SubElement(root, f"{{{ERN_NAMESPACE}}}MessageHeader")
    _el(header, "MessageThreadId", thread_id)
    _el(header, "MessageId", message_id)
    upc_header = (release.upc or "").strip() or str(release.id)
    _el(header, "MessageFileName", f"{upc_header}.xml")
    sender = ET.SubElement(header, f"{{{ERN_NAMESPACE}}}MessageSender")
    _el(sender, "PartyId", COIN_DIGITAL_PARTY_ID)
    name_el = ET.SubElement(sender, f"{{{ERN_NAMESPACE}}}PartyName")
    _el(name_el, "FullName", COIN_DIGITAL_PARTY_NAME)
    for rec_party_id, rec_party_name in _recipients_for_store(store):
        recipient = ET.SubElement(header, f"{{{ERN_NAMESPACE}}}MessageRecipient")
        _el(recipient, "PartyId", rec_party_id)
        rec_name = ET.SubElement(recipient, f"{{{ERN_NAMESPACE}}}PartyName")
        _el(rec_name, "FullName", rec_party_name)
    _el(header, "MessageCreatedDateTime", msg_created)
    control_type = (message_control_type or "LiveMessage").strip()
    if control_type not in ("LiveMessage", "TestMessage", "UpdateMessage"):
        control_type = "LiveMessage"
    _el(header, "MessageControlType", control_type)
    if control_type == "UpdateMessage" and linked_message_id and linked_message_id.strip():
        _el(header, "LinkedMessageId", linked_message_id.strip())

    # Audiomack: UpdateIndicator per their onboard samples (new.xml / update.xml / takedown.xml)
    if (store or "").strip().lower() == "audiomack":
        update_indicator = "UpdateMessage" if control_type == "UpdateMessage" else "OriginalMessage"
        _el(root, "UpdateIndicator", update_indicator)

    # ----- Collect artists and build PartyList -----
    release_artists = list(
        RelatedArtists.objects.filter(release=release, relation_key="release").select_related("artist")
    )
    tracks = list(
        Track.objects.filter(release=release).order_by("id")
    )
    track_artist_rels = {}
    for t in tracks:
        track_artist_rels[t.id] = list(
            RelatedArtists.objects.filter(track=t, relation_key="track").select_related("artist")
        )

    seen_artist_ids = set()
    artist_refs = {}  # artist_id -> PartyReference
    party_list = ET.SubElement(root, f"{{{ERN_NAMESPACE}}}PartyList")

    for ra in release_artists:
        if ra.artist_id and ra.artist_id not in seen_artist_ids:
            seen_artist_ids.add(ra.artist_id)
            ref = "P_" + _slug(ra.artist.name)
            artist_refs[ra.artist_id] = ref
            party = ET.SubElement(party_list, f"{{{ERN_NAMESPACE}}}Party")
            _el(party, "PartyReference", ref)
            pname = ET.SubElement(party, f"{{{ERN_NAMESPACE}}}PartyName")
            _el_cdata(pname, "FullName", (ra.artist.name or "").strip())
            pid = ET.SubElement(party, f"{{{ERN_NAMESPACE}}}PartyId")
            _el(pid, "ProprietaryId", str(ra.artist.id), **{"Namespace": f"DPID:{COIN_DIGITAL_PARTY_ID}"})
            if getattr(ra.artist, "spotify_id", None) and ra.artist.spotify_id.strip():
                _el(pid, "ProprietaryId", ra.artist.spotify_id.strip(), **{"Namespace": "spotify"})
            # Audiomack sample: PartyId Namespace PADPIDA2017103008S for artist mapping (when we have audiomack_id)
            if (store or "").strip().lower() == "audiomack":
                aid = getattr(ra.artist, "audiomack_id", None)
                if aid is not None and str(aid).strip():
                    _el(pid, "ProprietaryId", str(aid).strip(), **{"Namespace": f"DPID:{AUDIOMACK_PARTY_ID}"})
            # Meta sample: PartyId Namespace Facebook AAP for artist mapping; ArtistProfilePage (Facebook/Instagram)
            if (store or "").strip().lower() == "meta":
                mid = getattr(ra.artist, "meta_artist_id", None) or getattr(ra.artist, "facebook_artist_id", None)
                if mid is not None and str(mid).strip():
                    _el(pid, "ProprietaryId", str(mid).strip(), **{"Namespace": META_FACEBOOK_AAP_PARTY_ID})
                fb_url = (
                    getattr(ra.artist, "facebook_profile_url", None)
                    or getattr(ra.artist, "facebook_url", None)
                    or getattr(ra.artist, "facebook_page", None)
                )
                if fb_url and str(fb_url).strip():
                    _el(party, "ArtistProfilePage", str(fb_url).strip())
                ig_url = getattr(ra.artist, "instagram_profile_url", None) or getattr(ra.artist, "instagram_url", None)
                if ig_url and str(ig_url).strip():
                    _el(party, "ArtistProfilePage", str(ig_url).strip())
    for t in tracks:
        for ra in track_artist_rels.get(t.id, []):
            if ra.artist_id and ra.artist_id not in seen_artist_ids:
                seen_artist_ids.add(ra.artist_id)
                ref = "P_" + _slug(ra.artist.name)
                artist_refs[ra.artist_id] = ref
                party = ET.SubElement(party_list, f"{{{ERN_NAMESPACE}}}Party")
                _el(party, "PartyReference", ref)
                pname = ET.SubElement(party, f"{{{ERN_NAMESPACE}}}PartyName")
                _el_cdata(pname, "FullName", (ra.artist.name or "").strip())
                pid = ET.SubElement(party, f"{{{ERN_NAMESPACE}}}PartyId")
                _el(pid, "ProprietaryId", str(ra.artist.id), **{"Namespace": f"DPID:{COIN_DIGITAL_PARTY_ID}"})
                if getattr(ra.artist, "spotify_id", None) and ra.artist.spotify_id.strip():
                    _el(pid, "ProprietaryId", ra.artist.spotify_id.strip(), **{"Namespace": "spotify"})
                if (store or "").strip().lower() == "audiomack":
                    aid = getattr(ra.artist, "audiomack_id", None)
                    if aid is not None and str(aid).strip():
                        _el(pid, "ProprietaryId", str(aid).strip(), **{"Namespace": f"DPID:{AUDIOMACK_PARTY_ID}"})
                if (store or "").strip().lower() == "meta":
                    mid = getattr(ra.artist, "meta_artist_id", None) or getattr(ra.artist, "facebook_artist_id", None)
                    if mid is not None and str(mid).strip():
                        _el(pid, "ProprietaryId", str(mid).strip(), **{"Namespace": META_FACEBOOK_AAP_PARTY_ID})
                    fb_url = (
                        getattr(ra.artist, "facebook_profile_url", None)
                        or getattr(ra.artist, "facebook_url", None)
                        or getattr(ra.artist, "facebook_page", None)
                    )
                    if fb_url and str(fb_url).strip():
                        _el(party, "ArtistProfilePage", str(fb_url).strip())
                    ig_url = getattr(ra.artist, "instagram_profile_url", None) or getattr(ra.artist, "instagram_url", None)
                    if ig_url and str(ig_url).strip():
                        _el(party, "ArtistProfilePage", str(ig_url).strip())

    label_name = "Unknown"
    label_ref = "P_label"
    if getattr(release, "label_id", None) and release.label:
        label_name = (release.label.label or "").strip() or "Unknown"
        label_ref = "P_" + _slug(label_name) + "_label"
        party = ET.SubElement(party_list, f"{{{ERN_NAMESPACE}}}Party")
        _el(party, "PartyReference", label_ref)
        pname = ET.SubElement(party, f"{{{ERN_NAMESPACE}}}PartyName")
        _el_cdata(pname, "FullName", label_name)

    vendor_ref = "P_vendor_code"
    party = ET.SubElement(party_list, f"{{{ERN_NAMESPACE}}}Party")
    _el(party, "PartyReference", vendor_ref)
    pname = ET.SubElement(party, f"{{{ERN_NAMESPACE}}}PartyName")
    _el_cdata(pname, "FullName", COIN_DIGITAL_PARTY_NAME)
    pid = ET.SubElement(party, f"{{{ERN_NAMESPACE}}}PartyId")
    _el(pid, "ProprietaryId", COIN_DIGITAL_PARTY_ID, **{"Namespace": COIN_DIGITAL_PARTY_ID})

    # ----- ResourceList -----
    resource_list = ET.SubElement(root, f"{{{ERN_NAMESPACE}}}ResourceList")
    lang_iso_release = language_to_iso(getattr(release, "language", None) or "")

    p_year = (getattr(release, "copyright_recording_year", None) or "").strip() or "2024"
    p_text = (getattr(release, "copyright_recording_text", None) or "").strip() or label_name

    for idx, track in enumerate(tracks):
        isrc = (track.isrc or "").strip().upper()
        if not isrc:
            isrc = f"TMP{release.id:06d}{idx:02d}"
        res_ref = f"A_{isrc}"
        lang_track = language_to_iso(getattr(track, "language", None) or "")
        display_artist_track = _get_display_artist_names(track_artist_rels.get(track.id, []))
        if not display_artist_track:
            display_artist_track = _get_display_artist_names(release_artists)

        sr = ET.SubElement(resource_list, f"{{{ERN_NAMESPACE}}}SoundRecording")
        _el(sr, "ResourceReference", res_ref)
        _el(sr, "Type", "MusicalWorkSoundRecording")

        edition = ET.SubElement(sr, f"{{{ERN_NAMESPACE}}}SoundRecordingEdition")
        rid = ET.SubElement(edition, f"{{{ERN_NAMESPACE}}}ResourceId")
        _el(rid, "ISRC", isrc)
        pline = ET.SubElement(edition, f"{{{ERN_NAMESPACE}}}PLine")
        _el(pline, "Year", p_year)
        _el_cdata(pline, "PLineText", p_text)
        tech = ET.SubElement(edition, f"{{{ERN_NAMESPACE}}}TechnicalDetails")
        _el(tech, "TechnicalResourceDetailsReference", f"T_{isrc}")
        delivery = ET.SubElement(tech, f"{{{ERN_NAMESPACE}}}DeliveryFile")
        _el(delivery, "Type", "AudioFile")
        f_el = ET.SubElement(delivery, f"{{{ERN_NAMESPACE}}}File")
        uri_audio = f"resources/1_{idx + 1}.flac"
        _el(f_el, "URI", uri_audio)
        if (store or "").strip().lower() == "tiktok" and resource_md5_map and uri_audio in resource_md5_map:
            hash_el = ET.SubElement(f_el, f"{{{ERN_NAMESPACE}}}HashSum")
            _el(hash_el, "HashSumValue", (resource_md5_map.get(uri_audio) or "").strip().lower())
            _el(hash_el, "Algorithm", "MD5")

        _el_cdata(sr, "DisplayTitleText", (track.title or "").strip())
        disp_title = ET.SubElement(sr, f"{{{ERN_NAMESPACE}}}DisplayTitle", ApplicableTerritoryCode=DEFAULT_TERRITORY, IsDefault="true")
        _el_cdata(disp_title, "TitleText", (track.title or "").strip())
        add_title = ET.SubElement(sr, f"{{{ERN_NAMESPACE}}}AdditionalTitle", ApplicableTerritoryCode=DEFAULT_TERRITORY, IsDefault="true", TitleType="FormalTitle")
        _el_cdata(add_title, "TitleText", (track.title or "").strip())

        disp_artist_name = ET.SubElement(
            sr, f"{{{ERN_NAMESPACE}}}DisplayArtistName",
            ApplicableTerritoryCode=DEFAULT_TERRITORY,
            LanguageAndScriptCode=lang_track,
            IsDefault="true",
        )
        disp_artist_name.text = (display_artist_track or "Unknown").strip()

        seq_disp = 0
        for ra in (track_artist_rels.get(track.id, []) or release_artists):
            ddex_role = _role_to_ddex_display_artist_role(ra.role)
            if ddex_role and ra.artist_id:
                ref = artist_refs.get(ra.artist_id)
                if ref:
                    seq_disp += 1
                    disp_artist = ET.SubElement(sr, f"{{{ERN_NAMESPACE}}}DisplayArtist", **{"SequenceNumber": str(seq_disp)})
                    _el(disp_artist, "ArtistPartyReference", ref)
                    _el(disp_artist, "DisplayArtistRole", ddex_role)
        seq_contrib = 0
        for ra in (track_artist_rels.get(track.id, []) or release_artists):
            contrib_role = _role_to_ddex_contributor_role(ra.role)
            if contrib_role and ra.artist_id:
                ref = artist_refs.get(ra.artist_id)
                if ref:
                    seq_contrib += 1
                    contrib = ET.SubElement(sr, f"{{{ERN_NAMESPACE}}}Contributor", **{"SequenceNumber": str(seq_contrib)})
                    _el(contrib, "ContributorPartyReference", ref)
                    _el(contrib, "Role", contrib_role)

        # Explicit ownership: we own 100% in Worldwide (fixes YouTube/Content ID "ownership not defined" errors)
        rights = ET.SubElement(
            sr, f"{{{ERN_NAMESPACE}}}ResourceRightsController",
            ApplicableTerritoryCode=DEFAULT_TERRITORY,
        )
        _el(rights, "RightsControllerPartyReference", vendor_ref)
        _el(rights, "RightsControlType", "RightsController")
        _el(rights, "RightSharePercentage", "100")
        # Meta sample: DelegatedUsageRights (UserMakeAvailableLabelProvided) for Facebook/Instagram Music
        if (store or "").strip().lower() == "meta":
            delegated = ET.SubElement(rights, f"{{{ERN_NAMESPACE}}}DelegatedUsageRights")
            _el(delegated, "UseType", USE_USER_MAKE_AVAILABLE_LABEL_PROVIDED)
            _el(delegated, "TerritoryOfRightsDelegation", DEFAULT_TERRITORY)

        dur = _get_track_duration(track, idx, audio_paths_by_index)
        _el(sr, "Duration", dur)
        _el(sr, "ParentalWarningType", _parental_warning(track.explicit_lyrics))
        _el(sr, "LanguageOfPerformance", lang_track)

    # Cover image
    upc = (release.upc or "").strip() or str(release.id)
    cover_ref = f"A_COVER_{upc}"
    img = ET.SubElement(resource_list, f"{{{ERN_NAMESPACE}}}Image")
    _el(img, "ResourceReference", cover_ref)
    _el(img, "Type", "FrontCoverImage")
    img_rid = ET.SubElement(img, f"{{{ERN_NAMESPACE}}}ResourceId")
    _el(img_rid, "ProprietaryId", f"COVER_{upc}", **{"Namespace": COIN_DIGITAL_PARTY_ID})
    img_tech = ET.SubElement(img, f"{{{ERN_NAMESPACE}}}TechnicalDetails")
    _el(img_tech, "TechnicalResourceDetailsReference", f"T_COVER_{upc}")
    _el(img_tech, "ImageCodecType", "JPEG")
    _el(img_tech, "ImageHeight", "3000")
    _el(img_tech, "ImageWidth", "3000")
    img_file = ET.SubElement(img_tech, f"{{{ERN_NAMESPACE}}}File")
    uri_cover = "resources/coverart.jpg"
    _el(img_file, "URI", uri_cover)
    if (store or "").strip().lower() == "tiktok" and resource_md5_map and uri_cover in resource_md5_map:
        hash_el = ET.SubElement(img_file, f"{{{ERN_NAMESPACE}}}HashSum")
        _el(hash_el, "HashSumValue", (resource_md5_map.get(uri_cover) or "").strip().lower())
        _el(hash_el, "Algorithm", "MD5")

    # ----- ReleaseList -----
    release_list = ET.SubElement(root, f"{{{ERN_NAMESPACE}}}ReleaseList")
    release_ref = f"R_{upc}"
    display_artist_release = _get_display_artist_names(release_artists) or "Unknown"
    genre_text = (getattr(release, "primary_genre", None) or "").strip() or "Other"
    rel_date = release.digital_release_date or release.original_release_date
    rel_date_str = rel_date.strftime("%Y-%m-%d") if rel_date else "2024-01-01"
    orig_date = getattr(release, "original_release_date", None) or rel_date
    orig_date_str = orig_date.strftime("%Y-%m-%d") if orig_date else rel_date_str

    total_seconds = 0
    for idx, track in enumerate(tracks):
        path_or_url = (audio_paths_by_index and audio_paths_by_index.get(idx)) or getattr(track, "audio_track_url", None)
        secs = duration_seconds(path_or_url) if path_or_url else None
        if secs is not None:
            total_seconds += secs
    release_duration = duration_to_ddex(total_seconds if total_seconds else None)

    rel = ET.SubElement(release_list, f"{{{ERN_NAMESPACE}}}Release")
    _el(rel, "ReleaseReference", release_ref)
    _el(rel, "ReleaseType", _release_type_ddex(release.album_format))
    rel_id = ET.SubElement(rel, f"{{{ERN_NAMESPACE}}}ReleaseId")
    _el(rel_id, "ICPN", upc)
    _el(rel_id, "ProprietaryId", upc, Namespace=COIN_DIGITAL_PARTY_ID)
    _el_cdata(rel, "DisplayTitleText", (release.title or "").strip())
    disp_title = ET.SubElement(rel, f"{{{ERN_NAMESPACE}}}DisplayTitle", ApplicableTerritoryCode=DEFAULT_TERRITORY, IsDefault="true")
    _el_cdata(disp_title, "TitleText", (release.title or "").strip())
    add_title = ET.SubElement(rel, f"{{{ERN_NAMESPACE}}}AdditionalTitle", ApplicableTerritoryCode=DEFAULT_TERRITORY, IsDefault="true", TitleType="FormalTitle")
    _el_cdata(add_title, "TitleText", (release.title or "").strip())
    disp_artist_name = ET.SubElement(
        rel, f"{{{ERN_NAMESPACE}}}DisplayArtistName",
        ApplicableTerritoryCode=DEFAULT_TERRITORY,
        LanguageAndScriptCode=lang_iso_release,
        IsDefault="true",
    )
    disp_artist_name.text = display_artist_release.strip()
    seq = 0
    for ra in release_artists:
        ddex_role = _role_to_ddex_display_artist_role(ra.role)
        if ddex_role and ra.artist_id:
            ref = artist_refs.get(ra.artist_id)
            if ref:
                seq += 1
                disp_artist = ET.SubElement(rel, f"{{{ERN_NAMESPACE}}}DisplayArtist", **{"SequenceNumber": str(seq)})
                _el(disp_artist, "ArtistPartyReference", ref)
                _el(disp_artist, "DisplayArtistRole", ddex_role)
    _el(rel, "ReleaseLabelReference", label_ref, ApplicableTerritoryCode=DEFAULT_TERRITORY)
    pline = ET.SubElement(rel, f"{{{ERN_NAMESPACE}}}PLine")
    _el(pline, "Year", p_year)
    _el_cdata(pline, "PLineText", p_text)
    cline = ET.SubElement(rel, f"{{{ERN_NAMESPACE}}}CLine")
    _el(cline, "Year", p_year)
    _el_cdata(cline, "CLineText", p_text)
    _el(rel, "Duration", release_duration)
    genre_el = ET.SubElement(rel, f"{{{ERN_NAMESPACE}}}Genre")
    _el_cdata(genre_el, "GenreText", genre_text)
    _el(rel, "ReleaseDate", rel_date_str)
    _el(rel, "OriginalReleaseDate", orig_date_str)
    _el(rel, "ParentalWarningType", _parental_warning(
        next((t.explicit_lyrics for t in tracks), "not_explicit")
    ))
    _el(rel, "IsMultiArtistCompilation", "false")

    is_simple_single = _release_profile_version(release.album_format) == "SimpleAudioSingle"
    rg = ET.SubElement(rel, f"{{{ERN_NAMESPACE}}}ResourceGroup")
    _el(rg, "SequenceNumber", "1")
    for idx, track in enumerate(tracks):
        isrc = (track.isrc or "").strip().upper() or f"TMP{release.id:06d}{idx:02d}"
        item = ET.SubElement(rg, f"{{{ERN_NAMESPACE}}}ResourceGroupContentItem")
        _el(item, "SequenceNumber", str(idx + 1))
        _el(item, "ReleaseResourceReference", f"A_{isrc}")
        if is_simple_single:
            _el(item, "LinkedReleaseResourceReference", cover_ref)
    if not is_simple_single:
        _el(rg, "LinkedReleaseResourceReference", cover_ref)
    _el(rel, "IsSoundtrack", "false")

    if not is_simple_single:
        for idx, track in enumerate(tracks):
            isrc = (track.isrc or "").strip().upper() or f"TMP{release.id:06d}{idx:02d}"
            tr = ET.SubElement(release_list, f"{{{ERN_NAMESPACE}}}TrackRelease")
            _el(tr, "ReleaseReference", f"R_{isrc}")
            tr_id = ET.SubElement(tr, f"{{{ERN_NAMESPACE}}}ReleaseId")
            _el(tr_id, "ProprietaryId", f"{upc}_{isrc}_R_{isrc}", **{"Namespace": COIN_DIGITAL_PARTY_ID})
            _el(tr, "ReleaseResourceReference", f"A_{isrc}")
            _el(tr, "ReleaseLabelReference", label_ref, ApplicableTerritoryCode=DEFAULT_TERRITORY)
            g_el = ET.SubElement(tr, f"{{{ERN_NAMESPACE}}}Genre")
            _el_cdata(g_el, "GenreText", (getattr(track, "primary_genre", None) or "").strip() or genre_text)
            if (store or "").strip().lower() == "meta":
                _el(tr, "ReleaseVisibilityReference", "V1")

    # ----- DealList -----
    deal_list = ET.SubElement(root, f"{{{ERN_NAMESPACE}}}DealList")
    rd_tracks = ET.SubElement(deal_list, f"{{{ERN_NAMESPACE}}}ReleaseDeal")
    for idx, track in enumerate(tracks):
        isrc = (track.isrc or "").strip().upper() or f"TMP{release.id:06d}{idx:02d}"
        _el(rd_tracks, "DealReleaseReference", f"R_{isrc}")
    _add_deal_terms_for_store(
        rd_tracks, rel_date_str, store, vendor_ref,
        takedown_immediate=takedown_immediate, takedown_end_date=takedown_end_date,
    )
    rd_release = ET.SubElement(deal_list, f"{{{ERN_NAMESPACE}}}ReleaseDeal")
    _el(rd_release, "DealReleaseReference", release_ref)
    _add_deal_terms_for_store(
        rd_release, rel_date_str, store, vendor_ref,
        takedown_immediate=takedown_immediate, takedown_end_date=takedown_end_date,
    )
    # Meta sample: TrackReleaseVisibility (VisibilityReference V1, preview start datetimes)
    if (store or "").strip().lower() == "meta":
        visibility = ET.SubElement(deal_list, f"{{{ERN_NAMESPACE}}}TrackReleaseVisibility")
        _el(visibility, "VisibilityReference", "V1")
        _el(visibility, "TrackListingPreviewStartDateTime", f"{rel_date_str}T00:00:00")
        _el(visibility, "ClipPreviewStartDateTime", f"{rel_date_str}T00:00:00")

    return _serialize(root)


def _add_deal_terms_for_store(
    release_deal: ET.Element,
    start_date: str,
    store: str,
    vendor_ref: str,
    takedown_immediate: Optional[bool] = None,
    takedown_end_date: Optional[str] = None,
) -> None:
    """Add deal terms from registry deal_profile: streaming, ugc, meta, download; or Gaana takedown."""
    store = (store or "spotify").strip().lower()
    if store == "gaana" and (takedown_immediate or takedown_end_date):
        _add_deal_terms_gaana_takedown(
            release_deal, start_date,
            takedown_immediate=bool(takedown_immediate),
            end_date=takedown_end_date,
        )
        return
    if store == "audiomack":
        _add_deal_terms_audiomack(release_deal, start_date, end_date=takedown_end_date)
        return
    if store == "meta":
        _add_deal_terms_meta(release_deal, start_date)
        return
    profile = get_deal_profile(store)
    if profile == "ugc":
        _add_deal_terms_tiktok(release_deal, start_date, vendor_ref)
        return
    if profile == "download":
        _add_deal_terms_download(release_deal, start_date)
        return
    # streaming or any other / missing: use Spotify-style
    _add_deal_terms_spotify(release_deal, start_date)


def _add_deal_terms_spotify(release_deal: ET.Element, start_date: str) -> None:
    start_dt = f"{start_date}T00:00:00"
    for model_type in (DEAL_SUBSCRIPTION, DEAL_ADVERTISEMENT):
        deal = ET.SubElement(release_deal, f"{{{ERN_NAMESPACE}}}Deal")
        terms = ET.SubElement(deal, f"{{{ERN_NAMESPACE}}}DealTerms")
        _el(terms, "TerritoryCode", DEFAULT_TERRITORY)
        validity = ET.SubElement(terms, f"{{{ERN_NAMESPACE}}}ValidityPeriod")
        _el(validity, "StartDateTime", start_dt)
        _el(terms, "CommercialModelType", model_type)
        if model_type == DEAL_SUBSCRIPTION:
            _el(terms, "UseType", USE_CONDITIONAL_DOWNLOAD)
        _el(terms, "UseType", USE_ON_DEMAND_STREAM)
        _el(terms, "UseType", USE_NON_INTERACTIVE_STREAM)


def _add_deal_terms_gaana_takedown(
    release_deal: ET.Element,
    start_date: str,
    takedown_immediate: bool = True,
    end_date: Optional[str] = None,
) -> None:
    """Gaana takedown: NewReleaseMessage with either TakeDown true or ValidityPeriod EndDate (ERN 4.3)."""
    for model_type in (DEAL_SUBSCRIPTION, DEAL_ADVERTISEMENT):
        deal = ET.SubElement(release_deal, f"{{{ERN_NAMESPACE}}}Deal")
        terms = ET.SubElement(deal, f"{{{ERN_NAMESPACE}}}DealTerms")
        _el(terms, "TerritoryCode", DEFAULT_TERRITORY)
        if takedown_immediate:
            _el(terms, "TakeDown", "true")
        validity = ET.SubElement(terms, f"{{{ERN_NAMESPACE}}}ValidityPeriod")
        _el(validity, "StartDate", start_date)
        if end_date and not takedown_immediate:
            _el(validity, "EndDate", end_date)
        _el(terms, "CommercialModelType", model_type)
        _el(terms, "UseType", USE_ON_DEMAND_STREAM)
        _el(terms, "UseType", USE_NON_INTERACTIVE_STREAM)
        _el(terms, "UseType", USE_CONDITIONAL_DOWNLOAD)


def _add_deal_terms_audiomack(
    release_deal: ET.Element, start_date: str, end_date: Optional[str] = None
) -> None:
    """Audiomack (ERN 4.3): AdvertisementSupportedModel + SubscriptionModel, UseType OnDemandStream + NonInteractiveStream only.
    When end_date is set (YYYY-MM-DD), adds ValidityPeriod EndDate for takedown (per Audiomack sample)."""
    start_dt = f"{start_date}T00:00:00"
    for model_type in (DEAL_SUBSCRIPTION, DEAL_ADVERTISEMENT):
        deal = ET.SubElement(release_deal, f"{{{ERN_NAMESPACE}}}Deal")
        terms = ET.SubElement(deal, f"{{{ERN_NAMESPACE}}}DealTerms")
        _el(terms, "TerritoryCode", DEFAULT_TERRITORY)
        validity = ET.SubElement(terms, f"{{{ERN_NAMESPACE}}}ValidityPeriod")
        _el(validity, "StartDateTime", start_dt)
        if end_date and str(end_date).strip():
            _el(validity, "EndDate", str(end_date).strip()[:10])
        _el(terms, "CommercialModelType", model_type)
        _el(terms, "UseType", USE_ON_DEMAND_STREAM)
        _el(terms, "UseType", USE_NON_INTERACTIVE_STREAM)


def _add_deal_terms_meta(release_deal: ET.Element, start_date: str) -> None:
    """Meta (Facebook/Instagram Music) ERN 4.3 sample: RightsClaimModel, UserMakeAvailableUserProvided + UserMakeAvailableLabelProvided, RightsClaimPolicy Monetize."""
    start_dt = f"{start_date}T00:00:00"
    deal = ET.SubElement(release_deal, f"{{{ERN_NAMESPACE}}}Deal")
    terms = ET.SubElement(deal, f"{{{ERN_NAMESPACE}}}DealTerms")
    _el(terms, "TerritoryCode", DEFAULT_TERRITORY)
    validity = ET.SubElement(terms, f"{{{ERN_NAMESPACE}}}ValidityPeriod")
    _el(validity, "StartDateTime", start_dt)
    _el(terms, "CommercialModelType", DEAL_RIGHTS_CLAIM_MODEL)
    _el(terms, "UseType", USE_USER_MAKE_AVAILABLE_USER_PROVIDED)
    _el(terms, "UseType", USE_USER_MAKE_AVAILABLE_LABEL_PROVIDED)
    policy = ET.SubElement(terms, f"{{{ERN_NAMESPACE}}}RightsClaimPolicy")
    _el(policy, "RightsClaimPolicyType", RIGHTS_CLAIM_POLICY_MONETIZE)


def _add_deal_terms_tiktok(
    release_deal: ET.Element,
    start_date: str,
    vendor_ref: str,
) -> None:
    """TikTok UGC / Library feed: RightsClaimModel, UserMakeAvailableUserProvided, RightsController (100%)."""
    start_dt = f"{start_date}T00:00:00"
    deal = ET.SubElement(release_deal, f"{{{ERN_NAMESPACE}}}Deal")
    terms = ET.SubElement(deal, f"{{{ERN_NAMESPACE}}}DealTerms")
    _el(terms, "TerritoryCode", DEFAULT_TERRITORY)
    validity = ET.SubElement(terms, f"{{{ERN_NAMESPACE}}}ValidityPeriod")
    _el(validity, "StartDateTime", start_dt)
    _el(terms, "CommercialModelType", DEAL_RIGHTS_CLAIM_MODEL)
    _el(terms, "UseType", USE_USER_MAKE_AVAILABLE_USER_PROVIDED)
    _el(terms, "RightsClaimPolicyType", RIGHTS_CLAIM_POLICY_MONETIZE)
    rights_ctrl = ET.SubElement(deal, f"{{{ERN_NAMESPACE}}}RightsController")
    _el(rights_ctrl, "RightsControllerPartyReference", vendor_ref)
    _el(rights_ctrl, "RightsControllerRole", RIGHTS_CONTROLLER_ROLE)
    _el(rights_ctrl, "RightSharePercentage", "100")


def _add_deal_terms_download(release_deal: ET.Element, start_date: str) -> None:
    """Download profile: PayAsYouGoModel + PermanentDownload (ERN 4.3)."""
    start_dt = f"{start_date}T00:00:00"
    deal = ET.SubElement(release_deal, f"{{{ERN_NAMESPACE}}}Deal")
    terms = ET.SubElement(deal, f"{{{ERN_NAMESPACE}}}DealTerms")
    _el(terms, "TerritoryCode", DEFAULT_TERRITORY)
    validity = ET.SubElement(terms, f"{{{ERN_NAMESPACE}}}ValidityPeriod")
    _el(validity, "StartDateTime", start_dt)
    _el(terms, "CommercialModelType", DEAL_PAY_AS_YOU_GO)
    _el(terms, "UseType", USE_PERMANENT_DOWNLOAD)


def build_takedown_message(
    release: Release,
    store: str = "spotify",
    takedown_reason: Optional[str] = None,
    message_thread_id: Optional[str] = None,
    release_references: Optional[List[str]] = None,
) -> str:
    """
    Build ERN 4.3 PurgeReleaseMessage (takedown) for the given Release.
    Applies to Single, EP, or Album: one release reference R_{upc} is used.
    store: DSP code from registry.
    takedown_reason: optional (e.g. RightsIssue, ArtistRequest, ContractExpiry, Other).
    release_references: optional list of release refs (e.g. ["R_<upc>"]); default [f"R_{upc}"].
    Returns XML string (utf-8).
    """
    root = ET.Element(
        f"{{{ERN_NAMESPACE}}}PurgeReleaseMessage",
        attrib={"LanguageAndScriptCode": LANGUAGE_SCRIPT_CODE},
    )
    root.set(f"{{{NS_XSI}}}schemaLocation", ERN_SCHEMA_LOCATION)

    thread_id = message_thread_id or uuid.uuid4().hex
    message_id = uuid.uuid4().hex
    msg_created = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00")

    header = ET.SubElement(root, f"{{{ERN_NAMESPACE}}}MessageHeader")
    _el(header, "MessageThreadId", thread_id)
    _el(header, "MessageId", message_id)
    sender = ET.SubElement(header, f"{{{ERN_NAMESPACE}}}MessageSender")
    _el(sender, "PartyId", COIN_DIGITAL_PARTY_ID)
    name_el = ET.SubElement(sender, f"{{{ERN_NAMESPACE}}}PartyName")
    _el(name_el, "FullName", COIN_DIGITAL_PARTY_NAME)
    rec_party_id, rec_party_name = _recipient_for_store(store)
    recipient = ET.SubElement(header, f"{{{ERN_NAMESPACE}}}MessageRecipient")
    _el(recipient, "PartyId", rec_party_id)
    rec_name = ET.SubElement(recipient, f"{{{ERN_NAMESPACE}}}PartyName")
    _el(rec_name, "FullName", rec_party_name)
    _el(header, "MessageCreatedDateTime", msg_created)
    _el(header, "MessageControlType", "LiveMessage")

    upc = (release.upc or "").strip() or str(release.id)
    refs = release_references if release_references is not None else [f"R_{upc}"]
    ref_list = ET.SubElement(root, f"{{{ERN_NAMESPACE}}}ReleaseReferenceList")
    for ref in refs:
        _el(ref_list, "ReleaseReference", ref)

    if takedown_reason and takedown_reason.strip():
        _el(root, "TakedownReason", takedown_reason.strip())

    return _serialize(root)


def _serialize(root: ET.Element) -> str:
    """Pretty-print XML with ern prefix."""
    # ERN 4.3 schemas commonly use a namespaced root and unqualified local
    # elements. Build tags are created namespaced for convenience, then we
    # strip namespaces from descendants before serialization.
    for elem in root.iter():
        if elem is root:
            continue
        if isinstance(elem.tag, str) and elem.tag.startswith("{"):
            elem.tag = elem.tag.split("}", 1)[1]

    ET.register_namespace("ern", ERN_NAMESPACE)
    ET.register_namespace("xsi", NS_XSI)
    rough = ET.tostring(root, encoding="unicode")
    reparsed = minidom.parseString(rough)
    return reparsed.toprettyxml(indent="  ", encoding="utf-8").decode("utf-8")
