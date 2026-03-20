# Apple Music Feed Improvements (Style Guide & Bridge Onboarding)

This checklist is based on the [Apple Music Style Guide](https://help.apple.com/itc/musicstyleguide/en.lproj/static.html) and the **Apple Bridge – Member Onboarding Guide**. It helps ensure our Apple Music delivery feed (Merlin Bridge, iTunes Importer music5.3) meets Apple’s requirements and reduces tickets / failed deliveries.

---

## References

- **Apple Music Style Guide:** https://help.apple.com/itc/musicstyleguide/en.lproj/static.html  
- **Merlin Bridge Member Onboarding Guide:** (Word doc – delivery paths, package format, testing checklist)  
- **iTunes Package Music Specification:** (Apple’s technical spec for XML/fields)  
- **MERLIN_BRIDGE_APPLE_MUSIC.md:** Our Bridge SFTP setup and delivery path (`apple/regular`, etc.)

---

## Implemented in Code

| Requirement | Source | Status |
|-------------|--------|--------|
| **Featuring/With not Primary** | Style Guide 2.13 | ✅ Artists with role Featuring or With are sent with `primary="false"` and role `Featuring` or `With`. |
| **No emoji in titles or artist names** | Style Guide 1.10 | ✅ Emoji stripped from album title, track title, and artist name in XML. |
| **Explicit / Clean flagging** | Style Guide 6.1, 6.2 | ✅ `explicit_content`: `explicit`, `clean`, or `none` from track’s explicit_lyrics. |
| **Metadata XML named `metadata.xml`** | Bridge Onboarding | ✅ Inside package dir `{upc}/` as `metadata.xml`. |
| **Package file extension `.itmsp`** | Bridge / Apple | ✅ We upload only `{upc}.itmsp` (no .zip; Bridge rejects wrong extension). |
| **Delivery path** | Bridge Onboarding | ✅ `MERLIN_BRIDGE_SFTP_REMOTE_PATH=apple/regular` (or priority/backlog). |
| **Package = directory with metadata at top level** | Apple Music Spec 5.3 | ✅ Zip contains `{upc}/metadata.xml`, `{upc}/{upc}.jpg`, audio. |

---

## Data / Content Guidelines (for your metadata)

These are not auto-enforced in code; ensure your **source data** (release/track/artist in DB) follows them.

### Titles (Style Guide 3)

- **No extra words in title:** Do not include Exclusive, Limited Edition, Album Version, Original Mix, Digital Only, Clean Version, Explicit Version, Dolby Atmos, lossless, etc.
- **Singles:** 1–3 tracks, each &lt;10 min → album title should end with **- Single** (we do not auto-append; add in title if needed).
- **EPs:** 4–6 tracks, total ≤30 min → album title should end with **- EP**.
- **Version info:** Use parentheses/brackets for (Live), (Remix), [Radio Edit], etc.; we pass through.
- **No track numbers in title:** e.g. avoid "12. Song Title".
- **Casing:** English titles in title case; other languages per Style Guide (e.g. sentence case for German, French).

### Artists (Style Guide 2)

- **One artist per field:** Each artist in a separate `<artist>` block; no "Artist A & Artist B" in one name.
- **Compound artists:** Each main artist as separate Primary (e.g. two Primaries for "Artist A & Artist B").
- **Featuring in title:** Use "(feat. Artist B)" or "(with Artist B)" in **track/album title**; keep "feat." and "with" lowercase. We do not auto-add this; ensure titles match.
- **Accuracy:** Full, standard spellings; no role/instrument/date in name (e.g. no "Artist (Guitarist)").

### Genres (Style Guide 4)

- Use **Apple’s genre list** (iTunes Package Music Specification Addendum). Our `GENRE_TO_APPLE_CODE` is a subset; expand as needed for Indian/regional (e.g. Bollywood, Tamil, Hindi Movie, Devotional, etc.).

### Original Release Date (Style Guide 5)

- **Accuracy:** Use the date of first release (digital or physical). For remastered, use **original** release date.
- Post-2000: use full date (YYYY-MM-DD). We use `original_release_date` / `digital_release_date`.

### Parental Advisory (Style Guide 6)

- **Explicit:** Flag as explicit when content is explicit; do not put "(Explicit)" in title.
- **Clean:** Flag as clean only when there is a **corresponding explicit version** of the same track. We support `explicit_lyrics` = clean/edited → `explicit_content="clean"`.

### Artwork (Style Guide 7 & Onboarding)

- **Format:** .jpg or .png, square, **minimum 1400×1400**, preferred **3000×3000**, RGB (no CMYK).
- **Content:** No URLs, logos, QR codes, or competitor references. We do not validate dimensions in code; ensure assets meet this before upload.

### Audio (Onboarding)

- **Format:** .wav or .flac, **two-channel stereo**.  
- **Sample rate:** 16‑bit 44.1 kHz, or 24‑bit 44.1/48/88.2/96/176.4/192 kHz.  
- We pass through your audio; ensure files meet spec.

### XML (Onboarding)

- **No null/empty tags:** Required elements should have values. We use defaults (e.g. "Unknown", "Track") where needed; avoid leaving required fields empty in DB.
- **DPID in vendor_id:** We use `{DPID}_{upc}` and `{DPID}_{upc}_{isrc}` for album and track.

---

## Optional / Future Improvements

| Item | Description |
|------|-------------|
| **Auto Single/EP suffix** | Derive track count and duration; append " - Single" or " - EP" to album title when applicable. |
| **Title case for English** | Auto-apply title case to English titles per Style Guide 3.21. |
| **Artwork dimensions check** | Validate min 1400×1400 (and optionally 3000×3000) before upload; warn or reject. |
| **Genre code list** | Expand `GENRE_TO_APPLE_CODE` to full Apple list + Indian genres (Bollywood, Tamil, etc.). |
| **Lyrics / Digital Booklet** | Add if you deliver lyrics or booklets per Apple spec. |
| **Motion Art / Dolby Atmos** | Per Onboarding doc; add if you deliver these asset types. |

---

## Bridge Testing Checklist (from Onboarding)

Before going live, complete the **Apple Music Checklist** in the Bridge dashboard (test mode):

- [ ] At least one **full-length** record (6+ tracks, &gt;30 min).
- [ ] At least one **EP** (3–6 tracks, &lt;30 min).
- [ ] An **update** to one of the above.
- [ ] A **takedown** for one of the above.
- [ ] Examples that include: **Compound artists**, **Featured artists**, **Preorder**, **Instant Grat** track, **Streaming only**, **Retail only** (as applicable).

Use **Checklist** tab in Bridge to mark items green before switching to live.

---

## Summary

- **Code:** Featuring/With → not Primary and correct role; emoji stripped; Explicit/Clean supported; metadata.xml and path per Bridge.
- **Data:** Titles, artists, genres, dates, and assets should follow the Style Guide and Onboarding doc; we do not auto-fix all of these.
- **Testing:** Use Bridge test mode and the Apple Music Checklist before going live.
