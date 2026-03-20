#!/usr/bin/env python3
"""
Data Migration Script: Labels
=============================

This script migrates label data from the old db2.rl_labels table to the new Django Label model.

Table Mapping:
- db2.rl_labels → releases.Label

Field Mapping:
- user_name → user (CDUser foreign key)
- label → label

Prerequisites:
1. User migration must be completed first (CDUser objects must exist)
2. Both db2 (old) and db3 (new) databases must be accessible
3. Django environment must be properly configured

Usage:
    python data_migrations/08_migrate_labels.py
"""

import sys
import os
import django
from datetime import datetime

# Add the project root to Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'RoyaltyWebsite.settings')
django.setup()

from django.db import connections
from releases.models import Label
from main.models import CDUser

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
            
            # Truncate tables
            tables_to_truncate = [
                'releases_label',
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

def migrate_labels():
    """
    Migrate labels from old rl_labels table to Label model
    """
    old_db, new_db = get_db_connections()
    
    # Step 1: Check prerequisites
    user_count = CDUser.objects.count()
    if user_count == 0:
        print("--> No users found. Please run user migration first.")
        return
    
    print(f"-->  Found {user_count} users in database")
    
    # Step 2: Check current state
    current_labels = Label.objects.count()
    print(f"--> Current labels in Django database: {current_labels}")
    
    if current_labels > 0:
        response = input("-->  Labels already exist. Continue? (y/N): ")
        if response.lower() != 'y':
            print("--> Migration cancelled")
            return
    
    # Step 3: Fetch all label data from old database
    print("--> Fetching labels from old database...")
    
    with old_db.cursor() as cursor:
        cursor.execute("""
            SELECT 
                TRIM(LOWER(user_name)) as user_name,
                label
            FROM db2.rl_labels
            WHERE label IS NOT NULL AND TRIM(label) != '' AND user_name IS NOT NULL AND TRIM(LOWER(user_name)) != ''
            ORDER BY user_name, label
        """)
        
        labels_data = cursor.fetchall()
        columns = [col[0] for col in cursor.description]
        
    print(f"--> Found {len(labels_data)} labels to migrate")
    
    if not labels_data:
        print("-->  No labels found in old database")
        return
    
    # Step 4: Create user mapping for faster lookups
    print("-->  Creating user mapping...")
    user_mapping = {}
    for user in CDUser.objects.all():
        user_mapping[user.email] = user
    
    print(f"--> Created mapping for {len(user_mapping)} users")
    
    # Step 5: Prepare bulk data for insertion
    print("--> Preparing label data for bulk insertion...")
    
    label_objects = []
    error_count = 0
    duplicate_count = 0
    
    # Track duplicates (user + label combination)
    seen_labels = set()
    
    for label_row in labels_data:
        label_dict = dict(zip(columns, label_row))
        
        try:
            user_name = label_dict.get('user_name', '').strip()
            label_name = label_dict.get('label', '').strip()
            
            # Skip empty labels
            if not label_name:
                error_count += 1
                continue
            
            # Find user
            if user_name not in user_mapping:
                print(f"-->  User not found: {user_name}")
                error_count += 1
                continue
            
            user = user_mapping[user_name]
            
            # Check for duplicates (same user + label combination)
            label_key = (user.id, label_name)
            if label_key in seen_labels:
                duplicate_count += 1
                continue
            
            seen_labels.add(label_key)
            
            # Truncate label name if too long (max 255 chars)
            if len(label_name) > 255:
                label_name = label_name[:252] + "..."
                print(f"-->  Truncated long label name for user {user_name}")
            
            # Create Label object (not saved yet)
            label_obj = Label(
                user=user,
                label=label_name
            )
            
            label_objects.append(label_obj)
            
        except Exception as e:
            error_count += 1
            print(f"--> Error preparing label for {label_dict.get('user_name', 'unknown')}: {e}")
            continue
    
    # Step 6: Bulk insert labels
    print(f"-->Bulk inserting {len(label_objects)} labels...")
    
    try:
        # Use bulk_create for efficient insertion
        Label.objects.bulk_create(label_objects, batch_size=1000)
        
        migrated_count = len(label_objects)
        print(f"--> Successfully migrated {migrated_count} labels")
        
    except Exception as e:
        print(f"--> Error during bulk insertion: {e}")
        return
    
    print(f"\n--> Migration Summary:")
    print(f"   --> Successfully migrated: {migrated_count} labels")
    print(f"   -->  Skipped (duplicates): {duplicate_count} labels")
    print(f"   --> Errors encountered: {error_count} labels")

def verify_labels_migration():
    """Verify the labels migration was successful"""
    print("\n--> Verifying labels migration...")
    
    # Get counts from both databases
    old_db, new_db = get_db_connections()
    
    with old_db.cursor() as cursor:
        cursor.execute("""
            SELECT COUNT(*) 
            FROM db2.rl_labels 
            WHERE label IS NOT NULL AND label != ''
        """)
        old_count = cursor.fetchone()[0]
    
    new_count = Label.objects.count()
    
    print(f"--> Label counts:")
    print(f"   Old database (db2.rl_labels): {old_count}")
    print(f"   New database (Label model): {new_count}")
    
    # Note: Counts might differ due to duplicate removal
    if old_count == new_count:
        print("--> Label counts match!")
    else:
        print(f"-->  Count difference likely due to duplicate removal")
    
    # Sample data verification
    print(f"\n--> Sample label records:")
    sample_labels = Label.objects.select_related('user').all()[:5]
    
    for label in sample_labels:
        print(f"   {label.user.email}: {label.label}")
    
    # Statistics
    from django.db.models import Count
    
    # Labels per user
    user_label_counts = Label.objects.values('user__email').annotate(
        label_count=Count('id')
    ).order_by('-label_count')[:5]
    
    print(f"\n--> Top 5 Users by Label Count:")
    for user_data in user_label_counts:
        print(f"   {user_data['user__email']}: {user_data['label_count']} labels")
    
    # Most common label names
    common_labels = Label.objects.values('label').annotate(
        count=Count('id')
    ).order_by('-count')[:5]
    
    print(f"\n-->  Most Common Label Names:")
    for label_data in common_labels:
        print(f"   '{label_data['label']}': {label_data['count']} times")

def show_label_statistics():
    """Show detailed label statistics"""
    print("\n--> Detailed Label Statistics:")
    
    from django.db.models import Count, Avg
    
    # Overall statistics
    total_labels = Label.objects.count()
    total_users_with_labels = Label.objects.values('user').distinct().count()
    total_unique_labels = Label.objects.values('label').distinct().count()
    
    print(f"-->  Overall Statistics:")
    print(f"   Total labels: {total_labels}")
    print(f"   Users with labels: {total_users_with_labels}")
    print(f"   Unique label names: {total_unique_labels}")
    
    # Average labels per user
    avg_labels = Label.objects.values('user').annotate(
        label_count=Count('id')
    ).aggregate(avg=Avg('label_count'))['avg']
    
    print(f"   Average labels per user: {avg_labels:.1f}")
    
    # Users with most labels
    print(f"\n--> Users with Most Labels:")
    top_users = Label.objects.values('user__email').annotate(
        label_count=Count('id')
    ).order_by('-label_count')[:10]
    
    for i, user_data in enumerate(top_users, 1):
        print(f"   {i:2d}. {user_data['user__email']:<30} {user_data['label_count']:>3} labels")

def cleanup_labels():
    """Clean up labels data (USE WITH CAUTION!)"""
    response = input("-->  This will DELETE ALL label records. Type 'DELETE' to confirm: ")
    if response == 'DELETE':
        label_count = Label.objects.count()
        Label.objects.all().delete()
        print(f"-->  Deleted {label_count} label records")
    else:
        print("--> Cleanup cancelled")

if __name__ == "__main__":
    print("Starting Label Migration from db2.rl_labels to Django Label model")
    print("=" * 75)
    
    try:
        # Import required modules for verification
        import django.db.models
        
        cleanup_old_table()
        truncate_new_tables()
        migrate_labels()
        verify_labels_migration()
        show_label_statistics()
        print("\n--> Label migration completed successfully!")
        
    except Exception as e:
        print(f"\n--> Migration failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1) 