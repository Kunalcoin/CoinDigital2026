# DDEX Feed Requirements (Insert, Update, Takedown)

**Version:** We always use **DDEX ERN 4.3** (latest) for deployment for all stores (Spotify, TikTok, etc.). TikTok receives 4.3 feeds; no 3.8.2.

**Message types:** We support **INSERT**, **UPDATE**, and **TAKEDOWN** for **Singles**, **EP**, and **Album**:

| Message type | ERN 4.3 format | Single / EP / Album |
|--------------|----------------|----------------------|
| **INSERT** | NewReleaseMessage (MessageControlType LiveMessage or TestMessage) | Yes — release type from `album_format` (Single, EP, Album) |
| **UPDATE** | NewReleaseMessage (MessageControlType UpdateMessage, LinkedMessageId = original Insert MessageId) | Yes — same release content as Insert, with link to original |
| **TAKEDOWN** | PurgeReleaseMessage with ReleaseReferenceList (e.g. R_{UPC}) | Yes — one release reference per release |

**Commands:** `python manage.py build_ddex <release_id> [--action insert|update|takedown] [--store <dsp_code>]`. For update use `--original-message-id`. For takedown use optional `--takedown-reason`.

Based on DDEX ERN 4.3 samples, here's what we need to build DDEX feeds for **Singles, EP, and Album** releases for **Spotify** and **TikTok**.

---

## 1. **Message Header** (Required for all operations)

### Sender Information (Your Company)
- **PartyId** - Your DDEX Party ID (e.g. "PADPIDA2013042401U" format)
- **PartyName** - Your company name (e.g. "Coin Digital")
- **MessageId** - Unique message ID (we can generate: timestamp + UUID)
- **MessageThreadId** - Thread ID for related messages (optional, can use MessageId)
- **MessageCreatedDateTime** - ISO 8601 timestamp (e.g. "2026-02-05T14:57:25+01:00")

### Recipient Information
- **Spotify:** PartyId `PADPIDA2011072101T`, PartyName "Spotify"
- **TikTok:** PartyId `PADPIDA2018082301A`, PartyName "TikTok / Bytedance" (ERN 4.3; we always use 4.3 for deployment)
- **Audiomack:** PartyId from env `DDEX_PARTY_ID_AUDIOMACK` (default placeholder until provided by Audiomack), PartyName "Audiomack"

**Questions for you:**
1. Do you have a **DDEX Party ID** assigned to Coin Digital? (If not, you may need to register/get one)
2. What is **Spotify's DDEX Party ID**? (We'll need this to send them feeds)

---

## 2. **Party List** (Artists, Label, Contributors)

### Release-Level Artists
- **Artist Name** (Full Name) - from `RelatedArtists` where `relation_key="release"` and `role="Primary Artist"`
- **Artist First Name / Last Name** - from `Artist.first_name`, `Artist.last_name` (if available)
- **Artist Party Reference** - Unique ID for each artist (we can generate: "P{artist_id}" or use artist name)
- **Display Artist Role** - "MainArtist" for primary artist

### Track-Level Artists (per track)
- **Artist Name** - from `RelatedArtists` where `relation_key="track"` and `role="Primary Artist"` or `role="Artist"`
- **Artist Party Reference** - Same as release-level
- **Display Artist Role** - "MainArtist"

### Contributors (Composers, Lyricists, Producers, etc.)
- **Contributor Name** - from `RelatedArtists` with roles like "Composer", "Lyricist", "Producer", etc.
- **Contributor Party Reference** - Unique ID per contributor
- **Role** - DDEX role code (e.g. "Composer", "Lyricist", "Producer", "Arranger")

### Label
- **Label Name** - from `Release.label.label`
- **Label Party Reference** - Unique ID for label (e.g. "P{label_id}")

**Questions:**
3. Do you have **ISNI** (International Standard Name Identifier) or **IPI** (Interested Party Information) codes for artists? (Optional but recommended)
4. For **contributors** (composers, lyricists), do you store their **first name / last name** separately, or just full name?

---

## 3. **Resource List** (SoundRecordings = Tracks)

### Per Track (SoundRecording)
- **ISRC** - from `Track.isrc` ✅ (we have this)
- **Track Title** - from `Track.title` ✅
- **Remix Version** - from `Track.remix_version` ✅
- **Duration** - Track duration in ISO 8601 format (e.g. "PT3M45S" = 3 minutes 45 seconds)
  - **Question:** Do you store track duration anywhere? If not, we'll need to extract it from the audio file (`Track.audio_track_url`)
- **Display Title** - Track title (can be same as title)
- **Display Artist Name** - Primary artist for this track
- **Language of Performance** - from `Track.language` (need ISO 639-2 code, e.g. "en", "hi", "ja")
  - **Question:** Your `LANGUAGES` list has full names (e.g. "English", "Hindi"). Do you have ISO codes mapping, or should we map them?
- **IsInstrumental** - boolean (true if no vocals)
  - **Question:** Do you have a field for this, or should we infer from lyrics?
- **ParentalWarningType** - from `Track.explicit_lyrics`:
  - "NotExplicit" if `explicit_lyrics="not_explicit"`
  - "Explicit" if `explicit_lyrics="explicit"`
  - "Clean" if `explicit_lyrics="cleaned"`
- **CreationDate** - Track creation/recording date (ISO date, e.g. "2024-01-01")
  - **Question:** Do you store track creation/recording date? If not, we can use release date or leave approximate

### P-Line (Phonogram Copyright)
- **Year** - from `Release.copyright_recording_year` ✅
- **PLineText** - from `Release.copyright_recording_text` ✅
  - Format: "(P) {year} {copyright_recording_text}"

### Technical Details (Audio File)
- **File URI** - URL to audio file (`Track.audio_track_url`) ✅
- **File Format** - Extract from file extension (e.g. "WAV", "MP3", "FLAC")
- **File Size** - Size in bytes (may need to fetch from S3)
- **Bit Depth** - Audio bit depth (may need to extract from audio metadata)
- **Sample Rate** - Audio sample rate (e.g. 44100, 48000) (may need to extract from audio metadata)

**Questions:**
5. Do you store **track duration** anywhere, or should we extract it from the audio file?
6. Do you have **audio metadata** (bit depth, sample rate) stored, or should we extract from files?
7. For **language**, do you have ISO 639-2 codes, or should we map from your language names?

---

## 4. **Release List**

### Release-Level Information
- **Release Type** - Based on `Release.album_format`:
  - "Single" if `album_format="single"`
  - "EP" if `album_format="ep"`
  - "Album" if `album_format="album"`
- **UPC** - from `Release.upc` ✅
- **ICPN** (International Catalog Product Number) - Usually same as UPC
- **Release Title** - from `Release.title` ✅
- **Display Artist Name** - Primary artist for release
- **Label Reference** - Link to label in PartyList
- **Release Date** - from `Release.digital_release_date` ✅ (ISO date format)
- **Original Release Date** - from `Release.original_release_date` ✅ (if different)
- **Genre** - from `Release.primary_genre` ✅
  - **Question:** Your genres are detailed (e.g. "Pop/K-Pop"). Spotify may need simpler genre codes. Do you have a mapping?
- **ParentalWarningType** - Release-level explicit content warning
- **IsMultiArtistCompilation** - boolean (true if multiple primary artists)
- **Duration** - Total release duration (sum of all track durations)

### Track Release (for Singles)
- If `album_format="single"`, create a `TrackRelease` entry linking to the single track
- **Release Reference** - Link to the SoundRecording
- **Release Label Reference** - Link to label

### Resource Group (for Album/EP)
- **Sequence Numbers** - Track order (1, 2, 3, ...)
- **Resource References** - Links to SoundRecordings in ResourceList

### Cover Art (Image Resource)
- **Image Type** - "FrontCoverImage"
- **Image URI** - from `Release.cover_art_url` ✅
- **File Format** - Extract from URL (e.g. "JPEG", "PNG")
- **File Size** - Size in bytes (may need to fetch from S3)

**Questions:**
8. For **genre mapping**, do you have Spotify genre codes, or should we use your genre names as-is?
9. Do you store **cover art dimensions** (width/height) or file size?

---

## 5. **Deal List** (Licensing / Territory / Commercial Terms)

### Territory
- **Territory Code** - from `Release.territories` ✅
  - **Question:** Your `territories` field says "Entire World" - do you need to map this to ISO territory codes (e.g. "Worldwide", "US", "IN")?

### Commercial Model Types
- **SubscriptionModel** - For streaming (Spotify Premium)
- **AdvertisementSupportedModel** - For free tier (Spotify Free)
- **PayAsYouGoModel** - For downloads (if applicable)

### Use Types
- **Stream** - Streaming access
- **PermanentDownload** - Download to own
- **ConditionalDownload** - Download with restrictions

### Validity Period
- **StartDate** - Release date (`Release.digital_release_date`)
- **EndDate** - Optional (if license expires)

### Price Information (if PayAsYouGoModel)
- **Price Code** - Price tier/code
  - **Question:** Do you have price codes/categories for Spotify? Or should we use `Release.price_category`?

**Questions:**
10. What **territory codes** should we use? (Worldwide, specific countries, etc.)
11. What **commercial models** and **use types** does Spotify require for your releases?
12. Do you have **Spotify-specific pricing** information, or should we use your `price_category`?

---

## 6. **Additional Requirements**

### For **Update** Messages
- **Previous MessageId** - Reference to the original Insert message
- **Updated Fields** - Only include fields that changed
- **UpdateReason** - Why the update (e.g. "MetadataCorrection", "PriceChange")

**Question:**
13. How do you want to track which releases have been sent to Spotify (so we can reference the original MessageId for updates)?

### For **Takedown** Messages
- **Release Reference** - Link to the release (UPC)
- **Takedown Reason** - Why takedown (e.g. "RightsIssue", "ArtistRequest")
- **Takedown Date** - When takedown takes effect

**Question:**
14. Do you have a **takedown reason** field, or should we use a default?

---

## 7. **Technical Setup**

### XML Generation
- **XML Namespace** - `http://ddex.net/xml/ern/431`
- **Schema Location** - `http://ddex.net/xml/ern/431/release-notification.xsd`
- **Release Profile** - "Audio" (for audio-only releases)
- **Language and Script Code** - "en" (or appropriate)
- **AVS Version** - "7"

### File Delivery
- **Delivery Method** - How will you send DDEX files to Spotify?
  - FTP/SFTP upload?
  - API endpoint?
  - Email?
- **File Naming Convention** - Format for DDEX XML files (e.g. "DDEX_{UPC}_{timestamp}.xml")

**Questions:**
15. How does **Spotify want to receive** DDEX feeds? (FTP, API, email, etc.)
16. What is their **endpoint/credentials** for receiving feeds?
17. Do they require **file validation** before sending? (XSD schema validation)

---

## 8. **Data Mapping Needed**

### Language Mapping
- Your `LANGUAGES` list → ISO 639-2 codes (e.g. "English" → "en", "Hindi" → "hi")

### Genre Mapping
- Your `GENRES` list → Spotify/DDEX genre codes (if different)

### Artist Role Mapping
- Your `ARTIST_ROLES` → DDEX role codes:
  - "Primary Artist" → "MainArtist"
  - "Composer" → "Composer"
  - "Lyricist" → "Lyricist"
  - "Producer" → "Producer"
  - etc.

### Territory Mapping
- "Entire World" → "Worldwide" (or specific territory codes)

**Question:**
18. Do you have **mapping tables** for these, or should we create them?

---

## Summary Checklist

Please provide:

- [ ] **DDEX Party ID** for Coin Digital (or how to get one)
- [ ] **Spotify's DDEX Party ID** and delivery method (FTP/API/email)
- [ ] **Track duration** - stored or extract from audio?
- [ ] **Audio metadata** (bit depth, sample rate) - stored or extract?
- [ ] **Language ISO codes** - mapping from your language names
- [ ] **Genre mapping** - Spotify codes or use yours as-is?
- [ ] **Territory codes** - Worldwide or specific countries?
- [ ] **Commercial models** Spotify requires (Subscription, Ad-supported, etc.)
- [ ] **Price codes** for Spotify (if applicable)
- [ ] **ISNI/IPI codes** for artists (if available)
- [ ] **Track creation dates** - stored or use release date?
- [ ] **Cover art dimensions/size** - stored or extract?
- [ ] **Takedown reason** field or default value
- [ ] **Message tracking** - how to store MessageId for updates

Once you provide these, I can start building the DDEX feed generator!

---

## 9. Update and Takedown Message Formats (ERN 4.3)

For **Update** and **Takedown**, use the same ERN 4.3 namespace and MessageHeader pattern as Insert; message type and body differ as below.

### 9.1 Update (Metadata or Deal changes)

- **Message type:** ERN **NewReleaseMessage** with **MessageControlType** `UpdateMessage` (or equivalent per ERN 4.3 spec).
- **Reference to original:** Include a reference to the previous Insert (e.g. **MessageId** of the original message, or **LinkedReleaseId** / **ReleaseId** so the DSP can match the release).
- **Content:** Send only the **sections that changed** (e.g. updated PartyList, ResourceList, ReleaseList, or DealList), or a full replacement of the release metadata so the DSP can replace the previous version.
- **UpdateReason** (if supported): e.g. `MetadataCorrection`, `PriceChange`, `TerritoryChange`.

Implementation note: Reuse the same builder as Insert; for "update" runs, set MessageControlType to the update type and reference the original MessageId in the header or in a linked message reference. Package layout can stay `{UPC}/{UPC}.xml` with updated XML.

### 9.2 Takedown

- **Message type:** ERN **ReleaseTakedownMessage** (or equivalent in ERN 4.3) indicating removal of content.
- **MessageHeader:** Same as Insert (MessageSender = Coin Digital, MessageRecipient = Spotify, MessageCreatedDateTime, MessageControlType e.g. `LiveMessage`).
- **Reference to release:** One or more **ReleaseReference** (e.g. `R_{UPC}`) and/or **ResourceReference** (e.g. `A_{ISRC}`) for the release/tracks being taken down.
- **TakedownReason:** Code or text (e.g. `RightsIssue`, `ArtistRequest`, `ContractExpiry`, `Other`). Use a default if your app does not store a reason.
- **Effective date:** Optional **TakedownDate** or validity period for when the takedown takes effect.

Implementation note: Implement a small builder that outputs a ReleaseTakedownMessage (or your DSP's required takedown format) with ReleaseReference(s) and optional ResourceReferences, reusing the same MessageHeader and Party IDs from `ddex_config.py`.

### 9.3 Package layout (Insert / Update)

- **Root folder:** `{UPC}/` (e.g. `8905285127614/`).
- **DDEX XML:** `{UPC}/{UPC}.xml` or `{UPC}.xml` inside the folder (e.g. `8905285127614.xml`).
- **Resources:** `{UPC}/resources/coverart.jpg`, `{UPC}/resources/1_1.flac`, `1_2.flac`, … (one file per track in order). XML references use relative paths: `resources/coverart.jpg`, `resources/1_1.flac`, etc.
- **Track duration:** Extracted from these audio files when building the DDEX (see `ddex_duration.py`); if unavailable, use `PT00H00M00S` as fallback.
