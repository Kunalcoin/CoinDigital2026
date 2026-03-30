"""Delete all per-user royalty CSV exports for one confirmed-sales month (S3 + DB)."""
from datetime import date

from django.core.management.base import BaseCommand, CommandError

from main.models import RoyaltyUserExport
from main.royalty_export_s3 import delete_royalty_export_object


class Command(BaseCommand):
    help = (
        "Remove RoyaltyUserExport rows and S3 objects for a given report_period "
        "(first day of confirmed sales month). Use before re-uploading that month."
    )

    def add_arguments(self, parser):
        parser.add_argument("--month", type=int, required=True, help="Month 1–12")
        parser.add_argument("--year", type=int, required=True, help="Four-digit year")
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Print counts only; do not delete.",
        )

    def handle(self, *args, **options):
        month = options["month"]
        year = options["year"]
        dry = options["dry_run"]
        if month < 1 or month > 12:
            raise CommandError("month must be 1–12")
        if year < 2000 or year > 2100:
            raise CommandError("year looks invalid")
        report_period = date(year, month, 1)
        qs = RoyaltyUserExport.objects.filter(report_period=report_period).order_by("pk")
        n = qs.count()
        if n == 0:
            self.stdout.write(
                self.style.SUCCESS(f"No exports for report_period={report_period.isoformat()}.")
            )
            return
        self.stdout.write(f"Found {n} export(s) for {report_period.isoformat()}.")
        if dry:
            self.stdout.write(self.style.WARNING("Dry-run: no deletions performed."))
            return
        deleted = 0
        for obj in qs.iterator(chunk_size=100):
            delete_royalty_export_object(obj.s3_key)
            obj.delete()
            deleted += 1
        self.stdout.write(
            self.style.SUCCESS(f"Deleted {deleted} export(s) and removed S3 objects.")
        )
