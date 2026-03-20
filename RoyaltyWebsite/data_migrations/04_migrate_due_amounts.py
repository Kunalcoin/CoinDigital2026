#!/usr/bin/env python3
"""
Data Migration Script: Due Amounts
==================================

This script migrates due amount data from the old db2.due_amount_agg table to the new Django DueAmount model.

Table Mapping:
- db2.due_amount_agg → main.DueAmount

Field Mapping:
- username → user (CDUser foreign key)
- amount_due → amount

Prerequisites:
1. User migration must be completed first (CDUser objects must exist)
2. Both db2 (old) and db3 (new) databases must be accessible
3. Django environment must be properly configured

Usage:
    python data_migrations/04_migrate_due_amounts.py
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
from main.models import DueAmount, CDUser

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
                'main_dueamount',
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

def migrate_due_amounts():
    """
    Migrate due amounts from old due_amount_agg table to DueAmount model
    """
    old_db, new_db = get_db_connections()
    
    # Step 1: Check prerequisites
    user_count = CDUser.objects.count()
    if user_count == 0:
        print("--> No users found. Please run user migration first.")
        return
    
    print(f"-->  Found {user_count} users in database")
    
    # Step 2: Check current state
    current_due_amounts = DueAmount.objects.count()
    print(f"--> Current due amounts in Django database: {current_due_amounts}")
    
    if current_due_amounts > 0:
        response = input("-->  Due amounts already exist. Continue? (y/N): ")
        if response.lower() != 'y':
            print("--> Migration cancelled")
            return
    
    # Step 3: Fetch all due amount data from old database
    print("--> Fetching due amounts from old database...")
    
    with old_db.cursor() as cursor:
        cursor.execute("""
            SELECT 
                username,
                amount_due
            FROM db2.due_amount_agg
            WHERE amount_due IS NOT NULL AND amount_due != 0
            ORDER BY username
        """)
        
        due_amounts_data = cursor.fetchall()
        columns = [col[0] for col in cursor.description]
        
    print(f"--> Found {len(due_amounts_data)} due amount records to migrate")
    
    if not due_amounts_data:
        print("-->  No due amounts found in old database")
        return
    
    # Step 4: Create user mapping for faster lookups
    print("--> Creating user mapping...")
    user_mapping = {}
    for user in CDUser.objects.all().filter(role__in=['intermediate', 'admin', 'normal']):
        user_mapping[user.email] = user
    
    print(f"--> Created mapping for {len(user_mapping)} users")
    
    # Step 5: Prepare bulk data for insertion
    print("--> Preparing due amount data for bulk insertion...")
    
    due_amount_objects = []
    error_count = 0
    skipped_count = 0
    
    for due_amount_row in due_amounts_data:
        due_amount_dict = dict(zip(columns, due_amount_row))
        
        try:
            username = due_amount_dict.get('username', '').strip().lower()
            amount_due = float(due_amount_dict.get('amount_due', 0) or 0)
            
            # Skip zero amounts
            if amount_due == 0:
                skipped_count += 1
                continue
            
            # Find user
            if username not in user_mapping:
                print(f"-->  User not found: {username}")
                error_count += 1
                continue
            
            user = user_mapping[username]
            
            # Create DueAmount object (not saved yet)
            due_amount_obj = DueAmount(
                user=user,
                amount=amount_due
            )
            
            due_amount_objects.append(due_amount_obj)
            
        except Exception as e:
            error_count += 1
            print(f"--> Error preparing due amount for {due_amount_dict.get('username', 'unknown')}: {e}")
            continue
    
    # Step 6: Bulk insert due amounts
    print(f"-->Bulk inserting {len(due_amount_objects)} due amount records...")
    
    try:
        # Use bulk_create for efficient insertion
        DueAmount.objects.bulk_create(due_amount_objects, batch_size=1000)
        
        migrated_count = len(due_amount_objects)
        print(f"--> Successfully migrated {migrated_count} due amount records")
        
    except Exception as e:
        print(f"--> Error during bulk insertion: {e}")
        return
    
    print(f"\n--> Migration Summary:")
    print(f"   --> Successfully migrated: {migrated_count} due amounts")
    print(f"   -->  Skipped (zero amounts): {skipped_count} records")
    print(f"   --> Errors encountered: {error_count} records")

def verify_due_amounts_migration():
    """Verify the due amounts migration was successful"""
    print("\n--> Verifying due amounts migration...")
    
    # Get counts from both databases
    old_db, new_db = get_db_connections()
    
    with old_db.cursor() as cursor:
        cursor.execute("""
            SELECT COUNT(*) 
            FROM db2.due_amount_agg 
            WHERE amount_due IS NOT NULL AND amount_due != 0
        """)
        old_count = cursor.fetchone()[0]
    
    new_count = DueAmount.objects.count()
    
    print(f"--> Due amount counts:")
    print(f"   Old database (db2.due_amount_agg): {old_count}")
    print(f"   New database (DueAmount model): {new_count}")
    
    if old_count == new_count:
        print("--> Due amount counts match!")
    else:
        print("-->  Due amount counts don't match - please review")
    
    # Sample data verification
    print(f"\n--> Sample due amount records:")
    sample_due_amounts = DueAmount.objects.select_related('user').all()[:3]
    
    for due_amount in sample_due_amounts:
        print(f"   {due_amount.user.email} - ₹{due_amount.amount:,.2f}")
    
    # Summary statistics
    from django.db.models import Sum, Avg, Max, Min
    
    stats = DueAmount.objects.aggregate(
        total=Sum('amount'),
        average=Avg('amount'),
        maximum=Max('amount'),
        minimum=Min('amount'),
        count=django.db.models.Count('id')
    )
    
    print(f"\n--> Due Amount Statistics:")
    print(f"   Total due amount: ₹{stats['total']:,.2f}")
    print(f"   Average due amount: ₹{stats['average']:,.2f}")
    print(f"   Maximum due amount: ₹{stats['maximum']:,.2f}")
    print(f"   Minimum due amount: ₹{stats['minimum']:,.2f}")
    print(f"   Total records: {stats['count']}")

def show_user_due_amounts():
    """Show users with highest due amounts"""
    print("\n--> Top 10 Users by Due Amount:")
    
    top_users = DueAmount.objects.select_related('user').order_by('-amount')[:10]
    
    for i, due_amount in enumerate(top_users, 1):
        print(f"   {i:2d}. {due_amount.user.email:<30} ₹{due_amount.amount:>10,.2f}")

def cleanup_due_amounts():
    """Clean up due amounts data (USE WITH CAUTION!)"""
    response = input("-->  This will DELETE ALL due amount records. Type 'DELETE' to confirm: ")
    if response == 'DELETE':
        due_amount_count = DueAmount.objects.count()
        DueAmount.objects.all().delete()
        print(f"-->  Deleted {due_amount_count} due amount records")
    else:
        print("--> Cleanup cancelled")

if __name__ == "__main__":
    print("[START] Starting Due Amount Migration from db2.due_amount_agg to Django DueAmount model")
    print("=" * 85)
    
    try:
        # Import required modules for verification
        import django.db.models
        
        cleanup_old_table()
        truncate_new_tables()
        migrate_due_amounts()
        verify_due_amounts_migration()
        show_user_due_amounts()
        print("\n--> Due amount migration completed successfully!")
        
    except Exception as e:
        print(f"\n--> Migration failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1) 