# Release CSV Export & Upload to Distribute (Sonosuite)

## What’s implemented

### 1. CSV export fixes (Download Selected)

The “Download Selected” report on **Pending for Approval** (and release report) now matches the accepted Sonosuite template:

- **#catalog_number** = **#upc** (same value for each release).
- **Dates** are in **yyyy-mm-dd** (`#digital_release`, `#original_release`).
- **#user_email** = release creator’s email (`created_by.email`). If missing, it falls back to `DEPLOYMENT_EMAIL` from settings/.env.

The CSV is generated in `releases/processor.py` via `generate_release_metadata_csv()`. Format matches the sample: `CSV_Audio_Album_Metadata_Template_Sample.csv`.

### 2. Flow (with auto-upload)

- User: **Distribute** (submit for approval) → release status = `pending_approval`.
- **Automatically:** The system generates the metadata CSV (with the fixes above) and **uploads it to Sonosuite** (coin.sonosuite.com) using the same credentials as in `.env` (`SONOSUITE_ADMIN_EMAIL`, `SONOSUITE_ADMIN_PASSWORD`). Upload endpoint: `SONOSUITE_API_BASE_URL` + `/distribution/api/upload` (override with `SONOSUITE_UPLOAD_PATH` if needed).
- If the upload fails (e.g. wrong path or API not available), the release **stays in draft** and is not set to pending approval; the user sees an error and can fix the issue and try again. Admin can use **Download Selected** and upload the CSV manually on coin.sonosuite.com if needed.
- Admin: **Approve** on the Royalty site → release is sent to all stores via the existing Sonosuite delivery API.

---

## Upload endpoint

Upload is sent to the same base URL as the rest of the API: **coin.sonosuite.com** (use this only; do not use any other base URL), using the same login token. Default path: **`/distribution/api/upload`**. If your Sonosuite instance uses a different path, set it in env:

- **`SONOSUITE_UPLOAD_PATH`** – e.g. `/distribution/api/import` or `/api/upload` (must start with `/`).
