#!/usr/bin/env python3
"""
Run this once if the app can't find your usage data:

    python discover.py

It prints every claude.ai API endpoint that returns JSON, along with the first
400 characters of each response, so you can identify the right one and update
scraper.py accordingly.

The browser used for cookie extraction is read from the same config file the
main app uses (~/.config/claude-ticker/config.json, key: "browser"). Override
it for a single run with the CLAUDE_TICKER_BROWSER environment variable:

    CLAUDE_TICKER_BROWSER=firefox python discover.py
"""

import json
import os
import sys

import browser_cookie3
import requests

from config import SUPPORTED_BROWSERS, get_browser

BASE = "https://claude.ai"

CANDIDATES = [
    "/api/auth/session",
    "/api/bootstrap",
    "/api/account",
    "/api/usage_limits",
    "/api/usage",
    "/api/account/usage",
    "/api/account/usage_limits",
    "/api/billing/usage_limits",
    "/api/billing/usage",
    "/api/plan",
    "/api/account/plan",
]

_BROWSER_FN = {
    "chrome": browser_cookie3.chrome,
    "chromium": browser_cookie3.chromium,
    "brave": browser_cookie3.brave,
    "firefox": browser_cookie3.firefox,
    "safari": browser_cookie3.safari,
    "edge": browser_cookie3.edge,
}


def main() -> None:
    # Allow one-shot browser override via env var
    browser = os.environ.get("CLAUDE_TICKER_BROWSER", "").lower() or get_browser()
    if browser not in SUPPORTED_BROWSERS:
        print(
            f"Unknown browser '{browser}'. "
            f"Supported: {', '.join(sorted(SUPPORTED_BROWSERS))}"
        )
        sys.exit(1)

    print(f"Using browser: {browser}")
    print("Grabbing cookies for claude.ai…")
    try:
        fn = _BROWSER_FN[browser]
        cookies = fn(domain_name=".claude.ai")
    except Exception as e:
        print(f"ERROR reading cookies: {e}")
        sys.exit(1)

    s = requests.Session()
    s.cookies = cookies
    s.headers["User-Agent"] = (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
    s.headers["Accept"] = "application/json, */*"
    s.headers["Referer"] = f"{BASE}/settings"

    # Check auth via bootstrap (works even when /api/auth/session returns 404)
    r = s.get(f"{BASE}/api/bootstrap", timeout=10)
    print(f"\nBootstrap check → HTTP {r.status_code}")
    if not r.ok:
        print("Could not reach /api/bootstrap - are you logged in to claude.ai?")
        sys.exit(1)

    try:
        data = r.json()
        print("Account keys:", list(data.get("account", {}).keys()))
        for m in data.get("account", {}).get("memberships", []):
            org = m.get("organization") or {}
            oid = org.get("uuid")
            if oid:
                print(f"  org_uuid = {oid}")
                CANDIDATES.insert(0, f"/api/organizations/{oid}/usage_limits")
                CANDIDATES.insert(1, f"/api/organizations/{oid}/usage")
                CANDIDATES.insert(2, f"/api/organizations/{oid}/limits")
    except Exception:
        pass

    print("\n── Probing endpoints ──────────────────────────────────────────")
    for path in CANDIDATES:
        try:
            r = s.get(f"{BASE}{path}", timeout=10)
            ct = r.headers.get("content-type", "")
            marker = "✓ JSON" if (r.ok and "json" in ct) else f"  {r.status_code}"
            print(f"{marker}  {path}")
            if r.ok and "json" in ct:
                snippet = json.dumps(r.json(), indent=2)[:400]
                for line in snippet.splitlines():
                    print(f"      {line}")
        except Exception as e:
            print(f"  ERR  {path}  ({e})")

    print("\nDone. Share the output above to help update scraper.py.")


if __name__ == "__main__":
    main()
