# Sonosuite API delivery — add operation IDs to Release

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("releases", "0010_add_approval_status_to_release"),
    ]

    operations = [
        migrations.AddField(
            model_name="release",
            name="sonosuite_operation_ids",
            field=models.TextField(blank=True, default="", verbose_name="Sonosuite operation IDs"),
        ),
    ]
