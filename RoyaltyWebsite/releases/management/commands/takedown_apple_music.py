"""
Send takedown (PurgeReleaseMessage) for a release to Apple Music via Merlin Bridge SFTP.
Use for Apple checklist compliance or to remove a release from Apple Music.

Run: python manage.py takedown_apple_music 36848
     python manage.py takedown_apple_music --upc 8905285306132
"""
from django.core.management.base import BaseCommand

from releases.merlin_bridge_delivery import deliver_takedown_to_merlin_bridge
from releases.models import Release
from releases.upc_utils import find_release_by_upc


class Command(BaseCommand):
    help = (
        "Send Apple Music (Merlin Bridge) takedown: build PurgeReleaseMessage XML, "
        "upload to Bridge SFTP at {path}/takedown/{upc}_PurgeRelease.xml."
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

    def handle(self, *args, **options):
        release_id = options.get("release_id")
        upc = (options.get("upc") or "").strip()
        if not release_id and not upc:
            self.stderr.write(
                self.style.ERROR("Provide release_id or --upc. Example: python manage.py takedown_apple_music --upc 8905285306132")
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

        self.stdout.write(f"Sending Apple Music takedown for release id={release.id} upc={getattr(release, 'upc', '')}...")
        try:
            ok, err, detail = deliver_takedown_to_merlin_bridge(release)
        except Exception as e:
            self.stderr.write(self.style.ERROR(f"Takedown failed: {e}"))
            raise

        if ok:
            self.stdout.write(self.style.SUCCESS(detail.get("message", "Apple Music takedown sent to Merlin Bridge SFTP.")))
            sftp_path = detail.get("merlin_bridge_sftp_path")
            if sftp_path:
                self.stdout.write(f"Takedown file uploaded to: {sftp_path}")
        else:
            self.stderr.write(self.style.ERROR(err or "Merlin Bridge SFTP takedown failed."))
            if detail:
                self.stderr.write(str(detail))
