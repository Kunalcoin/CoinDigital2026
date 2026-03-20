#!/usr/bin/env python3
"""
Django Superuser Creator Script
Creates a superuser with hardcoded credentials for development/testing purposes.
"""

import os
import sys
import django
from pathlib import Path

# Add the parent directory to Python path to import Django settings
current_dir = Path(__file__).resolve().parent
parent_dir = current_dir.parent
sys.path.append(str(parent_dir))

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'RoyaltyWebsite.settings')
django.setup()

from django.contrib.auth import get_user_model
from django.db import transaction

def create_superuser():
    """Create a superuser with hardcoded credentials"""
    print("[START] Starting Superuser Creation")
    print("=" * 50)
    
    # Hardcoded credentials
    EMAIL = 'sairsyed2@gmail.com'
    USERNAME = 'sairsyed2@gmail.com'
    PASSWORD = 'helloworld'
    
    User = get_user_model()
    
    try:
        with transaction.atomic():
            # Check if superuser already exists
            if User.objects.filter(email=EMAIL).exists():
                print(f"-->  Superuser with email '{EMAIL}' already exists")
                existing_user = User.objects.get(email=EMAIL)
                
                # Update to ensure it's a superuser
                if not existing_user.is_superuser:
                    existing_user.is_superuser = True
                    existing_user.is_staff = True
                    existing_user.set_password(PASSWORD)
                    existing_user.save()
                    print(f"--> Updated existing user to superuser status")
                else:
                    print(f"-->  User is already a superuser")
                
                return existing_user
            
            # Create new superuser
            print(f"--> Creating superuser with email: {EMAIL}")
            
            superuser = User.objects.create_superuser(
                email=USERNAME,
                password=PASSWORD
            )
            
            print(f"--> Successfully created superuser!")
            print(f"   📧 Email: {EMAIL}")
            print(f"   👤 Username: {USERNAME}")
            print(f"   🔑 Password: {PASSWORD}")
            print(f"   🆔 User ID: {superuser.id}")
            
            return superuser
            
    except Exception as e:
        print(f"--> Error creating superuser: {e}")
        import traceback
        traceback.print_exc()
        return None

def verify_superuser():
    """Verify the superuser was created successfully"""
    print("\n--> Verifying superuser creation...")
    
    EMAIL = 'sairsyed2@gmail.com'
    User = get_user_model()
    
    try:
        user = User.objects.get(email=EMAIL)
        
        print(f"--> Superuser verification:")
        print(f"   --> User exists: {user.email}")
        print(f"   --> Is superuser: {user.is_superuser}")
        print(f"   --> Is staff: {user.is_staff}")
        print(f"   --> Is active: {user.is_active}")
        print(f"   --> Date joined: {user.date_joined}")
        
        if user.is_superuser and user.is_staff and user.is_active:
            print("--> Superuser verification successful!")
            return True
        else:
            print("-->  Superuser verification failed - missing permissions")
            return False
            
    except User.DoesNotExist:
        print(f"--> Superuser with email '{EMAIL}' not found")
        return False
    except Exception as e:
        print(f"--> Error during verification: {e}")
        return False

def show_login_instructions():
    """Show instructions for logging into Django admin"""
    print("\n--> Django Admin Login Instructions:")
    print("=" * 50)
    print("1. Start your Django development server:")
    print("   python manage.py runserver")
    print()
    print("2. Navigate to Django Admin:")
    print("   http://localhost:8000/admin/")
    print()
    print("3. Login with these credentials:")
    print("   📧 Email/Username: sairsyed2@gmail.com")
    print("   🔑 Password: helloworld")
    print()
    print("4. You should now have full admin access!")

if __name__ == "__main__":
    print("🔐 Django Superuser Creator")
    print("Creating superuser with hardcoded credentials...")
    print()
    
    try:
        # Create superuser
        superuser = create_superuser()
        
        if superuser:
            # Verify creation
            if verify_superuser():
                show_login_instructions()
                print("\n--> Superuser creation completed successfully!")
            else:
                print("\n--> Superuser creation verification failed!")
        else:
            print("\n--> Superuser creation failed!")
            
    except Exception as e:
        print(f"\n--> Script failed with error: {e}")
        import traceback
        traceback.print_exc() 