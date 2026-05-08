"""
Claude Ticker - Windows system tray app (pystray + pywebview)

Tray icon shows:  Claude  S:37%  W:26%  |  13m
Left-click → floating popup with graphical arc rings (bottom-right, above taskbar).
Simple View: renders session-remaining % directly into the tray icon image.
"""

import ctypes
import json
import threading
import time
import webbrowser
from datetime import datetime

import pystray
import webview
from PIL import Image, ImageDraw, ImageFont

import version
from scraper import fetch_usage, session_minutes_remaining, weekly_reset_local_str
from ui_shared import HTML, _fmt

BASE_W, BASE_H = 320, 300


def _pressure_color(pct_used: float) -> str:
    if pct_used < 60:
        return "#34C759"
    if pct_used < 85:
        return "#FF9500"
    return "#FF3B30"


def _make_tray_image(text: str | None = None, bg: str = "#cc785c") -> Image.Image:
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([0, 0, 63, 63], radius=12, fill=bg)
    label = text if text is not None else "C"
    size = 18 if text is not None else 28
    try:
        font = ImageFont.load_default(size=size)
    except TypeError:
        font = ImageFont.load_default()
    d.text((32, 32), label, fill="#fff", font=font, anchor="mm")
    return img


def _screen_pos(w: int, h: int) -> tuple:
    """Bottom-right corner of the screen, above the Windows taskbar."""
    user32 = ctypes.windll.user32
    sw = user32.GetSystemMetrics(0)
    sh = user32.GetSystemMetrics(1)
    return sw - w - 12, sh - h - 52


class _Api:
    """Exposed to JavaScript as window.pywebview.api"""

    def __init__(self, app: "App"):
        self._app = app

    def refresh(self):
        threading.Thread(target=self._app._fetch, daemon=True).start()

    def quit(self):
        self._app._stop()

    def scale(self, val=1.0):
        self._app._apply_scale(float(val))

    def login(self):
        webbrowser.open("https://claude.ai")


class App:
    def __init__(self):
        self._lock = threading.Lock()
        self._window = None
        self._icon = None
        self._visible = False
        self._ready = False
        self._pending = None
        self._scale = 1.0
        self._simple_view = False
        self._last_session_used = None  # pct_used (0-100) for icon refresh

    def _toggle(self, *_):
        if self._window is None:
            return
        if self._visible:
            self._window.hide()
            self._visible = False
        else:
            x, y = _screen_pos(int(BASE_W * self._scale), int(BASE_H * self._scale))
            self._window.move(x, y)
            self._window.show()
            self._visible = True

    def _stop(self, *_):
        self._window.destroy()
        self._icon.stop()

    def _on_loaded(self):
        self._ready = True
        if self._pending is not None:
            self._window.evaluate_js(f"updateUsage({json.dumps(self._pending)});")
            self._pending = None

    def _update_icon(self):
        if self._simple_view and self._last_session_used is not None:
            rem = round(100 - self._last_session_used)
            bg = _pressure_color(self._last_session_used)
            self._icon.icon = _make_tray_image(text=f"{rem}%", bg=bg)
        else:
            self._icon.icon = _make_tray_image()

    def _fetch(self):
        if not self._lock.acquire(blocking=False):
            return
        try:
            d = fetch_usage()
            mins = session_minutes_remaining(d)
            wstr = weekly_reset_local_str(d)
            cd = _fmt(mins)
            s_rem = 100.0 - d.session_pct_used
            w_rem = 100.0 - d.weekly_pct_used

            self._last_session_used = d.session_pct_used
            title = f"Claude  S:{s_rem:.0f}%  W:{w_rem:.0f}%  |  {cd}"
            payload = {
                "session_pct_used": d.session_pct_used,
                "weekly_pct_used": d.weekly_pct_used,
                "session_countdown": cd,
                "weekly_resets_str": wstr or "-",
                "updated_at": datetime.now().strftime("%H:%M:%S"),
            }
            self._icon.title = title
            self._update_icon()
            if self._ready:
                self._window.evaluate_js(f"updateUsage({json.dumps(payload)});")
            else:
                self._pending = payload
        except Exception as exc:
            msg = str(exc)
            self._icon.title = "Claude ⚠"
            if self._ready:
                self._window.evaluate_js(f"showError({json.dumps(msg)});")
        finally:
            self._lock.release()

    def _apply_scale(self, scale: float):
        self._scale = scale
        w, h = int(BASE_W * scale), int(BASE_H * scale)
        self._window.resize(w, h)
        if self._visible:
            x, y = _screen_pos(w, h)
            self._window.move(x, y)

    def _toggle_simple_view(self, icon, item):
        self._simple_view = not self._simple_view
        self._update_icon()

    def _check_updates(self, *_):
        def _run():
            latest, url = version.check_for_updates()
            if latest:
                old_title = self._icon.title
                self._icon.title = f"Update available: v{latest} — opening browser…"
                webbrowser.open(url)
                time.sleep(5)
                self._icon.title = old_title
            else:
                old_title = self._icon.title
                self._icon.title = f"Up to date (v{version.__version__})"
                webbrowser.open(version.RELEASES_URL)
                time.sleep(4)
                self._icon.title = old_title

        threading.Thread(target=_run, daemon=True).start()

    def _timer(self):
        while True:
            time.sleep(120)
            self._fetch()

    def run(self):
        self._icon = pystray.Icon(
            "ClaudeTicker",
            _make_tray_image(),
            title="Claude …",
            menu=pystray.Menu(
                pystray.MenuItem("Show / Hide", self._toggle, default=True),
                pystray.MenuItem(
                    "Simple View (session % in icon)",
                    self._toggle_simple_view,
                    checked=lambda item: self._simple_view,
                ),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem("Check for Updates…", self._check_updates),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem("Quit", self._stop),
            ),
        )

        self._window = webview.create_window(
            "Claude Usage",
            html=HTML,
            js_api=_Api(self),
            width=BASE_W,
            height=BASE_H,
            resizable=False,
            on_top=True,
            hidden=True,
            frameless=True,
        )
        self._window.events.loaded += self._on_loaded

        threading.Thread(target=self._fetch, daemon=True).start()
        threading.Thread(target=self._timer, daemon=True).start()

        self._icon.run_detached()
        webview.start()  # blocks main thread until all windows destroyed


if __name__ == "__main__":
    App().run()
