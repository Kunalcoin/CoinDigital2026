#!/bin/bash
# Run the site locally at http://localhost:8000
# Uses .env/coin.env from this folder. SERVER=EC2 = use remote DB (need network). SERVER=LOCAL = use local MySQL.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR" || exit 1

# Ensure .env exists (Django loads it from here)
if [ ! -f ".env" ]; then
  [ -f "coin.env" ] && ln -sf coin.env .env || { echo "Error: No coin.env or .env"; exit 1; }
fi

# Export Sonosuite (and other) vars so they're in the process env when runserver runs
if [ -f "coin.env" ]; then
  set -a
  # shellcheck source=coin.env
  . ./coin.env
  set +a
fi

cd RoyaltyWebsite || exit 1

# Install deps if needed
if ! python3 -c "import django" 2>/dev/null; then
  echo "Installing dependencies..."
  pip3 install -r ../requirements.txt
fi

echo "Running migrations..."
python3 manage.py migrate --no-input 2>/dev/null || true

echo ""
echo "=============================================="
echo "  Local server: http://localhost:8000"
echo "  Press Ctrl+C to stop"
echo "=============================================="
echo ""
python3 manage.py runserver 8000
