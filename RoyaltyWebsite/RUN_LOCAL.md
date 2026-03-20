# Run the website locally

You can run the Royalty Website on your machine for development or testing (e.g. to use the **Distribute / Approve** button to deliver to Audiomack only).

---

## Option 1: Docker (recommended if you use Docker)

From the **django-docker-compose** folder (parent of RoyaltyWebsite):

```bash
cd /path/to/django-docker-compose
docker compose up --build
```

- Website: **http://localhost:8000** (or port 80 via nginx if configured)
- Ensure `.env` exists in `django-docker-compose` with DB, AWS, and any Sonosuite/Audiomack vars (see below).

---

## Option 2: Python on your machine

### 1. Prerequisites

- **Python 3.8+**
- **MySQL** (or access to a MySQL database)
- **Redis** (optional; needed only for Celery. Without it, the app still starts and the delivery button works.)

### 2. Environment file

Copy or create **`.env`** in the **RoyaltyWebsite** folder (or in **django-docker-compose** if you run from there). Include at least:

- **Database:** `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT`
- **Django:** `SECRET_KEY`, `DEBUG=True` for local
- **AWS (for uploads and optional Audiomack S3):** `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_STORAGE_BUCKET_NAME`
- **Audiomack-only delivery (Approve button sends only to Audiomack):**  
  `DELIVER_ONLY_AUDIOMACK=True`  
  - To upload to S3: `AUDIOMACK_S3_BUCKET=audiomack-contentimport`, `AUDIOMACK_S3_PREFIX=coin-digital` (use your actual bucket/prefix if different). Same AWS credentials as your main bucket.  
  - If `AUDIOMACK_S3_BUCKET` is not set, the DDEX XML is still built and saved under `RoyaltyWebsite/out_audiomack/<upc>.xml` and the release is marked approved.

### 3. Install dependencies

From **django-docker-compose** (where `requirements.txt` lives):

```bash
cd /path/to/django-docker-compose
python3 -m venv venv
source venv/bin/activate   # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

If you hit **Celery/Redis** errors when starting Django, you can still run the site: Celery is optional for the delivery flow. The app will start even if Redis is not installed.

### 4. Run migrations

```bash
cd RoyaltyWebsite
python manage.py migrate
```

### 5. Start the dev server

```bash
python manage.py runserver
```

- Website: **http://127.0.0.1:8000**
- Log in with an admin user to use **Approve** (delivery) on a release.

---

## Delivery (two separate actions)

- **Approve** – Sends to stores via the **Sonosuite API** (unchanged). No DDEX.
- **DDEX delivery for Audiomack** – A **separate button** on Preview & Distribute (admin). Builds DDEX ERN 4.3 and uploads to Audiomack S3 (set `AUDIOMACK_S3_BUCKET`, `AUDIOMACK_S3_PREFIX` in .env). Does not change approval status.

See **DDEX_DELIVERY_FLOW.md** for details.

---

## Summary

| Goal                         | Action                                                                 |
|-----------------------------|-------------------------------------------------------------------------|
| Run site locally            | Docker: `docker compose up` **or** Python: `pip install -r requirements.txt` then `python manage.py runserver` from RoyaltyWebsite. |
| Approve = deliver only Audiomack | Set `DELIVER_ONLY_AUDIOMACK=True` and (optionally) `AUDIOMACK_S3_BUCKET`, `AUDIOMACK_S3_PREFIX` in `.env`. |
| Run without Redis/Celery    | No change needed; Celery is optional and the app still starts.          |
