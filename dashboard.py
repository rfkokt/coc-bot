#!/usr/bin/env python3
"""Web dashboard COC bot: status jalan/mati + edit threshold + start/stop.
Stdlib only (http.server) — ga nambah dependency.
Jalanin:  venv/bin/python dashboard.py   → buka http://localhost:8787
"""
import http.server, json, os, re, signal, subprocess, sys, time, urllib.parse, threading, uuid
from coc_analyzer import analyze
from research import generate_deep_research
import research_config
import stats
import db

db.init_db()  # bikin tabel kalau DB ada

# ── Registry task deep-research (jalan di background thread) ──────────────
_RESEARCH_TASKS = {}  # session_id -> {status, phase, events, result, error, query, started}
_RESEARCH_LOCK = threading.Lock()


def _run_research_task(session_id, question):
    """Jalanin LiveResearcher di background, update registry per progress event."""
    from research_engine import LiveResearcher
    from research_config import load_config

    def on_progress(ev):
        with _RESEARCH_LOCK:
            t = _RESEARCH_TASKS.get(session_id)
            if t is not None:
                t["phase"] = ev.get("phase", t.get("phase"))
                t["events"].append(ev)
                t["events"] = t["events"][-40:]  # cap

    try:
        cfg = load_config()
        result = LiveResearcher(cfg, on_progress).research(question)
        with _RESEARCH_LOCK:
            t = _RESEARCH_TASKS.get(session_id)
            if t is not None:
                t["status"] = "done"
                t["result"] = result
                # auto-simpan ke DB (best-effort)
                meta = t.get("meta") or {}
                db.save_research(meta.get("account_id"), meta.get("account_name"),
                                 meta.get("th_level"), question, result)
    except Exception as e:
        with _RESEARCH_LOCK:
            t = _RESEARCH_TASKS.get(session_id)
            if t is not None:
                t["status"] = "error"
                t["error"] = str(e)

def _build_account_question(th, analysis):
    """Bikin pertanyaan research yg SPESIFIK ke kondisi akun — bukan generik.

    Ambil item yg belum max (recs cur<max) + gap hero/equip dari analysis,
    biar research nyari cara upgrade yg relevan buat akun ini.
    """
    year = time.strftime("%Y")
    recs = analysis.get("recs") or []
    # item belum max, kelompokin per kategori
    unmaxed = [r for r in recs if isinstance(r, dict) and r.get("cur", 0) < r.get("max", 0)]
    # dedup by name, ambil yg paling "ketinggalan" (gap terbesar) dulu
    seen, priority = set(), []
    for r in sorted(unmaxed, key=lambda x: (x.get("max", 0) - x.get("cur", 0)), reverse=True):
        nm = r.get("name")
        if nm and nm not in seen:
            seen.add(nm)
            priority.append(f"{nm} (lvl {r.get('cur',0)}/{r.get('max',0)})")
    top = priority[:12]

    summ = analysis.get("summary") or {}
    hero_gap = summ.get("heroes_gap", 0)
    equip_gap = summ.get("equip_gap", 0)

    parts = [f"I play Clash of Clans at Town Hall {th}."]
    if top:
        parts.append("These structures/troops are NOT yet maxed and need upgrading: "
                     + ", ".join(top) + ".")
    if hero_gap:
        parts.append(f"My heroes are {hero_gap} total levels below max.")
    if equip_gap:
        parts.append(f"My hero equipment is {equip_gap} total levels below max.")
    parts.append(
        f"Based on the current {year} meta, research the optimal UPGRADE PRIORITY ORDER "
        f"for exactly these items, which upgrades give the biggest offense/defense impact "
        f"first, the best attack strategies that use what I already have, hero equipment "
        f"upgrade order, and the fastest way to farm the resources these specific upgrades cost. "
        f"Be specific to my account state above, not generic TH{th} advice."
    )
    return " ".join(parts)

HERE = os.path.dirname(os.path.abspath(__file__))
PID_FILE = os.path.join(HERE, "bot.pid")
LOG_FILE = os.path.join(HERE, "bot_run.log")
CONFIG   = os.path.join(HERE, "config.py")
PYTHON   = os.path.join(HERE, "venv", "bin", "python")
PORT     = 8787

# ADB config dibaca dari config.py biar konsisten sama bot
sys.path.insert(0, HERE)
from config import ADB_PATH, _detect_device

def adb_status():
    """Cek koneksi ADB ke emulator. Resolve device LIVE tiap panggil
    biar kembali ke life saat BlueStacks restart/ganti port."""
    try:
        dev = _detect_device()  # cek devices + coba adb connect port BlueStacks
        out = subprocess.run([ADB_PATH, "-s", dev, "get-state"],
                             capture_output=True, text=True, timeout=5)
        if out.stdout.strip() == "device":
            return True, f"Terhubung ({dev})"
        err = (out.stderr or out.stdout).strip() or "device tidak ditemukan"
        return False, f"Tidak terhubung: {err}"
    except FileNotFoundError:
        return False, f"ADB tidak ada: {ADB_PATH}"
    except subprocess.TimeoutExpired:
        return False, "ADB timeout — BlueStacks jalan?"
    except Exception as e:
        return False, f"Error: {e}"

# setting yg boleh diedit dari web: nama di config.py → label
EDITABLE = {
    "GOLD_MIN": "Gold minimum",
    "ELIXIR_MIN": "Elixir minimum",
    "DARK_MIN": "Dark minimum",
    "STAR1_DAMAGE": "Damage bintang 1 (%)",
    "BATTLE_SECS": "Battle timeout (detik)",
}

def bot_pid():
    """pid bot kalau masih hidup, else None. Bersihkan orphan PID file."""
    if os.path.exists(PID_FILE):
        try:
            pid = int(open(PID_FILE).read().strip())
            os.kill(pid, 0)
            return pid
        except (ValueError, ProcessLookupError, PermissionError):
            pass  # process mati atau file corrupt → cleanup
        os.remove(PID_FILE)
    return None

def read_settings():
    """Baca nilai EDITABLE dari config.py via regex (angka, boleh _ pemisah ribuan)."""
    txt = open(CONFIG).read()
    out = {}
    for key in EDITABLE:
        m = re.search(rf"^{key}\s*=\s*([\d_]+)", txt, re.M)
        out[key] = int(m.group(1).replace("_", "")) if m else None
    return out

def write_setting(key, value):
    """Patch satu baris `KEY = ...` di config.py, ga sentuh komentar/struktur lain."""
    if key not in EDITABLE:
        raise ValueError("key tak dikenal")
    value = int(value)  # raise kalau bukan angka → validasi input
    txt = open(CONFIG).read()
    new, n = re.subn(rf"^({key}\s*=\s*)[\d_]+", rf"\g<1>{value}", txt, count=1, flags=re.M)
    if n != 1:
        raise ValueError(f"{key} tak ditemukan di config.py")
    open(CONFIG, "w").write(new)

def tail_log(n=40):
    if not os.path.exists(LOG_FILE):
        return "(belum ada log)"
    lines = open(LOG_FILE, errors="replace").read().splitlines()
    return "\n".join(lines[-n:])

def start_bot(ignore_schedule=False, mode="normal"):
    # cek ulang setelah acquire lock biar exclude race condition
    pid = bot_pid()
    if pid:
        return "Bot sudah jalan."
    # pre-flight: pastikan konek ke BlueStacks dulu
    ok, msg = adb_status()
    if not ok:
        return f"⛔ Gagal start — {msg}"
    env = dict(os.environ)
    for _k in [k for k in env if k.startswith("Malloc")]:
        del env[_k]   # buang Malloc* env — bikin noise "MallocStackLogging..." di log, ga ngaruh ke bot
    if ignore_schedule:
        env["COC_IGNORE_SCHEDULE"] = "1"
    env["COC_MODE"] = mode
    log = open(LOG_FILE, "w")
    proc = subprocess.Popen([PYTHON, "-u", "bot.py"], cwd=HERE, stdout=log, stderr=log, env=env, start_new_session=True)
    # tunggu subprocess tulis PID ke bot.pid (max 3s)
    for _ in range(30):
        time.sleep(0.1)
        pid = bot_pid()
        if pid:
            return "Bot distart."
    return "Bot distart (PID belum tercatat — cek log)."

def stop_bot():
    pid = bot_pid()
    if not pid:
        return "Bot tidak jalan."
    try:
        # kill seluruh process group (bot spawn subprocess), fallback ke SIGKILL
        try:
            os.killpg(os.getpgid(pid), signal.SIGTERM)
        except ProcessLookupError:
            pass  # process sudah mati
        except PermissionError:
            try:
                os.kill(pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        # cleanup file
        if os.path.exists(PID_FILE):
            os.remove(PID_FILE)
        return f"Bot dihentikan (pid {pid})."
    except Exception as e:
        return f"Gagal stop: {e}"

PAGE = """<!doctype html><meta charset=utf-8><title>COC Bot</title>
<meta name=viewport content="width=device-width,initial-scale=1">
<style>
  body{{font:15px system-ui,sans-serif;max-width:760px;margin:24px auto;padding:0 16px;background:#12141a;color:#e6e6e6}}
  h1{{font-size:20px}} .card{{background:#1c1f28;border:1px solid #2b2f3a;border-radius:10px;padding:16px;margin:14px 0}}
  .dot{{display:inline-block;width:11px;height:11px;border-radius:50%;margin-right:7px;vertical-align:middle}}
  .on{{background:#3ddc84}} .off{{background:#e5534b}} .sleep{{background:#e0b341}}
  button{{background:#2f6feb;color:#fff;border:0;border-radius:7px;padding:9px 16px;font-size:14px;cursor:pointer;margin-right:8px}}
  button.stop{{background:#e5534b}} button.test{{background:#8957e5}}
  button:disabled{{opacity:.4;cursor:not-allowed}}
  label{{display:block;margin:10px 0 3px;font-size:13px;color:#9aa4b2}}
  input{{background:#0e1015;border:1px solid #2b2f3a;color:#e6e6e6;border-radius:6px;padding:8px;width:180px}}
  pre{{background:#0e1015;border:1px solid #2b2f3a;border-radius:8px;padding:12px;overflow:auto;max-height:340px;font-size:12px;white-space:pre-wrap}}
  .st{{font-size:17px;font-weight:600}}
</style>
<h1>🏰 COC Bot Dashboard</h1>
<p style="margin:0 0 14px"><a href=/analyze style="color:#8ab4f8;font-size:14px">⚔️ Village Analyzer — Rekomendasi upgrade & strategi</a></p>
<div class=card>
  <div class=st id=adb_st><span class="dot {adbcls}"></span>ADB {adbmsg}</div>
  <p style="margin:8px 0 0;color:#9aa4b2;font-size:13px">BlueStacks harus nyala &amp; ADB nyambung sebelum start. <a href="/" style=color:#2f6feb>refresh</a></p>
</div>
<div class=card>
  <div class=st id=bot_st><span class="dot {dotcls}"></span>{status}</div>
  <p style="margin:12px 0 0">
    <button id=start_btn onclick="act('start')" {startdis}>▶ Start</button>
    <button class=test id=start_test_btn onclick="act('start_test')" {startdis}>🧪 Start (abaikan jadwal)</button>
    <button class=test id=start_loot_btn onclick="act('start_loot')" {startdis} style=background:#c9791b>💰 Start (force loot)</button>
    <button class=stop id=stop_btn onclick="act('stop')" {stopdis}>■ Stop</button>
  </p>
  <p id=msg style="color:#9aa4b2;font-size:13px;margin:8px 0 0;min-height:18px"></p>
</div>
<div class=card>
  <b>📊 Lifetime Stats</b>
  <div class=summary-grid id=stats style="margin-top:12px">{statsgrid}</div>
</div>
<div class=card>
  <b>⚙️ Settings</b>
  <form onsubmit="return save(event)">{fields}
    <p style="margin-top:14px"><button type=submit>💾 Simpan</button>
    <span style="color:#9aa4b2;font-size:13px">(restart bot buat apply)</span></p>
  </form>
</div>
<div class=card>
  <b>📜 Log</b> <span style="color:#9aa4b2;font-size:12px">(auto-refresh 3s)</span>
  <pre id=log>{log}</pre>
</div>
<script>
async function act(a){{const m=document.getElementById('msg');m.textContent='...';
  const r=await fetch('/action?a='+a,{{method:'POST'}});m.textContent=await r.text();
  setTimeout(()=>location.reload(),1200)}}
async function save(e){{e.preventDefault();const f=new FormData(e.target);
  const b=new URLSearchParams();for(const[k,v]of f)b.append(k,v);
  await fetch('/save',{{method:'POST',body:b}});alert('Tersimpan');location.reload();return false}}
setInterval(async()=>{{
  const lr=await fetch('/log');const el=document.getElementById('log');
  el.textContent=await lr.text();el.scrollTop=el.scrollHeight;
  // ponytail: refresh status+buttons tiap cycle biar ga basi saat bot start/stop dari luar
  const s=await(await fetch('/state')).json();
  document.getElementById('adb_st').innerHTML='<span class="dot '+s.adbcls+'"></span>ADB '+s.adbmsg;
  document.getElementById('bot_st').innerHTML='<span class="dot '+s.dotcls+'"></span>'+s.status;
  document.getElementById('start_btn').disabled=s.running;
  document.getElementById('start_test_btn').disabled=s.running;
  document.getElementById('start_loot_btn').disabled=s.running;
  document.getElementById('stop_btn').disabled=!s.running;
  document.getElementById('stats').innerHTML=s.statsgrid;
}},3000);
// scroll ke bawah pas load pertama
window.addEventListener('load',()=>{{const el=document.getElementById('log');el.scrollTop=el.scrollHeight}});
</script>
"""

def state():
    """Status live: dipakai render() awal + endpoint /state (auto-refresh)."""
    pid = bot_pid()
    log = tail_log()
    adb_ok, adb_msg = adb_status()
    adbcls = "on" if adb_ok else "off"
    if pid:
        # "tidur" kalau baris log terakhir nyebut di luar jam aktif
        sleeping = "luar jam aktif" in log.lower().split("\n")[-1] if log else False
        status = f"Tidur — di luar jam aktif (pid {pid})" if sleeping else f"Jalan (pid {pid})"
        dotcls = "sleep" if sleeping else "on"
    else:
        status, dotcls = "Mati", "off"
    return dict(status=status, dotcls=dotcls, adbcls=adbcls, adbmsg=adb_msg,
                running=pid is not None, statsgrid=stats_grid())

_player_cache = {}
def lookup_player(tag):
    """Nama akun dari player tag via ClashKing proxy (no auth, no CORS issue).
    Return {"name":..,"tag":..,"th":..} atau {"error":..}. Cache in-memory."""
    import urllib.request, ssl
    tag = tag.strip().upper()
    if not tag:
        return {"error": "tag kosong"}
    if not tag.startswith("#"):
        tag = "#" + tag
    if tag in _player_cache:
        return _player_cache[tag]
    try:
        import certifi
        ctx = ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        ctx = ssl._create_unverified_context()   # ponytail: mac tanpa certifi, fallback
    url = "https://proxy.clashk.ing/v1/players/" + urllib.parse.quote(tag)
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        d = json.load(urllib.request.urlopen(req, context=ctx, timeout=10))
        res = {"name": d.get("name"), "tag": d.get("tag", tag), "th": d.get("townHallLevel")}
        _player_cache[tag] = res
        return res
    except Exception as e:
        return {"error": str(e)}

def stats_grid():
    """HTML grid stats lifetime — dipakai render() awal + endpoint /state."""
    accounts = stats.load().get("accounts", {})
    if not accounts:
        return '<div class=summary-item><div class=summary-label>Belum ada data</div></div>'

    def fmt_dur(secs):
        h, m = divmod(int(secs) // 60, 60)
        return f"{h}j {m}m" if h else f"{m}m"

    blocks = []
    for name, s in sorted(accounts.items()):
        items = [("Serangan", f'{s.get("attacks",0):,}'),
                 ("Gold", f'{s.get("gold",0):,}'),
                 ("Elixir", f'{s.get("elixir",0):,}'),
                 ("Dark", f'{s.get("dark",0):,}'),
                 ("Durasi", fmt_dur(s.get("seconds",0)))]
        grid = "".join(
            f'<div class=summary-item><div class=summary-num>{v}</div>'
            f'<div class=summary-label>{lbl}</div></div>' for lbl, v in items)
        blocks.append(f'<div style="grid-column:1/-1;font-weight:600;color:#8ab4f8;margin:8px 0 2px">{name}</div>{grid}')
    return "".join(blocks)


def render():
    st = state()
    startdis = "disabled" if st["running"] else ""
    stopdis = "" if st["running"] else "disabled"
    s = read_settings()
    fields = "".join(
        f'<label>{lbl}</label><input name="{k}" value="{s[k] if s[k] is not None else ""}">'
        for k, lbl in EDITABLE.items())
    return PAGE.format(fields=fields, log=tail_log(),
                       startdis=startdis, stopdis=stopdis,
                       statsgrid=stats_grid(), **{k: v for k, v in st.items() if k != "statsgrid"})

ANALYZE_PAGE = '''<!doctype html><meta charset=utf-8><title>COC Village Analyzer</title>
<meta name=viewport content="width=device-width,initial-scale=1">
<style>
  body{font:15px system-ui,sans-serif;max-width:900px;margin:24px auto;padding:0 16px;background:#12141a;color:#e6e6e6}
  h1{font-size:20px} h2{font-size:16px;margin:20px 0 8px;color:#8ab4f8}
  .card{background:#1c1f28;border:1px solid #2b2f3a;border-radius:10px;padding:16px;margin:14px 0}
  textarea{width:100%;height:200px;background:#0e1015;border:1px solid #2b2f3a;color:#e6e6e6;border-radius:8px;padding:12px;font-size:12px;font-family:monospace;resize:vertical}
  button{background:#2f6feb;color:#fff;border:0;border-radius:7px;padding:12px 24px;font-size:15px;font-weight:600;cursor:pointer;transition:all .15s}
  button:hover{background:#4a8aff;transform:translateY(-1px)}
  button:disabled{opacity:.4;cursor:not-allowed;transform:none}
  .btn-row{display:flex;gap:10px;align-items:center;margin-top:12px;flex-wrap:wrap}
  .file-btn{background:#1c1f28;border:1px solid #2b2f3a;padding:8px 14px;font-size:13px;font-weight:400}
  .file-btn:hover{background:#2b2f3a}
  input[type=file]{display:none}
  table{width:100%;border-collapse:collapse;font-size:13px}
  th{text-align:left;padding:8px 6px;border-bottom:1px solid #2b2f3a;color:#9aa4b2;font-weight:500}
  td{padding:8px 6px;border-bottom:1px solid #1c1f28}
  .bar{height:6px;background:#2b2f3a;border-radius:3px;overflow:hidden;display:inline-block;width:80px;vertical-align:middle}
  .bar-fill{height:100%;border-radius:3px;background:#3ddc84}
  .bar-low{background:#e5534b}
  .tag{display:inline-block;padding:2px 8px;border-radius:4px;font-size:11px;font-weight:600}
  .tag-ready{background:#1a3a2a;color:#3ddc84}
  .tag-warn{background:#3a2a1a;color:#e0b341}
  .tag-hero{background:#2a1a3a;color:#b488f8}
  .tag-bldg{background:#1a2a3a;color:#68b8f8}
  .tag-equip{background:#3a1a2a;color:#f888b4}
  .summary-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:12px}
  .summary-item{background:#0e1015;border-radius:8px;padding:14px;text-align:center}
  .summary-num{font-size:28px;font-weight:700;color:#8ab4f8}
  .summary-label{font-size:12px;color:#9aa4b2;margin-top:4px}
  a{color:#2f6feb;text-decoration:none} a:hover{text-decoration:underline}
  .strat-card{background:#0e1015;border-radius:8px;padding:14px;margin:8px 0}
  .strat-name{font-weight:600;font-size:15px}
  .strat-desc{color:#9aa4b2;font-size:13px;margin-top:4px}
  .back{margin-bottom:16px}
</style>
<div class=back><a href=/>&larr; Dashboard</a></div>
<h1>⚔️ COC Village Analyzer</h1>
<div class=card>
  <p style=color:#9aa4b2;font-size:13px>Tempel JSON village export dari COC (clan profile / API). Bisa dari clashking atau export manual.</p>
  <form id=f onsubmit="event.preventDefault();doAnalyze()">
    <textarea id=json placeholder='Paste JSON village data here...'></textarea>
    <div class=btn-row>
      <button type=submit id=btn>🔍 Analyze</button>
      <label class="button file-btn" for=fileInput>📁 Load JSON File</label>
      <input type=file id=fileInput accept=.json onchange="loadFile(this)">
      <span id=err style="color:#e5534b;font-size:13px"></span>
    </div>
  </form>
</div>
<div id=result></div>
<script>
function loadFile(input){
  const f=input.files[0];if(!f)return;
  const r=new FileReader();
  r.onload=e=>{document.getElementById("json").value=e.target.result;doAnalyze()};
  r.readAsText(f);
}
async function doAnalyze(){
  const ta=document.getElementById("json"),btn=document.getElementById("btn"),err=document.getElementById("err"),res=document.getElementById("result");
  err.textContent="";btn.disabled=true;btn.textContent="Analyzing...";res.innerHTML="";
  try{
    const j=JSON.parse(ta.value);
    const r=await fetch("/api/analyze",{method:"POST",body:JSON.stringify(j),headers:{"Content-Type":"application/json"}});
    if(!r.ok)throw new Error(await r.text());
    res.innerHTML=renderResult(await r.json());
  }catch(e){err.textContent=e.message}
  btn.disabled=false;btn.textContent="🔍 Analyze";return false;
}
function pct(cur,max){return Math.round(cur/max*100)}
function bar(cur,max,cls){return `<span class=bar><span class="bar-fill ${cls||""}" style=width:${pct(cur,max)}%></span></span> ${pct(cur,max)}%`}
function renderResult(d){
  let h=`<div class=card><h2>🏰 Town Hall ${d.th_level}</h2>
  <div class=summary-grid>
    <div class=summary-item><div class=summary-num>${d.summary.heroes_gap}</div><div class=summary-label>Hero Level Gap</div></div>
    <div class=summary-item><div class=summary-num>${d.summary.equip_gap}</div><div class=summary-label>Equipment Level Gap</div></div>
    <div class=summary-item><div class=summary-num>${d.summary.upgrading_count}</div><div class=summary-label>Sedang Di-upgrade</div></div>
  </div></div>`;
  // Upgrading
  if(d.upgrading.length){
    h+=`<div class=card><h2>🔨 Sedang Di-upgrade</h2><table><tr><th>Building/Troop</th><th>Level</th></tr>`;
    d.upgrading.forEach(u=>{h+=`<tr><td>${u.name}</td><td>${u.lvl}</td></tr>`});
    h+=`</table></div>`;
  }
  // Hero recs
  const heroRecs=d.recs.filter(r=>r.cat==="hero");
  if(heroRecs.length){
    h+=`<div class=card><h2>👑 Hero Recommendations</h2><table><tr><th>Hero</th><th>Current</th><th>Max</th><th>Progress</th><th>Note</th></tr>`;
    heroRecs.forEach(r=>{const cls=r.gap>10?"bar-low":"";h+=`<tr><td><span class="tag tag-hero">${r.name}</span></td><td>${r.cur}</td><td>${r.max}</td><td>${bar(r.cur,r.max,cls)}</td><td>${r.note}</td></tr>`});
    h+=`</table></div>`;
  }
  // Building recs
  const bldgRecs=d.recs.filter(r=>r.cat==="building");
  if(bldgRecs.length){
    h+=`<div class=card><h2>🏗️ Building Recommendations</h2><table><tr><th>Building</th><th>Current</th><th>Max</th><th>Progress</th><th>Note</th></tr>`;
    bldgRecs.forEach(r=>{h+=`<tr><td><span class="tag tag-bldg">${r.name}</span></td><td>${r.cur}</td><td>${r.max}</td><td>${bar(r.cur,r.max)}</td><td>${r.note}</td></tr>`});
    h+=`</table></div>`;
  }
  // Equipment
  if(d.equip_recs.length){
    h+=`<div class=card><h2>⚡ Equipment (Top Upgrade Priority)</h2><table><tr><th>Equipment</th><th>Current</th><th>Max</th><th>Progress</th></tr>`;
    d.equip_recs.forEach(r=>{h+=`<tr><td><span class="tag tag-equip">${r.name}</span></td><td>${r.cur}</td><td>${r.max}</td><td>${bar(r.cur,r.max)}</td></tr>`});
    h+=`</table></div>`;
  }
  // Pets
  if(d.pet_recs.length){
    h+=`<div class=card><h2>🐾 Pets</h2><table><tr><th>Pet</th><th>Level</th><th>Max</th></tr>`;
    d.pet_recs.forEach(r=>{h+=`<tr><td>${r.name}</td><td>${r.cur}</td><td>${r.max}</td></tr>`});
    h+=`</table></div>`;
  }
  // Strategies
  if(d.strategies.length){
    h+=`<div class=card><h2>⚔️ Attack Strategies (TH${d.th_level})</h2>`;
    d.strategies.forEach(s=>{
      const cls=s.ready?"tag-ready":"tag-warn";
      h+=`<div class=strat-card><div class=strat-name>${s.name} <span class="tag ${cls}">${s.status}</span></div><div class=strat-desc>${s.desc}</div></div>`;
    });
    h+=`</div>`;
  }
  return h;
}
</script>'''

class H(http.server.BaseHTTPRequestHandler):
    def _send(self, body, ctype="text/html; charset=utf-8", code=200):
        b = body.encode() if isinstance(body, str) else body
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        path = urllib.parse.urlparse(self.path).path
        if path == "/":
            self._send(render())
        elif path == "/log":
            self._send(tail_log(), "text/plain; charset=utf-8")
        elif path == "/state":
            self._send(json.dumps(state()), "application/json")
        elif path == "/stats.json":
            self._send(json.dumps(stats.load()), "application/json")
        elif path.startswith("/api/player"):
            # Lookup nama akun dari player tag via ClashKing proxy (no auth).
            qs = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            tag = qs.get("tag", [""])[0]
            self._send(json.dumps(lookup_player(tag)), "application/json")
        elif path == "/analyze":
            self._send(ANALYZE_PAGE)
        elif path == "/api/db/accounts":
            self._send(json.dumps({"accounts": db.list_accounts()}), "application/json")
        elif path == "/api/db/loot":
            self._send(json.dumps({"loot": db.list_loot()}), "application/json")
        elif path == "/api/db/research":
            qs = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            acc = qs.get("account_id", [None])[0]
            self._send(json.dumps({"research": db.list_research(acc)}), "application/json")
        elif path == "/api/research/settings":
            self._send(json.dumps(research_config.public_config()), "application/json")
        elif path == "/api/research/models":
            try:
                from research_engine import list_models
                models = list_models(research_config.load_config())
                self._send(json.dumps({"models": models}), "application/json")
            except Exception as e:
                self._send(json.dumps({"models": [], "error": str(e)}), "application/json")
        elif path.startswith("/api/research/status/"):
            sid = path.rsplit("/", 1)[-1]
            with _RESEARCH_LOCK:
                t = _RESEARCH_TASKS.get(sid)
                snap = None if t is None else {
                    "status": t["status"], "phase": t.get("phase"),
                    "events": t["events"][-8:], "query": t.get("query"),
                    "result": t.get("result"), "error": t.get("error"),
                }
            if snap is None:
                self._send(json.dumps({"status": "not_found"}), "application/json", code=404)
            else:
                self._send(json.dumps(snap), "application/json")
        elif path.startswith("/api/proxy"):
            import urllib.request as urllib_req
            qs = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            img_url = qs.get("url", [""])[0]
            if img_url:
                try:
                    req = urllib_req.Request(img_url, headers={'User-Agent': 'Mozilla/5.0'})
                    with urllib_req.urlopen(req, timeout=5) as resp:
                        self.send_response(200)
                        self.send_header("Content-Type", resp.headers.get("Content-Type", "image/png"))
                        self.send_header("Cache-Control", "public, max-age=86400")
                        self.send_header("Access-Control-Allow-Origin", "*")
                        self.end_headers()
                        self.wfile.write(resp.read())
                        return
                except Exception:
                    pass
            self._send("Image not found", code=404)
        else:
            self._send("not found", code=404)
    def do_POST(self):
        path = urllib.parse.urlparse(self.path).path
        if path == "/action":
            a = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query).get("a", [""])[0]
            msg = {"start": lambda: start_bot(False),
                   "start_test": lambda: start_bot(True),
                   "start_loot": lambda: start_bot(True, mode="force_loot"),
                   "stop": stop_bot}.get(a, lambda: "aksi tak dikenal")()
            self._send(msg, "text/plain; charset=utf-8")
        elif path == "/save":
            n = int(self.headers.get("Content-Length", 0))
            form = urllib.parse.parse_qs(self.rfile.read(n).decode())
            try:
                for k, v in form.items():
                    write_setting(k, v[0])
                self._send("ok", "text/plain")
            except (ValueError, KeyError) as e:
                self._send(f"error: {e}", "text/plain", code=400)
        elif path == "/api/analyze":
            length = int(self.headers.get('Content-Length', 0))
            if length > 1024*1024:
                self._send('JSON too large', 'text/plain', code=413)
            else:
                try:
                    village = json.loads(self.rfile.read(length))
                    result = analyze(village)
                    self._send(json.dumps(result), "application/json")
                except json.JSONDecodeError as e:
                    self._send(f'Invalid JSON: {e}', 'text/plain', code=400)
                except Exception as e:
                    self._send(f'Analysis error: {e}', 'text/plain', code=500)
        elif path == "/api/research":
            length = int(self.headers.get('Content-Length', 0))
            if length > 1024*1024:
                self._send('Request too large', 'text/plain', code=413)
            else:
                try:
                    body = json.loads(self.rfile.read(length))
                    village = body.get('village')
                    if not village:
                        self._send('Missing village data', 'text/plain', code=400)
                        return
                    # First run normal analysis, then deep research
                    from coc_analyzer import analyze as coc_analyze
                    analysis = coc_analyze(village)
                    research = generate_deep_research(analysis)
                    research['analysis'] = analysis
                    self._send(json.dumps(research), "application/json")
                except json.JSONDecodeError as e:
                    self._send(f'Invalid JSON: {e}', 'text/plain', code=400)
                except Exception as e:
                    self._send(f'Research error: {e}', 'text/plain', code=500)
        elif path == "/api/db/sync":
            # Terima {accounts:[...]} dari frontend localStorage + sync loot dari stats.json.
            n = int(self.headers.get("Content-Length", 0))
            try:
                body = json.loads(self.rfile.read(n)) if n else {}
                na = db.upsert_accounts(body.get("accounts", []))
                import stats as _st
                nl = db.sync_loot(_st.load().get("accounts", {}))
                self._send(json.dumps({"accounts_saved": na, "loot_synced": nl}), "application/json")
            except Exception as e:
                self._send(f'Sync error: {e}', 'text/plain', code=400)
        elif path == "/api/db/research/save":
            # Simpan hasil research manual (CREATE). {account_id,account_name,th_level,query,result}
            n = int(self.headers.get("Content-Length", 0))
            try:
                b = json.loads(self.rfile.read(n))
                rid = db.save_research(b.get("account_id"), b.get("account_name"),
                                       b.get("th_level"), b.get("query"), b.get("result"))
                self._send(json.dumps({"id": rid}), "application/json")
            except Exception as e:
                self._send(f'Save error: {e}', 'text/plain', code=400)
        elif path == "/api/db/research/delete":
            # DELETE research by id. {id: N}
            n = int(self.headers.get("Content-Length", 0))
            try:
                b = json.loads(self.rfile.read(n))
                ok = db.delete_research(b.get("id"))
                self._send(json.dumps({"deleted": ok}), "application/json")
            except Exception as e:
                self._send(f'Delete error: {e}', 'text/plain', code=400)
        elif path == "/api/db/account/delete":
            # DELETE account by id. {id: "..."}
            n = int(self.headers.get("Content-Length", 0))
            try:
                b = json.loads(self.rfile.read(n))
                ok = db.delete_account(b.get("id"))
                self._send(json.dumps({"deleted": ok}), "application/json")
            except Exception as e:
                self._send(f'Delete error: {e}', 'text/plain', code=400)
        elif path == "/api/research/translate":
            # Translate report. {id: N, to: "id"} — cache di stats.translations
            n = int(self.headers.get("Content-Length", 0))
            try:
                b = json.loads(self.rfile.read(n))
                rid = b.get("id"); to = b.get("to", "id")
                row = db.get_research_by_id(rid)
                if not row:
                    self._send('not found', 'text/plain', code=404); return
                stats = row.get("stats") or {}
                cached = (stats.get("translations") or {}).get(to)
                if cached:
                    self._send(json.dumps({"report": cached, "lang": to, "cached": True}), "application/json"); return
                from research_engine import translate_text
                translated = translate_text(row["report"], to)
                db.set_translation(rid, to, translated)
                self._send(json.dumps({"report": translated, "lang": to, "cached": False}), "application/json")
            except Exception as e:
                self._send(f'Translate error: {e}', 'text/plain', code=400)
        elif path == "/api/research/settings":
            n = int(self.headers.get("Content-Length", 0))
            try:
                updates = json.loads(self.rfile.read(n))
                # kalau api_key kosong/mask, jangan timpa yg lama
                if not updates.get("llm_api_key") or str(updates.get("llm_api_key", "")).startswith("\u2022"):
                    updates.pop("llm_api_key", None)
                research_config.save_config(updates)
                self._send(json.dumps(research_config.public_config()), "application/json")
            except Exception as e:
                self._send(f'Settings error: {e}', 'text/plain', code=400)
        elif path == "/api/research/start":
            # Launch live LLM+SearXNG research di background thread. Return session_id.
            n = int(self.headers.get("Content-Length", 0))
            try:
                body = json.loads(self.rfile.read(n))
                question = (body.get("query") or "").strip()
                th = body.get("th_level")
                analysis = body.get("analysis") or {}
                if not question and th:
                    question = _build_account_question(th, analysis)
                if not question:
                    self._send("Missing query or th_level", "text/plain", code=400)
                    return
                sid = "rp-" + uuid.uuid4().hex[:12]
                with _RESEARCH_LOCK:
                    _RESEARCH_TASKS[sid] = {"status": "running", "phase": "planning",
                                            "events": [], "result": None, "error": None,
                                            "query": question, "started": time.time(),
                                            "meta": {"account_id": body.get("account_id"),
                                                     "account_name": body.get("account_name"),
                                                     "th_level": th}}
                threading.Thread(target=_run_research_task, args=(sid, question), daemon=True).start()
                self._send(json.dumps({"session_id": sid, "status": "running", "query": question}), "application/json")
            except Exception as e:
                self._send(f'Research start error: {e}', 'text/plain', code=500)
        else:
            self._send("not found", code=404)

    def log_message(self, *a):  # senyapin akses-log ke stderr
        pass

PORT = 5050
if __name__ == "__main__":
    print(f"Dashboard: http://localhost:{PORT}")
    # ThreadingHTTPServer: status polls tak boleh ke-block sama request lain yg lagi jalan
    # (research bisa 150s+; single-thread server bikin poll nyangkut → frontend kira "lost connection")
    http.server.ThreadingHTTPServer(("127.0.0.1", PORT), H).serve_forever()
