# Generated migration: WAV/MP3/FLAC URLs and upload timestamp

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("releases", "0014_track_sequence"),
    ]

    operations = [
        migrations.AddField(
            model_name="track",
            name="audio_wav_url",
            field=models.CharField(blank=True, default="", max_length=1024),
        ),
        migrations.AddField(
            model_name="track",
            name="audio_mp3_url",
            field=models.CharField(blank=True, default="", max_length=1024),
        ),
        migrations.AddField(
            model_name="track",
            name="audio_flac_url",
            field=models.CharField(blank=True, default="", max_length=1024),
        ),
        migrations.AddField(
            model_name="track",
            name="audio_uploaded_at",
            field=models.DateTimeField(
                blank=True,
                help_text="When the WAV was uploaded (stored UTC; display in IST).",
                null=True,
                verbose_name="Audio uploaded at (UTC)",
            ),
        ),
        migrations.AlterField(
            model_name="track",
            name="audio_track_url",
            field=models.CharField(blank=True, default="", max_length=1024),
        ),
    ]
