"""
Deliver one release to Audiomack, Gaana and TikTok (DDEX ERN 4.3).
Finds a release pending approval if no release_id given, otherwise uses the given ID.
Prints UPC, resources shared, and result (acknowledgement) per store.

Run: python manage.py ddex_deliver_all
     python manage.py ddex_deliver_all 36306
     python manage.py ddex_deliver_all --upc 8905285301465
"""
from django.core.management.base import BaseCommand

from releases.audiomack_delivery import deliver_release_to_audiomack
from releases.gaana_delivery import deliver_release_to_gaana
from releases.models import Release, Track
from releases.tiktok_delivery import deliver_release_to_tiktok


class Command(BaseCommand):
    help = (
        "Deliver one release to Audiomack, Gaana and TikTok. "
        "If no release_id/upc given, use the most recent release pending approval."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "release_id",
            nargs="?",
            type=int,
            help="Release ID (optional; if omitted, use latest pending_approval release)",
        )
        parser.add_argument(
            "--upc",
            type=str,
            help="Release UPC (alternative to release_id)",
        )

    def handle(self, *args, **options):
        release_id = options.get("release_id")
        upc_arg = (options.get("upc") or "").strip()
        release = None
        if release_id:
            try:
                release = Release.objects.get(pk=release_id)
            except Release.DoesNotExist:
                self.stderr.write(self.style.ERROR(f"Release not found (id={release_id})"))
                return
        elif upc_arg:
            try:
                release = Release.objects.get(upc=upc_arg)
            except Release.DoesNotExist:
                self.stderr.write(self.style.ERROR(f"Release not found (upc={upc_arg})"))
                return
        else:
            release = (
                Release.objects.filter(approval_status__iexact="pending_approval")
                .order_by("-submitted_for_approval_at", "-updated_at")
                .first()
            )
            if not release:
                self.stderr.write(
                    self.style.ERROR("No release pending approval found. Provide release_id or --upc.")
                )
                return

        upc = (release.upc or "").strip() or str(release.id)
        tracks = list(Track.objects.filter(release=release).order_by("id"))
        resource_list = ["resources/coverart.jpg"]
        for i in range(len(tracks)):
            resource_list.append(f"resources/1_{i + 1}.flac")

        self.stdout.write("")
        self.stdout.write(self.style.HTTP_INFO("=== DDEX delivery to Audiomack, Gaana, TikTok ==="))
        self.stdout.write(f"Release: {release.title} (id={release.id})")
        self.stdout.write(f"UPC: {upc}")
        self.stdout.write(f"Resources shared: {resource_list}")
        self.stdout.write("")

        # Audiomack
        self.stdout.write("Audiomack...")
        a_ok, a_err, a_detail = deliver_release_to_audiomack(release)
        if a_ok:
            self.stdout.write(self.style.SUCCESS(f"  OK: {a_detail.get('message', a_err or 'Delivered')}"))
            if a_detail.get("s3_bucket") and a_detail.get("s3_key"):
                self.stdout.write(f"  XML: s3://{a_detail['s3_bucket']}/{a_detail['s3_key']}")
        else:
            self.stdout.write(self.style.ERROR(f"  Failed: {a_err or a_detail.get('message', 'Unknown')}"))
        self.stdout.write("")

        # Gaana
        self.stdout.write("Gaana...")
        g_ok, g_err, g_detail = deliver_release_to_gaana(release)
        if g_ok:
            self.stdout.write(self.style.SUCCESS(f"  OK: {g_detail.get('message', g_err or 'Delivered')}"))
            if g_detail.get("gaana_sftp_uploaded"):
                self.stdout.write("  Uploaded to Gaana SFTP.")
        else:
            self.stdout.write(self.style.ERROR(f"  Failed: {g_err or g_detail.get('message', 'Unknown')}"))
        self.stdout.write("")

        # TikTok
        self.stdout.write("TikTok...")
        t_ok, t_err, t_detail = deliver_release_to_tiktok(release)
        if t_ok:
            self.stdout.write(self.style.SUCCESS(f"  OK: {t_detail.get('message', t_err or 'Delivered')}"))
            if t_detail.get("batch_id"):
                self.stdout.write(f"  Batch ID (report to TikTok): {t_detail['batch_id']}")
        else:
            self.stdout.write(self.style.ERROR(f"  Failed: {t_err or t_detail.get('message', 'Unknown')}"))
        self.stdout.write("")

        self.stdout.write(self.style.HTTP_INFO("=== Summary ==="))
        self.stdout.write(f"UPC: {upc}")
        self.stdout.write(f"Resources: {', '.join(resource_list)}")
        self.stdout.write(
            f"Audiomack: {'OK' if a_ok else 'FAILED'} | Gaana: {'OK' if g_ok else 'FAILED'} | TikTok: {'OK' if t_ok else 'FAILED'}"
        )
        if not (a_ok and g_ok and t_ok):
            self.stderr.write(self.style.WARNING("One or more stores failed. See messages above."))
