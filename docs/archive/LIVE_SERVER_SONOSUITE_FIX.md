# Fix "Delivery is not configured" on Live Server

When approving releases for API delivery, if you see **"Delivery is not configured. Set admin credentials in .env"**, add these variables to your **live server's `.env` file**.

---

## Step-by-step

### 1. SSH into your EC2 server

```bash
ssh -i coin_new.pem ubuntu@54.147.21.20
```

### 2. Run the diagnostic (after deploying latest code)

```bash
cd /home/ubuntu/RoyaltyWebsite
python3 manage.py sonosuite_check
```

This shows whether the Sonosuite vars are set and which `.env` paths exist. Use it to verify the fix.

### 3. Create or edit `.env`

Put `.env` in your **home directory** (recommended; app will load `~/.env`):

```bash
nano ~/.env
```

Or in the app directory:

```bash
cd /home/ubuntu/RoyaltyWebsite
nano .env
```

### 4. Add these three lines (update with your real Sonosuite credentials)

```env
SONOSUITE_API_BASE_URL="https://coin.sonosuite.com"
SONOSUITE_ADMIN_EMAIL="your-sonosuite-admin@email.com"
SONOSUITE_ADMIN_PASSWORD="your-sonosuite-password"
```

Save and exit (Ctrl+O, Enter, Ctrl+X in nano).

### 5. Restart the Django container

```bash
sudo docker compose restart django_gunicorn
```

Or, if you use `docker-compose` (with hyphen):

```bash
sudo docker-compose restart django_gunicorn
```

### 6. Verify

Open your live site, go to a release’s Preview & Distribute page, and click **Approve**. The "Delivery is not configured" error should no longer appear.

---

## Note

- The `.env` file is **not** deployed by rsync (it’s excluded for security), so you must add these values directly on the server.
- If you already have a `coin.env` with these credentials locally, copy those three lines into the server’s `.env`.
