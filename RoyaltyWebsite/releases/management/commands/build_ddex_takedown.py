"""
Generate DDEX ERN 4.3 takedown for a release.
- Audiomack: PurgeReleaseMessage.
- Gaana: NewReleaseMessage with TakeDown tag (immediate) or ValidityPeriod EndDate (time-based).
Run:
  python manage.py build_ddex_takedown <release_id> --store audiomack [--output path]
  python manage.py build_ddex_takedown <release_id> --store gaana [--immediate | --end-date YYYY-MM-DD] [--output path]
"""
import os
from django.core.management.base import BaseCommand
from releases.models import Release
from releases.ddex_audiomack_takedown import build_audiomack_takedown_message
from releases.ddex_builder import build_new_release_message


class Command(BaseCommand):
    help = (
        "Generate DDEX ERN 4.3 takedown XML. "
        "Use --store audiomack (PurgeReleaseMessage) or --store gaana (NewReleaseMessage with TakeDown/EndDate)."
    )

    def add_arguments(self, parser):
        parser.add_argument("release_id", type=int, help="Release ID (primary key)")
        parser.add_argument(
            "--store",
            type=str,
            default="audiomack",
            choices=["audiomack", "gaana"],
            help="Store (default: audiomack).",
        )
        parser.add_argument(
            "--output",
            "-o",
            type=str,
            help="Output file path. If omitted, prints to stdout.",
        )
        parser.add_argument(
            "--immediate",
            action="store_true",
            help="Gaana only: immediate takedown using TakeDown tag (default for gaana if --end-date not set).",
        )
        parser.add_argument(
            "--end-date",
            type=str,
            metavar="YYYY-MM-DD",
            help="Gaana only: time-based takedown using ValidityPeriod EndDate.",
        )

    def handle(self, *args, **options):
        release_id = options["release_id"]
        output_path = options.get("output")
        store = (options.get("store") or "audiomack").strip().lower()
        immediate = options.get("immediate", False)
        end_date = (options.get("end_date") or "").strip() or None

        try:
            release = Release.objects.get(id=release_id)
        except Release.DoesNotExist:
            self.stderr.write(self.style.ERROR(f"Release not found: {release_id}"))
            return

        if store == "audiomack":
            xml = build_audiomack_takedown_message(release)
        elif store == "gaana":
            # Gaana: NewReleaseMessage with takedown deal terms
            if end_date:
                xml = build_new_release_message(
                    release, store="gaana",
                    takedown_immediate=False, takedown_end_date=end_date,
                )
            else:
                xml = build_new_release_message(
                    release, store="gaana",
                    takedown_immediate=True, takedown_end_date=None,
                )
        else:
            self.stderr.write(self.style.ERROR(f"Unsupported store for takedown: {store}"))
            return

        if output_path:
            out_dir = os.path.dirname(output_path)
            if out_dir and not os.path.exists(out_dir):
                os.makedirs(out_dir, exist_ok=True)
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(xml)
            self.stdout.write(self.style.SUCCESS(f"DDEX takedown XML written to {output_path}"))
        else:
            self.stdout.write(xml)
