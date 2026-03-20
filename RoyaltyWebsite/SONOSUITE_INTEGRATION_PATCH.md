# Sonosuite API Delivery — Integration Patch

This document lists **every file added or changed** for Sonosuite API delivery and the **approval workflow** (user requests delivery → admin approves and sends to Sonosuite). Use it to **undo** the integration by reverting or removing these changes.

---

## Approval workflow (user → admin → Sonosuite)

1. **User** (normal/intermediate): On Preview & Distribute, clicks **Submit for approval**. Release status becomes `pending_approval`.
2. **Admin** (or staff): Sees **Approve & send to Sonosuite** and **Reject**. Approve assigns UPC/ISRC if needed, calls Sonosuite API (all stores), saves operation IDs, sets release to approved and published. Reject sets status to `rejected` (user can resubmit later).
3. **Admin** can also **Distribute this release** directly when the release is still in draft (no approval step; same as before: publish + Sonosuite).

---

## After applying this patch

1. **Run the new migration:**
   ```bash
   cd django-docker-compose/RoyaltyWebsite
   python3 manage.py migrate releases
   ```
2. **Set Sonosuite credentials** in `.env` or `coin.env` (if you use it):
   ```env
   SONOSUITE_API_BASE_URL="https://coin.sonosuite.com"
   SONOSUITE_ADMIN_EMAIL="your-sonosuite-admin@email.com"
   SONOSUITE_ADMIN_PASSWORD="your-password"
   ```
3. Ensure `requests` is in your requirements (the Sonosuite client uses it).

---

## Summary of changes

- **New files:** Sonosuite client, management command, migration, optional scripts.
- **Modified files:** `releases/models.py` (one field), `releases/views.py` (Sonosuite call after publish, approval workflow views and context), `releases/urls.py` (submit/approve/reject routes), two templates (distribution block, Sonosuite results in modal/JS).
- **Approval workflow:** Submit-for-approval, approve, reject views and template block (user requests delivery → admin sends to Sonosuite).
- **Optional:** `deliver_sonosuite_upcs.sh`, `sonosuite_diagnose.py`, env vars in `coin.env` or `.env`.

---

## 1. New files (add these for integration; delete to undo)

| File | Purpose |
|------|---------|
| `releases/sonosuite_client.py` | Sonosuite API client (login, delivery, get DSPs). |
| `releases/management/__init__.py` | Empty; makes `management` a package. |
| `releases/management/commands/__init__.py` | Empty; makes `commands` a package. |
| `releases/management/commands/sonosuite_deliver.py` | Management command: `python3 manage.py sonosuite_deliver UPC1 UPC2 ...` |
| `releases/migrations/0011_add_sonosuite_operation_ids.py` | Adds `sonosuite_operation_ids` to Release. |
| `deliver_sonosuite_upcs.sh` | (Optional) Script to deliver a list of UPCs. |
| `sonosuite_diagnose.py` | (Optional) Diagnostic script for one UPC. |

**To undo:** Delete the above files. Then run a migration to remove the field (see “Reverting the migration” below).

---

## 2. Modified files (patches applied)

### 2.1 `releases/models.py`

**Change:** Add one field to the `Release` model (after `approval_status` or before `created_at`):

```python
sonosuite_operation_ids = models.TextField("Sonosuite operation IDs", blank=True, default="")
```

**To undo:** Remove that line from the `Release` class.

---

### 2.2 `releases/views.py` — approval workflow and Sonosuite

**Changes:**
- **GET `preview_distribute_info`:** Add to context: `approval_status`, `can_trigger_sonosuite`, `sonosuite_operation_ids`.
- **POST `preview_distribute_info`:** After publish, call Sonosuite and add `sonosuite` to the JSON response (see section 2.2a below).
- **New views:** `submit_for_approval(request, primary_uuid)`, `approve_release(request, primary_uuid)`, `reject_release(request, primary_uuid)` (with constants `PENDING_APPROVAL`, `APPROVED`, `REJECTED`, `DRAFT`).

**To undo:** Remove the approval block and Sonosuite block from POST response; remove the three view functions and the extra context keys from the GET render.

### 2.2a `releases/views.py` — `preview_distribute_info` (POST branch)

**Change:** After `_release.save()` and before `return JsonResponse(...)` in the POST block (after sending email and `os.remove(data_file_path)`):

1. Call Sonosuite and build the response payload:
   - Import: `from releases.sonosuite_client import send_release_to_sonosuite, is_sonosuite_configured`
   - If `is_sonosuite_configured()` and `_release.upc`: call `send_release_to_sonosuite(upc=_release.upc)`, optionally save `sonosuite_operation_ids` on `_release`, and add a `sonosuite` dict to the JSON (e.g. `success`, `operation_ids`, `error`).
   - Else: set `sonosuite` to `{"success": False, "operation_ids": [], "error": "..."}`.
2. In the `JsonResponse`, add a `sonosuite` key with that dict (and keep `message`, `success`).

**To undo:** Remove the Sonosuite block and the `sonosuite` key from the `JsonResponse`; restore the original `return JsonResponse({"message": "...", "success": "success"})`.

---

### 2.3 `releases/templates/volt_preview_distribute_info.html`

**Change:** Inside the modal body, after the line with “This export has been created.” and before `<br>`:

Add a block for Sonosuite results:

```html
<div id="sonosuite-results-modal" style="display:none; margin-top:12px; padding:12px; background:#e8f4fd; border:1px solid #0d6efd; border-radius:8px;">
    <strong>Sonosuite (all stores via API):</strong> <span id="sonosuite-results-text"></span>
</div>
```

**To undo:** Remove the Sonosuite results `<div>`. Remove the entire "Distribution & approval" block and the JS functions `getCSRFToken`, `submit_for_approval`, `approve_release`, `reject_release`. Restore the single "Distribute this release" button in the bottom button row if it was removed.

---

### 2.4 `releases/templates/volt_releases_base.html` — `submit_preview_distribute()`

**Change:** In the `.then()` callback:

1. Set loading off: `set_loading("#in_preview_dist_info_btn", false, ...)` (second call was `true`, change to `false`).
2. If `response.sonosuite`: fill `#sonosuite-results-text` and show `#sonosuite-results-modal`.
3. Add a `.fail()` handler that sets loading off and shows an error.

**To undo:** Revert the function to the original (single `set_loading(..., true, ...)`, no Sonosuite block, no `.fail()`).

---

## 3. Environment (optional)

**Change:** In `coin.env` or `.env`, add (commented or filled):

```env
# SONOSUITE_API_BASE_URL="https://coin.sonosuite.com"
# SONOSUITE_ADMIN_EMAIL="your-sonosuite-admin@email.com"
# SONOSUITE_ADMIN_PASSWORD="your-password"
```

**To undo:** Remove or comment out these three lines.

---

## 4. Reverting the migration

After removing the field from `releases/models.py` and deleting the new migration file:

1. Create a new migration that removes the field, e.g.:
   ```bash
   python3 manage.py makemigrations releases --name remove_sonosuite_operation_ids
   ```
   (Edit the generated migration if needed so it only drops `sonosuite_operation_ids`.)
2. Apply it: `python3 manage.py migrate releases`.

If you prefer to keep the migration file but reverse its effect, create an empty migration and use `migrations.RunPython(noop, noop)` or `migrations.RemoveField(...)` for `sonosuite_operation_ids`.

---

## 5. Quick undo checklist

1. Delete: `releases/sonosuite_client.py`, `releases/management/commands/sonosuite_deliver.py`, `releases/management/__init__.py`, `releases/management/commands/__init__.py`, `releases/migrations/0011_add_sonosuite_operation_ids.py`, `deliver_sonosuite_upcs.sh`, `sonosuite_diagnose.py`.
2. In `releases/models.py`: remove the `sonosuite_operation_ids` field.
3. In `releases/views.py`: remove the Sonosuite block and `sonosuite` from the publish `JsonResponse`; remove approval context from GET; remove `submit_for_approval`, `approve_release`, `reject_release` views and constants.
4. In `releases/urls.py`: remove the three routes (submit-for-approval, approve, reject).
5. In `volt_preview_distribute_info.html`: remove the Distribution & approval block, Sonosuite results `<div>`, and the JS for submit/approve/reject/getCSRFToken; restore the single "Distribute this release" button in the bottom row.
6. In `volt_releases_base.html`: revert `submit_preview_distribute()` to the original.
7. In env: remove the three Sonosuite variables.
8. Create and run a migration to drop `sonosuite_operation_ids` (see section 4).

---

*Generated for Sonosuite API delivery integration. Only delivery-related code is included; no other features (e.g. approve API, login page, DDEX) are part of this patch.*
