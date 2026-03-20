# How delivery to stores works

**Delivery model:** We **push** the package (DDEX XML + cover + audio) to each DSP. No store retrieves content from our S3; we always upload to their system (their S3, SFTP, or API).

---

Two **separate** actions (no confusion between them):

1. **Approve** – Uses the **Sonosuite API** to send the release to all stores via their delivery. Same as before; no DDEX involved.
2. **DDEX delivery for Audiomack** – A **separate button** on the same page. Builds **DDEX ERN 4.3** for Audiomack and uploads the XML to Audiomack’s S3. Does **not** change approval status.

---

## Approve (API)

1. User clicks **“Distribute this release”** → release goes to **Pending approval**.
2. Admin clicks **“Approve”**.
3. Backend calls **Sonosuite** (if configured) and marks the release approved/published.

---

## DDEX delivery for Audiomack (separate button)

- On **Preview & Distribute**, admin sees an extra button: **“DDEX delivery for Audiomack”** (next to Approve / Distribute).
- When clicked: build DDEX ERN 4.3 for Audiomack → upload XML to S3 (if `AUDIOMACK_S3_BUCKET` is set) or save to `out_audiomack/<upc>.xml` locally. **Does not** change approval or published status.
- Use this when you want to deliver to Audiomack via your own DDEX feed; use **Approve** when you want to send to stores via the Sonosuite API.

**Audio and cover art** are already in your S3; the DDEX XML is built from the release/track data and uploaded to the Audiomack S3 path (or saved locally).

---

## Configuration (for DDEX delivery for Audiomack)

**You don’t need Audiomack’s S3.** By default the DDEX XML is uploaded to **your** S3 bucket (the same one used for WAV and poster: `AWS_STORAGE_BUCKET_NAME` in .env). Path: `ddex/audiomack/<date>/<upc>.xml`. So everything stays in your S3; you can then share or transfer from there.

**To push to Audiomack:** We need their S3 bucket and write access (credentials or cross-account). See **AUDIOMACK_PUSH_DELIVERY.md** for the exact list of questions to send them. Once we have bucket + credentials, we set `AUDIOMACK_S3_BUCKET`, `AUDIOMACK_S3_PREFIX`, and (if they give us keys) `AUDIOMACK_AWS_ACCESS_KEY_ID` / `AUDIOMACK_AWS_SECRET_ACCESS_KEY`; then the same button will push the full package to their bucket.  
If no Audiomack bucket is set, the package is built and saved to **our** S3 (`ddex/audiomack/<date>/`) for now; we do not push to their side until they provide access.

### DDEX Party IDs and store list

- **Coin Digital (sender):** `releases/ddex_config.py` → `COIN_DIGITAL_PARTY_ID` (from env `DDEX_PARTY_ID_COIN`).
- **Stores (recipients, deal terms):** `releases/data/ddex_dsps.json` — each DSP has `code`, `party_id`, `party_name`, `deal_profile`, `is_active`. The builder uses this to build store‑specific ERN 4.3.

---

## Where the buttons are

- **Approve** – Same as always: sends to stores via **Sonosuite API**. No DDEX.
- **DDEX delivery for Audiomack** – Separate button on **Preview & Distribute** (admin only). Builds DDEX and uploads to Audiomack S3. Does not approve the release.

---

## Adding more stores (future)

1. **DDEX build**  
   Already supported for any store in `ddex_dsps.json` via `build_new_release_message(release, store="...")`.

2. **Delivery method**  
   In `releases/store_delivery.py`:
   - Add the store code to `DELIVERY_IMPLEMENTED`.
   - In `deliver_release_to_store()`, add a branch that builds DDEX for that store and then does the store‑specific upload (e.g. S3, SFTP, API).

3. **Config**  
   Add the store to `DELIVERY_STORES` in .env, e.g. `DELIVERY_STORES=audiomack,gaana`.

---

## Takedown and update feed

- **Takedown request:** When a user submits a **takedown request** for a release (button on Preview & Distribute), the app:
  1. Marks the release as takedown requested and sends the usual email to support.
  2. Sends a **DDEX takedown feed** to Audiomack and Gaana:
     - **Audiomack:** PurgeReleaseMessage to their S3 (or your S3 at `ddex/audiomack/takedown/...`).
     - **Gaana:** NewReleaseMessage with TakeDown to your S3 and to Gaana SFTP (`upload/takedown/...`).
  DSP delivery failures are logged only; the user still gets “Your request to takedown this release is successfully submitted!”
- **Update:** To send an updated release (metadata or assets) to Audiomack/Gaana, use the same **DDEX delivery for Audiomack & Gaana** button for that release; it builds and pushes the current package. There is no separate “update request” flow; the one-click delivery is used for both new and updated releases.

---

## Summary

| What you want | What to do |
|---------------|------------|
| Send to stores via API (existing flow) | Use **Approve** (Sonosuite). |
| Send to Audiomack via our DDEX feed | Use the **DDEX delivery for Audiomack** button (separate; does not approve). |
| Audiomack S3 upload | Set `AUDIOMACK_S3_BUCKET` and `AUDIOMACK_S3_PREFIX` in .env. |
| WAV and poster already in S3 | No change; DDEX is built from DB; Audiomack gets XML to their S3. |
| Takedown request | User clicks takedown → email to support + DDEX takedown sent to Audiomack and Gaana automatically. |
| Live deployment checklist | See **LIVE_DDEX_DEPLOYMENT.md**. |
