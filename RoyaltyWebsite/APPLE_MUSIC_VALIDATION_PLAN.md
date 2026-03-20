# Apple Music Validation Plan (DDEX ERN 4.3) – Merlin Bridge

This plan maps the **10 Apple Music validation checks** (Merlin Bridge Checklist) to releases and deliveries using our DDEX ERN 4.3 pipeline. Execute step by step; after each delivery, confirm the check in the Bridge dashboard.

**Your DPID (Party ID):** From `ddex_config.py` / env `DDEX_PARTY_ID_COIN` (default `PADPIDA2023031502Y`). Used as sender in all messages.

**Delivery:** All test packages are sent to Merlin Bridge SFTP (Apple Music) via `releases/merlin_bridge_delivery.py`. Ensure `MERLIN_BRIDGE_SFTP_*` env vars and `DELIVERY_STORES` include `apple_music`. Use **TestMessage** for checklist (see below).

---

## Summary Table

| # | Check | Release type / data | Message type | Code status |
|---|--------|----------------------|--------------|-------------|
| 1 | Full Length Delivery | Album, 6+ tracks, 30+ min | NewReleaseMessage (Insert) | Ready |
| 2 | EP Delivery | EP, 3–6 tracks, <30 min | NewReleaseMessage (Insert) | Ready |
| 3 | Metadata Update Delivery | Update to a prior delivery | NewReleaseMessage (UpdateMessage + LinkedMessageId) | Ready (need to store MessageId) |
| 4 | Takedown Delivery | Any delivered product | PurgeReleaseMessage | Takedown to Bridge: to add |
| 5 | Compound Artist Delivery | Multiple Primary Artists (equal) | NewReleaseMessage (Insert) | Ready (multiple Primary Artist roles) |
| 6 | Featured Artist Delivery | At least one Featuring/Featured Artist | NewReleaseMessage (Insert) | Ready |
| 7 | Preorder Delivery | Future release date | NewReleaseMessage (Insert) | Ready (use future digital_release_date); optional: PreorderReleaseDate in XML |
| 8 | Instant Grat Delivery | 1+ track instant grat, ≤50% of tracks | NewReleaseMessage (Insert) | May need InstantGratificationDate in builder |
| 9 | Streaming Only Delivery | Product/track streaming only | NewReleaseMessage (Insert) | May need UseType subset (no download) |
| 10 | Retail Only Delivery | Product/track retail only | NewReleaseMessage (Insert) | May need UseType subset (e.g. PermanentDownload only) |

---

## Step-by-step execution plan

### Check 1: Full Length Delivery
- **Requirement:** 6+ tracks, full-length record, 30+ minutes.
- **Prepare:** One release with **Album** format, **6 or more tracks**, total duration ≥30 minutes. Set title, artists, UPC/ISRC, cover, audio, **Digital Release Date** and **Original Release Date**.
- **Build:** `build_new_release_message(release, store="apple_music")` with `message_control_type="TestMessage"` (for testing).
- **Deliver:** Use “Preview & Distribute” for this release with Apple Music selected, or run `deliver_release_to_store(release, "apple_music")`. Package uploads to Merlin Bridge SFTP.
- **In Bridge:** Mark “Full Length Delivery” complete when Apple accepts.

---

### Check 2: EP Delivery
- **Requirement:** 3–6 tracks, <30 minutes.
- **Prepare:** One release with **EP** format, **3–6 tracks**, total duration <30 minutes. Full metadata as above.
- **Build & deliver:** Same as Check 1; store = `apple_music`, MessageControlType = TestMessage.
- **In Bridge:** Mark “EP Delivery” complete.

---

### Check 3: Metadata Update Delivery
- **Requirement:** Update to data previously delivered (product or track level).
- **Prepare:** Use the **same release** as Check 1 or 2 (already delivered). Change something (e.g. title, artist name, track title) in the DB.
- **Build:** `build_new_release_message(release, store="apple_music", message_control_type="UpdateMessage", linked_message_id=<MessageId from first delivery>)`. We need to **store the MessageId** from the first delivery (e.g. in a log or small table) to pass as `linked_message_id`.
- **Deliver:** Upload this update package to Merlin Bridge SFTP (same structure as new release).
- **Code note:** Ensure we persist/supply `MessageId` from the initial Insert so UpdateMessage can reference it. Optional: add `linked_message_id` to Merlin Bridge delivery when doing an update.
- **In Bridge:** Mark “Metadata Update Delivery” complete.

---

### Check 4: Takedown Delivery
- **Requirement:** Takedown at **product level** only.
- **Prepare:** A release that was previously delivered to Apple Music (e.g. the one used for Check 1 or 2).
- **Build:** `build_takedown_message(release, store="apple_music")` → **PurgeReleaseMessage** with `ReleaseReferenceList` containing `R_{upc}`.
- **Deliver:** Upload this PurgeReleaseMessage XML to Merlin Bridge SFTP. **Current gap:** We only send takedown to Audiomack and Gaana; we need to add **Merlin Bridge (Apple Music) takedown** (build PurgeReleaseMessage for `apple_music` and upload to Bridge SFTP in the same way as Gaana takedown).
- **In Bridge:** Mark “Takedown Delivery” complete.

---

### Check 5: Compound Artist Delivery
- **Requirement:** Compound artists with **equal contribution** (product or track level).
- **Prepare:** One release (Single/EP/Album) with **multiple Primary Artists** (or Performer) on the same release or on a track—e.g. “Artist A & Artist B” with both as Primary Artist. Our DDEX builder already outputs multiple `DisplayArtist` with `DisplayArtistRole` MainArtist.
- **Build & deliver:** Standard NewReleaseMessage (TestMessage) for `apple_music`. No code change if we already support multiple primary artists.
- **In Bridge:** Mark “Compound Artist Delivery” complete.

---

### Check 6: Featured Artist Delivery
- **Requirement:** At least one **featured artist** (product or track level).
- **Prepare:** One release with at least one artist in **Featuring** or **Featured Artist** role (we have these in `ARTIST_ROLES`). Builder maps these to `DisplayArtistRole` MainArtist today; Apple may expect a specific role—we can confirm after first test.
- **Build & deliver:** Standard NewReleaseMessage (TestMessage) for `apple_music`.
- **In Bridge:** Mark “Featured Artist Delivery” complete.

---

### Check 7: Preorder Delivery
- **Requirement:** **Future** preorder start date (before full release / sale date).
- **Prepare (Merlin Bridge / iTunes Importer):** On the release, set **Apple Music pre-order sales start date** (`apple_music_preorder_start_date`) in Django admin under **License — Apple Music (Merlin Bridge)**. It must be **before** **Digital release date** and **in the future** on the day you deliver. `build_apple_itunes_metadata` emits `<preorder_sales_start_date>` on the **album** `<product>` only (not on track products — ITMS-4020).
- **Deliver:** Full `deliver_apple_music --upc …`. Clear the preorder date after the checklist if you do not want preorder on that UPC.
- **In Bridge:** Mark “Preorder Delivery” complete.

---

### Check 8: Instant Grat Delivery
- **Requirement:** Instant grat for **at least one track**, and **no more than 50%** of tracks (Merlin checklist wording).
- **Prepare:** Mark IG tracks in Django admin (`Track.apple_music_instant_grat`). At most **50%** of tracks may be IG (enforced before upload).
- **Build:** `metadata.xml` includes **`<preorder_type>` on each `<track>`** (sibling of `<products>`): `instant-gratification` or `standard`. Do **not** put `<preorder_type>` inside track `<product>` (schema rejects it). Album pre-order date stays on **album** `<product>` as `<preorder_sales_start_date>`.
- **Deliver:** Full `deliver_apple_music --upc …`
- **In Bridge:** Mark checklist when Merlin confirms.

---

### Check 9: Streaming Only Delivery
- **Requirement:** Product or at least one track set as **streaming only** (no download).
- **Prepare:** One release we intend to deliver as streaming-only. Our streaming deal already uses OnDemandStream, NonInteractiveStream, ConditionalDownload. For “streaming only” we may need to **omit** ConditionalDownload (and any PermanentDownload) from the deal terms for that release or track.
- **Build:** In `ddex_builder.py`, for Apple Music we may need a **streaming-only** variant: DealTerms with only OnDemandStream and NonInteractiveStream (no ConditionalDownload / PermanentDownload). This could be driven by a release flag (e.g. `streaming_only`) or a per-store rule.
- **Deliver:** NewReleaseMessage (TestMessage) to Merlin Bridge.
- **In Bridge:** Mark “Streaming Only Delivery” complete.

---

### Check 10: Retail Only Delivery
- **Requirement:** Product or at least one track set as **retail only** (e.g. download-only, no streaming).
- **Prepare:** One release we intend to deliver as retail-only.
- **Build:** DealTerms with only **PermanentDownload** (and possibly ConditionalDownload), **no** OnDemandStream/NonInteractiveStream. May need a release-level flag or store-specific deal variant in the builder.
- **Deliver:** NewReleaseMessage (TestMessage) to Merlin Bridge.
- **In Bridge:** Mark “Retail Only Delivery” complete.

---

## Execution order (recommended)

1. **Check 1 – Full Length** (Album, 6+ tracks, 30+ min) → deliver, note **MessageId** for Check 3.
2. **Check 2 – EP** (EP, 3–6 tracks, <30 min) → deliver.
3. **Check 5 – Compound Artist** → deliver.
4. **Check 6 – Featured Artist** → deliver.
5. **Check 7 – Preorder** (future date) → deliver.
6. **Check 3 – Metadata Update** → change metadata of release from Check 1, deliver UpdateMessage with LinkedMessageId.
7. **Check 4 – Takedown** → implement Merlin Bridge takedown upload, then send PurgeReleaseMessage for one of the delivered releases.
8. **Check 8 – Instant Grat** → add track-level instant grat in builder + DB if needed, then deliver.
9. **Check 9 – Streaming Only** → add streaming-only deal variant if needed, then deliver.
10. **Check 10 – Retail Only** → add retail-only deal variant if needed, then deliver.

---

## What we have today (no code change)

- **Full Length & EP:** `album_format` = Album/EP; track count and duration from DB + audio files. Builder outputs ReleaseType and Duration. **Ready.**
- **Compound Artist:** Multiple Primary Artist/Performer in RelatedArtists; builder outputs multiple DisplayArtist. **Ready.**
- **Featured Artist:** Featuring / Featured Artist roles in RelatedArtists; builder maps to DisplayArtist. **Ready.**
- **Preorder:** Set `digital_release_date` (and `original_release_date`) to a future date; builder outputs ReleaseDate/OriginalReleaseDate. **Ready** (optional: add PreorderReleaseDate in XML if Apple requires it).
- **Update:** Builder supports `message_control_type="UpdateMessage"` and `linked_message_id`. We need to **store and pass** the first delivery’s MessageId. **Small wiring.**
- **Takedown:** `build_takedown_message(release, store="apple_music")` exists. **Gap:** upload PurgeReleaseMessage to Merlin Bridge SFTP (new function + call from takedown flow or manual step).

---

## What we may need to add

- **Check 3:** Persist MessageId from first delivery (e.g. in release metadata or log) and pass it as `linked_message_id` when building/delivering the update. Optionally add a “Deliver as update” path in Merlin Bridge delivery that accepts `linked_message_id`.
- **Check 4:** **Merlin Bridge takedown:** Build PurgeReleaseMessage for `apple_music` and upload to Bridge SFTP (path similar to Gaana takedown). Optionally extend `_send_ddex_takedown_to_dsps` to include Apple Music when configured.
- **Check 8:** Track-level **instant gratification** (DB field + InstantGratificationDate in ERN 4.3 for selected tracks; enforce ≤50%).
- **Check 9:** **Streaming-only** deal variant for Apple (DealTerms without download UseTypes).
- **Check 10:** **Retail-only** deal variant for Apple (DealTerms with only download UseTypes).

---

## Quick reference: build & deliver

- **Build DDEX for Apple Music (test):**  
  `build_new_release_message(release, store="apple_music", message_control_type="TestMessage")`
- **Build update:**  
  `build_new_release_message(release, store="apple_music", message_control_type="UpdateMessage", linked_message_id=<saved_message_id>)`
- **Build takedown:**  
  `build_takedown_message(release, store="apple_music")`
- **Deliver to Merlin Bridge:**  
  From admin: approve release with Apple Music in delivery stores, or programmatically: `deliver_release_to_store(release, "apple_music")`.

Ensure **apple_music** is in `DELIVERY_STORES` and `releases/data/ddex_dsps.json` has `apple_music` with `is_active: true` when running these tests.
