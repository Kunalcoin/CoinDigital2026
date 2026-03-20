"""
Generate DDEX ERN 4.3 for many releases × all active DSPs (Phase 3 batch).
Use for "all approved" or "releases updated in last 24h".

Run:
  python manage.py build_ddex_batch --since 2026-01-27
  python manage.py build_ddex_batch --since 2026-01-27 --status approved
  python manage.py build_ddex_batch --since 2026-01-27 --limit 50 --output /tmp/batch
  python manage.py build_ddex_batch --since 2026-01-27 --dry-run
"""
import os
from datetime import datetime, timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone
from releases.models import Release
from releases.ddex_builder import build_new_release_message
from releases.ddex_dsp_registry import list_dsp_codes


class Command(BaseCommand):
    help = (
        "Generate DDEX ERN 4.3 for multiple releases for every active DSP. "
        "Releases: updated since --since date (or last 24h if not set). "
        "Output: <output>/<dsp_code>/<upc>/<upc>.xml"
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--since",
            type=str,
            help="Only releases updated on or after this date (YYYY-MM-DD). Default: 24 hours ago.",
        )
        parser.add_argument(
            "--status",
            type=str,
            default="",
            help="Optional: filter by approval_status (e.g. approved). Leave empty for all.",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=0,
            help="Max number of releases to process (0 = no limit).",
        )
        parser.add_argument(
            "--output",
            "-o",
            type=str,
            default="ddex_output",
            help="Base directory. Layout: <output>/<dsp_code>/<upc>/<upc>.xml",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="List releases and DSPs that would be processed; do not write files.",
        )
        parser.add_argument(
            "--verbose",
            action="store_true",
            help="Print each file path as written.",
        )

    def handle(self, *args, **options):
        since_arg = options.get("since")
        status_filter = (options.get("status") or "").strip()
        limit = options.get("limit") or 0
        output_base = (options.get("output") or "ddex_output").rstrip("/")
        dry_run = options.get("dry_run", False)
        verbose = options.get("verbose", False)

        if since_arg:
            try:
                since_date = datetime.strptime(since_arg.strip()[:10], "%Y-%m-%d")
                since_dt = timezone.make_aware(since_date.replace(hour=0, minute=0, second=0, microsecond=0))
            except ValueError:
                self.stderr.write(
                    self.style.ERROR("--since must be YYYY-MM-DD (e.g. 2026-01-27).")
                )
                return
        else:
            since_dt = timezone.now() - timedelta(hours=24)

        queryset = Release.objects.filter(updated_at__gte=since_dt).order_by("updated_at")
        if status_filter:
            queryset = queryset.filter(approval_status=status_filter)
        if limit > 0:
            queryset = queryset[:limit]

        releases = list(queryset)
        dsp_codes = list_dsp_codes(active_only=True)

        if not dsp_codes:
            self.stderr.write(
                self.style.WARNING("No active DSPs in registry. Add DSPs to releases/data/ddex_dsps.json.")
            )
            return

        if not releases:
            self.stdout.write(
                self.style.WARNING(
                    f"No releases found (updated since {since_dt.date()}"
                    + (f", status={status_filter}" if status_filter else "")
                    + ")."
                )
            )
            return

        self.stdout.write(
            f"Releases: {len(releases)} (updated since {since_dt.date()}"
            + (f", status={status_filter}" if status_filter else "")
            + f"). DSPs: {len(dsp_codes)}."
        )
        if dry_run:
            for r in releases:
                upc = (r.upc or "").strip() or str(r.id)
                self.stdout.write(f"  Would generate: {r.title} (UPC={upc}) × {len(dsp_codes)} DSPs")
            self.stdout.write(self.style.SUCCESS("Dry run done. Run without --dry-run to generate."))
            return

        total = 0
        for release in releases:
            upc = (release.upc or "").strip() or str(release.id)
            for dsp_code in dsp_codes:
                out_dir = os.path.join(output_base, dsp_code, upc)
                os.makedirs(out_dir, exist_ok=True)
                path = os.path.join(out_dir, f"{upc}.xml")
                xml = build_new_release_message(release, store=dsp_code)
                with open(path, "w", encoding="utf-8") as f:
                    f.write(xml)
                total += 1
                if verbose:
                    self.stdout.write(f"  {dsp_code}/{upc}: {path}")

        self.stdout.write(
            self.style.SUCCESS(
                f"Wrote {total} DDEX file(s) for {len(releases)} release(s) × {len(dsp_codes)} DSP(s) to {output_base}/"
            )
        )
