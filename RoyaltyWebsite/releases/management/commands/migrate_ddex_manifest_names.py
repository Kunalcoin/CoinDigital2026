"""
Migrate existing DDEX packages from manifest.xml / manifest.json to <upc>.xml / <upc>.json.

Scans S3 under ddex/packages/<release_id>/<upc>/ for legacy manifest.xml (and manifest.json).
For each found, copies to <upc>.xml and <upc>.json so all packages use UPC-based filenames.

Run: python manage.py migrate_ddex_manifest_names
     python manage.py migrate_ddex_manifest_names --dry-run
     python manage.py migrate_ddex_manifest_names --delete-legacy   # remove manifest.xml/json after copy
"""
import logging
from django.core.management.base import BaseCommand

logger = logging.getLogger(__name__)


def _get_bucket():
    from releases.ddex_package import _get_our_bucket
    return _get_our_bucket()


def _list_package_prefixes_with_legacy_manifest(s3, bucket: str):
    """List all prefixes under ddex/packages/ that contain manifest.xml. Yields (prefix, upc)."""
    prefix_base = "ddex/packages/"
    paginator = s3.get_paginator("list_objects_v2")
    seen = set()
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix_base):
        for obj in page.get("Contents") or []:
            key = (obj.get("Key") or "").strip()
            if not key.endswith("manifest.xml"):
                continue
            # key is like ddex/packages/123/4567890123456/manifest.xml
            parts = key.rsplit("/", 2)
            if len(parts) < 3:
                continue
            prefix_with_slash = parts[0] + "/" + parts[1] + "/"
            upc = parts[1]
            if prefix_with_slash in seen:
                continue
            seen.add(prefix_with_slash)
            yield (prefix_with_slash, upc)


class Command(BaseCommand):
    help = "Migrate DDEX packages from manifest.xml/manifest.json to <upc>.xml/<upc>.json in S3."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Only list what would be done, do not copy or delete.",
        )
        parser.add_argument(
            "--delete-legacy",
            action="store_true",
            help="After copying, delete legacy manifest.xml and manifest.json.",
        )

    def handle(self, *args, **options):
        dry_run = options.get("dry_run", False)
        delete_legacy = options.get("delete_legacy", False)

        try:
            from releases.processor import processor
            s3 = processor.get_s3_client()
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"S3 client: {e}"))
            return

        bucket = _get_bucket()
        self.stdout.write(f"Bucket: {bucket}")
        self.stdout.write(f"Prefix: ddex/packages/")
        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN – no changes will be made."))
        self.stdout.write("")

        migrated = 0
        errors = []

        for prefix, upc in _list_package_prefixes_with_legacy_manifest(s3, bucket):
            xml_src = f"{prefix}manifest.xml"
            xml_dst = f"{prefix}{upc}.xml"
            json_src = f"{prefix}manifest.json"
            json_dst = f"{prefix}{upc}.json"

            # Copy XML
            try:
                s3.head_object(Bucket=bucket, Key=xml_src)
            except Exception:
                continue
            if not dry_run:
                try:
                    s3.copy_object(
                        Bucket=bucket,
                        Key=xml_dst,
                        CopySource={"Bucket": bucket, "Key": xml_src},
                    )
                    self.stdout.write(f"  Copied {xml_src} -> {xml_dst}")
                except Exception as e:
                    errors.append(f"{prefix}: xml copy {e}")
                    continue
            else:
                self.stdout.write(f"  Would copy {xml_src} -> {xml_dst}")

            # Copy JSON if present
            try:
                s3.head_object(Bucket=bucket, Key=json_src)
                if not dry_run:
                    s3.copy_object(
                        Bucket=bucket,
                        Key=json_dst,
                        CopySource={"Bucket": bucket, "Key": json_src},
                    )
                    self.stdout.write(f"  Copied {json_src} -> {json_dst}")
                else:
                    self.stdout.write(f"  Would copy {json_src} -> {json_dst}")
            except Exception:
                pass

            if not dry_run and delete_legacy:
                try:
                    s3.delete_object(Bucket=bucket, Key=xml_src)
                    self.stdout.write(f"  Deleted {xml_src}")
                except Exception as e:
                    errors.append(f"{prefix}: delete xml {e}")
                try:
                    s3.delete_object(Bucket=bucket, Key=json_src)
                    self.stdout.write(f"  Deleted {json_src}")
                except Exception:
                    pass

            migrated += 1

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS(f"Packages processed: {migrated}"))
        if errors:
            for err in errors[:10]:
                self.stdout.write(self.style.ERROR(err))
            if len(errors) > 10:
                self.stdout.write(self.style.ERROR(f"... and {len(errors) - 10} more errors"))
