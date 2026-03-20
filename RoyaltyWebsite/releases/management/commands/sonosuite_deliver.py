"""
Trigger Sonosuite delivery for one or more UPCs (releases added in Sonosuite UI).
Run: python3 manage.py sonosuite_deliver 8905285299663
     python3 manage.py sonosuite_deliver 8905285299670 8905285299687 ...
     python3 manage.py sonosuite_deliver 8905285299670 8905285299687 [--dsp=spotify]
If --dsp is omitted, delivers to all DSPs returned by Sonosuite.
"""
from django.core.management.base import BaseCommand
from releases.sonosuite_client import (
    is_sonosuite_configured,
    send_release_to_sonosuite,
)


class Command(BaseCommand):
    help = (
        "Trigger Sonosuite delivery for one or more UPCs. "
        "Releases must already exist in Sonosuite (tracks/posters added via their UI). "
        "Uses SONOSUITE_API_BASE_URL, SONOSUITE_ADMIN_EMAIL, SONOSUITE_ADMIN_PASSWORD (e.g. in coin.env)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "upcs",
            nargs="+",
            type=str,
            help="One or more UPCs to deliver (e.g. 8905285299670 8905285299687)",
        )
        parser.add_argument(
            "--dsp",
            action="append",
            dest="dsp_codes",
            default=None,
            help="DSP code to deliver to (e.g. spotify). Can be repeated. If omitted, delivers to all DSPs.",
        )
        parser.add_argument(
            "--verbose",
            action="store_true",
            dest="verbose",
            help="Print full request/response and Sonosuite error bodies when delivery fails.",
        )

    def handle(self, *args, **options):
        raw = options.get("upcs") or []
        upcs = [u.strip() for u in raw if (u or "").strip()]
        if not upcs:
            self.stderr.write(self.style.ERROR("At least one UPC is required."))
            return

        if not is_sonosuite_configured():
            self.stderr.write(
                self.style.ERROR(
                    "Sonosuite not configured. Set in coin.env: "
                    "SONOSUITE_API_BASE_URL, SONOSUITE_ADMIN_EMAIL, SONOSUITE_ADMIN_PASSWORD"
                )
            )
            return

        dsp_codes = options.get("dsp_codes")
        verbose = options.get("verbose", False)
        self.stdout.write(f"Delivering {len(upcs)} UPC(s) via Sonosuite API")
        if dsp_codes:
            self.stdout.write(f"DSPs: {', '.join(dsp_codes)}")
        else:
            self.stdout.write("DSPs: all (from Sonosuite)")
        if verbose:
            self.stdout.write("Verbose: on (full errors will be shown)")
        self.stdout.write("")

        all_operation_ids = []
        failed = []
        for i, upc in enumerate(upcs, 1):
            self.stdout.write(f"[{i}/{len(upcs)}] UPC {upc} ...")
            result = send_release_to_sonosuite(upc=upc, dsp_codes=dsp_codes, verbose=verbose)
            if result.get("success"):
                op_ids = result.get("operation_ids", [])
                all_operation_ids.extend(op_ids)
                self.stdout.write(
                    self.style.SUCCESS(
                        f"  OK — Operation ID(s): {', '.join(op_ids) or 'none'}"
                    )
                )
            else:
                err = result.get("error", "Unknown error")
                failed.append((upc, err))
                self.stderr.write(self.style.ERROR(f"  Failed: {err}"))
                per_dsp = result.get("per_dsp_errors")
                if per_dsp:
                    for line in per_dsp:
                        self.stderr.write(self.style.WARNING(f"    {line}"))
            self.stdout.write("")

        self.stdout.write(self.style.HTTP_INFO("=== Summary ==="))
        self.stdout.write(f"  Delivered: {len(upcs) - len(failed)}/{len(upcs)}")
        if all_operation_ids:
            self.stdout.write(
                self.style.SUCCESS(f"  All operation IDs: {', '.join(all_operation_ids)}")
            )
        if failed:
            for upc, err in failed:
                self.stderr.write(self.style.ERROR(f"  {upc}: {err}"))
