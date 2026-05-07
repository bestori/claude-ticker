"""
Claude Ticker - Windows system tray app (pystray + pywebview)

Tray icon shows:  Claude  S:37%  W:26%  |  13m
Left-click → floating popup with graphical arc rings (bottom-right, above taskbar).
"""

import ctypes
import json
import threading
import time
from datetime import datetime

import pystray
import webview
from PIL import Image, ImageDraw

from scraper import fetch_usage, session_minutes_remaining, weekly_reset_local_str
from ui_shared import HTML, _fmt

BASE_W, BASE_H = 320, 290


def _make_tray_image() -> Image.Image:
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([0, 0, 63, 63], radius=12, fill="#cc785c")
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
        import webbrowser
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

            title = f"Claude  S:{s_rem:.0f}%  W:{w_rem:.0f}%  |  {cd}"
            payload = {
                "session_pct_used": d.session_pct_used,
                "weekly_pct_used": d.weekly_pct_used,
                "session_countdown": cd,
                "weekly_resets_str": wstr or "-",
                "updated_at": datetime.now().strftime("%H:%M:%S"),
            }
            self._icon.title = title
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
