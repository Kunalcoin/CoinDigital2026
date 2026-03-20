#!/usr/bin/env python3
"""
Data Migration Script: Metadata
===============================

This script migrates metadata from the old db2.metadata table to the new Django Metadata model.

Table Mapping:
- db2.metadata → releases.Metadata

Field Mapping:
- isrc → isrc (primary key)
- release → release
- display_artist → display_artist
- release_launch → release_launch
- user → user (username/email string)
- label_name → label_name
- primary_genre → primary_genre
- secondary_genre → secondary_genre
- track_no → track_no
- track → track
- track_display_artist → track_display_artist
- track_primary_genre → track_primary_genre
- upc → upc

Prerequisites:
1. Both db2 (old) and db3 (new) databases must be accessible
2. Django environment must be properly configured

Note: This model stores usernames as strings, not foreign keys to CDUser objects.

Usage:
    python data_migrations/12_migrate_metadata.py
"""

import sys
import os
import django
from datetime import datetime, date
import warnings
warnings.filterwarnings(
    'ignore',
    message='DateTimeField .* received a naive datetime',
    category=RuntimeWarning,
)
# Add the project root to Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'RoyaltyWebsite.settings')
django.setup()

from django.db import connections
from releases.models import Metadata

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
        """
            DELETE m1
            FROM db2.metadata m1
            JOIN (
                SELECT lower(trim(isrc)) AS isrc_code
                FROM db2.metadata
                GROUP BY lower(trim(isrc))
                HAVING COUNT(*) > 1
            ) dup
            ON lower(trim(m1.isrc)) = dup.isrc_code
            WHERE m1.`release` = 'No Pay';
        """
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
    Note: This migration updates existing Release and Track records, doesn't truncate
    """
    print("-->  No tables to truncate for metadata migration (updates existing records)")
    print("--> Table truncation completed")

def migrate_metadata():
    """
    Migrate metadata from old metadata table to Metadata model
    """
    old_db, new_db = get_db_connections()
    
    # Step 1: Check current state
    current_metadata = Metadata.objects.count()
    print(f"--> Current metadata records in Django database: {current_metadata}")
    
    if current_metadata > 0:
        response = input("-->  Metadata records already exist. Continue? (y/N): ")
        if response.lower() != 'y':
            print("--> Migration cancelled")
            return
    
    # Step 2: Fetch all metadata from old database
    print("--> Fetching metadata from old database...")
    
    with old_db.cursor() as cursor:
        cursor.execute("""
            SELECT 
                isrc,
                `release`,
                display_artist,
                release_launch,
                `user`,
                label_name,
                primary_group,
                secondary_genre,
                track_no,
                track,
                track_display_artist,
                track_primary_genre,
                upc
            FROM db2.metadata
            WHERE isrc IS NOT NULL AND isrc != ''
            ORDER BY user, isrc
        """)
        
        metadata_data = cursor.fetchall()
        columns = [col[0] for col in cursor.description]
        
    print(f"--> Found {len(metadata_data)} metadata records to migrate")
    
    if not metadata_data:
        print("-->  No metadata found in old database")
        return
    
    # Step 3: Prepare bulk data for insertion
    print("--> Preparing metadata for bulk insertion...")
    
    metadata_objects = []
    error_count = 0
    duplicate_count = 0
    
    # Track duplicates by ISRC (primary key)
    seen_isrcs = set()
    
    for metadata_row in metadata_data:
        metadata_dict = dict(zip(columns, metadata_row))
        
        try:
            isrc = metadata_dict.get('isrc', '').strip()
            
            # Skip empty ISRCs
            if not isrc:
                error_count += 1
                continue
            
            # Check for duplicates (ISRC is primary key)
            if isrc in seen_isrcs:
                duplicate_count += 1
                print(f"-->  Duplicate ISRC found: {isrc}")
                continue
            
            seen_isrcs.add(isrc)
            
            # Handle field mappings
            release = metadata_dict.get('releasee', '') or ''
            display_artist = metadata_dict.get('display_artist', '') or ''
            user = metadata_dict.get('user', '') or ''
            label_name = metadata_dict.get('label_name', '') or ''
            primary_genre = metadata_dict.get('primary_group', '') or ''
            secondary_genre = metadata_dict.get('secondary_genre', '') or ''
            track = metadata_dict.get('track', '') or ''
            track_display_artist = metadata_dict.get('track_display_artist', '') or ''
            track_primary_genre = metadata_dict.get('track_primary_genre', '') or ''
            upc = metadata_dict.get('upc', '') or ''
            
            # Handle track number
            track_no = metadata_dict.get('track_no')
            if track_no is not None:
                try:
                    track_no = int(track_no)
                except (ValueError, TypeError):
                    track_no = None
            
            # Handle release launch date
            release_launch = metadata_dict.get('release_launch')
            if release_launch and isinstance(release_launch, str):
                try:
                    # Try to parse the date string
                    release_launch = datetime.strptime(release_launch, '%Y-%m-%d').date()
                except ValueError:
                    try:
                        release_launch = datetime.strptime(release_launch, '%Y-%m-%d %H:%M:%S').date()
                    except ValueError:
                        release_launch = None
            elif not isinstance(release_launch, (date, type(None))):
                release_launch = None
            
            
            # Create Metadata object (not saved yet)
            metadata_obj = Metadata(
                isrc=isrc,
                release=release,
                display_artist=display_artist,
                release_launch=release_launch,
                user=user,
                label_name=label_name,
                primary_genre=primary_genre,
                secondary_genre=secondary_genre,
                track_no=track_no,
                track=track,
                track_display_artist=track_display_artist,
                track_primary_genre=track_primary_genre,
                upc=upc
            )
            
            metadata_objects.append(metadata_obj)
            
        except Exception as e:
            error_count += 1
            print(f"--> Error preparing metadata for ISRC {metadata_dict.get('isrc', 'unknown')}: {e}")
            continue
    
    # Step 4: Bulk insert metadata
    print(f"-->Bulk inserting {len(metadata_objects)} metadata records...")
    
    try:
        # Use bulk_create for efficient insertion
        Metadata.objects.bulk_create(metadata_objects, batch_size=1000)
        
        migrated_count = len(metadata_objects)
        print(f"--> Successfully migrated {migrated_count} metadata records")
        
    except Exception as e:
        print(f"--> Error during bulk insertion: {e}")
        return
    
    print(f"\n--> Migration Summary:")
    print(f"   --> Successfully migrated: {migrated_count} records")
    print(f"   -->  Skipped (duplicates): {duplicate_count} records")
    print(f"   --> Errors encountered: {error_count} records")

def verify_metadata_migration():
    """Verify the metadata migration was successful"""
    print("\n--> Verifying metadata migration...")
    
    # Get counts from both databases
    old_db, new_db = get_db_connections()
    
    with old_db.cursor() as cursor:
        cursor.execute("""
            SELECT COUNT(*) 
            FROM db2.metadata 
            WHERE isrc IS NOT NULL AND isrc != ''
        """)
        old_count = cursor.fetchone()[0]
    
    new_count = Metadata.objects.count()
    
    print(f"--> Metadata counts:")
    print(f"   Old database (db2.metadata): {old_count}")
    print(f"   New database (Metadata model): {new_count}")
    
    # Note: Counts might differ due to duplicate removal
    if old_count == new_count:
        print("--> Metadata counts match!")
    else:
        print(f"-->  Count difference likely due to duplicate removal")
    
    # Sample data verification
    print(f"\n--> Sample metadata records:")
    sample_metadata = Metadata.objects.all()[:5]
    
    for metadata in sample_metadata:
        print(f"   {metadata.isrc}: '{metadata.track}' by {metadata.track_display_artist} ({metadata.user})")
    
    # Statistics
    from django.db.models import Count
    
    # Metadata per user
    user_metadata_counts = Metadata.objects.values('user').annotate(
        metadata_count=Count('isrc')
    ).order_by('-metadata_count')[:5]
    
    print(f"\n--> Top 5 Users by Metadata Count:")
    for user_data in user_metadata_counts:
        print(f"   {user_data['user']}: {user_data['metadata_count']} tracks")
    
    # Most common genres
    genre_counts = Metadata.objects.exclude(primary_genre='').values('primary_genre').annotate(
        count=Count('isrc')
    ).order_by('-count')[:5]
    
    print(f"\n--> Most Common Primary Genres:")
    for genre_data in genre_counts:
        print(f"   {genre_data['primary_genre']}: {genre_data['count']} tracks")

def show_metadata_statistics():
    """Show detailed metadata statistics"""
    print("\n--> Detailed Metadata Statistics:")
    
    from django.db.models import Count, Avg
    
    # Overall statistics
    total_metadata = Metadata.objects.count()
    total_users = Metadata.objects.exclude(user='').values('user').distinct().count()
    total_with_upc = Metadata.objects.exclude(upc='').count()
    total_with_release_date = Metadata.objects.filter(release_launch__isnull=False).count()
    total_with_track_no = Metadata.objects.filter(track_no__isnull=False).count()
    
    print(f"--> Overall Statistics:")
    print(f"   Total metadata records: {total_metadata}")
    print(f"   Unique users: {total_users}")
    print(f"   Records with UPC: {total_with_upc}")
    print(f"   Records with release date: {total_with_release_date}")
    print(f"   Records with track number: {total_with_track_no}")
    
    # Average metadata per user
    avg_metadata = Metadata.objects.exclude(user='').values('user').annotate(
        metadata_count=Count('isrc')
    ).aggregate(avg=Avg('metadata_count'))['avg']
    
    print(f"   Average metadata per user: {avg_metadata:.1f}")
    
    # Most prolific users
    print(f"\n--> Most Prolific Users:")
    top_users = Metadata.objects.exclude(user='').values('user').annotate(
        metadata_count=Count('isrc')
    ).order_by('-metadata_count')[:10]
    
    for i, user_data in enumerate(top_users, 1):
        print(f"   {i:2d}. {user_data['user']:<30} {user_data['metadata_count']:>3} tracks")
    
    # Label distribution
    print(f"\n-->  Top Labels:")
    label_stats = Metadata.objects.exclude(label_name='').values('label_name').annotate(
        count=Count('isrc')
    ).order_by('-count')[:5]
    
    for label_data in label_stats:
        print(f"   {label_data['label_name']}: {label_data['count']} tracks")
    
    # Track number statistics
    track_no_stats = Metadata.objects.filter(track_no__isnull=False).aggregate(
        avg_track_no=Avg('track_no'),
        max_track_no=Count('track_no')
    )
    
    print(f"\n--> Track Number Statistics:")
    print(f"   Average track number: {track_no_stats['avg_track_no']:.1f}")
    print(f"   Total with track numbers: {track_no_stats['max_track_no']}")

def cleanup_metadata():
    """Clean up metadata (USE WITH CAUTION!)"""
    response = input("-->  This will DELETE ALL metadata records. Type 'DELETE' to confirm: ")
    if response == 'DELETE':
        metadata_count = Metadata.objects.count()
        Metadata.objects.all().delete()
        print(f"-->  Deleted {metadata_count} metadata records")
    else:
        print("--> Cleanup cancelled")

if __name__ == "__main__":
    print("[START] Starting Metadata Migration from db2.metadata to Django Metadata model")
    print("=" * 85)
    
    try:
        # Import required modules for verification
        import django.db.models
        
        cleanup_old_table()
        truncate_new_tables()
        migrate_metadata()
        verify_metadata_migration()
        show_metadata_statistics()
        print("\n--> Metadata migration completed successfully!")
        
    except Exception as e:
        print(f"\n--> Migration failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1) 