# Generated manually — Dolby Atmos asset fields for Merlin Bridge / Apple Music.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("releases", "0024_add_distribution_job_history"),
    ]

    operations = [
        migrations.AddField(
            model_name="track",
            name="apple_music_dolby_atmos_url",
            field=models.CharField(
                blank=True,
                default="",
                help_text="S3 or HTTPS URL to the Dolby Atmos master (BWF with ADM). Only used when the release "
                "owner has Apple Music Dolby Atmos enabled. Package filename: {UPC}_01_{NNN}_atmos.wav.",
                max_length=1024,
                verbose_name="Apple Music Dolby Atmos (BWF ADM .wav) URL",
            ),
        ),
        migrations.AddField(
            model_name="track",
            name="apple_music_dolby_atmos_isrc",
            field=models.CharField(
                blank=True,
                default="",
                help_text="Required for Atmos delivery: distinct ISRC for the immersive mix (no dashes in XML). "
                "Apple: external_identifier.isrc on the object-based audio data_file.",
                max_length=255,
                verbose_name="Apple Music Dolby Atmos ISRC (secondary)",
            ),
        ),
    ]
