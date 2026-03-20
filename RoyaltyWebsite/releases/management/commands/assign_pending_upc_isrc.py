"""
Assign UPC and ISRC to pending releases that are missing them.
Run: python manage.py assign_pending_upc_isrc
"""
from django.core.management.base import BaseCommand

from releases.models import Release, Track, UniqueCode
from releases.upc_utils import normalize_upc_to_13


class Command(BaseCommand):
    help = "Assign UPC and ISRC to pending releases that don't have them."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Only print what would be done, do not save.",
        )

    def handle(self, *args, **options):
        dry_run = options.get("dry_run", False)
        pending = Release.objects.filter(approval_status__iexact="pending_approval")
        updated = 0
        errors = []

        for release in pending:
            changed = False
            if not release.upc:
                upc_to_assign = UniqueCode.objects.filter(type=UniqueCode.TYPE.UPC, assigned=False).first()
                if not upc_to_assign:
                    errors.append(f"No UPC available for {release.title} ({release.pk})")
                    continue
                if not dry_run:
                    release.upc = normalize_upc_to_13(upc_to_assign.code) or upc_to_assign.code
                    upc_to_assign.assigned = True
                    upc_to_assign.save()
                    release.save(update_fields=["upc"])
                self.stdout.write(f"  Assigned UPC to {release.title}")
                changed = True

            for track in Track.objects.filter(release=release):
                if not track.isrc:
                    isrc_to_assign = UniqueCode.objects.filter(type=UniqueCode.TYPE.ISRC, assigned=False).first()
                    if not isrc_to_assign:
                        errors.append(f"No ISRC available for track '{track.title}' in {release.title}")
                        continue
                    if not dry_run:
                        track.isrc = isrc_to_assign.code
                        isrc_to_assign.assigned = True
                        track.save()
                        isrc_to_assign.save()
                    self.stdout.write(f"  Assigned ISRC to track '{track.title}' in {release.title}")
                    changed = True

            if changed:
                updated += 1

        if errors:
            for e in errors:
                self.stderr.write(self.style.ERROR(e))
        self.stdout.write(self.style.SUCCESS(f"Done. Updated {updated} release(s)."))
        if dry_run:
            self.stdout.write(self.style.WARNING("Dry run: no changes were saved."))
