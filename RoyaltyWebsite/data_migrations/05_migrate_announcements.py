#!/usr/bin/env python3
"""
Data Migration Script: Announcements
====================================

This script migrates announcement data from the old db2.announcements table to the new Django Announcement model.

Table Mapping:
- db2.announcements → main.Announcement

Field Mapping:
- announcement_id → announcement_id
- announcement → announcement
- created_at → created_at

Prerequisites:
1. Both db2 (old) and db3 (new) databases must be accessible
2. Django environment must be properly configured

Usage:
    python data_migrations/05_migrate_announcements.py
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
from main.models import Announcement

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
                'main_announcement',
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

def migrate_announcements():
    """
    Migrate announcements from old announcements table to Announcement model
    """
    old_db, new_db = get_db_connections()
    
    # Step 1: Check current state
    current_announcements = Announcement.objects.count()
    print(f"--> Current announcements in Django database: {current_announcements}")
    
    if current_announcements > 0:
        response = input("-->  Announcements already exist. Continue? (y/N): ")
        if response.lower() != 'y':
            print("--> Migration cancelled")
            return
    
    # Step 2: Fetch all announcement data from old database
    print("--> Fetching announcements from old database...")
    
    with old_db.cursor() as cursor:
        cursor.execute("""
            SELECT 
                announcement_id,
                announcement,
                created_at
            FROM db2.announcements
            ORDER BY created_at DESC
        """)
        
        announcements_data = cursor.fetchall()
        columns = [col[0] for col in cursor.description]
        
    print(f"--> Found {len(announcements_data)} announcements to migrate")
    
    if not announcements_data:
        print("-->  No announcements found in old database")
        return
    
    # Step 3: Prepare bulk data for insertion
    print("--> Preparing announcement data for bulk insertion...")
    
    announcement_objects = []
    error_count = 0
    
    for announcement_row in announcements_data:
        announcement_dict = dict(zip(columns, announcement_row))
        
        try:
            # Get announcement text and truncate if necessary (max 1024 chars in new model)
            announcement_text = announcement_dict.get('announcement', '') if announcement_dict.get('announcement') is not None else ''
            announcement_text = announcement_text.strip()
            if len(announcement_text) > 1024:
                announcement_text = announcement_text[:1021] + "..."
                print(f"-->  Truncated long announcement (ID: {announcement_dict.get('announcement_id')})")
            
            # Create Announcement object (not saved yet)
            announcement_obj = Announcement(
                announcement=announcement_text,
                created_at=announcement_dict.get('created_at', datetime.now())
            )
            
            announcement_objects.append(announcement_obj)
            
        except Exception as e:
            error_count += 1
            print(f"--> Error preparing announcement {announcement_dict.get('announcement_id', 'unknown')}: {e}")
            continue
    
    # Step 4: Bulk insert announcements
    print(f"-->Bulk inserting {len(announcement_objects)} announcements...")
    
    try:
        # Use bulk_create for efficient insertion
        Announcement.objects.bulk_create(announcement_objects, batch_size=1000)
        
        migrated_count = len(announcement_objects)
        print(f"--> Successfully migrated {migrated_count} announcements")
        
    except Exception as e:
        print(f"--> Error during bulk insertion: {e}")
        return
    
    print(f"\n--> Migration Summary:")
    print(f"   --> Successfully migrated: {migrated_count} announcements")
    print(f"   --> Errors encountered: {error_count} announcements")

def verify_announcements_migration():
    """Verify the announcements migration was successful"""
    print("\n--> Verifying announcements migration...")
    
    # Get counts from both databases
    old_db, new_db = get_db_connections()
    
    with old_db.cursor() as cursor:
        cursor.execute("SELECT COUNT(*) FROM db2.announcements")
        old_count = cursor.fetchone()[0]
    
    new_count = Announcement.objects.count()
    
    print(f"--> Announcement counts:")
    print(f"   Old database (db2.announcements): {old_count}")
    print(f"   New database (Announcement model): {new_count}")
    
    if old_count == new_count:
        print("--> Announcement counts match!")
    else:
        print("-->  Announcement counts don't match - please review")
    
    # Sample data verification
    print(f"\n--> Sample announcement records:")
    sample_announcements = Announcement.objects.all().order_by('-created_at')[:3]
    
    for announcement in sample_announcements:
        # Truncate announcement text for display
        text = announcement.announcement[:100] + "..." if len(announcement.announcement) > 100 else announcement.announcement
        print(f"   ID {announcement.announcement_id}: {text} ({announcement.created_at})")
    
    # Date range statistics
    from django.db.models import Min, Max
    
    date_stats = Announcement.objects.aggregate(
        oldest=Min('created_at'),
        newest=Max('created_at'),
        count=django.db.models.Count('announcement_id')
    )
    
    print(f"\n--> Announcement Statistics:")
    print(f"   Total announcements: {date_stats['count']}")
    print(f"   Oldest announcement: {date_stats['oldest']}")
    print(f"   Newest announcement: {date_stats['newest']}")

def show_recent_announcements():
    """Show most recent announcements"""
    print("\n--> Recent Announcements (Last 5):")
    
    recent_announcements = Announcement.objects.all().order_by('-created_at')[:5]
    
    for i, announcement in enumerate(recent_announcements, 1):
        # Truncate for display
        text = announcement.announcement[:80] + "..." if len(announcement.announcement) > 80 else announcement.announcement
        print(f"   {i}. {text}")
        print(f"      --> {announcement.created_at.strftime('%Y-%m-%d %H:%M:%S')}")

def cleanup_announcements():
    """Clean up announcements data (USE WITH CAUTION!)"""
    response = input("-->  This will DELETE ALL announcement records. Type 'DELETE' to confirm: ")
    if response == 'DELETE':
        announcement_count = Announcement.objects.count()
        Announcement.objects.all().delete()
        print(f"-->  Deleted {announcement_count} announcement records")
    else:
        print("--> Cleanup cancelled")

if __name__ == "__main__":
    print("[START] Starting Announcement Migration from db2.announcements to Django Announcement model")
    print("=" * 90)
    
    try:
        # Import required modules for verification
        import django.db.models
        
        cleanup_old_table()
        truncate_new_tables()
        migrate_announcements()
        verify_announcements_migration()
        show_recent_announcements()
        print("\n--> Announcement migration completed successfully!")
        
    except Exception as e:
        print(f"\n--> Migration failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1) 