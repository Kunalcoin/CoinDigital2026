"""
Set releases (by UPC) to Pending for Approval so they appear in the Pending for Approval
list and admins can approve them (and send to Sonosuite) in one go.

Run:
  python manage.py set_pending_approval 8905285299755 8905285299816 ...
  python manage.py set_pending_approval --file upcs.txt
"""
from django.core.management.base import BaseCommand

from releases.models import Release
from releases.upc_utils import find_release_by_upc


# Approval status used by the workflow
PENDING_APPROVAL = "pending_approval"


class Command(BaseCommand):
    help = (
        "Set releases with the given UPCs to Pending for Approval. "
        "They will appear in the Pending for Approval section; admin can then approve them."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "upcs",
            nargs="*",
            type=str,
            help="UPCs of releases to set to pending approval (or use --file)",
        )
        parser.add_argument(
            "--file",
            type=str,
            default=None,
            help="Path to a file with one UPC per line (optional).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Only print what would be updated, do not save.",
        )

    def handle(self, *args, **options):
        upcs = list(options.get("upcs") or [])
        file_path = options.get("file")
        dry_run = options.get("dry_run", False)

        if file_path:
            try:
                with open(file_path, "r") as f:
                    for line in f:
                        u = (line or "").strip()
                        if u and not u.startswith("#"):
                            upcs.append(u)
            except FileNotFoundError:
                self.stderr.write(self.style.ERROR(f"File not found: {file_path}"))
                return
            except Exception as e:
                self.stderr.write(self.style.ERROR(f"Error reading file: {e}"))
                return

        upcs = [u.strip() for u in upcs if (u or "").strip()]
        if not upcs:
            self.stderr.write(
                self.style.ERROR("Provide UPCs as arguments or use --file <path>.")
            )
            return

        self.stdout.write(f"Looking up {len(upcs)} UPC(s)...")
        updated = 0
        not_found = []
        for upc in upcs:
            release = find_release_by_upc(upc, Release)
            if release is None:
                not_found.append(upc)
                continue
            if dry_run:
                self.stdout.write(
                    self.style.WARNING(
                        f"  [dry-run] Would set {upc} ({release.title}) to pending_approval, published=False"
                    )
                )
                updated += 1
                continue
            release.approval_status = PENDING_APPROVAL
            release.published = False
            release.published_at = None
            release.save(update_fields=["approval_status", "published", "published_at"])
            self.stdout.write(
                self.style.SUCCESS(f"  Set {upc} ({release.title}) to Pending for Approval")
            )
            updated += 1

        if not_found:
            self.stdout.write(
                self.style.WARNING(f"UPC(s) not found ({len(not_found)}): {', '.join(not_found)}")
            )
        self.stdout.write(
            self.style.SUCCESS(f"Done. {updated} release(s) set to Pending for Approval.")
        )
        if dry_run:
            self.stdout.write(self.style.WARNING("Dry run: no changes were saved."))
