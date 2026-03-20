# Audiomack DDEX 4.3 – Test run (Insert, Update, Takedown)

Use this to test the Audiomack feed with three scenarios. All commands assume you are in the project root and have run migrations. S3 delivery is already set up (`audiomack-contentimport/coin-digital/...`); upload the generated XML (and assets) using your existing process.

---

## What’s in place

| Item | Status |
|------|--------|
| **Insert** (NewReleaseMessage, UpdateIndicator OriginalMessage) | ✅ `build_ddex <id> --store audiomack` |
| **Update** (NewReleaseMessage, UpdateIndicator UpdateMessage, LinkedMessageId) | ✅ `build_ddex <id> --action update --store audiomack --original-message-id <id>` |
| **Takedown** (NewReleaseMessage, UpdateIndicator UpdateMessage, ValidityPeriod EndDate) | ✅ `build_ddex <id> --action takedown --store audiomack` |
| Audiomack Artist ID in PartyList | ✅ When `Artist.audiomack_id` is set |
| Deal terms | OnDemandStream + NonInteractiveStream, AdvertisementSupported + Subscription |
| ERN 4.3 | ✅ Accepted by Audiomack |

**Image:** Audiomack prefer PNG; ensure cover art reference in the ERN points to a PNG when possible (e.g. in the resources folder for the batch).

---

## Test 1: Insert only (1 release)

1. Pick a release ID (e.g. `123`) that is approved and has UPC, tracks, cover art, and audio.
2. Generate Insert XML:
   ```bash
   cd RoyaltyWebsite
   python manage.py build_ddex 123 --store audiomack --output out_audiomack/insert_release/123.xml
   ```
3. **Capture the MessageId** from the generated XML (inside `<MessageHeader><MessageId>...</MessageId>`). You need it for Test 2 (Update).
4. Upload `out_audiomack/insert_release/123.xml` (and any referenced resources) to your Audiomack S3 path using your existing process.

---

## Test 2: Insert then Update (1 release)

1. **Insert** (same as Test 1):
   ```bash
   python manage.py build_ddex 124 --store audiomack --output out_audiomack/release_124/124_insert.xml
   ```
   Open `124_insert.xml`, copy the **MessageId** (e.g. `a1b2c3d4e5...`).

2. Change something on the release in the UI (e.g. title, artist, or release date) and save.

3. **Update** (use the MessageId from step 1):
   ```bash
   python manage.py build_ddex 124 --action update --store audiomack --original-message-id <PASTE_MESSAGE_ID_HERE> --output out_audiomack/release_124/124_update.xml
   ```
4. Upload both `124_insert.xml` and `124_update.xml` (in that order) to S3, or only the update if the insert was already delivered.

---

## Test 3: Insert → Update → Takedown (1 release)

1. **Insert:**
   ```bash
   python manage.py build_ddex 125 --store audiomack --output out_audiomack/release_125/125_insert.xml
   ```
   Copy the **MessageId** from the XML.

2. **Update** (after making a change to the release):
   ```bash
   python manage.py build_ddex 125 --action update --store audiomack --original-message-id <MESSAGE_ID> --output out_audiomack/release_125/125_update.xml
   ```

3. **Takedown** (NewReleaseMessage with UpdateMessage and ValidityPeriod EndDate; default end date = today):
   ```bash
   python manage.py build_ddex 125 --action takedown --store audiomack --output out_audiomack/release_125/125_takedown.xml
   ```
   Optional: set a specific end date:
   ```bash
   python manage.py build_ddex 125 --action takedown --store audiomack --takedown-end-date 2026-02-20 --output out_audiomack/release_125/125_takedown.xml
   ```

4. Upload insert, then update, then takedown to S3 in that order (or only the messages you haven’t yet delivered).

---

## Quick reference

| Scenario | Command |
|---------|--------|
| **Insert** | `python manage.py build_ddex <release_id> --store audiomack -o path/<upc>.xml` |
| **Update** | `python manage.py build_ddex <release_id> --action update --store audiomack --original-message-id <MessageId from insert> -o path/<upc>_update.xml` |
| **Takedown** | `python manage.py build_ddex <release_id> --action takedown --store audiomack [-o path/<upc>_takedown.xml] [--takedown-end-date YYYY-MM-DD]` |

- **MessageId** is in the Insert XML: `<MessageHeader><MessageId>...</MessageId></MessageHeader>`.
- Batch complete: if you use batch folders, add `BatchComplete_{delivery_name}.xml` (empty) in the Level 2 folder as recommended by Audiomack.
