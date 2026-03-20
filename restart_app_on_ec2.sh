#!/bin/bash
# Restart the Django app on live EC2 (so it picks up env changes e.g. MERLIN_BRIDGE_SFTP_REMOTE_PATH).
# Run from django-docker-compose folder: ./restart_app_on_ec2.sh

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
KEY="${SCRIPT_DIR}/coin_new.pem"
USER="ubuntu"
HOST="${DEPLOY_HOST:-54.147.21.20}"
DOCKER_PATH="${DEPLOY_DOCKER_PATH:-/home/ubuntu/coin-digital-app}"

if [ -f "$SCRIPT_DIR/coin.env" ]; then
  set -a
  source "$SCRIPT_DIR/coin.env" 2>/dev/null || true
  set +a
  [ -n "$DEPLOY_HOST" ] && HOST="$DEPLOY_HOST"
  [ -n "$DEPLOY_DOCKER_PATH" ] && DOCKER_PATH="$DEPLOY_DOCKER_PATH"
fi
if [ -n "$DEPLOY_SSH_KEY" ] && [ -f "$DEPLOY_SSH_KEY" ]; then
  KEY="$DEPLOY_SSH_KEY"
fi

if [ ! -f "$KEY" ]; then
  echo "Error: SSH key not found: $KEY"
  exit 1
fi
chmod 400 "$KEY" 2>/dev/null || true

echo "Restarting app on $USER@$HOST (path: $DOCKER_PATH) ..."
ssh -i "$KEY" -o StrictHostKeyChecking=accept-new "$USER@$HOST" "export DOCKER_PATH='$DOCKER_PATH'; bash -s" << 'REMOTE'
  if cd "$DOCKER_PATH" 2>/dev/null && (sudo docker compose ps 2>/dev/null | grep -q django) || (sudo docker-compose ps 2>/dev/null | grep -q django); then
    echo "Restarting Docker container django_gunicorn..."
    (cd "$DOCKER_PATH" && sudo docker compose restart django_gunicorn 2>/dev/null) || \
    (cd "$DOCKER_PATH" && sudo docker-compose restart django_gunicorn 2>/dev/null) || exit 1
    echo "Done."
  elif systemctl is-active --quiet gunicorn 2>/dev/null; then
    echo "Restarting gunicorn (systemd)..."
    sudo systemctl restart gunicorn
    echo "Done."
  else
    echo "Could not find Django (docker or gunicorn). Run manually on server:"
    echo "  cd $DOCKER_PATH && sudo docker compose restart django_gunicorn"
    echo "  or: sudo systemctl restart gunicorn"
    exit 1
  fi
REMOTE

echo "App restarted."
