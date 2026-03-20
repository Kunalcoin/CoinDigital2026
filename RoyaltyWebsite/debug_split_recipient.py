#!/usr/bin/env python3
"""
Debug script to check split_recipient calculations
Run: python3 debug_split_recipient.py ar@paisleyblvd.com
"""

import os
import sys
import django

# Setup Django
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'RoyaltyWebsite.settings')
django.setup()

from django.db import connection
from main.models import CDUser, Ratio
from releases.models import SplitReleaseRoyalty, Metadata, Track

def debug_split_recipient(email):
    email = email.lower().strip()
    print(f"\n{'='*80}")
    print(f"DEBUGGING SPLIT_RECIPIENT: {email}")
    print(f"{'='*80}\n")
    
    # 1. Check if user exists and role
    try:
        user = CDUser.objects.get(email=email)
        print(f"✓ User found: {user.email}")
        print(f"  Role: {user.role}")
        print(f"  Is split_recipient: {user.role == CDUser.ROLES.SPLIT_RECIPIENT}")
    except CDUser.DoesNotExist:
        print(f"✗ User NOT FOUND: {email}")
        return
    
    # 2. Check split records
    splits = SplitReleaseRoyalty.objects.filter(recipient_email=email)
    print(f"\n✓ Split records found: {splits.count()}")
    
    if splits.count() == 0:
        print("  ✗ NO SPLIT RECORDS FOUND - This is why net total is 0!")
        return
    
    # 3. For each split, check owner and their ratio
    print(f"\n{'='*80}")
    print("SPLIT RECORDS DETAILS:")
    print(f"{'='*80}\n")
    
    for split in splits[:10]:  # Show first 10
        print(f"Split ID: {split.id}")
        print(f"  Track: {split.track_id}")
        print(f"  Release: {split.release_id}")
        print(f"  Recipient Email: {split.recipient_email}")
        print(f"  Recipient Percentage: {split.recipient_percentage}%")
        
        # Get track ISRC
        try:
            track = Track.objects.get(id=split.track_id_id)
            isrc = track.isrc
            print(f"  Track ISRC: {isrc}")
            
            # Get metadata to find owner
            try:
                metadata = Metadata.objects.get(isrc=isrc)
                owner_email = metadata.user
                print(f"  Owner Email: {owner_email}")
                
                # Get owner's ratio
                try:
                    owner_user = CDUser.objects.get(email=owner_email)
                    active_ratio = Ratio.objects.filter(user=owner_user, status=Ratio.STATUS.ACTIVE).first()
                    if active_ratio:
                        print(f"  Owner Stores Ratio: {active_ratio.stores}%")
                        print(f"  Owner YouTube Ratio: {active_ratio.youtube}%")
                    else:
                        print(f"  ✗ Owner has NO ACTIVE RATIO!")
                        # Try any ratio
                        any_ratio = Ratio.objects.filter(user=owner_user).order_by('-id').first()
                        if any_ratio:
                            print(f"  (Found non-active ratio: stores={any_ratio.stores}%, youtube={any_ratio.youtube}%)")
                        else:
                            print(f"  ✗ Owner has NO RATIO AT ALL!")
                except CDUser.DoesNotExist:
                    print(f"  ✗ Owner user NOT FOUND: {owner_email}")
                except Exception as e:
                    print(f"  ✗ Error getting owner ratio: {e}")
                    
            except Metadata.DoesNotExist:
                print(f"  ✗ Metadata NOT FOUND for ISRC: {isrc}")
            except Exception as e:
                print(f"  ✗ Error getting metadata: {e}")
                
        except Track.DoesNotExist:
            print(f"  ✗ Track NOT FOUND: {split.track_id_id}")
        except Exception as e:
            print(f"  ✗ Error getting track: {e}")
        
        print()
    
    # 4. Check actual royalty data
    print(f"\n{'='*80}")
    print("ROYALTY DATA CHECK:")
    print(f"{'='*80}\n")
    
    # Get all ISRCs for this recipient
    recipient_isrcs = []
    for split in splits:
        try:
            track = Track.objects.get(id=split.track_id_id)
            if track.isrc:
                recipient_isrcs.append(track.isrc.upper())
        except:
            pass
    
    if recipient_isrcs:
        print(f"Found {len(recipient_isrcs)} unique ISRCs")
        print(f"Sample ISRCs: {recipient_isrcs[:5]}")
        
        # Check royalty totals for these ISRCs
        isrc_list = "', '".join(recipient_isrcs[:10])  # First 10
        query = f"""
            SELECT 
                UPPER(r.isrc) as isrc,
                m.user as owner_email,
                SUM(r.net_total_INR) as gross_total,
                COUNT(*) as record_count
            FROM releases_royalties r
            LEFT JOIN releases_metadata m ON UPPER(r.isrc) = UPPER(m.isrc)
            WHERE UPPER(r.isrc) IN ('{isrc_list}')
            GROUP BY UPPER(r.isrc), m.user
            LIMIT 20
        """
        
        with connection.cursor() as cursor:
            cursor.execute(query)
            results = cursor.fetchall()
            
            if results:
                print(f"\nRoyalty records found: {len(results)}")
                total_gross = 0
                for row in results:
                    isrc, owner_email, gross, count = row
                    print(f"  ISRC: {isrc}, Owner: {owner_email}, Gross: {gross:.2f}, Records: {count}")
                    total_gross += float(gross or 0)
                print(f"\nTotal Gross (sample): {total_gross:.2f}")
            else:
                print("✗ NO ROYALTY RECORDS FOUND for these ISRCs!")
    else:
        print("✗ Could not find ISRCs from split records")
    
    # 5. Check date range of royalty records
    print(f"\n{'='*80}")
    print("CHECKING DATE RANGE OF ROYALTY RECORDS:")
    print(f"{'='*80}\n")
    
    if recipient_isrcs:
        isrc_list = "', '".join(recipient_isrcs[:5])
        date_query = f"""
            SELECT 
                MIN(r.end_date) as min_date,
                MAX(r.end_date) as max_date,
                COUNT(*) as total_records
            FROM releases_royalties r
            WHERE UPPER(r.isrc) IN ('{isrc_list}')
        """
        
        with connection.cursor() as cursor:
            cursor.execute(date_query)
            date_result = cursor.fetchone()
            if date_result:
                min_date, max_date, total = date_result
                print(f"Date range: {min_date} to {max_date}")
                print(f"Total records: {total}")
    
    # 6. Test the actual query that's being used (WITHOUT date filter)
    print(f"\n{'='*80}")
    print("TESTING ACTUAL QUERY (NO DATE FILTER):")
    print(f"{'='*80}\n")
    
    test_query = f"""
        SELECT 
            m.track,
            UPPER(m.isrc) as isrc,
            SUM(r.units) as units,
            SUM(r.net_total_INR) as gross_total,
            SUM(
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
            ) as net_total,
            COUNT(*) as row_count
        FROM 
            releases_royalties r 
        INNER JOIN 
            releases_metadata m ON UPPER(r.isrc) = UPPER(m.isrc) 
        INNER JOIN 
            releases_track t ON UPPER(m.isrc) = UPPER(t.isrc)
        INNER JOIN 
            releases_splitreleaseroyalty sr ON t.id = sr.track_id_id 
                AND t.release_id = sr.release_id_id 
                AND LOWER(sr.recipient_email) = '{email}'
        WHERE 
            LOWER(sr.recipient_email) = '{email}'
            AND m.track IS NOT NULL
            AND r.channel != 'Youtube Official Channel'
        GROUP BY 
            m.track, UPPER(m.isrc)
        LIMIT 10
    """
    
    with connection.cursor() as cursor:
        cursor.execute(test_query)
        results = cursor.fetchall()
        
        if results:
            print(f"Query returned {len(results)} rows:")
            total_net = 0
            for row in results:
                track, isrc, units, gross, net, count = row
                print(f"  Track: {track}")
                print(f"    ISRC: {isrc}")
                print(f"    Gross: {gross:.2f}")
                print(f"    Net: {net:.2f}")
                print(f"    Units: {units}")
                print(f"    Rows: {count}")
                print()
                total_net += float(net or 0)
            print(f"Total Net (sample): {total_net:.2f}")
        else:
            print("✗ QUERY RETURNED NO ROWS!")
            print("\nThis means either:")
            print("  1. No royalty records match the split records")
            print("  2. The JOIN conditions are failing")
            print("  3. The WHERE clause is too restrictive")
    
    # 7. Test query WITH date filter (last 6 months)
    print(f"\n{'='*80}")
    print("TESTING ACTUAL QUERY (WITH 6 MONTH DATE FILTER):")
    print(f"{'='*80}\n")
    
    from datetime import date
    from dateutil.relativedelta import relativedelta
    
    right_date = date.today()
    left_date = date.today() - relativedelta(months=6)
    right_date_str = "/".join(str(right_date).split("-")[:2][::-1])
    left_date_str = "/".join(str(left_date).split("-")[:2][::-1])
    
    # Convert to SQL format
    left_date_sql = left_date_str.split("/")[1] + "-" + left_date_str.split("/")[0]
    right_date_sql = right_date_str.split("/")[1] + "-" + right_date_str.split("/")[0]
    
    date_filter = f" and LAST_DAY(end_date) >= '{left_date_sql}-01' and LAST_DAY(end_date) <= LAST_DAY('{right_date_sql}-01')"
    
    test_query_with_date = f"""
        SELECT 
            m.track,
            UPPER(m.isrc) as isrc,
            SUM(r.units) as units,
            SUM(r.net_total_INR) as gross_total,
            SUM(
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
            ) as net_total,
            COUNT(*) as row_count
        FROM 
            releases_royalties r 
        INNER JOIN 
            releases_metadata m ON UPPER(r.isrc) = UPPER(m.isrc) 
        INNER JOIN 
            releases_track t ON UPPER(m.isrc) = UPPER(t.isrc)
        INNER JOIN 
            releases_splitreleaseroyalty sr ON t.id = sr.track_id_id 
                AND t.release_id = sr.release_id_id 
                AND LOWER(sr.recipient_email) = '{email}'
        WHERE 
            LOWER(sr.recipient_email) = '{email}'
            AND m.track IS NOT NULL
            AND r.channel != 'Youtube Official Channel'
            {date_filter}
        GROUP BY 
            m.track, UPPER(m.isrc)
        LIMIT 10
    """
    
    print(f"Date filter: {date_filter}")
    print(f"Date range: {left_date_str} to {right_date_str}")
    
    with connection.cursor() as cursor:
        cursor.execute(test_query_with_date)
        results = cursor.fetchall()
        
        if results:
            print(f"Query returned {len(results)} rows:")
            total_net = 0
            for row in results:
                track, isrc, units, gross, net, count = row
                print(f"  Track: {track}")
                print(f"    ISRC: {isrc}")
                print(f"    Gross: {gross:.2f}")
                print(f"    Net: {net:.2f}")
                print(f"    Units: {units}")
                print(f"    Rows: {count}")
                print()
                total_net += float(net or 0)
            print(f"Total Net (with date filter): {total_net:.2f}")
        else:
            print("✗ QUERY RETURNED NO ROWS WITH DATE FILTER!")
            print("This means the royalty records are OUTSIDE the date range!")
    
    # 8. Check if owner ratio subquery works
    print(f"\n{'='*80}")
    print("TESTING OWNER RATIO SUBQUERY:")
    print(f"{'='*80}\n")
    
    # Get first split's owner
    if splits.exists():
        first_split = splits.first()
        try:
            track = Track.objects.get(id=first_split.track_id_id)
            metadata = Metadata.objects.get(isrc=track.isrc)
            owner_email = metadata.user
            
            ratio_query = f"""
                SELECT 
                    r2.stores,
                    r2.youtube,
                    r2.status,
                    u2.email
                FROM main_ratio r2 
                JOIN main_cduser u2 ON r2.user_id = u2.id 
                WHERE LOWER(u2.email) = LOWER('{owner_email}') 
                AND r2.status = 'active' 
                LIMIT 1
            """
            
            with connection.cursor() as cursor:
                cursor.execute(ratio_query)
                ratio_result = cursor.fetchone()
                
                if ratio_result:
                    stores, youtube, status, email = ratio_result
                    print(f"✓ Owner ratio found for {email}:")
                    print(f"  Stores: {stores}%")
                    print(f"  YouTube: {youtube}%")
                    print(f"  Status: {status}")
                else:
                    print(f"✗ NO ACTIVE RATIO FOUND for owner: {owner_email}")
                    # Try without status filter
                    ratio_query2 = f"""
                        SELECT 
                            r2.stores,
                            r2.youtube,
                            r2.status,
                            u2.email
                        FROM main_ratio r2 
                        JOIN main_cduser u2 ON r2.user_id = u2.id 
                        WHERE LOWER(u2.email) = LOWER('{owner_email}')
                        ORDER BY r2.id DESC
                        LIMIT 1
                    """
                    cursor.execute(ratio_query2)
                    ratio_result2 = cursor.fetchone()
                    if ratio_result2:
                        stores, youtube, status, email = ratio_result2
                        print(f"  (Found non-active ratio: stores={stores}%, youtube={youtube}%, status={status})")
                    else:
                        print(f"  ✗ NO RATIO AT ALL for owner: {owner_email}")
        except Exception as e:
            print(f"✗ Error testing owner ratio: {e}")
    
    print(f"\n{'='*80}\n")

if __name__ == '__main__':
    if len(sys.argv) > 1:
        email = sys.argv[1]
    else:
        email = 'ar@paisleyblvd.com'
    
    debug_split_recipient(email)
