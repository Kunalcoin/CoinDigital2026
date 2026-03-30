# Generated manually for Apple Music Dolby Atmos per-user flag.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("main", "0005_alter_cduser_language_alter_cduser_role"),
    ]

    operations = [
        migrations.AddField(
            model_name="cduser",
            name="apple_music_dolby_atmos_enabled",
            field=models.BooleanField(
                default=False,
                help_text="When enabled, this user’s releases may include Dolby Atmos (BWF ADM .wav) on tracks "
                "that have an Atmos URL and secondary ISRC; metadata uses <assets> per Apple Music spec.",
                verbose_name="Apple Music Dolby Atmos delivery",
            ),
        ),
        migrations.AddIndex(
            model_name="cduser",
            index=models.Index(
                fields=["apple_music_dolby_atmos_enabled"],
                name="apple_music_dolby_atmos_idx",
            ),
        ),
    ]
