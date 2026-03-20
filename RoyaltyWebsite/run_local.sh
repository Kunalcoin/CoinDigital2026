#!/usr/bin/env bash
# Run the site locally with SQLite (no MySQL needed).
# From django-docker-compose: ./RoyaltyWebsite/run_local.sh
# Or from RoyaltyWebsite: ./run_local.sh

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

# Load .env / coin.env if present (for SECRET_KEY, AWS, etc.)
if [ -f .env ]; then
    set -a
    source .env 2>/dev/null || true
    set +a
fi
if [ -f coin.env ]; then
    set -a
    source coin.env 2>/dev/null || true
    set +a
fi
# Use LOCAL_SQLITE so no MySQL is needed. (Writes .env.run_local so it overrides .env.)
# For first-time SQLite, migrations may need the DB; if you hit errors, use "Run with existing MySQL" in RUN_LOCALLY.md instead.
echo "SERVER=LOCAL_SQLITE" > "$PROJECT_ROOT/.env.run_local"
[ -z "$SECRET_KEY" ] && echo "SECRET_KEY=dev-secret-key-change-in-production" >> "$PROJECT_ROOT/.env.run_local"

cd "$SCRIPT_DIR"
echo "Running migrations..."
python3 manage.py migrate --noinput
echo "Starting server at http://127.0.0.1:8000"
python3 manage.py runserver 0.0.0.0:8000
