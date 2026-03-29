# Contributing to Claude Ticker

Thank you for contributing. This document covers how to set up a development
environment, run tests and the linter, and debug the most common failure mode
(the claude.ai API changing).

---

## Prerequisites

- **macOS** - required to run the app itself (menu bar + WebKit). Tests can run
  on any platform, but CI is pinned to `macos-latest` because `browser_cookie3`
  and `pycryptodome` have platform-specific behaviour.
- **Python 3.11+** - the codebase targets 3.11 as the minimum version.
- **Google Chrome** with an active `claude.ai` login - only needed if you want
  to run the app or the live scraper test.

---

## Development setup

```bash
# Clone and enter the repo
git clone https://github.com/bestori/claude-ticker.git
cd claude-ticker

# Create a virtual environment (recommended)
python3 -m venv .venv
source .venv/bin/activate

# Install development dependencies
pip install -r requirements-dev.txt

# Install full runtime dependencies (needed to build or run the app)
pip install -r requirements.txt
```

---

## Running the app without building

```bash
python3 app.py
```

The app appears in the menu bar immediately. Quit via the button in the popover
or `Ctrl-C` in the terminal.

---

## Running tests

```bash
pytest tests/ -v
```

All tests mock out network I/O and cookie access - no live claude.ai session is
needed. The suite runs in under a second.

Run a single test file:

```bash
pytest tests/test_scraper.py -v
```

Run a single test by name:

```bash
pytest tests/test_scraper.py::TestNextReset::test_past_timestamp_advanced_to_future -v
```

---

## Linting and formatting

The project uses [ruff](https://docs.astral.sh/ruff/) for both linting and
formatting.

```bash
# Check for lint errors (same check run in CI)
ruff check .

# Auto-fix all fixable issues
ruff check . --fix

# Check formatting
ruff format --check .

# Apply formatting
ruff format .
```

Configuration is in `pyproject.toml`. The only intentional suppression is
`E501` (line-too-long) in `app.py`, which contains a minified HTML/CSS/JS
constant with intentionally long lines.

---

## Debugging a broken scraper

The most common cause of breakage is Anthropic changing the claude.ai API -
either a new endpoint path, different authentication, or a changed response
schema.

### Step 1 - isolate the scraper

```bash
python3 -c "from scraper import fetch_usage; print(fetch_usage())"
```

A clean result looks like:

```
UsageData(session_pct_used=45.0, session_resets_at=datetime.datetime(...),
          weekly_pct_used=20.0, weekly_resets_at=datetime.datetime(...))
```

Common errors and what they mean:

| Error message | Likely cause | Where to look |
|---------------|-------------|---------------|
| `Could not read chrome cookies` | Keychain access denied, or Chrome not installed | System Settings → Privacy & Security → Keychain |
| `Could not find org UUID` | `/api/bootstrap` response shape changed | `scraper._get_org_uuid()` |
| `Usage API returned 404` | Endpoint path changed | Run `discover.py` |
| `Usage API returned 403` | Session cookie expired | Log out and back in to claude.ai in Chrome |
| `Network error fetching usage` | No internet, DNS failure, or claude.ai is down | Check connectivity |

### Step 2 - run the discovery probe

`discover.py` tries a broad list of candidate API paths and prints the first
400 characters of each successful JSON response:

```bash
python3 discover.py
```

To use a different browser for a single run (without editing the config):

```bash
CLAUDE_TICKER_BROWSER=firefox python3 discover.py
```

Sample output when the endpoint is found:

```
Using browser: chrome
Grabbing cookies for claude.ai…

Bootstrap check → HTTP 200
Account keys: ['tagged_id', 'uuid', 'email_address', 'memberships', ...]
  org_uuid = xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx

── Probing endpoints ──────────────────────────────────────────
✓ JSON  /api/organizations/xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx/usage
      {
        "five_hour": { "utilization": 45.0, "resets_at": "..." },
        "seven_day": { "utilization": 20.0, "resets_at": "..." },
        ...
      }
  404  /api/usage_limits
  ...
```

### Step 3 - update the parser

If the endpoint has moved, update `fetch_usage()` in `scraper.py:111`.

If the response schema has changed (different key names), update the field
lookups near `scraper.py:133`:

```python
five  = data.get("five_hour")  or {}   # ← update key if renamed
seven = data.get("seven_day")  or {}   # ← update key if renamed

session_pct_used = float(five.get("utilization") or 0)   # ← update field
weekly_pct_used  = float(seven.get("utilization") or 0)  # ← update field
```

Add or update the corresponding tests in `tests/test_scraper.py` to cover the
new response shape.

### Step 4 - add the new endpoint to discover.py

If a new endpoint was found, add it to `CANDIDATES` in `discover.py` so future
contributors find it quickly.

---

## Adding support for a new browser

1. Verify `browser_cookie3` has a function with that name (e.g.
   `browser_cookie3.vivaldi`).

2. Add the name to `SUPPORTED_BROWSERS` in `config.py`:

   ```python
   SUPPORTED_BROWSERS = frozenset(
       {"chrome", "chromium", "brave", "firefox", "safari", "edge", "vivaldi"}
   )
   ```

3. `scraper._make_session()` uses `getattr(browser_cookie3, browser)` - no
   other changes needed in the scraper.

4. Add the new browser to the parametrised test in `tests/test_config.py`:

   ```python
   @pytest.mark.parametrize("browser", sorted(SUPPORTED_BROWSERS))
   def test_all_supported_browsers_accepted(self, ...):
   ```

   This test is driven by `SUPPORTED_BROWSERS` directly, so no manual update
   is needed if the constant is updated correctly in step 2.

5. Update the browser table in `README.md`.

---

## Pull request checklist

- [ ] `pytest tests/ -v` passes with no failures
- [ ] `ruff check .` reports no errors
- [ ] `ruff format --check .` reports no changes needed
- [ ] No new hardcoded browser names outside `config.py`
- [ ] Any new API endpoint has been added to `discover.py`'s `CANDIDATES` list
- [ ] `CLAUDE.md` is updated if the architecture has changed

---

## Architecture overview

```
app.py        NSApplication delegate, NSStatusBar item, NSPopover + WKWebView,
              NSTimer for auto-refresh, thread-safe fetch dispatch
scraper.py    Cookie extraction, /api/bootstrap, /api/organizations/{uuid}/usage,
              reset-time arithmetic
config.py     ~/.config/claude-ticker/config.json read/write, browser selection
discover.py   One-shot diagnostic endpoint probe (not part of the running app)
setup.py      py2app bundle configuration (LSUIElement, Info.plist keys)
tests/        Unit tests for scraper.py and config.py (48 tests, no network I/O)
```

The popover UI is a self-contained HTML/CSS/JS string embedded at the top of
`app.py`. Python pushes data updates via `WKWebView.evaluateJavaScript`. The
page sends actions back (Refresh, Quit) via
`window.webkit.messageHandlers.<name>.postMessage()`, received by `_JSHandler`
which implements the `WKScriptMessageHandler` protocol.

---

## Reporting issues

Please include:
1. The output of `python3 discover.py`
2. Your macOS version (`sw_vers`)
3. Your Python version (`python3 --version`)
4. The browser you're using (from `~/.config/claude-ticker/config.json` or
   default `chrome`)
