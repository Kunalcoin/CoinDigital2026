# DDEX feed – status and flow

## Agreed flow

| Step | Who | Action | What happens |
|------|-----|--------|--------------|
| 1 | User | **Submit for approval** | System builds DDEX package (XML + poster + WAV + FLAC + MP3 per track) and **saves to our S3**. Release status → **pending_approval**. **No** delivery to stores. |
| 2 | Admin | **Approve release** | Release status → **approved**, published = true. **No** delivery. |
| 3 | Admin | **Clicks "DDEX delivery for Audiomack, Gaana & TikTok"** | System sends the **existing package** to each configured store (Audiomack, Gaana, TikTok) per their rules (S3/SFTP). |

---

## Current implementation status

### Done

- **Package on submit:** When the user submits for approval, the system:
  - Assigns UPC/ISRC if missing.
  - Checks: release has cover art; every track has at least one audio (FLAC or `audio_track_url`).
  - Builds the DDEX package and saves to S3 at `ddex/packages/<release_id>/<upc>/`:
    - `<upc>.xml` (ERN 4.3)
    - `resources/coverart.jpg`
    - Per track: `1_N.flac`, `1_N.wav`, `1_N.mp3` (when WAV/MP3 URLs exist)
  - Sets status to **pending_approval**. No delivery.

- **Approve is separate:** Admin “Approve” only updates status to **approved** and sets published. It does **not** trigger delivery.

- **DDEX Delivery is separate:** Admin must click **“DDEX delivery for Audiomack, Gaana & TikTok”** to send to stores. Before delivery:
  - Package must exist (created at submit-for-approval).
  - Release must be **approved**.

- **Rigid checks:**
  - Submit: cover art required; every track must have at least one audio; UPC/ISRC available.
  - DDEX Delivery: `package_exists(release)` and `release.approval_status == approved`.

### Optional / future

- **Store-specific formats:** Delivery today uses FLAC from track URLs. If a store requires WAV or MP3 from the package, delivery logic can be extended to read from the package path (e.g. `resources/1_1.wav`) when configured.
- **Retry / audit:** Package is stored once; admin can click DDEX delivery again to retry (e.g. after fixing store credentials). Consider storing last delivery result per store for audit.

---

## Checks enforced (rigid)

1. **Submit for approval**
   - Release is in draft (or rejected).
   - UPC codes available; one assigned to release.
   - ISRC codes available; one assigned per track.
   - Release has **cover art** (`cover_art_url`).
   - Every track has **at least one audio** (FLAC or `audio_track_url`).
   - After checks: build package (XML + poster + WAV + FLAC + MP3). If package build fails → 502, release remains pending.

2. **Approve**
   - Only admin/staff.
   - Release is **pending_approval**.
   - On success: status → approved, published = true. No delivery.

3. **DDEX Delivery button**
   - Only admin/staff.
   - **Package exists** in S3 (`ddex/packages/<release_id>/<upc>/<upc>.xml`).
   - Release is **approved**.
   - Then: send to each store in `DELIVERY_STORES` (Audiomack, Gaana, TikTok) per their rules.

---

## S3 package layout

```
s3://<our-bucket>/ddex/packages/<release_id>/<upc>/
├── <upc>.xml          # ERN 4.3 NewReleaseMessage
├── <upc>.json         # UPC, release_id, resource_md5_map (for TikTok)
└── resources/
    ├── coverart.jpg
    ├── 1_1.flac, 1_1.wav, 1_1.mp3   # track 1
    ├── 1_2.flac, 1_2.wav, 1_2.mp3   # track 2
    └── ...
```

---

## Env / config

- **Package build and storage:** Uses `AWS_STORAGE_BUCKET_NAME` (our bucket).
- **Delivery:** `DELIVERY_STORES=audiomack,gaana,tiktok` plus store-specific env (Audiomack S3, Gaana SFTP, TikTok S3). See `LIVE_DDEX_DEPLOYMENT.md` and store-specific docs.

---

## Summary

- **Submit** → build and store package (XML + poster + WAV + FLAC + MP3); status = pending_approval.
- **Approve** → status = approved only; no delivery.
- **DDEX Delivery** → send existing package to configured stores; requires package + approved.

Nothing is pending for the agreed flow; the rigid checks above are in place.
