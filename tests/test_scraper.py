"""
Unit tests for scraper.py.

All network I/O and cookie access is mocked - no live claude.ai session needed.
"""

import re
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest
import requests as requests_lib

from scraper import (
    UsageData,
    _minutes_until,
    _next_reset,
    _parse_iso,
    fetch_usage,
    session_minutes_remaining,
    weekly_reset_local_str,
)

# ── _parse_iso ────────────────────────────────────────────────────────────────


class TestParseIso:
    def test_valid_utc_string(self):
        result = _parse_iso("2026-04-01T12:00:00+00:00")
        assert result is not None
        assert result.tzinfo is not None

    def test_valid_offset_string(self):
        result = _parse_iso("2026-04-01T14:00:00+02:00")
        assert result is not None

    def test_none_returns_none(self):
        assert _parse_iso(None) is None

    def test_empty_string_returns_none(self):
        assert _parse_iso("") is None

    def test_invalid_string_returns_none(self):
        assert _parse_iso("not-a-date") is None


# ── _minutes_until ────────────────────────────────────────────────────────────


class TestMinutesUntil:
    def test_future_datetime_positive(self):
        future = datetime.now(timezone.utc) + timedelta(minutes=42)
        result = _minutes_until(future)
        assert result is not None
        assert 41 < result < 43

    def test_past_datetime_negative(self):
        past = datetime.now(timezone.utc) - timedelta(minutes=10)
        result = _minutes_until(past)
        assert result is not None
        assert result < 0

    def test_none_returns_none(self):
        assert _minutes_until(None) is None

    def test_naive_datetime_treated_as_utc(self):
        # naive datetime 60 min ahead of UTC (utcnow is naive UTC)
        naive = datetime.utcnow() + timedelta(minutes=60)
        result = _minutes_until(naive)
        assert result is not None
        assert 58 < result < 62


# ── _next_reset ───────────────────────────────────────────────────────────────


class TestNextReset:
    def test_future_timestamp_returned_unchanged(self):
        future = datetime.now(timezone.utc) + timedelta(hours=2)
        result = _next_reset(future, window_hours=5)
        # Should be equal (within floating-point noise from the while condition)
        assert result is not None
        diff = abs((result - future).total_seconds())
        assert diff < 1

    def test_past_timestamp_advanced_to_future(self):
        past = datetime.now(timezone.utc) - timedelta(hours=1)
        result = _next_reset(past, window_hours=5)
        assert result is not None
        assert result > datetime.now(timezone.utc)

    def test_very_old_timestamp_advanced_multiple_windows(self):
        # 12 hours ago with a 5-hour window → needs to advance at least twice
        old = datetime.now(timezone.utc) - timedelta(hours=12)
        result = _next_reset(old, window_hours=5)
        assert result is not None
        assert result > datetime.now(timezone.utc)
        # Result should be within one window of now
        assert result < datetime.now(timezone.utc) + timedelta(hours=5)

    def test_none_returns_none(self):
        assert _next_reset(None, window_hours=5) is None

    def test_naive_datetime_treated_as_utc(self):
        naive_past = datetime.now() - timedelta(hours=2)
        assert naive_past.tzinfo is None
        result = _next_reset(naive_past, window_hours=5)
        assert result is not None
        assert result > datetime.now(timezone.utc)

    def test_weekly_window(self):
        past = datetime.now(timezone.utc) - timedelta(days=3)
        result = _next_reset(past, window_hours=7 * 24)
        assert result is not None
        assert result > datetime.now(timezone.utc)
        assert result < datetime.now(timezone.utc) + timedelta(days=7)


# ── fetch_usage ───────────────────────────────────────────────────────────────

# Reusable mock API responses
_BOOTSTRAP = {
    "account": {
        "memberships": [
            {
                "organization": {
                    "uuid": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
                    "id": 99999,
                }
            }
        ]
    }
}

_USAGE_FUTURE = {
    "five_hour": {
        "utilization": 45.0,
        "resets_at": "2099-01-01T10:00:00+00:00",
    },
    "seven_day": {
        "utilization": 20.0,
        "resets_at": "2099-01-07T00:00:00+00:00",
    },
    "extra_usage": {"is_enabled": True, "used_credits": 0.0},
}

_USAGE_PAST_RESET = {
    "five_hour": {
        "utilization": 80.0,
        "resets_at": "2020-01-01T00:00:00+00:00",  # far in the past
    },
    "seven_day": {
        "utilization": 60.0,
        "resets_at": "2020-01-01T00:00:00+00:00",
    },
}


def _make_mock_session(bootstrap=None, usage=None, usage_status=200):
    """Return a mock requests.Session with two canned GET responses."""
    resp_bootstrap = MagicMock()
    resp_bootstrap.ok = True
    resp_bootstrap.json.return_value = bootstrap or _BOOTSTRAP
    resp_bootstrap.raise_for_status = MagicMock()

    resp_usage = MagicMock()
    resp_usage.ok = usage_status == 200
    resp_usage.status_code = usage_status
    resp_usage.json.return_value = usage or _USAGE_FUTURE
    if usage_status != 200:
        resp_usage.raise_for_status.side_effect = requests_lib.HTTPError(
            f"HTTP {usage_status}"
        )
    else:
        resp_usage.raise_for_status = MagicMock()

    mock_session = MagicMock()
    mock_session.get.side_effect = [resp_bootstrap, resp_usage]
    mock_session.cookies = MagicMock()
    mock_session.headers = {}
    return mock_session


class TestFetchUsage:
    def _patch(self, mock_session, browser="chrome"):
        """Context managers to patch browser_cookie3 and requests.Session."""
        mock_bc = MagicMock()
        mock_bc.chrome.return_value = MagicMock()
        mock_bc.firefox.return_value = MagicMock()
        mock_bc.safari.return_value = MagicMock()
        mock_bc.brave.return_value = MagicMock()
        mock_bc.edge.return_value = MagicMock()
        mock_bc.chromium.return_value = MagicMock()
        return (
            patch("scraper.browser_cookie3", mock_bc),
            patch("scraper.requests.Session", return_value=mock_session),
            patch("scraper.get_browser", return_value=browser),
        )

    def test_returns_usage_data(self):
        ms = _make_mock_session()
        p1, p2, p3 = self._patch(ms)
        with p1, p2, p3:
            d = fetch_usage()
        assert isinstance(d, UsageData)
        assert d.session_pct_used == 45.0
        assert d.weekly_pct_used == 20.0

    def test_reset_times_are_future(self):
        ms = _make_mock_session()
        p1, p2, p3 = self._patch(ms)
        with p1, p2, p3:
            d = fetch_usage()
        assert d.session_resets_at is not None
        assert d.weekly_resets_at is not None
        assert d.session_resets_at > datetime.now(timezone.utc)
        assert d.weekly_resets_at > datetime.now(timezone.utc)

    def test_past_resets_at_advanced_to_future(self):
        ms = _make_mock_session(usage=_USAGE_PAST_RESET)
        p1, p2, p3 = self._patch(ms)
        with p1, p2, p3:
            d = fetch_usage()
        assert d.session_resets_at > datetime.now(timezone.utc)
        assert d.weekly_resets_at > datetime.now(timezone.utc)

    def test_http_error_raises_runtime_error(self):
        ms = _make_mock_session(usage_status=403)
        p1, p2, p3 = self._patch(ms)
        with p1, p2, p3, pytest.raises(RuntimeError):
            fetch_usage()

    def test_missing_org_uuid_raises_runtime_error(self):
        bad_bootstrap = {"account": {"memberships": []}}
        ms = _make_mock_session(bootstrap=bad_bootstrap)
        p1, p2, p3 = self._patch(ms)
        with p1, p2, p3, pytest.raises(RuntimeError, match="org UUID"):
            fetch_usage()

    def test_uses_configured_browser(self):
        ms = _make_mock_session()
        mock_bc = MagicMock()
        mock_bc.firefox.return_value = MagicMock()
        with (
            patch("scraper.browser_cookie3", mock_bc),
            patch("scraper.requests.Session", return_value=ms),
            patch("scraper.get_browser", return_value="firefox"),
        ):
            fetch_usage()
        mock_bc.firefox.assert_called_once_with(domain_name=".claude.ai")

    def test_null_utilization_defaults_to_zero(self):
        usage = {
            "five_hour": {
                "utilization": None,
                "resets_at": "2099-01-01T10:00:00+00:00",
            },
            "seven_day": {
                "utilization": None,
                "resets_at": "2099-01-07T00:00:00+00:00",
            },
        }
        ms = _make_mock_session(usage=usage)
        p1, p2, p3 = self._patch(ms)
        with p1, p2, p3:
            d = fetch_usage()
        assert d.session_pct_used == 0.0
        assert d.weekly_pct_used == 0.0

    def test_missing_five_hour_key(self):
        usage = {
            "seven_day": {
                "utilization": 50.0,
                "resets_at": "2099-01-07T00:00:00+00:00",
            },
        }
        ms = _make_mock_session(usage=usage)
        p1, p2, p3 = self._patch(ms)
        with p1, p2, p3:
            d = fetch_usage()
        assert d.session_pct_used == 0.0
        assert d.weekly_pct_used == 50.0


# ── session_minutes_remaining ─────────────────────────────────────────────────


class TestSessionMinutesRemaining:
    def _data(self, session_resets_at):
        return UsageData(
            session_pct_used=50.0,
            session_resets_at=session_resets_at,
            weekly_pct_used=30.0,
            weekly_resets_at=datetime.now(timezone.utc) + timedelta(days=3),
        )

    def test_90_minutes_remaining(self):
        dt = datetime.now(timezone.utc) + timedelta(minutes=90)
        result = session_minutes_remaining(self._data(dt))
        assert 89 < result < 91

    def test_none_when_no_reset_time(self):
        d = UsageData(
            session_pct_used=50.0,
            session_resets_at=None,
            weekly_pct_used=30.0,
            weekly_resets_at=None,
        )
        assert session_minutes_remaining(d) is None


# ── weekly_reset_local_str ────────────────────────────────────────────────────


class TestWeeklyResetLocalStr:
    def _data(self, weekly_resets_at):
        return UsageData(
            session_pct_used=50.0,
            session_resets_at=datetime.now(timezone.utc) + timedelta(hours=2),
            weekly_pct_used=30.0,
            weekly_resets_at=weekly_resets_at,
        )

    def test_returns_day_and_time_string(self):
        dt = datetime(2026, 4, 7, 3, 0, 0, tzinfo=timezone.utc)
        result = weekly_reset_local_str(self._data(dt))
        assert result is not None
        # e.g. "Tue 3:00 AM" or "Tue 5:00 AM" depending on local TZ offset
        assert re.match(
            r"^(Mon|Tue|Wed|Thu|Fri|Sat|Sun) \d{1,2}:\d{2} (AM|PM)$",
            result,
        ), f"Unexpected format: {result!r}"

    def test_none_when_no_reset_time(self):
        d = UsageData(
            session_pct_used=50.0,
            session_resets_at=None,
            weekly_pct_used=30.0,
            weekly_resets_at=None,
        )
        assert weekly_reset_local_str(d) is None
