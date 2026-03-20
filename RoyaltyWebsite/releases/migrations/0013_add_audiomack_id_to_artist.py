# Add Audiomack Artist ID to Artist for DDEX / Audiomack delivery

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("releases", "0012_add_submitted_for_approval_at"),
    ]

    operations = [
        migrations.AddField(
            model_name="artist",
            name="audiomack_id",
            field=models.CharField(
                blank=True,
                default="",
                max_length=1024,
                verbose_name="Audiomack Artist ID",
            ),
        ),
    ]
