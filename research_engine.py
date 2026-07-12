#!/usr/bin/env python3
"""LLM + SearXNG deep-research engine. Stdlib only (urllib + threads).

Adaptasi DeepResearcher Odysseus (IterResearch pattern) ke COC bot:
  PLAN → generate queries → SearXNG search → fetch+extract (LLM) → synthesize → decide → final report

Beda dari research.py (yang hardcoded): ini manggil LLM beneran + nyari web via SearXNG.
"""
import json
import re
import time
import urllib.request
import urllib.parse
import urllib.error
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from html.parser import HTMLParser

from research_config import load_config

# Beberapa WAF/Cloudflare blok default Python-urllib UA (-> 403). Samar jadi browser.
_UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"


# ── LLM call (OpenAI-compatible /chat/completions) ───────────────────────

def _chat_url(base: str) -> str:
    base = (base or "").rstrip("/")
    if base.endswith("/chat/completions"):
        return base
    if not base.endswith("/v1") and "/v1" not in base:
        base += "/v1"
    return base + "/chat/completions"


def llm_call(messages, cfg, temperature=0.3, max_tokens=2048, timeout=90) -> str:
    """Blocking OpenAI-compatible chat call. Return isi teks (thinking di-strip)."""
    url = _chat_url(cfg["llm_base_url"])
    payload = {
        "model": cfg.get("llm_model") or "",
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": False,
    }
    headers = {"Content-Type": "application/json", "User-Agent": _UA}
    if cfg.get("llm_api_key"):
        headers["Authorization"] = f"Bearer {cfg['llm_api_key']}"

    body = json.dumps(payload).encode()
    # Retry buat 5xx / timeout / connection blip (9router kadang 502 pas rame).
    last_err = None
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, data=body, headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = json.loads(resp.read())
            content = data["choices"][0]["message"]["content"]
            return _strip_thinking(content)
        except urllib.error.HTTPError as e:
            last_err = e
            if e.code in (429, 500, 502, 503, 504) and attempt < 2:
                time.sleep(1.5 * (attempt + 1))
                continue
            raise
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            last_err = e
            if attempt < 2:
                time.sleep(1.5 * (attempt + 1))
                continue
            raise
    raise last_err if last_err else RuntimeError("llm_call failed")


def _strip_thinking(text: str) -> str:
    """Buang <think>...</think> block dari reasoning models."""
    if not text:
        return ""
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL | re.IGNORECASE)
    return text.strip()


def list_models(cfg) -> list:
    """GET /v1/models — return list nama model yg tersedia."""
    base = (cfg["llm_base_url"] or "").rstrip("/")
    if not base.endswith("/v1") and "/v1" not in base:
        base += "/v1"
    url = base + "/models"
    headers = {"User-Agent": _UA}
    if cfg.get("llm_api_key"):
        headers["Authorization"] = f"Bearer {cfg['llm_api_key']}"
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read())
    models = [m.get("id", "") for m in data.get("data", []) if m.get("id")]
    # Filter non-chat models (embedding/tts/dll) — sama kayak Odysseus
    non_chat = ("embed", "tts-", "whisper", "dall-e", "moderation", "rerank", "clip", "stable-diffusion")
    return [m for m in models if not any(p in m.lower() for p in non_chat)]


# ── SearXNG search ───────────────────────────────────────────────────────

def searxng_search(query: str, cfg, count=8) -> list:
    """SearXNG JSON API. Return [{title, url, snippet}]."""
    # Query kepanjangan bikin engine balik sampah — potong ke ~8 kata.
    words = query.split()
    if len(words) > 8:
        query = " ".join(words[:8])
    instance = (cfg["searxng_url"] or "").rstrip("/")
    # Engine google/brave/ddg sering keblok dari IP datacenter (CAPTCHA).
    # Default ke engine yg jalan; bisa di-override via cfg["searxng_engines"].
    p = {"q": query, "format": "json", "language": "en", "safesearch": 1}
    # cfg bisa punya key dengan nilai None (kena overwrite pas save config lain) —
    # jadi jangan andelin default arg .get(); fallback eksplisit.
    engines = cfg.get("searxng_engines") or "google,mojeek,presearch"
    p["engines"] = engines
    params = urllib.parse.urlencode(p)
    url = f"{instance}/search?{params}"
    req = urllib.request.Request(url, headers={"User-Agent": _UA})
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read())
    # Domain sampah yg sering bocor dari engine (bukan sumber strategi COC).
    JUNK = ("youtube.com/watch", "youtube.com/channel", "support.google.com",
            "zhihu.com", "reddit.com/r/piracy", "tp-link.com", "pisowifi",
            "play.google.com", "apps.apple.com", "google.com/chrome", "tuoitre.vn")
    # keyword yg nandain hasil relevan ke Clash of Clans
    COC_HINT = ("clash", "coc", "townhall", "town-hall", "th16", "th15", "th17",
                "supercell", "clashofclans", "hero", "attack", "base", "upgrade")
    out = []
    for r in data.get("results", []):
        url = r.get("url", "")
        if not url:
            continue
        low = (url + " " + r.get("title", "") + " " + r.get("content", "")).lower()
        if any(j in url.lower() for j in JUNK):
            continue
        # buang hasil yg jelas ga nyambung ke COC
        if not any(h in low for h in COC_HINT):
            continue
        out.append({"title": r.get("title", ""), "url": url, "snippet": r.get("content", "")})
        if len(out) >= count:
            break
    return out


# ── Fetch webpage → plain text ───────────────────────────────────────────

class _TextExtractor(HTMLParser):
    """Ambil teks readable dari HTML, skip script/style/nav."""
    _SKIP = {"script", "style", "noscript", "nav", "header", "footer", "svg", "form"}

    def __init__(self):
        super().__init__()
        self.parts = []
        self._skip_depth = 0

    def handle_starttag(self, tag, attrs):
        if tag in self._SKIP:
            self._skip_depth += 1

    def handle_endtag(self, tag):
        if tag in self._SKIP and self._skip_depth > 0:
            self._skip_depth -= 1

    def handle_data(self, data):
        if self._skip_depth == 0:
            t = data.strip()
            if t:
                self.parts.append(t)


def fetch_page_text(url: str, timeout=12, max_chars=12000) -> str:
    """Fetch URL, ekstrak teks. Return "" kalau gagal."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": _UA})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            ctype = resp.headers.get("Content-Type", "")
            if "html" not in ctype and "text" not in ctype:
                return ""
            raw = resp.read(2_000_000)  # cap 2MB
        html = raw.decode("utf-8", errors="ignore")
        p = _TextExtractor()
        p.feed(html)
        text = "\n".join(p.parts)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text[:max_chars]
    except Exception:
        return ""


# ── Prompts (dari Odysseus, disesuaikan) ─────────────────────────────────

def _date_ctx():
    now = datetime.now()
    return (f"Today is {now.strftime('%B %d, %Y')}. When a query needs a year or "
            f"says 'latest'/'current', use {now.strftime('%Y')} or relative wording.\n\n")

PLAN_PROMPT = """You are a research strategist for Clash of Clans strategy.

Question: {q}

Break this into 3-4 SHORT web search queries (each 3-6 words MAX). Search engines \
return junk if queries are long or stuff many item names together. Keep each query \
focused on ONE topic. Prefer the Town Hall level + one theme per query.

GOOD: ["TH16 upgrade priority guide 2026", "TH16 best attack strategy", "TH16 hero equipment tier list", "TH16 farming army"]
BAD (too long/stuffed): ["TH16 upgrade order 2026 Barbarian King Monolith Scattershot best defense priority"]

Return ONLY the JSON array."""

FOLLOWUP_PROMPT = """You are refining Clash of Clans strategy research.

Question: {q}

What we know so far:
{report}

Generate ONLY a JSON array of 2-3 follow-up search queries to fill gaps or \
verify claims. Return just the array."""

EXTRACT_PROMPT = """Extract Clash of Clans strategy info from the webpage below.

Topic: {q}

If the page contains ANY Clash of Clans strategy, upgrade, attack, hero, or base info, \
set relevant=true (be generous — most CoC guide pages are relevant). Only set relevant=false \
if the page is totally unrelated (e.g. a login page, ads, or non-CoC content).

Return a JSON object: {{"relevant": true/false, "summary": "2-4 sentence summary of the \
useful CoC facts", "key_points": ["specific fact 1", "specific fact 2", "specific fact 3"]}}

Webpage content:
{content}"""

SYNTH_PROMPT = """You are writing a Clash of Clans strategy research report.

Question: {q}

Current report:
{report}

New findings:
{findings}

Integrate the new findings into an updated, well-organized report. Use ## headings. \
Keep source URLs as inline [title](url) citations. Remove redundancy. Write ONLY the report."""

STOP_PROMPT = """Question: {q}

Evidence gathered so far:
{report}

You are deciding whether to gather MORE sources or stop and write the final report.

Say YES (stop) ONLY if for EVERY part of the question below you already have at least 2 \
independent facts with sources. Say NO (keep researching) if ANY part is thin, missing, \
vague, or relies on a single source.

Reply ONLY "YES" or "NO" then one line listing which parts are covered vs missing."""

FINAL_PROMPT = """Write an ACTIONABLE Clash of Clans strategy report for THIS player.

Player's situation:
{q}

Evidence gathered:
{report}

Use exactly these ## sections (skip any with no data). Every item MUST say
WHAT to do and WHY — never just describe.

## TL;DR — Do This Now
3-5 numbered actions in priority order. Each: **Action** — why it matters (1 line).

## Priority Guide
Ranked numbered list of what to upgrade first. Each item:
1. **[Item]** (lvl current→max) — Impact: offense/defense/farming. **Next step:** <specific action>.

## Attack Strategies
For each: **Name** — army comp, when to use, one practical tip.

## Heroes & Equipment
Upgrade order with reasoning.

## Farming
Best army + league to fund the upgrades above.

## Recommendation
One paragraph: the single most important focus next.

Rules:
- Cite sources inline as [title](url).
- Tie every recommendation to the player's UNMAXED items listed above — no generic TH advice.
- If evidence is thin for a section, say so instead of inventing."""


# ── JSON parsing helpers ─────────────────────────────────────────────────

def _parse_json_array(text: str) -> list:
    text = _strip_fences(text)
    try:
        v = json.loads(text)
        if isinstance(v, list):
            return [str(x) for x in v]
    except json.JSONDecodeError:
        pass
    m = re.search(r"\[[\s\S]*\]", text)
    if m:
        try:
            v = json.loads(m.group())
            if isinstance(v, list):
                return [str(x) for x in v]
        except json.JSONDecodeError:
            pass
    # last resort: harvest quoted strings
    items = re.findall(r'"([^"]+)"', text)
    return items[:4]


def _parse_json_obj(text: str):
    text = _strip_fences(text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    m = re.search(r"\{[\s\S]*\}", text)
    if m:
        try:
            return json.loads(m.group())
        except json.JSONDecodeError:
            pass
    return None


def _strip_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    return text.strip()


# ── Main engine ──────────────────────────────────────────────────────────

class LiveResearcher:
    """Iterative LLM+SearXNG researcher. progress_cb(dict) buat streaming status."""

    def __init__(self, cfg, progress_cb=None):
        self.cfg = cfg
        self.progress = progress_cb or (lambda e: None)
        self.urls_seen = set()
        self.sources = []
        self.max_rounds = cfg.get("max_rounds")
        if self.max_rounds is None:
            self.max_rounds = 3
        self.auto_rounds = self.max_rounds <= 0  # 0 = AI yg nentuin kapan stop
        if self.auto_rounds:
            self.max_rounds = 6  # safety cap — LLM bisa stop lebih awal via _should_stop
        self.max_urls = cfg.get("max_urls_per_round", 3)
        self.max_time = cfg.get("max_time", 300)
        self._t0 = 0

    def _emit(self, **kw):
        try:
            self.progress(kw)
        except Exception:
            pass

    def _time_up(self):
        return (time.time() - self._t0) > self.max_time

    def research(self, question: str) -> dict:
        self._t0 = time.time()
        cfg = self.cfg
        # Selalu return dict (catch-all) biar save_research selalu dipanggil di
        # _run_research_task — sebelumnya exception di sini bikin row DB gak ke-save.
        try:
            return self._research_inner(question)
        except Exception as e:
            self._emit(phase="warning", message=f"Research error: {type(e).__name__}: {e}")
            return {
                "report": (getattr(self, "_partial", "") or
                           f"Research gagal: {type(e).__name__}. Cek log backend."),
                "sources": self.sources,
                "stats": {"duration": f"{time.time()-self._t0:.0f}s",
                          "sources": len(self.sources),
                          "findings": 0,
                          "model": cfg.get("llm_model", ""),
                          "error": str(e)},
            }

    def _research_inner(self, question: str) -> dict:
        cfg = self.cfg
        # topik pendek buat extract (biar LLM ga bingung nilai relevansi dgn paragraf panjang)
        import re as _re
        m = _re.search(r"[Tt]own [Hh]all (\d+)|TH\s*(\d+)", question)
        thn = (m.group(1) or m.group(2)) if m else ""
        self._extract_topic = f"Clash of Clans Town Hall {thn} strategy, upgrades, attacks, heroes" if thn else "Clash of Clans strategy and upgrades"

        # PLAN — generate initial queries
        self._emit(phase="planning")
        queries = self._plan(question)
        report = ""
        all_findings = []

        for rnd in range(1, self.max_rounds + 1):
            if self._time_up():
                break
            self._emit(phase="searching", round=rnd, total_sources=len(self.sources))

            if rnd > 1:
                queries = self._followup(question, report)
            if not queries:
                break

            # SEARCH + EXTRACT
            findings = self._search_and_extract(queries, question, rnd)
            if findings:
                all_findings.extend(findings)
                self._emit(phase="analyzing", round=rnd, total_sources=len(self.sources))
                report = self._synthesize(question, findings, report)

            # DECIDE — LLM nentuin kapan konteks cukup. Bisa ronde 1 kalau
            # memang udah cukup, bisa sampai max_rounds kalau belum.
            if self.auto_rounds and report:
                if self._should_stop(question, report, rnd):
                    break
            elif not self.auto_rounds and rnd >= 2 and report:
                if self._should_stop(question, report, rnd):
                    break

        # FINAL REPORT
        self._emit(phase="writing", total_sources=len(self.sources))
        # Kalau report kosong padahal ada findings, susun bahan dari findings
        # dulu sebelum final — dulu ini bikin row tersimpan kosong (id 15/16).
        if (not report or not report.strip()) and all_findings:
            report = "\n\n".join(f"### {f.get('title','Source')}\n{f.get('summary','')}"
                                  for f in all_findings if f.get('summary'))
        final = self._final(question, report) if report else (
            "No information could be gathered. Cek koneksi SearXNG & LLM."
        )
        # Safety net: kalau final entah kenapa kosong tapi ada report/findings, pakai itu.
        if (not final or not final.strip()):
            final = report or (
                "\n\n".join(f"- {f.get('title','Source')}: {f.get('summary','')}"
                            for f in all_findings)
                if all_findings else "No information could be gathered.")
        elapsed = time.time() - self._t0
        self._partial = final  # simpen biar catch-all di research() bisa pakai
        return {
            "report": final,
            "sources": self.sources,
            "stats": {
                "duration": f"{elapsed:.0f}s",
                "sources": len(self.sources),
                "findings": len(all_findings),
                "model": cfg.get("llm_model", ""),
            },
        }

    def _plan(self, q):
        # coba beberapa kali — model kadang balik kosong/prosa, bukan JSON array.
        for attempt in range(2):
            try:
                resp = llm_call([{"role": "user", "content": _date_ctx() + PLAN_PROMPT.format(q=q)}],
                                self.cfg, temperature=0.4 + attempt * 0.3, max_tokens=512, timeout=60)
                queries = _parse_json_array(resp)
                if queries:
                    return queries
            except Exception as e:
                self._emit(phase="warning", message=f"Plan attempt {attempt+1} failed: {e}")
        # fallback: bikin query dari kata kunci pertanyaan sendiri biar research tetep jalan
        self._emit(phase="warning", message="Plan kosong, pakai query fallback")
        return self._fallback_queries(q)

    def _fallback_queries(self, q):
        """Query cadangan kalau LLM plan gagal — ekstrak TH + kata kunci dari pertanyaan."""
        import re as _re
        year = time.strftime("%Y")
        m = _re.search(r"[Tt]own [Hh]all (\d+)|TH\s*(\d+)", q)
        th = (m.group(1) or m.group(2)) if m else ""
        base = f"Town Hall {th}" if th else "Clash of Clans"
        # ambil nama item yg disebut (kata Kapital berturut) buat query spesifik
        items = _re.findall(r"([A-Z][a-z]+(?: [A-Z][a-z]+){0,2}) \(lvl", q)
        # query PENDEK — search engine gagal kalau kepanjangan/keyword numpuk
        qs = [
            f"{base} upgrade priority guide {year}",
            f"{base} best attack strategy {year}",
            f"{base} hero equipment tier list {year}",
        ]
        # item spesifik: query terpisah per item (jangan digabung jadi 1 query panjang)
        for it in items[:2]:
            qs.append(f"{base} {it} upgrade worth it")
        return qs

    def _followup(self, q, report):
        try:
            resp = llm_call([{"role": "user", "content": FOLLOWUP_PROMPT.format(q=q, report=report[:3000])}],
                            self.cfg, temperature=0.5, max_tokens=512, timeout=60)
            return _parse_json_array(resp)
        except Exception:
            return []

    def _search_and_extract(self, queries, question, rnd):
        # Search semua query paralel
        to_fetch = []
        cap = self.max_urls  # total URL per ronde (bukan per-query) biar ga meledak
        with ThreadPoolExecutor(max_workers=4) as ex:
            futs = {ex.submit(self._safe_search, q): q for q in queries}
            for fut in as_completed(futs):
                for r in fut.result():
                    if r["url"] not in self.urls_seen and len(to_fetch) < cap:
                        self.urls_seen.add(r["url"])
                        to_fetch.append(r)

        if not to_fetch or self._time_up():
            return []

        # Fetch + extract SEMUA paralel (1 worker per URL) biar cepat
        findings = []
        with ThreadPoolExecutor(max_workers=max(4, len(to_fetch))) as ex:
            futs = {ex.submit(self._extract_one, r, question): r for r in to_fetch}
            for fut in as_completed(futs):
                f = fut.result()
                if f:
                    findings.append(f)
        return findings

    def _safe_search(self, q):
        try:
            return searxng_search(q, self.cfg)
        except Exception as e:
            self._emit(phase="warning", message=f"Search failed: {e}")
            return []

    def _extract_one(self, result, question):
        url, title = result["url"], result["title"]
        self._emit(phase="reading", url=url, title=title, total_sources=len(self.sources))
        text = fetch_page_text(url)
        if not text or len(text) < 200:
            time.sleep(0.5); text = fetch_page_text(url)  # retry sekali
        if not text or len(text) < 200:
            self._emit(phase="warning", message=f"Fetch gagal/kosong: {title[:35]} ({len(text or '')}c)")
            return None
        try:
            resp = llm_call(
                [{"role": "user", "content": EXTRACT_PROMPT.format(q=getattr(self, "_extract_topic", question), content=text)}],
                self.cfg, temperature=0.2, max_tokens=1024, timeout=self.cfg.get("extraction_timeout", 45),
            )
            parsed = _parse_json_obj(resp)
            if parsed and parsed.get("relevant") and parsed.get("summary"):
                self.sources.append({"url": url, "title": title})
                return {"url": url, "title": title, "summary": parsed["summary"],
                        "key_points": parsed.get("key_points", [])}
            # parse gagal atau ditandai ga relevan — kasih tau kenapa
            if parsed is None:
                self._emit(phase="warning", message=f"Extract JSON gagal parse: {title[:35]}")
            elif not parsed.get("relevant"):
                self._emit(phase="warning", message=f"Ditandai tak relevan: {title[:35]}")
        except Exception as e:
            self._emit(phase="warning", message=f"Extract error ({title[:25]}): {type(e).__name__} {str(e)[:40]}")
        return None

    def _synthesize(self, q, findings, report):
        ftext = "\n\n".join(
            f"[{f['title']}]({f['url']})\n{f['summary']}\n" +
            "\n".join(f"- {p}" for p in f.get("key_points", []))
            for f in findings
        )
        # Prompt kegedean bikin model balik kosong — batasi ukuran input.
        ftext = ftext[:6000]
        prev = (report or "(first round)")[:4000]
        try:
            out = llm_call(
                [{"role": "user", "content": SYNTH_PROMPT.format(q=q, report=prev, findings=ftext)}],
                self.cfg, temperature=0.3, max_tokens=3000, timeout=90)
            if out and out.strip():
                return out.strip()
            # model balik kosong — gabung manual biar report ga hilang
            self._emit(phase="warning", message="Synth balik kosong, pakai gabungan manual")
            return (report + "\n\n" + ftext).strip() if report else ftext
        except Exception as e:
            self._emit(phase="warning", message=f"Synth failed: {e}")
            return report or ftext

    def _should_stop(self, q, report, rnd):
        try:
            resp = llm_call(
                [{"role": "user", "content": STOP_PROMPT.format(q=q, report=report)}],
                self.cfg, temperature=0.1, max_tokens=128, timeout=45)
            ans = re.sub(r'^[\s*_`"\'>#-]+', "", resp).upper()
            return ans.startswith("YES")
        except Exception:
            return False

    def _final(self, q, report):
        try:
            out = llm_call(
                [{"role": "user", "content": FINAL_PROMPT.format(q=q, report=report[:7000])}],
                self.cfg, temperature=0.3, max_tokens=3000, timeout=90)
            # Model kadang balik kosong pas prompt gede — fallback ke report sintesis.
            return out.strip() if out and out.strip() else report
        except Exception as e:
            self._emit(phase="warning", message=f"Final report gagal: {type(e).__name__}, pakai draft")
            return report


LANGS = {"id": "Indonesian (Bahasa Indonesia)", "en": "English"}
TRANSLATE_PROMPT = """Translate the following Clash of Clans strategy report into {lang_name}.

Rules:
- Preserve ALL markdown formatting exactly: ## headings, **bold**, [text](url) links, numbered lists, bullet lists.
- Keep Clash of Clans proper nouns as-is (do NOT translate them): Town Hall, Barbarian King, Archer Queen, Grand Warden, Royal Champion, Eagle Artillery, Clan Castle, Laboratory, etc.
- Translate everything else naturally.
- Return ONLY the translated markdown, no preamble.

Report:
{text}"""

def translate_text(text: str, to: str = "id") -> str:
    """Translate report via LLM. Reuse llm_call. Return original on failure."""
    from research_config import load_config
    if to not in LANGS:
        raise ValueError(f"unknown lang {to}")
    out = llm_call(
        [{"role": "user", "content": TRANSLATE_PROMPT.format(lang_name=LANGS[to], text=text[:7000])}],
        load_config(), temperature=0.2, max_tokens=3000, timeout=90,
    )
    return out.strip() if out else text

def run_research(question: str, progress_cb=None) -> dict:
    """Entry point: jalanin deep research untuk 1 pertanyaan."""
    cfg = load_config()
    return LiveResearcher(cfg, progress_cb).research(question)
