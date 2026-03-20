# Deploy to live: Sonosuite API + approval workflow + bulk approve

**Source (tested):** `live_code_complete_20260123_/django-docker-compose/RoyaltyWebsite`  
**Target (live):** Your live website codebase (e.g. `Coin Digital for API/...` or your server repo)

---

## What will be pushed (all related to API deliveries)

### 1. Backend – releases app

| File | What it does |
|------|----------------|
| **releases/sonosuite_client.py** | Sonosuite API: login, delivery (send to DSPs), get DSPs, upload CSV helper. Base URL: coin.sonosuite.com. User-friendly error for 404/HTML. |
| **releases/views.py** | Approval workflow: `pending_approval_releases`, `submit_for_approval`, `approve_release`, `reject_release`, `bulk_approve_releases`, `_approve_single_release`. Distribute POST = set pending only (no ingestion API). Preview/distribute context (approval_status, can_trigger_sonosuite). Reject = back to draft. |
| **releases/urls.py** | Routes: `releases/pending_approval/`, `releases/<id>/submit-for-approval/`, `releases/<id>/approve/`, `releases/bulk_approve/`, `releases/<id>/reject/`. |
| **releases/processor.py** | CSV export: `#catalog_number` = `#upc`, dates in `yyyy-mm-dd`, `#user_email` from creator or DEPLOYMENT_EMAIL. Temp CSV in temp dir (no CWD). |
| **releases/models.py** | Fields: `approval_status`, `sonosuite_operation_ids` (if not already in live). |
| **releases/migrations/** | Migration that adds `approval_status` and migration that adds `sonosuite_operation_ids` (names may differ: e.g. `0010_add_approval_status`, `0011_add_sonosuite_operation_ids` or `0013_add_release_approval_status`, `0014_add_sonosuite_operation_ids`). |

### 2. Templates

| File | What it does |
|------|----------------|
| **releases/templates/volt_preview_distribute_info.html** | Preview & Distribute: “Distribute this release” / “Submit for approval”, “Approve” / “Reject”, “Pending approval” / “Distributed”. Exports modal (sonosuite-results). |
| **releases/templates/volt_releases_base.html** | JS: `submit_preview_distribute()`, `approve_release()`, `reject_release()`. Modal message from `response.sonosuite.message`. Reload after success. Error handler shows server message. |
| **releases/templates/volt_releases.html** | “Approve Releases” button (only on Pending for Approval tab). `approveSelectedReleases()`: POST selected rows to `releases/bulk_approve/`, show result, reload table. |

### 3. Main URL config (if needed)

| File | What to do |
|------|------------|
| **RoyaltyWebsite/urls.py** | Ensure `path("", include("releases.urls"))` is present and, if needed, listed **before** `include("main.urls")` so `/releases/...` is matched. |

### 4. Optional – management commands & docs

| File | What it does |
|------|----------------|
| **releases/management/commands/sonosuite_deliver.py** | `python manage.py sonosuite_deliver UPC [UPC ...]` for manual delivery. |
| **CONFIGURE_SONOSUITE.md** | How to set SONOSUITE_ADMIN_EMAIL, SONOSUITE_ADMIN_PASSWORD, SONOSUITE_API_BASE_URL. |
| **DISTRIBUTE_CSV_AND_UPLOAD.md** | Flow: Distribute → pending, ingest via platform, Approve → delivery. CSV export notes. |
| **SONOSUITE_WHAT_IS_LEFT_AND_QUESTIONS.md** | What’s done, what to ask Sonosuite (bulk CSV details). |
| **EMAIL_REPLY_TO_SONOSUITE_BULK_CSV.md** | Draft email to Sonosuite for bulk CSV ingestion. |

---

## What you need on the live server (env)

- **SONOSUITE_ADMIN_EMAIL** – Admin login for coin.sonosuite.com  
- **SONOSUITE_ADMIN_PASSWORD** – Admin password  
- **SONOSUITE_API_BASE_URL** – Optional; default `https://coin.sonosuite.com`

Without these, “Approve” / “Approve Releases” will show “delivery is not configured”.

---

## Summary of behaviour being pushed

1. **Distribute (user or admin)**  
   Sets release to “pending approval”. Message: ingest via platform (bulk CSV or UI), then Approve. No API upload (no ingestion endpoint).

2. **Pending for Approval page**  
   `GET /releases/pending_approval/` – list of pending releases; “Download Selected” (CSV); **“Approve Releases”** (bulk approve selected rows).

3. **Approve (single)**  
   From a release’s Preview & Distribute: admin clicks “Approve” → assign UPC/ISRC if needed → call Sonosuite delivery API → set approved/published.

4. **Approve (bulk)**  
   On Pending for Approval: select rows → “Approve Releases” → same as single approve for each selected release; response shows approved count and per-release errors.

5. **Reject**  
   Admin clicks “Reject” → release goes back to draft (unpublish), can be re-submitted.

6. **Delivery API**  
   Login → get DSP list → POST delivery per DSP with release UPC (coin.sonosuite.com).

---

## What I will do when you confirm

1. Copy/sync the files listed above from **live_code_complete_20260123_/django-docker-compose/RoyaltyWebsite** into your **live** project (you tell me the path, e.g. `Coin Digital for API/django-docker-compose/RoyaltyWebsite`).
2. Add any missing URL routes in live’s **releases/urls.py** (submit-for-approval, approve, bulk_approve, reject) if not already there.
3. Ensure **RoyaltyWebsite/urls.py** includes releases and order is correct.
4. Leave migrations as-is in live; you run `python manage.py migrate` on the server after deploy.

Reply with **“Confirm, push to live”** and the **exact path to your live website project** (the folder that contains `releases/`, `main/`, `RoyaltyWebsite/urls.py`). Then I’ll apply the changes.
