"""
Diagnose Sonosuite credentials. Run: python manage.py sonosuite_check

Shows whether SONOSUITE_* vars are set and where .env is being loaded from.
"""
import os
from pathlib import Path

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Check if Sonosuite credentials (SONOSUITE_*) are configured. Use to debug 'Delivery is not configured'."

    def handle(self, *args, **options):
        # Paths that might contain .env (this file: releases/management/commands/sonosuite_check.py)
        base_dir = Path(__file__).resolve().parent.parent.parent  # RoyaltyWebsite
        app_root = base_dir.parent  # django-docker-compose or parent of RoyaltyWebsite
        paths_to_check = [
            Path("/app/.env"),
            app_root / ".env",
            app_root / "coin.env",
            base_dir / ".env",
            base_dir / "coin.env",
            Path.home() / ".env",
        ]

        self.stdout.write("=== Sonosuite credential check ===\n")

        email = os.getenv("SONOSUITE_ADMIN_EMAIL", "")
        password = os.getenv("SONOSUITE_ADMIN_PASSWORD", "")
        base_url = os.getenv("SONOSUITE_API_BASE_URL", "")

        self.stdout.write(f"SONOSUITE_ADMIN_EMAIL: {'SET (' + email[:3] + '***)' if email else 'MISSING'}")
        self.stdout.write(f"SONOSUITE_ADMIN_PASSWORD: {'SET (****)' if password else 'MISSING'}")
        self.stdout.write(f"SONOSUITE_API_BASE_URL: {base_url or '(empty, will use default)'}\n")

        if email and password:
            self.stdout.write(self.style.SUCCESS("Configured: YES - Approve/Delivery should work."))
        else:
            self.stdout.write(self.style.ERROR("Configured: NO - Add credentials to .env and restart the app."))

        self.stdout.write("\nPaths checked for .env / coin.env:")
        for p in paths_to_check:
            exists = p.exists()
            self.stdout.write(f"  {'[EXISTS]' if exists else '[not found]'} {p}")

        self.stdout.write(f"\nCurrent working directory: {os.getcwd()}")
