# TikTok DDEX Delivery Setup (S3)

TikTok/ByteDance deliver via **S3**. This document describes how to configure delivery using the bucket and credentials they provided.

---

## What’s in place

- **DDEX build for TikTok:** Party ID `PADPIDA2018082301A`, Party Name "TikTok / Bytedance", UGC deal profile. See `releases/data/ddex_dsps.json` and `releases/ddex_builder.py`.
- **ByteDance sample alignment:** XML includes **MD5 HashSum** for each file (cover + audio) per their ERN 4.3 sample and Partner Implementation Doc. Built automatically when delivering to TikTok.
- **Delivery module:** `releases/tiktok_delivery.py` builds DDEX for TikTok and uploads the package (XML + cover + audio) to **TikTok’s S3 bucket** using the credentials in `coin.env`.
- **UI:** The **“DDEX delivery for Audiomack, Gaana & TikTok”** button on Preview & Distribute runs delivery for all three; TikTok uploads to S3 when configured.
- **CLI:** `python manage.py ddex_deliver_tiktok <release_id>` or `python manage.py ddex_deliver_tiktok --upc <upc>`.

---

## Environment variables (use TikTok’s S3 details)

**Do not commit credentials to git.** These are set in **`coin.env`** (django-docker-compose/coin.env). Ensure `coin.env` is not committed if it contains secrets.

TikTok’s team provided:

- **bucket:** `bytedance-s3-eusg-projectm-upload`
- **prefix:** `resso-label-eu-singapore-8/`
- **ak:** (access key)  
- **sk:** (secret key)

Set in `.env`:

| Variable | Description | Value (from TikTok email) |
|----------|-------------|----------------------------|
| `TIKTOK_S3_BUCKET` | TikTok S3 bucket name | `bytedance-s3-eusg-projectm-upload` |
| `TIKTOK_S3_PREFIX` | Prefix/folder path in bucket | `resso-label-eu-singapore-8/` |
| `TIKTOK_AWS_ACCESS_KEY_ID` | TikTok S3 access key | (from their email: `ak`) |
| `TIKTOK_AWS_SECRET_ACCESS_KEY` | TikTok S3 secret key | (from their email: `sk`) |

**Example .env snippet (use the values they sent you):**

```bash
TIKTOK_S3_BUCKET=bytedance-s3-eusg-projectm-upload
TIKTOK_S3_PREFIX=resso-label-eu-singapore-8/
TIKTOK_AWS_ACCESS_KEY_ID=<ak from TikTok>
TIKTOK_AWS_SECRET_ACCESS_KEY=<sk from TikTok>
```

If `TIKTOK_S3_BUCKET` is not set, the app still builds TikTok DDEX but skips upload and reports that delivery was skipped.

---

## Upload layout on TikTok S3

Each delivery uses a **batch ID** (timestamp `YYYYMMDDHHMMSS`). Files are written under the prefix as:

- `{TIKTOK_S3_PREFIX}{batch_id}/{upc}.xml` — DDEX ERN 4.3 NewReleaseMessage for TikTok (UGC).
- `{TIKTOK_S3_PREFIX}{batch_id}/resources/coverart.jpg` — cover art.
- `{TIKTOK_S3_PREFIX}{batch_id}/resources/1_1.flac`, `1_2.flac`, … — track audio.

Example:  
`resso-label-eu-singapore-8/20250224143000/8901234567890.xml`  
`resso-label-eu-singapore-8/20250224143000/resources/coverart.jpg`  
`resso-label-eu-singapore-8/20250224143000/resources/1_1.flac`

After a successful delivery, the response includes **batch_id** and **upc** so you can send them to TikTok as requested (“Please let us know the batch IDs and UPCs once delivered”).

---

## How to deliver

1. **From the UI:**  
   Open the release’s **Preview & Distribute** page and click **“DDEX delivery for Audiomack, Gaana & TikTok”**.  
   TikTok delivery runs when `TIKTOK_S3_BUCKET` and TikTok credentials are set.

2. **From the CLI:**  
   - One release:  
     `python manage.py ddex_deliver_tiktok <release_id>`  
     or  
     `python manage.py ddex_deliver_tiktok --upc <upc>`  
   - Build DDEX XML only (no upload):  
     `python manage.py build_ddex <release_id> --store tiktok [--output /path]`

3. **Reporting to TikTok:**  
   After each successful delivery, note the **Batch ID** and **UPC** from the success message or response detail and email them to TikTok as requested.

---

## Checklist

- [ ] Add TikTok S3 settings to `.env`: `TIKTOK_S3_BUCKET`, `TIKTOK_S3_PREFIX`, `TIKTOK_AWS_ACCESS_KEY_ID`, `TIKTOK_AWS_SECRET_ACCESS_KEY`. **Do not commit .env.**
- [ ] Send 1–2 test deliveries in the expected standard (DDEX ERN 4.3 + resources under batch_id).
- [ ] Email TikTok the **batch ID(s)** and **UPC(s)** once delivered so they can test.
- [ ] If TikTok require a different folder structure or naming, we can adjust `releases/tiktok_delivery.py`.

---

## Files involved

| Purpose | File |
|--------|------|
| TikTok delivery (build + S3 upload) | `releases/tiktok_delivery.py` |
| Store delivery routing (includes TikTok) | `releases/store_delivery.py` |
| Preview & Distribute button (Audiomack + Gaana + TikTok) | `releases/views.py` (`ddex_deliver_audiomack`), `releases/templates/volt_preview_distribute_info.html` |
| CLI: deliver one release to TikTok | `releases/management/commands/ddex_deliver_tiktok.py` |
| DSP registry (TikTok entry) | `releases/data/ddex_dsps.json` |
| DDEX config (TikTok Party ID/name) | `releases/ddex_config.py` |
