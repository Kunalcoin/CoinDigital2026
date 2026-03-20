# DDEX Package-First Architecture (Scalable to 40+ DSPs)

## Why this approach

**Current flow:** On "Distribute", we build DDEX XML per store, read assets from release S3, and upload to each DSP. That means:
- XML is rebuilt every time you distribute (or per store).
- Each store has custom code (audiomack_delivery.py, gaana_delivery.py, tiktok_delivery.py).
- Adding a new DSP = new module + new logic. Hard to scale to 40 DSPs.

**Better flow (package-first):**
1. **Once per release:** Build one canonical DDEX package (ERN 4.3 XML + cover + audio) and **save it in our S3**.
2. **On distribute:** For each configured DSP, **send that existing package** to the DSP (S3 or SFTP) according to their config. No per-DSP XML building unless the DSP needs a variant (e.g. TikTok with MD5).

Benefits:
- Single source of truth: one package per release in S3.
- Add a new DSP = add config (destination type + credentials); distribution is "push package to endpoint".
- Retry any DSP without rebuilding. Audit trail: package is stored.
- Scales to 40 DSPs with one distribution loop + one adapter per transport (S3, SFTP).

---

## When to create the package and distribute

| Option | When | Pros | Cons |
|--------|------|------|------|
| **A. On upload** | When user uploads release / assets | Package ready early | Metadata may change; need to rebuild on approval anyway |
| **B. On submit for approval** ✓ | When user submits for approval | Package ready for admin; distribution only on approve; clear split of responsibilities | Builds for every submission (admin can still reject) |
| **C. On first distribute** | When admin first clicks "Distribute" | Build only when needed | Separate step from approval |
| **D. Explicit "Prepare package"** | Admin clicks "Prepare DDEX package" once | Can distribute many times from same package | Extra click |

**Recommended flow:**

1. **User:** Submits for approval (e.g. "Submit for approval") → at that moment the system **creates the DDEX package once** (XML + cover + audio) and saves it in our S3. Release status → **pending_approval**. Nothing is sent to any store yet.
2. **Admin:** Approves the release → at that moment the system **distributes** the existing package to **all** configured stores (Audiomack, Gaana, TikTok, etc.) via S3 or SFTP per store config. Release status → **approved**.

So: **package is created when the user submits for approval**; **distribution to all stores happens when the admin approves** (no build at approval time).

### Flow in short

| Step | Who | Action | What happens |
|------|-----|--------|--------------|
| 1 | User | Submits for approval | System **builds DDEX package** (XML + cover + audio) and **saves to S3**. Release status → **pending_approval**. No delivery to stores. |
| 2 | Admin | Approves release | System **distributes** the existing package from S3 to all configured stores (S3/SFTP per store). Release status → **approved**. |

Implementation hooks:
- **Package creation:** in `submit_for_approval` (or right after status is set to pending_approval), assign UPC/ISRC if needed (so the package is complete), then call "build DDEX package and save to S3".
- **Distribution:** in `approve_release` / `_approve_single_release`, call "distribute existing package to all DDEX stores" (read package from S3, send to each store). No package build at approval.

---

## S3 layout: canonical package

Store one package per release in **our** bucket (e.g. `coindigital-media`):

```
s3://<our-bucket>/ddex/packages/<release_id>/<upc>/
├── <upc>.xml             # canonical ERN 4.3 NewReleaseMessage
├── <upc>.json            # optional: metadata (upc, isrcs, resource_md5_map for TikTok, etc.)
└── resources/
    ├── coverart.jpg      # cover image (or .png)
    ├── 1_1.flac         # track 1
    ├── 1_2.flac         # track 2
    └── ...
```

- **<upc>.xml:** Standard ERN 4.3; same file can be sent to most DSPs.
- **resources/:** Actual files (cover + audio). URIs in the XML reference these relative paths (e.g. `resources/1_1.flac`).
- **<upc>.json (optional):** Store `resource_md5_map` (for TikTok), UPC, ISRCs, so we can generate store-specific XML without re-reading files.

Package is **self-contained**: distribution just uploads this folder to each DSP’s destination.

---

## When to build the package (concrete)

1. **UPC/ISRC:** Assign if not already (same as now).
2. **XML:** Build once with `build_new_release_message(release, store=None)` (generic ERN 4.3).
3. **Resources:** Copy/link cover and audio from release assets into `ddex/packages/<release_id>/<upc>/resources/`. Optionally compute and store MD5 for each file in `<upc>.json`.
4. **Upload to S3:** Write `<upc>.xml` and `resources/*` to our bucket at the path above.

Only one "package build" implementation; no store-specific logic at build time (except optionally precomputing MD5 for TikTok).

---

## Distribution: send package to each DSP

**Idea:** One registry entry per DSP with **delivery method** (S3 or SFTP) and **credentials/path**. Distribution = loop over DSPs and "send package to this DSP".

### Extend DSP config (e.g. in `ddex_dsps.json` or a separate `dsp_delivery.json`)

Keep Party ID / deal profile in `ddex_dsps.json`. Add **delivery** config (can be same file or separate):

```json
{
  "code": "audiomack",
  "delivery": {
    "method": "s3",
    "bucket_env": "AUDIOMACK_S3_BUCKET",
    "prefix_env": "AUDIOMACK_S3_PREFIX",
    "credentials": "default"
  }
},
{
  "code": "gaana",
  "delivery": {
    "method": "sftp",
    "host_env": "GAANA_SFTP_HOST",
    "port_env": "GAANA_SFTP_PORT",
    "username_env": "GAANA_SFTP_USERNAME",
    "password_env": "GAANA_SFTP_PASSWORD",
    "path_env": "GAANA_SFTP_REMOTE_PATH"
  }
},
{
  "code": "tiktok",
  "delivery": {
    "method": "s3",
    "bucket_env": "TIKTOK_S3_BUCKET",
    "prefix_env": "TIKTOK_S3_PREFIX",
    "credentials": "tiktok",
    "xml_variant": "md5"
  }
}
```

- **method:** `s3` | `sftp`.
- **\*_env:** Env var names (e.g. `GAANA_SFTP_HOST`); no secrets in JSON.
- **credentials:** `default` (use app AWS) or `tiktok` (use TIKTOK_AWS_*).
- **xml_variant:** Optional. `md5` = for this DSP, generate XML that includes `<HashSum>` from manifest (or compute on the fly from package resources).

### Distribution loop (pseudo-code)

```
for each dsp in configured_dsps:
  package_path = s3://our-bucket/ddex/packages/<release_id>/<upc>/
  if dsp.delivery.xml_variant == "md5":
    xml = load_canonical_xml(package_path) + inject_md5_from_manifest_or_compute(package_path)
  else:
    xml = load_canonical_xml(package_path)

  if dsp.delivery.method == "s3":
    upload_to_dsp_s3(xml, package_path/resources/*, dsp.delivery)
  else if dsp.delivery.method == "sftp":
    upload_to_dsp_sftp(xml, package_path/resources/*, dsp.delivery)
```

- **S3 adapter:** Read package from our S3; upload XML + resources to DSP bucket/prefix (one client per credential set).
- **SFTP adapter:** Read package from our S3; upload same files to DSP SFTP path.

No store-specific "build DDEX" at distribute time; only optional XML variant (e.g. MD5) and one adapter per transport.

---

## Scaling to 40 DSPs

| Piece | How it scales |
|-------|----------------|
| **Package build** | One implementation. Runs once per release (on "Prepare" or first Distribute). |
| **DSP list** | Add 40 entries in registry with `delivery.method`, `delivery.*_env`, optional `xml_variant`. |
| **Distribution** | One loop: for each DSP, load package from S3, apply variant if needed, call S3 or SFTP adapter. |
| **New DSP** | Add one config block (method + env vars); no new Python module. |
| **Credentials** | All in env (or secrets manager); no secrets in code or JSON. |

Store-specific quirks (e.g. path format, batch ID) can be handled by:
- **Path template in config** (e.g. `prefix_env` + rule like "upload to prefix/{batch_id}/{upc}.xml"), or
- **Small per-DSP "formatter"** (e.g. TikTok batch_id) that stays in config or a tiny plugin map (dsp_code → formatter).

---

## Store audio formats (FLAC, MP3, WAV)

Many stores accept **FLAC** or **MP3**; some require **WAV**. The canonical package currently stores one format (e.g. FLAC as `1_1.flac`) in `resources/`. To support per-store formats later:

- **Option A:** Store one canonical format in the package (e.g. FLAC). For stores that require WAV or MP3, add a conversion step at distribution time (or pre-generate and store multiple files in the package, e.g. `resources/1_1.flac`, `resources/1_1.wav`).
- **Option B:** Add `preferred_format` (or `accepted_formats`) to the DSP delivery config in the registry. When distributing, if the store’s preferred format differs from the package’s, convert on the fly (e.g. FLAC → WAV) or pick the matching file if multiple formats are stored in the package.

For now the package uses the same format as the release’s uploaded audio (typically FLAC). When you add more stores, extend the registry with format preferences and implement conversion or multi-format storage as needed.

---

## Migration from current code

1. **Add package build:** New function (or management command) that builds canonical XML + copies resources to `s3://.../ddex/packages/<release_id>/<upc>/` and optionally writes `<upc>.json` with MD5.
2. **Add delivery config:** Extend `ddex_dsps.json` (or new file) with `delivery` per DSP.
3. **Add generic S3 sender:** Given package S3 path + DSP delivery config, upload package to DSP S3.
4. **Add generic SFTP sender:** Given package S3 path + DSP delivery config, download from our S3 and upload to DSP SFTP.
5. **TikTok variant:** When `xml_variant == "md5"`, generate XML with HashSum from package manifest or by reading resources from S3.
6. **"Prepare package" action:** Button or command that ensures package exists (build if missing).
7. **"Distribute" action:** For each configured DSP, send package using the right adapter. Replace or wrap current per-store delivery calls so the UI still shows "Distribute to Audiomack, Gaana, TikTok" and later "Distribute to 40 DSPs".
8. **Deprecate:** Over time, replace `audiomack_delivery.py` / `gaana_delivery.py` / `tiktok_delivery.py` with the generic adapters + config.

---

## Summary

- **Save DDEX XML + art + audio in S3 when the package is prepared** (on first distribute or on explicit "Prepare DDEX package"), not at upload time, so metadata is final.
- **Distribution = send that package to each DSP** via S3 or SFTP from config; only optional XML variant (e.g. TikTok MD5) at send time.
- **Scaling to 40 DSPs:** One package build, one S3 adapter, one SFTP adapter, and 40 config entries — no 40 separate delivery modules.

This is the recommended way to deal with SFTP and DDEX deliveries at scale.
