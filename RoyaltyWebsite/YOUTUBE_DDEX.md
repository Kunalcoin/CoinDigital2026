# YouTube DDEX Feed Setup

This document describes how to set up **YouTube DDEX** for the Royalty website, using the existing DDEX ERN 4.3 pipeline and DSP registry. It is based on [YouTube’s official DDEX documentation](https://support.google.com/youtube/answer/3503737).

---

## 1. YouTube DDEX Overview

YouTube’s DDEX feed is for **music label and distributor partners** who use **YouTube Studio Content Manager** and support:

- **Art Tracks** for YouTube Premium  
- **Upload of music videos** to channel(s)  
- **Rights management** for sound recordings and/or music videos via **Content ID**

**Requirements:**

- **ERN version:** YouTube supports **ERN 3.4–3.8 and 4.3**. This project uses **ERN 4.3**, which is supported.
- **Release profiles:** Feeds must follow either the [Audio Album profile](https://ern-rp.ddex.net/electronic-release-notification-message-suite%253A-part-2-release-profiles/6-rules-for-release-profiles/6.2-audio-profile/) or the [Single Resource Release profile](https://ern-rp.ddex.net/electronic-release-notification-message-suite%253A-part-2-release-profiles/6-rules-for-release-profiles/6.5-simple-audio-single-profile/), as published by DDEX.

---

## 2. ERN Message Structure (YouTube)

### ERN 4.3 (what we use)

| Section         | Purpose |
|----------------|---------|
| **MessageHeader** | Sender/recipient (DDEX Party IDs), message ID, timestamp |
| **PartyList**     | All parties (artists, writers, labels) |
| **ResourceList**  | Sound recordings, videos, images (with unique references) |
| **ReleaseList**   | Releases (single, EP, album) and their structure/sequence |
| **DealList**      | Commercial terms per release (territories, usage rights, Content ID, dates) |

### Filename rule

Per [DDEX convention](https://support.google.com/youtube/answer/3503737): **the DDEX filename must include the unique release ID** (UPC, EAN or GRid) from `<ReleaseId>`.

**Our implementation:** We already output XML as `{upc}.xml` under `{dsp_code}/{upc}/`, so the release ID (UPC) is in the filename. No change needed.

### Sound recording ownership (Worldwide)

To avoid “ownership not defined” errors (e.g. from YouTube Content ID or partners like Sonosuite), each **SoundRecording** must clearly state who owns the asset and where. Our builder emits **ResourceRightsController** for every sound recording with:

- **ApplicableTerritoryCode="Worldwide"** — ownership applies in the WW territory.
- **RightsControllerPartyReference** — the label/vendor party (your company).
- **RightsControlType** — RightsController.
- **RightSharePercentage** — 100 (full ownership).

This matches “we own full ownership in the WW area” for all assets and aligns with the Art Track / direct DDEX reference samples.

---

## 3. How This Project Supports YouTube

### DSP registry

YouTube Music is already in the DSP registry as **`youtube_music`**:

- **File:** `releases/data/ddex_dsps.json`
- **Entry:** `code: "youtube_music"`, `party_name: "YouTube Music"`, `deal_profile: "streaming"`, `is_active: false`
- **Party ID:** Currently `PADPIDA_PLACEHOLDER_YOUTUBE`. This must be replaced with the **official YouTube/Google DDEX Party ID** once provided by your YouTube partner representative.

### Deal profile

YouTube is configured with **`deal_profile: "streaming"`**, which produces:

- **CommercialModelType:** SubscriptionModel, AdvertisementSupportedModel  
- **UseType:** OnDemandStream, NonInteractiveStream, ConditionalDownload  

This matches typical streaming/Art Track use for YouTube Music.

### Release profiles

Our builder already maps to DDEX release profiles:

- **Album / EP** → `ReleaseProfileVersionId`: **Audio** (Audio Album profile)  
- **Single** → **SimpleAudioSingle** (Single Resource Release profile)  

So we comply with YouTube’s required profiles.

### Commands (no code change)

Once `youtube_music` is active and has a real Party ID:

- **One release, YouTube only:**  
  `python manage.py build_ddex <release_id> --store youtube_music`
- **One release, all active DSPs (including YouTube):**  
  `python manage.py build_ddex_all <release_id> [--output ddex_output]`
- **Batch:**  
  `python manage.py build_ddex_batch [--since YYYY-MM-DD] [--status approved]`

Output layout: `output/youtube_music/{upc}/{upc}.xml`.

---

## 4. Steps to Enable YouTube DDEX

### 4.1 Prerequisites (with YouTube)

1. **YouTube Studio Content Manager**  
   You must be a music label/distributor partner with Content Manager access.

2. **Your DDEX Party ID**  
   YouTube needs your company’s DDEX Party ID. If you don’t have one, apply at [dpid.ddex.net](http://dpid.ddex.net/).  
   Our sender Party ID is configured in `releases/ddex_config.py` (e.g. `COIN_DIGITAL_PARTY_ID`).

3. **Delivery method**  
   YouTube uses **SFTP or Aspera** for DDEX. Your **partner representative** must set up a dropbox (we recommend a dedicated one for DDEX, separate from Content ID).

### 4.2 Configure the registry

1. **Get YouTube’s DDEX Party ID**  
   Obtain the official Party ID (DPID) for YouTube/Google from your partner representative or YouTube’s DDEX onboarding docs.

2. **Edit** `releases/data/ddex_dsps.json`:
   - Set `youtube_music.party_id` to the real Party ID (replace `PADPIDA_PLACEHOLDER_YOUTUBE`).
   - Set `youtube_music.is_active` to `true` when you are ready to generate/deliver.

### 4.3 Test batches (YouTube’s process)

From [Preparing to upload DDEX files](https://support.google.com/youtube/answer/3498397):

1. **TestMessage**  
   Use `MessageControlType` **TestMessage** for validation (e.g. `python manage.py build_ddex <release_id> --store youtube_music --test` if your command supports `--test`, or set TestMessage in the builder for `youtube_music`).  
   Copy the DDEX file (and optionally media) to your YouTube dropbox.

2. **BatchComplete**  
   After uploading all files for a batch, create a file whose name starts with **BatchComplete**, then any characters, then `.xml` (e.g. `BatchComplete_1.xml`). This tells YouTube the batch is ready.  
   Test messages are only validated, not ingested; media files are not required for TestMessage.

3. **Test scenarios**  
   Submit test batches for:
   - Full new album  
   - Full new single  
   - (If applicable) Full new multi-disc release, full update, metadata-only update, separate deal terms, add track to album  

4. **Go live**  
   When validation succeeds, switch to **LiveMessage**, include media files, and repeat the upload. Then do ~200 releases for end-to-end testing with your partner rep.

### 4.4 Delivery (SFTP/Aspera)

- **Current codebase:** Dedicated YouTube delivery (e.g. `youtube_delivery.py` or a generic delivery layer) is not implemented yet. Gaana and Audiomack use SFTP/S3 in `gaana_delivery.py` and `audiomack_delivery.py`.
- **To add YouTube delivery:** Implement a similar module that:
  - Builds the DDEX package for `youtube_music` (XML + assets).
  - Uploads to the **SFTP or Aspera** dropbox provided by YouTube (paths and credentials from your partner rep or env/secrets).
  - Optionally writes a **BatchComplete** file and uploads it when the batch is complete.

Credentials and paths should be stored in environment or a secrets manager (e.g. `YOUTUBE_SFTP_HOST`, `YOUTUBE_SFTP_USER`, etc.), not in code.

---

## 5. Checklist

- [ ] Partner rep has configured your YouTube account for DDEX.
- [ ] Your company has a DDEX Party ID (and it’s set in `ddex_config.py`).
- [ ] YouTube’s Party ID obtained and set in `releases/data/ddex_dsps.json` for `youtube_music`.
- [ ] SFTP or Aspera dropbox for DDEX set up by partner rep.
- [ ] Test batches (TestMessage) uploaded and validated; then LiveMessage + media and end-to-end test.
- [ ] `youtube_music.is_active` set to `true` when going live.
- [ ] (Optional) Implement `youtube_delivery.py` (or equivalent) and wire it into your release/distribution flow.

---

## 6. References

- [Understanding the YouTube DDEX feed](https://support.google.com/youtube/answer/3503737)  
- [Preparing to upload DDEX files](https://support.google.com/youtube/answer/3498397)  
- [Message header](https://support.google.com/youtube/answer/3505274)  
- [DDEX ERN standard](https://kb.ddex.net/implementing-each-standard/electronic-release-notification-message-suite-(ern)/)  
- Internal: `DDEX_DSP_FLOW.md`, `DEAL_PROFILES.md`, `releases/data/ddex_dsps.json`
