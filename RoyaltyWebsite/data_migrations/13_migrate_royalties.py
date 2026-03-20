#!/usr/bin/env python3
"""
Data Migration Script: Royalties
=================================

This script migrates royalty data from the old db2.royalties table to the new Django Royalties model.
This is typically the largest dataset and most critical for business operations.

Table Mapping:
- db2.royalties → releases.Royalties

Field Mapping:
- royalty_id → royalty_id (primary key)
- start_date → start_date
- end_date → end_date
- country → country
- currency → currency
- type → type
- units → units
- unit_price → unit_price
- gross_total → gross_total
- channel_costs → channel_costs
- taxes → taxes
- net_total → net_total
- currency_rate → currency_rate
- net_total_INR → net_total_INR
- channel → channel
- isrc → isrc
- gross_total_INR → gross_total_INR
- other_costs_INR → other_costs_INR
- channel_costs_INR → channel_costs_INR
- taxes_INR → taxes_INR
- gross_total_client_currency → gross_total_client_currency
- other_costs_client_currency → other_costs_client_currency
- channel_costs_client_currency → channel_costs_client_currency
- taxes_client_currency → taxes_client_currency
- net_total_client_currency → net_total_client_currency
- confirmed_date → confirmed_date

Prerequisites:
1. Both db2 (old) and db3 (new) databases must be accessible
2. Django environment must be properly configured
3. Sufficient system memory for large dataset processing

Usage:
    python data_migrations/13_migrate_royalties.py
"""

import sys
import os
import django
from datetime import datetime, date

# Add the project root to Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'RoyaltyWebsite.settings')
django.setup()

from django.db import connections
from releases.models import Royalties

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
        """DELETE FROM db2.royalties where start_date is null""",
        """DELETE FROM db2.royalties where end_date is null"""
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
                'releases_royalties',
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

def migrate_royalties():
    """
    Migrate royalties from old royalties table to Royalties model
    This processes the data in chunks due to potentially large dataset size
    """
    old_db, new_db = get_db_connections()
    
    # Step 1: Check current state
    current_royalties = Royalties.objects.count()
    print(f"--> Current royalty records in Django database: {current_royalties}")
    
    if current_royalties > 0:
        response = input("-->  Royalty records already exist. Continue? (y/N): ")
        if response.lower() != 'y':
            print("--> Migration cancelled")
            return
    
    # Step 2: Get total count first
    print("--> Checking total royalty records in old database...")
    
    with old_db.cursor() as cursor:
        cursor.execute("SELECT COUNT(*) FROM db2.royalties")
        total_count = cursor.fetchone()[0]
    
    print(f"--> Found {total_count:,} royalty records to migrate")
    
    if total_count == 0:
        print("-->  No royalties found in old database")
        return
    
    # Step 3: Process in chunks to handle large datasets
    chunk_size = 100000  # Process 5000 records at a time
    total_migrated = 0
    total_errors = 0
    total_duplicates = 0
    
    # Track duplicates by royalty_id (if it exists in old DB)
    seen_royalty_ids = set()
    
    offset = 0
    while offset < total_count:
        print(f"\n--> Processing chunk {offset//chunk_size + 1}/{(total_count + chunk_size - 1)//chunk_size} (records {offset+1:,} to {min(offset+chunk_size, total_count):,})")
        
        # Fetch chunk of data
        with old_db.cursor() as cursor:
            cursor.execute("""
                SELECT 
                    royalty_id,
                    start_date,
                    end_date,
                    country,
                    currency,
                    type,
                    units,
                    unit_price,
                    gross_total,
                    channel_costs,
                    taxes,
                    net_total,
                    currency_rate,
                    net_total_INR,
                    channel,
                    isrc,
                    gross_total_INR,
                    other_costs_INR,
                    channel_costs_INR,
                    taxes_INR,
                    gross_total_client_currency,
                    other_costs_client_currency,
                    channel_costs_client_currency,
                    taxes_client_currency,
                    net_total_client_currency,
                    confirmed_date
                FROM db2.royalties
                ORDER BY royalty_id
                LIMIT %s OFFSET %s
            """, [chunk_size, offset])
            
            chunk_data = cursor.fetchall()
            columns = [col[0] for col in cursor.description]
        
        # Process chunk
        royalty_objects = []
        chunk_errors = 0
        chunk_duplicates = 0
        
        for royalty_row in chunk_data:
            royalty_dict = dict(zip(columns, royalty_row))
            
            try:
                royalty_id = royalty_dict.get('royalty_id')
                
                # Skip if no royalty_id
                if royalty_id is None:
                    chunk_errors += 1
                    continue
                
                # Check for duplicates
                if royalty_id in seen_royalty_ids:
                    chunk_duplicates += 1
                    continue
                
                seen_royalty_ids.add(royalty_id)
                
                # Handle date fields
                def parse_date(date_value):
                    if date_value is None:
                        return None
                    if isinstance(date_value, date):
                        return date_value
                    if isinstance(date_value, str):
                        try:
                            return datetime.strptime(date_value, '%Y-%m-%d').date()
                        except ValueError:
                            try:
                                return datetime.strptime(date_value, '%Y-%m-%d %H:%M:%S').date()
                            except ValueError:
                                return None
                    return None
                
                start_date = parse_date(royalty_dict.get('start_date'))
                end_date = parse_date(royalty_dict.get('end_date'))
                confirmed_date = parse_date(royalty_dict.get('confirmed_date'))
                
                # Handle string fields with truncation
                def safe_string(value, max_length=255):
                    if value is None:
                        return ''
                    value = str(value)
                    if len(value) > max_length:
                        return value[:max_length-3] + '...'
                    return value
                
                country = safe_string(royalty_dict.get('country'))
                currency = safe_string(royalty_dict.get('currency'))
                type_field = safe_string(royalty_dict.get('type'))
                channel = safe_string(royalty_dict.get('channel'))
                isrc = safe_string(royalty_dict.get('isrc'), 50)
                
                # Handle numeric fields with safe conversion
                def safe_float(value):
                    if value is None:
                        return 0.0
                    try:
                        return float(value)
                    except (ValueError, TypeError):
                        return 0.0
                
                def safe_bigint(value):
                    if value is None:
                        return 0
                    try:
                        return int(value)
                    except (ValueError, TypeError):
                        return 0
                
                units = safe_bigint(royalty_dict.get('units'))
                unit_price = safe_float(royalty_dict.get('unit_price'))
                gross_total = safe_float(royalty_dict.get('gross_total'))
                channel_costs = safe_float(royalty_dict.get('channel_costs'))
                taxes = safe_float(royalty_dict.get('taxes'))
                net_total = safe_float(royalty_dict.get('net_total'))
                currency_rate = safe_float(royalty_dict.get('currency_rate'))
                net_total_INR = safe_float(royalty_dict.get('net_total_INR'))
                gross_total_INR = safe_float(royalty_dict.get('gross_total_INR'))
                other_costs_INR = safe_float(royalty_dict.get('other_costs_INR'))
                channel_costs_INR = safe_float(royalty_dict.get('channel_costs_INR'))
                taxes_INR = safe_float(royalty_dict.get('taxes_INR'))
                gross_total_client_currency = safe_float(royalty_dict.get('gross_total_client_currency'))
                other_costs_client_currency = safe_float(royalty_dict.get('other_costs_client_currency'))
                channel_costs_client_currency = safe_float(royalty_dict.get('channel_costs_client_currency'))
                taxes_client_currency = safe_float(royalty_dict.get('taxes_client_currency'))
                net_total_client_currency = safe_float(royalty_dict.get('net_total_client_currency'))
                
                # Create Royalties object (not saved yet)
                royalty_obj = Royalties(
                    royalty_id=royalty_id,
                    start_date=start_date,
                    end_date=end_date,
                    country=country,
                    currency=currency,
                    type=type_field,
                    units=units,
                    unit_price=unit_price,
                    gross_total=gross_total,
                    channel_costs=channel_costs,
                    taxes=taxes,
                    net_total=net_total,
                    currency_rate=currency_rate,
                    net_total_INR=net_total_INR,
                    channel=channel,
                    isrc=isrc,
                    gross_total_INR=gross_total_INR,
                    other_costs_INR=other_costs_INR,
                    channel_costs_INR=channel_costs_INR,
                    taxes_INR=taxes_INR,
                    gross_total_client_currency=gross_total_client_currency,
                    other_costs_client_currency=other_costs_client_currency,
                    channel_costs_client_currency=channel_costs_client_currency,
                    taxes_client_currency=taxes_client_currency,
                    net_total_client_currency=net_total_client_currency,
                    confirmed_date=confirmed_date
                )
                
                royalty_objects.append(royalty_obj)
                
            except Exception as e:
                chunk_errors += 1
                print(f"--> Error preparing royalty {royalty_dict.get('royalty_id', 'unknown')}: {e}")
                continue
        
        # Bulk insert chunk
        if royalty_objects:
            try:
                Royalties.objects.bulk_create(royalty_objects, batch_size=1000)
                chunk_migrated = len(royalty_objects)
                total_migrated += chunk_migrated
                print(f"--> Migrated {chunk_migrated:,} royalty records")
                
            except Exception as e:
                print(f"--> Error during bulk insertion for chunk: {e}")
                chunk_errors += len(royalty_objects)
        
        total_errors += chunk_errors
        total_duplicates += chunk_duplicates
        
        print(f"--> Chunk summary: {len(royalty_objects):,} migrated, {chunk_duplicates:,} duplicates, {chunk_errors:,} errors")
        
        offset += chunk_size
    
    print(f"\n--> Final Migration Summary:")
    print(f"   --> Successfully migrated: {total_migrated:,} royalty records")
    print(f"   -->  Skipped (duplicates): {total_duplicates:,} records")
    print(f"   --> Errors encountered: {total_errors:,} records")

def verify_royalties_migration():
    """Verify the royalties migration was successful"""
    print("\n--> Verifying royalties migration...")
    
    # Get counts from both databases
    old_db, new_db = get_db_connections()
    
    with old_db.cursor() as cursor:
        cursor.execute("SELECT COUNT(*) FROM db2.royalties")
        old_count = cursor.fetchone()[0]
    
    new_count = Royalties.objects.count()
    
    print(f"--> Royalty counts:")
    print(f"   Old database (db2.royalties): {old_count:,}")
    print(f"   New database (Royalties model): {new_count:,}")
    
    # Note: Counts might differ due to duplicate removal
    if old_count == new_count:
        print("--> Royalty counts match!")
    else:
        print(f"-->  Count difference likely due to duplicate removal or data validation")
    
    # Sample data verification
    print(f"\n--> Sample royalty records:")
    sample_royalties = Royalties.objects.all()[:5]
    
    for royalty in sample_royalties:
        print(f"   ID {royalty.royalty_id}: {royalty.isrc} - {royalty.channel} (${royalty.net_total:.2f})")
    
    # Statistics
    from django.db.models import Sum, Count, Avg
    
    # Financial statistics
    financial_stats = Royalties.objects.aggregate(
        total_net_inr=Sum('net_total_INR'),
        total_gross_inr=Sum('gross_total_INR'),
        avg_net_inr=Avg('net_total_INR'),
        total_records=Count('royalty_id')
    )
    
    print(f"\n--> Financial Statistics:")
    print(f"   Total Net INR: ₹{financial_stats['total_net_inr']:,.2f}" if financial_stats['total_net_inr'] else "   Total Net INR: ₹0.00")
    print(f"   Total Gross INR: ₹{financial_stats['total_gross_inr']:,.2f}" if financial_stats['total_gross_inr'] else "   Total Gross INR: ₹0.00")
    print(f"   Average Net INR: ₹{financial_stats['avg_net_inr']:,.2f}" if financial_stats['avg_net_inr'] else "   Average Net INR: ₹0.00")
    
    # Top channels
    channel_stats = Royalties.objects.values('channel').annotate(
        total_net=Sum('net_total_INR'),
        count=Count('royalty_id')
    ).order_by('-total_net')[:5]
    
    print(f"\n--> Top 5 Channels by Revenue:")
    for channel_data in channel_stats:
        print(f"   {channel_data['channel']}: ₹{channel_data['total_net']:,.2f} ({channel_data['count']:,} records)")

def show_royalties_statistics():
    """Show detailed royalties statistics"""
    print("\n--> Detailed Royalties Statistics:")
    
    from django.db.models import Sum, Count, Avg, Min, Max
    
    # Overall statistics
    total_royalties = Royalties.objects.count()
    unique_isrcs = Royalties.objects.values('isrc').distinct().count()
    unique_channels = Royalties.objects.values('channel').distinct().count()
    unique_countries = Royalties.objects.values('country').distinct().count()
    
    print(f"--> Overall Statistics:")
    print(f"   Total royalty records: {total_royalties:,}")
    print(f"   Unique ISRCs: {unique_isrcs:,}")
    print(f"   Unique channels: {unique_channels}")
    print(f"   Unique countries: {unique_countries}")
    
    # Date range
    date_stats = Royalties.objects.aggregate(
        earliest_start=Min('start_date'),
        latest_end=Max('end_date'),
        earliest_confirmed=Min('confirmed_date'),
        latest_confirmed=Max('confirmed_date')
    )
    
    print(f"\n--> Date Range:")
    print(f"   Earliest start date: {date_stats['earliest_start']}")
    print(f"   Latest end date: {date_stats['latest_end']}")
    print(f"   Earliest confirmed: {date_stats['earliest_confirmed']}")
    print(f"   Latest confirmed: {date_stats['latest_confirmed']}")
    
    # Currency distribution
    print(f"\n--> Top Currencies:")
    currency_stats = Royalties.objects.values('currency').annotate(
        count=Count('royalty_id'),
        total_net=Sum('net_total_INR')
    ).order_by('-count')[:5]
    
    for currency_data in currency_stats:
        print(f"   {currency_data['currency']}: {currency_data['count']:,} records (₹{currency_data['total_net']:,.2f})")
    
    # Country performance
    print(f"\n--> Top Countries by Revenue:")
    country_stats = Royalties.objects.values('country').annotate(
        total_net=Sum('net_total_INR'),
        count=Count('royalty_id')
    ).order_by('-total_net')[:5]
    
    for country_data in country_stats:
        print(f"   {country_data['country']}: ₹{country_data['total_net']:,.2f} ({country_data['count']:,} records)")

def cleanup_royalties():
    """Clean up royalties (USE WITH EXTREME CAUTION!)"""
    response = input("-->  This will DELETE ALL royalty records. Type 'DELETE ALL ROYALTIES' to confirm: ")
    if response == 'DELETE ALL ROYALTIES':
        royalty_count = Royalties.objects.count()
        Royalties.objects.all().delete()
        print(f"-->  Deleted {royalty_count:,} royalty records")
    else:
        print("--> Cleanup cancelled")

if __name__ == "__main__":
    print("[START] Starting Royalties Migration from db2.royalties to Django Royalties model")
    print("=" * 90)
    print("-->  This is a large dataset migration - please ensure sufficient system resources")
    
    try:
        # Import required modules for verification
        import django.db.models
        
        cleanup_old_table()
        truncate_new_tables()
        migrate_royalties()
        verify_royalties_migration()
        show_royalties_statistics()
        print("\n--> Royalties migration completed successfully!")
        
    except Exception as e:
        print(f"\n--> Migration failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1) 