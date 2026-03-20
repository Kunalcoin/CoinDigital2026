#!/usr/bin/env python3
"""
Data Migration Script: Payments
===============================

This script migrates payment data from the old db2.payments table to the new Django Payment model.

Table Mapping:
- db2.payments → main.Payment

Field Mapping:
- id → (auto-generated)
- username → username  
- date_of_payment → date_of_payment
- amount_paid → amount_paid
- tds → tds
- tds_percentage → tds_percentage
- source_account → source_account
- sent_to_name → sent_to_name
- sent_to_account_number → sent_to_account_number
- sent_to_ifsc_code → sent_to_ifsc_code
- transfer_id → transfer_id

Prerequisites:
1. User migration must be completed first
2. Both db2 (old) and db3 (new) databases must be accessible
3. Django environment must be properly configured

Usage:
    python data_migrations/03_migrate_payments.py
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
from main.models import Payment

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
                'main_payment',
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

def migrate_payments():
    """
    Migrate payments from old payments table to Payment model
    """
    old_db, new_db = get_db_connections()
    
    # Step 1: Check current state
    current_payments = Payment.objects.count()
    print(f"--> Current payments in Django database: {current_payments}")
    
    if current_payments > 0:
        response = input("-->  Payments already exist. Continue? (y/N): ")
        if response.lower() != 'y':
            print("--> Migration cancelled")
            return
    
    # Step 2: Fetch all payment data from old database
    print("--> Fetching payments from old database...")
    
    with old_db.cursor() as cursor:
        cursor.execute("""
            SELECT 
                id,
                username,
                date_of_payment,
                amount_paid,
                tds,
                tds_percentage,
                source_account,
                sent_to_name,
                sent_to_account_number,
                sent_to_ifsc_code,
                transfer_id
            FROM db2.payments
            ORDER BY id
        """)
        
        payments_data = cursor.fetchall()
        columns = [col[0] for col in cursor.description]
        
    print(f"--> Found {len(payments_data)} payments to migrate")
    
    if not payments_data:
        print("--> No payments found in old database")
        return
    
    # Step 3: Prepare bulk data for insertion
    print("--> Preparing payment data for bulk insertion...")
    
    payment_objects = []
    error_count = 0
    
    for payment_row in payments_data:
        payment_dict = dict(zip(columns, payment_row))
        
        try:
            # Create Payment object (not saved yet)
            payment_obj = Payment(
                username=payment_dict.get('username', '') or '',
                date_of_payment=payment_dict.get('date_of_payment'),
                amount_paid=float(payment_dict.get('amount_paid', 0) or 0),
                tds=float(payment_dict.get('tds', 0) or 0),
                tds_percentage=int(payment_dict.get('tds_percentage', 0) or 0),
                source_account=payment_dict.get('source_account', '') or '',
                sent_to_name=payment_dict.get('sent_to_name', '') or '',
                sent_to_account_number=payment_dict.get('sent_to_account_number', '') or '',
                sent_to_ifsc_code=payment_dict.get('sent_to_ifsc_code', '') or '',
                transfer_id=payment_dict.get('transfer_id', '') or ''
            )
            
            payment_objects.append(payment_obj)
            
        except Exception as e:
            error_count += 1
            print(f"--> Error preparing payment {payment_dict.get('id', 'unknown')}: {e}")
            continue
    
    # Step 4: Bulk insert payments
    print(f"--> Bulk inserting {len(payment_objects)} payments...")
    
    try:
        # Use bulk_create for efficient insertion
        Payment.objects.bulk_create(payment_objects, batch_size=1000)
        
        migrated_count = len(payment_objects)
        print(f"--> Successfully migrated {migrated_count} payments")
        
    except Exception as e:
        print(f"--> Error during bulk insertion: {e}")
        return
    
    print(f"\n--> Migration Summary:")
    print(f"   --> Successfully migrated: {migrated_count} payments")
    print(f"   --> Errors encountered: {error_count} payments")

def verify_payments_migration():
    """Verify the payments migration was successful"""
    print("\n--> Verifying payments migration...")
    
    # Get counts from both databases
    old_db, new_db = get_db_connections()
    
    with old_db.cursor() as cursor:
        cursor.execute("SELECT COUNT(*) FROM db2.payments")
        old_count = cursor.fetchone()[0]
    
    new_count = Payment.objects.count()
    
    print(f"--> Payment counts:")
    print(f"   Old database (db2.payments): {old_count}")
    print(f"   New database (Payment model): {new_count}")
    
    if old_count == new_count:
        print("--> Payment counts match!")
    else:
        print("-->  Payment counts don't match - please review")
    
    # Sample data verification
    print(f"\n--> Sample payment records:")
    sample_payments = Payment.objects.all()[:3]
    
    for payment in sample_payments:
        print(f"   {payment.username} - ₹{payment.amount_paid} on {payment.date_of_payment}")
    
    # Summary statistics
    total_amount = Payment.objects.aggregate(
        total=django.db.models.Sum('amount_paid')
    )['total'] or 0
    
    total_tds = Payment.objects.aggregate(
        total=django.db.models.Sum('tds')
    )['total'] or 0
    
    print(f"\n--> Payment Statistics:")
    print(f"   Total amount paid: ₹{total_amount:,.2f}")
    print(f"   Total TDS: ₹{total_tds:,.2f}")

def cleanup_payments():
    """Clean up payments data (USE WITH CAUTION!)"""
    response = input("-->  This will DELETE ALL payment records. Type 'DELETE' to confirm: ")
    if response == 'DELETE':
        payment_count = Payment.objects.count()
        Payment.objects.all().delete()
        print(f"-->  Deleted {payment_count} payment records")
    else:
        print("--> Cleanup cancelled")

if __name__ == "__main__":
    print("[START] Starting Payment Migration from db2.payments to Django Payment model")
    print("=" * 75)
    
    try:
        # Import required modules for verification
        import django.db.models
        
        cleanup_old_table()
        truncate_new_tables()
        migrate_payments()
        verify_payments_migration()
        print("\n--> Payment migration completed successfully!")
        
    except Exception as e:
        print(f"\n--> Migration failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1) 