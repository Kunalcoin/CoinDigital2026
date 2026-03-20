# Fix MySQL 1364: Field 'apple_music_commercial_model' doesn't have a default value
# when INSERT omits the column (e.g. Release.objects.create(title=..., created_by=...)).
# Safe no-op on non-MySQL databases.

from django.db import migrations


def fix_mysql_default(apps, schema_editor):
    conn = schema_editor.connection
    if conn.vendor != "mysql":
        return
    with conn.cursor() as cursor:
        cursor.execute(
            """
            UPDATE releases_release
            SET apple_music_commercial_model = 'both'
            WHERE apple_music_commercial_model IS NULL OR apple_music_commercial_model = '';
            """
        )
        cursor.execute(
            """
            ALTER TABLE releases_release
            MODIFY COLUMN apple_music_commercial_model VARCHAR(20) NOT NULL DEFAULT 'both';
            """
        )


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("releases", "0020_track_apple_music_instant_grat"),
    ]

    operations = [
        migrations.RunPython(fix_mysql_default, noop_reverse),
    ]
