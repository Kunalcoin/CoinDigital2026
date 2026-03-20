# Apple Music Delivery via Merlin Bridge (In-House)

Apple Music is delivered through **Merlin Bridge**. With the account reverted to in-house, delivery uses **SFTP with SSH-RSA key authentication** (no password). This doc describes what you need to do in the Bridge dashboard and what the app needs to deliver.

---

## 1. What You Need to Do in Merlin Bridge

### 1.1 Provide a public SSH key (required)

- In the **Bridge dashboard** go to **Settings** → **Manage SSH Keys**.
- Add a **public** SSH key. Merlin require it to be **SSH-RSA**.
- **Do not** upload your private key anywhere; only the **public** key goes to Bridge.

**If you don’t have an SSH-RSA key yet:**

```bash
# Generate SSH-RSA key pair (e.g. for Merlin Bridge only)
ssh-keygen -t rsa -b 4096 -f ~/.ssh/merlin_bridge_rsa -C "merlin-bridge-apple"
# No passphrase is easier for automation; use a passphrase if you prefer (see 2.2 below).
```

- Copy the **contents of the public key** (e.g. `~/.ssh/merlin_bridge_rsa.pub`) and paste it in Bridge → Settings → Manage SSH Keys.
- The **private key** (e.g. `~/.ssh/merlin_bridge_rsa`) will be used by the app for SFTP (see env vars below).

### 1.2 Get SFTP credentials

- In the **Bridge dashboard** go to **Settings** → **Content Delivery Info**.
- Note: **Host**, **Port**, **Username**. (No password — authentication is by SSH key.)
- **Coin Digital** values (Merlin only provides these; no upload path is specified):
  - **Host:** `content.bridge.merlinnetwork.org`
  - **Port:** `22`
  - **User:** `Coin_Digital_Private_Limited-Kunalkansalca@gmail.com`

### 1.3 Apple test checklist

- In the **Bridge dashboard** go to the **Checklist** tab.
- Follow the **Apple checklist** for test packages (e.g. test release types, metadata, assets). The app will build DDEX (ERN 4.3) for Apple Music and upload via SFTP; you run and confirm test deliveries from the checklist in Bridge.

---

## 2. What the App Needs (Environment / Config)

Set these in your `.env` (or server environment). **Do not commit private keys to git.**

| Variable | Description | Example |
|----------|-------------|--------|
| `MERLIN_BRIDGE_SFTP_HOST` | SFTP host from Bridge → Content Delivery Info | `content.bridge.merlinnetwork.org` |
| `MERLIN_BRIDGE_SFTP_PORT` | SFTP port (optional, default 22) | `22` |
| `MERLIN_BRIDGE_SFTP_USERNAME` | SFTP username from Content Delivery Info | `Coin_Digital_Private_Limited-Kunalkansalca@gmail.com` |
| `MERLIN_BRIDGE_SFTP_PRIVATE_KEY_PATH` | **Either** path to the private key file (recommended) | `/path/to/merlin_bridge_rsa` |
| `MERLIN_BRIDGE_SFTP_PRIVATE_KEY` | **Or** full PEM content of the private key (e.g. for Docker secrets) | `-----BEGIN OPENSSH PRIVATE KEY-----...` |

- You must set **either** `MERLIN_BRIDGE_SFTP_PRIVATE_KEY_PATH` **or** `MERLIN_BRIDGE_SFTP_PRIVATE_KEY`, not both. Path is easier on a server with a mounted key file.
- The key must be **RSA** (SSH-RSA). If you use an Ed25519 key, Bridge will not accept it; generate an RSA key as in 1.1.

**Upload path (required for packages to appear in Bridge):**

| Variable | Description | Value (per Merlin) |
|----------|-------------|--------------------|
| `MERLIN_BRIDGE_SFTP_REMOTE_PATH` | Base directory on SFTP. We upload a single final package file to `{REMOTE_PATH}/{upc}.itmsp.zip` (e.g. `apple/regular/8905285306132.itmsp.zip`). Bridge expects the **.itmsp.zip** final filename. | **`apple/regular`** for normal delivery. Use **`apple/priority`** for urgent/street-date; **`apple/backlog`** for large catalog. |

Set in `coin.env` or `.env`:

```bash
MERLIN_BRIDGE_SFTP_REMOTE_PATH=apple/regular
```

**Optional:**

| Variable | Description | Default |
|----------|-------------|--------|
| `MERLIN_BRIDGE_SFTP_KEY_PASSPHRASE` | **Required if your private key is encrypted.** Passphrase for the key. Prefer setting in `.env` (not committed). | (none) |
| `MERLIN_BRIDGE_S3_CONNECT_TIMEOUT` | Seconds to wait when opening the TCP connection to S3. | `30` |
| `MERLIN_BRIDGE_S3_READ_TIMEOUT` | Seconds between socket reads while downloading an object (not total transfer time). Raise if you see read timeouts on slow networks; full WAV pulls can take many minutes. | `600` |

**If you see "Invalid SSH key or passphrase: private key file is encrypted":** your key has a passphrase. Set `MERLIN_BRIDGE_SFTP_KEY_PASSPHRASE` in `.env` (or your env) to the key’s passphrase and restart the app. Do not commit the passphrase to git.

**Delivery looks “stuck” on `Fetching track 1/9 from S3`:** Full Apple delivery downloads every audio file into memory before SFTP. Large WAV/FLAC files (100–500+ MB each) can take **5–20+ minutes per track** on a slow or long-distance link. The command now logs **progress about every 10 MB** and uses a **600s read timeout** by default. If it still times out, set `MERLIN_BRIDGE_S3_READ_TIMEOUT=1200` (or higher) in `.env`. For metadata-only updates after an initial delivery, use `deliver_apple_music --metadata-only` (no full audio re-download).

**Including Apple Music in delivery**

- Add `apple_music` to `DELIVERY_STORES` in `.env`, e.g.:  
  `DELIVERY_STORES=audiomack,gaana,tiktok,apple_music`
- When you’re ready to deliver to Apple Music, set `apple_music` to `is_active: true` in `releases/data/ddex_dsps.json` (and set the correct Party ID when Merlin/Apple provide it).

---

## 3. How Delivery Works in This Repo

- **Format:** The app uses **Apple iTunes Importer (music5.3)** XML for Merlin Bridge (same format as your current provider). **Not DDEX** for Apple Music via Bridge.
- **Build:** `releases/apple_itunes_importer.py` builds the metadata XML from your Release/Track/Artist/Label data.
- **Upload:** `releases/merlin_bridge_delivery.py` fetches cover and audio from S3, builds the metadata XML, packages into the required **final** upload file `{upc}.itmsp.zip`, and uploads to Merlin Bridge SFTP.
  - Inside `{upc}.itmsp.zip` there is a top-level directory `{upc}.itmsp/` containing:
    - **`metadata.xml`** (required name; inside `{upc}.itmsp/`)
    - **`{upc}.jpg`** (artwork)
    - **`{upc}_01_001.wav`** (and further tracks as needed; `.flac` if that’s what you store).
    - **Dolby Atmos (optional):** **`{upc}_01_001_atmos.wav`** … one BWF ADM master per track that has Atmos enabled (see below).
- **Merlin paths (per Bridge team):** Set `MERLIN_BRIDGE_SFTP_REMOTE_PATH=apple/regular` for normal delivery; `apple/priority` for urgent/street-date; `apple/backlog` for large catalog.

### Per-user Dolby Atmos (gated)

- **Who can deliver Atmos:** Only releases whose **`created_by`** user has **`apple_music_dolby_atmos_enabled`** set to true on **`CDUser`**. Admins toggle this in **Manage users → Edit user** (same area as split royalties) or when **creating** a normal user (checkbox on add-user form), or via Django admin on the user.
- **Track fields (Django admin → Track, or admin UI if exposed):**
  - **`apple_music_dolby_atmos_url`** — S3/HTTPS URL to the **BWF ADM** `.wav` (24-bit LPCM @ 48 kHz per Apple).
  - **`apple_music_dolby_atmos_isrc`** — **Secondary ISRC** for the immersive mix (letters/digits only in XML; required by Apple on the object-based `data_file`).
- **Metadata:** When the above are present and the file is included in the package, `metadata.xml` uses an **`<assets><asset type="full">`** block with **`audio.2_0`** (stereo) and **`audio.object_based`** (Dolby Atmos), per **Apple Music Specification 5.3** (immersive audio). If the user flag is off, stereo-only **`<audio_file>`** is emitted as before.
- **Metadata-only updates:** If checksums for stereo/Atmos files are unchanged, Bridge may accept metadata-only packages without re-uploading binaries (same as stereo-only behavior).
- **Admin flow:** When admin approves a release and Apple Music is in `DELIVERY_STORES`, the app delivers the Apple-format package to Bridge SFTP.
- **Takedown:** On **Preview & Distribute**, admin can click **Takedown from Apple Music only** to send a DDEX PurgeReleaseMessage to Merlin Bridge SFTP at `{base_path}/takedown/{upc}_PurgeRelease.xml`. The same takedown is also sent when a user submits a **Takedown Request** (with Audiomack and Gaana).

### Merlin checklist: Streaming only vs Retail only

On each **Release** in Django admin, set **Apple Music commercial model** (under *License & Pricing*):

| Setting | XML effect | Use for checklist |
|--------|------------|-------------------|
| **Streaming + download (default)** | `cleared_for_sale` and `cleared_for_stream` both true | Normal catalog |
| **Streaming only** | Sale false, stream true (+ `stream_start_date`) | **Streaming Only Delivery** |
| **Retail / download only (no streaming)** | Sale true, stream false (+ `sales_start_date`, price tier) | **Retail Only Delivery** |

Use **one release/UPC** for the streaming-only test and **another release/UPC** for the retail-only test. Current Coin Digital checklist pair (set in admin under **License — Apple Music (Merlin Bridge)**):

| UPC | Commercial model |
|-----|------------------|
| `8905285306446` | Streaming only |
| `8905285306453` | Retail / download only |

Then run full `deliver_apple_music` for each. After the checklist passes, set both releases back to **Streaming + download (default)** if you want standard distribution.

**Do not set Apple Music pre-order on the retail-only UPC** (`8905285306453`). Apple returns **ITMS-4020** (“Preorder date is not allowed on this offer”) for pre-order metadata on a download-only / retail-only product. Use **Streaming + download (default)** (or streaming-only) for pre-order + instant grat; keep retail-only releases **without** a pre-order date.

### Merlin checklist: Preorder delivery

1. In Django admin, open the release → **License — Apple Music (Merlin Bridge)** → set **Apple Music pre-order sales start date** to a date **before** **Digital release date** (street date) and **still in the future** on the day you upload (e.g. pre-order opens next week, digital release next month).
2. Run full `deliver_apple_music --upc …`. The metadata includes `<preorder_sales_start_date>` on the **album** `<product>` only (not on track `<product>` — Apple ITMS-4020 if placed on track offers). **Retail/download-only** commercial model cannot carry pre-order dates; delivery will fail validation if both are set.
3. After Bridge validates the checklist, clear the pre-order date (leave empty) and re-deliver if you no longer want pre-order on that UPC.

**Why Bridge still shows an old “Release Date” (e.g. 17 Mar):** The dashboard reflects the **dates in the last package we uploaded** (`metadata.xml`). We set **album and track** `original_release_date`, plus `sales_start_date` / `stream_start_date` in `<product>`, from Django **`Digital release date`** (if set), otherwise **`Original release date`**. Editing the date **only** in the Merlin Bridge UI does **not** change what Apple gets—the next successful **`deliver_apple_music`** from Coin Digital overwrites it.

**Pre-order 21 Mar example:** Pre-order **must open before** the street date. If **Apple Music pre-order sales start date** = `2026-03-21`, then **Digital release date** must be **after** 21 March (e.g. `2026-03-28`). A street date of **17 March** with pre-order **21 March** is invalid; the delivery command will **refuse to upload** and tell you to fix Django.

### Merlin checklist: Instant Grat Delivery

During a pre-order, Apple expects each track to include **`<preorder_type>` on the `<track>` element** (not inside `<product>`). Values: **`instant-gratification`** for IG tracks, **`standard`** for the rest (see Apple Music Specification — Pre-Orders / instant gratification). Putting `<preorder_type>` inside track `<product>` triggers schema errors (“element not expected”).

1. In Django admin, mark **Apple Music instant gratification (pre-order)** on the IG tracks. **At most half** of the tracks may be IG; delivery is blocked if you exceed that.
2. **Pre-order date** is on the **album** `<product>` as `<preorder_sales_start_date>` (when commercial model is not retail-only).
3. Run **`deliver_apple_music --upc …`**; `metadata.xml` will include the track-level `<preorder_type>` values above.

**Manual test (one release):**

```bash
python manage.py build_ddex_all <release_id> --output ddex_output
# Then trigger delivery for apple_music from the admin “Preview & Distribute” (or equivalent) for that release.
```

Or call the delivery function for `apple_music` for a given release so the package is built and uploaded to Merlin Bridge; then use the **Checklist** tab in Bridge to confirm the test package with Apple.

---

## 3b. Current flow vs “files stay in S3” (like your current partner)

**Current flow (this repo):** Artwork and audio are stored in your S3. On delivery we **download from S3 → our server → upload to Merlin Bridge SFTP**. So files are copied to Bridge. Delivery time: ~30–90 seconds in production (fast S3 + SFTP from the live server).

**Partner-style flow (“files stay in S3”):** Artwork and audio stay in S3. You send only **metadata (e.g. XML) plus URLs or access** so the aggregator **pulls** the files from S3. Your server does no file transfer; the aggregator fetches. That’s why it can feel like ~10 seconds (you only submit metadata).

To do the same we would need **Merlin Bridge (or Apple) to support “content in S3” or “pull from URL”**, for example:

- We build the Apple iTunes Importer XML with **file names, size, and MD5** (size/MD5 can come from S3 `HeadObject` and `ETag` without downloading the full file in many cases).
- We send **only the XML** to Bridge (e.g. upload just the XML to SFTP, or submit via an API).
- We give Bridge **pre-signed S3 URLs** (or IAM / bucket access) for the artwork and audio files; **they** download from S3.

**Next step:** Check with Merlin Bridge (or their docs) whether they support:
- “Content via URL” or “ingest from S3 / pre-signed URL”, or  
- An API that accepts metadata + URLs instead of receiving the actual files on SFTP.

If they do, we can add a **delivery mode** that keeps files in S3 and only sends metadata + URLs (and optionally only uploads the XML to SFTP). If they only accept files on SFTP, the current “download from S3 then upload to SFTP” flow stays.

---

## 4. Checklist Summary

- [ ] Generate or have an **SSH-RSA** key pair; add the **public** key in Bridge → Settings → Manage SSH Keys.
- [ ] In Bridge → Settings → Content Delivery Info, note **Host**, **Port**, **Username**.
- [ ] Set `MERLIN_BRIDGE_SFTP_HOST`, `MERLIN_BRIDGE_SFTP_PORT`, `MERLIN_BRIDGE_SFTP_USERNAME`, and either `MERLIN_BRIDGE_SFTP_PRIVATE_KEY_PATH` or `MERLIN_BRIDGE_SFTP_PRIVATE_KEY` in `.env`.
- [ ] Set **`MERLIN_BRIDGE_SFTP_REMOTE_PATH=apple/regular`** (required; use `apple/priority` or `apple/backlog` if needed).
- [ ] Add `apple_music` to `DELIVERY_STORES` when you want to deliver to Apple Music.
- [ ] Run test deliveries per the **Apple checklist** in the Bridge dashboard (Checklist tab); see Apple Member Guide for testing.

---

## 5. "Delivered via SFTP" but package not visible in Bridge (resolved)

**Per Merlin (Bridge team):**

- **Upload path:** Set `MERLIN_BRIDGE_SFTP_REMOTE_PATH=apple/regular` for normal delivery. Use `apple/priority` for urgent/street-date, or `apple/backlog` for large catalog.
  - We upload the final file `{path}/{upc}.itmsp.zip` (e.g. `apple/regular/8905285306132.itmsp.zip`).
- **Package contents:** `{upc}.itmsp.zip` is a zip that contains a top-level folder `{upc}.itmsp/` with **metadata.xml**, `{upc}.jpg`, and audio per Apple Music Spec 5.3.
- **Testing:** Use the **Checklist** tab in the Bridge UI; see the Apple Member Guide (page 11) for test delivery steps.

If you still don’t see the package, verify on SFTP that the file `apple/regular/{upc}.itmsp.zip` exists (Bridge expects the final .itmsp.zip filename).

---

## 6. "UPC not found" or content not showing in Bridge dashboard

Per the **Merlin Bridge Member Onboarding Guide**, content does **not** load by default on the Bridge Content page. Use these steps:

### 1. Search for the UPC
- On the Bridge dashboard (bridge.merlinnetwork.org), go to the **Content** / search page.
- In the search bar, enter the UPC: **8905285306132** (or use **Advanced search** and search by UPC).
- Try filtering by **label** or **delivery date** if you have many deliveries.

### 2. Check status (Received / Failed / Warning / Validated)
- If the package appears in search results, open it and check the **status**:
  - **Received** – Upload seen; not yet validated.
  - **Failed** – Bridge validation found errors. Click the package → open the latest delivery → check **Bridge Validation** or **DSP Feedback** for the error message (e.g. XML, missing asset, naming). Fix and re-deliver.
  - **Warning** – Package is still delivered to Apple; you may want to fix the warning for future deliveries.
  - **Validated** – Passed Bridge; then it goes to **Platform Delivery** (Queued → Verified → Delivered).

### 3. Test vs Live
- If your account is still in **test mode**, test deliveries show with a **two small gears** icon. Ensure you’re looking at the right view (test vs live).
- Until the **Apple checklist** is all green and you’ve clicked **Start Deliveries**, you are in test mode. Test deliveries may appear only when filters/search include test content.

### 4. Confirm the package is on SFTP
- Log in via SFTP (same host/user/key as the app) and confirm the **.itmsp package** exists:
  - **Path:** `apple/regular/8905285306132.itmsp`
  - The .itmsp file is a zip; it should contain folder `8905285306132/` with `metadata.xml`, `8905285306132.jpg`, and audio (e.g. `.wav` or `.flac`) inside.
- If the **file is missing** or in the **wrong path** (e.g. only `8905285306132.itmsp` at home, not under `apple/regular/`), set `MERLIN_BRIDGE_SFTP_REMOTE_PATH=apple/regular` in your env and **re-deliver** the release.

### 5. Re-deliver with correct path
- Ensure **coin.env** (or .env) has: `MERLIN_BRIDGE_SFTP_REMOTE_PATH=apple/regular`
- Restart the app if you changed env, then deliver again for UPC 8905285306132 (from Preview & Distribute → "Deliver to Apple Music only", or run `python manage.py deliver_apple_music --upc 8905285306132` with that env set).
- After upload, search again in Bridge for **8905285306132** and check the new delivery’s status and any validation errors.

### 6. Nothing shows up in Bridge at all (no row, no failed, nothing)
- **Set the path:** If `MERLIN_BRIDGE_SFTP_REMOTE_PATH` is not set, the file is uploaded to your SFTP **home directory**. Bridge may only scan specific folders. Set `MERLIN_BRIDGE_SFTP_REMOTE_PATH=apple/regular` in **coin.env** (or .env), then re-run delivery.
- **See what’s on SFTP:** Run `python manage.py list_merlin_bridge_sftp` (with env loaded). It lists `.`, `apple/`, `apple/regular/`, and `incoming/` so you can see (1) if the connection works, (2) where your files landed, (3) whether `apple/regular` exists. If your .zip/.itmsp files appear under a path but Bridge still shows nothing, the path Bridge scans may be different.
- **Confirm with Merlin:** Ask Merlin support: (1) **Which exact SFTP path does Bridge scan for Apple Music packages?** (e.g. `apple/regular`, `incoming`, or something else.) (2) Is there an ingestion delay? (3) Do they need a specific file extension or folder structure to trigger ingestion?

### 7. Package shows but Bridge says "incorrect file extension – add .itmsp"
We upload **both** `{upc}.itmsp` and `{upc}.zip` (same content) so the delivery appears in Bridge; their dashboard only lists when a file is present, and that triggers on the .zip. If Bridge then flags "use .itmsp extension", reply to the ticket: **"We upload the same package as both .itmsp and .zip to apple/regular/. The .itmsp file is at apple/regular/{upc}.itmsp. Please use the .itmsp file for processing. Can you confirm Bridge can be configured to ingest/list .itmsp files so we can stop uploading .zip?"**

---

## 8. Updating metadata, audio, or artwork (re-delivery)

There is **no separate "update" flow**. Each delivery builds a fresh package from:

- **Metadata:** Release and Track fields in the DB (title, artists, genre, date, label, copyright, explicit, etc.) and related artists.
- **Artwork:** The file at the release's **cover_art_url** (S3).
- **Audio:** Each track's **audio_track_url** or **audio_wav_url** (S3).

To change what goes to Apple Music:

| What to change | Where to change it | Then |
|----------------|--------------------|------|
| **Metadata** (title, artist, genre, date, label, etc.) | Edit the release/tracks/artists in the **Django admin** or your app UI and save. | Re-run the deliver command (same UPC). |
| **Artwork** | Replace the image in **S3** at the same key the release's `cover_art_url` points to, **or** update `cover_art_url` to a new S3 key and upload the new image there. | Re-run the deliver command. |
| **Audio** (replace a track's file) | Replace the file in **S3** at the same key the track's `audio_track_url` / `audio_wav_url` points to, **or** upload a new file to S3 and set that track's `audio_track_url` / `audio_wav_url` to the new URL. | Re-run the deliver command. |

Re-delivery **overwrites** the previous package on Bridge (same `{upc}.itmsp.zip`). After you see "Upload complete", search for the UPC in Bridge; the latest delivery will reflect your changes (Bridge/Apple will process the new package).

### Metadata-only update (`--metadata-only`)

**Merlin Bridge often rejects metadata-only packages** with an error like *“Missing binaries stated in the metadata file”* (e.g. `{upc}.jpg`, `{upc}_01_001.wav`). In that case you **must** use a **full** delivery (no `--metadata-only`) so the zip contains metadata **and** all referenced assets.

For the **“Metadata Update Delivery”** checklist, a **full** `deliver_apple_music` after editing metadata in Django is usually correct: the new XML plus cover + audio are uploaded together.

Optional `--metadata-only` (XML-only zip, sizes/MD5 from S3) is only useful if Bridge explicitly accepts it for your account:

```bash
python manage.py deliver_apple_music --upc YOUR_UPC --metadata-only
```

---

## 9. Takedown format (Apple iTunes Importer, same as Sonosuite)

**We now use Apple iTunes Importer (music5.3) for takedown** (not DDEX): upload `{upc}.itmsp.zip` to the same path as delivery (e.g. apple/regular/), with only metadata.xml inside and `<cleared_for_sale>false</cleared_for_stream>false</cleared_for_stream>`. No tracks or artwork. This matches Sonosuite; Bridge shows the red Takedown status.

**PurgeReleaseMessage** is the DDEX (ERN 4.3) standard message for **removing a release** from a DSP. It tells the platform: “take down this release.”

- **Content:** A list of **release references** (e.g. `R_8905285306132`) that identify which release(s) to remove. No audio or artwork—just the instruction to purge.
- **We send:** One XML file per takedown: `{upc}_PurgeRelease.xml`, uploaded to Merlin Bridge SFTP at `{MERLIN_BRIDGE_SFTP_REMOTE_PATH}/takedown/{upc}_PurgeRelease.xml` (e.g. `apple/regular/takedown/8905285306132_PurgeRelease.xml`).

So when you run the takedown command, we build this DDEX “purge” message and upload it to Bridge; Apple/Merlin are expected to process it and remove that release from Apple Music.

---

## 10. Takedown uploaded but nothing shows in Bridge

If the takedown command succeeds (file uploaded to `apple/regular/takedown/{upc}_PurgeRelease.xml`) but **nothing appears in the Bridge dashboard** for takedown:

1. **Confirm the file is on SFTP**  
   Run:  
   `python manage.py list_merlin_bridge_sftp`  
   (and, if you have SFTP access, check that `apple/regular/takedown/` exists and contains your `*_PurgeRelease.xml` file).

2. **Bridge may not surface takedowns in the same place as deliveries**  
   Takedowns might be processed in the background and not show as a separate “delivery” in the Content list. The checklist item “Takedown Delivery” may be marked complete once Bridge has accepted/processed a takedown file, even if there is no separate takedown row in the UI.

3. **Path or format may differ from what we use**  
   We send a **DDEX** PurgeReleaseMessage. Bridge/Apple might expect:
   - A **different SFTP path** (e.g. `apple/takedown/` instead of `apple/regular/takedown/`, or a path Merlin specifies).
   - A **different format** (e.g. an Apple-specific takedown format rather than DDEX).

**Expected behaviour (reference):** When takedown is ingested correctly, Bridge shows the release in the content list with a red **Takedown** status tag (UPC, artist, title, original release date, and a takedown timestamp). This is how it appears when takedown is initiated from Sonosuite.

**What to do:** Ask **Merlin Bridge support** (or check their Apple Music / onboarding docs):

- **Which exact SFTP path should we use for Apple Music takedown files?** (e.g. `apple/regular/takedown/` or something else?)
- **Do you accept DDEX PurgeReleaseMessage XML for takedown, or do you require a different format?**
- **How does Sonosuite submit takedowns to Bridge?** (path, file naming, and format) so we can match it and have our takedowns show in the content list with the "Takedown" status like Sonosuite’s.
- **How do we confirm in Bridge that a takedown was received and processed?** (e.g. row with "Takedown" in the list, Checklist only, or a specific tab?)

Once they confirm the path and format (and, if possible, share how Sonosuite sends takedowns), we can adjust the upload path or the XML we generate so our takedowns appear the same way.
