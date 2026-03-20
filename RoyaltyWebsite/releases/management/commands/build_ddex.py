"""
Generate DDEX ERN 4.3 XML for a release (Insert, Update, or Takedown).
Supports Single, EP, and Album. We use 4.3 for all DSPs.
Run: python manage.py build_ddex 123
     python manage.py build_ddex 123 --action update --original-message-id <message_id>
     python manage.py build_ddex 123 --action takedown --takedown-reason ArtistRequest
     python manage.py build_ddex 123 --store jiosaavn --test
DSP codes: releases/data/ddex_dsps.json.
"""
import os
from django.core.management.base import BaseCommand
from releases.models import Release
from releases.ddex_builder import build_new_release_message, build_takedown_message
from releases.ddex_dsp_registry import get_dsp


class Command(BaseCommand):
    help = (
        "Generate DDEX ERN 4.3 XML: Insert (default), Update, or Takedown for Single/EP/Album. "
        "Use --store <dsp_code>. DSP list: releases/data/ddex_dsps.json."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "release_id",
            nargs="?",
            type=int,
            help="Release ID (primary key)",
        )
        parser.add_argument(
            "--upc",
            type=str,
            help="Release UPC (alternative to release_id)",
        )
        parser.add_argument(
            "--action",
            type=str,
            default="insert",
            choices=["insert", "update", "takedown"],
            help="Message type: insert (default), update, or takedown.",
        )
        parser.add_argument(
            "--store",
            type=str,
            default="spotify",
            help="DSP code from registry (e.g. spotify, tiktok, jiosaavn). Default: spotify.",
        )
        parser.add_argument(
            "--original-message-id",
            type=str,
            help="Required for --action update: MessageId of the original Insert message.",
        )
        parser.add_argument(
            "--takedown-reason",
            type=str,
            help="Optional for --action takedown (e.g. RightsIssue, ArtistRequest, ContractExpiry, Other).",
        )
        parser.add_argument(
            "--takedown-end-date",
            type=str,
            help="For --action takedown --store audiomack: EndDate YYYY-MM-DD (default: today). Ignored for other stores.",
        )
        parser.add_argument(
            "--output",
            "-o",
            type=str,
            help="Output file path. If omitted, prints to stdout.",
        )
        parser.add_argument(
            "--test",
            action="store_true",
            help="Use MessageControlType TestMessage (e.g. JioSaavn testing). Only for insert.",
        )
        parser.add_argument(
            "--verbose",
            action="store_true",
            help="Print release info before generating.",
        )

    def handle(self, *args, **options):
        release_id = options.get("release_id")
        upc = options.get("upc")
        action = (options.get("action") or "insert").strip().lower()
        output_path = options.get("output")
        store = options.get("store", "spotify")
        original_message_id = options.get("original_message_id")
        takedown_reason = options.get("takedown_reason")
        takedown_end_date = options.get("takedown_end_date")
        use_test_message = options.get("test", False)
        verbose = options.get("verbose", False)

        if not release_id and not upc:
            self.stderr.write(
                self.style.ERROR(
                    "Provide either release_id or --upc. "
                    "Example: python manage.py build_ddex 123  OR  python manage.py build_ddex --upc 8905285299663"
                )
            )
            return

        if action == "update" and not original_message_id:
            self.stderr.write(
                self.style.ERROR("For --action update you must provide --original-message-id (MessageId of the original Insert).")
            )
            return

        try:
            if release_id:
                release = Release.objects.get(id=release_id)
            else:
                release = Release.objects.get(upc=upc.strip())
        except Release.DoesNotExist:
            self.stderr.write(self.style.ERROR(f"Release not found (id={release_id or 'N/A'}, upc={upc or 'N/A'})"))
            return

        dsp = get_dsp(store)
        if dsp is None and verbose:
            self.stdout.write(self.style.WARNING(f"DSP '{store}' not in registry; using fallback if known."))

        if verbose:
            self.stdout.write(f"Release: {release.title} (ID={release.id}, UPC={release.upc})")
            self.stdout.write(f"Album format: {release.album_format} (Single/EP/Album supported)")
            self.stdout.write(f"Tracks: {release.track_set.count()}")
            self.stdout.write(f"Store: {store} (ERN 4.3)")
            self.stdout.write(f"Action: {action}")
            if action == "insert":
                self.stdout.write(f"MessageControlType: {'TestMessage' if use_test_message else 'LiveMessage'}")
            elif action == "update":
                self.stdout.write(f"LinkedMessageId: {original_message_id}")
            elif action == "takedown":
                if takedown_reason:
                    self.stdout.write(f"TakedownReason: {takedown_reason}")
                if (store or "").strip().lower() == "audiomack" and takedown_end_date:
                    self.stdout.write(f"TakedownEndDate (Audiomack): {takedown_end_date}")
            self.stdout.write("")

        if action == "takedown" and (store or "").strip().lower() == "audiomack":
            # Audiomack sample: NewReleaseMessage with UpdateMessage + ValidityPeriod EndDate (not PurgeReleaseMessage)
            from datetime import datetime, timezone
            end_date = (takedown_end_date or "").strip() or datetime.now(timezone.utc).strftime("%Y-%m-%d")
            xml = build_new_release_message(
                release,
                store=store,
                message_control_type="UpdateMessage",
                takedown_end_date=end_date,
            )
        elif action == "takedown":
            xml = build_takedown_message(
                release, store=store, takedown_reason=takedown_reason
            )
        else:
            message_control_type = "TestMessage" if use_test_message else ("UpdateMessage" if action == "update" else "LiveMessage")
            xml = build_new_release_message(
                release,
                store=store,
                message_control_type=message_control_type,
                linked_message_id=original_message_id if action == "update" else None,
            )

        if output_path:
            out_dir = os.path.dirname(output_path)
            if out_dir and not os.path.exists(out_dir):
                os.makedirs(out_dir, exist_ok=True)
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(xml)
            self.stdout.write(self.style.SUCCESS(f"DDEX XML written to {output_path}"))
        else:
            self.stdout.write(xml)
