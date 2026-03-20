"""
Send a release to Gaana: build Gaana DDEX XML and upload to your S3 with resources (cover + audio).
Same as the Gaana part of "DDEX delivery for Audiomack & Gaana" on Preview & Distribute.

Run: python manage.py ddex_deliver_gaana 36306
     python manage.py ddex_deliver_gaana --upc 8905285301465
"""
from django.core.management.base import BaseCommand

from releases.gaana_delivery import deliver_release_to_gaana
from releases.models import Release


class Command(BaseCommand):
    help = (
        "Send release to Gaana: build DDEX ERN 4.3 for Gaana, upload XML to your S3, "
        "and copy cover + audio into resources/ (full package)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "release_id",
            nargs="?",
            type=int,
            help="Release ID (e.g. 36306)",
        )
        parser.add_argument(
            "--upc",
            type=str,
            help="Release UPC (alternative to release_id)",
        )

    def handle(self, *args, **options):
        release_id = options.get("release_id")
        upc = (options.get("upc") or "").strip()
        if not release_id and not upc:
            self.stderr.write(
                self.style.ERROR("Provide release_id or --upc. Example: python manage.py ddex_deliver_gaana 36306")
            )
            return
        try:
            if release_id:
                release = Release.objects.get(pk=release_id)
            else:
                release = Release.objects.get(upc=upc)
        except Release.DoesNotExist:
            self.stderr.write(self.style.ERROR(f"Release not found (id={release_id or 'N/A'}, upc={upc or 'N/A'})"))
            return

        self.stdout.write(f"Sending release to Gaana: {release.title} (id={release.id}, upc={release.upc or 'N/A'})")
        success, err, detail = deliver_release_to_gaana(release)
        if not success:
            self.stderr.write(self.style.ERROR(err or detail.get("message", "Delivery failed.")))
            if detail.get("asset_errors"):
                for e in detail["asset_errors"]:
                    self.stderr.write(f"  - {e}")
            return
        msg = detail.get("message", "Done.")
        self.stdout.write(self.style.SUCCESS(msg))
        if detail.get("s3_bucket") and detail.get("s3_key"):
            self.stdout.write(f"  XML: s3://{detail['s3_bucket']}/{detail['s3_key']}")
        if detail.get("assets_copied") is not None:
            self.stdout.write(f"  Resources copied: {detail['assets_copied']} file(s)")
        if detail.get("asset_errors"):
            for e in detail["asset_errors"]:
                self.stdout.write(self.style.WARNING(f"  Warning: {e}"))
