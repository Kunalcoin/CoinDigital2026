# Generated manually for distribution job cancellation

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("releases", "0025_track_apple_music_dolby_atmos"),
    ]

    operations = [
        migrations.AddField(
            model_name="distributionjob",
            name="cancel_requested",
            field=models.BooleanField(
                default=False,
                help_text="Set by admin cancel; worker aborts between stores / during large S3 reads.",
            ),
        ),
    ]
