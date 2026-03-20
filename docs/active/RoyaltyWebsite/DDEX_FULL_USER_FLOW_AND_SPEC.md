# DDEX Full User Flow & Implementation Spec

**Purpose:** Single reference for you and your developer. Use this to discuss with the developer and to give the AI (Cursor) clear, step-by-step prompts so it can design and implement correctly.

**Developer’s role:** Supervise the flow, correct your steps, and help you phrase commands/prompts for the AI (e.g. “implement store selection popup”, “rename S3 resources to UPC_01.wav”).

---

## Part 1: What You Want to Achieve (Goals)

1. **Normal user** creates a release with mandatory + optional fields.
2. User fills **artist social IDs** (e.g. Spotify, YouTube username).
3. User adds **tracks**; system saves each in **3 formats**: WAV (original), MP3, FLAC.
4. User **distributes** by selecting **which stores** (DSPs) to use; a **popup** asks “which stores?” with **all selected by default**.
5. On “Distribute”, the release is **not** sent to stores yet; it is sent to **admin for approval**.
6. When sent to admin, the system **builds DDEX XML** and **saves resources to S3** with a fixed naming convention (see below).
7. When **admin approves**, the system **sends the package only to the stores the user selected** (SFTP, S3, or other method per store).
8. **XML is generated only for the stores selected by the user** (not for all 40 DSPs).
9. User can **update** a release and request **takedown**; both go through admin (update = separate approval column; takedown = separate admin page).
10. Scale to **~40 DSPs** with one config-driven flow (registry + deal profiles).

---

## Part 2: End-to-End Flow (Step-by-Step)

### Phase A: User Creates & Submits Release

| Step | Who | Action | What the system does |
|------|-----|--------|----------------------|
| A1 | User | Creates release | Enters mandatory + optional release fields. |
| A2 | User | Fills artist social IDs | e.g. Spotify ID, YouTube username (stored on Artist or Release). |
| A3 | User | Adds tracks | For each track: upload/store WAV (original), and system generates/saves MP3 and FLAC (or user uploads all three). Tracks are saved with `audio_wav_url`, `audio_mp3_url`, `audio_flac_url`. |
| A4 | User | Clicks “Distribute this release” | **Popup** appears: “Select stores for distribution.” List of all available DSPs (from registry), **all checked by default**. User can uncheck some. User confirms. |
| A5 | User | Confirms in popup | System **does not** send to any store. It: (1) Saves **selected store codes** (e.g. `audiomack`, `gaana`, `spotify`) on the release (new field or relation). (2) Sets release **approval_status = pending_approval**. (3) **Builds DDEX package** (XML + resources) and **saves to S3** with the naming below. (4) Optionally notifies admin. **No delivery to DSPs yet.** |

**Important:** “Distribute” in the UI = “Submit for approval” + “Prepare DDEX package”. Actual delivery happens only after admin approval.

---

### Phase B: S3 Package When Submitted for Approval

When the user submits for approval (after selecting stores), the system must:

1. **Assign UPC/ISRC** if not already assigned.
2. **Build DDEX ERN 4.3 XML** (one “canonical” or per-store later; see Phase D).
3. **Save the following to your S3 bucket** (e.g. `ddex/packages/<release_id>/<upc>/` or equivalent):

**Naming convention you specified:**

| Resource | S3 filename (in package folder) |
|----------|----------------------------------|
| Artwork | `UPC.jpg` (e.g. `8905285301465.jpg`) |
| Track 1 WAV | `UPC_01.wav` |
| Track 2 WAV | `UPC_02.wav` |
| Track 1 MP3 | `UPC_01.mp3` |
| Track 2 MP3 | `UPC_02.mp3` |
| Track 1 FLAC | `UPC_01.flac` |
| Track 2 FLAC | `UPC_02.flac` |
| … | `UPC_<NN>.wav`, `UPC_<NN>.mp3`, `UPC_<NN>.flac` (NN = track number, 01, 02, …) |
| DDEX XML | e.g. `UPC.xml` or `<upc>.xml` (per store: see Phase D) |

So:

- **Artwork:** `UPC.jpg`
- **Audio:** `UPC_01.wav`, `UPC_01.mp3`, `UPC_01.flac`, then `UPC_02.*`, `UPC_03.*`, etc.

**Current code** uses different names (`coverart.jpg`, `1_1.flac`, `1_2.wav`). Implementation task: change package build to use **UPC.jpg** and **UPC_01.wav / UPC_01.mp3 / UPC_01.flac**, etc., and ensure DDEX XML references these filenames.

---

### Phase C: Admin Approval and Delivery to Stores

| Step | Who | Action | What the system does |
|------|-----|--------|----------------------|
| C1 | Admin | Sees release in “Pending approval” | Release is in list with status `pending_approval`; package already in S3. |
| C2 | Admin | Clicks “Approve” | System: (1) Sets **approval_status = approved**, **published = true**. (2) **Distributes only to the stores the user selected** (from A5). For each selected store: build or pick the XML for that store (see Phase D), then send package (XML + artwork + audio) via that store’s method: **SFTP** or **S3** or **API** as per DSP config. (3) Log success/failure per store. |
| C3 | — | Per-store delivery | Use existing delivery adapters (e.g. Audiomack S3, Gaana SFTP, TikTok S3). Only call delivery for DSPs that are in the release’s **selected stores** list. |

**Rule:** No delivery to a store that the user did not select. No XML generated for non-selected stores.

---

### Phase D: XML Per Selected Store Only

- **XML** should be created **only for the DSPs the user selected** (not for all 40).
- When building the package on submit (Phase B), you can either:
  - **Option 1:** Build one canonical XML and, on delivery, generate store-specific XML only for each selected DSP (different Party IDs, deal terms), or
  - **Option 2:** At submit time, build and store one XML per selected DSP in S3 (e.g. `UPC_audiomack.xml`, `UPC_gaana.xml`).
- **Recommendation:** Build **one canonical package** (one XML + resources with UPC naming). On **admin approve**, for **each selected store** generate that store’s XML (from registry: Party ID, deal profile) and send that XML + the same resources to the store. This avoids storing 40 XMLs when the user selected 3 stores.
- **Result:** Only selected stores get an XML and a delivery.

---

### Phase E: Update Release

- User has the **right to update** the release (metadata, tracks, artwork, etc.).
- After editing, when user submits again (e.g. “Submit update for approval” or same “Distribute” with a different meaning for already-approved releases):
  - Use a **separate column** such as **“Update approval”** (e.g. `update_pending_approval` / `update_approved`) so admin can see “this release has an update waiting.”
- Flow: same route as new distribution — **sent to admin for approval**. On admin approval of the update:
  - Rebuild DDEX package (with new metadata/assets) and **deliver update** to the **same set of stores** the user had selected (or allow re-selection of stores for the update; clarify with product).
- Implementation: add field(s) for update approval state; re-use same “approval” UX with a different label/column for “Update pending” vs “New release pending.”

---

### Phase F: Takedown

- User can request **takedown** of a release.
- Takedown **does not** execute immediately at user click. Instead:
  - System records “takedown requested” (e.g. `takedown_requested = True` and optionally `takedown_approval_status = pending`).
  - **Separate admin page** (e.g. “Takedown requests”) lists releases with takedown requested; admin can **process** (approve/execute) takedown.
- When admin **approves/processes** takedown:
  - System sends **DDEX takedown** (e.g. PurgeReleaseMessage or NewReleaseMessage with TakeDown) **only to the stores where this release was distributed** (i.e. the same selected stores at the time of approval), using each store’s method (SFTP/S3/API).
- So: **same route** in the sense that user requests → admin sees it; but **takedown has its own page** and its own “process” action.

---

## Part 3: What Is Already Designed vs What To Implement

### Already in place (design / code you have)

- **DDEX ERN 4.3** builder and **DSP registry** (`ddex_dsps.json`): Party ID, party name, deal profile (streaming, ugc, meta, download).
- **Deal profiles** and **scale to 40 DSPs**: add entries to registry; one code path for build/delivery.
- **Package-first flow**: build package on submit, distribute on approve (see `DDEX_PACKAGE_FIRST_ARCHITECTURE.md`).
- **Submit for approval** → `approval_status = pending_approval`; **Approve** → `approval_status = approved`, publish.
- **DDEX package build** and save to S3 (`ddex_package.py`): currently uses `coverart.jpg`, `1_1.flac`, `1_2.wav`, etc.
- **Delivery** to some DSPs (e.g. Audiomack S3, Gaana SFTP, TikTok); **takedown** DDEX for Audiomack and Gaana (currently sent on user takedown request; you want this moved to “after admin processes”).
- **Track formats**: model has `audio_wav_url`, `audio_mp3_url`, `audio_flac_url`; package build already copies WAV/MP3/FLAC when present.

### To implement (gaps)

| # | Item | Description |
|---|------|-------------|
| 1 | **Store selection (user)** | Popup on “Distribute” with list of all DSPs from registry; default = all selected; save selected store codes on release (e.g. `Release.selected_dsp_codes` JSON or M2M table). |
| 2 | **S3 resource naming** | Change package build to save: artwork as `UPC.jpg`; audio as `UPC_01.wav`, `UPC_01.mp3`, `UPC_01.flac`, `UPC_02.*`, … and update XML references to these filenames. |
| 3 | **XML only for selected stores** | When building package or when delivering: generate DDEX XML only for DSPs in the release’s selected store list. On approve: deliver only to those DSPs. |
| 4 | **Delivery only to selected stores** | In approve flow: loop only over `release.selected_dsp_codes` (or equivalent); call existing S3/SFTP delivery per store. |
| 5 | **Update approval** | New state/column for “update pending approval”; same flow as submit → admin approves → then rebuild package and send update to (same or re-selected) stores. |
| 6 | **Takedown admin page** | Separate page “Takedown requests” where admin sees releases with `takedown_requested`; button “Process takedown” sends DDEX takedown to the stores where that release was delivered (only those). Do not send takedown to DSPs on user click; send only after admin processes. |
| 7 | **Artist social IDs** | Ensure artist (or release) has fields for Spotify ID, YouTube username, etc., and that these are shown in release form and can be used in DDEX if needed. |
| 8 | **40 DSPs** | Complete registry with all 40 DSPs (Party IDs, deal profiles, delivery method); add delivery config (SFTP/S3/API) per DSP and wire delivery loop to config. |

---

## Part 4: Flow Summary (Checklist for Developer)

- [ ] **A1–A3** Release creation, artist social IDs, tracks in WAV/MP3/FLAC (already largely there; confirm UX and storage).
- [ ] **A4–A5** “Distribute” opens store-selection popup (default all); on confirm → save selected DSPs, set pending_approval, build DDEX package, save to S3 with **UPC.jpg** and **UPC_01.wav/mp3/flac** naming.
- [ ] **B** Package build uses your S3 naming (UPC.jpg, UPC_01.*, UPC_02.*, …) and XML references these.
- [ ] **C** On admin Approve: distribute only to selected stores; per-store delivery method (SFTP/S3/API) from registry.
- [ ] **D** XML generated only for selected stores; delivery only to selected stores.
- [ ] **E** Update release: separate “update approval” state; on approval, rebuild package and deliver update to the relevant stores.
- [ ] **F** Takedown: user requests → admin sees on “Takedown requests” page → admin processes → DDEX takedown sent only to stores where release was delivered.
- [ ] **40 DSPs** Registry + delivery config for all; one code path for build and delivery.

---

## Part 5: How to Use This With Your Developer and the AI

1. **Share this doc** with your developer so they can validate the flow and point out any wrong step or missing piece.
2. **Prompts for the AI (Cursor):** Use one flow-step at a time, for example:
   - “Implement the store selection popup on Distribute: list all DSPs from ddex_dsps.json, default all selected, save selected codes on Release.”
   - “Change DDEX package S3 naming to UPC.jpg for artwork and UPC_01.wav, UPC_01.mp3, UPC_01.flac (and 02, 03…) for tracks; update XML references.”
   - “On admin approve, deliver only to the stores saved in release’s selected DSP list.”
   - “Add an Update approval column and flow: when user submits an update, set update_pending_approval; on admin approval, rebuild package and deliver update to selected stores.”
   - “Add a Takedown requests admin page; when admin processes, send DDEX takedown only to the stores where this release was delivered.”
3. **Developer** can then refine these prompts (e.g. exact field names, API contracts, or edge cases) so the AI produces the right design and code.

---

## Part 6: Reference – Existing Docs in This Repo

- **DDEX_DSP_FLOW.md** – Registry, deal profiles, generate for all DSPs, delivery (FTP/SFTP/API).
- **DDEX_PACKAGE_FIRST_ARCHITECTURE.md** – Build package once on submit, distribute on approve; S3 layout; scaling to 40 DSPs.
- **DDEX_DELIVERY_FLOW.md** – Approve vs DDEX delivery; takedown and update (current behavior).
- **AUDIOMACK_PUSH_DELIVERY.md** – Push to Audiomack S3 (no pull).
- **DEAL_PROFILES.md** – Streaming, UGC, meta, download.
- **ddex_dsps.json** – DSP registry (code, party_id, party_name, deal_profile, is_active).

Use this flow as the single source of truth for “what we want”; use the other docs for technical details (registry, deal profiles, delivery methods). Your developer can align implementation to this flow and help you phrase AI prompts for each step.
