#!/usr/bin/env python3
"""
Data Migration Script: User Login to CDUser and Ratio Models
============================================================

This script migrates data from the old db2.user_login table to the new Django models:
- CDUser (main user model)
- Ratio (user ratio/percentage model)

Prerequisites:
1. Both db2 (old) and db3 (new) databases must be accessible
2. Django environment must be properly configured
3. Run this script from Django project root

Usage:
    python data_migrations/01_migrate_users.py
"""

import sys
import os
import django
from datetime import datetime
import hashlib

# Add the project root to Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'RoyaltyWebsite.settings')
django.setup()

from django.db import connections
from main.models import CDUser, Ratio
from django.contrib.auth.hashers import make_password

def get_db_connections():
    """Get database connections for old and new databases"""
    try:
        # Old database connection (db2)
        old_db = connections['db2']  # Adjust if needed
        
        # New database connection (db3) 
        new_db = connections['default']  # This should be your Django db
        
        return old_db, new_db
    except Exception as e:
        print(f"Error establishing database connections: {e}")
        sys.exit(1)

def cleanup_old_table():
    """
    Run cleanup queries on the old database table before migration
    """
    print("[CLEAN] Running cleanup on old database...")
    
    old_db, _ = get_db_connections()
    
    cleanup_queries = [

    ]
    
    with old_db.cursor() as cursor:
        for query in cleanup_queries:
            try:
                cursor.execute(query)
                print(f"--> Executed: {query[:50]}...")
            except Exception as e:
                print(f"-->  Warning - Could not execute cleanup query: {e}")
                # Continue with other queries even if one fails
    
    print("--> Cleanup completed")

def truncate_new_tables():
    """
    Truncate Django model tables before migration
    Temporarily disables foreign key constraints
    """
    print("-->  Truncating target tables...")
    
    _, new_db = get_db_connections()
    
    with new_db.cursor() as cursor:
        try:
            # Disable foreign key checks
            cursor.execute("SET FOREIGN_KEY_CHECKS = 0")
            
            # Truncate tables (in reverse dependency order)
            tables_to_truncate = [
                'main_ratio',        # Child table first
                'main_cduser',       # Parent table second
            ]
            
            for table in tables_to_truncate:
                cursor.execute(f"TRUNCATE TABLE {table}")
                print(f"--> Truncated table: {table}")
            
            # Re-enable foreign key checks
            cursor.execute("SET FOREIGN_KEY_CHECKS = 1")
            print("--> Foreign key constraints re-enabled")
            
        except Exception as e:
            # Make sure to re-enable foreign key checks even if truncation fails
            try:
                cursor.execute("SET FOREIGN_KEY_CHECKS = 1")
            except:
                pass
            print(f"--> Error during table truncation: {e}")
            raise
    
    print("--> Table truncation completed")

def migrate_users():
    """
    Migrate users from old user_login table to CDUser and Ratio models
    """
    old_db, new_db = get_db_connections()
    
    # Step 1: Fetch all users from old database
    print("--> Fetching users from old database...")
    
    with old_db.cursor() as cursor:
        cursor.execute("""
            SELECT 
                LOWER(username) as username,
                password,
                LOWER(role) as role,
                ratio,
                yt_ratio,
                LOWER(belongs_to) as belongs_to,
                name as first_name,
                surname as last_name,
                country,
                language,
                city,
                street,
                postal_code,
                contact_phone,
                company,
                company_name,
                fiskal_id_number,
                country_phone,
                company_contact_phone,
                pan_number as pan,
                gst_number,
                account_name,
                account_number,
                ifsc_code as ifsc,
                sort_code,
                swift_code,
                iban_number as iban,
                country_of_bank as bank_country,
                bank_name,
                status,
                sales_payout,
                sales_payout_threshold
            FROM db2.user_login
            WHERE username <> 'sairsyed2@gmail.com'
            ORDER BY 
                CASE 
                    WHEN role = 'admin' THEN 1
                    WHEN role = 'intermediate' THEN 2  
                    WHEN role = 'normal' THEN 3
                    ELSE 4
                END
           
        """)
        
        users_data = cursor.fetchall()
        columns = [col[0] for col in cursor.description]
        
    print(f"--> Found {len(users_data)} users to migrate")
    
    # Step 2: Create user mapping for parent relationships
    user_mapping = {}  # old_username -> new_user_id
    parent_mapping = {}  # username -> belongs_to (for later processing)
    
    # Step 3: Process users in order (admin -> intermediate -> normal)
    migrated_count = 0
    error_count = 0
    
    for user_row in users_data:
        user_dict = dict(zip(columns, user_row))
        
        try:
            
            password = f'temp_password_{user_dict["username"]}'
            django_password = make_password(password)
            ## log the password in a file
            with open('passwords.txt', 'a') as f:
                f.write(f"{user_dict['username']}: {password}:{django_password} || {user_dict['role']}\n")
            
            # Determine parent user (if belongs_to is set)
            parent_user = None
            belongs_to = user_dict.get('belongs_to')
            if belongs_to and belongs_to in user_mapping:
                try:
                    parent_user = CDUser.objects.get(id=user_mapping[belongs_to])
                except CDUser.DoesNotExist:
                    print(f"-->  Parent user {belongs_to} not found for {user_dict['username']}")
                    parent_user = None
            
            # Store belongs_to for later processing if parent not found yet
            if belongs_to and belongs_to not in user_mapping:
                parent_mapping[user_dict['username']] = belongs_to
            
            # Create CDUser instance
            cd_user = CDUser.objects.create(
                email=user_dict['username'],
                password=django_password,
                is_active=bool(user_dict.get('status', True)),
                role=user_dict.get('role', 'normal').lower(),
                first_name=user_dict.get('first_name', '') or 'Unknown',
                last_name=user_dict.get('last_name', '') or 'User',
                country=user_dict.get('country', '') or 'India, IN',
                language=user_dict.get('language', '') or 'English',
                city=user_dict.get('city', '') or '',
                street=user_dict.get('street', '') or '',
                postal_code=user_dict.get('postal_code', '') or '',
                contact_phone=user_dict.get('contact_phone', '') or 'N/A',
                company=user_dict.get('company', '') or '',
                company_name=user_dict.get('company_name', '') or '',
                fiskal_id_number=user_dict.get('fiskal_id_number', '') or '',
                country_phone=user_dict.get('country_phone', '') or '',
                company_contact_phone=user_dict.get('company_contact_phone', '') or 'N/A',
                pan=user_dict.get('pan', '') or 'N/A',
                gst_number=user_dict.get('gst_number', '') or '',
                account_name=user_dict.get('account_name', '') or '',
                account_number=user_dict.get('account_number', '') or '',
                ifsc=user_dict.get('ifsc', '') or '',
                sort_code=user_dict.get('sort_code', '') or '',
                swift_code=user_dict.get('swift_code', '') or '',
                iban=user_dict.get('iban', '') or '',
                bank_country=user_dict.get('bank_country', '') or '',
                bank_name=user_dict.get('bank_name', '') or '',
                parent=parent_user,
                created_at=datetime.now(),
                updated_at=datetime.now()
            )
            
            # Store mapping for future parent relationships
            user_mapping[user_dict['username']] = cd_user.id
            
            # Create Ratio record if ratio data exists
            ratio_value = user_dict.get('ratio', 0) or 0
            yt_ratio_value = user_dict.get('yt_ratio', 0) or 0
            
            Ratio.objects.create(
                user=cd_user,
                stores=int(ratio_value),
                youtube=int(yt_ratio_value),
                sales_payout=user_dict.get('sales_payout', 0) or 0,
                sales_payout_threshold=user_dict.get('sales_payout_threshold', 0) or 0,
                status=Ratio.STATUS.ACTIVE
            )
            
            migrated_count += 1
            print(f"--> Migrated user: {user_dict['username']} ({user_dict.get('role', 'unknown')})")
            
        except Exception as e:
            error_count += 1
            print(f"--> Error migrating user {user_dict.get('username', 'unknown')}: {e}")
            continue
    
    # Step 4: Process remaining parent relationships
    print("\n--> Processing remaining parent relationships...")
    
    for username, belongs_to in parent_mapping.items():
        if belongs_to in user_mapping:
            try:
                child_user = CDUser.objects.get(email=username)
                parent_user = CDUser.objects.get(id=user_mapping[belongs_to])
                child_user.parent = parent_user
                child_user.save()
                print(f"--> Updated parent relationship: {username} -> {belongs_to}")
            except CDUser.DoesNotExist:
                print(f"--> Could not find users to update relationship: {username} -> {belongs_to}")
            except Exception as e:
                print(f"--> Error updating parent relationship {username} -> {belongs_to}: {e}")
    
    print(f"\n--> Migration Summary:")
    print(f"   --> Successfully migrated: {migrated_count} users")
    print(f"   --> Errors encountered: {error_count} users")
    print(f"   --> Parent relationships processed: {len(parent_mapping)}")

def verify_migration():
    """Verify the migration was successful"""
    print("\n--> Verifying migration...")
    
    user_counts = {
        'admin': CDUser.objects.filter(role=CDUser.ROLES.ADMIN).count(),
        'intermediate': CDUser.objects.filter(role=CDUser.ROLES.INTERMEDIATE).count(),
        'normal': CDUser.objects.filter(role=CDUser.ROLES.NORMAL).count(),
        'member': CDUser.objects.filter(role=CDUser.ROLES.MEMBER).count(),
    }
    
    ratio_count = Ratio.objects.count()
    users_with_parents = CDUser.objects.filter(parent__isnull=False).count()
    
    print(f"--> User counts by role:")
    for role, count in user_counts.items():
        print(f"   {role.capitalize()}: {count}")
    
    print(f"--> Ratio records created: {ratio_count}")
    print(f"--> Users with parent relationships: {users_with_parents}")

if __name__ == "__main__":
    print("Starting User Migration from db2.user_login to Django CDUser model")
    print("=" * 70)
    
    try:
        cleanup_old_table()
        truncate_new_tables()
        migrate_users()
        verify_migration()
        print("\n--> User migration completed successfully!")
        
    except Exception as e:
        print(f"\n--> Migration failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1) 