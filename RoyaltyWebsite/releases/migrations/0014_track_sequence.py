# Generated migration: add Track.sequence for drag-and-drop ordering

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("releases", "0013_add_audiomack_id_to_artist"),
    ]

    operations = [
        migrations.AddField(
            model_name="track",
            name="sequence",
            field=models.PositiveIntegerField(
                default=0,
                help_text="Order of track in release (1-based). 0 = legacy, use id order.",
                verbose_name="Display order",
            ),
        ),
    ]
