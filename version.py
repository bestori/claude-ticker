import json
import os
import sys
import urllib.request

# Patched by CI during release builds (see .github/workflows/release.yml).
# In development, _get_version() reads from the git tag instead.
_BAKED_VERSION = "1"

GITHUB_REPO = "bestori/claude-ticker"
RELEASES_URL = f"https://github.com/{GITHUB_REPO}/releases"


def _get_version() -> str:
    if getattr(sys, "frozen", False):
        # Running inside a py2app / PyInstaller bundle — git not available.
        return _BAKED_VERSION
    try:
        import subprocess
        tag = subprocess.check_output(
            ["git", "describe", "--tags", "--exact-match", "HEAD"],
            stderr=subprocess.DEVNULL,
            cwd=os.path.dirname(os.path.abspath(__file__)),
        ).decode().strip().lstrip("v")
        if tag:
            return tag
    except Exception:
        pass
    return _BAKED_VERSION


__version__ = _get_version()


def check_for_updates():
    """Return (latest_version, release_url) if newer release exists, else (None, None)."""
    api = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
    req = urllib.request.Request(
        api, headers={"User-Agent": f"claude-ticker/{__version__}"}
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            data = json.loads(r.read())
    except Exception:
        return None, None
    tag = data.get("tag_name", "").lstrip("v")
    url = data.get("html_url", RELEASES_URL)
    if tag and _newer(tag, __version__):
        return tag, url
    return None, None


def _newer(a: str, b: str) -> bool:
    try:
        return int(a) > int(b)
    except ValueError:
        return False
