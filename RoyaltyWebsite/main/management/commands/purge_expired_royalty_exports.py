"""Delete S3 objects and DB rows for RoyaltyUserExport past expires_at."""
from django.core.management.base import BaseCommand
from django.utils import timezone

from main.models import RoyaltyUserExport
from main.royalty_export_s3 import delete_royalty_export_object


class Command(BaseCommand):
    help = "Remove expired per-user royalty CSV exports (S3 + metadata). Run daily via cron."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="List what would be deleted without deleting.",
        )

    def handle(self, *args, **options):
        dry = options["dry_run"]
        now = timezone.now()
        qs = RoyaltyUserExport.objects.filter(expires_at__lt=now).order_by("pk")
        n = qs.count()
        if n == 0:
            self.stdout.write(self.style.SUCCESS("No expired royalty exports."))
            return
        self.stdout.write(f"Found {n} expired export(s).")
        deleted = 0
        for obj in qs.iterator(chunk_size=100):
            if not dry:
                delete_royalty_export_object(obj.s3_key)
                obj.delete()
            deleted += 1
        if dry:
            self.stdout.write(self.style.WARNING(f"Dry-run: would delete {deleted} record(s)."))
        else:
            self.stdout.write(self.style.SUCCESS(f"Deleted {deleted} expired export(s)."))
