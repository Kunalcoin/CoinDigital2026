#!/usr/bin/env bash
# Run the site locally using db4 – credentials from .env in django-docker-compose.
# Ensure .env has: SERVER=LOCAL, LOCAL_DB_HOST, LOCAL_DB_USER, LOCAL_DB_PASSWORD
# From django-docker-compose: ./RoyaltyWebsite/run_local_with_db4.sh
# Or from RoyaltyWebsite: ./run_local_with_db4.sh

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Load .env and coin.env from django-docker-compose (db4 credentials)
if [ -f "$PROJECT_ROOT/.env" ]; then
  set -a
  source "$PROJECT_ROOT/.env" 2>/dev/null || true
  set +a
fi
if [ -f "$PROJECT_ROOT/coin.env" ]; then
  set -a
  source "$PROJECT_ROOT/coin.env" 2>/dev/null || true
  set +a
fi

# Use MySQL db4 (SERVER=LOCAL). Overrides .env.run_local if present.
export SERVER=LOCAL

cd "$SCRIPT_DIR"
PORT="${1:-8000}"
echo "Using db4 (SERVER=LOCAL). Credentials from .env."
echo "Starting server at http://127.0.0.1:$PORT"
python3 manage.py runserver 0.0.0.0:"$PORT"
