#!/usr/bin/env python
"""
Verify due balance for mgmt@jaytrak.com (or any username) against the formula:

  Formula:
  - Gross = royalty amount (releases_royalties.net_total_INR)
  - Post-admin remainder = Gross × (owner_ratio / 100)   [owner's ratio from main_ratio]
  - Split recipient amount = Remainder × (recipient_percentage / 100)
  - Due balance = SUM(split recipient amounts) - payments (amount_paid + tds)

Run from project root: python manage.py shell < RoyaltyWebsite/check_due_balance_mgmt.py
Or: cd RoyaltyWebsite && python -c "
import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'RoyaltyWebsite.settings')
django.setup()
exec(open('check_due_balance_mgmt.py').read())
"
"""
import os
import sys
import django

# Allow running from RoyaltyWebsite or project root
if __name__ == "__main__" or "DJANGO_SETTINGS_MODULE" not in os.environ:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "RoyaltyWebsite.settings")
    django.setup()

from django.db import connection

USERNAME = "mgmt@jaytrak.com"


def run_verification(username):
    with connection.cursor() as cursor:
        # 1) Role and stored due amount
        cursor.execute(
            """
            SELECT u.email, u.role,
                   (SELECT r.stores FROM main_ratio r WHERE r.user_id = u.id AND r.status = 'active' LIMIT 1) AS user_stores,
                   (SELECT r.youtube FROM main_ratio r WHERE r.user_id = u.id AND r.status = 'active' LIMIT 1) AS user_youtube,
                   d.amount AS stored_due_amount
            FROM main_cduser u
            LEFT JOIN main_dueamount d ON d.user_id = u.id
            WHERE LOWER(u.email) = LOWER(%s)
            """,
            [username],
        )
        row = cursor.fetchone()
        if not row:
            print(f"User not found: {username}")
            return
        email, role, user_stores, user_youtube, stored_due = row
        print(f"User: {email}")
        print(f"Role: {role}")
        print(f"User ratio (stores, youtube): {user_stores}, {user_youtube}")
        print(f"Stored due amount (main_dueamount): {stored_due}")
        print()

        # 2) Breakdown by formula: for each (isrc, channel_type) where user is recipient
        #    gross, owner_email, owner_ratio (stores or youtube), recipient_percentage,
        #    remainder = gross * owner_ratio/100, split_amount = remainder * recipient_percentage/100
        cursor.execute(
            """
            WITH recipient_royalty_totals AS (
                SELECT 
                    UPPER(r.isrc) AS isrc,
                    CASE WHEN r.channel LIKE 'Youtube Official Channel' THEN 'youtube' ELSE 'stores' END AS channel_type,
                    SUM(r.net_total_INR) AS gross
                FROM releases_royalties r
                JOIN releases_metadata m ON UPPER(r.isrc) = UPPER(m.isrc)
                JOIN releases_track t ON UPPER(r.isrc) = UPPER(t.isrc)
                JOIN releases_splitreleaseroyalty sr ON t.id = sr.track_id_id AND t.release_id = sr.release_id_id AND LOWER(sr.recipient_email) = %s
                WHERE LOWER(m.user) != %s
                GROUP BY UPPER(r.isrc), CASE WHEN r.channel LIKE 'Youtube Official Channel' THEN 'youtube' ELSE 'stores' END
            ),
            recipient_split AS (
                SELECT DISTINCT UPPER(t.isrc) AS isrc, sr.recipient_percentage, LOWER(m.user) AS owner_email
                FROM releases_track t
                JOIN releases_metadata m ON UPPER(t.isrc) = UPPER(m.isrc)
                JOIN releases_splitreleaseroyalty sr ON t.id = sr.track_id_id AND t.release_id = sr.release_id_id AND LOWER(sr.recipient_email) = %s
                WHERE LOWER(m.user) != %s
            ),
            owner_ratios AS (
                SELECT LOWER(u.email) AS owner_email, COALESCE(r.stores, 0) AS stores_ratio, COALESCE(r.youtube, 0) AS youtube_ratio
                FROM main_cduser u
                LEFT JOIN main_ratio r ON u.id = r.user_id AND r.status = 'active'
            )
            SELECT 
                rrt.isrc,
                rrt.channel_type,
                rrt.gross,
                rsp.owner_email,
                rsp.recipient_percentage,
                CASE WHEN rrt.channel_type = 'youtube' THEN COALESCE(orr.youtube_ratio, 0) ELSE COALESCE(orr.stores_ratio, 0) END AS owner_ratio_pct,
                rrt.gross * (CASE WHEN rrt.channel_type = 'youtube' THEN COALESCE(orr.youtube_ratio, 0) ELSE COALESCE(orr.stores_ratio, 0) END / 100) AS remainder,
                rrt.gross * (CASE WHEN rrt.channel_type = 'youtube' THEN COALESCE(orr.youtube_ratio, 0) ELSE COALESCE(orr.stores_ratio, 0) END / 100) * rsp.recipient_percentage / 100 AS split_amount
            FROM recipient_royalty_totals rrt
            JOIN recipient_split rsp ON rrt.isrc = rsp.isrc
            LEFT JOIN owner_ratios orr ON rsp.owner_email = orr.owner_email
            ORDER BY rrt.isrc, rrt.channel_type
            """,
            [username, username, username, username],
        )
        rows = cursor.fetchall()
        cols = [c[0] for c in cursor.description]

    print("Formula breakdown (per ISRC × channel_type):")
    print("  remainder = gross × (owner_ratio/100);  split_amount = remainder × (recipient_percentage/100)")
    print()
    total_net = 0
    for r in rows:
        d = dict(zip(cols, r))
        total_net += float(d["split_amount"] or 0)
        print(f"  isrc={d['isrc']} channel={d['channel_type']} gross={d['gross']:.2f} owner={d['owner_email']} owner_ratio%={d['owner_ratio_pct']} recipient%={d['recipient_percentage']} remainder={d['remainder']:.2f} split_amount={d['split_amount']:.2f}")

    print()
    print(f"Sum of split amounts (net total before payments): {total_net:.2f}")

    # 3) Payments
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT COALESCE(SUM(amount_paid), 0), COALESCE(SUM(tds), 0) FROM main_payment WHERE LOWER(username) = LOWER(%s)",
            [username],
        )
        row = cursor.fetchone()
    amount_paid = float(row[0] or 0)
    tds = float(row[1] or 0)
    print(f"Payments (amount_paid + tds): {amount_paid:.2f} + {tds:.2f} = {amount_paid + tds:.2f}")

    computed_due = round(total_net - amount_paid - tds, 2)
    print(f"Computed due balance (formula): {computed_due}")
    print()
    print(f"Stored due amount:              {stored_due}")
    if stored_due is not None and abs(float(stored_due) - computed_due) > 0.01:
        print("  -> MISMATCH: stored value does not match formula.")
    else:
        print("  -> OK: matches formula.")


def refresh_and_verify(username):
    """Update stored due balance from formula, then verify."""
    from main.processor import processor
    print(f"Refreshing due balance for {username}...")
    new_amount = processor.refresh_due_balance(username)
    print(f"Stored due amount updated to: {new_amount}")
    print()
    run_verification(username)


if __name__ == "__main__":
    run_verification(USERNAME)
