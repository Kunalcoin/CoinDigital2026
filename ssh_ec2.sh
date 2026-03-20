#!/bin/bash
# Connect to EC2 via SSH. Run from django-docker-compose folder: ./ssh_ec2.sh
# Or use the commands below directly in Terminal.

# Option A: Using coin_new.pem (this folder) and IP 54.147.21.20
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
KEY="${SCRIPT_DIR}/coin_new.pem"
USER="ubuntu"
HOST="54.147.21.20"

# Option B: Using Mac SSH key and hostname (uncomment to use)
# KEY="/Users/ashimagoel/.ssh/id_ed25519"
# HOST="ec2-54-84-50-236.compute-1.amazonaws.com"

if [ ! -f "$KEY" ]; then
  echo "SSH key not found: $KEY"
  echo "Use: ssh -i /path/to/your-key.pem ubuntu@YOUR_EC2_IP"
  exit 1
fi
chmod 400 "$KEY" 2>/dev/null || true
echo "Connecting to $USER@$HOST ..."
exec ssh -i "$KEY" -o StrictHostKeyChecking=accept-new "$USER@$HOST" "$@"
