#!/usr/bin/env python3
"""
Test script to verify split_recipient query execution
Run on EC2: python3 test_split_query.py ar@paisleyblvd.com
"""

import os
import sys
import django

# Setup Django
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'RoyaltyWebsite.settings')
django.setup()

from django.db import connection
from main.models import CDUser

def test_query(email):
    email = email.lower().strip()
    print(f"\n{'='*80}")
    print(f"TESTING QUERY FOR: {email}")
    print(f"{'='*80}\n")
    
    # Check user
    try:
        user = CDUser.objects.get(email=email)
        print(f"User: {user.email}, Role: {user.role}")
        is_split_recipient = (user.role == CDUser.ROLES.SPLIT_RECIPIENT)
        print(f"Is split_recipient: {is_split_recipient}")
    except CDUser.DoesNotExist:
        print(f"User NOT FOUND!")
        return
    
    # Build the actual query that should be executed
    username = email
    split_join_type = 'INNER' if is_split_recipient else 'LEFT'
    metadata_join_type = 'INNER' if is_split_recipient else 'LEFT'
    track_join_type = 'INNER' if is_split_recipient else 'LEFT'
    split_where_clause = f"LOWER(sr.recipient_email) = '{username}'" if is_split_recipient else f"(LOWER(m.user) = '{username}' OR LOWER(sr.recipient_email) = '{username}')"
    
    # Test query (simplified version of top_tracks_query)
    test_query = f"""
        SELECT 
            m.track,
            UPPER(m.isrc) as isrc,
            sum(r.units) as units,
            sum(r.net_total_INR) as gross_total,
            sum(
                CASE 
                    WHEN sr.recipient_email IS NOT NULL THEN 
                        r.net_total_INR * (
                            COALESCE(
                                (SELECT r2.stores FROM main_ratio r2 
                                 JOIN main_cduser u2 ON r2.user_id = u2.id 
                                 WHERE LOWER(u2.email) = LOWER(m.user) AND r2.status = 'active' LIMIT 1),
                                0
                            ) / 100
                        ) * (sr.recipient_percentage / 100)
                    ELSE 0
                END
            ) as net_total
        FROM 
            releases_royalties r 
        {metadata_join_type} JOIN 
            releases_metadata m ON UPPER(r.isrc) = UPPER(m.isrc) 
        {track_join_type} JOIN 
            releases_track t ON UPPER(m.isrc) = UPPER(t.isrc)
        {split_join_type} JOIN 
            releases_splitreleaseroyalty sr ON t.id = sr.track_id_id 
                AND t.release_id = sr.release_id_id 
                AND LOWER(sr.recipient_email) = '{username}'
        WHERE 
            {split_where_clause}
            AND m.user IS NOT NULL
            AND m.track IS NOT NULL
            AND r.channel != 'Youtube Official Channel'
        GROUP BY 
            m.track, UPPER(m.isrc)
        LIMIT 5
    """
    
    print("EXECUTING QUERY:")
    print("="*80)
    print(test_query)
    print("="*80)
    print()
    
    with connection.cursor() as cursor:
        cursor.execute(test_query)
        results = cursor.fetchall()
        
        if results:
            print(f"✓ Query returned {len(results)} rows:")
            total_net = 0
            for row in results:
                track, isrc, units, gross, net = row
                print(f"  Track: {track}")
                print(f"    ISRC: {isrc}")
                print(f"    Gross: {gross:.2f}")
                print(f"    Net: {net:.2f}")
                print(f"    Units: {units}")
                print()
                total_net += float(net or 0)
            print(f"Total Net: {total_net:.2f}")
        else:
            print("✗ Query returned NO ROWS!")
            print("\nDebugging why...")
            
            # Check if split records exist
            check_splits = f"""
                SELECT COUNT(*) as count
                FROM releases_splitreleaseroyalty sr
                WHERE LOWER(sr.recipient_email) = '{username}'
            """
            cursor.execute(check_splits)
            split_count = cursor.fetchone()[0]
            print(f"  Split records for {username}: {split_count}")
            
            # Check if royalty records exist for those tracks
            if split_count > 0:
                check_royalties = f"""
                    SELECT COUNT(*) as count
                    FROM releases_royalties r
                    INNER JOIN releases_metadata m ON UPPER(r.isrc) = UPPER(m.isrc)
                    INNER JOIN releases_track t ON UPPER(m.isrc) = UPPER(t.isrc)
                    INNER JOIN releases_splitreleaseroyalty sr ON t.id = sr.track_id_id 
                        AND t.release_id = sr.release_id_id 
                        AND LOWER(sr.recipient_email) = '{username}'
                    WHERE r.channel != 'Youtube Official Channel'
                """
                cursor.execute(check_royalties)
                royalty_count = cursor.fetchone()[0]
                print(f"  Royalty records matching splits: {royalty_count}")
    
    print(f"\n{'='*80}\n")

if __name__ == '__main__':
    if len(sys.argv) > 1:
        email = sys.argv[1]
    else:
        email = 'ar@paisleyblvd.com'
    
    test_query(email)
