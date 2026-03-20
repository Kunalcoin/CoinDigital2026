# DDEX Feed Setup Flow for ~40 DSPs

We use **DDEX ERN 4.3** for all DSPs. This document describes the recommended flow to scale from a few stores to **~40 DSPs** without per-DSP code branches.

---

## 1. High-Level Flow (What to Do)

| Phase | Goal | Outcome |
|-------|------|---------|
| **1. Registry** | Single source of truth for all DSPs | One config (YAML/DB) with Party ID, name, deal profile, delivery |
| **2. Deal profiles** | Reusable deal templates | Few profiles (e.g. streaming, ugc) mapped to many DSPs |
| **3. Generate** | One code path for all DSPs | Build XML by `dsp_code` from registry; no 40 if/else |
| **4. Deliver** | Send the right package to each DSP | Per-DSP delivery (FTP/SFTP/API) and optional scheduling |

---

## 2. Recommended Step-by-Step Flow

### Phase 1: DSP Registry (Do First)

1. **List the 40 DSPs** you need to support (names + any existing Party IDs from their onboarding docs).
2. **Create one DSP registry** (see below: YAML file or DB table) with for each DSP:
   - `code` (slug, e.g. `spotify`, `tiktok`, `apple_music`)
   - `party_id` (DDEX Party ID from the DSP)
   - `party_name` (official name for MessageRecipient)
   - `deal_profile` (e.g. `streaming` or `ugc` — see Phase 2)
   - Optional later: `delivery_type`, `delivery_config`, `is_active`
3. **Obtain Party IDs** for each DSP (from their DDEX onboarding / partner portal). If a DSP has no Party ID yet, use a placeholder and update when they provide it.

**Result:** Adding DSP #41 = add one row/entry to the registry; no code change.

---

### Phase 2: Deal Profiles (Reusable Templates)

Most DSPs fall into a small set of deal structures. Define **deal profiles** and assign each DSP to one:

| Profile ID | Use case | Typical elements (ERN 4.3) |
|------------|----------|-----------------------------|
| **streaming** | Spotify, Apple, Audiomack, most streamers | SubscriptionModel + AdvertisementSupportedModel; UseType: OnDemandStream, NonInteractiveStream, ConditionalDownload |
| **ugc** | TikTok (UGC/Library) | RightsClaimModel; UserMakeAvailableUserProvided; RightsController 100%; RightsClaimPolicyType Monetize |
| **download** | DSPs that need download-only terms | PayAsYouGoModel or similar + PermanentDownload (add when needed) |

**Flow:**

1. Implement in code one builder per **profile** (e.g. `_add_deal_terms_streaming`, `_add_deal_terms_ugc`).
2. In the registry, set **deal_profile** per DSP (e.g. `spotify` → `streaming`, `tiktok` → `ugc`).
3. When building XML for a DSP, look up `deal_profile` and call the matching deal builder.

**Result:** New DSP with same deal type as Spotify = set `deal_profile: streaming`; no new deal code.

**Implementation:** All three profiles are implemented. See **DEAL_PROFILES.md** for details. In `ddex_dsps.json`, set each DSP's `deal_profile` to `streaming`, `ugc`, or `download`.

---

### Phase 3: Generate Feeds for All DSPs (implemented)

1. **Single release, many DSPs**
   - For a given release (by ID or UPC), loop over **active** DSPs in the registry.
   - For each DSP: `build_new_release_message(release, store=dsp_code)` (or `dsp_code` once refactored).
   - Write one package per DSP (e.g. `output/{dsp_code}/{upc}/...`).

2. **Batch / scheduled**
   - Define a list of releases (e.g. “all approved”, “releases updated in last 24h”).
   - For each release × each active DSP, generate the DDEX package.
   - Celery: use build_ddex_all_task.delay() or build_ddex_batch_task.delay() so generation does not block the UI; optional Beat runs daily. See CELERY_DDEX.md.

3. **Commands**
   - One release, one DSP: `python manage.py build_ddex <release_id> --store <dsp_code>`
   - One release, all DSPs: `python manage.py build_ddex_all <release_id> [--output ddex_output] [--test]` → `<output>/<dsp_code>/<upc>/<upc>.xml` per DSP.
   - Many × all: `python manage.py build_ddex_batch [--since YYYY-MM-DD] [--status approved] [--limit N] [--dry-run]` → same layout.

**Result:** One code path; “run for 40 DSPs” = iterate the registry and call the same builder 40 times.

---

### Phase 4: Delivery (FTP / SFTP / API)

1. **Per-DSP delivery config** (in registry or separate table):
   - `delivery_type`: `ftp`, `sftp`, `api`, `manual`
   - Credentials (store in env or secrets manager; reference by key, e.g. `DSP_SPOTIFY_SFTP_HOST`).
   - Paths (e.g. inbox folder, file naming rules).

2. **After generation**
   - For each DSP: upload the package (XML + assets) to their endpoint (FTP/SFTP) or POST to API.
   - Log success/failure per DSP; retry or alert on failure.

3. **Optional**
   - Dashboard: “Last delivered to Spotify”, “Pending for TikTok”, etc.
   - Scheduling: e.g. nightly job “generate + deliver for all releases updated today”.

**Result:** Each of the 40 DSPs gets the right package to the right place without manual uploads.

---

## 3. Flow Summary (Checklist)

- [ ] **Registry:** Create and maintain one DSP list (YAML or DB) with code, party_id, party_name, deal_profile.
- [ ] **Deal profiles:** Implement streaming + ugc (and others as needed); map each DSP to a profile.
- [ ] **Generate:** Refactor builder to take `dsp_code` and read recipient + deal_profile from registry; add “build for all DSPs” for a release.
- [ ] **Party IDs:** Fill in Party IDs for all 40 DSPs (from their docs or partner team); use placeholder until then.
- [ ] **Test:** Generate one release for 2–3 DSPs (e.g. Spotify, TikTok), validate XML (schema + spot-check).
- [ ] **Deliver:** Add delivery config per DSP and automate upload (FTP/SFTP/API) when ready.
- [ ] **Update / Takedown:** Extend builder for Update and Takedown messages; same registry (same DSP list) for all message types.

---

## 4. How to Onboard One New DSP (DSP #41)

1. Get from the DSP: **DDEX Party ID**, **Party Name**, **delivery method** (FTP/SFTP/API), **deal/rights requirements** (or confirm they use “standard streaming”).
2. Choose **deal_profile** (streaming / ugc / download or new profile if needed).
3. Add **one entry** to the DSP registry (code, party_id, party_name, deal_profile, delivery_type if applicable).
4. If new deal profile: implement one deal builder and register it; then assign the profile to the DSP.
5. Generate a test package for one release and send to the DSP (or their test environment).
6. No change to “build for all DSPs” logic — the new DSP is included automatically.

---

## 5. Technical Implementation (This Repo)

- **DSP registry:** `RoyaltyWebsite/releases/data/ddex_dsps.json` — add new DSPs here (code, party_id, party_name, deal_profile, is_active). Loaded by `releases/ddex_dsp_registry.py`; used by `ddex_builder.py`.
- **Deal profiles:** Implemented as functions (`_add_deal_terms_spotify` = streaming, `_add_deal_terms_tiktok` = ugc); selected by `deal_profile` from registry.
- **Builder:** `build_new_release_message(release, store=dsp_code)` — `dsp_code` is the registry key; recipient and deal terms come from registry + profile.
- **Commands:**
  - **One DSP:** `python manage.py build_ddex <release_id> --store <dsp_code>` (e.g. `--store spotify`, `--store tiktok`).
  - **All active DSPs:** `python manage.py build_ddex_all <release_id> --output ddex_output` — writes `ddex_output/<upc>/<dsp_code>.xml` for each active DSP.

**To reach 40 DSPs:** Add 40 entries to `releases/data/ddex_dsps.json` (copy existing block, set code/party_id/party_name, set deal_profile to `streaming` or `ugc`, set `is_active: true` when ready). No code change required.

This gives you a clear flow to scale to 40 DSPs and a single place (registry + deal profiles) to maintain and extend.
