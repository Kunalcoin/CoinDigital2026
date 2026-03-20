# Meta (Facebook / Instagram Music) – DDEX ERN 4.3 delivery feed

This doc describes the **Meta** delivery feed aligned to the **ERN 4.3 hybrid audio sample** (`ERN4.3-sample-hybrid-audio-xml.xml`) and what to ask Meta if needed.

---

## 1. What we implemented (from the sample)

| Item | Sample value | Our implementation |
|------|--------------|---------------------|
| **MessageRecipient** | Two: Facebook_SRP (PADPIDA2013071501L), Facebook_AAP (PADPIDA2018010804X) | We add **both** recipients for `store=meta`. |
| **Namespace** | http://ddex.net/xml/ern/43 | We use ERN 4.3 ✓ |
| **ReleaseProfileVersionId** | Audio | We use Audio or SimpleAudioSingle ✓ |
| **AvsVersionId** | 3 (in sample) | We use 6 (config); confirm with Meta if they require 3. |
| **PartyList – artists** | PartyId with Namespace distributor + **Namespace PADPIDA2018010804X** (Facebook AAP artist ID); **ArtistProfilePage** (Facebook + Instagram URLs) | We add **meta_artist_id** / **facebook_artist_id** and **facebook_profile_url** / **instagram_profile_url** when present on Artist. |
| **SoundRecording** | ResourceRightsController + **DelegatedUsageRights** (UseType UserMakeAvailableUserProvided or UserMakeAvailableLabelProvided) | We add **DelegatedUsageRights** (UserMakeAvailableLabelProvided, TerritoryOfRightsDelegation Worldwide) for every track when `store=meta`. |
| **DealList** | One ReleaseDeal; Deal with RightsClaimModel, UseType UserMakeAvailableUserProvided + UserMakeAvailableLabelProvided, **RightsClaimPolicy** (RightsClaimPolicyType Monetize) | We use **RightsClaimModel**, both UseTypes, and **RightsClaimPolicy** with Monetize ✓ |
| **TrackReleaseVisibility** | VisibilityReference V1, TrackListingPreviewStartDateTime, ClipPreviewStartDateTime | We add **TrackReleaseVisibility** with V1 and release date as start. |
| **TrackRelease** | **ReleaseVisibilityReference** V1 | We add **ReleaseVisibilityReference** V1 on each TrackRelease for meta. |
| **SentOnBehalfOf** | Optional (rights holder) | Not added yet; can add when we have a distinct rights-holder party. |
| **ClipDetails** | Preview (StartPoint 15, DurationUsed PT30S) on each SoundRecording | Not added; optional for preview clips. |
| **HashSum** | Algorithm MD5, HashSumValue | We use our existing hash structure; confirm if Meta requires a specific format. |

---

## 2. How to generate the feed

```bash
python manage.py build_ddex <release_id> --store meta [--output path]
```

Config: `releases/ddex_config.py` (META_FACEBOOK_SRP_*, META_FACEBOOK_AAP_*).  
DSP registry: `releases/data/ddex_dsps.json` (code `meta`, deal_profile `meta`).

---

## 3. Optional: artist mapping and profile pages

When you have them, set on **Artist** (or equivalent):

- **meta_artist_id** or **facebook_artist_id** – Facebook AAP artist ID (Namespace PADPIDA2018010804X in PartyList).
- **facebook_profile_url** / **facebook_url** – Facebook profile URL → **ArtistProfilePage**.
- **instagram_profile_url** / **instagram_url** – Instagram profile URL → **ArtistProfilePage**.

The builder already outputs these when present.

---

## 4. Questions to ask Meta (if needed)

1. **AvsVersionId:** The sample uses `AvsVersionId="3"`; we use `6`. Do you require a specific value for ERN 4.3 deliveries?

2. **Delivery method:** How should we deliver the DDEX (e.g. SFTP, S3, API, portal)? Do you provide bucket/credentials or onboarding steps?

3. **SentOnBehalfOf:** Do you require **SentOnBehalfOf** (rights holder PartyId/PartyName) in the header when the sender is a distributor acting on behalf of a label/rights holder?

4. **ClipDetails / preview:** Do you require **ClipDetails** (e.g. 30-second preview from a start point) on each SoundRecording, or is it optional?

5. **DelegatedUsageRights – UseType:** The sample uses both **UserMakeAvailableUserProvided** and **UserMakeAvailableLabelProvided** (per track). We currently send **UserMakeAvailableLabelProvided** for all tracks. Should we send both UseTypes per track, or is LabelProvided sufficient when we are the label/distributor?

6. **Update and takedown:** What message types do you accept for **metadata update** and **takedown** (e.g. NewReleaseMessage with update indicator, PurgeReleaseMessage, or other)? Any required elements (e.g. reason codes, dates)?

7. **File / asset delivery:** Expected structure for the package (e.g. folder per release, manifest, naming for XML and audio/image files)?

8. **HashSum:** Do you require a specific **HashSum** format (e.g. Algorithm + HashSumValue as in the sample) and algorithm (e.g. MD5)?

---

## 5. Code references

- Config: `releases/ddex_config.py` (META_FACEBOOK_SRP_*, META_FACEBOOK_AAP_*, USE_USER_MAKE_AVAILABLE_LABEL_PROVIDED).
- Builder: `releases/ddex_builder.py` – `_recipients_for_store("meta")`, `_add_deal_terms_meta()`, DelegatedUsageRights, TrackReleaseVisibility, ReleaseVisibilityReference, Meta PartyId and ArtistProfilePage in PartyList.
- Registry: `releases/data/ddex_dsps.json` – `meta`, deal_profile `meta`.
- Command: `python manage.py build_ddex <id> --store meta`.
