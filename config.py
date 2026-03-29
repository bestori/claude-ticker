"""
User configuration for Claude Ticker.

Config file location: ~/.config/claude-ticker/config.json

Supported keys
--------------
browser : str
    Which browser to read cookies from. One of: chrome, firefox, safari,
    brave, edge, chromium. Defaults to "chrome".

Example config file
-------------------
{
  "browser": "firefox"
}

Any unknown keys are silently ignored. Any error reading or parsing the file
causes the app to fall back to defaults - it will never crash on a bad config.
"""

import json
from pathlib import Path

CONFIG_DIR = Path.home() / ".config" / "claude-ticker"
CONFIG_FILE = CONFIG_DIR / "config.json"

SUPPORTED_BROWSERS = frozenset(
    {"chrome", "chromium", "brave", "firefox", "safari", "edge"}
)

DEFAULT_CONFIG: dict = {"browser": "chrome"}


def load_config() -> dict:
    """
    Read ~/.config/claude-ticker/config.json.
    Returns DEFAULT_CONFIG on any error (missing file, bad JSON, wrong type).
    """
    try:
        with open(CONFIG_FILE) as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return dict(DEFAULT_CONFIG)
        return data
    except (OSError, json.JSONDecodeError):
        return dict(DEFAULT_CONFIG)


def get_browser() -> str:
    """
    Return the configured browser name, validated against SUPPORTED_BROWSERS.
    Falls back to "chrome" if the value is missing or unrecognised.
    """
    value = load_config().get("browser", DEFAULT_CONFIG["browser"])
    if not isinstance(value, str) or value.lower() not in SUPPORTED_BROWSERS:
        return DEFAULT_CONFIG["browser"]
    return value.lower()


def save_config(updates: dict) -> None:
    """
    Merge *updates* into the current config and write it back to disk.
    Creates the config directory if it does not exist.
    """
    current = load_config()
    current.update(updates)
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, "w") as f:
        json.dump(current, f, indent=2)
