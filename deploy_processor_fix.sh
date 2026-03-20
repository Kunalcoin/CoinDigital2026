#!/bin/bash

# Quick deployment script to upload processor.py fix to EC2
# This script uploads only the modified processor.py file and restarts the Django service

set -e  # Exit on error

# Configuration
EC2_IP="54.147.21.20"
EC2_USER="ubuntu"  # Change to "ec2-user" if using Amazon Linux
SSH_KEY="coin_new.pem"  # Path to your SSH key
LOCAL_FILE="RoyaltyWebsite/main/processor.py"
REMOTE_DIR="~/coin-digital-app"
REMOTE_FILE="$REMOTE_DIR/RoyaltyWebsite/main/processor.py"

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Deploying Split Recipient Fix to EC2${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

# Check if SSH key exists
if [ ! -f "$SSH_KEY" ]; then
    echo -e "${RED}Error: SSH key '$SSH_KEY' not found!${NC}"
    echo "Please ensure the SSH key is in the current directory or provide full path."
    exit 1
fi

# Set proper permissions for SSH key
chmod 400 "$SSH_KEY"

# Check if local file exists
if [ ! -f "$LOCAL_FILE" ]; then
    echo -e "${RED}Error: Local file '$LOCAL_FILE' not found!${NC}"
    exit 1
fi

# Test SSH connection
echo -e "${YELLOW}Step 1: Testing SSH connection...${NC}"
if ssh -i "$SSH_KEY" -o StrictHostKeyChecking=no -o ConnectTimeout=10 "$EC2_USER@$EC2_IP" "echo 'Connection successful'" > /dev/null 2>&1; then
    echo -e "${GREEN}✓ SSH connection successful${NC}"
else
    echo -e "${RED}✗ Cannot connect to EC2 server${NC}"
    echo "Please verify:"
    echo "  - EC2 instance is running"
    echo "  - IP address: $EC2_IP"
    echo "  - SSH key: $SSH_KEY"
    echo "  - Security group allows SSH (port 22)"
    exit 1
fi

# Upload the file
echo -e "${YELLOW}Step 2: Uploading processor.py to EC2...${NC}"
scp -i "$SSH_KEY" "$LOCAL_FILE" "$EC2_USER@$EC2_IP:$REMOTE_FILE"

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ File uploaded successfully${NC}"
else
    echo -e "${RED}✗ File upload failed${NC}"
    exit 1
fi

# Restart Django service
echo -e "${YELLOW}Step 3: Restarting Django service...${NC}"
echo "This may take a few moments..."

# Try different restart methods based on how Django is running
if ssh -i "$SSH_KEY" "$EC2_USER@$EC2_IP" "cd $REMOTE_DIR && sudo docker-compose ps | grep -q django" > /dev/null 2>&1; then
    # Using Docker Compose
    echo "Detected Docker Compose setup"
    ssh -i "$SSH_KEY" "$EC2_USER@$EC2_IP" "cd $REMOTE_DIR && sudo docker-compose restart django_gunicorn"
    echo -e "${GREEN}✓ Django service restarted (Docker Compose)${NC}"
elif ssh -i "$SSH_KEY" "$EC2_USER@$EC2_IP" "systemctl is-active --quiet gunicorn" > /dev/null 2>&1; then
    # Using systemd
    echo "Detected systemd service"
    ssh -i "$SSH_KEY" "$EC2_USER@$EC2_IP" "sudo systemctl restart gunicorn"
    echo -e "${GREEN}✓ Django service restarted (systemd)${NC}"
elif ssh -i "$SSH_KEY" "$EC2_USER@$EC2_IP" "supervisorctl status | grep -q django" > /dev/null 2>&1; then
    # Using supervisor
    echo "Detected supervisor"
    ssh -i "$SSH_KEY" "$EC2_USER@$EC2_IP" "sudo supervisorctl restart django"
    echo -e "${GREEN}✓ Django service restarted (supervisor)${NC}"
else
    echo -e "${YELLOW}⚠ Could not auto-detect service manager${NC}"
    echo "Please manually restart Django service on EC2:"
    echo "  - Docker: cd $REMOTE_DIR && sudo docker-compose restart django_gunicorn"
    echo "  - systemd: sudo systemctl restart gunicorn"
    echo "  - supervisor: sudo supervisorctl restart django"
fi

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Deployment Complete!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "Next steps:"
echo "1. Test the fix by logging in as: ar@paisleyblvd.com"
echo "2. Check Net Total (INR) - should show 18,953.07 instead of 0"
echo ""
echo "To view logs:"
echo "  ssh -i $SSH_KEY $EC2_USER@$EC2_IP 'cd $REMOTE_DIR && sudo docker-compose logs -f django_gunicorn'"
