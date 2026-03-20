#!/bin/bash

# Deployment script for split_recipient fix to EC2
# Usage: ./deploy_to_ec2.sh

# Configuration - UPDATE THESE VALUES
EC2_USER="ubuntu"  # Change to your EC2 username
EC2_HOST="your-ec2-ip-or-domain.com"  # Change to your EC2 hostname/IP
EC2_KEY_PATH="~/.ssh/your-key.pem"  # Change to your SSH key path
REMOTE_PATH="/path/to/django-docker-compose/RoyaltyWebsite/main/"  # Change to your remote path

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${YELLOW}=== Deploying Split Recipient Fix to EC2 ===${NC}\n"

# Step 1: Backup current file on EC2
echo -e "${YELLOW}Step 1: Backing up current processor.py on EC2...${NC}"
ssh -i ${EC2_KEY_PATH} ${EC2_USER}@${EC2_HOST} \
    "cd ${REMOTE_PATH} && cp processor.py processor.py.backup_\$(date +%Y%m%d_%H%M%S) && echo 'Backup created successfully'"

if [ $? -ne 0 ]; then
    echo -e "${RED}Error: Failed to create backup. Please check your SSH connection.${NC}"
    exit 1
fi

# Step 2: Upload new processor.py
echo -e "\n${YELLOW}Step 2: Uploading new processor.py...${NC}"
scp -i ${EC2_KEY_PATH} \
    RoyaltyWebsite/main/processor.py \
    ${EC2_USER}@${EC2_HOST}:${REMOTE_PATH}processor.py

if [ $? -ne 0 ]; then
    echo -e "${RED}Error: Failed to upload file.${NC}"
    exit 1
fi

echo -e "${GREEN}File uploaded successfully!${NC}"

# Step 3: Verify file was uploaded
echo -e "\n${YELLOW}Step 3: Verifying file upload...${NC}"
ssh -i ${EC2_KEY_PATH} ${EC2_USER}@${EC2_HOST} \
    "cd ${REMOTE_PATH} && ls -lh processor.py && echo 'File verified'"

# Step 4: Restart Django service
echo -e "\n${YELLOW}Step 4: Restarting Django service...${NC}"
echo -e "Choose your Django service type:"
echo "1) Gunicorn (systemd)"
echo "2) Supervisor"
echo "3) Manual process (PM2/nohup)"
echo "4) Docker container"
read -p "Enter choice (1-4): " service_type

case $service_type in
    1)
        ssh -i ${EC2_KEY_PATH} ${EC2_USER}@${EC2_HOST} \
            "sudo systemctl restart gunicorn && echo 'Gunicorn restarted'"
        ;;
    2)
        ssh -i ${EC2_KEY_PATH} ${EC2_USER}@${EC2_HOST} \
            "sudo supervisorctl restart django && echo 'Supervisor restarted'"
        ;;
    3)
        echo -e "${YELLOW}Please manually restart your Django process on EC2${NC}"
        ;;
    4)
        ssh -i ${EC2_KEY_PATH} ${EC2_USER}@${EC2_HOST} \
            "docker-compose restart django || docker restart django-container && echo 'Docker container restarted'"
        ;;
    *)
        echo -e "${RED}Invalid choice. Please restart Django manually.${NC}"
        ;;
esac

# Step 5: Check Django service status
echo -e "\n${YELLOW}Step 5: Checking Django service status...${NC}"
ssh -i ${EC2_KEY_PATH} ${EC2_USER}@${EC2_HOST} \
    "ps aux | grep -E 'manage.py|gunicorn|python.*django' | grep -v grep || echo 'Please check service status manually'"

echo -e "\n${GREEN}=== Deployment Complete ===${NC}"
echo -e "${YELLOW}Next steps:${NC}"
echo "1. Test login as ar@paisleyblvd.com"
echo "2. Verify Net Total (INR) shows correct value (18,953.07)"
echo "3. Check Django logs for any errors"
