"""
Claude Ticker - macOS menu bar app (PyObjC + WKWebView)

Status bar shows:  Claude  S:37%  W:26%  |  13m
                   CLD 63%                       (laptop mode)
Click → NSPopover with graphical progress rings.
"""

import json
import subprocess
import threading
import webbrowser
from datetime import datetime

import AppKit
import objc
import WebKit
from Foundation import NSObject, NSOperationQueue, NSTimer, NSUserDefaults

import version
from config import get_laptop_mode, save_config
from scraper import fetch_usage, session_minutes_remaining, weekly_reset_local_str
from ui_shared import HTML, _fmt, _title

# ── JS → Python message handler ───────────────────────────────────────────────


class _JSHandler(NSObject):
    """Receives postMessage() calls from JavaScript."""

    def initWithCallback_(self, cb):
        self = objc.super(_JSHandler, self).init()
        if self is None:
            return None
        self._cb = cb
        return self

    def userContentController_didReceiveScriptMessage_(self, ucc, msg):
        self._cb(msg.name(), msg.body())


# ── main app delegate ─────────────────────────────────────────────────────────


class AppDelegate(NSObject):
    def applicationDidFinishLaunching_(self, _):
        self._lock = threading.Lock()
        self._ready = False  # page loaded flag
        self._pending = None  # payload buffered before page ready
        self._laptop = get_laptop_mode()  # short menu bar text ("CLD 91%")
        self._last = None  # (s_rem, w_rem, countdown) from last good fetch
        self._err = False  # last fetch failed

        self._build_status_bar()
        self._build_popover()

        # First fetch + 120-second auto-refresh
        threading.Thread(target=self._fetch, daemon=True).start()
        NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(
            120.0, self, "tick:", None, True
        )

    # ── status bar ─────────────────────────────────────────────────────────

    @objc.python_method
    def _build_status_bar(self):
        # ponytail: force the menu bar slot every launch so the notch never trims it.
        # Value = points from the right screen edge; 340 lands just left of Bluetooth.
        # "Item-0" is the autosave name macOS assigns when none is set.
        # Cmd-drag won't stick across relaunches; make it a config key if needed.
        NSUserDefaults.standardUserDefaults().setFloat_forKey_(
            340.0, "NSStatusItem Preferred Position Item-0"
        )
        self._item = AppKit.NSStatusBar.systemStatusBar().statusItemWithLength_(
            AppKit.NSVariableStatusItemLength
        )
        btn = self._item.button()
        btn.setTitle_(f"{self._brand()} …")
        btn.setTarget_(self)
        btn.setAction_("onStatusClick:")
        btn.sendActionOn_(
            AppKit.NSEventMaskLeftMouseDown | AppKit.NSEventMaskRightMouseDown
        )
        self._menu = self._build_menu()

    @objc.python_method
    def _build_menu(self):
        menu = AppKit.NSMenu.alloc().init()

        def _item(title, sel):
            it = AppKit.NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
                title, sel, ""
            )
            it.setTarget_(self)
            return it

        menu.addItem_(_item("Login to Claude.ai", "menuOpenClaude:"))
        menu.addItem_(_item("Logout", "menuLogout:"))
        menu.addItem_(_item("Refresh", "menuRefresh:"))
        menu.addItem_(AppKit.NSMenuItem.separatorItem())
        menu.addItem_(_item("Check for Updates…", "menuCheckUpdates:"))
        menu.addItem_(AppKit.NSMenuItem.separatorItem())
        menu.addItem_(_item("Quit", "menuQuit:"))
        return menu

    def onStatusClick_(self, sender):
        event = AppKit.NSApp.currentEvent()
        if event.type() == AppKit.NSEventTypeRightMouseDown:
            self._pop.close()
            self._item.popUpStatusItemMenu_(self._menu)
        else:
            if self._pop.isShown():
                self._pop.close()
            else:
                btn = self._item.button()
                self._pop.showRelativeToRect_ofView_preferredEdge_(
                    btn.bounds(), btn, AppKit.NSRectEdgeMinY
                )

    def menuOpenClaude_(self, sender):
        subprocess.Popen(["open", "https://claude.ai"])

    def menuLogout_(self, sender):
        subprocess.Popen(["open", "https://claude.ai/logout"])

    def menuRefresh_(self, sender):
        threading.Thread(target=self._fetch, daemon=True).start()

    def menuCheckUpdates_(self, sender):
        def _run():
            latest, url = version.check_for_updates()
            target = url if latest else version.RELEASES_URL
            webbrowser.open(target)
            if latest:
                NSOperationQueue.mainQueue().addOperationWithBlock_(
                    lambda: self._item.button().setTitle_(
                        f"{self._brand()}  ↑ v{latest} available"
                    )
                )

        threading.Thread(target=_run, daemon=True).start()

    def menuQuit_(self, sender):
        AppKit.NSApplication.sharedApplication().terminate_(None)

    # ── popover + webview ──────────────────────────────────────────────────

    @objc.python_method
    def _build_popover(self):
        cfg = WebKit.WKWebViewConfiguration.alloc().init()
        ucc = WebKit.WKUserContentController.alloc().init()

        self._jsh = _JSHandler.alloc().initWithCallback_(self._on_js)
        ucc.addScriptMessageHandler_name_(self._jsh, "refresh")
        ucc.addScriptMessageHandler_name_(self._jsh, "quit")
        ucc.addScriptMessageHandler_name_(self._jsh, "scale")
        ucc.addScriptMessageHandler_name_(self._jsh, "login")
        ucc.addScriptMessageHandler_name_(self._jsh, "laptop")
        cfg.setUserContentController_(ucc)

        frame = AppKit.NSMakeRect(0, 0, 320, 290)
        self._wv = WebKit.WKWebView.alloc().initWithFrame_configuration_(frame, cfg)
        self._wv.setNavigationDelegate_(self)
        # transparent background so card shadow looks right
        self._wv.setValue_forKey_(False, "drawsBackground")
        self._wv.loadHTMLString_baseURL_(HTML, None)

        vc = AppKit.NSViewController.alloc().init()
        vc.setView_(self._wv)

        self._pop = AppKit.NSPopover.alloc().init()
        self._pop.setContentSize_(AppKit.NSMakeSize(320, 290))
        self._pop.setContentViewController_(vc)
        self._pop.setBehavior_(AppKit.NSPopoverBehaviorTransient)

    def webView_didFinishNavigation_(self, wv, nav):
        self._ready = True
        self._wv.evaluateJavaScript_completionHandler_(
            f"setLaptopUI({json.dumps(self._laptop)});", None
        )
        if self._pending is not None:
            self._push(self._pending)
            self._pending = None

    @objc.python_method
    def _on_js(self, name, body=None):
        if name == "refresh":
            threading.Thread(target=self._fetch, daemon=True).start()
        elif name == "quit":
            AppKit.NSApplication.sharedApplication().terminate_(None)
        elif name == "login":
            subprocess.Popen(["open", "https://claude.ai"])
        elif name == "scale":
            s = float(body)
            NSOperationQueue.mainQueue().addOperationWithBlock_(
                lambda: self._apply_scale(s)
            )
        elif name == "laptop":
            self._laptop = body == "1"
            save_config({"laptop_mode": self._laptop})
            self._retitle()

    # ── timer ──────────────────────────────────────────────────────────────

    def tick_(self, _):
        threading.Thread(target=self._fetch, daemon=True).start()

    # ── data fetch ─────────────────────────────────────────────────────────

    @objc.python_method
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

            payload = {
                "session_pct_used": d.session_pct_used,
                "weekly_pct_used": d.weekly_pct_used,
                "session_countdown": cd,
                "weekly_resets_str": wstr or "-",
                "updated_at": datetime.now().strftime("%H:%M:%S"),
            }
            NSOperationQueue.mainQueue().addOperationWithBlock_(
                lambda: self._apply((s_rem, w_rem, cd), payload)
            )
        except Exception as exc:
            msg = str(exc)
            NSOperationQueue.mainQueue().addOperationWithBlock_(
                lambda: self._apply_err(msg)
            )
        finally:
            self._lock.release()

    @objc.python_method
    def _brand(self):
        return "CLD" if self._laptop else "Claude"

    @objc.python_method
    def _retitle(self):
        if self._err:
            t = f"{self._brand()} ⚠"
        elif self._last:
            t = _title(*self._last, laptop=self._laptop)
        else:
            t = f"{self._brand()} …"
        self._item.button().setTitle_(t)

    @objc.python_method
    def _apply(self, last, payload):
        self._last, self._err = last, False
        self._retitle()
        if self._ready:
            self._push(payload)
        else:
            self._pending = payload

    @objc.python_method
    def _push(self, payload):
        js = f"updateUsage({json.dumps(payload)});"
        self._wv.evaluateJavaScript_completionHandler_(js, None)

    @objc.python_method
    def _apply_scale(self, scale):
        w = int(320 * scale)
        h = int(290 * scale)
        self._wv.setFrame_(AppKit.NSMakeRect(0, 0, w, h))
        self._pop.setContentSize_(AppKit.NSMakeSize(w, h))

    @objc.python_method
    def _apply_err(self, msg):
        self._err = True
        self._retitle()
        if self._ready:
            self._wv.evaluateJavaScript_completionHandler_(
                f"showError({json.dumps(msg)});", None
            )


# ── entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app = AppKit.NSApplication.sharedApplication()
    app.setActivationPolicy_(AppKit.NSApplicationActivationPolicyAccessory)

    delegate = AppDelegate.alloc().init()
    app.setDelegate_(delegate)

    app.run()
