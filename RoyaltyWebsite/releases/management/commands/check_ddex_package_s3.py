"""
List DDEX package files in S3 for a release. Use to verify package was stored on submit-for-approval.
Run: python manage.py check_ddex_package_s3 36562
     python manage.py check_ddex_package_s3 --release 36562
"""
from django.core.management.base import BaseCommand

from releases.ddex_package import _get_our_bucket, get_manifest_xml_key, get_package_s3_prefix, package_exists
from releases.models import Release


class Command(BaseCommand):
    help = "List DDEX package files in S3 for a release (by id or UPC)."

    def add_arguments(self, parser):
        parser.add_argument("release_id", nargs="?", type=str, help="Release ID (e.g. 36562)")
        parser.add_argument("--release", type=str, dest="release_id_opt", help="Release ID (alternative)")

    def handle(self, *args, **options):
        rid = options.get("release_id") or options.get("release_id_opt")
        if not rid:
            self.stdout.write(self.style.ERROR("Provide release ID: python manage.py check_ddex_package_s3 36562"))
            return
        try:
            release = Release.objects.get(pk=rid)
        except Release.DoesNotExist:
            self.stdout.write(self.style.ERROR(f"Release {rid} not found."))
            return

        bucket = _get_our_bucket()
        prefix = get_package_s3_prefix(release).rstrip("/") + "/"
        exists = package_exists(release)

        self.stdout.write(f"Release: {release.id}  Title: {release.title}")
        self.stdout.write(f"UPC: {getattr(release, 'upc', '') or '(none)'}")
        self.stdout.write(f"Bucket: {bucket}")
        self.stdout.write(f"Prefix: {prefix}")
        manifest_key = get_manifest_xml_key(release)
        self.stdout.write(f"Package exists ({manifest_key.split('/')[-1]}): {exists}")
        self.stdout.write("")

        try:
            from releases.processor import processor
            s3 = processor.get_s3_client()
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Cannot get S3 client: {e}"))
            return

        try:
            paginator = s3.get_paginator("list_objects_v2")
            count = 0
            for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
                for obj in page.get("Contents") or []:
                    key = obj.get("Key", "")
                    size = obj.get("Size", 0)
                    short_key = key.replace(prefix, "", 1) if key.startswith(prefix) else key
                    self.stdout.write(f"  {short_key}  ({size} bytes)")
                    count += 1
            if count == 0:
                self.stdout.write(self.style.WARNING("  (no objects found at this prefix)"))
            else:
                self.stdout.write("")
                self.stdout.write(self.style.SUCCESS(f"Total: {count} file(s)."))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"List failed: {e}"))
