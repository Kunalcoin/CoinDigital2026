#!/bin/bash
# Backup live website from EC2 and download to local.
# Run from django-docker-compose folder: chmod +x backup_live_from_ec2.sh && ./backup_live_from_ec2.sh
# Backup name: coindigital12032026latestbackup

set -e
BACKUP_NAME="coindigital12032026latestbackup"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
KEY="${SCRIPT_DIR}/coin_new.pem"
USER="ubuntu"
HOST="54.147.21.20"
REMOTE_APP_PATH="/home/ubuntu/coin-digital-app"
LOCAL_SAVE_DIR="${HOME}/Downloads"

if [ ! -f "$KEY" ]; then
  echo "SSH key not found: $KEY"
  echo "Put your EC2 .pem key at: $KEY"
  echo "Or set KEY= path to your .pem and run again."
  exit 1
fi
chmod 400 "$KEY" 2>/dev/null || true

echo "=== 1. Creating backup on EC2 (${BACKUP_NAME}.tar.gz) ... ==="
ssh -i "$KEY" -o StrictHostKeyChecking=accept-new "$USER@$HOST" "cd /home/ubuntu && tar czf ${BACKUP_NAME}.tar.gz coin-digital-app 2>/dev/null || tar czf ${BACKUP_NAME}.tar.gz -C /home/ubuntu coin-digital-app"
echo "=== 2. Downloading backup to ${LOCAL_SAVE_DIR} ... ==="
scp -i "$KEY" -o StrictHostKeyChecking=accept-new "$USER@$HOST:/home/ubuntu/${BACKUP_NAME}.tar.gz" "${LOCAL_SAVE_DIR}/"
echo "=== 3. Removing backup from EC2 (to save space) ... ==="
ssh -i "$KEY" "$USER@$HOST" "rm -f /home/ubuntu/${BACKUP_NAME}.tar.gz"
echo "=== Done. Backup saved to: ${LOCAL_SAVE_DIR}/${BACKUP_NAME}.tar.gz ==="
echo "To extract locally: cd /path/to/folder && tar xzf ${LOCAL_SAVE_DIR}/${BACKUP_NAME}.tar.gz"
