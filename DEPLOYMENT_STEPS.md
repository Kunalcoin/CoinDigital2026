# Deployment Steps for Split Recipient Fix

## Quick Deployment (Manual Steps)

### Prerequisites
- SSH access to EC2 server
- SSH key file
- EC2 server IP/hostname
- Path to Django project on EC2

---

## Method 1: Using SCP (Simple File Transfer)

### Step 1: Backup Current File on EC2
```bash
# SSH into EC2
ssh -i ~/.ssh/your-key.pem ubuntu@your-ec2-ip

# Navigate to project directory
cd /path/to/django-docker-compose/RoyaltyWebsite/main/

# Create backup
cp processor.py processor.py.backup_$(date +%Y%m%d_%H%M%S)
ls -lh processor.py.backup_*
```

### Step 2: Upload New File from Local Machine
```bash
# From your LOCAL machine (in the project root)
cd "/Users/ashimagoel/Documents/COIN DIGTAL NEW Working/live_code_complete_20260123_/django-docker-compose"

# Upload file using SCP
scp -i ~/.ssh/your-key.pem \
    RoyaltyWebsite/main/processor.py \
    ubuntu@your-ec2-ip:/path/to/django-docker-compose/RoyaltyWebsite/main/processor.py
```

### Step 3: Verify File Upload
```bash
# SSH into EC2
ssh -i ~/.ssh/your-key.pem ubuntu@your-ec2-ip

# Check file
cd /path/to/django-docker-compose/RoyaltyWebsite/main/
ls -lh processor.py
head -n 20 processor.py  # Verify it's the new file
```

### Step 4: Restart Django Service

**Option A: If using Gunicorn (systemd)**
```bash
sudo systemctl restart gunicorn
sudo systemctl status gunicorn
```

**Option B: If using Supervisor**
```bash
sudo supervisorctl restart django
sudo supervisorctl status django
```

**Option C: If using Docker**
```bash
cd /path/to/django-docker-compose
docker-compose restart django
# OR
docker restart django-container-name
```

**Option D: If running manually (PM2/nohup)**
```bash
# Find the process
ps aux | grep "manage.py runserver" | grep -v grep

# Kill and restart (adjust command based on your setup)
pkill -f "manage.py runserver"
# Then restart using your usual method
```

### Step 5: Check Django Logs
```bash
# Check if Django is running
ps aux | grep -E "manage.py|gunicorn|python.*django" | grep -v grep

# View logs (adjust path based on your setup)
tail -f /var/log/gunicorn/error.log
# OR
tail -f /path/to/django-docker-compose/logs/django.log
# OR
docker logs django-container-name -f
```

---

## Method 2: Using Git (If Repository is Set Up)

### Step 1: Commit Changes Locally
```bash
cd "/Users/ashimagoel/Documents/COIN DIGTAL NEW Working/live_code_complete_20260123_/django-docker-compose"

# If git is initialized
git add RoyaltyWebsite/main/processor.py
git commit -m "Fix split_recipient net total calculation - prevent double ratio application"
git push origin main  # or master, depending on your branch
```

### Step 2: Pull Changes on EC2
```bash
# SSH into EC2
ssh -i ~/.ssh/your-key.pem ubuntu@your-ec2-ip

# Navigate to project
cd /path/to/django-docker-compose

# Pull changes
git pull origin main  # or master

# Verify
git log -1
```

### Step 3: Restart Django Service
(Follow Step 4 from Method 1)

---

## Method 3: Using Deployment Script

### Step 1: Make Script Executable
```bash
cd "/Users/ashimagoel/Documents/COIN DIGTAL NEW Working/live_code_complete_20260123_/django-docker-compose"
chmod +x deploy_to_ec2.sh
```

### Step 2: Edit Script with Your EC2 Details
```bash
nano deploy_to_ec2.sh
# Update:
# - EC2_USER
# - EC2_HOST
# - EC2_KEY_PATH
# - REMOTE_PATH
```

### Step 3: Run Script
```bash
./deploy_to_ec2.sh
```

---

## Verification Steps

### 1. Test Split Recipient User
```bash
# Log in to your application as: ar@paisleyblvd.com
# Check the dashboard
# Net Total (INR) should show: 18,953.07 (not 0)
```

### 2. Check Django Logs for Errors
```bash
# On EC2
tail -f /var/log/gunicorn/error.log
# Look for any Python errors or tracebacks
```

### 3. Verify Calculation
- Gross Total: 89,190.91
- Owner's Ratio: 85%
- Recipient Percentage: 25%
- Expected Net Total: 89,190.91 × 85% × 25% = 18,953.07

---

## Rollback (If Something Goes Wrong)

### Option 1: Restore from Backup
```bash
# SSH into EC2
ssh -i ~/.ssh/your-key.pem ubuntu@your-ec2-ip

# Navigate to directory
cd /path/to/django-docker-compose/RoyaltyWebsite/main/

# List backups
ls -lh processor.py.backup_*

# Restore latest backup
cp processor.py.backup_YYYYMMDD_HHMMSS processor.py

# Restart Django service
sudo systemctl restart gunicorn  # or your service
```

### Option 2: Git Revert (If using Git)
```bash
# On EC2
cd /path/to/django-docker-compose
git checkout HEAD~1 -- RoyaltyWebsite/main/processor.py
# Restart service
```

---

## Troubleshooting

### Issue: File upload fails
- Check SSH key permissions: `chmod 400 ~/.ssh/your-key.pem`
- Verify EC2 security group allows SSH (port 22)
- Check file path on EC2 is correct

### Issue: Django won't start
- Check Python syntax: `python3 -m py_compile RoyaltyWebsite/main/processor.py`
- Check Django logs for errors
- Verify all dependencies are installed

### Issue: Still showing 0
- Clear browser cache
- Check Django is using the new file (restart service)
- Verify split_recipient user has active split records
- Check Django logs for SQL query errors

---

## Quick Reference Commands

```bash
# Upload file
scp -i ~/.ssh/key.pem local_file.py user@ec2:/remote/path/

# SSH into EC2
ssh -i ~/.ssh/key.pem user@ec2-ip

# Restart Gunicorn
sudo systemctl restart gunicorn

# Check service status
sudo systemctl status gunicorn

# View logs
tail -f /var/log/gunicorn/error.log

# Check if Django is running
ps aux | grep manage.py | grep -v grep
```
