#!/usr/bin/env python3
"""
Diagnose Sonosuite delivery: print full request and response for one UPC.
Run from RoyaltyWebsite with .env or coin.env (or API.env) loaded.

  python3 sonosuite_diagnose.py 8905285299670

This shows exactly what we send to Sonosuite and what they return.
"""
import json
import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))
os.chdir(BASE_DIR)

from dotenv import load_dotenv
load_dotenv(BASE_DIR / ".env", override=True)
load_dotenv(BASE_DIR / "API.env", override=True)
load_dotenv(BASE_DIR / "coin.env", override=True)

from releases.sonosuite_client import (
    get_sonosuite_config,
    is_sonosuite_configured,
    sonosuite_login,
    sonosuite_get_dsps,
    sonosuite_delivery,
)

def main():
    upc = (sys.argv[1] or "").strip() if len(sys.argv) > 1 else "8905285299670"
    print("=== Sonosuite delivery diagnostic ===\n")
    print("UPC:", upc)

    if not is_sonosuite_configured():
        print("ERROR: Sonosuite not configured. Set in .env or coin.env:")
        print("  SONOSUITE_API_BASE_URL  (e.g. https://coin.sonosuite.com)")
        print("  SONOSUITE_ADMIN_EMAIL")
        print("  SONOSUITE_ADMIN_PASSWORD")
        sys.exit(1)

    cfg = get_sonosuite_config()
    base_url = cfg["base_url"]
    print("Base URL:", base_url)
    print("Login email:", (cfg["admin_username"] or "")[:3] + "***")
    print()

    print("1. POST", base_url + "/distribution/api/login")
    token, err = sonosuite_login(cfg["admin_username"], cfg["admin_password"], base_url)
    if not token:
        print("   Login FAILED:", err)
        sys.exit(1)
    print("   Login OK (token received)\n")

    print("2. GET", base_url + "/distribution/api/dsp")
    dsps = sonosuite_get_dsps(token, base_url)
    if not dsps:
        print("   No DSPs returned. Check token and base URL.")
        sys.exit(1)
    print("   DSPs:", len(dsps))
    for d in dsps[:5]:
        print("     -", d.get("dsp_code"), d.get("dsp_name", ""))
    if len(dsps) > 5:
        print("     ... and", len(dsps) - 5, "more")
    dsp_code = dsps[0].get("dsp_code") if dsps else None
    if not dsp_code:
        print("   No dsp_code in response. Keys:", list(dsps[0].keys()) if dsps else [])
        sys.exit(1)
    print("   Using first DSP for test:", dsp_code, "\n")

    print("3. POST", base_url + "/distribution/api/delivery")
    payload = {"dsp_code": dsp_code, "upcs": [upc], "deliver_taken_down": False}
    print("   Request body:", json.dumps(payload, indent=2))
    result = sonosuite_delivery(token, dsp_code, [upc], base_url, verbose=False)
    print()
    print("   Response:")
    print("   - success:", result.get("success"))
    print("   - operation_id:", result.get("operation_id"))
    if result.get("error"):
        print("   - error:", result.get("error"))
    if result.get("raw_response"):
        print("   - raw_response:", result["raw_response"][:500])
    print()
    if result.get("success"):
        print("SUCCESS: Delivery accepted. Check Sonosuite UI for operation / exports.")
    else:
        print("FAILED: Sonosuite rejected the delivery. Fix the error above.")
    sys.exit(0 if result.get("success") else 1)


if __name__ == "__main__":
    main()
