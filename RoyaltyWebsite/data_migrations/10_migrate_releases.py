#!/usr/bin/env python3
"""
Data Migration Script: Releases
===============================

This script migrates release data from the old db2.rl_release table to the new Django Release model.
It also integrates license data from the rl_licenses table.

Table Mapping:
- db2.rl_release → releases.Release
- db2.rl_licenses → releases.Release (license fields)

Field Mapping:
- primary_uuid → (internal reference for RelatedArtists)
- title → title
- cover_art_path → cover_art_url
- remix_version → remix_version
- artist → (JSON data for RelatedArtists - handled separately)
- label → label (Label foreign key)
- primary_genre → primary_genre
- secondary_genre → secondary_genre
- language → language
- album_format → album_format
- upc_code → upc
- reference_number → reference_number
- gr_id → grid
- release_description → description
- created_by → created_by (CDUser foreign key)
- is_published → published
- published_at → (string field - ignored)
- takedown_requested → takedown_requested
- published_at_time → published_at

License Fields (from rl_licenses):
- price_category → price_category
- digital_release_date → digital_release_date
- original_release_date → original_release_date
- license_type → license_type
- license_holder_year → license_holder_year
- license_holder_name → license_holder_name
- copyright_recording_year → copyright_recording_year
- copyright_recording_text → copyright_recording_text
- territories → territories

Prerequisites:
1. User migration must be completed first (CDUser objects must exist)
2. Label migration must be completed first (Label objects must exist)
3. Both db2 (old) and db3 (new) databases must be accessible
4. Django environment must be properly configured

Usage:
    python data_migrations/10_migrate_releases.py
"""

import sys
import os
import django
import json
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
from releases.models import Release, Label
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
        "DELETE FROM db2.rl_release where upc_code is null",
        """ 
        DELETE FROM db2.rl_release
        WHERE lower(trim(created_by)) not in 
        (select lower(trim(username)) as username
        from db2.user_login) 
        """,
        
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
                'releases_track',           # Child tables first
                'releases_relatedartists',
                'releases_release',         # Parent table second
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

def map_album_format(old_format):
    """Map old album format values to new enum values"""
    if not old_format:
        return Release.ALBUM_FORMAT.SINGLE
    
    old_format = str(old_format).lower().strip()
    
    # Map old format values to new ones
    if old_format in ['single', 'track']:
        return Release.ALBUM_FORMAT.SINGLE
    elif old_format in ['ep', 'mini', 'mini-album']:
        return Release.ALBUM_FORMAT.EP
    elif old_format in ['album', 'lp', 'full']:
        return Release.ALBUM_FORMAT.ALBUM
    else:
        # Default to single for unknown formats
        print(f"-->  Unknown album format '{old_format}' - defaulting to SINGLE")
        return Release.ALBUM_FORMAT.SINGLE

def map_price_category(old_category):
    """Map old price category values to new enum values"""
    if not old_category:
        return Release.PRICE_CATEGORY.BUDGET
    
    old_category = str(old_category).lower().strip()
    
    if old_category in ['mid', 'middle']:
        return Release.PRICE_CATEGORY.MID
    elif old_category in ['budget', 'low']:
        return Release.PRICE_CATEGORY.BUDGET
    elif old_category in ['full', 'standard']:
        return Release.PRICE_CATEGORY.FULL
    elif old_category in ['premium', 'high']:
        return Release.PRICE_CATEGORY.PREMIUM
    else:
        return Release.PRICE_CATEGORY.BUDGET

def map_license_type(old_type):
    """Map old license type values to new enum values"""
    if not old_type:
        return Release.LICENSE_TYPE.COPYRIGHT
    
    old_type = str(old_type).lower().strip()
    
    if 'creative' in old_type or 'common' in old_type:
        return Release.LICENSE_TYPE.CREATIVE_COMMON
    else:
        return Release.LICENSE_TYPE.COPYRIGHT

def parse_date_string(date_str):
    """Parse various date string formats"""
    if not date_str:
        return None
    
    date_str = str(date_str).strip()
    if not date_str or date_str.lower() in ['null', 'none', '']:
        return None
    
    # Try different date formats
    formats = ['%Y-%m-%d', '%d/%m/%Y', '%m/%d/%Y', '%Y-%m-%d %H:%M:%S']
    
    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt).date()
        except ValueError:
            continue
    
    print(f"-->  Could not parse date: {date_str}")
    return None

def migrate_releases():
    """
    Migrate releases from old rl_release table to Release model
    """
    old_db, new_db = get_db_connections()
    
    # Step 1: Check prerequisites
    user_count = CDUser.objects.count()
    if user_count == 0:
        print("--> No users found. Please run user migration first.")
        return
    
    label_count = Label.objects.count()
    if label_count == 0:
        print("--> No labels found. Please run label migration first.")
        return
    
    print(f"-->  Found {user_count} users and {label_count} labels in database")
    
    # Step 2: Check current state
    current_releases = Release.objects.count()
    print(f"--> Current releases in Django database: {current_releases}")
    
    if current_releases > 0:
        response = input("-->  Releases already exist. Continue? (y/N): ")
        if response.lower() != 'y':
            print("--> Migration cancelled")
            return
    
    # Step 3: Fetch license data for reference
    print("--> Fetching license data from old database...")
    
    license_data = {}
    with old_db.cursor() as cursor:
        cursor.execute("""
            SELECT 
                release_fk,
                price_category,
                digital_release_date,
                original_release_date,
                license_type,
                license_holder_year,
                license_holder_name,
                copyright_recording_year,
                copyright_recording_text,
                territories
            FROM db2.rl_licenses
        """)
        
        for row in cursor.fetchall():
            license_data[row[0]] = {
                'price_category': row[1],
                'digital_release_date': row[2],
                'original_release_date': row[3],
                'license_type': row[4],
                'license_holder_year': row[5],
                'license_holder_name': row[6],
                'copyright_recording_year': row[7],
                'copyright_recording_text': row[8],
                'territories': row[9]
            }
    
    print(f"--> Found {len(license_data)} license records")
    
    # Step 4: Fetch all release data from old database
    print("--> Fetching releases from old database...")
    
    with old_db.cursor() as cursor:
        cursor.execute("""
            SELECT 
                primary_uuid,
                title,
                cover_art_path,
                remix_version,
                artist,
                label,
                primary_genre,
                secondary_genre,
                language,
                album_format,
                upc_code,
                reference_number,
                gr_id,
                release_description,
                created_by,
                is_published,
                published_at,
                takedown_requested,
                published_at_time
            FROM db2.rl_release
            ORDER BY created_by, title
        """)
        
        releases_data = cursor.fetchall()
        columns = [col[0] for col in cursor.description]
        
    print(f"--> Found {len(releases_data)} releases to migrate")
    
    if not releases_data:
        print("-->  No releases found in old database")
        return
    
    # Step 5: Create user and label mappings for faster lookups
    print("-->  Creating user and label mappings...")
    user_mapping = {}
    for user in CDUser.objects.all():
        user_mapping[user.email.lower()] = user
    
    label_mapping = {}
    for label in Label.objects.select_related('user').all():
        # Key by user_email + label_name combination
        label_key = f"{label.user.email.lower()}:{label.label}"
        label_mapping[label_key] = label
    
    print(f"--> Created mapping for {len(user_mapping)} users and {len(label_mapping)} labels")
    
    # Step 6: Prepare bulk data for insertion
    print("--> Preparing release data for bulk insertion...")
    
    release_objects = []
    error_count = 0
    duplicate_count = 0
    artist_json_data = {}  # Store artist JSON data for RelatedArtists migration
    
    # Track duplicates (user + title combination)
    seen_releases = set()
    
    for release_row in releases_data:
        release_dict = dict(zip(columns, release_row))
        
        try:
            user_name = release_dict.get('created_by').strip().lower() if release_dict.get('created_by') else ''
            release_title = release_dict.get('title').strip() if release_dict.get('title') else ''
            primary_uuid = release_dict.get('primary_uuid').strip() if release_dict.get('primary_uuid') else ''
            upc = str(release_dict.get('upc_code')) if release_dict.get('upc_code') else ''
            # Skip empty titles
            if not release_title:
                error_count += 1
                continue
            
            # Find user
            if user_name not in user_mapping:
                print(f"-->  User not found: {user_name}")
                error_count += 1
                continue
            
            user = user_mapping[user_name]
            
            # Check for duplicates (same user + title combination)
            release_key = (user.id, release_title, upc)
            if release_key in seen_releases:
                duplicate_count += 1
                continue
            
            seen_releases.add(release_key)
            
            # Handle artist JSON data (store for RelatedArtists migration)
            artist_json = release_dict.get('artist', '')
            if artist_json and artist_json.strip():
                try:
                    artist_data = json.loads(artist_json)
                    # Store with user+title as key for RelatedArtists migration
                    artist_json_data[f"{user_name}:{release_title}"] = {
                        'type': 'release',
                        'artist_data': artist_data,
                        'primary_uuid': primary_uuid
                    }
                except json.JSONDecodeError as e:
                    import traceback
                    traceback.print_exc()
                    print(f"-->  Invalid JSON in artist field for release {release_title}: {e}")
            
            # Handle label foreign key
            label = None
            label_name = release_dict.get('label', '').strip() if release_dict.get('label') else ''
            if label_name:
                label_key = f"{user_name}:{label_name}"
                if label_key in label_mapping:
                    label = label_mapping[label_key]
                else:
                    print(f"-->  Label not found: {label_name} for user {user_name}")
                    # Create a new label
                    label = Label.objects.create(
                        label=label_name,
                        user=user
                    )
                    label_mapping[label_key] = label
            
            # Map album format
            old_format = release_dict.get('album_format')
            album_format = map_album_format(old_format)
            
            # Handle various field mappings
            cover_art_url = release_dict.get('cover_art_path', None) or ''
            remix_version = release_dict.get('remix_version', None) or ''
            primary_genre = release_dict.get('primary_genre', None) or 'N/A'
            secondary_genre = release_dict.get('secondary_genre', None) or 'N/A'
            language = release_dict.get('language', None) or 'N/A'
            upc = str(release_dict.get('upc_code', '')) if release_dict.get('upc_code') else ''
            reference_number = release_dict.get('reference_number', None) or ''
            grid = release_dict.get('gr_id', None) or ''
            description = release_dict.get('release_description', '') or ''
            
            # Handle boolean fields
            published = bool(release_dict.get('is_published', False))
            takedown_requested = bool(release_dict.get('takedown_requested', False))
            
            # Handle datetime fields
            published_at = None
            if release_dict.get('published_at_time'):
                try:
                    published_at = release_dict['published_at_time']
                except (ValueError, TypeError) as e:
                    import traceback
                    traceback.print_exc()
                    print(f"-->  Invalid published_at_time for release {release_title}: {e}")
            
            # Handle license data
            license_info = license_data.get(primary_uuid, {})
            price_category = map_price_category(license_info.get('price_category'))
            digital_release_date = parse_date_string(license_info.get('digital_release_date'))
            original_release_date = parse_date_string(license_info.get('original_release_date'))
            license_type = map_license_type(license_info.get('license_type'))
            license_holder_year = str(license_info.get('license_holder_year', ''))[:4]
            license_holder_name = str(license_info.get('license_holder_name', ''))[:255]
            copyright_recording_year = str(license_info.get('copyright_recording_year', ''))[:255]
            copyright_recording_text = str(license_info.get('copyright_recording_text', ''))[:255]
            territories = str(license_info.get('territories', 'Entire World'))[:255]
            
            # Truncate fields if too long
            if len(release_title) > 255:
                release_title = release_title[:252] + "..."
            if len(description) > 1024:
                description = description[:1021] + "..."
            if len(cover_art_url) > 1024:
                cover_art_url = cover_art_url[:1021] + "..."
            if len(remix_version) > 255:
                remix_version = remix_version[:252] + "..."
            
            # Create Release object (not saved yet)
            release_obj = Release(
                title=release_title,
                cover_art_url=cover_art_url,
                remix_version=remix_version,
                primary_genre=primary_genre,
                secondary_genre=secondary_genre,
                language=language,
                album_format=album_format,
                upc=upc,
                reference_number=reference_number,
                grid=grid,
                description=description,
                created_by=user,
                published=published,
                takedown_requested=takedown_requested,
                published_at=published_at,
                label=label,
                # License fields
                price_category=price_category,
                digital_release_date=digital_release_date,
                original_release_date=original_release_date,
                license_type=license_type,
                license_holder_year=license_holder_year,
                license_holder_name=license_holder_name,
                copyright_recording_year=copyright_recording_year,
                copyright_recording_text=copyright_recording_text,
                territories=territories
            )
            
            release_objects.append(release_obj)
            
        except Exception as e:
            error_count += 1
            print(f"--> Error preparing release {release_dict.get('title', 'unknown')}: {e}")
            import traceback
            traceback.print_exc()
            continue
    
    # Step 7: Bulk insert releases
    print(f"-->Bulk inserting {len(release_objects)} releases...")
    
    try:
        # Use bulk_create for efficient insertion
        Release.objects.bulk_create(release_objects, batch_size=1000)
        
        migrated_count = len(release_objects)
        print(f"--> Successfully migrated {migrated_count} releases")
        
        # Save artist JSON data for RelatedArtists migration
        if artist_json_data:
            import pickle
            with open('data_migrations/artist_json_releases.pkl', 'wb') as f:
                pickle.dump(artist_json_data, f)
            print(f"-->Saved {len(artist_json_data)} release artist JSON records for RelatedArtists migration")
        
    except Exception as e:
        print(f"--> Error during bulk insertion: {e}")
        import traceback
        traceback.print_exc()
        return
    
    print(f"\n--> Migration Summary:")
    print(f"   --> Successfully migrated: {migrated_count} releases")
    print(f"   -->  Skipped (duplicates): {duplicate_count} releases")
    print(f"   --> Errors encountered: {error_count} releases")

def verify_releases_migration():
    """Verify the releases migration was successful"""
    print("\n--> Verifying releases migration...")
    
    # Get counts from both databases
    old_db, new_db = get_db_connections()
    
    with old_db.cursor() as cursor:
        cursor.execute("SELECT COUNT(*) FROM db2.rl_release")
        old_count = cursor.fetchone()[0]
    
    new_count = Release.objects.count()
    
    print(f"--> Release counts:")
    print(f"   Old database (db2.rl_release): {old_count}")
    print(f"   New database (Release model): {new_count}")
    
    # Note: Counts might differ due to duplicate removal
    if old_count == new_count:
        print("--> Release counts match!")
    else:
        print(f"-->  Count difference likely due to duplicate removal")
    
    # Sample data verification
    print(f"\n--> Sample release records:")
    sample_releases = Release.objects.select_related('created_by', 'label').all()[:5]
    
    for release in sample_releases:
        print(f"   {release.created_by.email}: {release.title}")
        print(f"      Format: {release.album_format}, Genre: {release.primary_genre}")
        if release.label:
            print(f"      Label: {release.label.label}")
        if release.upc:
            print(f"      UPC: {release.upc}")

def show_release_statistics():
    """Show detailed release statistics"""
    print("\n--> Detailed Release Statistics:")
    
    from django.db.models import Count, Q
    
    # Overall statistics
    total_releases = Release.objects.count()
    published_count = Release.objects.filter(published=True).count()
    with_label_count = Release.objects.exclude(label__isnull=True).count()
    with_upc_count = Release.objects.exclude(upc='').count()
    takedown_count = Release.objects.filter(takedown_requested=True).count()
    
    print(f"--> Overall Statistics:")
    print(f"   Total releases: {total_releases}")
    print(f"   Published releases: {published_count}")
    print(f"   Releases with labels: {with_label_count}")
    print(f"   Releases with UPC: {with_upc_count}")
    print(f"   Takedown requested: {takedown_count}")
    
    # Format distribution
    format_stats = Release.objects.values('album_format').annotate(
        count=Count('id')
    ).order_by('-count')
    
    print(f"\n--> Album Format Distribution:")
    for format_data in format_stats:
        print(f"   {format_data['album_format']}: {format_data['count']} releases")
    
    # Genre distribution
    genre_stats = Release.objects.values('primary_genre').annotate(
        count=Count('id')
    ).order_by('-count')[:10]
    
    print(f"\n--> Top 10 Primary Genres:")
    for genre_data in genre_stats:
        print(f"   {genre_data['primary_genre']}: {genre_data['count']} releases")
    
    # Users with most releases
    user_stats = Release.objects.values('created_by__email').annotate(
        count=Count('id')
    ).order_by('-count')[:10]
    
    print(f"\n--> Top 10 Users by Release Count:")
    for user_data in user_stats:
        print(f"   {user_data['created_by__email']}: {user_data['count']} releases")

def cleanup_releases():
    """Clean up releases data (USE WITH CAUTION!)"""
    response = input("-->  This will DELETE ALL release records. Type 'DELETE' to confirm: ")
    if response == 'DELETE':
        release_count = Release.objects.count()
        Release.objects.all().delete()
        print(f"-->  Deleted {release_count} release records")
        
        # Also clean up the artist JSON data file
        try:
            os.remove('data_migrations/artist_json_releases.pkl')
            print("-->  Deleted artist JSON data file")
        except FileNotFoundError:
            import traceback
            traceback.print_exc()
            pass
    else:
        print("--> Cleanup cancelled")

if __name__ == "__main__":
    print("[START] Starting Release Migration from db2.rl_release to Django Release model")
    print("=" * 80)
    
    try:
        cleanup_old_table()
        truncate_new_tables()
        migrate_releases()
        verify_releases_migration()
        show_release_statistics()
        print("\n--> Release migration completed successfully!")
        
    except Exception as e:
        print(f"\n--> Migration failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1) 