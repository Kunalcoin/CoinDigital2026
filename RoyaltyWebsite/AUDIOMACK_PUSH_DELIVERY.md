# Audiomack – Push delivery

**Model:** Coin Digital **pushes** the DDEX package (XML + cover + audio) to Audiomack. No DSP pulls from our S3.

---

## You're already set up – no need to ask for credentials

If Audiomack is **already receiving** your deliveries (e.g. they confirmed receipt on 19th February and again with recent batch IDs like 20260224070434050, 20260224073852263, 20260224075835713), then **you don't need to ask them for credentials or bucket details now.**

- **Why you didn't need them "that time" on 19 Feb:** Because the setup was already in place. When you use "DDEX delivery for Audiomack" (or your approval/delivery flow), the app uploads to S3. For that to reach **Audiomack's** bucket, your **deployment** (e.g. EC2/server) already has the right config: `AUDIOMACK_S3_BUCKET` (and prefix if needed, and any credentials if their bucket is in a different AWS account). That config is often in the server's `.env` or secrets, not necessarily in the repo's `coin.env`.
- **Why you don't need them now:** Same reason. They're already receiving your content via their S3. No further request to Audiomack is needed.

**Reply you can send to Audiomack (e.g. to their latest email):**

> Hi,  
> Thank you for confirming. We're glad the deliveries are coming through correctly (including the three you listed today). We don't need any changes — we'll continue using the same feed.  
> Thanks,  
> Kunal  

---

## When you would need to "ask" for details

The sections below are **only for** the case when you're **not** yet set up — e.g. a new partner or a new feed that has never delivered. If Audiomack is already receiving your DDEX (as they are now), you can skip them.

---

## If Audiomack say they already have a feed for Coin Digital

**Important:** The feed they have for Coin Digital **is** your DDEX feed. The delivery they confirmed on 19th February was **your DDEX XML** that you provided to them — **not** Sonosuite. Sonosuite does not handle your DDEX.

- You are **not** asking to add a second feed. The existing feed = your DDEX (same format you sent on 19 Feb).
- If they're already receiving (as in their email listing today's deliveries), you don't need to ask for S3 details — you're already pushing to their bucket.

---

## What to ask Audiomack (only if you are NOT yet set up)

Use this only when you **don't** yet have a working feed and need to set up push to their S3 from scratch.

Send them something like this (adjust tone as needed):

---

**Subject:** DDEX push delivery – S3 access for Coin Digital

We deliver content by **pushing** DDEX packages (ERN 4.3 XML + cover art + audio) to your system. We do not expose our S3 for pull; we will upload directly to the location you specify.

To enable push delivery to Audiomack, please provide:

1. **S3 bucket**
   - Bucket name we should upload to.
   - AWS region (e.g. `us-east-1`).

2. **Path / prefix**
   - Folder structure you expect (e.g. `incoming/coin-digital/` or `{date}/{upc}/`).
   - We currently generate: one folder per delivery with `<upc>.xml` and a `resources/` subfolder (cover + audio). We can align to your naming if needed.

3. **Write access**
   One of:
   - **Option A – IAM user:** Access Key ID + Secret Access Key for an IAM user that has `s3:PutObject` (and if needed `s3:PutObjectAcl`) on that bucket/prefix. We will store these securely and use them only for push.
   - **Option B – Cross-account role:** Our AWS account ID so you can add a bucket policy allowing us to put objects; you provide the bucket name and prefix.
   - **Option C – Pre-signed POST / URL:** If you prefer not to share long-term credentials, a way for us to obtain a pre-signed URL or POST policy per delivery (e.g. via an API you provide).

4. **Batch / completion**
   - Do you require a "batch complete" marker (e.g. `BatchComplete_{id}.xml`) in the folder? If yes, format and naming.

5. **Test**
   - After we have the above, we will push one test package (e.g. UPC 8905285301465) and ask you to confirm receipt.

Our technical contact: [your email]

---

## Once we have the details (for new setup only)

- We will set in `.env` (or your secrets manager):
  - `AUDIOMACK_S3_BUCKET` = their bucket name
  - `AUDIOMACK_S3_PREFIX` = their requested prefix (e.g. `incoming/coin-digital`)
  - If Option A: `AUDIOMACK_AWS_ACCESS_KEY_ID` and `AUDIOMACK_AWS_SECRET_ACCESS_KEY` (or equivalent env names we define)
- When `AUDIOMACK_S3_BUCKET` is set, we upload the **full package** to their bucket:
  - XML at `prefix/delivery_id/upc.xml`
  - Cover + audio in `prefix/delivery_id/resources/` (coverart.jpg, 1_1.flac, 1_2.flac, …).
  - Uses your AWS client (same credentials must have PutObject on their bucket, or use Audiomack's keys if they provided them).

No DSP retrieves data from our S3; we always push to each store.
