# Audiomack DDEX output – Release 36329 (UPC 8905285301670)

**Release:** https://royalties.coindigital.in/releases/release_info/36329

## Generate Insert XML

From the **RoyaltyWebsite** directory, with Django environment (venv with all deps, or Docker):

**Option A – Python (venv):**
```bash
cd RoyaltyWebsite
python manage.py build_ddex 36329 --store audiomack --verbose --output out_audiomack/36329_8905285301670.xml
```

**Option B – By UPC:**
```bash
python manage.py build_ddex --upc 8905285301670 --store audiomack --verbose --output out_audiomack/36329_8905285301670.xml
```

**Option C – Docker:**
```bash
# From django-docker-compose (parent of RoyaltyWebsite)
docker compose run --rm -v "$(pwd)/RoyaltyWebsite/out_audiomack:/app/out_audiomack" django_gunicorn python manage.py build_ddex 36329 --store audiomack --verbose --output /app/out_audiomack/36329_8905285301670.xml
```

After the command runs, the file **`36329_8905285301670.xml`** will be in this folder.

## Next step

Upload the XML (and any referenced assets per your batch layout) to your Audiomack S3 path, e.g.:

`audiomack-contentimport/coin-digital/<delivery_folder>/`

Use your existing S3 delivery process. If you use a batch folder, add an empty **BatchComplete_&lt;delivery_name&gt;.xml** in the Level 2 folder as recommended by Audiomack.
