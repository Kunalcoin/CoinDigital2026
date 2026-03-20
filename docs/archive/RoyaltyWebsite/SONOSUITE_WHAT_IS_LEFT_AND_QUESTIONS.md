# What’s Left to Achieve Our Goal & What to Ask Sonosuite

## Sonosuite’s response (summary)

The Distribution API **does not provide endpoints for content ingestion or updates**. Releases must be ingested first using one of:

- **Bulk upload via CSV** (ingestion only)
- **Content ingestion via DDEX** (ingestion only)
- **Platform UI** (ingestion and updates)

Once content is in the system, it can be delivered through the Distribution API as expected.

---

## Our goal (summary)

1. **User** clicks **Distribute** → release goes to “pending approval”; admin is responsible for ingesting it (bulk CSV or Platform UI).
2. **Admin** ingests the release via the platform (CSV or UI), then clicks **Approve** in our app → we call the Distribution API to trigger delivery to stores.
3. If delivery fails, we show a clear error; the release is not marked as distributed.

---

## What we’ve done (in our app)

- **Distribute flow:** User/admin clicks Distribute → we set the release to **pending approval** (no API upload, as there is no ingestion endpoint). Success message tells admin to ingest via the platform (bulk CSV or UI) and to use “Download Selected” on Pending for Approval to get the metadata CSV.
- **Approve flow:** Admin clicks Approve → we call your **delivery** API (login + get DSP list + POST delivery per DSP with the release UPC). Same base URL and credentials.
- **Reject:** Admin can reject; release goes back to draft and can be re-submitted.
- **CSV export:** We generate a metadata CSV (Download Selected on Pending for Approval) with columns aligned to a standard template (#title, #upc, #catalog_number, dates, #user_email, audio/cover URLs, etc.) for use in bulk CSV upload or manual entry.

---

## What’s left / what we need from Sonosuite

1. **Bulk CSV ingestion details**  
   We want to use “bulk upload via CSV” where possible. We need:
   - How to perform it (Platform UI only, or any programmatic way?).
   - If UI: exact URL/path and steps.
   - CSV template/spec (columns, encoding) so our export matches.
   - Typical time until the release is available for delivery after upload.

2. **Optional: confirm delivery API**  
   We use login → GET dsp → POST delivery per DSP. If anything differs, we need the correct spec.

---

## Reply email to Sonosuite (bulk CSV details)

See **EMAIL_REPLY_TO_SONOSUITE_BULK_CSV.md** for a ready-to-send reply asking for:

- How to perform bulk CSV upload (UI only or programmatic).
- If UI: URL and steps.
- CSV template/spec.
- Typical time until release is available for delivery.
