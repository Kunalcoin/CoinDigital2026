# DDEX Gaana Integration

This document describes the Gaana DDEX setup and how to use it for Insert, Update, and Takedown, including batch folder structure and SFTP delivery.

---

## 1. Gaana Party ID and Registry

Gaana (Entertainment Network India Limited) is configured in the DSP registry:

- **Code:** `gaana`
- **Party ID:** `PADPIDA2025121702Q` (from Gaana sample files)
- **Party Name:** Entertainment Network India Limited
- **Deal profile:** streaming (SubscriptionModel + AdvertisementSupportedModel; OnDemandStream, NonInteractiveStream, ConditionalDownload)
- **Config:** `RoyaltyWebsite/releases/data/ddex_dsps.json` — Gaana is set `is_active: true` for generation/delivery.

---

## 2. Release Types and Message Types

- **Release types:** Single, Album, EP, etc. are set via `<ReleaseType>` under `ReleaseList` (from `release.album_format`: single → Single, ep → EP, album → Album).
- **Insert:** NewReleaseMessage (LiveMessage) — full metadata + resources.
- **Update:** Two forms:
  - **Metadata-only:** NewReleaseMessage with `MessageControlType="UpdateMessage"` and `LinkedMessageId` set to the original Insert message ID. No new media assets required.
  - **Metadata + media:** Same as above; include updated/changed assets in the batch.
- **Takedown:** Two options (both use NewReleaseMessage with special deal terms):
  - **Immediate:** `TakeDown` tag in `DealTerms` (`<TakeDown>true</TakeDown>`).
  - **Time-based:** `ValidityPeriod` with `EndDate` (YYYY-MM-DD).

Sample reference files (for structure only, do not copy as-is) are under:  
`users/ashimagoel/documents/DDEX Files/Gaana`

---

## 3. Commands

### Insert (new release)

Generate DDEX for Gaana only (standard layout):

```bash
python manage.py build_ddex <release_id> --store gaana [--output path]
```

Generate for all active DSPs (including Gaana):

```bash
python manage.py build_ddex_all <release_id> [--output ddex_output]
```

### Gaana batch (Insert) — required folder structure for Gaana SFTP

Gaana requires a strict batch layout. Use:

```bash
python manage.py build_ddex_gaana_batch <release_id> [--output ddex_gaana_batches] [--batch-number 20250216120000001]
# or by UPC:
python manage.py build_ddex_gaana_batch --upc 3667007197057 --output /tmp/gaana_batches
```

This creates:

```
<output>/<BatchNumber>/
    <upc>/
        <upc>.xml
        resources/    (place cover art and audio here)
    BatchComplete_<BatchNumber>.xml
```

- Put assets in `resources/` so they match the URIs in the XML (e.g. `coverart.jpg`, `1_1.flac`, `1_2.flac` for tracks).
- Upload the **entire** `<BatchNumber>` folder to the Gaana SFTP path they provide.

### Update (metadata-only or metadata + media)

- **Metadata-only:** Generate NewReleaseMessage with Update flag and same UPC; no new media needed in the batch.
- **Metadata + media:** Same XML type; include updated/changed assets in `resources/` and reference them in the XML if your builder outputs different URIs.

Use the same batch command and add `--update` and (if available) `--linked-message-id`:

```bash
python manage.py build_ddex_gaana_batch <release_id> --update [--linked-message-id <original_MessageId>]
```

For a single XML file (non-batch) you can call the builder with `message_control_type="UpdateMessage"` and `linked_message_id` set.

### Takedown

**Automatic (when user requests takedown):**  
When a user submits a **takedown request** for a release (button on Preview & Distribute), the app automatically sends a DDEX takedown to **Audiomack** and **Gaana**: Gaana receives a NewReleaseMessage with TakeDown at `upload/takedown/<batch>/<upc>_takedown.xml` on SFTP. No manual command needed.

**Manual (CLI):**

**Immediate (TakeDown tag):**

```bash
python manage.py build_ddex_takedown <release_id> --store gaana [--output path]
# or with explicit immediate flag:
python manage.py build_ddex_takedown <release_id> --store gaana --immediate
```

**Time-based (EndDate):**

```bash
python manage.py build_ddex_takedown <release_id> --store gaana --end-date 2025-12-28 [--output path]
```

Takedown XML is a NewReleaseMessage with the same structure as Insert but with takedown deal terms. For Gaana batch delivery, place this XML in the same batch layout (e.g. `<BatchNumber>/<upc>/<upc>.xml` for the takedown message) and include `BatchComplete_<BatchNumber>.xml`.

---

## 4. Delivery

### One-click: Preview & Distribute (Audiomack & Gaana)

On **Preview and Distribute** (`/releases/preview_distribute_info/<release_id>`), the button **"DDEX delivery for Audiomack & Gaana"** (admin only):

- Builds DDEX ERN 4.3 for **Audiomack** and **Gaana** (store-specific XML).
- Uploads **XML + cover + audio** to **your S3** in two folders:
  - **Audiomack:** `ddex/audiomack/<YYYYMMDD>/<upc>.xml` and `.../resources/` (coverart.jpg, 1_1.flac, …).
  - **Gaana:** `ddex/gaana/<YYYYMMDD>/<upc>.xml` and `.../resources/` (same assets).
- No Audiomack or Gaana S3 bucket is required; packages live in your bucket. You can share access or transfer to Gaana (e.g. SFTP) as agreed.

Gaana has **whitelisted** the IP **54.147.21.20** for SFTP. The push to Gaana **must run from the server with that IP** (e.g. your EC2). Running from a different machine (e.g. laptop) will get "Connection reset by peer".

**Upload path:** You land in `/Gaana_Daily/CoinDigital/backup` (chroot). Use **`upload/`** for new deliveries. Set `GAANA_SFTP_REMOTE_PATH=upload` in .env so the app uploads to `upload/<BatchNumber>/<upc>/` (XML + resources/ + BatchComplete).

### SFTP (optional / alternate)

- Gaana also supports **SFTP-based** delivery.
- They provide SFTP credentials and upload path; **static IP has been provided and whitelisted**.
- For strict batch layout (BatchNumber/upc/upc.xml, BatchComplete_*.xml), use `build_ddex_gaana_batch` and upload the generated folder to their SFTP. The one-click flow above produces the same XML + resources in S3; you can move that folder to SFTP if needed.

---

## 5. Testing (per Gaana email)

1. Upload batches for **all** of: **Insert**, **Update**, **Takedown** for the **same UPC** on their SFTP.
2. They will validate:
   - Folder structure
   - Metadata files
   - All scenarios (Insert / Update / Takedown)
3. After successful verification, they will set up the DDEX pipeline for live deliveries.
4. After uploading test batches, inform them on the same email thread.

---

## 6. Checklist

- [x] Gaana added to DSP registry with Party ID `PADPIDA2025121702Q` and name "Entertainment Network India Limited".
- [x] Insert: `build_ddex --store gaana` and `build_ddex_gaana_batch` for batch layout.
- [x] Update: NewReleaseMessage with `UpdateMessage` and optional `LinkedMessageId`; batch command supports `--update`.
- [x] Takedown: `build_ddex_takedown --store gaana` with `--immediate` or `--end-date YYYY-MM-DD`.
- [x] Static IP provided to Gaana; IP whitelisted.
- [x] One-click delivery: "DDEX delivery for Audiomack & Gaana" on Preview & Distribute builds Gaana DDEX and saves XML + poster + audio to your S3 (`ddex/gaana/<date>/`).
- [ ] Upload test batches (Insert, Update, Takedown for same UPC) to Gaana SFTP or share S3 package and confirm with Gaana.

---

## 7. File / Code References

| Item | Location |
|------|----------|
| DSP registry | `releases/data/ddex_dsps.json` (gaana entry) |
| DDEX builder (Insert/Update/Takedown terms) | `releases/ddex_builder.py` |
| Gaana delivery (S3 package: XML + resources) | `releases/gaana_delivery.py` |
| Takedown command (Audiomack + Gaana) | `releases/management/commands/build_ddex_takedown.py` |
| Gaana batch layout + BatchComplete | `releases/management/commands/build_ddex_gaana_batch.py` |
| Preview & Distribute view (Audiomack + Gaana button) | `releases/views.py` (`ddex_deliver_audiomack`), `volt_preview_distribute_info.html` |
| Gaana sample files (reference only) | `users/ashimagoel/documents/DDEX Files/Gaana` |
| MessageFileName | Set in builder to `{upc}.xml` for Gaana compatibility |
