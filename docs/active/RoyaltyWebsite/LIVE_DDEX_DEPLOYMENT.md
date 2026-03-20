# Live DDEX Deployment Checklist (Audiomack, Gaana & TikTok)

Use this to confirm all DDEX delivery and takedown/update feed pieces are deployed and working on the live website (EC2).

---

## 0. Deploy path (critical)

The deploy script (`deploy_to_server.sh`) pushes code to **DEPLOY_PATH** from `RoyaltyWebsite/coin.env`. This **must** be the path the running app uses, or the server will keep running old code.

- Default: `DEPLOY_PATH="/home/ubuntu/coin-digital-app/RoyaltyWebsite"` (Docker app root).
- If your app runs from a different directory, set `DEPLOY_PATH` in `coin.env` to that path.
- After rsync, **restart the app** so it loads the new code:  
  `cd /home/ubuntu/coin-digital-app && docker-compose restart django_gunicorn`

If Gaana still shows "AccessDenied (PutObject)" or TikTok is missing from the response, the running app is likely using old code — verify DEPLOY_PATH and restart.

---

## 1. Code / Files to Deploy on Live

Ensure these are present and up to date on the live server (e.g. `/home/ubuntu/coin-digital-app/RoyaltyWebsite/`):

| Item | Path | Purpose |
|------|------|---------|
| DDEX delivery view (Audiomack + Gaana + TikTok, _safe_deliver, logging) | `releases/views.py` | One-click delivery + takedown integration |
| Takedown helper in view | `releases/views.py` → `_send_ddex_takedown_to_dsps` | Sends DDEX takedown to both DSPs when user requests takedown |
| Audiomack delivery + takedown | `releases/audiomack_delivery.py` | New release + PurgeReleaseMessage takedown |
| Gaana delivery + takedown | `releases/gaana_delivery.py` | New release (SFTP-only when GAANA_SFTP_HOST set) + takedown |
| TikTok delivery | `releases/tiktok_delivery.py` | New release to TikTok S3 (MD5, batch_id) |
| DDEX builder (takedown terms for Gaana) | `releases/ddex_builder.py` | Used by gaana_delivery for takedown |
| Audiomack takedown builder | `releases/ddex_audiomack_takedown.py` | PurgeReleaseMessage |
| DSP registry | `releases/data/ddex_dsps.json` | audiomack, gaana with party_id, deal_profile |
| Preview & Distribute template | `releases/templates/volt_preview_distribute_info.html` | DDEX delivery button (admin only) |
| Management commands | `releases/management/commands/ddex_deliver_audiomack.py`, `ddex_deliver_gaana.py`, `build_ddex_takedown.py` | CLI delivery and takedown |

---

## 2. Environment Variables on Live (EC2)

In `.env` or `coin.env` (and loaded by the Django container):

**Audiomack (push to their S3):**

- `AUDIOMACK_S3_BUCKET` – e.g. `audiomack-contentimport`
- `AUDIOMACK_S3_PREFIX` – e.g. `coin-digital`
- AWS credentials that can write to that bucket (or same as `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` if Audiomack uses them)

**Gaana (SFTP):**  
Required so the app uses SFTP-only and does not call S3 PutObject (which can cause AccessDenied on live).

- `GAANA_SFTP_HOST` – e.g. `223.165.25.236`
- `GAANA_SFTP_PORT` – e.g. `22`
- `GAANA_SFTP_USERNAME` – e.g. `CoinDigital`
- `GAANA_SFTP_PASSWORD` – (password)
- `GAANA_SFTP_REMOTE_PATH` – **`upload`** (required; you land in backup/ and Gaana gave upload/ for new files)

**TikTok (S3):**

- `TIKTOK_S3_BUCKET`, `TIKTOK_S3_PREFIX`, `TIKTOK_AWS_ACCESS_KEY_ID`, `TIKTOK_AWS_SECRET_ACCESS_KEY` (see `TIKTOK_DDEX_DELIVERY.md`)

**Your S3 (for staging / Audiomack / app):**

- `AWS_STORAGE_BUCKET_NAME` – e.g. `coindigital-media`
- `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` (for Audiomack push and app; Gaana on live uses SFTP-only when GAANA_SFTP_HOST is set)

---

## 3. What Works on Live

- **DDEX delivery for Audiomack, Gaana & TikTok**  
  Button on Preview & Distribute (admin only) builds ERN 4.3, delivers to Audiomack S3, Gaana via SFTP (when GAANA_SFTP_HOST set), and TikTok S3. All three outcomes (and errors) are returned in the response.

- **Takedown request → DDEX feed**  
  When a user submits a **takedown request** for a release:
  1. Existing: `takedown_requested` is set, support email is sent.
  2. New: DDEX takedown is sent to both DSPs:
     - **Audiomack:** PurgeReleaseMessage uploaded to their S3 at `prefix/takedown/<delivery_id>/<upc>_PurgeRelease.xml` (or your S3 at `ddex/audiomack/takedown/...` if no Audiomack bucket).
     - **Gaana:** NewReleaseMessage with TakeDown uploaded to your S3 at `ddex/gaana/takedown/<date>/<upc>_takedown.xml` and to Gaana SFTP at `upload/takedown/<batch>/<upc>_takedown.xml`.

  Failures in DSP delivery are logged only; the user still sees “Your request to takedown this release is successfully submitted!”

- **Update**  
  Metadata or full release updates use the same DDEX builder (UpdateMessage / linked message). Delivering an update to Audiomack/Gaana is done via the same “DDEX delivery” button for the release (builds a new package). There is no separate “update request” button; use the one-click delivery for the updated release when needed.

---

## 4. After Deploy

1. Restart the Django container so it picks up code and env (e.g. `GAANA_SFTP_REMOTE_PATH=upload`):  
   `docker compose restart django_gunicorn`
2. Test DDEX delivery: open a release → Preview & Distribute → “DDEX delivery for Audiomack & Gaana” → confirm success for both (or one) and check logs if one fails.
3. Test takedown: submit a takedown request for a release that was previously delivered → confirm success message → check logs for “DDEX takedown sent to Audiomack” / “DDEX takedown sent to Gaana” or warnings.

---

## 5. Logs

- DDEX delivery (and UPC) is logged in the view: `DDEX delivery requested: primary_uuid=... upc=...`
- Takedown to DSPs: `DDEX takedown sent to Audiomack for release ...` / `... to Gaana ...` or `DDEX takedown to Audiomack/Gaana failed for release ...`
- Check Django/gunicorn logs on EC2 (e.g. `docker logs ... django_gunicorn`).
