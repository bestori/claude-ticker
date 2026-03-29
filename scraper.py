"""
Fetches Claude.ai plan usage limits (session + weekly) using
the current browser session cookies for authentication.

Endpoint: GET /api/organizations/{org_uuid}/usage
Response shape:
  {
    "five_hour":  { "utilization": 96.0, "resets_at": "<iso>" },   <- session
    "seven_day":  { "utilization": 73.0, "resets_at": "<iso>" },   <- weekly
    ...
  }

The browser used for cookie extraction is read from
~/.config/claude-ticker/config.json (key: "browser"). Defaults to "chrome".
"""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

import browser_cookie3
import requests

from config import SUPPORTED_BROWSERS, get_browser

BASE = "https://claude.ai"

# Supported browser names - must match browser_cookie3 function names exactly
_BROWSER_NAMES = frozenset({"chrome", "chromium", "brave", "firefox", "safari", "edge"})


@dataclass
class UsageData:
    session_pct_used: float  # 0–100
    session_resets_at: Optional[datetime]  # timezone-aware UTC datetime
    weekly_pct_used: float  # 0–100
    weekly_resets_at: Optional[datetime]


# ── helpers ───────────────────────────────────────────────────────────────────


def _make_session() -> requests.Session:
    browser = get_browser()
    # Use getattr so patching browser_cookie3 in tests works correctly
    fn = getattr(browser_cookie3, browser, browser_cookie3.chrome)
    try:
        cookies = fn(domain_name=".claude.ai")
    except Exception as e:
        raise RuntimeError(
            f"Could not read {browser} cookies: {e}\n"
            f"Supported browsers: {', '.join(sorted(SUPPORTED_BROWSERS))}"
        ) from e
    s = requests.Session()
    s.cookies = cookies
    s.headers.update(
        {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept": "application/json, */*",
            "Referer": f"{BASE}/settings",
        }
    )
    return s


def _get_org_uuid(s: requests.Session) -> str:
    """Return the organisation UUID from /api/bootstrap."""
    r = s.get(f"{BASE}/api/bootstrap", timeout=10)
    r.raise_for_status()
    data = r.json()
    for m in data.get("account", {}).get("memberships", []):
        org = m.get("organization") or {}
        uid = org.get("uuid")
        if uid:
            return uid
    raise RuntimeError(
        "Could not find org UUID in /api/bootstrap response. "
        "Are you logged in to claude.ai in Chrome?"
    )


def _parse_iso(ts: Optional[str]) -> Optional[datetime]:
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts)
    except ValueError:
        return None


def _minutes_until(dt: Optional[datetime]) -> Optional[float]:
    """Minutes until dt (UTC-aware). Returns negative if already past."""
    if dt is None:
        return None
    now = datetime.now(timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return (dt - now).total_seconds() / 60


def _next_reset(dt: Optional[datetime], window_hours: int) -> Optional[datetime]:
    """
    If dt is in the past, advance by window_hours until it's in the future.
    Handles the case where the API gives the last-reset time rather than the
    next-reset time.
    """
    if dt is None:
        return None
    now = datetime.now(timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    while dt <= now:
        dt += timedelta(hours=window_hours)
    return dt


# ── public API ────────────────────────────────────────────────────────────────


def fetch_usage() -> UsageData:
    """
    Returns current Claude.ai session + weekly usage.
    Raises RuntimeError on auth or network failure.
    """
    s = _make_session()
    org_uuid = _get_org_uuid(s)

    url = f"{BASE}/api/organizations/{org_uuid}/usage"
    try:
        r = s.get(url, timeout=10)
        r.raise_for_status()
    except requests.HTTPError as e:
        raise RuntimeError(f"Usage API returned {r.status_code}: {e}") from e
    except requests.RequestException as e:
        raise RuntimeError(f"Network error fetching usage: {e}") from e

    data = r.json()

    five = data.get("five_hour") or {}
    seven = data.get("seven_day") or {}

    sess_raw = _parse_iso(five.get("resets_at"))
    week_raw = _parse_iso(seven.get("resets_at"))

    # If resets_at is in the past the server hasn't refreshed yet;
    # advance forward by the window size until it's future.
    sess_reset = _next_reset(sess_raw, window_hours=5)
    week_reset = _next_reset(week_raw, window_hours=7 * 24)

    return UsageData(
        session_pct_used=float(five.get("utilization") or 0),
        session_resets_at=sess_reset,
        weekly_pct_used=float(seven.get("utilization") or 0),
        weekly_resets_at=week_reset,
    )


# ── convenience accessors (used by app.py) ───────────────────────────────────


def session_minutes_remaining(d: UsageData) -> Optional[float]:
    return _minutes_until(d.session_resets_at)


def weekly_reset_local_str(d: UsageData) -> Optional[str]:
    """Format weekly reset as local day + time, e.g. 'Tue 3:00 AM'."""
    if d.weekly_resets_at is None:
        return None
    local = d.weekly_resets_at.astimezone()  # system timezone
    return local.strftime("%a %-I:%M %p")
