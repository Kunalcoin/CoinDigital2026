"""
Build DDEX ERN 4.3 PurgeReleaseMessage for Audiomack (takedown).
Use when Audiomack accepts PurgeReleaseMessage for 4.3; otherwise use
NewReleaseMessage with UpdateIndicator and ValidityPeriod EndDate (see DDEX_AUDIOMACK_4.3.md).
"""
import uuid
from datetime import datetime, timezone
from typing import List, Optional

import xml.etree.ElementTree as ET
from xml.dom import minidom

from releases.ddex_config import (
    COIN_DIGITAL_PARTY_ID,
    COIN_DIGITAL_PARTY_NAME,
    AUDIOMACK_PARTY_ID,
    AUDIOMACK_PARTY_NAME,
    ERN_NAMESPACE,
    ERN_SCHEMA_LOCATION,
)
from releases.models import Release

NS_XSI = "http://www.w3.org/2001/XMLSchema-instance"


def _el(parent: ET.Element, tag: str, text: Optional[str] = None, **attrib) -> ET.Element:
    child = ET.SubElement(parent, f"{{{ERN_NAMESPACE}}}{tag}", **attrib)
    if text is not None:
        child.text = text
    return child


def build_audiomack_takedown_message(
    release: Release,
    message_thread_id: Optional[str] = None,
    release_references: Optional[List[str]] = None,
) -> str:
    """
    Build ERN 4.3 PurgeReleaseMessage XML for takedown on Audiomack.
    release_references: optional list of release refs (e.g. ["R_8905285127614"]); if None, uses main release ref R_{upc}.
    Returns XML string (utf-8).
    """
    root = ET.Element(
        f"{{{ERN_NAMESPACE}}}PurgeReleaseMessage",
        attrib={"LanguageAndScriptCode": "en"},
    )
    root.set(f"{{{NS_XSI}}}schemaLocation", ERN_SCHEMA_LOCATION)

    # MessageHeader (same pattern as NewReleaseMessage)
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
    recipient = ET.SubElement(header, f"{{{ERN_NAMESPACE}}}MessageRecipient")
    _el(recipient, "PartyId", AUDIOMACK_PARTY_ID)
    rec_name = ET.SubElement(recipient, f"{{{ERN_NAMESPACE}}}PartyName")
    _el(rec_name, "FullName", AUDIOMACK_PARTY_NAME)
    _el(header, "MessageCreatedDateTime", msg_created)
    _el(header, "MessageControlType", "LiveMessage")

    # ReleaseReferenceList
    upc = (release.upc or "").strip() or str(release.id)
    refs = release_references if release_references is not None else [f"R_{upc}"]
    ref_list = ET.SubElement(root, f"{{{ERN_NAMESPACE}}}ReleaseReferenceList")
    for ref in refs:
        _el(ref_list, "ReleaseReference", ref)

    return _serialize(root)


def _serialize(root: ET.Element) -> str:
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
