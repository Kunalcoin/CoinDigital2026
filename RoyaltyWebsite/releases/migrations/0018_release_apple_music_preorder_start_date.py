# Generated manually — Apple Music preorder (Merlin Bridge checklist)

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("releases", "0017_release_apple_music_commercial_model"),
    ]

    operations = [
        migrations.AddField(
            model_name="release",
            name="apple_music_preorder_start_date",
            field=models.DateField(
                blank=True,
                help_text="If set, metadata.xml includes preorder_sales_start_date on each product (Merlin preorder checklist). Must be before Digital release date and should be in the future when you deliver.",
                null=True,
                verbose_name="Apple Music pre-order sales start date",
            ),
        ),
    ]
