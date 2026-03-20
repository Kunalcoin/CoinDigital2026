#!/usr/bin/env python3
"""
Data Migration Script: Unique Codes (Assignable Codes)
======================================================

This script migrates unique code data from the old db2.assignable_code table to the new Django UniqueCode model.

Table Mapping:
- db2.assignable_code → releases.UniqueCode

Field Mapping:
- type → type (upc/isrc mapping)
- code → code
- is_assigned → assigned

Prerequisites:
1. Both db2 (old) and db3 (new) databases must be accessible
2. Django environment must be properly configured

Usage:
    python data_migrations/07_migrate_unique_codes.py
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
from releases.models import UniqueCode

def get_db_connections():
    """Get database connections for old and new databases"""
    try:
        print("Getting database connections...")
        print(connections.all)
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
                'releases_uniquecode',
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

def map_code_type(old_type):
    """
    Map old type values to new UniqueCode.TYPE choices
    
    Old possible values: various strings
    New values: upc, isrc
    """
    if not old_type:
        return UniqueCode.TYPE.ISRC  # Default
    
    old_type = str(old_type).lower().strip()
    
    # Map old type values to new ones
    if old_type in ['upc', 'upc_code', 'upccode']:
        return UniqueCode.TYPE.UPC
    elif old_type in ['isrc', 'isrc_code', 'isrccode']:
        return UniqueCode.TYPE.ISRC
    else:
        # Default to ISRC for unknown types
        print(f"-->  Unknown type '{old_type}' - defaulting to ISRC")
        return UniqueCode.TYPE.ISRC

def migrate_unique_codes():
    """
    Migrate unique codes from old assignable_code table to UniqueCode model
    """
    old_db, new_db = get_db_connections()
    
    # Step 1: Check current state
    current_codes = UniqueCode.objects.count()
    print(f"--> Current unique codes in Django database: {current_codes}")
    
    if current_codes > 0:
        response = input("-->  Unique codes already exist. Continue? (y/N): ")
        if response.lower() != 'y':
            print("--> Migration cancelled")
            return
    
    # Step 2: Fetch all unique code data from old database
    print("--> Fetching unique codes from old database...")
    
    with old_db.cursor() as cursor:
        cursor.execute("""
            SELECT 
                type,
                code,
                is_assigned
            FROM db2.assignable_code
            ORDER BY type, code
        """)
        
        codes_data = cursor.fetchall()
        columns = [col[0] for col in cursor.description]
        
    print(f"--> Found {len(codes_data)} unique codes to migrate")
    
    if not codes_data:
        print("-->  No unique codes found in old database")
        return
    
    # Step 3: Prepare bulk data for insertion
    print("--> Preparing unique code data for bulk insertion...")
    
    code_objects = []
    error_count = 0
    duplicate_count = 0
    
    # Track duplicates
    seen_codes = set()
    
    for code_row in codes_data:
        code_dict = dict(zip(columns, code_row))
        
        try:
            code_value = code_dict.get('code', '').strip()
            
            # Skip empty codes
            if not code_value:
                error_count += 1
                continue
            
            # Check for duplicates
            if code_value in seen_codes:
                duplicate_count += 1
                print(f"-->  Duplicate code found: {code_value}")
                continue
            
            seen_codes.add(code_value)
            
            # Map type
            old_type = code_dict.get('type')
            new_type = map_code_type(old_type)
            
            # Handle assignment status
            is_assigned = code_dict.get('is_assigned')
            if is_assigned is None:
                is_assigned = False
            else:
                # Convert to boolean
                is_assigned = bool(is_assigned)
            
            # Create UniqueCode object (not saved yet)
            code_obj = UniqueCode(
                type=new_type,
                code=code_value,
                assigned=is_assigned
            )
            
            code_objects.append(code_obj)
            
        except Exception as e:
            error_count += 1
            print(f"--> Error preparing code {code_dict.get('code', 'unknown')}: {e}")
            continue
    
    # Step 4: Bulk insert unique codes
    print(f"-->Bulk inserting {len(code_objects)} unique codes...")
    
    try:
        # Use bulk_create for efficient insertion
        UniqueCode.objects.bulk_create(code_objects, batch_size=1000)
        
        migrated_count = len(code_objects)
        print(f"--> Successfully migrated {migrated_count} unique codes")
        
    except Exception as e:
        print(f"--> Error during bulk insertion: {e}")
        return
    
    print(f"\n--> Migration Summary:")
    print(f"   --> Successfully migrated: {migrated_count} codes")
    print(f"   -->  Skipped (duplicates): {duplicate_count} codes")
    print(f"   --> Errors encountered: {error_count} codes")

def verify_unique_codes_migration():
    """Verify the unique codes migration was successful"""
    print("\n--> Verifying unique codes migration...")
    
    # Get counts from both databases
    old_db, new_db = get_db_connections()
    
    with old_db.cursor() as cursor:
        cursor.execute("SELECT COUNT(DISTINCT code) FROM db2.assignable_code WHERE code IS NOT NULL AND code != ''")
        old_count = cursor.fetchone()[0]
    
    new_count = UniqueCode.objects.count()
    
    print(f"--> Unique code counts:")
    print(f"   Old database (db2.assignable_code): {old_count}")
    print(f"   New database (UniqueCode model): {new_count}")
    
    if old_count == new_count:
        print("--> Unique code counts match!")
    else:
        print("-->  Unique code counts don't match - please review")
    
    # Type distribution
    type_counts = {
        'UPC': UniqueCode.objects.filter(type=UniqueCode.TYPE.UPC).count(),
        'ISRC': UniqueCode.objects.filter(type=UniqueCode.TYPE.ISRC).count(),
    }
    
    print(f"\n--> Code Type Distribution:")
    for code_type, count in type_counts.items():
        print(f"   {code_type}: {count}")
    
    # Assignment status
    assignment_counts = {
        'Assigned': UniqueCode.objects.filter(assigned=True).count(),
        'Available': UniqueCode.objects.filter(assigned=False).count(),
    }
    
    print(f"\n--> Assignment Status:")
    for status, count in assignment_counts.items():
        print(f"   {status}: {count}")
    
    # Sample data verification
    print(f"\n--> Sample code records:")
    sample_codes = UniqueCode.objects.all()[:5]
    
    for code in sample_codes:
        status = "--> Assigned" if code.assigned else "--> Available"
        print(f"   {code.type.upper()}: {code.code} - {status}")

def show_code_statistics():
    """Show detailed code statistics"""
    print("\n--> Detailed Code Statistics:")
    
    # Codes by type and status
    from django.db.models import Count, Q
    
    stats = UniqueCode.objects.aggregate(
        total_upc=Count('id', filter=Q(type=UniqueCode.TYPE.UPC)),
        assigned_upc=Count('id', filter=Q(type=UniqueCode.TYPE.UPC, assigned=True)),
        total_isrc=Count('id', filter=Q(type=UniqueCode.TYPE.ISRC)),
        assigned_isrc=Count('id', filter=Q(type=UniqueCode.TYPE.ISRC, assigned=True)),
        total_codes=Count('id'),
        total_assigned=Count('id', filter=Q(assigned=True))
    )
    
    print(f"--> UPC Codes:")
    print(f"   Total: {stats['total_upc']}")
    print(f"   Assigned: {stats['assigned_upc']}")
    print(f"   Available: {stats['total_upc'] - stats['assigned_upc']}")
    
    print(f"\n--> ISRC Codes:")
    print(f"   Total: {stats['total_isrc']}")
    print(f"   Assigned: {stats['assigned_isrc']}")
    print(f"   Available: {stats['total_isrc'] - stats['assigned_isrc']}")
    
    print(f"\n--> Overall:")
    print(f"   Total codes: {stats['total_codes']}")
    print(f"   Total assigned: {stats['total_assigned']}")
    print(f"   Total available: {stats['total_codes'] - stats['total_assigned']}")

def cleanup_unique_codes():
    """Clean up unique codes data (USE WITH CAUTION!)"""
    response = input("-->  This will DELETE ALL unique code records. Type 'DELETE' to confirm: ")
    if response == 'DELETE':
        code_count = UniqueCode.objects.count()
        UniqueCode.objects.all().delete()
        print(f"-->  Deleted {code_count} unique code records")
    else:
        print("--> Cleanup cancelled")

if __name__ == "__main__":
    print("[START] Starting Unique Code Migration from db2.assignable_code to Django UniqueCode model")
    print("=" * 95)
    
    try:
        # Import required modules for verification
        import django.db.models
        
        cleanup_old_table()
        truncate_new_tables()
        migrate_unique_codes()
        verify_unique_codes_migration()
        show_code_statistics()
        print("\n--> Unique code migration completed successfully!")
        
    except Exception as e:
        print(f"\n--> Migration failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1) 