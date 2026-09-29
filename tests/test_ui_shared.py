"""
Unit tests for ui_shared.py helpers (pure string formatting, no GUI).
"""

from ui_shared import _fmt, _title


def test_title_long_form():
    assert _title(91.0, 73.0, "4h18m") == "Claude  S:91%  W:73%  |  4h18m"


def test_title_laptop_mode_is_short():
    assert _title(91.0, 73.0, "4h18m", laptop=True) == "CLD 91%"


def test_fmt():
    assert _fmt(None) == "?"
    assert _fmt(59) == "59m"
    assert _fmt(258) == "4h18m"
