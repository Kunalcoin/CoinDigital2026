"""
Generate DDEX ERN 4.3 XML for one release for all active DSPs (Phase 3).
One package per DSP: output/{dsp_code}/{upc}/{upc}.xml

Run:
  python manage.py build_ddex_all 123
  python manage.py build_ddex_all 123 --output /tmp/ddex_packages
  python manage.py build_ddex_all --upc 8905285299663
"""
import os
from django.core.management.base import BaseCommand
from releases.models import Release
from releases.ddex_builder import build_new_release_message
from releases.ddex_dsp_registry import list_dsp_codes


class Command(BaseCommand):
    help = (
        "Generate DDEX ERN 4.3 for the given release for every active DSP. "
        "Writes one package per DSP: <output>/<dsp_code>/<upc>/<upc>.xml"
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
            default="ddex_output",
            help="Base directory. Layout: <output>/<dsp_code>/<upc>/<upc>.xml",
        )
        parser.add_argument(
            "--test",
            action="store_true",
            help="Use MessageControlType TestMessage (e.g. JioSaavn testing).",
        )
        parser.add_argument(
            "--verbose",
            action="store_true",
            help="Print each DSP and file path.",
        )

    def handle(self, *args, **options):
        release_id = options.get("release_id")
        upc_arg = options.get("upc")
        output_base = (options.get("output") or "ddex_output").rstrip("/")
        use_test_message = options.get("test", False)
        verbose = options.get("verbose", False)

        if not release_id and not upc_arg:
            self.stderr.write(
                self.style.ERROR(
                    "Provide either release_id or --upc. "
                    "Example: python manage.py build_ddex_all 123  OR  python manage.py build_ddex_all --upc 8905285299663"
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
        dsp_codes = list_dsp_codes(active_only=True)
        if not dsp_codes:
            self.stderr.write(
                self.style.WARNING("No active DSPs in registry. Add DSPs to releases/data/ddex_dsps.json.")
            )
            return

        message_control_type = "TestMessage" if use_test_message else "LiveMessage"
        written = 0
        for dsp_code in dsp_codes:
            # One package per DSP: output/{dsp_code}/{upc}/{upc}.xml
            out_dir = os.path.join(output_base, dsp_code, upc)
            os.makedirs(out_dir, exist_ok=True)
            path = os.path.join(out_dir, f"{upc}.xml")
            xml = build_new_release_message(
                release, store=dsp_code, message_control_type=message_control_type
            )
            with open(path, "w", encoding="utf-8") as f:
                f.write(xml)
            written += 1
            if verbose:
                self.stdout.write(f"  {dsp_code}: {path}")

        self.stdout.write(
            self.style.SUCCESS(
                f"Wrote {written} DDEX package(s) for release {release.title} (UPC={upc}) to {output_base}/<dsp_code>/{upc}/"
            )
        )
