# Generated manually — Apple Music Instant Grat (Merlin Bridge checklist)

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("releases", "0019_alter_release_apple_music_preorder_start_date"),
    ]

    operations = [
        migrations.AddField(
            model_name="track",
            name="apple_music_instant_grat",
            field=models.BooleanField(
                default=False,
                help_text="If the release has an Apple Music pre-order, mark tracks that are Instant Grat "
                "(available during pre-order). Merlin requires ≥1 such track and ≤50% of all tracks. "
                "Ignored when the release has no pre-order date.",
                verbose_name="Apple Music instant gratification (pre-order)",
            ),
        ),
    ]
