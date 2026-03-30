#!/usr/bin/env python3
"""
Find all releases_metadata rows where track, release, or label_name
contain the b'...' prefix and fix them by removing the b' prefix.

Run with SERVER=EC2 to use db4.
  --export   Write CSV of all isrc + current/correct track names (for restore).
  --update   Strip b' prefix (use position 3, not 4, to keep first letter).
  --recover  Restore track/release from releases_track where isrc matches.
"""
import os
import sys
import csv
import time
import django

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "RoyaltyWebsite.settings")
django.setup()

from django.db import connection


def clean_b_prefix(val):
    if val is None:
        return None
    s = str(val).strip()
    if not s:
        return s
    if s.startswith("b'") and s.endswith("'"):
        return s[2:-1].replace("\\'", "'")
    if s.startswith('b"') and s.endswith('"'):
        return s[2:-1].replace('\\"', '"')
    return s


def run_list():
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT isrc, user, track, `release`, label_name
            FROM releases_metadata
            WHERE track LIKE "b'%%" OR track LIKE 'b"%%'
               OR `release` LIKE "b'%%" OR `release` LIKE 'b"%%'
               OR (label_name IS NOT NULL AND (label_name LIKE "b'%%" OR label_name LIKE 'b"%%'))
               OR (display_artist IS NOT NULL AND (display_artist LIKE "b'%%" OR display_artist LIKE 'b"%%'))
            ORDER BY user, track
            """
        )
        rows = cursor.fetchall()
    cols = ["isrc", "user", "track", "release", "label_name"]
    print("Rows with b' prefix:")
    print("=" * 80)
    if not rows:
        print("  None found.")
        return []
    for r in rows:
        print(dict(zip(cols, r)))
    print("Total:", len(rows))
    return rows


def run_export():
    """Export all releases_metadata with current track/release + correct names from releases_track."""
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT
              m.isrc,
              m.user,
              m.track AS current_track,
              m.`release` AS current_release,
              m.label_name AS current_label_name,
              t.title AS correct_track,
              r.title AS correct_release
            FROM releases_metadata m
            LEFT JOIN releases_track t ON UPPER(TRIM(t.isrc)) = UPPER(TRIM(m.isrc))
            LEFT JOIN releases_release r ON t.release_id = r.id
            ORDER BY m.user, m.isrc
            """
        )
        rows = cursor.fetchall()
        cols = [c[0] for c in cursor.description]

    out_path = os.path.join(os.path.dirname(__file__), "metadata_track_list_export.csv")
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(cols)
        for r in rows:
            w.writerow([str(x) if x is not None else "" for x in r])
    print("Exported", len(rows), "rows to:", out_path)
    print("Columns: isrc, user, current_track, current_release, current_label_name, correct_track, correct_release")


def run_update():
    """Strip b' prefix using SUBSTRING(col, 3, L-3) so first letter is kept."""
    with connection.cursor() as cursor:
        cursor.execute(
            """
            UPDATE releases_metadata
            SET
              track = CASE
                WHEN track LIKE "b'%%" AND track LIKE "%%'" THEN SUBSTRING(track, 3, CHAR_LENGTH(track) - 3)
                WHEN track LIKE 'b"%%' AND track LIKE '%%"' THEN SUBSTRING(track, 3, CHAR_LENGTH(track) - 3)
                ELSE track
              END,
              `release` = CASE
                WHEN `release` LIKE "b'%%" AND `release` LIKE "%%'" THEN SUBSTRING(`release`, 3, CHAR_LENGTH(`release`) - 3)
                WHEN `release` LIKE 'b"%%' AND `release` LIKE '%%"' THEN SUBSTRING(`release`, 3, CHAR_LENGTH(`release`) - 3)
                ELSE `release`
              END,
              label_name = CASE
                WHEN label_name LIKE "b'%%" AND label_name LIKE "%%'" THEN SUBSTRING(label_name, 3, CHAR_LENGTH(label_name) - 3)
                WHEN label_name LIKE 'b"%%' AND label_name LIKE '%%"' THEN SUBSTRING(label_name, 3, CHAR_LENGTH(label_name) - 3)
                ELSE label_name
              END,
              display_artist = CASE
                WHEN display_artist LIKE "b'%%" AND display_artist LIKE "%%'" THEN SUBSTRING(display_artist, 3, CHAR_LENGTH(display_artist) - 3)
                WHEN display_artist LIKE 'b"%%' AND display_artist LIKE '%%"' THEN SUBSTRING(display_artist, 3, CHAR_LENGTH(display_artist) - 3)
                ELSE display_artist
              END
            WHERE track LIKE "b'%%" OR track LIKE 'b"%%'
               OR `release` LIKE "b'%%" OR `release` LIKE 'b"%%'
               OR (label_name IS NOT NULL AND (label_name LIKE "b'%%" OR label_name LIKE 'b"%%'))
               OR (display_artist IS NOT NULL AND (display_artist LIKE "b'%%" OR display_artist LIKE 'b"%%'))
            """
        )
        updated = cursor.rowcount
    print("Updated", updated, "row(s) in releases_metadata.")


BATCH_SIZE = 200   # Small batches to avoid lock wait timeout (try 300 if 200 is slow)
BATCH_DELAY = 0.4  # Seconds to wait between batches to reduce lock contention


def run_recover():
    """Restore track, release, label_name, display_artist, track_display_artist from releases tables where isrc matches. Uses batches to avoid lock timeout."""
    with connection.cursor() as cursor:
        # Increase lock wait timeout for this session (seconds)
        try:
            cursor.execute("SET SESSION innodb_lock_wait_timeout = 300")
        except Exception:
            pass

        # Get all isrcs that have a matching track (so we only update those)
        cursor.execute(
            """
            SELECT DISTINCT UPPER(TRIM(m.isrc))
            FROM releases_metadata m
            INNER JOIN releases_track t ON UPPER(TRIM(t.isrc)) = UPPER(TRIM(m.isrc))
            """
        )
        isrcs = [row[0] for row in cursor.fetchall()]
    if not isrcs:
        print("No metadata rows with matching releases_track found.")
        return

    total = len(isrcs)
    print("Found", total, "ISRCs to recover. Processing in batches of", BATCH_SIZE, "...")

    n1 = n2 = n3 = n4 = 0
    for start in range(0, total, BATCH_SIZE):
        batch = isrcs[start : start + BATCH_SIZE]
        placeholders = ",".join(["%s"] * len(batch))
        with connection.cursor() as cursor:
            # 1) track + release
            cursor.execute(
                """
                UPDATE releases_metadata m
                INNER JOIN releases_track t ON UPPER(TRIM(t.isrc)) = UPPER(TRIM(m.isrc))
                INNER JOIN releases_release r ON t.release_id = r.id
                SET m.track = t.title, m.`release` = r.title
                WHERE UPPER(TRIM(m.isrc)) IN (""" + placeholders + ")",
                batch,
            )
            n1 += cursor.rowcount

            # 2) label_name
            cursor.execute(
                """
                UPDATE releases_metadata m
                INNER JOIN releases_track t ON UPPER(TRIM(t.isrc)) = UPPER(TRIM(m.isrc))
                INNER JOIN releases_release r ON t.release_id = r.id
                INNER JOIN releases_label l ON r.label_id = l.id
                SET m.label_name = l.label
                WHERE UPPER(TRIM(m.isrc)) IN (""" + placeholders + ")",
                batch,
            )
            n2 += cursor.rowcount

            # 3) track_display_artist
            cursor.execute(
                """
                UPDATE releases_metadata m
                INNER JOIN releases_track t ON UPPER(TRIM(t.isrc)) = UPPER(TRIM(m.isrc))
                INNER JOIN (
                  SELECT track_id, MIN(artist_id) AS artist_id
                  FROM releases_relatedartists
                  WHERE relation_key = 'track' AND track_id IS NOT NULL
                  GROUP BY track_id
                ) ra ON ra.track_id = t.id
                INNER JOIN releases_artist a ON ra.artist_id = a.id
                SET m.track_display_artist = a.name
                WHERE UPPER(TRIM(m.isrc)) IN (""" + placeholders + ")",
                batch,
            )
            n3 += cursor.rowcount

            # 4) display_artist
            cursor.execute(
                """
                UPDATE releases_metadata m
                INNER JOIN releases_track t ON UPPER(TRIM(t.isrc)) = UPPER(TRIM(m.isrc))
                INNER JOIN releases_release r ON t.release_id = r.id
                INNER JOIN (
                  SELECT release_id, MIN(artist_id) AS artist_id
                  FROM releases_relatedartists
                  WHERE relation_key = 'release' AND release_id IS NOT NULL
                  GROUP BY release_id
                ) ra ON ra.release_id = r.id
                INNER JOIN releases_artist a ON ra.artist_id = a.id
                SET m.display_artist = a.name
                WHERE UPPER(TRIM(m.isrc)) IN (""" + placeholders + ")",
                batch,
            )
            n4 += cursor.rowcount

        print("  Batch", (start // BATCH_SIZE) + 1, ":", start + len(batch), "/", total)
        if BATCH_DELAY and start + BATCH_SIZE < total:
            time.sleep(BATCH_DELAY)

    print("Recovered track/release for", n1, "row(s).")
    print("Recovered label_name for", n2, "row(s).")
    print("Recovered track_display_artist for", n3, "row(s).")
    print("Recovered display_artist for", n4, "row(s).")


if __name__ == "__main__":
    if "--export" in sys.argv:
        print("Exporting all ISRCs and track names...")
        run_export()
    elif "--recover" in sys.argv:
        print("Recovering from releases_track...")
        run_recover()
    elif "--update" in sys.argv:
        print("Removing b' prefix...")
        run_update()
    else:
        run_list()
        print()
        print("Options: --export  --update  --recover")
