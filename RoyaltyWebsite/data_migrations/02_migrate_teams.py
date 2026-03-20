#!/usr/bin/env python3
"""
Data Migration Script: Teams to CDUser Parent-Child Relationships
===============================================================

This script migrates team relationships from the old db2.teams table to 
CDUser parent-child relationships in the new Django structure.

The old teams table structure:
- member_username (child)
- member_password 
- leader_username (parent)

New structure:
- CDUser.parent field points to the parent user
- Team members become users with parent relationships

Prerequisites:
1. User migration (01_migrate_users.py) must be completed first
2. Both db2 (old) and db3 (new) databases must be accessible  
3. Django environment must be properly configured

Usage:
    python data_migrations/02_migrate_teams.py
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
from main.models import CDUser
from django.contrib.auth.hashers import make_password

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
    Note: This migration only updates existing CDUser records, doesn't truncate
    """
    print("-->  No tables to truncate for team migration (updates existing users)")
    print("--> Table truncation completed")

def migrate_teams():
    """
    Migrate team relationships from old teams table to CDUser parent relationships
    """
    old_db, new_db = get_db_connections()
    
    # Step 1: Fetch all team relationships from old database
    print("--> Fetching team relationships from old database...")
    
    with old_db.cursor() as cursor:
        cursor.execute("""
            SELECT 
                LOWER(member_username) as member_username,
                LOWER(leader_username) as leader_username
            FROM db2.teams
            ORDER BY leader_username, member_username
        """)
        
        teams_data = cursor.fetchall()
        columns = [col[0] for col in cursor.description]
        
    print(f"--> Found {len(teams_data)} team relationships to migrate")
    
    if not teams_data:
        print("--> No team relationships found. Migration completed.")
        return
    
    # Step 2: Pre-fetch all existing users to avoid repeated queries
    print("--> Pre-fetching existing users...")
    existing_users = {user.email: user for user in CDUser.objects.all()}
    print(f"--> Pre-fetched {len(existing_users)} existing users")
    
    # Step 3: Process team relationships and prepare bulk data
    migrated_count = 0
    error_count = 0
    created_members = 0
    updated_relationships = 0
    
    # Lists for bulk operations
    users_to_create = []
    password_entries = []
    
    for team_row in teams_data:
        team_dict = dict(zip(columns, team_row))
        
        try:
            member_username = team_dict['member_username']
            leader_username = team_dict['leader_username']
            member_password = team_dict.get('member_password', '')
            
            print(f"--> Processing team relationship: {member_username} -> {leader_username}")
            
            # Find the leader user from pre-fetched data
            leader_user = existing_users.get(leader_username)
            if not leader_user:
                print(f"--> Leader user not found: {leader_username}")
                error_count += 1
                continue
            
            # Check if member user exists in pre-fetched data
            member_user_db = existing_users.get(member_username)
            if member_user_db:
                print(f"--> Member User {member_user_db.email} already exists")
            else:
                # Prepare new member user for bulk creation
                print(f"--> Preparing new member user: {member_username}")
                
                password = f'temp_password_{member_username}'
                django_password = make_password(password)

                # Store password entry for batch write
                password_entries.append(f"{member_username}: {password}:{django_password} || member || {leader_username}\n")
                
                # Create user object for bulk insertion
                new_user = CDUser(
                    email=member_username,
                    password=django_password,
                    is_active=True,
                    role=CDUser.ROLES.MEMBER,
                    first_name='Team',
                    last_name='Member',
                    country=leader_user.country,
                    language=leader_user.language,
                    contact_phone=leader_user.contact_phone,
                    company_contact_phone=leader_user.company_contact_phone,
                    pan=leader_user.pan,
                    parent=leader_user,
                    created_at=datetime.now(),
                    updated_at=datetime.now()
                )
                
                users_to_create.append(new_user)
                created_members += 1
            
            migrated_count += 1
            
        except Exception as e:
            error_count += 1
            print(f"--> Error processing team relationship {team_dict.get('member_username', 'unknown')} -> {team_dict.get('leader_username', 'unknown')}: {e}")
            continue
    
    # Step 4: Perform bulk operations
    if users_to_create:
        print(f"[START] Performing bulk creation of {len(users_to_create)} member users...")
        CDUser.objects.bulk_create(users_to_create, batch_size=100)
        print(f"--> Bulk created {len(users_to_create)} member users")
    
    if password_entries:
        print(f"--> Writing {len(password_entries)} password entries...")
        with open('passwords.txt', 'a') as f:
            f.writelines(password_entries)
        print("--> Password entries written")
    
    print(f"\n--> Team Migration Summary:")
    print(f"   --> Total relationships processed: {migrated_count}")
    print(f"   --> New member users created: {created_members}")
    print(f"   --> Existing users updated with parent: {updated_relationships}")
    print(f"   --> Errors encountered: {error_count}")

def verify_team_migration():
    """Verify the team migration was successful"""
    print("\n--> Verifying team migration...")
    
    # Count users by role
    role_counts = {
        'admin': CDUser.objects.filter(role=CDUser.ROLES.ADMIN).count(),
        'intermediate': CDUser.objects.filter(role=CDUser.ROLES.INTERMEDIATE).count(),
        'normal': CDUser.objects.filter(role=CDUser.ROLES.NORMAL).count(),
        'member': CDUser.objects.filter(role=CDUser.ROLES.MEMBER).count(),
    }
    
    # Count parent-child relationships
    users_with_parents = CDUser.objects.filter(parent__isnull=False).count()
    users_with_children = CDUser.objects.filter(cduser__isnull=False).distinct().count()
    
    print(f"--> User counts by role:")
    for role, count in role_counts.items():
        print(f"   {role.capitalize()}: {count}")
    
    print(f"--> Users with parent relationships: {users_with_parents}")
    print(f"--> Users with children: {users_with_children}")
    
    # Show some sample relationships
    print(f"\n--> Sample parent-child relationships:")
    sample_relationships = CDUser.objects.filter(parent__isnull=False).select_related('parent')[:5]
    
    for user in sample_relationships:
        print(f"   {user.email} ({user.role}) -> {user.parent.email} ({user.parent.role})")

def show_team_hierarchy():
    """Display team hierarchy for verification"""
    print("\n-->  Team Hierarchy:")
    
    # Get all parent users (users who have children)
    parent_users = CDUser.objects.filter(cduser__isnull=False).distinct()
    
    for parent in parent_users:
        children = parent.cduser_set.all()
        print(f"\n--> {parent.email} ({parent.role}):")
        for child in children:
            print(f"   └── {child.email} ({child.role})")

if __name__ == "__main__":
    print("[START] Starting Team Migration from db2.teams to CDUser parent-child relationships")
    print("=" * 80)
    
    try:
        # Check if users exist first
        user_count = CDUser.objects.count()
        if user_count == 0:
            print("--> No users found. Please run user migration (01_migrate_users.py) first.")
            sys.exit(1)
        
        print(f"--> Found {user_count} existing users")
        
        cleanup_old_table()
        truncate_new_tables()
        migrate_teams()
        verify_team_migration()
        show_team_hierarchy()
        print("\n--> Team migration completed successfully!")
        
    except Exception as e:
        print(f"\n--> Migration failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1) 