#!/usr/bin/env python
"""
Fix payment email issues in main_payment table:
1. Fix panjaabrecordss@gmailcom -> panjaabrecordss@gmail.com
2. Find all @gmail.com misspellings
3. Find emails with leading/trailing spaces
"""
import os
import sys
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "RoyaltyWebsite.settings")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
django.setup()

from django.db import connection

def main():
    with connection.cursor() as cursor:
        # 1. Fix panjaabrecordss@gmailcom -> panjaabrecordss@gmail.com
        cursor.execute("""
            UPDATE main_payment 
            SET username = 'panjaabrecordss@gmail.com' 
            WHERE LOWER(TRIM(username)) = 'panjaabrecordss@gmailcom'
        """)
        fixed1 = cursor.rowcount
        print(f"FIXED: panjaabrecordss@gmailcom -> panjaabrecordss@gmail.com: {fixed1} row(s)")

        # 2. Find @gmail.com misspellings (contains gmail but doesn't end with @gmail.com)
        cursor.execute("""
            SELECT username, COUNT(*) as cnt 
            FROM main_payment 
            WHERE LOWER(username) LIKE '%gmail%' 
              AND LOWER(username) NOT LIKE '%@gmail.com'
            GROUP BY username
            ORDER BY cnt DESC
        """)
        gmail_misspellings = cursor.fetchall()
        print(f"\n--- @gmail.com MISSPELLINGS (payments not charged in dashboard) ---")
        for row in gmail_misspellings:
            print(f"  '{row[0]}' - {row[1]} payment(s)")

        # 3. Find emails with leading or trailing spaces
        cursor.execute("""
            SELECT username, COUNT(*) as cnt 
            FROM main_payment 
            WHERE username != TRIM(username)
            GROUP BY username
            ORDER BY cnt DESC
        """)
        space_issues = cursor.fetchall()
        print(f"\n--- SPACES BEFORE/AFTER EMAIL (payments not charged in dashboard) ---")
        for row in space_issues:
            print(f"  '{row[0]}' (repr: {repr(row[0])}) - {row[1]} payment(s)")

        # 4. Fix @gmail.cm -> @gmail.com
        cursor.execute("""
            UPDATE main_payment 
            SET username = REPLACE(username, '@gmail.cm', '@gmail.com')
            WHERE username LIKE '%@gmail.cm'
        """)
        gmail_cm_fix = cursor.rowcount
        print(f"\nFIXED: @gmail.cm -> @gmail.com: {gmail_cm_fix} row(s)")

        # 5. Fix leading/trailing spaces and tabs (CHAR(9)=tab, CHAR(10)=LF, CHAR(13)=CR)
        cursor.execute("""
            UPDATE main_payment 
            SET username = TRIM(REPLACE(REPLACE(REPLACE(username, CHAR(9), ''), CHAR(10), ''), CHAR(13), ''))
            WHERE username REGEXP '[[:space:]]' OR username != TRIM(username)
        """)
        trim_count = cursor.rowcount
        print(f"FIXED: Trimmed spaces/tabs: {trim_count} row(s)")

        # 6. Fix other common gmailcom -> gmail.com (missing dot)
        cursor.execute("""
            SELECT DISTINCT username FROM main_payment 
            WHERE LOWER(TRIM(username)) LIKE '%@gmailcom'
        """)
        more_gmailcom = cursor.fetchall()
        print(f"\n--- OTHER @gmailcom (missing dot) INSTANCES ---")
        for row in more_gmailcom:
            print(f"  '{row[0]}'")
            fixed = row[0].replace('@gmailcom', '@gmail.com').replace('@GMAILCOM', '@gmail.com')
            cursor.execute(
                "UPDATE main_payment SET username = %s WHERE username = %s",
                [fixed, row[0]]
            )
            print(f"    -> Fixed to '{fixed}' ({cursor.rowcount} rows)")

    print("\nDone.")

if __name__ == "__main__":
    print("Connecting to db4 and fixing payment emails...\n")
    main()
