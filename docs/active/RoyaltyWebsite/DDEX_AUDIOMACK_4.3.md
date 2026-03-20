# Audiomack DDEX 4.3 – Ingestion, Update, Takedown

This doc captures **only the details we need** for Audiomack feeds in **ERN 4.3**. It is derived from **Audiomack’s onboard DDEX samples** (new.xml, update.xml, takedown.xml – ERN 382), the **Audiomack DDEX Requirements (updated Aug 2024)** PDF, and mapped to our 4.3 implementation.

---

## 0a. Using Audiomack onboard samples (new / update / takedown)

We use the three samples as the reference and map them to ERN 4.3:

| Sample | UpdateIndicator | Territory | Deal ValidityPeriod | Our implementation |
|--------|------------------|------------|----------------------|--------------------|
| **new.xml** | OriginalMessage | Worldwide | StartDate only | Ingestion: we set UpdateIndicator **OriginalMessage** for store=audiomack; DealList with StartDateTime; TerritoryCode Worldwide. |
| **update.xml** | OriginalMessage | Full ISO list (AD, AE, …) | StartDate | Metadata/territory update: full territory list; we can add when we implement update flow. |
| **takedown.xml** | UpdateMessage | Full ISO list | **EndDate** (e.g. 2024-08-30) | Takedown = NewReleaseMessage with **UpdateMessage** + ValidityPeriod **EndDate**. We follow this pattern (no PurgeReleaseMessage in samples). |

From the samples we have also aligned:

- **MessageRecipient:** PADPIDA2017103008S, Audiomack LLC.
- **DealList:** ReleaseDeal with DealReleaseReference to track (R1); two Deals (AdvertisementSupportedModel, SubscriptionModel), each with **Stream** + **OnDemandStream** in 382 → we use OnDemandStream + NonInteractiveStream in 4.3.
- **DisplayArtist:** In 382, PartyId with Namespace sender + PartyId Namespace PADPIDA2017103008S (empty or Audiomack Artist ID). In 4.3 we reference artists via PartyList; we add **PartyId with Namespace DPID:PADPIDA2017103008S** in PartyList when we have **audiomack_id** on the artist so releases map to the correct profile.
- **UpdateIndicator:** We now set it for store=audiomack: **OriginalMessage** for new, **UpdateMessage** for update/takedown (when using message_control_type="UpdateMessage").

Takedown: we will implement **Option B** (NewReleaseMessage with UpdateMessage + EndDate) to match the takedown sample; PurgeReleaseMessage remains optional if Audiomack later confirm they accept it for 4.3.

---

## 0. Extract from Audiomack DDEX Requirements PDF (Aug 2024)

| Item | PDF value | Use for our feed |
|------|-----------|-------------------|
| **DDEX versions (PDF)** | 4.1.1 and 3.8.2 (examples 3.8.2) | **We use 4.3** – need to confirm they accept 4.3 |
| **Party ID** | PA-DPIDA-2017103008-S (with hyphens); in XML sample: `PADPIDA2017103008S` | We use `PADPIDA2017103008S` ✓ |
| **Party Name** | Audiomack LLC | We use this ✓ |
| **Deals** | AdvertisementSupportedModel, SubscriptionModel (album or track level) | We use both ✓ |
| **Use types (PDF)** | Stream or OnDemandStream | We use OnDemandStream + NonInteractiveStream; confirm for 4.3 |
| **File delivery** | **AWS S3 only** (no SFTP/SSH) | We **push** to their S3. We need bucket name, prefix, and write credentials. See **AUDIOMACK_PUSH_DELIVERY.md** for what to ask them. |
| **Batch (preferred)** | Level 2 = batch folder, Level 3 = release folders (UPC/GRid) | Document; 100 releases/batch, 30 min between batches, 1000/day |
| **Batch complete** | Empty file `BatchComplete_{delivery_name}.xml` in Level 2 folder | Add when we implement S3 delivery |
| **Audio** | FLAC 44.1 kHz preferred; 24-bit accepted but not recommended; no Dolby Atmos/Spatial | Asset spec; we reference resources/1_N.flac |
| **Image** | **PNG** preferred, max 50MB (no max dimensions) | We currently reference JPEG; consider PNG for Audiomack or document |
| **Audiomack Artist ID** | Must be sent in DisplayArtist: `<PartyId Namespace="DPID:PADPIDA2017103008S">2066684</PartyId>`; for 4.1.1 use PartyList/Party | **Feed update:** add when we have Artist’s Audiomack ID so releases map to correct artist profile |
| **Timed release** | StartDateTime with timezone (Z or offset); they use furthest time for all territories | We can add Z (UTC) to StartDateTime |
| **Samples they want** | New song, new album, metadata update, audio update, takedown | We have new + takedown; clarify update formats for 4.3 |

---

## 1. Message header (all message types)

| Field | Value (ERN 4.3) |
|-------|------------------|
| **MessageRecipient PartyId** | `PADPIDA2017103008S` |
| **MessageRecipient PartyName** | `Audiomack LLC` |
| **MessageSender** | Coin Digital Party ID (from config) |
| **Namespace / schema** | `http://ddex.net/xml/ern/43` |

Configured in `releases/ddex_config.py` and `releases/data/ddex_dsps.json`.

---

## 2. Ingestion (New release)

- **Message type:** `NewReleaseMessage` (ERN 4.3).
- **UpdateIndicator:** `OriginalMessage` (we set this for store=audiomack per new.xml).
- **Deal terms (from Audiomack samples, applied in 4.3):**
  - Two deals: `AdvertisementSupportedModel` and `SubscriptionModel`.
  - **UseType:** `OnDemandStream`, `NonInteractiveStream` (no `ConditionalDownload` – matches Audiomack samples).
  - **TerritoryCode:** `Worldwide`.
  - **ValidityPeriod:** `StartDateTime` only (release date; no end date for new ingest).
- **ReleaseDeal:** One or more `DealReleaseReference` to track-level release refs (e.g. `R_{isrc}`) and optionally main release ref; we reference both track-level and main release.
- **Content:** ResourceList (SoundRecordings + Image), ReleaseList (main Release + TrackReleases), DealList as above.

Our ingestion is generated with:

```bash
python manage.py build_ddex <release_id> --store audiomack [--output path]
```

---

## 3. Update (metadata / territory / validity change)

From Audiomack’s **update** sample (ERN 382):

- **UpdateIndicator:** `UpdateMessage`.
- **Structure:** Same as NewReleaseMessage (full ResourceList, ReleaseList, DealList).
- **Territory:** Update sample uses explicit list of ISO territory codes (e.g. AD, AE, …) instead of only “Worldwide” when communicating territory or validity changes.
- **ValidityPeriod:** Can include **EndDate** to end availability (e.g. for takedown or territory removal).

For **ERN 4.3** we will:

- Send **NewReleaseMessage** with an update indicator (e.g. `UpdateMessage` if supported in 4.3) and the same header as ingestion.
- Include full metadata and deal terms; for “end of availability” we use **ValidityPeriod EndDate** in DealTerms.

**Open point for Audiomack:** In ERN 4.3, is the update flow (metadata / territory / validity change) still **NewReleaseMessage** with an update indicator, and do you require explicit territory lists in updates?

---

## 4. Takedown

From Audiomack’s sample (labelled takedown):

- They use **NewReleaseMessage** with **UpdateIndicator = UpdateMessage** and **ValidityPeriod EndDate** in DealTerms to signal end of availability (no PurgeReleaseMessage in the sample).

For **ERN 4.3** we support two options until Audiomack confirms:

1. **Option A – PurgeReleaseMessage (ERN 4.3 standard):**  
   Message type `PurgeReleaseMessage` with MessageHeader (same sender/recipient as above) and **ReleaseReference** list (e.g. main release ref `R_{upc}` and optionally track refs). No ResourceList/DealList.

2. **Option B – NewReleaseMessage with EndDate (per your sample):**  
   Same as update: **NewReleaseMessage** with update indicator and **DealTerms.ValidityPeriod.EndDate** set to the takedown effective date.

**Open point for Audiomack:** For ERN 4.3, do you accept **PurgeReleaseMessage** for takedowns, or only **NewReleaseMessage** with UpdateIndicator and ValidityPeriod EndDate? If you accept PurgeReleaseMessage, we can generate it with:  
`python manage.py build_ddex_takedown <release_id> --store audiomack [--output path]`

---

## 5. Field mappings (from samples → our 4.3 use)

| Sample (382) | Our ERN 4.3 |
|--------------|-------------|
| ParentalWarningType `NoAdviceAvailable` | We use `Explicit` / `NotExplicit`; confirm if you require `NoAdviceAvailable` or accept our mapping. |
| UseType `Stream` + `OnDemandStream` | We use `OnDemandStream` + `NonInteractiveStream` (4.3 equivalents). |
| ValidityPeriod `StartDate` (date only) | We use `StartDateTime` (date + T00:00:00). |
| TerritoryCode `Worldwide` (new) | We use `Worldwide` for ingestion. |

---

## 6. Feed updates (from Aug 2024 PDF)

- **Audiomack Artist ID:** When we have an Audiomack Artist ID for an artist, we send it in **PartyList/Party** (PartyId Namespace DPID:PADPIDA2017103008S) for store=audiomack so releases map to the correct profile. **Done:** Builder adds this when `Artist.audiomack_id` is set. Add an `audiomack_id` field on the Artist model when ready.
- **Image:** PDF says PNG, max 50MB. We currently reference JPEG/coverart; for Audiomack delivery we can document “supply PNG” or allow PNG file reference when generating for audiomack.
- **Timed release:** Use StartDateTime with timezone (e.g. `Z` for UTC); PDF says they use the furthest time for all territories.
- **Delivery:** Document S3-only; batch layout and BatchComplete file when we implement the delivery pipeline.

---

## 7. Final questions for Audiomack (after using your samples)

We have aligned our ERN 4.3 feed to your **onboard samples** (new.xml, update.xml, takedown.xml) and your Aug 2024 PDF. We set **UpdateIndicator** (OriginalMessage / UpdateMessage), same MessageRecipient and deal structure, and we will send **Audiomack Artist ID** in PartyList/Party when we have it. For takedown we follow your sample (NewReleaseMessage with UpdateMessage + ValidityPeriod EndDate).

**Contact:** contentoperations@anghami.com (general); api@audiomack.com (API keys for OAuth/Artist ID).

Please confirm or provide the following:

1. **ERN 4.3:** Your document lists 4.1.1 and 3.8.2; our pipeline is ERN 4.3 only. Do you accept **ERN 4.3** for new deliveries, updates, and takedowns? Any 4.3-specific required elements or schema constraints?

2. **Use types:** The document states “Stream or OnDemandStream”. For ERN 4.3 we use **OnDemandStream** and **NonInteractiveStream**. Do you accept these for 4.3, or do you require “Stream” (and if so, what is the exact 4.3 UseType value)?

3. **ParentalWarningType:** Your samples use NoAdviceAvailable; we use Explicit / NotExplicit. Do you accept these or require NoAdviceAvailable in some cases?

4. **S3 delivery:** We will deliver via AWS S3 per your requirements. Please provide (or confirm process for) bucket name, region, and credentials for our account. Confirm folder structure and that **BatchComplete_{delivery_name}.xml** (empty) in Level 2 is still required for 4.3 batches.

5. **Audiomack Artist ID:** We will send it in **PartyList/Party** (PartyId Namespace DPID:PADPIDA2017103008S) for ERN 4.3. Confirm this is correct and that only MainArtist is processed.

6. **Image:** Your PDF says PNG preferred, max 50MB; your samples reference JPEG. Should the ERN resource reference point to a **PNG** file for Audiomack, or is JPEG acceptable when we supply PNG in the resources folder?

---

## 7a. Audiomack reply (Feb 2026)

Audiomack responded to the above. They noted that **a feed is already set up and delivering to S3** (e.g. recent delivery: `audiomack-contentimport/coin-digital/20260217093805337`) and asked to clarify intent behind “creating another feed”.

**Confirmed by Audiomack:**

| # | Topic | Answer |
|---|--------|--------|
| 1 | ERN 4.3 | Yes, they accept ERN v4.3. |
| 2 | Use types | Yes, they accept **OnDemandStream** and **NonInteractiveStream**. |
| 3 | ParentalWarningType | Yes, they accept **Explicit** and **NotExplicit**. |
| 4 | Batch complete | Yes, **Batch Complete** files are recommended. |
| 5 | Audiomack Artist ID in PartyList (DPID:PADPIDA2017103008S) | Yes, correct. They **only process MainArtist**. |
| 6 | Image | ERN references should point to a **PNG** file, ideally. |

**Action:** Clarify to Audiomack that we were not creating a second feed but confirming alignment with their samples and 4.3; then ask when we can start ingestion (or confirm we are ready). For future deliveries, ensure cover art resource reference in the ERN points to PNG when delivering to Audiomack.

---

## 8. Code references

- Config: `releases/ddex_config.py` (AUDIOMACK_PARTY_ID, AUDIOMACK_PARTY_NAME).
- DSP registry: `releases/data/ddex_dsps.json` (audiomack entry).
- Ingestion builder: `releases/ddex_builder.py` (`build_new_release_message(..., store="audiomack")`, `_add_deal_terms_audiomack`). For audiomack we set **UpdateIndicator** (OriginalMessage/UpdateMessage) and **PartyId** with Namespace DPID:PADPIDA2017103008S in PartyList when `Artist.audiomack_id` is set.
- Management command: `python manage.py build_ddex <id> --store audiomack`.
- Takedown (when used): `releases/ddex_audiomack_takedown.py` – `build_audiomack_takedown_message()`.
