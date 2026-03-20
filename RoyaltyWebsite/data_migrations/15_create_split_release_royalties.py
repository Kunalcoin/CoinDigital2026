#!/usr/bin/env python3
"""
Data Migration Script: Split Release Royalties
=============================================

This script creates a SplitReleaseRoyalty object for each Release, assigning 100% to the user who created the release.

Prerequisites:
1. User and Release migrations must be completed first (CDUser and Release objects must exist)
2. SplitReleaseRoyalty model must exist and be migrated
3. Django environment must be properly configured

Usage:
    python data_migrations/15_create_split_release_royalties.py
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

from releases.models import Release, SplitReleaseRoyalty
from main.models import CDUser
from django.db import transaction

def create_split_release_royalties():
    """
    For each Release, create a SplitReleaseRoyalty for the creator with 100% if not already present.
    """
    print("\n[START] Creating SplitReleaseRoyalty objects for each Release...")
    releases = Release.objects.select_related('created_by').all()
    created = 0
    skipped = 0
    errors = 0
    batch = []
    BATCH_SIZE = 1000

    for release in releases:
        user = release.created_by
        # Check if already exists
        exists = SplitReleaseRoyalty.objects.filter(user=user, release=release).exists()
        if exists:
            skipped += 1
            continue
        try:
            srr = SplitReleaseRoyalty(user=user, release=release, percentage=100.0)
            batch.append(srr)
            if len(batch) >= BATCH_SIZE:
                SplitReleaseRoyalty.objects.bulk_create(batch)
                created += len(batch)
                batch = []
        except Exception as e:
            print(f"--> Error for release '{release.title}' (user: {user.email}): {e}")
            errors += 1
    # Final batch
    if batch:
        SplitReleaseRoyalty.objects.bulk_create(batch)
        created += len(batch)

    print(f"\n--> SplitReleaseRoyalty creation summary:")
    print(f"   --> Created: {created}")
    print(f"   -->  Skipped (already exist): {skipped}")
    print(f"   --> Errors: {errors}")

def verify_split_release_royalties():
    """
    Verify that every Release has a SplitReleaseRoyalty for its creator with 100%.
    """
    print("\n--> Verifying SplitReleaseRoyalty objects...")
    releases = Release.objects.select_related('created_by').all()
    missing = 0
    wrong_percentage = 0
    for release in releases:
        user = release.created_by
        srr = SplitReleaseRoyalty.objects.filter(user=user, release=release).first()
        if not srr:
            print(f"--> Missing SplitReleaseRoyalty for release '{release.title}' (user: {user.email})")
            missing += 1
        elif srr.percentage != 100.0:
            print(f"-->  Wrong percentage for release '{release.title}' (user: {user.email}): {srr.percentage}")
            wrong_percentage += 1
    print(f"\n--> Verification summary:")
    print(f"   Missing: {missing}")
    print(f"   Wrong percentage: {wrong_percentage}")
    print(f"   Total releases checked: {releases.count()}")

if __name__ == "__main__":
    print("[START] Starting SplitReleaseRoyalty creation for all releases")
    print("=" * 80)
    try:
        create_split_release_royalties()
        verify_split_release_royalties()
        print("\n--> SplitReleaseRoyalty creation completed successfully!")
    except Exception as e:
        print(f"\n--> Migration failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1) 