import json
import pymysql
from dotenv import load_dotenv
import os
load_dotenv(override=True)

# --> Replace these with your actual DB credentials
DB_CONFIG = {
    "host": os.getenv("EC2_DB_HOST"),
    "user": os.getenv("EC2_DB_USER"),
    "password": os.getenv("EC2_DB_PASSWORD"),
    "database": "db4",
    "port": 3306
}

DROP_TABLE_SQL = """
DROP TABLE IF EXISTS db4.artist_roles;
"""
# --> Table create SQL
CREATE_TABLE_SQL = """
CREATE TABLE db4.artist_roles (
    id INT AUTO_INCREMENT PRIMARY KEY,
    primary_uuid CHAR(36) NOT NULL,
    artist_role VARCHAR(255) NOT NULL,
    artist_id INT NOT NULL,
    username VARCHAR(255) NOT NULL
);
"""

# --> Insert SQL
INSERT_SQL = """
INSERT INTO artist_roles (primary_uuid, artist_role, artist_id, username)
VALUES (%s, %s, %s, %s)
"""

conn = pymysql.connect(**DB_CONFIG, charset='utf8mb4', cursorclass=pymysql.cursors.Cursor)
cursor = conn.cursor()

cursor.execute(DROP_TABLE_SQL)
cursor.execute(CREATE_TABLE_SQL)
conn.commit()

def flatten_artist_data(table_name, primary_uuid_column, artist_column):
    conn = pymysql.connect(**DB_CONFIG, charset='utf8mb4', cursorclass=pymysql.cursors.Cursor)
    cursor = conn.cursor()

    # Step 2: Fetch rows from rl_release
    cursor.execute(f"SELECT {primary_uuid_column}, {artist_column}, lower(trim(created_by)) as created_by FROM db2.{table_name}")
    rows = cursor.fetchall()

    insert_data = []

    for primary_uuid, artist_json, created_by in rows:
        if not artist_json:
            continue

        try:
            artist_data = json.loads(artist_json)
        except json.JSONDecodeError:
            print(f"[SKIP] Invalid JSON for UUID: {primary_uuid}")
            continue

        username = created_by

        for role, artist_ids in artist_data.items():
            if isinstance(artist_ids, list):
                for artist_id in artist_ids:
                    if isinstance(artist_id, int):
                        insert_data.append((primary_uuid, role, artist_id, username))
                    else:
                        print(f"[WARN] Non-integer artist_id in UUID {primary_uuid}: {artist_id}")

    # Step 3: Insert into artist_roles
    if insert_data:
        cursor.executemany(INSERT_SQL, insert_data)
        conn.commit()
        print(f"[DONE] Inserted {cursor.rowcount} rows into artist_roles.")
    else:
        print("[INFO] No valid artist data to insert.")

    cursor.close()
    conn.close()

if __name__ == "__main__":
    flatten_artist_data("rl_release", "primary_uuid", "artist")
    flatten_artist_data("rl_tracks", "primary_track_uuid", "artist")
