# Pending for Spotify — DDEX Feed Setup

We have built our DDEX ERN 4.3 feed (Insert, Update, Takedown for Single, EP, Album) and use **Spotify’s Party ID** `PADPIDA2011072101T` in the registry. To complete setup and go live, we need the following from the **Spotify team**.

---

## What we need from Spotify

| # | Item | Why we need it |
|---|------|----------------|
| 1 | **Confirmation of Spotify DDEX Party ID** | We are using `PADPIDA2011072101T` for MessageRecipient. Please confirm this is correct for receiving feeds from labels/distributors. |
| 2 | **Delivery method** | How should we send DDEX feeds to Spotify? (e.g. SFTP, FTP, API, or partner portal upload.) |
| 3 | **Delivery credentials / access** | For the chosen method: host, port, username, authentication (password or SSH public key), and any whitelisting (e.g. our server’s public IP or SSH key). |
| 4 | **Folder structure and file naming** | Required layout (e.g. `batch_id/upc/upc.xml`) and naming rules for the DDEX XML and linked asset files (audio, artwork). |
| 5 | **DDEX version** | We generate **ERN 4.3**. Please confirm you accept 4.3 or specify the required version and schema (e.g. XSD URL). |
| 6 | **Test and go-live process** | Steps for (a) submitting a test package, (b) validation/feedback, and (c) moving to production (e.g. production SFTP/API or credentials). |
| 7 | **Technical requirements** | Any mandatory elements, validation (e.g. XSD), or format requirements we must follow. |
| 8 | **Contact for feeds** | Who we should contact for feed onboarding, delivery issues, and feed-related support. |

---

## What we have ready

- DDEX ERN 4.3 messages: **Insert** (NewReleaseMessage), **Update** (with LinkedMessageId), **Takedown** (PurgeReleaseMessage).
- Support for **Single**, **EP**, and **Album**.
- Our **sender** details (Coin Digital Party ID and Party Name) for MessageHeader.
- Deal terms: SubscriptionModel + AdvertisementSupportedModel; OnDemandStream, NonInteractiveStream, ConditionalDownload.
- Ability to generate one package per release or batch (including via Celery).

Once we have the items above from Spotify, we can complete configuration (credentials, paths, and test/production steps) and start delivering feeds.
