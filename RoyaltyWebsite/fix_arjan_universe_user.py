#!/usr/bin/env python3
"""
Move track "ArjanUniverse" from user officialrnait@gmail.com to browncollabcoindigital@gmail.com
in releases_metadata (so royalties show under the correct user).

Run with SERVER=EC2 to use db4.
"""
import os
import sys
import django

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "RoyaltyWebsite.settings")
django.setup()

from django.db import connection

TRACK_NAME = "ArjanUniverse"  # exact or use LIKE for variants
FROM_USER = "officialrnait@gmail.com"
TO_USER = "browncollabcoindigital@gmail.com"


def run():
    with connection.cursor() as cursor:
        # Find rows: track matches ArjanUniverse and user is officialrnait
        cursor.execute(
            """
            SELECT isrc, user, track, `release`, label_name
            FROM releases_metadata
            WHERE LOWER(TRIM(user)) = LOWER(TRIM(%s))
              AND (TRIM(track) = %s OR REPLACE(track, ' ', '') = %s OR track LIKE %s)
            """,
            [FROM_USER, TRACK_NAME, TRACK_NAME.replace(" ", ""), "%" + TRACK_NAME + "%"],
        )
        rows = cursor.fetchall()
        cols = ["isrc", "user", "track", "release", "label_name"]

    if not rows:
        print("No rows found for user", FROM_USER, "with track matching", TRACK_NAME)
        return

    print("Found", len(rows), "row(s) to update:")
    for r in rows:
        print(" ", dict(zip(cols, r)))

    with connection.cursor() as cursor:
        cursor.execute(
            """
            UPDATE releases_metadata
            SET user = %s
            WHERE LOWER(TRIM(user)) = LOWER(TRIM(%s))
              AND (TRIM(track) = %s OR REPLACE(track, ' ', '') = %s OR track LIKE %s)
            """,
            [TO_USER, FROM_USER, TRACK_NAME, TRACK_NAME.replace(" ", ""), "%" + TRACK_NAME + "%"],
        )
        n = cursor.rowcount
    print("Updated", n, "row(s): user set to", TO_USER)
    print("ArjanUniverse should now appear under", TO_USER, "in royalties.")


if __name__ == "__main__":
    run()
