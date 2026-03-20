# Generated manually for Apple Music Merlin Bridge checklist (streaming / retail only)

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("releases", "0016_alter_relatedartists_role_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="release",
            name="apple_music_commercial_model",
            field=models.CharField(
                choices=[
                    ("both", "Streaming + download (default)"),
                    ("streaming_only", "Streaming only"),
                    ("retail_only", "Retail / download only (no streaming)"),
                ],
                default="both",
                help_text="Merlin Bridge: use Streaming only or Retail only for checklist test deliveries; default is both.",
                max_length=20,
                verbose_name="Apple Music commercial model",
            ),
        ),
    ]
