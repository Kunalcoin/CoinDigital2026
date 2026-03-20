"""
Send a release to TikTok: build TikTok DDEX XML (UGC) and upload to TikTok S3.
Same as the TikTok part of "DDEX delivery for Audiomack, Gaana & TikTok" on Preview & Distribute.

Run: python manage.py ddex_deliver_tiktok 36306
     python manage.py ddex_deliver_tiktok --upc 8905285301465

Requires TIKTOK_S3_BUCKET, TIKTOK_S3_PREFIX, TIKTOK_AWS_ACCESS_KEY_ID, TIKTOK_AWS_SECRET_ACCESS_KEY in .env (see TIKTOK_DDEX_DELIVERY.md).
"""
from django.core.management.base import BaseCommand

from releases.models import Release
from releases.tiktok_delivery import deliver_release_to_tiktok


class Command(BaseCommand):
    help = (
        "Send release to TikTok: build DDEX ERN 4.3 for TikTok (UGC), upload XML + resources to TikTok S3."
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
                self.style.ERROR("Provide release_id or --upc. Example: python manage.py ddex_deliver_tiktok 36306")
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

        self.stdout.write(f"Sending release to TikTok: {release.title} (id={release.id}, upc={release.upc or 'N/A'})")
        success, err, detail = deliver_release_to_tiktok(release)
        if not success:
            self.stderr.write(self.style.ERROR(err or detail.get("message", "Delivery failed.")))
            return
        msg = detail.get("message", "Done.")
        self.stdout.write(self.style.SUCCESS(msg))
        if detail.get("tiktok_s3_uploaded"):
            self.stdout.write("  Uploaded to TikTok S3.")
        if detail.get("batch_id"):
            self.stdout.write(f"  Batch ID (report to TikTok): {detail['batch_id']}")
        if detail.get("upc"):
            self.stdout.write(f"  UPC (report to TikTok): {detail['upc']}")
