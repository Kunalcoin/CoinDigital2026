#!/bin/bash
# Run the site locally with SQLite (no MySQL/EC2 needed). Use for testing e.g. Apple Music Merlin Bridge.
# Loads coin.env and .env for S3, Merlin Bridge, etc.; overrides SERVER=LOCAL_SQLITE so DB is SQLite.
# From django-docker-compose: ./run_local_sqlite.sh
# Access at http://127.0.0.1:8000

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$SCRIPT_DIR"
DJANGO_DIR="$SCRIPT_DIR/RoyaltyWebsite"

# Load env but we will force SERVER=LOCAL_SQLITE
if [ -f "$PROJECT_ROOT/coin.env" ]; then
  set -a
  source "$PROJECT_ROOT/coin.env" 2>/dev/null || true
  set +a
fi
if [ -f "$PROJECT_ROOT/.env" ]; then
  set -a
  source "$PROJECT_ROOT/.env" 2>/dev/null || true
  set +a
fi
export SERVER=LOCAL_SQLITE

cd "$DJANGO_DIR"
PORT="${1:-8000}"

echo "=========================================="
echo "Starting Django (SQLite) at http://127.0.0.1:$PORT"
echo "=========================================="
python3 manage.py migrate --no-input 2>/dev/null || true
python3 manage.py runserver 0.0.0.0:"$PORT"
