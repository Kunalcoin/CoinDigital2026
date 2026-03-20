# DDEX store connection status (Gaana, Audiomack, TikTok)

Quick reference for whether we can connect to and deliver to each store.

---

## Gaana — **Working**

- **Status:** You have successfully connected and delivered at least one release.
- **How:** SFTP using credentials in `coin.env` (`GAANA_SFTP_HOST`, `GAANA_SFTP_USERNAME`, `GAANA_SFTP_PASSWORD`, etc.). Delivery runs from your server (IP whitelisted by Gaana).
- **No change needed** for Gaana.

---

## Audiomack — **Can connect (to our S3); push to their S3 not yet set**

- **What works today:** We build DDEX for Audiomack and upload the package to **your** S3 bucket (`AWS_STORAGE_BUCKET_NAME` = `coindigital-media`) at:
  - `ddex/audiomack/<date>/<upc>.xml`
  - `ddex/audiomack/<date>/resources/` (cover + audio)
- **So we are “able to connect”** in the sense that delivery runs and files are stored (in your bucket). Audiomack would need to pull from there, or you share the package, unless we push to their bucket.
- **To push directly to Audiomack’s S3:** They need to give you:
  - Bucket name and prefix (folder path)
  - Write access: either IAM keys for that bucket, or a bucket policy allowing your AWS account
- **Then set in `coin.env`:**
  - `AUDIOMACK_S3_BUCKET` = their bucket name
  - `AUDIOMACK_S3_PREFIX` = their prefix (e.g. `incoming/coin-digital`)
  - If they give you IAM keys: `AUDIOMACK_AWS_ACCESS_KEY_ID` and `AUDIOMACK_AWS_SECRET_ACCESS_KEY`  
  (The code currently uses your main AWS credentials for S3; if you add Audiomack’s bucket, we may need to add support for `AUDIOMACK_AWS_*` when their bucket is in a different account.)
- **Details:** See `AUDIOMACK_PUSH_DELIVERY.md` for the exact questions to send Audiomack.

**Summary:** Yes, we can connect and deliver for Audiomack (to our S3). Pushing to their S3 depends on them providing bucket + credentials/access.

---

## TikTok — **Configured; should be able to connect**

- **Status:** TikTok S3 delivery is configured in `coin.env`:
  - `TIKTOK_S3_BUCKET=bytedance-s3-eusg-projectm-upload`
  - `TIKTOK_S3_PREFIX=resso-label-eu-singapore-8/`
  - `TIKTOK_AWS_ACCESS_KEY_ID` and `TIKTOK_AWS_SECRET_ACCESS_KEY` set
- **So we are set up to connect** to TikTok’s S3 and push the DDEX package (XML + cover + audio with MD5 hashes).
- **If TikTok delivery fails:** Typical causes:
  1. **Credentials:** Key/secret wrong or rotated — ask TikTok to confirm or re-issue.
  2. **Region:** Bucket may be in a specific region (e.g. Singapore). If you see errors like “permanent redirect” or “wrong region,” we can add `TIKTOK_S3_REGION` (e.g. `ap-southeast-1`) to the S3 client in `releases/tiktok_delivery.py`.
  3. **Network/firewall:** Server must be able to reach AWS S3 (HTTPS). If you run only from a locked-down network, allow outbound to `*.s3.*.amazonaws.com`.
  4. **Permissions:** The IAM user for the keys must have `s3:PutObject` (and list if we use it) on that bucket/prefix.

**Summary:** Yes, we are able to connect to TikTok in code; if you see errors, check credentials, region, and network.

---

## What is the “issue” now?

- **Gaana:** No issue; delivery is working.
- **Audiomack:** No “connection” issue; delivery runs and saves to your S3. The only gap is pushing to **Audiomack’s own bucket** once they provide bucket name and access.
- **TikTok:** No missing config; if a specific error appears when you run delivery (e.g. from “DDEX delivery for Audiomack, Gaana & TikTok” or `ddex_deliver_all`), share the error message and we can fix (e.g. region or credentials).

---

## Quick check from your server

Run:

```bash
cd RoyaltyWebsite
python3 manage.py ddex_deliver_all <release_id>
```

- **Gaana:** Should succeed (you already delivered once).
- **Audiomack:** Should succeed (upload to your S3); if you later set `AUDIOMACK_S3_BUCKET`, it will push to their bucket instead.
- **TikTok:** Should succeed if credentials and network are correct; if it fails, the command output will show the error (e.g. Access Denied, InvalidAccessKeyId, connection timeout). Share that error to fix the connection.
