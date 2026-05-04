# Claude Ticker

[![CI](https://github.com/bestori/claude-ticker/actions/workflows/lint.yml/badge.svg)](https://github.com/bestori/claude-ticker/actions/workflows/lint.yml)

> [!WARNING]
> **Unofficial side project - not affiliated with or endorsed by Anthropic.**
> This uses [claude.ai](https://claude.ai)'s internal, undocumented API. It may break at any time.
> The app will show `Claude ⚠` if something changes on Anthropic's end.

---

## Why do you need *yet another ticker*?

Another inevitable Claude session... and you suddenly hit a rate limit.  
Sounds familiar?...  
You know there are usage limits.  
What bugged me was that the only way to check how much runway I had left was to open a browser, navigate to **Settings → Usage**, and **read a progress bar**.

That page looks like this:

![Claude.ai Settings → Usage page showing session and weekly limits](docs/screenshots/claude-settings-before.png)

It's genuinely useful information - a 5-hour rolling session window and a 7-day weekly cap, both shown as percentages with reset times. But it lives buried in a settings page. I found myself checking it constantly, tabbing away from whatever I was doing, and then tabbing back.

So I thought: this is exactly the kind of thing a menu bar ticker is for. Bitcoin prices live up there. My internet speed lives up there. Why not my Claude usage?

Shortly after, I had a Python script scraping the page. Then - a proper macOS `.app` with a graphical popover. This is that app.

---

## What it does

A tiny item lives permanently in your menu bar (macOS) or system tray (Windows):

![Claude Ticker in the macOS menu bar](docs/screenshots/menubar.png)

- `S:XX%` - how much of your **session** window is still available
- `W:XX%` - how much of your **weekly** limit is still available
- `XXm / XhXXm` - time until your current session resets

Click it and you get a proper graphical popup:

![Claude Ticker popover with arc rings](docs/screenshots/popover.png)

Two cards with animated SVG arc rings, one for each limit window. The rings fill clockwise and change colour as usage climbs:

| Usage | Ring colour |
|-------|------------|
| 0 – 59% | Green |
| 60 – 84% | Orange |
| 85 – 100% | Red |

Fully dark-mode aware. Refreshes every 120 seconds on its own, or on demand via the Refresh button. Use the **A− / A+** buttons to scale the popup to your taste.

**[PRs, issues, and contributions welcome!](https://github.com/bestori/claude-ticker)**

---

## How it actually works

No API key required. No Anthropic SDK. It does exactly what your browser does when you open that settings page - it reads your existing browser session cookie and makes the same internal API call the web UI makes.

The two calls it makes every refresh:

```
GET /api/bootstrap          → your org UUID
GET /api/organizations/{uuid}/usage  → the usage numbers
```

The response from that second call is what feeds the whole thing:

```json
{
  "five_hour": {
    "utilization": 63.0,
    "resets_at": "2026-03-29T18:00:00+00:00"
  },
  "seven_day": {
    "utilization": 70.0,
    "resets_at": "2026-04-01T00:00:00+00:00"
  }
}
```

The `utilization` is percent used. The `resets_at` gives the countdown.

On first launch, macOS will ask for **Keychain access** - that's the app asking permission to decrypt Chrome's stored cookies. Allow it. Nothing is stored or sent anywhere else.

---

## Quick start

### macOS

```bash
pip3 install -r requirements.txt   # install deps
./build.sh                         # build ClaudeTicker.app
cp -r dist/ClaudeTicker.app /Applications/
open /Applications/ClaudeTicker.app
```

> First launch: right-click → Open (macOS Gatekeeper). After that, launch normally.  
> Auto-start: System Settings → General → Login Items → `+` → pick `ClaudeTicker.app`.

### Windows

```bat
pip install -r requirements-windows.txt
pyinstaller app_windows.py --onefile --windowed --name ClaudeTicker
dist\ClaudeTicker.exe
```

> Popup appears bottom-right, above the taskbar. Left-click tray icon to show/hide. Right-click for Quit.  
> Auto-start: add shortcut to `ClaudeTicker.exe` in `shell:startup`.

---

## Requirements

### macOS
- macOS 13 Ventura or later (tested on macOS 15 Sequoia)
- Python 3.11+
- Chrome, Firefox, Safari, Brave, or Edge with an active [claude.ai](https://claude.ai) login

### Windows
- Windows 10 or later (WebView2 runtime required — pre-installed on Win10/11)
- Python 3.11+
- Chrome, Firefox, Brave, or Edge with an active [claude.ai](https://claude.ai) login

### Both
- A [Claude.ai](https://claude.ai) paid plan (Pro, Team, or Max — free tier doesn't expose these limits)

---

## Browser configuration

Chrome by default. To use something else, create `~/.config/claude-ticker/config.json`:

```json
{ "browser": "firefox" }
```

Valid values: `chrome`, `chromium`, `brave`, `firefox`, `safari` (macOS only), `edge`.
Changes take effect on the next refresh - no restart needed.

---

## Running in dev mode (no build)

### macOS
```bash
python3 app.py
```

### Windows
```bat
python app_windows.py
```

To test just the data fetching on either platform:

```bash
python3 -c "
from scraper import fetch_usage, session_minutes_remaining, weekly_reset_local_str
d = fetch_usage()
print(f'Session: {d.session_pct_used:.0f}% used | resets in {session_minutes_remaining(d):.0f}m')
print(f'Weekly:  {d.weekly_pct_used:.0f}% used | resets {weekly_reset_local_str(d)}')
"
```

---

## Troubleshooting

| Symptom | Most likely cause | Fix |
|---------|------------------|-----|
| `Claude ⚠` in menu bar | Cookie expired or not logged in | Log out and back into [claude.ai](https://claude.ai) in Chrome |
| `Could not find org UUID` | `/api/bootstrap` changed | Run `python3 discover.py` |
| `Claude ⚠` after an Anthropic update | API endpoint or response shape changed | Run `python3 discover.py` and open an issue |
| Keychain prompt denied (macOS) | Denied on first run | System Settings → Privacy & Security → Keychain Access |
| Shows `…` forever | First fetch still in progress | Wait 30s; if stuck, quit and restart |
| Popup doesn't appear (Windows) | WebView2 not installed | Install [Microsoft Edge WebView2](https://developer.microsoft.com/en-us/microsoft-edge/webview2/) |

If the API has moved, `discover.py` will probe a list of candidate endpoints and show you exactly what comes back:

```bash
python3 discover.py
# or for a specific browser:
CLAUDE_TICKER_BROWSER=firefox python3 discover.py
```

---

## Project structure

```
claude-ticker/
├── app.py                macOS UI — NSStatusItem, NSPopover, WKWebView, NSTimer
├── app_windows.py        Windows UI — pystray tray icon, pywebview floating window
├── ui_shared.py          Shared HTML/CSS/JS popup + _fmt() helper (both platforms)
├── scraper.py            All HTTP — cookie extraction, API calls, reset arithmetic
├── config.py             Browser selection via ~/.config/claude-ticker/config.json
├── discover.py           One-shot endpoint probe (run when the scraper breaks)
├── setup.py              py2app bundle config (macOS)
├── build.sh              macOS build + sign in one step
├── requirements.txt      macOS runtime deps
├── requirements-windows.txt  Windows runtime deps (pystray, pywebview, pillow)
├── requirements-dev.txt  Test/lint deps (pytest, ruff)
├── pyproject.toml        Ruff + pytest config
├── tests/
│   ├── test_scraper.py   Unit tests for scraper.py (fully mocked)
│   └── test_config.py    Unit tests for config.py
└── .github/workflows/lint.yml  CI (ruff + pytest, macos-latest)
```

---

## Running the tests

No live Claude session needed - everything is mocked.

```bash
pip install -r requirements-dev.txt
pytest tests/ -v
```

---

## Under the hood

**Why PyObjC on macOS and not something like `rumps`?**
`rumps` wraps standard `NSMenu` dropdowns - text only. The graphical popover with arc rings needs `NSPopover` + `WKWebView`, which requires direct AppKit/WebKit bindings. PyObjC gives you the full Cocoa API from Python.

**Why pystray + pywebview on Windows?**
The popup HTML/CSS/JS is already a self-contained page — pywebview renders it in an Edge WebView2 window. pystray handles the system tray icon. Together they're a thin wrapper around the same UI, with no Electron or Node.js involved.

**How does the same HTML work on both platforms?**
The JS bridge uses a `_post()` function that detects the host at runtime: on macOS it routes through `window.webkit.messageHandlers`; on Windows through `window.pywebview.api`. The HTML lives in `ui_shared.py` and is imported by both `app.py` and `app_windows.py`.

**Thread model:**
The UI runs on the main thread (NSRunLoop on macOS, pywebview event loop on Windows). All network I/O happens on daemon background threads. A non-blocking `threading.Lock` prevents concurrent fetches.

---

## Privacy

- Cookies are read locally from your browser's on-disk profile - no browser extension involved.
- They're used only to authenticate the two API calls per refresh cycle.
- Nothing is logged, stored, or sent anywhere else. No analytics, no telemetry.
