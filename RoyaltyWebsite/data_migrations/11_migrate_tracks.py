#!/usr/bin/env python3
"""
Data Migration Script: Tracks
=============================

This script migrates track data from the old db2.rl_tracks table to the new Django Track model.

Table Mapping:
- db2.rl_tracks → releases.Track

Field Mapping:
- release_fk → release (Release foreign key via UUID mapping)
- primary_track_uuid → (internal reference for RelatedArtists)
- release_upc_code → (not used in new model)
- remix_version → remix_version
- title → title
- created_by → created_by (CDUser foreign key)
- audio_path → audio_track_url
- artist → (JSON data for RelatedArtists - handled separately)
- primary_genere → primary_genre (note: typo in old DB)
- secondary_genere → secondary_genre (note: typo in old DB)
- isrc_code → isrc
- iswc_code → iswc
- publishing_rights_owner → publishing_rights_owner
- publishing_rights_year → publishing_rights_year
- lyrics → lyrics
- explicit_lyrics → explicit_lyrics
- language → language
- available_separately → available_separately
- start_point → start_point
- notes → notes
- token → (not used in new model)

Prerequisites:
1. User migration must be completed first (CDUser objects must exist)
2. Release migration must be completed first (Release objects must exist)
3. Both db2 (old) and db3 (new) databases must be accessible
4. Django environment must be properly configured

Usage:
    python data_migrations/11_migrate_tracks.py
"""

import sys
import os
import django
import json
from datetime import datetime

# Add the project root to Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'RoyaltyWebsite.settings')
django.setup()

from django.db import connections
from releases.models import Track, Release
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
        """DELETE FROM db2.rl_tracks where release_fk not in (SELECT primary_uuid FROM db2.rl_release)""",
        """UPDATE  db2.rl_tracks 
            SET created_by = 'official.yuvrajmusic09@gmail.com' WHERE created_by = 'yuvrajstudios@gmail.com'""",
        """UPDATE  db2.rl_tracks 
            SET created_by = 'surennamdevofficial@gmail.com' WHERE created_by = 'surennamdev@gmail.com'""",
        """ DELETE FROM db2.rl_tracks where isrc_code is null""",
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
                'releases_track',
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

def map_explicit_lyrics(old_value):
    """Map old explicit_lyrics values to new enum values"""
    if not old_value:
        return Track.EXPLICIT_LYRICS.NOT_EXPLICIT
    
    old_value = str(old_value).lower().strip()
    
    if old_value in ['yes', 'explicit', 'true', '1']:
        return Track.EXPLICIT_LYRICS.EXPLICIT
    elif old_value in ['cleaned', 'clean']:
        return Track.EXPLICIT_LYRICS.CLEANED
    else:
        return Track.EXPLICIT_LYRICS.NOT_EXPLICIT

def migrate_tracks():
    """
    Migrate tracks from old rl_tracks table to Track model
    """
    old_db, new_db = get_db_connections()
    
    # Step 1: Check prerequisites
    user_count = CDUser.objects.count()
    if user_count == 0:
        print("--> No users found. Please run user migration first.")
        return
    
    release_count = Release.objects.count()
    if release_count == 0:
        print("--> No releases found. Please run release migration first.")
        return
    
    print(f"-->  Found {user_count} users and {release_count} releases in database")
    
    # Step 2: Check current state
    current_tracks = Track.objects.count()
    print(f"--> Current tracks in Django database: {current_tracks}")
    
    if current_tracks > 0:
        response = input("-->  Tracks already exist. Continue? (y/N): ")
        if response.lower() != 'y':
            print("--> Migration cancelled")
            return
    
    # Step 3: Create release UUID mapping
    print("-->  Creating release UUID mapping...")
    
    release_uuid_mapping = {}
    with old_db.cursor() as cursor:
        cursor.execute("""
            SELECT primary_uuid, created_by, title, upc_code
            FROM db2.rl_release
        """)
        print("--> Fetching releases from old database...")
        old_releases = cursor.fetchall()

    print(f"--> Old releases: {len(old_releases)}")

    # 2. Build list of UPCs we need
    upc_list = [upc for (_, _, _, upc) in old_releases]
    # 3. Bulk-fetch matching new Release objects
    print("--> Fetching matching releases from new database…")
    new_qs = Release.objects.filter(upc__in=upc_list)
    # turn that queryset into a {upc: Release} dict
    new_by_upc = {r.upc: r for r in new_qs}
    print(f"--> Found {len(new_by_upc)} matching releases in new database")

    # 4. Map old UUID → Release
    release_uuid_mapping = {}
    for old_uuid, created_by, title, upc in old_releases:
        release = new_by_upc.get(str(upc))
        if release:
            release_uuid_mapping[old_uuid.strip()] = release
        else:
            continue

    print(f"--> Created mapping for {len(release_uuid_mapping)} release UUIDs")
    
    print(f"--> Created mapping for {len(release_uuid_mapping)} release UUIDs")
    
    # Step 4: Fetch all track data from old database
    print("--> Fetching tracks from old database...")
    
    with old_db.cursor() as cursor:
        cursor.execute("""
            SELECT 
                release_fk,
                primary_track_uuid,
                release_upc_code,
                remix_version,
                title,
                created_by,
                audio_path,
                artist,
                primary_genere,
                secondary_genere,
                isrc_code,
                iswc_code,
                publishing_rights_owner,
                publishing_rights_year,
                lyrics,
                explicit_lyrics,
                language,
                available_separately,
                start_point,
                notes,
                token
            FROM db2.rl_tracks
            ORDER BY created_by, title
        """)
        
        tracks_data = cursor.fetchall()
        columns = [col[0] for col in cursor.description]
        
    print(f"--> Found {len(tracks_data)} tracks to migrate")
    
    if not tracks_data:
        print("-->  No tracks found in old database")
        return
    
    # Step 5: Create user mapping for faster lookups
    print("-->  Creating user mapping...")
    user_mapping = {}
    for user in CDUser.objects.all():
        user_mapping[user.email.lower()] = user
    
    print(f"--> Created mapping for {len(user_mapping)} users")
    
    # Step 6: Prepare bulk data for insertion
    print("--> Preparing track data for bulk insertion...")
    
    track_objects = []
    error_count = 0
    duplicate_count = 0
    artist_json_data = {}  # Store artist JSON data for RelatedArtists migration
    
    # Track duplicates (release + title combination)
    seen_tracks = set()
    
    for track_row in tracks_data:
        track_dict = dict(zip(columns, track_row))
        
        try:
            release_fk = track_dict.get('release_fk', '').strip() if track_dict.get('release_fk') else ''
            track_title = track_dict.get('title', '').strip() if track_dict.get('title') else ''
            user_name = track_dict.get('created_by', '').strip().lower() if track_dict.get('created_by') else ''
            primary_track_uuid = track_dict.get('primary_track_uuid', '').strip() if track_dict.get('primary_track_uuid') else ''
            isrc_code = track_dict.get('isrc_code', '') if track_dict.get('isrc_code') else ''
            # Skip empty titles
            if not track_title:
                error_count += 1
                continue
            
            # Find release
            if release_fk not in release_uuid_mapping:
                print(f"-->  Release not found for FK: {release_fk}")
                error_count += 1
                continue
            
            release = release_uuid_mapping[release_fk]
            
            # Find user
            if user_name not in user_mapping:
                print(f"-->  User not found: {user_name}")
                error_count += 1
                continue
            
            user = user_mapping[user_name]
            
            # Check for duplicates (same release + title combination)
            track_key = (release.id, track_title, isrc_code)
            if track_key in seen_tracks:
                duplicate_count += 1
                continue
            
            seen_tracks.add(track_key)
            
            # Handle artist JSON data (store for RelatedArtists migration)
            artist_json = track_dict.get('artist', '')
            if artist_json and artist_json.strip():
                try:
                    artist_data = json.loads(artist_json)
                    # Store with user+title as key for RelatedArtists migration
                    artist_json_data[f"{user_name}:{track_title}"] = {
                        'type': 'track',
                        'artist_data': artist_data,
                        'primary_track_uuid': primary_track_uuid,
                        'release_title': release.title
                    }
                except json.JSONDecodeError as e:
                    print(f"-->  Invalid JSON in artist field for track {track_title}: {e}")
            
            # Handle field mappings
            remix_version = track_dict.get('remix_version', '') or ''
            audio_track_url = track_dict.get('audio_path', '') or ''
            primary_genre = track_dict.get('primary_genere', '') or 'Other'  # Note: genere typo in old DB
            secondary_genre = track_dict.get('secondary_genere', '') or ''  # Note: genere typo in old DB
            isrc = track_dict.get('isrc_code', '') or ''
            iswc = track_dict.get('iswc_code', '') or ''
            publishing_rights_owner = track_dict.get('publishing_rights_owner', '') or ''
            publishing_rights_year = track_dict.get('publishing_rights_year', '') or ''
            lyrics = track_dict.get('lyrics', '') or ''
            language = track_dict.get('language', '') or 'English'
            start_point = track_dict.get('start_point', '') or '00:00'
            notes = track_dict.get('notes', '') or ''
            
            # Handle boolean field
            available_separately = bool(track_dict.get('available_separately', True))
            
            # Map explicit lyrics
            explicit_lyrics = map_explicit_lyrics(track_dict.get('explicit_lyrics'))
            
            # Truncate fields if too long
            if len(track_title) > 1024:
                track_title = track_title[:1021] + "..."
            if len(audio_track_url) > 1024:
                audio_track_url = audio_track_url[:1021] + "..."
            if len(lyrics) > 4096:
                lyrics = lyrics[:4093] + "..."
            if len(notes) > 1024:
                notes = notes[:1021] + "..."
            if len(remix_version) > 255:
                remix_version = remix_version[:252] + "..."
            if len(publishing_rights_owner) > 255:
                publishing_rights_owner = publishing_rights_owner[:252] + "..."
            if len(publishing_rights_year) > 4:
                publishing_rights_year = publishing_rights_year[:4]
            if len(isrc) > 255:
                isrc = isrc[:255]
            if len(iswc) > 255:
                iswc = iswc[:255]
            
            # Create Track object (not saved yet)
            track_obj = Track(
                release=release,
                remix_version=remix_version,
                title=track_title,
                created_by=user,
                audio_track_url=audio_track_url,
                primary_genre=primary_genre,
                secondary_genre=secondary_genre,
                isrc=isrc,
                iswc=iswc,
                publishing_rights_owner=publishing_rights_owner,
                publishing_rights_year=publishing_rights_year,
                lyrics=lyrics,
                explicit_lyrics=explicit_lyrics,
                language=language,
                available_separately=available_separately,
                start_point=start_point,
                notes=notes
            )
            
            track_objects.append(track_obj)
            
        except Exception as e:
            error_count += 1
            print(f"--> Error preparing track {track_dict.get('title', 'unknown')}: {e}")
            continue
    
    # Step 7: Bulk insert tracks
    print(f"-->Bulk inserting {len(track_objects)} tracks...")
    
    try:
        # Use bulk_create for efficient insertion
        Track.objects.bulk_create(track_objects, batch_size=1000)
        
        migrated_count = len(track_objects)
        print(f"--> Successfully migrated {migrated_count} tracks")
        
        # Save artist JSON data for RelatedArtists migration
        if artist_json_data:
            import pickle
            with open('data_migrations/artist_json_tracks.pkl', 'wb') as f:
                pickle.dump(artist_json_data, f)
            print(f"-->Saved {len(artist_json_data)} track artist JSON records for RelatedArtists migration")
        
    except Exception as e:
        print(f"--> Error during bulk insertion: {e}")
        return
    
    print(f"\n--> Migration Summary:")
    print(f"   --> Successfully migrated: {migrated_count} tracks")
    print(f"   -->  Skipped (duplicates): {duplicate_count} tracks")
    print(f"   --> Errors encountered: {error_count} tracks")

def verify_tracks_migration():
    """Verify the tracks migration was successful"""
    print("\n--> Verifying tracks migration...")
    
    # Get counts from both databases
    old_db, new_db = get_db_connections()
    
    with old_db.cursor() as cursor:
        cursor.execute("SELECT COUNT(*) FROM db2.rl_tracks")
        old_count = cursor.fetchone()[0]
    
    new_count = Track.objects.count()
    
    print(f"--> Track counts:")
    print(f"   Old database (db2.rl_tracks): {old_count}")
    print(f"   New database (Track model): {new_count}")
    
    # Note: Counts might differ due to duplicate removal
    if old_count == new_count:
        print("--> Track counts match!")
    else:
        print(f"-->  Count difference likely due to duplicate removal")
    
    # Sample data verification
    print(f"\n--> Sample track records:")
    sample_tracks = Track.objects.select_related('release', 'created_by').all()[:5]
    
    for track in sample_tracks:
        print(f"   {track.created_by.email}: {track.title}")
        print(f"      Release: {track.release.title}")
        print(f"      Genre: {track.primary_genre}, Language: {track.language}")
        if track.isrc:
            print(f"      ISRC: {track.isrc}")
    
    # Statistics
    from django.db.models import Count
    
    # Tracks per release
    release_track_counts = Track.objects.values('release__title').annotate(
        track_count=Count('id')
    ).order_by('-track_count')[:5]
    
    print(f"\n--> Top 5 Releases by Track Count:")
    for release_data in release_track_counts:
        print(f"   {release_data['release__title']}: {release_data['track_count']} tracks")
    
    # Most common genres
    genre_counts = Track.objects.values('primary_genre').annotate(
        count=Count('id')
    ).order_by('-count')
    
    print(f"\n--> Genre Distribution:")
    for genre_data in genre_counts:
        print(f"   {genre_data['primary_genre']}: {genre_data['count']} tracks")

def show_track_statistics():
    """Show detailed track statistics"""
    print("\n--> Detailed Track Statistics:")
    
    from django.db.models import Count, Avg, Q
    
    # Overall statistics
    total_tracks = Track.objects.count()
    total_releases_with_tracks = Track.objects.values('release').distinct().count()
    total_with_isrc = Track.objects.exclude(isrc='').count()
    total_with_lyrics = Track.objects.exclude(lyrics='').count()
    total_explicit = Track.objects.filter(explicit_lyrics=Track.EXPLICIT_LYRICS.EXPLICIT).count()
    total_available_separately = Track.objects.filter(available_separately=True).count()
    
    print(f"--> Overall Statistics:")
    print(f"   Total tracks: {total_tracks}")
    print(f"   Releases with tracks: {total_releases_with_tracks}")
    print(f"   Tracks with ISRC: {total_with_isrc}")
    print(f"   Tracks with lyrics: {total_with_lyrics}")
    print(f"   Explicit tracks: {total_explicit}")
    print(f"   Available separately: {total_available_separately}")
    
    # Average tracks per release
    avg_tracks = Track.objects.values('release').annotate(
        track_count=Count('id')
    ).aggregate(avg=Avg('track_count'))['avg']
    
    print(f"   Average tracks per release: {avg_tracks:.1f}")
    
    # Users with most tracks
    print(f"\n--> Top 10 Users by Track Count:")
    user_stats = Track.objects.values('created_by__email').annotate(
        track_count=Count('id')
    ).order_by('-track_count')[:10]
    
    for i, user_data in enumerate(user_stats, 1):
        print(f"   {i:2d}. {user_data['created_by__email']:<30} {user_data['track_count']:>3} tracks")
    
    # Language distribution
    language_stats = Track.objects.values('language').annotate(
        count=Count('id')
    ).order_by('-count')[:10]
    
    print(f"\n--> Top 10 Languages:")
    for lang_data in language_stats:
        print(f"   {lang_data['language']}: {lang_data['count']} tracks")
    
    # Explicit content breakdown
    explicit_stats = Track.objects.values('explicit_lyrics').annotate(
        count=Count('id')
    ).order_by('-count')
    
    print(f"\n--> Explicit Content Breakdown:")
    for explicit_data in explicit_stats:
        print(f"   {explicit_data['explicit_lyrics']}: {explicit_data['count']} tracks")

def cleanup_tracks():
    """Clean up tracks data (USE WITH CAUTION!)"""
    response = input("-->  This will DELETE ALL track records. Type 'DELETE' to confirm: ")
    if response == 'DELETE':
        track_count = Track.objects.count()
        Track.objects.all().delete()
        print(f"-->  Deleted {track_count} track records")
        
        # Also clean up the artist JSON data file
        try:
            os.remove('data_migrations/artist_json_tracks.pkl')
            print("-->  Deleted artist JSON data file")
        except FileNotFoundError:
            pass
    else:
        print("--> Cleanup cancelled")

if __name__ == "__main__":
    print("[START] Starting Track Migration from db2.rl_tracks to Django Track model")
    print("=" * 80)
    
    try:
        cleanup_old_table()
        truncate_new_tables()
        migrate_tracks()
        verify_tracks_migration()
        show_track_statistics()
        print("\n--> Track migration completed successfully!")
        
    except Exception as e:
        print(f"\n--> Migration failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1) 