#!/usr/bin/env bash
# Build Audiomack DDEX Insert for release 36329 (UPC 8905285301670)
# Run from RoyaltyWebsite: ./out_audiomack/build_36329.sh
# Or with Docker from django-docker-compose:
#   docker compose run --rm -v "$(pwd)/RoyaltyWebsite/out_audiomack:/app/out_audiomack" django_gunicorn /app/out_audiomack/build_36329.sh

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/.."
if command -v python3 >/dev/null 2>&1; then PY=python3; else PY=python; fi
$PY manage.py build_ddex 36329 --store audiomack --verbose --output out_audiomack/36329_8905285301670.xml
echo "Done. Output: out_audiomack/36329_8905285301670.xml"
