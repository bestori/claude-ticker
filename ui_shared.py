"""
Shared UI constants used by both the macOS (app.py) and Windows (app_windows.py) builds.

HTML is a self-contained popup page with SVG arc rings.
The JS bridge uses _post() which detects the host at runtime:
  - macOS  → window.webkit.messageHandlers
  - Windows → window.pywebview.api
"""


def _fmt(m):
    if m is None:
        return "?"
    m = max(0, int(m))
    return f"{m}m" if m < 60 else f"{m // 60}h{m % 60:02d}m"


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
  width:320px;height:290px;overflow:hidden;
  background:var(--bg);
  font-family:-apple-system,"SF Pro Text",BlinkMacSystemFont,"Segoe UI",sans-serif;
  color:var(--text);font-size:14px;
  -webkit-font-smoothing:antialiased;
  user-select:none;-webkit-user-select:none;
}

.wrap{padding:14px 14px 12px;display:flex;flex-direction:column;gap:9px;height:100%}

/* ── header ── */
.hdr{display:flex;align-items:center;gap:8px;font-size:16px;font-weight:600}
.logo{
  width:24px;height:24px;border-radius:6px;
  background:linear-gradient(135deg,#cc785c,#e8956d);
  display:flex;align-items:center;justify-content:center;
  color:#fff;font-size:13px;font-weight:700;flex-shrink:0;
}

/* ── cards ── */
.card{
  background:var(--card);border-radius:11px;
  padding:12px 14px;display:flex;align-items:center;gap:13px;
  box-shadow:0 1px 3px rgba(0,0,0,.06);
}

/* ── ring ── */
.ring-wrap{position:relative;width:62px;height:62px;flex-shrink:0}
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
.ring-pct{font-size:13px;font-weight:700;line-height:1}
.ring-lbl{font-size:9px;color:var(--sub);margin-top:2px;letter-spacing:.2px}

/* ── card text ── */
.info{flex:1;min-width:0}
.info-label{font-size:11px;font-weight:500;text-transform:uppercase;letter-spacing:.5px;color:var(--sub);margin-bottom:5px}
.info-rem{font-size:27px;font-weight:700;line-height:1;letter-spacing:-.5px}
.info-rem em{font-size:15px;font-weight:500;font-style:normal;color:var(--sub)}
.info-reset{font-size:13px;color:var(--sub);margin-top:5px}

/* ── footer ── */
.footer{display:flex;align-items:center;justify-content:space-between;padding-top:1px}
.ts{font-size:12px;color:var(--sub)}
.btns{display:flex;gap:6px}
button{
  font-family:inherit;font-size:13px;font-weight:500;
  padding:5px 14px;border-radius:7px;border:none;
  background:var(--btn);color:var(--text);cursor:pointer;
  -webkit-appearance:none;transition:background .12s,opacity .12s;
}
button:hover{background:var(--btn-h)}
button:disabled{opacity:.4;cursor:default}
.primary{background:var(--accent);color:#fff}
.primary:hover{opacity:.85}
.sz-btn{font-size:12px;padding:4px 10px;color:var(--text);background:var(--btn);border-radius:6px;font-weight:600}

/* ── error ── */
.err{
  display:none;padding:9px 11px;border-radius:9px;
  background:rgba(255,59,48,.1);color:#ff3b30;
  font-size:11px;line-height:1.45;
}

/* ── auth screen (not logged in) ── */
.auth-screen{
  display:none;flex:1;flex-direction:column;align-items:center;justify-content:center;
  gap:14px;text-align:center;
}
.auth-screen .auth-msg{font-size:13px;color:var(--sub);line-height:1.5}
.auth-screen .auth-login{font-size:14px;padding:8px 24px}
</style>
</head>
<body>
<div class="wrap">

  <div class="hdr">
    <div class="logo">C</div>
    Claude Usage
  </div>

  <div id="cards">
    <!-- session card -->
    <div class="card" style="margin-bottom:9px">
      <div class="ring-wrap">
        <svg width="62" height="62" viewBox="0 0 62 62">
          <circle class="track" cx="31" cy="31" r="24"/>
          <circle class="arc" id="s-arc" cx="31" cy="31" r="24"/>
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
        <svg width="62" height="62" viewBox="0 0 62 62">
          <circle class="track" cx="31" cy="31" r="24"/>
          <circle class="arc" id="w-arc" cx="31" cy="31" r="24"/>
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
  </div>

  <!-- auth screen: shown instead of cards when not logged in -->
  <div class="auth-screen" id="auth-screen">
    <div class="auth-msg" id="auth-msg">Not logged in to Claude.<br>Sign in in your browser, then click Refresh.</div>
    <button class="primary auth-login" onclick="doLogin()">Log in to Claude</button>
  </div>

  <div class="err" id="err"></div>

  <div class="footer">
    <div class="btns" id="scale-btns">
      <button class="sz-btn" onclick="changeScale(-0.1)" title="Smaller">A−</button>
      <button class="sz-btn" onclick="changeScale(0.1)"  title="Larger">A+</button>
      <span class="ts" id="ts">-</span>
    </div>
    <div class="btns" id="footer-btns">
      <button onclick="doQuit()">Quit</button>
      <button class="primary" id="ref-btn" onclick="doRefresh()">Refresh</button>
    </div>
  </div>

</div>
<script>
const C = 2 * Math.PI * 24;

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

function _showCards(yes) {
  document.getElementById('cards').style.display = yes ? 'block' : 'none';
  document.getElementById('auth-screen').style.display = yes ? 'none' : 'flex';
  document.getElementById('scale-btns').style.visibility = yes ? 'visible' : 'hidden';
  document.getElementById('footer-btns').style.display = yes ? 'flex' : 'none';
}

function updateUsage(d) {
  hasData = true;
  _showCards(true);
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
  const b = document.getElementById('ref-btn');
  b.textContent = 'Refresh'; b.disabled = false;
  const isAuth = msg.startsWith('AUTH:');
  const displayMsg = isAuth ? msg.slice(5) : msg;
  if (isAuth) {
    _showCards(false);
    document.getElementById('ts').textContent = '';
  } else if (hasData) {
    const ts = document.getElementById('ts');
    const short = displayMsg.length > 50 ? displayMsg.slice(0, 47) + '…' : displayMsg;
    ts.textContent = '⚠ ' + short;
    ts.title = displayMsg;
  } else {
    const el = document.getElementById('err');
    el.style.display = 'block';
    el.textContent = '⚠ ' + displayMsg;
  }
}

/* Platform-agnostic bridge: WKWebView on macOS, pywebview on Windows */
function _post(name, val) {
  if (window.webkit && window.webkit.messageHandlers) {
    window.webkit.messageHandlers[name].postMessage(val != null ? String(val) : '');
  } else if (window.pywebview) {
    if (val != null) window.pywebview.api[name](val);
    else window.pywebview.api[name]();
  }
}

function doRefresh() {
  const b = document.getElementById('ref-btn');
  b.textContent = '…'; b.disabled = true;
  _post('refresh');
}
function doQuit() { _post('quit'); }
function doLogin() { _post('login'); }

initArc('s-arc');
initArc('w-arc');

let hasData = false;
let scale = 1.0;
function changeScale(delta) {
  scale = Math.round(Math.max(0.7, Math.min(1.5, scale + delta)) * 10) / 10;
  document.documentElement.style.zoom = scale;
  _post('scale', scale);
}
</script>
</body>
</html>
"""
