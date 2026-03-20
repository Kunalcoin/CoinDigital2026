#!/bin/bash
# Run the site locally using live DB (db4 on EC2)
# From django-docker-compose: ./start_local_with_db4.sh

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Temporarily disable .env.run_local so SERVER=EC2 from coin.env is used
RESTORE_ENV=0
if [ -f .env.run_local ]; then
  mv .env.run_local .env.run_local.bak
  RESTORE_ENV=1
  echo "Using EC2 db4 (live data)"
fi
# Restore on exit (Ctrl+C or normal exit)
cleanup() {
  if [ $RESTORE_ENV -eq 1 ] && [ -f .env.run_local.bak ]; then
    mv .env.run_local.bak .env.run_local
    echo "Restored .env.run_local"
  fi
}
trap cleanup EXIT

# Load coin.env for EC2_DB_* vars
if [ -f coin.env ]; then
  set -a
  source coin.env
  set +a
fi

# Ensure SERVER=EC2 (use live db4)
export SERVER=EC2

cd RoyaltyWebsite

# Install deps if needed
if ! python3 -c "import django" 2>/dev/null; then
  echo "Installing dependencies..."
  pip3 install -r ../requirements.txt
fi

echo ""
echo "=============================================="
echo "  Local server: http://127.0.0.1:8000"
echo "  Using DB: db4 on ec2-54-84-50-236 (live data)"
echo "  Press Ctrl+C to stop"
echo "=============================================="
echo ""

python3 manage.py runserver 0.0.0.0:8000
