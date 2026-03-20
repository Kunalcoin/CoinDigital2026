"""
List contents of Merlin Bridge SFTP so we can see where files land and what Bridge might be scanning.
Use this when deliveries don't show up in the Bridge dashboard.

Run from RoyaltyWebsite with env loaded (e.g. source coin.env):
  python manage.py list_merlin_bridge_sftp
"""
import os
from django.core.management.base import BaseCommand

from releases.merlin_bridge_delivery import open_merlin_bridge_sftp


class Command(BaseCommand):
    help = (
        "List Merlin Bridge SFTP directories to verify connection and see where packages are. "
        "Use when deliveries don't show in Bridge."
    )

    def handle(self, *args, **options):
        base_path = (os.getenv("MERLIN_BRIDGE_SFTP_REMOTE_PATH") or "").strip().rstrip("/")
        self.stdout.write(f"MERLIN_BRIDGE_SFTP_REMOTE_PATH = {repr(base_path) or '(not set - uploads go to SFTP home)'}")
        self.stdout.write("")

        sftp, transport, err = open_merlin_bridge_sftp()
        if err:
            self.stderr.write(self.style.ERROR(f"Cannot connect: {err}"))
            return

        try:
            paths_to_list = [".", "apple", "apple/regular", "incoming"]
            if base_path and base_path not in paths_to_list:
                paths_to_list.append(base_path)
            # List takedown subfolder if we use apple/regular (where we upload PurgeRelease XML)
            if base_path and base_path.strip():
                paths_to_list.append(f"{base_path}/takedown")

            for path in paths_to_list:
                try:
                    attrs = sftp.listdir_attr(path)
                    self.stdout.write(self.style.SUCCESS(f"  {path or '.'}/  ({len(attrs)} items)"))
                    for a in sorted(attrs, key=lambda x: x.filename):
                        size = f"{a.st_size:,} bytes" if a.st_size else "-"
                        self.stdout.write(f"    {a.filename}  {size}")
                except FileNotFoundError:
                    self.stdout.write(self.style.WARNING(f"  {path or '.'}/  (does not exist)"))
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f"  {path or '.'}/  error: {e}"))
                self.stdout.write("")

            self.stdout.write("If apple/regular/ exists and has your .zip/.itmsp files but Bridge shows nothing,")
            self.stdout.write("ask Merlin: which exact path does Bridge scan for Apple Music packages?")
        finally:
            transport.close()
