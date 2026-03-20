# Run the site locally

Use this to develop and test (tracks view, processing, DDEX package flow) on your machine before deploying to live.

## Use my db4 credentials from .env

If your **.env** (in **django-docker-compose**) already has db4 credentials:

1. Ensure **.env** contains:
   - `SERVER=LOCAL`
   - `LOCAL_DB_HOST=...` (your MySQL host)
   - `LOCAL_DB_USER=...`
   - `LOCAL_DB_PASSWORD=...`
   - `SECRET_KEY=...` (any value for local)

2. Run (from **django-docker-compose**):
   ```bash
   ./RoyaltyWebsite/run_local_with_db4.sh
   ```
   Or use port **8001** if 8000 is in use:
   ```bash
   ./RoyaltyWebsite/run_local_with_db4.sh 8001
   ```
   Then open **http://127.0.0.1:8000** or **http://127.0.0.1:8001**.

3. From **RoyaltyWebsite** folder you can also run:
   ```bash
   cd "/Users/ashimagoel/Documents/COIN DIGTAL NEW Working/live_code_complete_20260123_/django-docker-compose/RoyaltyWebsite"
   SERVER=LOCAL python3 manage.py runserver 0.0.0.0:8001
   ```
   (Settings loads .env from django-docker-compose; `SERVER=LOCAL` ensures db4 is used even if .env.run_local exists.)

---

## Quick start: run with your existing MySQL (recommended)

Use your **current database** (e.g. EC2 MySQL) so the site runs locally with real data.

1. In **django-docker-compose**, create or edit **.env** and set:
   ```bash
   SERVER=LOCAL
   LOCAL_DB_HOST=ec2-54-84-50-236.compute-1.amazonaws.com
   LOCAL_DB_USER=admincoin
   LOCAL_DB_PASSWORD=<your-db-password>
   SECRET_KEY=any-secret-for-local
   ```
   (Use the same host/user/password as your EC2 DB.)

2. Install and run:
   ```bash
   cd "/Users/ashimagoel/Documents/COIN DIGTAL NEW Working/live_code_complete_20260123_/django-docker-compose"
   pip install -r requirements.txt
   cd RoyaltyWebsite
   python3 manage.py runserver
   ```
3. Open **http://127.0.0.1:8000** and log in.

If the track page shows “Unknown column … audio_wav_url”, add the missing columns to MySQL (see `releases/migrations/fix_track_columns.sql` or run the four `ALTER TABLE` statements from that file).

---

## Port already in use?

If you see **"Error: That port is already in use"**:

- **Option A – Use another port (e.g. 8001):**
  ```bash
  cd "/Users/ashimagoel/Documents/COIN DIGTAL NEW Working/live_code_complete_20260123_/django-docker-compose/RoyaltyWebsite"
  SERVER=LOCAL_SQLITE python3 manage.py runserver 0.0.0.0:8001
  ```
  Then open **http://127.0.0.1:8001**

- **Option B – Free port 8000** (macOS):
  ```bash
  lsof -ti:8000 | xargs kill -9
  ```
  Then run `runserver 0.0.0.0:8000` again.

---

## Optional: run with SQLite (no MySQL)

From **django-docker-compose**:

```bash
./RoyaltyWebsite/run_local.sh
```

This sets `SERVER=LOCAL_SQLITE` and starts the server. **Note:** Some migrations are written for MySQL; if SQLite migrations fail, use “Run with your existing MySQL” above. For a fresh SQLite DB, create a user: `cd RoyaltyWebsite && SERVER=LOCAL_SQLITE python manage.py createsuperuser` (after ensuring `.env.run_local` exists with `SERVER=LOCAL_SQLITE`).

---

## Option 1: Django runserver (no Docker)

1. **Open a terminal** and go to the project root that contains both `RoyaltyWebsite` and `.env`:
   ```bash
   cd "/Users/ashimagoel/Documents/COIN DIGTAL NEW Working/live_code_complete_20260123_/django-docker-compose"
   ```

2. **Create a virtual environment** (recommended):
   ```bash
   python3 -m venv venv
   source venv/bin/activate   # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies** (requirements are in parent folder):
   ```bash
   pip install -r requirements.txt
   ```

4. **Choose database:**
   - **SQLite (easiest):** In `.env` (in `django-docker-compose`) set `SERVER=LOCAL_SQLITE`. No MySQL needed.
   - **Local MySQL:** Set `SERVER=LOCAL` and `LOCAL_DB_HOST`, `LOCAL_DB_USER`, `LOCAL_DB_PASSWORD` in `.env`.

5. **Run the server** from the `RoyaltyWebsite` app folder:
   ```bash
   cd RoyaltyWebsite
   python manage.py runserver
   ```
   Or use the script: from `django-docker-compose`, run `./RoyaltyWebsite/run_local.sh` (uses SQLite).

6. **Open in browser:** [http://127.0.0.1:8000](http://127.0.0.1:8000)

   Log in and test: releases, submit for approval, admin approve, tracks view, etc.

7. **DDEX package flow (optional):** To test submit → build package, approve → distribute, set in `.env` (in `django-docker-compose`):  
   `DELIVERY_STORES=audiomack,gaana,tiktok`  
   and configure each store’s credentials (Audiomack S3, Gaana SFTP, TikTok S3). Then submit for approval builds the package; admin approve distributes to all configured stores.

8. **Track audio (WAV → MP3/FLAC):** When you upload a WAV on a track and save, the app converts it to MP3 and FLAC (same quality). **FFmpeg must be installed** on the machine running the app (local or server): macOS: `brew install ffmpeg`; Ubuntu: `sudo apt-get install ffmpeg`.

When everything is sorted locally, deploy to live with `./deploy_to_server.sh` from `RoyaltyWebsite`.

---

## Option 2: Docker Compose (same as production)

From the `django-docker-compose` folder:

```bash
cd "/Users/ashimagoel/Documents/COIN DIGTAL NEW Working/live_code_complete_20260123_/django-docker-compose"
docker-compose up --build
```

Then open [http://localhost:8000](http://localhost:8000) (or port 80 if nginx is used). Stop with `Ctrl+C` or `docker-compose down`.

---

## Local vs live

- **Local:** Use `runserver` or Docker; `.env` and DB (e.g. SQLite or local MySQL) are for development. No deploy.
- **Live:** After testing locally, run `RoyaltyWebsite/deploy_to_server.sh` and restart the app on the server.
