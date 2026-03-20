#!/bin/bash
# Deploy Sonosuite API + approval workflow to live EC2.
# Run from django-docker-compose folder: ./deploy_sonosuite_to_live.sh
# Uses same key/host as ssh_ec2.sh unless you set DEPLOY_HOST/DEPLOY_DOCKER_PATH in coin.env (RoyaltyWebsite/coin.env).

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOCAL_ROYALTY="$SCRIPT_DIR/RoyaltyWebsite"
KEY="$SCRIPT_DIR/coin_new.pem"
USER="ubuntu"
# Default: same as ssh_ec2.sh. Override via RoyaltyWebsite/coin.env (DEPLOY_HOST, DEPLOY_DOCKER_PATH)
HOST="${DEPLOY_HOST:-54.147.21.20}"
# Docker project root on server (has docker-compose.yml). RoyaltyWebsite rsyncs into it.
DOCKER_PATH="${DEPLOY_DOCKER_PATH:-/home/ubuntu/coin-digital-app}"
REMOTE_ROYALTY="$DOCKER_PATH/RoyaltyWebsite"

if [ -f "$LOCAL_ROYALTY/coin.env" ]; then
  set -a
  source "$LOCAL_ROYALTY/coin.env" 2>/dev/null || true
  set +a
  [ -n "$DEPLOY_HOST" ] && HOST="$DEPLOY_HOST"
  [ -n "$DEPLOY_DOCKER_PATH" ] && DOCKER_PATH="$DEPLOY_DOCKER_PATH" && REMOTE_ROYALTY="$DOCKER_PATH/RoyaltyWebsite"
fi
if [ -n "$DEPLOY_SSH_KEY" ] && [ -f "$DEPLOY_SSH_KEY" ]; then
  KEY="$DEPLOY_SSH_KEY"
fi

if [ ! -f "$KEY" ]; then
  echo "Error: SSH key not found: $KEY"
  exit 1
fi
if [ ! -d "$LOCAL_ROYALTY" ]; then
  echo "Error: RoyaltyWebsite folder not found: $LOCAL_ROYALTY"
  exit 1
fi

chmod 400 "$KEY" 2>/dev/null || true
echo "=== Deploying Sonosuite + approval workflow to live ==="
echo "From: $LOCAL_ROYALTY"
echo "To:   $USER@$HOST:$REMOTE_ROYALTY"
echo "Key:  $KEY"
echo ""

# 1. Rsync code (exclude env, cache, media, .git)
RSYNC_SSH="ssh -i '$KEY' -o StrictHostKeyChecking=accept-new"
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
  --exclude 'staticfiles/' \
  "$LOCAL_ROYALTY/" \
  "$USER@$HOST:$REMOTE_ROYALTY/"

echo ""
echo "=== Running migrations and restart on server ==="
# 2. On server: migrate inside Docker (app runs in container; host may not have Django)
if ssh -i "$KEY" -o StrictHostKeyChecking=accept-new "$USER@$HOST" "sudo docker ps -q -f name=django" 2>/dev/null | grep -q .; then
  echo "Running migrations inside Docker container..."
  ssh -i "$KEY" "$USER@$HOST" 'CONTAINER=$(sudo docker ps -q -f name=django | head -1); sudo docker exec $CONTAINER python manage.py migrate releases --noinput'
else
  echo "Docker not found, trying direct python3..."
  ssh -i "$KEY" -o StrictHostKeyChecking=accept-new "$USER@$HOST" "cd $REMOTE_ROYALTY && python3 manage.py migrate releases --noinput" || true
fi
echo "Migrations done."

# 3. Rebuild and restart Docker (code is COPY'd at build time — restart alone does NOT pick up new code)
if ssh -i "$KEY" "$USER@$HOST" "cd $DOCKER_PATH && sudo docker compose ps 2>/dev/null | grep -q django" 2>/dev/null; then
  echo "Rebuilding and restarting Django (Docker Compose)..."
  ssh -i "$KEY" "$USER@$HOST" "cd $DOCKER_PATH && sudo docker compose build django_gunicorn --no-cache && sudo docker compose up -d django_gunicorn" 2>/dev/null || \
  ssh -i "$KEY" "$USER@$HOST" "cd $DOCKER_PATH && sudo docker-compose build django_gunicorn --no-cache && sudo docker-compose up -d django_gunicorn" 2>/dev/null || true
elif ssh -i "$KEY" "$USER@$HOST" "systemctl is-active --quiet gunicorn" 2>/dev/null; then
  echo "Restarting gunicorn (systemd)..."
  ssh -i "$KEY" "$USER@$HOST" "sudo systemctl restart gunicorn"
elif ssh -i "$KEY" "$USER@$HOST" "supervisorctl status 2>/dev/null | grep -q django" 2>/dev/null; then
  echo "Restarting Django (supervisor)..."
  ssh -i "$KEY" "$USER@$HOST" "sudo supervisorctl restart django"
else
  echo "Could not auto-detect Docker. Rebuild manually on server:"
  echo "  cd $DOCKER_PATH && sudo docker compose build django_gunicorn --no-cache && sudo docker compose up -d django_gunicorn"
  echo "  or: sudo systemctl restart gunicorn"
fi

echo ""
echo "=== Done. Sonosuite + approval workflow is deployed. ==="
echo "Set on server (e.g. in .env or coin.env): SONOSUITE_API_BASE_URL, SONOSUITE_ADMIN_EMAIL, SONOSUITE_ADMIN_PASSWORD"
