# Fix MySQL 1364: Field 'apple_music_instant_grat' doesn't have a default value
# when INSERT omits the column (e.g. Track.objects.create(...)).
# Safe no-op on non-MySQL databases.

from django.db import migrations


def fix_mysql_default(apps, schema_editor):
    conn = schema_editor.connection
    if conn.vendor != "mysql":
        return
    with conn.cursor() as cursor:
        cursor.execute(
            """
            ALTER TABLE releases_track
            MODIFY COLUMN apple_music_instant_grat tinyint(1) NOT NULL DEFAULT 0;
            """
        )


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("releases", "0022_alter_track_apple_music_instant_grat_help"),
    ]

    operations = [
        migrations.RunPython(fix_mysql_default, noop_reverse),
    ]
