#!/bin/bash
# Set up Git on EC2 (live instance) and push code to GitHub.
# Run from django-docker-compose folder: chmod +x setup_git_on_ec2_and_push.sh && ./setup_git_on_ec2_and_push.sh
#
# Prerequisites:
# - EC2 has git installed (script will try: sudo apt-get install -y git)
# - GitHub repo exists: https://github.com/Kunalcoin/CoinDigital2026
# - GitHub auth from EC2: when 'git push' runs, use a Personal Access Token (PAT) as the password
#   (Settings → Developer settings → Personal access tokens). Or use SSH: add EC2's ~/.ssh/id_rsa.pub to GitHub.

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
KEY="${SCRIPT_DIR}/coin_new.pem"
USER="ubuntu"
HOST="54.147.21.20"
REMOTE_APP_PATH="/home/ubuntu/coin-digital-app"
GITHUB_REPO="https://github.com/Kunalcoin/CoinDigital2026.git"
GIT_EMAIL="kunalkansal@coindigital.in"
GIT_USERNAME="Kunalcoin"

if [ ! -f "$KEY" ]; then
  echo "SSH key not found: $KEY"
  exit 1
fi
chmod 400 "$KEY" 2>/dev/null || true

echo "=== 1. Copying .gitignore to EC2 ... ==="
scp -i "$KEY" -o StrictHostKeyChecking=accept-new "${SCRIPT_DIR}/.gitignore" "$USER@$HOST:${REMOTE_APP_PATH}/.gitignore"

echo "=== 2. Setting Git config and initializing repo on EC2 ... ==="
ssh -i "$KEY" -o StrictHostKeyChecking=accept-new "$USER@$HOST" bash -s << REMOTESCRIPT
set -e
export GIT_EMAIL="$GIT_EMAIL"
export GIT_USERNAME="$GIT_USERNAME"
export REMOTE_APP_PATH="$REMOTE_APP_PATH"
export GITHUB_REPO="$GITHUB_REPO"

# Install git if missing
command -v git >/dev/null 2>&1 || sudo apt-get update -qq && sudo apt-get install -y -qq git

# Global config (so all repos on this server use this identity)
git config --global user.email "\$GIT_EMAIL"
git config --global user.name "\$GIT_USERNAME"

cd "\$REMOTE_APP_PATH"

# Remove existing .git if any (start fresh from current live code)
rm -rf .git 2>/dev/null || true

git init
git add .
git status

# Show what will be committed (should NOT list .env, coin.env - they must be in .gitignore)
echo "--- Files staged (verify no .env or coin.env) ---"
git diff --cached --name-only | head -50

read -p "Proceed with commit and push? (y/n) " -n 1 -r
echo
if [[ ! \$REPLY =~ ^[Yy]\$ ]]; then echo "Aborted."; exit 1; fi

git commit -m "Initial commit from live (EC2) - Coin Digital Royalty website"
git branch -M main
git remote add origin "\$GITHUB_REPO"
# If the repo already has commits (e.g. from a previous push), use: git pull origin main --allow-unrelated-histories then push; or git push -u origin main --force (overwrites remote).
git push -u origin main
REMOTESCRIPT

echo "=== Done. ==="
echo "If push asked for a password, use a GitHub Personal Access Token (not your GitHub password)."
