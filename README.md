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

A tiny item lives permanently in your macOS menu bar:

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

Fully dark-mode aware. Refreshes every 120 seconds on its own, or on demand via the Refresh button.  

**Note: macOS only. [PRs, issues, and contributions welcome!](https://github.com/bestori/claude-ticker)**

---

## How it actually works

No API key required. No Anthropic SDK. It does exactly what your browser does when you open that settings page - it reads your existing Chrome session cookie and makes the same internal API call the web UI makes.

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

## Requirements

- macOS 13 Ventura or later (tested on macOS 15 Sequoia)
- Python 3.11+
- Chrome, Firefox, Safari, Brave, or Edge with an active [claude.ai](https://claude.ai) login
- A [Claude.ai](https://claude.ai) paid plan (Pro, Team, or Max - free tier doesn't expose these limits)

---

## Installation

```bash
# 1. Install dependencies
pip3 install -r requirements.txt

# 2. Build the .app
./build.sh

# 3. Install
cp -r dist/ClaudeTicker.app /Applications/
```

**First launch:** right-click → Open the first time (macOS Gatekeeper, unsigned app). After that, launch normally.

**Auto-start on login:** System Settings → General → Login Items → `+` → pick `ClaudeTicker.app`.

---

## Browser configuration

Chrome by default. To use something else, create `~/.config/claude-ticker/config.json`:

```json
{ "browser": "firefox" }
```

Valid values: `chrome`, `chromium`, `brave`, `firefox`, `safari`, `edge`.
Changes take effect on the next refresh - no restart needed.

---

## Running in dev mode (no .app build)

```bash
python3 app.py
```

App appears in the menu bar immediately. To test just the data fetching:

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
| Keychain prompt denied | Denied on first run | System Settings → Privacy & Security → Keychain Access |
| Shows `…` forever | First fetch still in progress | Wait 30s; if stuck, quit and restart |

If the API has moved, `discover.py` will probe a list of candidate endpoints and show you exactly what comes back:

```bash
python3 discover.py
# or for a specific browser:
CLAUDE_TICKER_BROWSER=firefox python3 discover.py
```

---

## Project structure

```
claude_osx_util/
├── app.py               Menu bar UI - NSStatusItem, NSPopover, WKWebView, NSTimer
├── scraper.py           All HTTP - cookie extraction, API calls, reset arithmetic
├── config.py            Browser selection via ~/.config/claude-ticker/config.json
├── discover.py          One-shot endpoint probe (run when the scraper breaks)
├── setup.py             py2app bundle config
├── build.sh             build + sign in one step
├── requirements.txt     Runtime deps
├── requirements-dev.txt Test/lint deps (pytest, ruff)
├── pyproject.toml       Ruff config
├── tests/
│   ├── test_scraper.py  27 unit tests, fully mocked
│   └── test_config.py   21 unit tests
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

**Why PyObjC and not something like `rumps`?**
`rumps` wraps standard `NSMenu` dropdowns - text only. The graphical popover with arc rings needs `NSPopover` + `WKWebView`, which requires direct AppKit/WebKit bindings. PyObjC gives you the full Cocoa API from Python.

**Why is the popup HTML embedded as a Python string?**
py2app's resource directory layout differs between dev and bundled mode. Embedding the HTML as a constant in `app.py` sidesteps path-resolution entirely and keeps the popover self-contained.

**Thread model:**
The UI runs on the main `NSRunLoop`. All network I/O happens on background threads. Results are posted back to the main thread via `NSOperationQueue.mainQueue()`. A non-blocking `threading.Lock` prevents concurrent fetches.

---

## Privacy

- Cookies are read locally from your browser's on-disk profile - no browser extension involved.
- They're used only to authenticate the two API calls per refresh cycle.
- Nothing is logged, stored, or sent anywhere else. No analytics, no telemetry.
