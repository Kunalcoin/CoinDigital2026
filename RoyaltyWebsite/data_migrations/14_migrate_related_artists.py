#!/usr/bin/env python3
"""
Data Migration Script: Related Artists
======================================

This script migrates artist relationship data from the old artist JSON fields in releases and tracks
to the new Django RelatedArtists model.

The old database stored artist relationships as JSON strings in the 'artist' column of both
rl_release and rl_tracks tables in the format:
{"Role Name": [artist_id1, artist_id2], "Another Role": [artist_id3]}

Example JSON:
{"Actor": [1606, 1974, 1976], "Primary Artist": [1298, 1601], "Composer": [1602], 
 "Lyricist": [1602], "Producer": [1603, 1301], "Arranger": [1603]}

This script:
1. Loads the artist JSON data saved by release and track migrations
2. Maps old artist IDs to new Artist objects
3. Creates RelatedArtists records linking artists to releases/tracks with proper roles

Table Mapping:
- db2.rl_release.artist (JSON) → releases.RelatedArtists (release relationships)
- db2.rl_tracks.artist (JSON) → releases.RelatedArtists (track relationships)

Prerequisites:
1. User migration must be completed first (CDUser objects must exist)
2. Artist migration must be completed first (Artist objects must exist)
3. Release migration must be completed first (Release objects must exist)
4. Track migration must be completed first (Track objects must exist)
5. Both release and track migrations must have generated their artist JSON files

Usage:
    python data_migrations/14_migrate_related_artists.py

ISSUES:
-- Artist ids not available in rl_artist data
select count(distinct id) FROM db2.rl_artists where id not in (select artist_id from db2.artist_roles) -- 1062

select count(distinct artist_id) from db2.artist_roles where id not in (select id from db2.rl_artists)
and lower(trim(username))  in (
select lower(trim(username)) from db2.user_login 
)  ; -- 15022

"""

import sys
import os
import django
import json
import pickle
from datetime import datetime

# Add the project root to Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'RoyaltyWebsite.settings')
django.setup()

from django.db import connections
from releases.models import RelatedArtists, Artist, Release, Track
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
                'releases_relatedartists',
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

def load_artist_json_data():
    """Load artist JSON data saved by release and track migrations"""
    release_data = {}
    track_data = {}
    
    # Load release artist data
    try:
        with open('C:/Users/mirza/Desktop/PERSONAL/With Sair/cd/django-docker-compose/RoyaltyWebsite/data_migrations/artist_json_releases.pkl', 'rb') as f:
            release_data = pickle.load(f)
        print(f"--> Loaded {len(release_data)} release artist JSON records")
    except FileNotFoundError:
        print("-->  No release artist JSON file found - run release migration first")
    
    # Load track artist data
    try:
        with open('C:/Users/mirza/Desktop/PERSONAL/With Sair/cd/django-docker-compose/RoyaltyWebsite/data_migrations/artist_json_tracks.pkl', 'rb') as f:
            track_data = pickle.load(f)
        print(f"--> Loaded {len(track_data)} track artist JSON records")
    except FileNotFoundError:
        print("-->  No track artist JSON file found - run track migration first")
    
    return release_data, track_data

def load_all_artists():
    """Load all existing artists into memory for fast lookup"""
    print("--> Loading all existing artists into memory...")
    artists = Artist.objects.select_related('user').all()
    artist_cache = {artist.artist_id: artist for artist in artists}
    print(f"--> Loaded {len(artist_cache)} artists into cache")
    return artist_cache

def get_artist_by_id(artist_id, artist_cache, missing_artists_dict):
    """Get Artist object from cache, track missing ones for bulk creation"""
    if artist_id in artist_cache:
        return artist_cache[artist_id]
    else:
        # Track missing artist for bulk creation later
        if artist_id not in missing_artists_dict:
            missing_artists_dict[artist_id] = None  # Will be filled with Artist object later
        return None

def refresh_artist_cache(artist_cache, missing_artists_dict):
    """Refresh the artist cache with newly created artists"""
    print("--> Refreshing artist cache with newly created artists...")
    for artist_id in missing_artists_dict.keys():
        if missing_artists_dict[artist_id] is not None:
            artist_cache[artist_id] = missing_artists_dict[artist_id]
    print(f"--> Artist cache now contains {len(artist_cache)} artists")

def create_missing_artists_bulk(missing_artists_dict, context_data):
    """Bulk create missing artists and update the dictionary with created objects"""
    if not missing_artists_dict:
        return
    
    print(f"--> Bulk creating {len(missing_artists_dict)} missing artists...")
    
    # Get default user for fallback
    default_user = CDUser.objects.first()
    
    # Prepare artist objects for bulk creation
    artists_to_create = []
    for artist_id in missing_artists_dict.keys():
        # Find best context for this artist
        context_info = context_data.get(artist_id, {})
        context_user = context_info.get('user', default_user)
        context_type = context_info.get('type', 'unknown')
        context_uuid = context_info.get('uuid', 'unknown')
        
        placeholder_name = f"ARTIST_NOT_FOUND_{context_type}_{context_uuid}"
        
        artist_obj = Artist(
            artist_id=artist_id,
            user=context_user,
            name=placeholder_name,
            first_name="",
            last_name="",
            apple_music_id="",
            spotify_id="",
            youtube_username="",
            soundcloud_page="",
            facebook_page="",
            x_username="",
            website="",
            biography=""
        )
        artists_to_create.append(artist_obj)
    
    # Bulk create artists
    try:
        created_artists = Artist.objects.bulk_create(artists_to_create, batch_size=1000)
        print(f"--> Successfully created {len(created_artists)} placeholder artists")
        
        # Update the dictionary with created objects
        # Note: bulk_create doesn't return objects with IDs in older Django versions
        # So we need to fetch them again
        for artist_id in missing_artists_dict.keys():
            try:
                missing_artists_dict[artist_id] = Artist.objects.get(artist_id=artist_id)
            except Artist.DoesNotExist:
                print(f"-->  Failed to retrieve created artist with ID: {artist_id}")
                
    except Exception as e:
        print(f"--> Error during bulk artist creation: {e}")
        # Fallback to individual creation
        for artist_obj in artists_to_create:
            try:
                created_artist = Artist.objects.create(
                    artist_id=artist_obj.artist_id,
                    user=artist_obj.user,
                    name=artist_obj.name,
                    first_name="",
                    last_name="",
                    apple_music_id="",
                    spotify_id="",
                    youtube_username="",
                    soundcloud_page="",
                    facebook_page="",
                    x_username="",
                    website="",
                    biography=""
                )
                missing_artists_dict[artist_obj.artist_id] = created_artist
            except Exception as create_error:
                print(f"-->  Failed to create artist {artist_obj.artist_id}: {create_error}")

def bulk_load_uuid_mappings(release_uuids, track_uuids):
    """Bulk load UUID to UPC/ISRC mappings and Django objects"""
    old_db, _ = get_db_connections()
    
    release_mapping = {}  # uuid -> Release object
    track_mapping = {}    # uuid -> Track object
    
    # Bulk load release UUIDs to UPC codes
    if release_uuids:
        print(f"--> Bulk loading {len(release_uuids)} release UUID mappings...")
        with old_db.cursor() as cursor:
            # Create placeholders for IN clause
            placeholders = ','.join(['%s'] * len(release_uuids))
            cursor.execute(f"""
                SELECT primary_uuid, upc_code 
                FROM db2.rl_release 
                WHERE primary_uuid IN ({placeholders}) AND upc_code IS NOT NULL AND upc_code != ''
            """, list(release_uuids))
            
            uuid_to_upc = {row[0]: row[1] for row in cursor.fetchall()}
        
        # Bulk load Django Release objects by UPC
        if uuid_to_upc:
            upc_codes = list(uuid_to_upc.values())
            django_releases = Release.objects.filter(upc__in=upc_codes).select_related('created_by')
            upc_to_release = {release.upc: release for release in django_releases}
            # Map UUIDs to Release objects
            for uuid, upc in uuid_to_upc.items():
                if str(upc) in upc_to_release:
                    release_mapping[uuid] = upc_to_release[str(upc)]
        
        print(f"--> Loaded {len(release_mapping)} release mappings")
    
    # Bulk load track UUIDs to ISRC codes
    if track_uuids:
        print(f"--> Bulk loading {len(track_uuids)} track UUID mappings...")
        with old_db.cursor() as cursor:
            # Create placeholders for IN clause
            placeholders = ','.join(['%s'] * len(track_uuids))
            cursor.execute(f"""
                SELECT primary_track_uuid, isrc_code 
                FROM db2.rl_tracks 
                WHERE primary_track_uuid IN ({placeholders}) AND isrc_code IS NOT NULL AND isrc_code != ''
            """, list(track_uuids))
            
            uuid_to_isrc = {row[0]: row[1] for row in cursor.fetchall()}
        
        # Bulk load Django Track objects by ISRC
        if uuid_to_isrc:
            isrc_codes = list(uuid_to_isrc.values())
            django_tracks = Track.objects.filter(isrc__in=isrc_codes).select_related('created_by', 'release')
            isrc_to_track = {track.isrc: track for track in django_tracks}
            
            # Map UUIDs to Track objects
            for uuid, isrc in uuid_to_isrc.items():
                if isrc in isrc_to_track:
                    track_mapping[uuid] = isrc_to_track[isrc]
        
        print(f"--> Loaded {len(track_mapping)} track mappings")
    
    return release_mapping, track_mapping

def get_release_by_uuid(release_uuid, release_mapping):
    """Get Release object from pre-loaded mapping"""
    return release_mapping.get(release_uuid)

def get_track_by_uuid(track_uuid, track_mapping):
    """Get Track object from pre-loaded mapping"""
    return track_mapping.get(track_uuid)

def migrate_related_artists():
    """
    Migrate artist relationships from JSON data to RelatedArtists model
    """
    # Step 1: Check prerequisites
    user_count = CDUser.objects.count()
    artist_count = Artist.objects.count()
    release_count = Release.objects.count()
    track_count = Track.objects.count()
    
    if user_count == 0:
        print("--> No users found. Please run user migration first.")
        return
    if artist_count == 0:
        print("--> No artists found. Please run artist migration first.")
        return
    if release_count == 0:
        print("--> No releases found. Please run release migration first.")
        return
    if track_count == 0:
        print("--> No tracks found. Please run track migration first.")
        return
    
    print(f"-->  Found {user_count} users, {artist_count} artists, {release_count} releases, {track_count} tracks")
    
    # Step 2: Check current state
    current_related_artists = RelatedArtists.objects.count()
    print(f"--> Current related artists in Django database: {current_related_artists}")
    
    if current_related_artists > 0:
        response = input("-->  Related artists already exist. Continue? (y/N): ")
        if response.lower() != 'y':
            print("--> Migration cancelled")
            return
    
    # Step 3: Load artist JSON data
    print("--> Loading artist JSON data...")
    release_data, track_data = load_artist_json_data()
    
    if not release_data and not track_data:
        print("--> No artist JSON data found. Please run release and track migrations first.")
        return
    
    # Step 4: Collect all UUIDs for bulk loading
    print("--> Collecting UUIDs for bulk loading...")
    
    release_uuids = set()
    track_uuids = set()
    
    # Collect release UUIDs
    for key, data in release_data.items():
        primary_uuid = data.get('primary_uuid', '')
        if primary_uuid:
            release_uuids.add(primary_uuid)
    
    # Collect track UUIDs
    for key, data in track_data.items():
        primary_track_uuid = data.get('primary_track_uuid', '')
        if primary_track_uuid:
            track_uuids.add(primary_track_uuid)
    
    print(f"--> Found {len(release_uuids)} unique release UUIDs and {len(track_uuids)} unique track UUIDs")
    
    # Bulk load UUID mappings
    release_mapping, track_mapping = bulk_load_uuid_mappings(release_uuids, track_uuids)
    
    # Step 5: Load all existing artists into cache
    artist_cache = load_all_artists()
    
    # Step 6: Collect all missing artists and context data
    print("--> Collecting missing artists and context data...")
    
    missing_artists_dict = {}  # artist_id -> Artist object (None initially)
    context_data = {}  # artist_id -> context info
    
    # First pass: collect all artist IDs and their context
    print("Release data: ", len(release_data))
    print("Track data: ", len(track_data))

    input("Press Enter to continue...")
    
    for key, data in release_data.items():
        try:
            user_email, release_title = key.split(':', 1)
            artist_data = data['artist_data']
            primary_uuid = data.get('primary_uuid', '')
            
            # Find the release using bulk mapping
            release = None
            if primary_uuid:
                release = get_release_by_uuid(primary_uuid, release_mapping)
            
            if not release:
                continue
                
            context_user = release.created_by
            
            # Collect artist IDs and context
            for role, artist_ids in artist_data.items():
                if not isinstance(artist_ids, list):
                    artist_ids = [artist_ids]
                
                for artist_id in artist_ids:
                    # Store context for this artist
                    if artist_id not in context_data:
                        context_data[artist_id] = {
                            'user': context_user,
                            'type': 'release',
                            'uuid': primary_uuid
                        }
                    
                    # Check if artist exists, track missing ones
                    get_artist_by_id(artist_id, artist_cache, missing_artists_dict)
                        
        except Exception as e:
            print(f"--> Error collecting from release {key}: {e}")
    
    # Collect from track data too
    for key, data in track_data.items():
        try:
            user_email, track_title = key.split(':', 1)
            artist_data = data['artist_data']
            primary_track_uuid = data.get('primary_track_uuid', '')
            
            # Find the track using bulk mapping
            track = None
            if primary_track_uuid:
                track = get_track_by_uuid(primary_track_uuid, track_mapping)
            
            if not track:
                continue
                
            context_user = track.created_by
            
            # Collect artist IDs and context
            for role, artist_ids in artist_data.items():
                if not isinstance(artist_ids, list):
                    artist_ids = [artist_ids]
                
                for artist_id in artist_ids:
                    # Store context for this artist (prefer release context if exists)
                    if artist_id not in context_data:
                        context_data[artist_id] = {
                            'user': context_user,
                            'type': 'track',
                            'uuid': primary_track_uuid
                        }
                    
                    # Check if artist exists, track missing ones
                    get_artist_by_id(artist_id, artist_cache, missing_artists_dict)
                        
        except Exception as e:
            print(f"--> Error collecting from track {key}: {e}")
    
    # Bulk create missing artists
    create_missing_artists_bulk(missing_artists_dict, context_data)
    
    # Refresh artist cache with newly created artists
    refresh_artist_cache(artist_cache, missing_artists_dict)
    
    # Step 6: Process release artist relationships
    print("--> Processing release artist relationships...")
    
    release_related_artists = []
    release_errors = 0
    
    for key, data in release_data.items():
        try:
            user_email, release_title = key.split(':', 1)
            artist_data = data['artist_data']
            primary_uuid = data.get('primary_uuid', '')
            
            # Find the release using bulk mapping
            release = None
            if primary_uuid:
                release = get_release_by_uuid(primary_uuid, release_mapping)
            else:
                print(f"-->  Release not found: {user_email} - {release_title}")
                release_errors += 1
                continue
            # if not release:
            #     try:
            #         release = Release.objects.get(
            #             created_by__email=user_email,
            #             title=release_title
            #         )
            #     except Release.DoesNotExist:
            #         print(f"-->  Release not found: {user_email} - {release_title}")
            #         release_errors += 1
            #         continue
            #     except Release.MultipleObjectsReturned:
            #         release = Release.objects.filter(
            #             created_by__email=user_email,
            #             title=release_title
            #         ).first()
            
            # Process each role and its artist IDs
            for role, artist_ids in artist_data.items():
                if not isinstance(artist_ids, list):
                    artist_ids = [artist_ids]
                
                for artist_id in artist_ids:
                    # Get artist from cache (now includes newly created ones)
                    artist = get_artist_by_id(artist_id, artist_cache, {})
                    
                    if artist:
                        # Create RelatedArtists object
                        related_artist = RelatedArtists(
                            release=release,
                            track=None,
                            relation_key='release',
                            artist=artist,
                            role=role
                        )
                        release_related_artists.append(related_artist)
                    else:
                        release_errors += 1
                        
        except Exception as e:
            print(f"--> Error processing release {key}: {e}")
            release_errors += 1
    
    print(f"--> Prepared {len(release_related_artists)} release artist relationships")
    
    # Step 7: Process track artist relationships
    print("--> Processing track artist relationships...")
    
    track_related_artists = []
    track_errors = 0
    
    for key, data in track_data.items():
        try:
            user_email, track_title = key.split(':', 1)
            artist_data = data['artist_data']
            release_title = data['release_title']
            primary_track_uuid = data.get('primary_track_uuid', '')
            
            # Find the track using bulk mapping
            track = None
            if primary_track_uuid:
                track = get_track_by_uuid(primary_track_uuid, track_mapping)
            else:
                print(f"-->  Track not found: {user_email} - {track_title} (from {release_title})")
                track_errors += 1
                continue
            # if not track:
            #     try:
            #         track = Track.objects.get(
            #             created_by__email=user_email,
            #             title=track_title,
            #             release__title=release_title
            #         )
            #     except Track.DoesNotExist:
            #         print(f"-->  Track not found: {user_email} - {track_title} (from {release_title})")
            #         track_errors += 1
            #         continue
            #     except Track.MultipleObjectsReturned:
            #         track = Track.objects.filter(
            #             created_by__email=user_email,
            #             title=track_title,
            #             release__title=release_title
            #         ).first()
            
            # Process each role and its artist IDs
            for role, artist_ids in artist_data.items():
                if not isinstance(artist_ids, list):
                    artist_ids = [artist_ids]
                
                for artist_id in artist_ids:
                    # Get artist from cache (now includes newly created ones)
                    artist = get_artist_by_id(artist_id, artist_cache, {})
                    
                    if artist:
                        # Create RelatedArtists object
                        related_artist = RelatedArtists(
                            release=None,
                            track=track,
                            relation_key='track',
                            artist=artist,
                            role=role
                        )
                        track_related_artists.append(related_artist)
                    else:
                        track_errors += 1
                        
        except Exception as e:
            print(f"--> Error processing track {key}: {e}")
            track_errors += 1
    
    print(f"--> Prepared {len(track_related_artists)} track artist relationships")
    
    # Step 8: Bulk insert all related artists
    all_related_artists = release_related_artists + track_related_artists
    
    if not all_related_artists:
        print("-->  No related artist relationships to insert")
        return
    
    print(f"-->Bulk inserting {len(all_related_artists)} related artist relationships...")
    
    try:
        # Remove duplicates by converting to set and back
        # (Django will handle this during bulk_create if there are uniqueness constraints)
        RelatedArtists.objects.bulk_create(all_related_artists, batch_size=1000, ignore_conflicts=True)
        
        # Get actual count inserted
        final_count = RelatedArtists.objects.count()
        inserted_count = final_count - current_related_artists
        
        print(f"--> Successfully inserted {inserted_count} related artist relationships")
        
    except Exception as e:
        print(f"--> Error during bulk insertion: {e}")
        return
    
    print(f"\n--> Migration Summary:")
    print(f"   --> Release relationships processed: {len(release_related_artists)}")
    print(f"   --> Track relationships processed: {len(track_related_artists)}")
    print(f"   --> Total relationships inserted: {inserted_count}")
    print(f"   --> Release processing errors: {release_errors}")
    print(f"   --> Track processing errors: {track_errors}")

def verify_related_artists_migration():
    """Verify the related artists migration was successful"""
    print("\n--> Verifying related artists migration...")
    
    # Overall counts
    total_related_artists = RelatedArtists.objects.count()
    release_relationships = RelatedArtists.objects.filter(relation_key='release').count()
    track_relationships = RelatedArtists.objects.filter(relation_key='track').count()
    
    print(f"--> Related Artist counts:")
    print(f"   Total relationships: {total_related_artists}")
    print(f"   Release relationships: {release_relationships}")
    print(f"   Track relationships: {track_relationships}")
    
    # Sample data verification
    print(f"\n--> Sample related artist records:")
    
    # Sample release relationships
    release_samples = RelatedArtists.objects.filter(
        relation_key='release'
    ).select_related('release', 'artist', 'artist__user')[:3]
    
    print(f"   Release Relationships:")
    for rel in release_samples:
        print(f"     {rel.release.title} - {rel.role}: {rel.artist.name} ({rel.artist.user.email})")
    
    # Sample track relationships
    track_samples = RelatedArtists.objects.filter(
        relation_key='track'
    ).select_related('track', 'track__release', 'artist', 'artist__user')[:3]
    
    print(f"   Track Relationships:")
    for rel in track_samples:
        print(f"     {rel.track.title} (from {rel.track.release.title}) - {rel.role}: {rel.artist.name} ({rel.artist.user.email})")

def show_related_artists_statistics():
    """Show detailed related artists statistics"""
    print("\n--> Detailed Related Artists Statistics:")
    
    from django.db.models import Count
    
    # Overall statistics
    total_relationships = RelatedArtists.objects.count()
    unique_artists = RelatedArtists.objects.values('artist').distinct().count()
    unique_releases = RelatedArtists.objects.filter(relation_key='release').values('release').distinct().count()
    unique_tracks = RelatedArtists.objects.filter(relation_key='track').values('track').distinct().count()
    
    print(f"--> Overall Statistics:")
    print(f"   Total relationships: {total_relationships}")
    print(f"   Unique artists involved: {unique_artists}")
    print(f"   Releases with artist relationships: {unique_releases}")
    print(f"   Tracks with artist relationships: {unique_tracks}")
    
    # Role distribution
    role_stats = RelatedArtists.objects.values('role').annotate(
        count=Count('id')
    ).order_by('-count')
    
    print(f"\n--> Role Distribution:")
    for role_data in role_stats:
        print(f"   {role_data['role']}: {role_data['count']} relationships")
    
    # Most active artists
    artist_stats = RelatedArtists.objects.values(
        'artist__name', 'artist__user__email'
    ).annotate(
        relationship_count=Count('id')
    ).order_by('-relationship_count')[:10]
    
    print(f"\n--> Top 10 Most Active Artists:")
    for i, artist_data in enumerate(artist_stats, 1):
        print(f"   {i:2d}. {artist_data['artist__name']} ({artist_data['artist__user__email']}): {artist_data['relationship_count']} relationships")
    
    # Release vs Track breakdown
    relation_breakdown = RelatedArtists.objects.values('relation_key').annotate(
        count=Count('id')
    ).order_by('-count')
    
    print(f"\n--> Relationship Type Breakdown:")
    for relation_data in relation_breakdown:
        print(f"   {relation_data['relation_key'].title()}: {relation_data['count']} relationships")

def cleanup_related_artists():
    """Clean up related artists data (USE WITH CAUTION!)"""
    response = input("-->  This will DELETE ALL related artist records. Type 'DELETE' to confirm: ")
    if response == 'DELETE':
        related_artist_count = RelatedArtists.objects.count()
        RelatedArtists.objects.all().delete()
        print(f"-->  Deleted {related_artist_count} related artist records")
    else:
        print("--> Cleanup cancelled")

if __name__ == "__main__":
    print("[START] Starting Related Artists Migration from JSON data to Django RelatedArtists model")
    print("=" * 90)
    
    try:
        cleanup_old_table()
        truncate_new_tables()
        migrate_related_artists()
        verify_related_artists_migration()
        show_related_artists_statistics()
        print("\n--> Related Artists migration completed successfully!")
        
    except Exception as e:
        print(f"\n--> Migration failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1) 