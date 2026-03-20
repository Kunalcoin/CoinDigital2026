# Changes to Push to Live EC2 Server

Use this list to deploy all local changes to your live website (royalties.coindigital.in).

---

## Summary of Changes

| # | Area | Description |
|---|------|-------------|
| 1 | Sonosuite credentials | Load env from multiple paths; docker-compose env_file |
| 2 | UPC format | Normalize to 13-digit for Sonosuite API; display 13-digit in UI |
| 3 | Bulk approve | Timeout + clearer feedback ("X out of Y delivered") |
| 4 | Approval flow | Auto-assign UPC/ISRC on submit; assign on preview for existing pending |
| 5 | Pending list | Submitted date column; sort by submission date (latest first) |
| 6 | Management commands | set_delivered, assign_pending_upc_isrc, sonosuite_check |
| 7 | CSV export | Sonosuite-compatible format (column names, padding) |
| 8 | Approve feedback | Show UPC + operation IDs in success message |

---

## Files to Deploy

### Django-docker-compose (project root)

| File | Change |
|------|--------|
| `docker-compose.yml` | Added `env_file: - .env` for Sonosuite vars |
| `start_local_server.sh` | Export Sonosuite vars from coin.env before runserver |
| `LIVE_SERVER_SONOSUITE_FIX.md` | New: Instructions for fixing "Delivery not configured" on live |
| `CHANGES_TO_PUSH_TO_LIVE.md` | New: This file |

### RoyaltyWebsite/RoyaltyWebsite (settings)

| File | Change |
|------|--------|
| `settings.py` | Fallback load `~/.env` when Sonosuite vars missing |

### RoyaltyWebsite/releases

| File | Change |
|------|--------|
| `models.py` | Added `submitted_for_approval_at` field |
| `views.py` | Submit assigns UPC/ISRC; preview assigns for pending; submitted date in list; approve message with operation IDs; bulk approve "X out of Y" message |
| `processor.py` | UPC 13-digit in get_pd_context + context_generator; CSV format for Sonosuite (track column names, metadata padding) |
| `sonosuite_client.py` | Load env from /app; _normalize_upcs_to_13; normalize in delivery + get_releases |
| `upc_utils.py` | No changes (already had normalize_upc_to_13) |
| `templates/volt_releases.html` | Bulk approve timeout 300000; better error msg; Submitted column for pending; success message |
| `migrations/0012_add_submitted_for_approval_at.py` | New: Migration for submitted_for_approval_at |
| `management/commands/sonosuite_check.py` | New: Diagnostic for Sonosuite credentials |
| `management/commands/set_delivered.py` | New: Move releases to Delivered by UPC |
| `management/commands/assign_pending_upc_isrc.py` | New: Assign UPC/ISRC to pending releases missing them |

### RoyaltyWebsite (optional)

| File | Change |
|------|--------|
| `upcs_to_delivered.txt` | Optional: Sample UPC list for set_delivered |
| `sql_set_delivered.sql` | Optional: SQL template for manual DB update |

---

## Deployment Steps

### 1. Rsync code to EC2

From your local machine:

```bash
cd "/Users/ashimagoel/Documents/COIN DIGTAL NEW Working/live_code_complete_20260123_/django-docker-compose"
./deploy_sonosuite_to_live.sh
```

Or manually:

```bash
rsync -avz --progress -e "ssh -i coin_new.pem -o StrictHostKeyChecking=accept-new" \
  --exclude '__pycache__' --exclude '*.pyc' --exclude '.env' --exclude 'coin.env' \
  --exclude 'db.sqlite3' --exclude 'media/' --exclude '.git/' --exclude 'node_modules/' \
  RoyaltyWebsite/ ubuntu@54.147.21.20:/home/ubuntu/RoyaltyWebsite/
```

Then sync docker-compose and related files to the coin-digital-app directory (if your deploy copies there):

```bash
# Copy docker-compose.yml, etc. to server
scp -i coin_new.pem docker-compose.yml ubuntu@54.147.21.20:/home/ubuntu/coin-digital-app/
```

### 2. Run migrations on server

```bash
ssh -i coin_new.pem ubuntu@54.147.21.20
sudo docker exec -it coin-digital-app-django_gunicorn-1 python manage.py migrate releases
```

### 3. Rebuild Docker (if docker-compose.yml changed)

```bash
cd /home/ubuntu/coin-digital-app
sudo docker compose build django_gunicorn --no-cache
sudo docker compose up -d django_gunicorn
```

Or just restart if no Dockerfile/yml change:

```bash
sudo docker compose restart django_gunicorn
```

### 4. Verify Sonosuite credentials on server

Ensure `.env` in `/home/ubuntu/coin-digital-app/` has:

```
SONOSUITE_API_BASE_URL="https://coin.sonosuite.com"
SONOSUITE_ADMIN_EMAIL="your-email"
SONOSUITE_ADMIN_PASSWORD="your-password"
```

---

## Post-deploy Checklist

- [ ] Migrations ran successfully (0012)
- [ ] Sonosuite credentials in server .env
- [ ] Test single approve on a pending release
- [ ] Test bulk approve (select 1–2 releases)
- [ ] Test Download Selected — CSV should be Sonosuite-compatible
- [ ] Pending for Approval shows Submitted column, sorted by latest first
- [ ] New submissions get UPC/ISRC assigned automatically

---

## Quick File List (for rsync/copy)

```
django-docker-compose/docker-compose.yml
django-docker-compose/start_local_server.sh
django-docker-compose/LIVE_SERVER_SONOSUITE_FIX.md
RoyaltyWebsite/RoyaltyWebsite/settings.py
RoyaltyWebsite/releases/models.py
RoyaltyWebsite/releases/views.py
RoyaltyWebsite/releases/processor.py
RoyaltyWebsite/releases/sonosuite_client.py
RoyaltyWebsite/releases/templates/volt_releases.html
RoyaltyWebsite/releases/migrations/0012_add_submitted_for_approval_at.py
RoyaltyWebsite/releases/management/commands/sonosuite_check.py
RoyaltyWebsite/releases/management/commands/set_delivered.py
RoyaltyWebsite/releases/management/commands/assign_pending_upc_isrc.py
```
