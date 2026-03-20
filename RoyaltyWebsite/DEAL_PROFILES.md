# Deal Profiles (Phase 2) — Reusable Templates

We use **three deal profiles** for DDEX ERN 4.3. Each DSP in the registry is assigned one profile via **`deal_profile`**. No per-DSP deal code: add a DSP, set its profile, done.

---

## Profile summary

| Profile ID   | Use case                          | ERN 4.3 elements |
|-------------|------------------------------------|------------------|
| **streaming** | Spotify, Apple, Audiomack, most streamers | **CommercialModelType:** SubscriptionModel, AdvertisementSupportedModel<br>**UseType:** OnDemandStream, NonInteractiveStream, ConditionalDownload |
| **ugc**       | TikTok (UGC/Library)               | **CommercialModelType:** RightsClaimModel<br>**UseType:** UserMakeAvailableUserProvided<br>**RightsClaimPolicyType:** Monetize<br>**RightsController:** 100% (vendor reference) |
| **download**  | DSPs that need download-only terms | **CommercialModelType:** PayAsYouGoModel<br>**UseType:** PermanentDownload |

---

## 1. Streaming

- **When to use:** Default for most DSPs (streaming services, on-demand audio).
- **DealTerms:** Two deals — SubscriptionModel and AdvertisementSupportedModel. ValidityPeriod with StartDateTime. TerritoryCode Worldwide. UseTypes: OnDemandStream, NonInteractiveStream, ConditionalDownload (for subscription).
- **Registry:** Set `"deal_profile": "streaming"` for the DSP.

---

## 2. UGC

- **When to use:** TikTok (and any DSP that uses the same UGC/Library feed model).
- **DealTerms:** One deal — RightsClaimModel, UserMakeAvailableUserProvided, RightsClaimPolicyType Monetize, plus RightsController (vendor, 100%).
- **Registry:** Set `"deal_profile": "ugc"` for the DSP.

---

## 3. Download

- **When to use:** DSPs that require download-only (e.g. permanent download, pay-per-download).
- **DealTerms:** One deal — PayAsYouGoModel, UseType PermanentDownload. ValidityPeriod with StartDateTime. TerritoryCode Worldwide.
- **Registry:** Set `"deal_profile": "download"` for the DSP.

---

## Assigning a profile to a DSP

In **`releases/data/ddex_dsps.json`**, set **`deal_profile`** to one of:

- `streaming`
- `ugc`
- `download`

Example for a download-only store:

```json
{
  "code": "example_download_store",
  "party_id": "PADPIDA_PLACEHOLDER_EXAMPLE",
  "party_name": "Example Download Store",
  "deal_profile": "download",
  "is_active": false
}
```

No code change required. The builder selects the deal template from **`deal_profile`** when generating DDEX.
