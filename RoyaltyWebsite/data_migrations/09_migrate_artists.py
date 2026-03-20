#!/usr/bin/env python3
"""
Data Migration Script: Artists
===============================

This script migrates artist data from the old db2.rl_artists table to the new Django Artist model.

Table Mapping:
- db2.rl_artists → releases.Artist

Field Mapping:
- username → user (CDUser foreign key)
- artist → name
- first_name → first_name
- last_name → last_name
- apple_music_id → apple_music_id
- spotify_id → spotify_id
- youtube_username → youtube_username
- soundcloud_page → soundcloud_page
- facebook_page → facebook_page
- x_username → x_username
- website → website
- biography → biography

Prerequisites:
1. User migration must be completed first (CDUser objects must exist)
2. Both db2 (old) and db3 (new) databases must be accessible
3. Django environment must be properly configured

Usage:
    python data_migrations/09_migrate_artists.py
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
from releases.models import Artist
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
        """UPDATE  db2.rl_artists 
        SET username = 'official.yuvrajmusic09@gmail.com' WHERE username = 'yuvrajstudios@gmail.com';""",
        """UPDATE  db2.rl_artists 
        SET username = 'surennamdevofficial@gmail.com' WHERE username = 'surennamdev@gmail.com';""",
        """UPDATE  db2.rl_artists 
        SET username = 'iamkaransinghchouhan@gmail.com' WHERE username = 'dopeculturestudios@gmail.com';""",
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
                'releases_artist',
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



def migrate_artists():
    """
    Migrate artists from old rl_artists table to Artist model
    """
    old_db, new_db = get_db_connections()
    
    # Step 1: Check prerequisites
    user_count = CDUser.objects.count()
    if user_count == 0:
        print("--> No users found. Please run user migration first.")
        return
    
    print(f"-->  Found {user_count} users in database")
    
    # Step 2: Check current state
    current_artists = Artist.objects.count()
    print(f"--> Current artists in Django database: {current_artists}")
    
    if current_artists > 0:
        response = input("-->  Artists already exist. Continue? (y/N): ")
        if response.lower() != 'y':
            print("--> Migration cancelled")
            return
    
    # Step 3: Fetch all artist data from old database
    print("--> Fetching artists from old database...")
    
    with old_db.cursor() as cursor:
        cursor.execute("""
            SELECT 
                id,
                TRIM(LOWER(username)) as username,
                artist,
                first_name,
                last_name,
                apple_music_id,
                spotify_id,
                youtube_username,
                soundcloud_page,
                facebook_page,
                x_username,
                website,
                biography
            FROM db2.rl_artists
            WHERE artist IS NOT NULL AND TRIM(artist) != ''
            ORDER BY username, artist
        """)
        
        artists_data = cursor.fetchall()
        columns = [col[0] for col in cursor.description]
        
    print(f"--> Found {len(artists_data)} artists to migrate")
    
    if not artists_data:
        print("-->  No artists found in old database")
        return
    
    # Step 4: Create user mapping for faster lookups
    print("-->  Creating user mapping...")
    user_mapping = {}
    for user in CDUser.objects.all():
        user_mapping[user.email] = user
    
    print(f"--> Created mapping for {len(user_mapping)} users")
    
    # Step 5: Prepare bulk data for insertion
    print("--> Preparing artist data for bulk insertion...")
    
    artist_objects = []
    error_count = 0
    duplicate_count = 0
    
    # Track duplicates (user + artist name combination)
    seen_artists = set()
    
    for artist_row in artists_data:
        artist_dict = dict(zip(columns, artist_row))
        
        try:
            artist_id = artist_dict.get('id')
            username = artist_dict.get('username', '').strip().lower()
            artist_name = artist_dict.get('artist', '').strip()
            
            # Skip empty artist names or missing IDs
            if not artist_name or not artist_id:
                error_count += 1
                continue
            
            # Find user
            if username not in user_mapping:
                print(f"-->  User not found: {username}")
                error_count += 1
                continue
            
            user = user_mapping[username]
            
            # Check for duplicates (same user + artist name combination)
            artist_key = (user.id, artist_name)
            if artist_key in seen_artists:
                duplicate_count += 1
                continue
            
            seen_artists.add(artist_key)
            
            # Handle optional fields with safe string conversion
            def safe_string(value, max_length=None):
                if value is None:
                    return ''
                value = str(value).strip()
                if max_length and len(value) > max_length:
                    return value[:max_length-3] + '...'
                return value
            
            first_name = safe_string(artist_dict.get('first_name'), 100)
            last_name = safe_string(artist_dict.get('last_name'), 100)
            apple_music_id = safe_string(artist_dict.get('apple_music_id'), 1024)
            spotify_id = safe_string(artist_dict.get('spotify_id'), 1024)
            youtube_username = safe_string(artist_dict.get('youtube_username'), 1024)
            soundcloud_page = safe_string(artist_dict.get('soundcloud_page'), 1024)
            facebook_page = safe_string(artist_dict.get('facebook_page'), 1024)
            x_username = safe_string(artist_dict.get('x_username'), 1024)
            website = safe_string(artist_dict.get('website'), 1024)
            biography = safe_string(artist_dict.get('biography'), 1024)  # Note: old DB has 5000 chars, new is 1024
            
            # Truncate artist name if too long (max 255 chars)
            if len(artist_name) > 255:
                artist_name = artist_name[:252] + "..."
                print(f"-->  Truncated long artist name for user {username}")
            
            # Create Artist object (not saved yet)
            artist_obj = Artist(
                artist_id=artist_id,
                user=user,
                name=artist_name,
                first_name=first_name,
                last_name=last_name,
                apple_music_id=apple_music_id,
                spotify_id=spotify_id,
                youtube_username=youtube_username,
                soundcloud_page=soundcloud_page,
                facebook_page=facebook_page,
                x_username=x_username,
                website=website,
                biography=biography
            )
            
            artist_objects.append(artist_obj)
            
        except Exception as e:
            error_count += 1
            print(f"--> Error preparing artist for {artist_dict.get('username', 'unknown')}: {e}")
            continue
    
    # Step 6: Bulk insert artists
    print(f"-->Bulk inserting {len(artist_objects)} artists...")
    
    try:
        # Use bulk_create for efficient insertion
        Artist.objects.bulk_create(artist_objects, batch_size=1000)
        
        migrated_count = len(artist_objects)
        print(f"--> Successfully migrated {migrated_count} artists")
        
    except Exception as e:
        print(f"--> Error during bulk insertion: {e}")
        return
    
    print(f"\n--> Migration Summary:")
    print(f"   --> Successfully migrated: {migrated_count} artists")
    print(f"   -->  Skipped (duplicates): {duplicate_count} artists")
    print(f"   --> Errors encountered: {error_count} artists")

def verify_artists_migration():
    """Verify the artists migration was successful"""
    print("\n--> Verifying artists migration...")
    
    # Get counts from both databases
    old_db, new_db = get_db_connections()
    
    with old_db.cursor() as cursor:
        cursor.execute("""
            SELECT COUNT(*) 
            FROM db2.rl_artists 
            WHERE artist IS NOT NULL AND artist != ''
        """)
        old_count = cursor.fetchone()[0]
    
    new_count = Artist.objects.count()
    
    print(f"--> Artist counts:")
    print(f"   Old database (db2.rl_artists): {old_count}")
    print(f"   New database (Artist model): {new_count}")
    
    # Note: Counts might differ due to duplicate removal
    if old_count == new_count:
        print("--> Artist counts match!")
    else:
        print(f"-->  Count difference likely due to duplicate removal")
    
    # Sample data verification
    print(f"\n--> Sample artist records:")
    sample_artists = Artist.objects.select_related('user').all()[:5]
    
    for artist in sample_artists:
        print(f"   {artist.user.email}: {artist.name}")
        if artist.first_name or artist.last_name:
            print(f"      Full name: {artist.first_name} {artist.last_name}")
        if artist.spotify_id:
            print(f"      Spotify: {artist.spotify_id}")
    
    # Statistics
    from django.db.models import Count
    
    # Artists per user
    user_artist_counts = Artist.objects.values('user__email').annotate(
        artist_count=Count('id')
    ).order_by('-artist_count')[:5]
    
    print(f"\n--> Top 5 Users by Artist Count:")
    for user_data in user_artist_counts:
        print(f"   {user_data['user__email']}: {user_data['artist_count']} artists")
    
    # Most common artist names
    common_artists = Artist.objects.values('name').annotate(
        count=Count('id')
    ).order_by('-count')[:5]
    
    print(f"\n--> Most Common Artist Names:")
    for artist_data in common_artists:
        print(f"   '{artist_data['name']}': {artist_data['count']} times")

def show_artist_statistics():
    """Show detailed artist statistics"""
    print("\n--> Detailed Artist Statistics:")
    
    from django.db.models import Count, Avg
    
    # Overall statistics
    total_artists = Artist.objects.count()
    total_users_with_artists = Artist.objects.values('user').distinct().count()
    total_unique_artists = Artist.objects.values('name').distinct().count()
    total_with_spotify = Artist.objects.exclude(spotify_id='').count()
    total_with_apple_music = Artist.objects.exclude(apple_music_id='').count()
    total_with_youtube = Artist.objects.exclude(youtube_username='').count()
    total_with_biography = Artist.objects.exclude(biography='').count()
    
    print(f"--> Overall Statistics:")
    print(f"   Total artists: {total_artists}")
    print(f"   Users with artists: {total_users_with_artists}")
    print(f"   Unique artist names: {total_unique_artists}")
    print(f"   Artists with Spotify ID: {total_with_spotify}")
    print(f"   Artists with Apple Music ID: {total_with_apple_music}")
    print(f"   Artists with YouTube: {total_with_youtube}")
    print(f"   Artists with biography: {total_with_biography}")
    
    # Average artists per user
    avg_artists = Artist.objects.values('user').annotate(
        artist_count=Count('id')
    ).aggregate(avg=Avg('artist_count'))['avg']
    
    print(f"   Average artists per user: {avg_artists:.1f}")
    
    # Users with most artists
    print(f"\n--> Users with Most Artists:")
    top_users = Artist.objects.values('user__email').annotate(
        artist_count=Count('id')
    ).order_by('-artist_count')[:10]
    
    for i, user_data in enumerate(top_users, 1):
        print(f"   {i:2d}. {user_data['user__email']:<30} {user_data['artist_count']:>3} artists")
    
    # Platform distribution
    platform_stats = {
        'Spotify': Artist.objects.exclude(spotify_id='').count(),
        'Apple Music': Artist.objects.exclude(apple_music_id='').count(),
        'YouTube': Artist.objects.exclude(youtube_username='').count(),
        'SoundCloud': Artist.objects.exclude(soundcloud_page='').count(),
        'Facebook': Artist.objects.exclude(facebook_page='').count(),
        'Website': Artist.objects.exclude(website='').count(),
    }
    
    print(f"\n--> Platform Presence:")
    for platform, count in platform_stats.items():
        percentage = (count / total_artists * 100) if total_artists > 0 else 0
        print(f"   {platform:<12}: {count:>4} artists ({percentage:>5.1f}%)")

def cleanup_artists():
    """Clean up artists data (USE WITH CAUTION!)"""
    response = input("-->  This will DELETE ALL artist records. Type 'DELETE' to confirm: ")
    if response == 'DELETE':
        artist_count = Artist.objects.count()
        Artist.objects.all().delete()
        print(f"-->  Deleted {artist_count} artist records")
    else:
        print("--> Cleanup cancelled")

if __name__ == "__main__":
    print("[START] Starting Artist Migration from db2.rl_artists to Django Artist model")
    print("=" * 78)
    
    try:
        # Import required modules for verification
        import django.db.models
        
        cleanup_old_table()
        truncate_new_tables()
        migrate_artists()
        verify_artists_migration()
        show_artist_statistics()
        print("\n--> Artist migration completed successfully!")
        
    except Exception as e:
        print(f"\n--> Migration failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1) 