#!/usr/bin/env python3
"""
Data Migration Script: User Requests
====================================

This script migrates user request data from the old db2.user_requests table to the new Django Request model.

Table Mapping:
- db2.user_requests → main.Request

Field Mapping:
- request_id → (auto-generated)
- requester_user → user (CDUser foreign key)
- ticket_name → title
- description → description
- created_at → created_at (auto-set to current time for updated_at)
- status → status (mapped from old status format)
- admin_comments → feedback

Prerequisites:
1. User migration must be completed first (CDUser objects must exist)
2. Both db2 (old) and db3 (new) databases must be accessible
3. Django environment must be properly configured

Usage:
    python data_migrations/06_migrate_user_requests.py
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
from main.models import Request, CDUser

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
                'main_request',
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

def map_status(old_status):
    """
    Map old status values to new Request.STATUS choices
    
    Old possible values: various strings
    New values: PENDING, IN REVIEW, CLOSED
    """
    if not old_status:
        return Request.STATUS.PENDING
    
    old_status = str(old_status).upper().strip()
    
    # Map old status values to new ones
    if old_status in ['PENDING', 'OPEN', 'NEW', 'SUBMITTED']:
        return Request.STATUS.PENDING
    elif old_status in ['IN REVIEW', 'INREVIEW', 'IN_REVIEW', 'REVIEW', 'REVIEWING', 'PROCESSING']:
        return Request.STATUS.IN_REVIEW
    elif old_status in ['CLOSED', 'RESOLVED', 'COMPLETED', 'DONE', 'FINISHED']:
        return Request.STATUS.CLOSED
    else:
        # Default to pending for unknown statuses
        print(f"-->  Unknown status '{old_status}' - defaulting to PENDING")
        return Request.STATUS.PENDING

def migrate_user_requests():
    """
    Migrate user requests from old user_requests table to Request model
    """
    old_db, new_db = get_db_connections()
    
    # Step 1: Check prerequisites
    user_count = CDUser.objects.count()
    if user_count == 0:
        print("--> No users found. Please run user migration first.")
        return
    
    print(f"-->  Found {user_count} users in database")
    
    # Step 2: Check current state
    current_requests = Request.objects.count()
    print(f"--> Current requests in Django database: {current_requests}")
    
    if current_requests > 0:
        response = input("-->  Requests already exist. Continue? (y/N): ")
        if response.lower() != 'y':
            print("--> Migration cancelled")
            return
    
    # Step 3: Fetch all request data from old database
    print("--> Fetching user requests from old database...")
    
    with old_db.cursor() as cursor:
        cursor.execute("""
            SELECT 
                request_id,
                requester_user,
                ticket_name,
                description,
                created_at,
                status,
                admin_comments
            FROM db2.user_requests
            ORDER BY created_at DESC
        """)
        
        requests_data = cursor.fetchall()
        columns = [col[0] for col in cursor.description]
        
    print(f"--> Found {len(requests_data)} user requests to migrate")
    
    if not requests_data:
        print("-->  No user requests found in old database")
        return
    
    # Step 4: Create user mapping for faster lookups
    print("-->  Creating user mapping...")
    user_mapping = {}
    for user in CDUser.objects.all():
        user_mapping[user.email] = user
    
    print(f"--> Created mapping for {len(user_mapping)} users")
    
    # Step 5: Prepare bulk data for insertion
    print("--> Preparing request data for bulk insertion...")
    
    request_objects = []
    error_count = 0
    
    for request_row in requests_data:
        request_dict = dict(zip(columns, request_row))
        
        try:
            requester_user = request_dict.get('requester_user', '').strip().lower()
            
            # Find user
            if requester_user not in user_mapping:
                print(f"-->  User not found: {requester_user}")
                error_count += 1
                continue
            
            user = user_mapping[requester_user]
            
            # Prepare fields with length limits
            title = request_dict.get('ticket_name', '') if request_dict.get('ticket_name') is not None else ''
            title = title.strip()[:100]  # Max 100 chars
            description = request_dict.get('description', '') if request_dict.get('description') is not None else ''
            description = description.strip()[:5000]  # Max 5000 chars
            feedback = request_dict.get('admin_comments', '') if request_dict.get('admin_comments') is not None else ''
            feedback = feedback.strip()[:5000]  # Max 5000 chars
            
            # Map status
            old_status = request_dict.get('status')
            new_status = map_status(old_status)
            
            # Handle created_at
            created_at = request_dict.get('created_at')
            if not created_at:
                created_at = datetime.now()
            
            # Create Request object (not saved yet)
            request_obj = Request(
                user=user,
                title=title,
                description=description,
                feedback=feedback or '',
                status=new_status,
                created_at=created_at,
                updated_at=created_at  # Set same as created_at initially
            )
            
            request_objects.append(request_obj)
            
        except Exception as e:
            error_count += 1
            print(f"--> Error preparing request {request_dict.get('request_id', 'unknown')}: {e}")
            continue
    
    # Step 6: Bulk insert requests
    print(f"-->Bulk inserting {len(request_objects)} user requests...")
    
    try:
        # Use bulk_create for efficient insertion
        Request.objects.bulk_create(request_objects, batch_size=1000)
        
        migrated_count = len(request_objects)
        print(f"--> Successfully migrated {migrated_count} user requests")
        
    except Exception as e:
        print(f"--> Error during bulk insertion: {e}")
        return
    
    print(f"\n--> Migration Summary:")
    print(f"   --> Successfully migrated: {migrated_count} requests")
    print(f"   --> Errors encountered: {error_count} requests")

def verify_requests_migration():
    """Verify the requests migration was successful"""
    print("\n--> Verifying requests migration...")
    
    # Get counts from both databases
    old_db, new_db = get_db_connections()
    
    with old_db.cursor() as cursor:
        cursor.execute("SELECT COUNT(*) FROM db2.user_requests")
        old_count = cursor.fetchone()[0]
    
    new_count = Request.objects.count()
    
    print(f"--> Request counts:")
    print(f"   Old database (db2.user_requests): {old_count}")
    print(f"   New database (Request model): {new_count}")
    
    if old_count == new_count:
        print("--> Request counts match!")
    else:
        print("-->  Request counts don't match - please review")
    
    # Status distribution
    status_counts = {
        'PENDING': Request.objects.filter(status=Request.STATUS.PENDING).count(),
        'IN REVIEW': Request.objects.filter(status=Request.STATUS.IN_REVIEW).count(),
        'CLOSED': Request.objects.filter(status=Request.STATUS.CLOSED).count(),
    }
    
    print(f"\n--> Request Status Distribution:")
    for status, count in status_counts.items():
        print(f"   {status}: {count}")
    
    # Sample data verification
    print(f"\n--> Sample request records:")
    sample_requests = Request.objects.select_related('user').all()[:3]
    
    for request in sample_requests:
        title = request.title[:50] + "..." if len(request.title) > 50 else request.title
        print(f"   {request.user.email}: {title} ({request.status})")
    
    # Date range statistics
    from django.db.models import Min, Max
    
    date_stats = Request.objects.aggregate(
        oldest=Min('created_at'),
        newest=Max('created_at'),
        count=django.db.models.Count('id')
    )
    
    print(f"\n--> Request Statistics:")
    print(f"   Total requests: {date_stats['count']}")
    print(f"   Oldest request: {date_stats['oldest']}")
    print(f"   Newest request: {date_stats['newest']}")

def show_request_summary():
    """Show summary of requests by user and status"""
    print("\n--> Request Summary by Status:")
    
    # Requests by status
    from django.db.models import Count
    
    status_summary = Request.objects.values('status').annotate(
        count=Count('id')
    ).order_by('-count')
    
    for status_data in status_summary:
        print(f"   {status_data['status']}: {status_data['count']} requests")
    
    # Recent requests
    print(f"\n--> Recent Requests (Last 5):")
    recent_requests = Request.objects.select_related('user').order_by('-created_at')[:5]
    
    for i, request in enumerate(recent_requests, 1):
        title = request.title[:40] + "..." if len(request.title) > 40 else request.title
        print(f"   {i}. {request.user.email}: {title}")
        print(f"      Status: {request.status} | {request.created_at.strftime('%Y-%m-%d %H:%M')}")

def cleanup_requests():
    """Clean up requests data (USE WITH CAUTION!)"""
    response = input("-->  This will DELETE ALL request records. Type 'DELETE' to confirm: ")
    if response == 'DELETE':
        request_count = Request.objects.count()
        Request.objects.all().delete()
        print(f"-->  Deleted {request_count} request records")
    else:
        print("--> Cleanup cancelled")

if __name__ == "__main__":
    print("[START] Starting User Request Migration from db2.user_requests to Django Request model")
    print("=" * 90)
    
    try:
        # Import required modules for verification
        import django.db.models
        
        cleanup_old_table()
        truncate_new_tables()
        migrate_user_requests()
        verify_requests_migration()
        show_request_summary()
        print("\n--> User request migration completed successfully!")
        
    except Exception as e:
        print(f"\n--> Migration failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1) 