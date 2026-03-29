# CLAUDE.md

> This file is read automatically by [Claude Code](https://claude.ai/code).
> It documents project architecture and non-obvious implementation decisions.

## What this project is

A macOS menu bar app that shows Claude.ai plan usage (session + weekly) with a countdown to reset. It pulls live data from a browser's session cookies → claude.ai internal API, and refreshes every 120 seconds.

Menu bar: `Claude  S:37%  W:26%  |  13m`
Click → NSPopover with animated SVG arc rings, colour-coded by pressure level, and reset countdowns for both windows.

## Commands

```bash
# Install runtime dependencies
pip3 install -r requirements.txt

# Install dev/test dependencies (no PyObjC needed)
pip3 install -r requirements-dev.txt

# Run directly (no .app, for dev/testing)
python3 app.py

# Test the scraper alone
python3 -c "from scraper import fetch_usage, session_minutes_remaining, weekly_reset_local_str; d = fetch_usage(); print(d)"

# If the scraper stops working, probe for the API endpoint
python3 discover.py

# Run unit tests
pytest tests/ -v

# Lint
ruff check .
ruff format --check .

# Build the .app bundle
python3 setup.py py2app
codesign --force --deep --sign - dist/ClaudeTicker.app

# Install system-wide
cp -r dist/ClaudeTicker.app /Applications/
```

## Architecture

```
app.py               PyObjC NSApplication delegate - status bar item, NSPopover
                     with WKWebView, NSTimer refresh loop, JS↔Python bridge
scraper.py           All HTTP logic - cookie extraction, bootstrap call,
                     usage API call, reset-time arithmetic
config.py            Reads ~/.config/claude-ticker/config.json for browser selection
discover.py          One-shot helper to probe API endpoints (run when scraper breaks)
setup.py             py2app config - produces dist/ClaudeTicker.app
tests/               Unit tests for scraper.py and config.py (no network I/O)
```

**Data flow:**
1. `browser_cookie3.<browser>(domain_name=".claude.ai")` - browser chosen via `config.get_browser()`
2. `GET /api/bootstrap` → org UUID
3. `GET /api/organizations/{org_uuid}/usage` → JSON with `five_hour` (session) and `seven_day` (weekly) keys
4. `utilization` field = % used (0–100); `resets_at` = ISO UTC datetime

**Key detail - `resets_at` handling:** The API sometimes returns a timestamp already in the past. `_next_reset()` in `scraper.py` advances it by the window size until it's future.

**Key detail - `@objc.python_method`:** PyObjC registers all methods on NSObject subclasses as ObjC selectors. Private helper methods with extra arguments (e.g. `_apply(self, title, payload)`) must be decorated with `@objc.python_method` to prevent registration failures.

**Key detail - browser dispatch:** `scraper._make_session()` uses `getattr(browser_cookie3, browser)` (not a pre-built dict) so that `browser_cookie3` can be mocked cleanly in tests.

## Dependencies

| Package | Purpose |
|---|---|
| `browser-cookie3` | Decrypt browser cookies from macOS Keychain |
| `pycryptodome` | Required by browser-cookie3 for AES decryption |
| `pyobjc-framework-Cocoa` | NSStatusBar, NSPopover, NSTimer, AppKit bindings |
| `pyobjc-framework-WebKit` | WKWebView bindings |
| `py2app` | Bundle into a `.app` (build-time only) |
| `ruff` | Linter + formatter (dev only) |
| `pytest` | Test runner (dev only) |

## macOS permissions

On first run macOS will prompt for Keychain access (to decrypt browser cookies). Allow it. If denied, browser-cookie3 will fail silently and `fetch_usage()` will raise a RuntimeError shown in the menu bar as `Claude ⚠`.
