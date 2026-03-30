#!/bin/bash
# Push this RoyaltyWebsite folder (live replica) to live server via SSH.
# Server details from coin.env. PEM: coin_new.pem in this folder.
# Run from this folder: chmod +x deploy_to_server.sh && ./deploy_to_server.sh

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOCAL_ROOT="$SCRIPT_DIR"
COIN_ENV="${LOCAL_ROOT}/coin.env"

if [ -f "$COIN_ENV" ]; then
  set -a
  source "$COIN_ENV" 2>/dev/null || true
  set +a
fi

SERVER_USER="${DEPLOY_USER:-ubuntu}"
SERVER_HOST="${DEPLOY_HOST:-${EC2_DB_HOST:-}}"
# Deploy to the path the running app uses (e.g. Docker app at coin-digital-app/RoyaltyWebsite)
REMOTE_PATH="${DEPLOY_PATH:-${DEPLOY_DOCKER_PATH:+${DEPLOY_DOCKER_PATH}/RoyaltyWebsite}}"
REMOTE_PATH="${REMOTE_PATH:-/home/ubuntu/RoyaltyWebsite}"
if [ -n "$DEPLOY_SSH_KEY" ] && [ -f "$DEPLOY_SSH_KEY" ]; then
  SSH_KEY="$DEPLOY_SSH_KEY"
elif [ -f "${LOCAL_ROOT}/coin_new.pem" ]; then
  SSH_KEY="${LOCAL_ROOT}/coin_new.pem"
elif [ -f "${LOCAL_ROOT}/../coin_new.pem" ]; then
  SSH_KEY="${LOCAL_ROOT}/../coin_new.pem"
else
  SSH_KEY=""
fi

if [ -z "$SERVER_HOST" ]; then
  echo "Error: DEPLOY_HOST or EC2_DB_HOST not set in coin.env"
  exit 1
fi
if [ -z "$SSH_KEY" ] || [ ! -f "$SSH_KEY" ]; then
  echo "Error: coin_new.pem not found in this folder. Tried: ${LOCAL_ROOT}/coin_new.pem"
  exit 1
fi

chmod 400 "$SSH_KEY" 2>/dev/null || true
echo "Deploying FROM: $LOCAL_ROOT"
echo "Using SSH key: $SSH_KEY"
echo "Pushing to: ${SERVER_USER}@${SERVER_HOST}:${REMOTE_PATH}"
# Quote key path so spaces (e.g. "COIN DIGTAL NEW Working") don't break SSH
RSYNC_SSH="ssh -i '$SSH_KEY' -o StrictHostKeyChecking=accept-new"
rsync -avz --progress -e "$RSYNC_SSH" \
  --exclude '__pycache__' \
  --exclude '*.pyc' \
  --exclude '.env' \
  --exclude 'coin.env' \
  --exclude 'db.sqlite3' \
  --exclude 'media/' \
  --exclude '.git/' \
  --exclude 'node_modules/' \
  --exclude '.DS_Store' \
  "$LOCAL_ROOT/" \
  "${SERVER_USER}@${SERVER_HOST}:${REMOTE_PATH}/"

if [ $? -eq 0 ]; then
  echo "Done. Code is at ${REMOTE_PATH} on the server."
  echo ""
  echo "IMPORTANT — Django must read files from this path on the host:"
  echo "  If docker-compose does NOT bind-mount the app (e.g.  ./RoyaltyWebsite:/app ),"
  echo "  rsync updates the disk but the container still uses the OLD code from the image."
  echo "  Fix: add that volume to django_gunicorn, OR rebuild: docker compose build --no-cache django_gunicorn && docker compose up -d"
  echo ""
  echo "Restart the app so it loads new code:"
  echo "  ssh -i \"$SSH_KEY\" ${SERVER_USER}@${SERVER_HOST}"
  echo "Then on the server: cd ${DEPLOY_DOCKER_PATH:-/home/ubuntu/coin-digital-app} && docker-compose restart django_gunicorn"
  echo "(Or: sudo systemctl restart gunicorn if not using Docker.)"
  echo "Ensure server .env has GAANA_SFTP_HOST (and TIKTOK_S3_*) if you use those deliveries."
else
  echo "Rsync failed. Check SSH key and paths."
  exit 1
fi
