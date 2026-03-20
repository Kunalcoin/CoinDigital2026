"""
Deliver a release to Apple Music via Merlin Bridge (Apple iTunes Importer format, SFTP).
Same as clicking "Deliver to Apple Music only" on the Preview & Distribute page.

Run: python manage.py deliver_apple_music 36848
     python manage.py deliver_apple_music --upc 8905285304930
     python manage.py deliver_apple_music --upc 8905285306064 --metadata-only
"""
from django.core.management.base import BaseCommand

from releases.merlin_bridge_delivery import deliver_release_to_merlin_bridge
from releases.models import Release
from releases.upc_utils import find_release_by_upc


class Command(BaseCommand):
    help = (
        "Deliver release to Apple Music via Merlin Bridge: build Apple iTunes Importer XML, "
        "upload to Bridge SFTP (metadata + artwork + audio). "
        "Use --metadata-only to upload only metadata.xml inside .itmsp.zip (Bridge metadata update checklist)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "release_id",
            nargs="?",
            type=int,
            help="Release ID (e.g. 36848)",
        )
        parser.add_argument(
            "--upc",
            type=str,
            help="Release UPC (alternative to release_id)",
        )
        parser.add_argument(
            "--metadata-only",
            action="store_true",
            help=(
                "Upload ONLY metadata.xml (no .jpg / .wav in the zip). "
                "Apple/Bridge will report 'Missing binaries' if the validator expects assets in the package — "
                "use full delivery (omit this flag) for normal delivery and first ingest."
            ),
        )

    def handle(self, *args, **options):
        release_id = options.get("release_id")
        upc = (options.get("upc") or "").strip()
        if not release_id and not upc:
            self.stderr.write(
                self.style.ERROR("Provide release_id or --upc. Example: python manage.py deliver_apple_music 36848")
            )
            return
        try:
            if release_id:
                release = Release.objects.get(pk=release_id)
            else:
                release = find_release_by_upc(upc, Release)
                if not release:
                    self.stderr.write(self.style.ERROR(f"Release not found for UPC: {upc}"))
                    return
        except Release.DoesNotExist:
            self.stderr.write(self.style.ERROR(f"Release not found (id={release_id or 'N/A'}, upc={upc or 'N/A'})"))
            return

        approval = (getattr(release, "approval_status", None) or "").strip().lower()
        if approval != "approved":
            self.stderr.write(
                self.style.ERROR(f"Release must be approved first. Current status: {approval!r}")
            )
            return

        meta_only = bool(options.get("metadata_only"))
        if meta_only:
            self.stdout.write(f"Metadata-only update: release id={release.id} upc={getattr(release, 'upc', '')} → Merlin Bridge...")
            self.stderr.write(
                self.style.WARNING(
                    "WARNING: --metadata-only puts NO .jpg or audio files in the .itmsp.zip. "
                    "If metadata.xml still names those files (normal for us), Apple/Merlin often reports "
                    "'Missing binaries stated in the metadata file'. "
                    "For a normal delivery or to fix that error, run WITHOUT --metadata-only "
                    "(full S3 download + zip with metadata + artwork + all tracks)."
                )
            )
            self.stdout.write("Building XML with size/MD5 from S3 (HeadObject; cover read once for JPEG MD5)...")
        else:
            self.stdout.write(f"Delivering release id={release.id} upc={getattr(release, 'upc', '')} to Apple Music (Merlin Bridge)...")
            self.stdout.write(
                "Loading SSH key and fetching assets from S3 (full audio per track; large WAV/FLAC can take "
                "many minutes — you should see progress every ~10 MB. Timeouts: MERLIN_BRIDGE_S3_READ_TIMEOUT, default 600s)..."
            )
        try:
            ok, err, detail = deliver_release_to_merlin_bridge(release, metadata_only=meta_only)
        except Exception as e:
            self.stderr.write(self.style.ERROR(f"Delivery failed: {e}"))
            raise

        if ok:
            self.stdout.write(self.style.SUCCESS(detail.get("message", "Delivered to Merlin Bridge SFTP.")))
            sftp_path = detail.get("merlin_bridge_sftp_path")
            if sftp_path:
                self.stdout.write(f"If Bridge does not show the package, log in to SFTP and confirm the file exists at: {sftp_path}")
        else:
            self.stderr.write(self.style.ERROR(err or "Merlin Bridge SFTP upload failed."))
            if detail:
                self.stderr.write(str(detail))
