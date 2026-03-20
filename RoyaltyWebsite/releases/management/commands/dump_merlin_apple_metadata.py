"""
Dump the generated Apple Music (music5.3) metadata.xml we would deliver to Merlin Bridge.

Usage:
  python manage.py dump_merlin_apple_metadata --upc 8905285306132
  python manage.py dump_merlin_apple_metadata --upc 8905285306064 --full
  python manage.py dump_merlin_apple_metadata <release_id> --output /tmp/metadata.xml
"""
import re
from django.core.management.base import BaseCommand

from releases.apple_itunes_importer import build_apple_itunes_metadata
from releases.models import Release
from releases.upc_utils import find_release_by_upc, normalize_upc_to_13


class Command(BaseCommand):
    help = "Dump generated Merlin Bridge Apple metadata.xml for a given release/upc."

    def add_arguments(self, parser):
        parser.add_argument("release_id", nargs="?", type=int, help="Release ID")
        parser.add_argument("--upc", type=str, help="Release UPC")
        parser.add_argument(
            "--full",
            action="store_true",
            help="Print the entire metadata.xml (not just vendor_id/upc summary).",
        )
        parser.add_argument(
            "--output",
            type=str,
            default="",
            help="Write full XML to this file path (implies full XML).",
        )

    def handle(self, *args, **options):
        release_id = options.get("release_id")
        upc = (options.get("upc") or "").strip()

        if not release_id and not upc:
            self.stderr.write(self.style.ERROR("Provide release_id or --upc"))
            return

        if release_id:
            release = Release.objects.get(pk=release_id)
        else:
            release = find_release_by_upc(upc, Release)
            if not release:
                self.stderr.write(self.style.ERROR(f"Release not found for UPC: {upc}"))
                return

        upc_norm = normalize_upc_to_13(upc) or (getattr(release, "upc", "") or "").strip()
        upc_norm = upc_norm or str(release.id)

        xml = build_apple_itunes_metadata(release, upc_norm, file_info={}, audio_extension="wav")
        # Extract album-level vendor_id and upc
        m_vendor = re.search(r"<album>.*?<vendor_id>(.*?)</vendor_id>", xml, flags=re.DOTALL)
        m_vendor2 = re.search(r"<vendor_id>(.*?)</vendor_id>", xml)
        m_upc = re.search(r"<upc>(.*?)</upc>", xml)

        vendor_val = (m_vendor.group(1) if m_vendor else (m_vendor2.group(1) if m_vendor2 else None))
        upc_val = m_upc.group(1) if m_upc else None

        self.stdout.write(self.style.SUCCESS("Generated metadata.xml values:"))
        self.stdout.write(f"  album.vendor_id = {vendor_val}")
        self.stdout.write(f"  album.upc       = {upc_val}")

        # Also helpful for diagnosing: show the DPID-like prefix before the underscore.
        if vendor_val and "_" in vendor_val:
            self.stdout.write(f"  dpid_prefix     = {vendor_val.split('_', 1)[0]}")

        out_path = (options.get("output") or "").strip()
        if options.get("full") or out_path:
            self.stdout.write("")
            if out_path:
                with open(out_path, "w", encoding="utf-8") as f:
                    f.write(xml)
                self.stdout.write(self.style.SUCCESS(f"Full metadata.xml written to: {out_path}"))
            else:
                self.stdout.write(self.style.SUCCESS("Full metadata.xml:"))
                self.stdout.write(xml)
        else:
            self.stdout.write("")
            self.stdout.write("(Use --full to print the entire XML, or --output path.xml to save it.)")

