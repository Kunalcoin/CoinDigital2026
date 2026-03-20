"""
Build a Gaana DDEX batch: BatchNumber/upc/upc.xml, upc/resources/, BatchComplete_{BatchNumber}.xml.
Gaana requires this folder structure for SFTP delivery. Run:
  python manage.py build_ddex_gaana_batch <release_id> [--output dir] [--batch-number N]
  python manage.py build_ddex_gaana_batch --upc 3667007197057 --output /tmp/gaana_batches
After generation, place your assets in <batch>/<upc>/resources/ (e.g. coverart.jpg, 1_1.flac) to match
the URIs in the XML, then upload the whole batch folder to Gaana SFTP.
"""
import os
from datetime import datetime, timezone
from django.core.management.base import BaseCommand
from releases.models import Release
from releases.ddex_builder import build_new_release_message


def _batch_complete_xml(batch_number: str) -> str:
    """Minimal BatchComplete marker for Gaana (they validate folder structure)."""
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<BatchComplete BatchNumber="{batch_number}" xmlns="http://ddex.net/xml/ern/43">
  <BatchId>{batch_number}</BatchId>
  <CompletedDateTime>{datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")}</CompletedDateTime>
</BatchComplete>
"""


class Command(BaseCommand):
    help = (
        "Build a Gaana DDEX batch: BatchNumber/upc/upc.xml, upc/resources/, BatchComplete_<BatchNumber>.xml. "
        "Place assets in upc/resources/ (coverart.jpg, 1_1.flac, etc.) then upload to Gaana SFTP."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "release_id",
            nargs="?",
            type=int,
            help="Release ID (primary key)",
        )
        parser.add_argument(
            "--upc",
            type=str,
            help="Release UPC (alternative to release_id)",
        )
        parser.add_argument(
            "--output",
            "-o",
            type=str,
            default="ddex_gaana_batches",
            help="Base directory for batches (default: ddex_gaana_batches).",
        )
        parser.add_argument(
            "--batch-number",
            type=str,
            help="Batch number (default: timestamp-based, e.g. 20250216120000001).",
        )
        parser.add_argument(
            "--update",
            action="store_true",
            help="Generate Update message (metadata-only) instead of Insert.",
        )
        parser.add_argument(
            "--linked-message-id",
            type=str,
            help="For --update: MessageId of the original Insert message.",
        )

    def handle(self, *args, **options):
        release_id = options.get("release_id")
        upc_arg = options.get("upc")
        output_base = (options.get("output") or "ddex_gaana_batches").rstrip("/")
        batch_number = options.get("batch_number")
        is_update = options.get("update", False)
        linked_message_id = options.get("linked_message_id")

        if not release_id and not upc_arg:
            self.stderr.write(
                self.style.ERROR(
                    "Provide either release_id or --upc. "
                    "Example: python manage.py build_ddex_gaana_batch 123  OR  build_ddex_gaana_batch --upc 3667007197057"
                )
            )
            return

        try:
            if release_id:
                release = Release.objects.get(id=release_id)
            else:
                release = Release.objects.get(upc=upc_arg.strip())
        except Release.DoesNotExist:
            self.stderr.write(
                self.style.ERROR(f"Release not found (id={release_id or 'N/A'}, upc={upc_arg or 'N/A'})")
            )
            return

        upc = (release.upc or "").strip() or str(release.id)
        if not batch_number:
            batch_number = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S") + "001"

        batch_dir = os.path.join(output_base, batch_number)
        upc_dir = os.path.join(batch_dir, upc)
        resources_dir = os.path.join(upc_dir, "resources")

        os.makedirs(resources_dir, exist_ok=True)

        message_control_type = "UpdateMessage" if is_update else "LiveMessage"
        xml = build_new_release_message(
            release,
            store="gaana",
            message_control_type=message_control_type,
            linked_message_id=linked_message_id,
        )

        upc_xml_path = os.path.join(upc_dir, f"{upc}.xml")
        with open(upc_xml_path, "w", encoding="utf-8") as f:
            f.write(xml)

        batch_complete_path = os.path.join(batch_dir, f"BatchComplete_{batch_number}.xml")
        with open(batch_complete_path, "w", encoding="utf-8") as f:
            f.write(_batch_complete_xml(batch_number))

        self.stdout.write(
            self.style.SUCCESS(
                f"Gaana batch created: {batch_dir}\n"
                f"  {upc}/{upc}.xml\n"
                f"  {upc}/resources/ (place coverart.jpg, 1_1.flac, etc. here)\n"
                f"  BatchComplete_{batch_number}.xml\n"
                f"Then upload the folder '{batch_number}' to Gaana SFTP."
            )
        )
