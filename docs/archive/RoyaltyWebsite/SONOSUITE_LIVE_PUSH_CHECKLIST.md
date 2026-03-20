# Sonosuite API — What to Push to Live Website

Use this checklist to deploy the Sonosuite API and approval workflow to your live site. All paths below are **relative to the RoyaltyWebsite folder** (project root).

---

## 1. The four features being pushed

| # | Feature | What it does |
|---|--------|----------------|
| **1** | **Pending for Approval** | Dashboard shows a "Pending for Approval" count and card (clickable). Sidebar has "Pending Approval" link. List page `/releases/pending_approval/` shows all releases waiting for admin approval. When any user clicks "Distribute", the release moves here. |
| **2** | **Approval and Rejection** | On a release’s Preview & Distribute page, admin sees "Approve" and "Reject" when the release is pending. **Approve** → publishes the release and sends it to Sonosuite (all stores via API). **Reject** → moves the release back to drafts (see #3). |
| **3** | **Rejected releases moved to Drafts** | When admin clicks "Reject", the release’s status is set back to draft (unpublished). It appears in the **Draft** list and can be edited and submitted for approval again. |
| **4** | **Bulk approving releases** | On the Pending for Approval list, admin can select multiple rows (checkboxes) and click **"Approve Releases"**. All selected releases are approved and sent to Sonosuite in one go. Results show how many succeeded and any errors. |

---

## 2. Complete list of files to push

### Releases app (Sonosuite + approval workflow)

| Path | Purpose |
|------|--------|
| `releases/sonosuite_client.py` | Sonosuite API client: login, delivery to DSPs, get DSPs. Uses env: SONOSUITE_API_BASE_URL, SONOSUITE_ADMIN_EMAIL, SONOSUITE_ADMIN_PASSWORD. |
| `releases/models.py` | Fields: `approval_status`, `sonosuite_operation_ids`. |
| `releases/views.py` | `pending_approval_releases`, `submit_for_approval`, `approve_release`, `reject_release`, `bulk_approve_releases`, `_approve_single_release`. GET preview_distribute_info: context `approval_status`, `can_trigger_sonosuite`, `sonosuite_operation_ids`. POST preview_distribute_info: after publish, optional Sonosuite call. `releases_paginated`: filter for `request_type == "pending_approval"`. |
| `releases/urls.py` | Routes: `releases/pending_approval/`, `releases/<uuid>/submit-for-approval/`, `releases/<uuid>/approve/`, `releases/bulk_approve/`, `releases/<uuid>/reject/`. |
| `releases/migrations/0010_add_approval_status_to_release.py` | Adds `approval_status` to Release. |
| `releases/migrations/0011_add_sonosuite_operation_ids.py` | Adds `sonosuite_operation_ids` to Release. |
| `releases/management/__init__.py` | Package marker. |
| `releases/management/commands/__init__.py` | Package marker. |
| `releases/management/commands/sonosuite_deliver.py` | Management command: `python manage.py sonosuite_deliver UPC1 UPC2 ...`. |
| `releases/management/commands/set_pending_approval.py` | Management command: set releases by UPC to pending approval (e.g. `--file upcs.txt`). |
| `releases/templates/volt_preview_distribute_info.html` | Distribute / Approve / Reject / Pending / Distributed buttons next to Delete; Sonosuite results in modal; JS: submit_for_approval, approve_release, reject_release, getCSRFToken. |
| `releases/templates/volt_releases.html` | Pending for Approval title and "Approve Releases" button; `approveSelectedReleases()` calling `/releases/bulk_approve/`. |
| `releases/templates/volt_releases_base.html` | JS: submit_preview_distribute() shows Sonosuite result in modal; .fail() handler. |

### Main app (dashboard + sidebar)

| Path | Purpose |
|------|--------|
| `main/views.py` | `get_dashboard`: adds `pending_approval_count` (releases with `approval_status='pending_approval'`, `published=False`). |
| `main/templates/volt_dashboard.html` | Fourth summary card: "Pending for Approval" with count, linked to `/releases/pending_approval/`. |
| `main/templates/volt_base.html` | Sidebar: "Pending Approval" link (`/releases/pending_approval/`) and updated Draft active state (exclude pending_approval). (All 4 sidebar variants.) |

### Optional (scripts / docs)

| Path | Purpose |
|------|--------|
| `deliver_sonosuite_upcs.sh` | Optional shell script to run sonosuite_deliver for a list of UPCs. |
| `sonosuite_diagnose.py` | Optional diagnostic script for one UPC. |
| `upcs_to_pending_approval.txt` | Optional: list of UPCs for `set_pending_approval --file`. |
| `SONOSUITE_INTEGRATION_PATCH.md` | Full integration + undo instructions. |

---

## 3. On the live server after pushing code

1. **Run migrations**
   ```bash
   cd /path/to/RoyaltyWebsite
   python3 manage.py migrate releases
   ```
   This applies `0010_add_approval_status_to_release` and `0011_add_sonosuite_operation_ids` if not already applied.

2. **Set environment variables** (e.g. in `.env` or `coin.env`)
   ```env
   SONOSUITE_API_BASE_URL="https://coin.sonosuite.com"
   SONOSUITE_ADMIN_EMAIL="your-sonosuite-admin@email.com"
   SONOSUITE_ADMIN_PASSWORD="your-password"
   ```
   Without these, Approve / Approve Releases will report that delivery is not configured.

3. **Restart the app** (e.g. gunicorn/uWSGI or Docker) so new code and env are loaded.

4. **Optional:** To move existing UPCs into Pending for Approval (e.g. ones already “distributed” on the old flow):
   ```bash
   python3 manage.py set_pending_approval --file upcs_to_pending_approval.txt
   ```

---

## 4. Quick reference — URLs added

| URL | Method | Purpose |
|-----|--------|--------|
| `/releases/pending_approval/` | GET | List of releases pending approval. |
| `/releases/<primary_uuid>/submit-for-approval/` | POST | User “Distribute” → set release to pending approval. |
| `/releases/<primary_uuid>/approve/` | POST | Admin single approve → publish + Sonosuite API. |
| `/releases/bulk_approve/` | POST | Admin bulk approve (body: `selectedRows[]` = list of release primary UUIDs). |
| `/releases/<primary_uuid>/reject/` | POST | Admin reject → release back to draft. |

---

## 5. Summary

- **Pending for Approval** = dashboard card + sidebar + list page + count.
- **Approval and Rejection** = single Approve/Reject on release page; backend sends to Sonosuite on Approve.
- **Rejected → Drafts** = Reject sets `approval_status` to draft and unpublishes; release appears in Draft list.
- **Bulk approve** = Pending for Approval list → select rows → “Approve Releases” → bulk approve and send to Sonosuite.

Push the files in **Section 2**, run **Section 3** on the server, and the live site will have all four Sonosuite API–related features.
