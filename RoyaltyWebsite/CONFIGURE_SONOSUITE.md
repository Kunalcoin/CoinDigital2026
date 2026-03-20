# Configure Sonosuite (fix "Sonosuite not configured" on Approve)

When an admin clicks **Approve & send to Sonosuite**, the app must have Sonosuite credentials set. Otherwise you see: *"Sonosuite not configured (SONOSUITE_ADMIN_EMAIL, SONOSUITE_ADMIN_PASSWORD)."*

## What to set

Add these variables to the **environment** where the website runs. The app reads them via `os.getenv()`.

| Variable | Required | Example |
|----------|----------|---------|
| **SONOSUITE_ADMIN_EMAIL** | Yes | Your Sonosuite admin login email |
| **SONOSUITE_ADMIN_PASSWORD** | Yes | Your Sonosuite admin password |
| **SONOSUITE_API_BASE_URL** | No (default: https://coin.sonosuite.com) | `https://coin.sonosuite.com` — use this only; do not use any other base URL. |

## Where to set them

### 1. Local or same-server run (no Docker)

- **Option A:** In the **parent of RoyaltyWebsite** folder, create or edit **`.env`**  
  - Full path example: `live_code_complete_20260123_/django-docker-compose/.env`  
  - Add lines:
    ```env
    SONOSUITE_API_BASE_URL="https://coin.sonosuite.com"
    SONOSUITE_ADMIN_EMAIL="your-sonosuite-admin@example.com"
    SONOSUITE_ADMIN_PASSWORD="your-password"
    ```
- **Option B:** In **RoyaltyWebsite** folder, create or edit **`RoyaltyWebsite/.env`**  
  - Add the same three lines as above.

Then **restart the Django/gunicorn process** so it reloads the environment.

### 2. Docker

- Put the same variables in the **`.env`** file used by Docker (e.g. `django-docker-compose/.env`), or pass them as environment variables in `docker-compose.yml` or your deployment config.
- Restart the container after changing env.

### 3. Production (e.g. EC2, Elastic Beanstalk, etc.)

- In your deployment panel or server config, set **environment variables**:
  - `SONOSUITE_ADMIN_EMAIL`
  - `SONOSUITE_ADMIN_PASSWORD`
  - (optional) `SONOSUITE_API_BASE_URL`
- Restart the application server so it picks up the new variables.

## Verify

- Restart the app, then click **Approve & send to Sonosuite** again.  
- If credentials are correct, the release will be sent to Sonosuite and you’ll see success and operation IDs.  
- If you still see "not configured", the process is not reading the env file (wrong path or not restarted).
