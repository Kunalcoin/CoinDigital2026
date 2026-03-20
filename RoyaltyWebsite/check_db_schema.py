#!/usr/bin/env python
"""
Compare EC2 db4 schema with Django's expected schema.
Run with SERVER=EC2 to connect to EC2 db4.
From django-docker-compose: mv .env.run_local .env.run_local.bak; source coin.env; cd RoyaltyWebsite; python3 check_db_schema.py
"""
import os
import sys

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "RoyaltyWebsite.settings")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import django
django.setup()

from django.db import connection
from django.apps import apps

def get_expected_tables():
    """Get all tables Django expects from models."""
    tables = set()
    for model in apps.get_models():
        if model._meta.managed:
            tables.add(model._meta.db_table)
    return sorted(tables)

def get_expected_columns(table_name):
    """Get expected columns for a table from Django model."""
    for model in apps.get_models():
        if model._meta.db_table == table_name:
            cols = []
            for f in model._meta.get_fields():
                if hasattr(f, 'column') and f.column and not getattr(f, 'many_to_many', False):
                    cols.append(f.column)
            return cols
    return []

def get_db_tables(cursor):
    """Get all tables in the database."""
    cursor.execute("SHOW TABLES")
    return sorted([row[0] for row in cursor.fetchall()])

def get_db_columns(cursor, table_name):
    """Get all columns in a table."""
    cursor.execute(f"DESCRIBE `{table_name}`")
    return [row[0] for row in cursor.fetchall()]

def main():
    print("=" * 60)
    print("DB Schema Comparison: EC2 db4 vs Django Expected")
    print("=" * 60)

    expected_tables = get_expected_tables()
    print(f"\nDjango expects {len(expected_tables)} tables:")
    for t in expected_tables:
        print(f"  - {t}")

    with connection.cursor() as cursor:
        db_tables = get_db_tables(cursor)
        print(f"\nEC2 db4 has {len(db_tables)} tables:")
        for t in db_tables:
            print(f"  - {t}")

        # Compare
        expected_set = set(expected_tables)
        db_set = set(db_tables)

        missing_tables = expected_set - db_set
        extra_tables = db_set - expected_set

        print("\n" + "=" * 60)
        print("COMPARISON RESULTS")
        print("=" * 60)

        if missing_tables:
            print(f"\nMISSING TABLES (in Django but NOT in EC2 db4): {len(missing_tables)}")
            for t in sorted(missing_tables):
                print(f"  - {t}")
        else:
            print("\nAll expected tables exist in EC2 db4.")

        if extra_tables:
            print(f"\nEXTRA TABLES (in EC2 db4 but not in Django): {len(extra_tables)}")
            for t in sorted(extra_tables):
                print(f"  - {t}")

        # Column comparison for each expected table
        print("\n" + "=" * 60)
        print("COLUMN COMPARISON (expected tables)")
        print("=" * 60)

        column_issues = []
        for table in expected_tables:
            if table not in db_set:
                continue
            expected_cols = set(get_expected_columns(table))
            db_cols = set(get_db_columns(cursor, table))
            missing_cols = expected_cols - db_cols
            extra_cols = db_cols - expected_cols
            if missing_cols or extra_cols:
                column_issues.append((table, missing_cols, extra_cols))

        if column_issues:
            for table, missing, extra in column_issues:
                print(f"\n{table}:")
                if missing:
                    print(f"  MISSING columns: {sorted(missing)}")
                if extra:
                    print(f"  EXTRA columns (in DB, not in Django): {sorted(extra)}")
        else:
            print("\nAll expected columns match for tables that exist.")

    print("\nDone.")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        import traceback
        print(f"Error: {e}")
        traceback.print_exc()
        sys.exit(1)
