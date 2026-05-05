# CLAUDE.md

> This file is read automatically by [Claude Code](https://claude.ai/code).
> It documents project architecture and non-obvious implementation decisions.

## What this project is

A macOS menu bar / Windows system tray app that shows Claude.ai plan usage (session + weekly) with a countdown to reset. It pulls live data from a browser's session cookies → claude.ai internal API, and refreshes every 120 seconds.

Menu bar: `Claude  S:37%  W:26%  |  13m`
Click → popup with animated SVG arc rings, colour-coded by pressure level, and reset countdowns for both windows.

## Commands

```bash
# Install runtime dependencies (macOS)
pip3 install -r requirements-macos.txt

# Install runtime dependencies (Windows)
pip install -r requirements-windows.txt

# Install dev/test dependencies (any platform, no PyObjC needed)
pip3 install -r requirements-dev.txt

# Run directly - macOS
python3 app.py

# Run directly - Windows
python app_windows.py

# Test the scraper alone
python3 -c "from scraper import fetch_usage, session_minutes_remaining, weekly_reset_local_str; d = fetch_usage(); print(d)"

# If the scraper stops working, probe for the API endpoint
python3 discover.py

# Run unit tests
pytest tests/ -v

# Lint
ruff check .
ruff format --check .

# Build the .app bundle (macOS)
python3 setup.py py2app
codesign --force --deep --sign - dist/ClaudeTicker.app

# Build the .exe (Windows)
pyinstaller app_windows.py --onefile --windowed --name ClaudeTicker

# Install system-wide (macOS)
cp -r dist/ClaudeTicker.app /Applications/
```

## Architecture

```
ui_shared.py         Shared HTML/CSS/JS popup + _fmt() helper
                     Imported by both app.py and app_windows.py
app.py               macOS only: PyObjC NSApplication delegate - status bar item,
                     NSPopover with WKWebView, NSTimer refresh loop, JS↔Python bridge
app_windows.py       Windows only: pystray tray icon + pywebview floating window,
                     positioned bottom-right above taskbar, same HTML as macOS
scraper.py           All HTTP logic - cookie extraction, bootstrap call,
                     usage API call, reset-time arithmetic (cross-platform)
config.py            Reads ~/.config/claude-ticker/config.json for browser selection
discover.py          One-shot helper to probe API endpoints (run when scraper breaks)
setup.py             py2app config - produces dist/ClaudeTicker.app (macOS only)
tests/               Unit tests for scraper.py and config.py (no network I/O)
```

**Data flow:**
1. `browser_cookie3.<browser>(domain_name=".claude.ai")` - browser chosen via `config.get_browser()`
2. `GET /api/bootstrap` → all org UUIDs (account may have multiple)
3. `GET /api/organizations/{org_uuid}/usage` → tried for each UUID; first 200 wins
4. JSON with `five_hour` (session) and `seven_day` (weekly) keys
5. `utilization` field = % used (0–100); `resets_at` = ISO UTC datetime

**Key detail - multiple org UUIDs:** The bootstrap endpoint returns multiple org memberships. Some return 403 on the usage endpoint. `fetch_usage()` tries all UUIDs in order and uses the first that returns 200.

**Key detail - `resets_at` handling:** The API sometimes returns a timestamp already in the past. `_next_reset()` in `scraper.py` advances it by the window size until it's future.

**Key detail - `@objc.python_method`:** PyObjC registers all methods on NSObject subclasses as ObjC selectors. Private helper methods with extra arguments (e.g. `_apply(self, title, payload)`) must be decorated with `@objc.python_method` to prevent registration failures.

**Key detail - browser dispatch:** `scraper._make_session()` uses `getattr(browser_cookie3, browser)` (not a pre-built dict) so that `browser_cookie3` can be mocked cleanly in tests.

**Key detail - JS bridge:** The popup HTML uses `_post(name, val)` which detects the host at runtime: `window.webkit.messageHandlers` on macOS, `window.pywebview.api` on Windows. All UI changes must go in `ui_shared.py`.

**Key detail - strftime on Windows:** `%-I` (remove leading zero from hour) is macOS/Linux only. `scraper.weekly_reset_local_str()` uses `%#I` on Windows and `%-I` elsewhere via `platform.system()`.

## Dependencies

### macOS
| Package | Purpose |
|---|---|
| `browser-cookie3` | Decrypt browser cookies from macOS Keychain |
| `pycryptodome` | Required by browser-cookie3 for AES decryption |
| `certifi` | CA bundle — explicit path avoids py2app bundling issues |
| `pyobjc-framework-Cocoa` | NSStatusBar, NSPopover, NSTimer, AppKit bindings |
| `pyobjc-framework-WebKit` | WKWebView bindings |
| `py2app` | Bundle into a `.app` (build-time only) |

### Windows
| Package | Purpose |
|---|---|
| `browser-cookie3` | Decrypt browser cookies |
| `pycryptodome` | Required by browser-cookie3 for AES decryption |
| `certifi` | CA bundle |
| `pystray` | System tray icon |
| `pywebview` | Floating popup window via Edge WebView2 |
| `pillow` | Tray icon image generation |
| `pyinstaller` | Bundle into a `.exe` (build-time only) |

### Both
| Package | Purpose |
|---|---|
| `ruff` | Linter + formatter (dev only) |
| `pytest` | Test runner (dev only) |

## macOS permissions

On first run macOS will prompt for Keychain access (to decrypt browser cookies). Allow it. If denied, browser-cookie3 will fail silently and `fetch_usage()` will raise a RuntimeError shown in the menu bar as `Claude ⚠`.
