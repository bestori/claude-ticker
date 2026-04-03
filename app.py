"""
Claude Ticker - macOS menu bar app (PyObjC + WKWebView)

Status bar shows:  Claude  S:37%  W:26%  |  13m
Click → NSPopover with graphical progress rings.
"""

import json
import threading
from datetime import datetime

import AppKit
import objc
import WebKit
from Foundation import NSObject, NSOperationQueue, NSTimer

from scraper import fetch_usage, session_minutes_remaining, weekly_reset_local_str

# ── HTML popup UI ─────────────────────────────────────────────────────────────

HTML = """\
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<meta name="color-scheme" content="light dark">
<style>
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}

:root{
  --bg:#f2f2f7;--card:#fff;--text:#1d1d1f;--sub:#86868b;
  --sep:rgba(0,0,0,.08);--btn:rgba(0,0,0,.06);--btn-h:rgba(0,0,0,.12);
  --accent:#0071e3;
}
@media(prefers-color-scheme:dark){
  :root{
    --bg:#1c1c1e;--card:#2c2c2e;--text:#f5f5f7;--sub:#98989d;
    --sep:rgba(255,255,255,.1);--btn:rgba(255,255,255,.08);--btn-h:rgba(255,255,255,.15);
    --accent:#2997ff;
  }
}

html,body{
  width:300px;height:290px;overflow:hidden;
  background:var(--bg);
  font-family:-apple-system,"SF Pro Text",BlinkMacSystemFont,sans-serif;
  color:var(--text);font-size:13px;
  -webkit-font-smoothing:antialiased;
  user-select:none;-webkit-user-select:none;
}

.wrap{padding:14px 14px 12px;display:flex;flex-direction:column;gap:9px;height:100%}

/* ── header ── */
.hdr{display:flex;align-items:center;gap:8px;font-size:14px;font-weight:600}
.logo{
  width:22px;height:22px;border-radius:6px;
  background:linear-gradient(135deg,#cc785c,#e8956d);
  display:flex;align-items:center;justify-content:center;
  color:#fff;font-size:12px;font-weight:700;flex-shrink:0;
}

/* ── cards ── */
.card{
  background:var(--card);border-radius:11px;
  padding:11px 13px;display:flex;align-items:center;gap:13px;
  box-shadow:0 1px 3px rgba(0,0,0,.06);
}

/* ── ring ── */
.ring-wrap{position:relative;width:58px;height:58px;flex-shrink:0}
.ring-wrap svg{transform:rotate(-90deg)}
circle.track{fill:none;stroke:var(--sep);stroke-width:5.5}
circle.arc{
  fill:none;stroke-width:5.5;stroke-linecap:round;
  transition:stroke-dashoffset .7s cubic-bezier(.4,0,.2,1),stroke .4s ease;
}
.ring-inner{
  position:absolute;inset:0;
  display:flex;flex-direction:column;align-items:center;justify-content:center;
}
.ring-pct{font-size:12px;font-weight:700;line-height:1}
.ring-lbl{font-size:8px;color:var(--sub);margin-top:1px;letter-spacing:.2px}

/* ── card text ── */
.info{flex:1;min-width:0}
.info-label{font-size:10px;font-weight:500;text-transform:uppercase;letter-spacing:.5px;color:var(--sub);margin-bottom:5px}
.info-rem{font-size:23px;font-weight:700;line-height:1;letter-spacing:-.5px}
.info-rem em{font-size:13px;font-weight:500;font-style:normal;color:var(--sub)}
.info-reset{font-size:11px;color:var(--sub);margin-top:4px}

/* ── footer ── */
.footer{display:flex;align-items:center;justify-content:space-between;padding-top:1px}
.ts{font-size:11px;color:var(--sub)}
.btns{display:flex;gap:6px}
button{
  font-family:inherit;font-size:12px;font-weight:500;
  padding:5px 13px;border-radius:7px;border:none;
  background:var(--btn);color:var(--text);cursor:pointer;
  -webkit-appearance:none;transition:background .12s,opacity .12s;
}
button:hover{background:var(--btn-h)}
button:disabled{opacity:.4;cursor:default}
.primary{background:var(--accent);color:#fff}
.primary:hover{opacity:.85}

/* ── error ── */
.err{
  display:none;padding:9px 11px;border-radius:9px;
  background:rgba(255,59,48,.1);color:#ff3b30;
  font-size:11px;line-height:1.45;
}
</style>
</head>
<body>
<div class="wrap">

  <div class="hdr">
    <div class="logo">C</div>
    Claude Usage
  </div>

  <!-- session card -->
  <div class="card">
    <div class="ring-wrap">
      <svg width="58" height="58" viewBox="0 0 58 58">
        <circle class="track" cx="29" cy="29" r="22.5"/>
        <circle class="arc" id="s-arc" cx="29" cy="29" r="22.5"/>
      </svg>
      <div class="ring-inner">
        <div class="ring-pct" id="s-rpct">-</div>
        <div class="ring-lbl">used</div>
      </div>
    </div>
    <div class="info">
      <div class="info-label">Session &middot; 5-hour window</div>
      <div class="info-rem" id="s-rem">-<em>% left</em></div>
      <div class="info-reset" id="s-reset">Resets in -</div>
    </div>
  </div>

  <!-- weekly card -->
  <div class="card">
    <div class="ring-wrap">
      <svg width="58" height="58" viewBox="0 0 58 58">
        <circle class="track" cx="29" cy="29" r="22.5"/>
        <circle class="arc" id="w-arc" cx="29" cy="29" r="22.5"/>
      </svg>
      <div class="ring-inner">
        <div class="ring-pct" id="w-rpct">-</div>
        <div class="ring-lbl">used</div>
      </div>
    </div>
    <div class="info">
      <div class="info-label">Weekly &middot; 7-day window</div>
      <div class="info-rem" id="w-rem">-<em>% left</em></div>
      <div class="info-reset" id="w-reset">Resets -</div>
    </div>
  </div>

  <div class="err" id="err"></div>

  <div class="footer">
    <span class="ts" id="ts">-</span>
    <div class="btns">
      <button onclick="doQuit()">Quit</button>
      <button class="primary" id="ref-btn" onclick="doRefresh()">Refresh</button>
    </div>
  </div>

</div>
<script>
const C = 2 * Math.PI * 22.5;

function color(u) {
  if (u < 60)  return '#34C759';
  if (u < 85)  return '#FF9500';
  return '#FF3B30';
}

function initArc(id) {
  const el = document.getElementById(id);
  el.style.strokeDasharray = C;
  el.style.strokeDashoffset = C;
  el.style.stroke = 'var(--sep)';
}

function setArc(id, used) {
  const el = document.getElementById(id);
  el.style.strokeDasharray = C;
  el.style.strokeDashoffset = C * (1 - Math.min(used, 100) / 100);
  el.style.stroke = color(used);
}

function updateUsage(d) {
  document.getElementById('err').style.display = 'none';
  const su = d.session_pct_used, sr = Math.round(100 - su);
  const wu = d.weekly_pct_used,  wr = Math.round(100 - wu);

  setArc('s-arc', su);
  document.getElementById('s-rpct').textContent  = Math.round(su) + '%';
  document.getElementById('s-rem').innerHTML     = sr + '<em>% left</em>';
  document.getElementById('s-reset').textContent = 'Resets in ' + d.session_countdown;

  setArc('w-arc', wu);
  document.getElementById('w-rpct').textContent  = Math.round(wu) + '%';
  document.getElementById('w-rem').innerHTML     = wr + '<em>% left</em>';
  document.getElementById('w-reset').textContent = 'Resets ' + d.weekly_resets_str;

  document.getElementById('ts').textContent = 'Updated ' + d.updated_at;
  const b = document.getElementById('ref-btn');
  b.textContent = 'Refresh'; b.disabled = false;
}

function showError(msg) {
  const el = document.getElementById('err');
  el.style.display = 'block';
  el.textContent   = '⚠\u2009' + msg;
  const b = document.getElementById('ref-btn');
  b.textContent = 'Refresh'; b.disabled = false;
}

function doRefresh() {
  const b = document.getElementById('ref-btn');
  b.textContent = '…'; b.disabled = true;
  window.webkit.messageHandlers.refresh.postMessage('');
}
function doQuit() {
  window.webkit.messageHandlers.quit.postMessage('');
}

initArc('s-arc');
initArc('w-arc');
</script>
</body>
</html>
"""


# ── helpers ───────────────────────────────────────────────────────────────────


def _fmt(m):
    if m is None:
        return "?"
    m = max(0, int(m))
    return f"{m}m" if m < 60 else f"{m // 60}h{m % 60:02d}m"


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
        self._cb(msg.name())


# ── main app delegate ─────────────────────────────────────────────────────────


class AppDelegate(NSObject):
    def applicationDidFinishLaunching_(self, _):
        self._lock = threading.Lock()
        self._ready = False  # page loaded flag
        self._pending = None  # payload buffered before page ready

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
        self._item = AppKit.NSStatusBar.systemStatusBar().statusItemWithLength_(
            AppKit.NSVariableStatusItemLength
        )
        btn = self._item.button()
        btn.setTitle_("Claude …")
        btn.setTarget_(self)
        btn.setAction_("onStatusClick:")
        btn.sendActionOn_(AppKit.NSEventMaskLeftMouseDown)

    def onStatusClick_(self, sender):
        if self._pop.isShown():
            self._pop.close()
        else:
            btn = self._item.button()
            self._pop.showRelativeToRect_ofView_preferredEdge_(
                btn.bounds(), btn, AppKit.NSRectEdgeMinY
            )

    # ── popover + webview ──────────────────────────────────────────────────

    @objc.python_method
    def _build_popover(self):
        cfg = WebKit.WKWebViewConfiguration.alloc().init()
        ucc = WebKit.WKUserContentController.alloc().init()

        self._jsh = _JSHandler.alloc().initWithCallback_(self._on_js)
        ucc.addScriptMessageHandler_name_(self._jsh, "refresh")
        ucc.addScriptMessageHandler_name_(self._jsh, "quit")
        cfg.setUserContentController_(ucc)

        frame = AppKit.NSMakeRect(0, 0, 300, 290)
        self._wv = WebKit.WKWebView.alloc().initWithFrame_configuration_(frame, cfg)
        self._wv.setNavigationDelegate_(self)
        # transparent background so card shadow looks right
        self._wv.setValue_forKey_(False, "drawsBackground")
        self._wv.loadHTMLString_baseURL_(HTML, None)

        vc = AppKit.NSViewController.alloc().init()
        vc.setView_(self._wv)

        self._pop = AppKit.NSPopover.alloc().init()
        self._pop.setContentSize_(AppKit.NSMakeSize(300, 290))
        self._pop.setContentViewController_(vc)
        self._pop.setBehavior_(AppKit.NSPopoverBehaviorTransient)

    def webView_didFinishNavigation_(self, wv, nav):
        self._ready = True
        if self._pending is not None:
            self._push(self._pending)
            self._pending = None

    @objc.python_method
    def _on_js(self, name):
        if name == "refresh":
            threading.Thread(target=self._fetch, daemon=True).start()
        elif name == "quit":
            AppKit.NSApplication.sharedApplication().terminate_(None)

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

            title = f"Claude  S:{s_rem:.0f}%  W:{w_rem:.0f}%  |  {cd}"
            payload = {
                "session_pct_used": d.session_pct_used,
                "weekly_pct_used": d.weekly_pct_used,
                "session_countdown": cd,
                "weekly_resets_str": wstr or "-",
                "updated_at": datetime.now().strftime("%H:%M:%S"),
            }
            NSOperationQueue.mainQueue().addOperationWithBlock_(
                lambda: self._apply(title, payload)
            )
        except Exception as exc:
            msg = str(exc)
            NSOperationQueue.mainQueue().addOperationWithBlock_(
                lambda: self._apply_err(msg)
            )
        finally:
            self._lock.release()

    @objc.python_method
    def _apply(self, title, payload):
        self._item.button().setTitle_(title)
        if self._ready:
            self._push(payload)
        else:
            self._pending = payload

    @objc.python_method
    def _push(self, payload):
        js = f"updateUsage({json.dumps(payload)});"
        self._wv.evaluateJavaScript_completionHandler_(js, None)

    @objc.python_method
    def _apply_err(self, msg):
        self._item.button().setTitle_("Claude ⚠")
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
