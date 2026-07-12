import React, { useState, useEffect, useCallback, useRef } from 'react';
import { Brain, Settings2, RefreshCw, AlertCircle, Search, FileText, CheckCircle2, Loader2, Globe, X, Save } from 'lucide-react';

const API = 'http://localhost:5050';

type Props = { thLevel?: number; accountId?: string; accountName?: string; thImg?: string; analysis?: any };

type Settings = {
  llm_base_url: string;
  llm_api_key: string;
  llm_model: string;
  searxng_url: string;
  max_rounds: number;
  llm_api_key_set?: boolean;
};

// ── Minimal markdown → React (headings, bold, links, lists) ──────────────
function renderMarkdown(md: string): React.ReactNode {
  if (!md) return null;
  const lines = md.split('\n');
  const out: React.ReactNode[] = [];
  let list: string[] = [];
  const flush = () => {
    if (list.length) {
      out.push(
        <ul key={`ul-${out.length}`} className="list-disc pl-6 flex flex-col gap-1 my-2">
          {list.map((li, i) => <li key={i} className="text-sm text-gray-300 normal-case leading-relaxed">{inline(li)}</li>)}
        </ul>
      );
      list = [];
    }
  };
  const inline = (t: string): React.ReactNode => {
    const parts: React.ReactNode[] = [];
    const re = /\[([^\]]+)\]\(([^)]+)\)|\*\*([^*]+)\*\*/g;
    let last = 0, m: RegExpExecArray | null, k = 0;
    while ((m = re.exec(t))) {
      if (m.index > last) parts.push(t.slice(last, m.index));
      if (m[1]) parts.push(<a key={k++} href={m[2]} target="_blank" rel="noopener noreferrer" className="text-blue-400 hover:underline">{m[1]}</a>);
      else if (m[3]) parts.push(<strong key={k++} className="text-white font-bold">{m[3]}</strong>);
      last = re.lastIndex;
    }
    if (last < t.length) parts.push(t.slice(last));
    return parts;
  };
  for (const raw of lines) {
    const line = raw.trimEnd();
    if (/^###\s+/.test(line)) { flush(); out.push(<h4 key={out.length} className="font-grotesk text-base text-blue-300 mt-4 mb-1 tracking-wide">{inline(line.replace(/^###\s+/, ''))}</h4>); }
    else if (/^##\s+/.test(line)) { flush(); out.push(<h3 key={out.length} className="font-grotesk text-xl text-white mt-5 mb-2 tracking-wider border-b border-white/5 pb-1">{inline(line.replace(/^##\s+/, ''))}</h3>); }
    else if (/^#\s+/.test(line)) { flush(); out.push(<h2 key={out.length} className="font-grotesk text-2xl text-white mt-5 mb-2">{inline(line.replace(/^#\s+/, ''))}</h2>); }
    else if (/^[-*]\s+/.test(line)) { list.push(line.replace(/^[-*]\s+/, '')); }
    else if (line.trim() === '') { flush(); }
    else { flush(); out.push(<p key={out.length} className="text-sm text-gray-300 normal-case leading-relaxed my-2">{inline(line)}</p>); }
  }
  flush();
  return out;
}

const PHASE_LABEL: Record<string, string> = {
  planning: 'Planning research queries',
  searching: 'Searching the web (SearXNG)',
  reading: 'Reading & extracting sources',
  analyzing: 'Synthesizing findings',
  writing: 'Writing final report',
  warning: 'Warning',
};

const LiveResearchView: React.FC<Props> = ({ thLevel, accountId, accountName, thImg, analysis }) => {
  const [showSettings, setShowSettings] = useState(false);
  const [settings, setSettings] = useState<Settings>({
    llm_base_url: '',
    llm_api_key: '',
    llm_model: '',
    searxng_url: '',
    max_rounds: 3
  });
  const [models, setModels] = useState<string[]>([]);
  const [modelsLoading, setModelsLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [savedMsg, setSavedMsg] = useState('');

  const [sessionId, setSessionId] = useState<string | null>(null);
  const [status, setStatus] = useState<string>('idle');
  const [phase, setPhase] = useState<string>('');
  const [events, setEvents] = useState<any[]>([]);
  const [result, setResult] = useState<any>(null);
  const [error, setError] = useState<string>('');
  const pollRef = useRef<any>(null);

  const loadSettings = useCallback(async () => {
    try {
      const r = await fetch(`${API}/api/research/settings`);
      setSettings(await r.json());
    } catch { setError('Cannot reach backend at :5050'); }
  }, []);

  useEffect(() => { loadSettings(); }, [loadSettings]);
  useEffect(() => () => { if (pollRef.current) clearInterval(pollRef.current); }, []);

  const fetchModels = useCallback(async () => {
    setModelsLoading(true); setSavedMsg('');
    try {
      // save dulu URL/key yg lagi diketik, biar fetch pakai config terbaru
      if (settings) {
        const body: any = {
          llm_base_url: settings.llm_base_url,
          searxng_url: settings.searxng_url,
        };
        if (settings.llm_api_key && !settings.llm_api_key.startsWith('•')) body.llm_api_key = settings.llm_api_key;
        await fetch(`${API}/api/research/settings`, {
          method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
        });
      }
      const r = await fetch(`${API}/api/research/models`);
      const j = await r.json();
      setModels(j.models || []);
      if (j.error) setSavedMsg(`Model fetch gagal: ${j.error}`);
      else if (!j.models?.length) setSavedMsg('0 model — cek URL/API key');
      else setSavedMsg(`${j.models.length} model ditemukan`);
    } catch { setSavedMsg('Failed to fetch models'); }
    setModelsLoading(false);
  }, [settings]);

  const saveSettings = useCallback(async () => {
    if (!settings) return;
    setSaving(true); setSavedMsg('');
    try {
      const body: any = {
        llm_base_url: settings.llm_base_url,
        llm_model: settings.llm_model,
        searxng_url: settings.searxng_url,
        max_rounds: Number.isFinite(Number(settings.max_rounds)) ? Number(settings.max_rounds) : 3,
      };
      // hanya kirim api_key kalau user ngetik baru (bukan mask ••••)
      if (settings.llm_api_key && !settings.llm_api_key.startsWith('•')) body.llm_api_key = settings.llm_api_key;
      const r = await fetch(`${API}/api/research/settings`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
      });
      setSettings(await r.json());
      setSavedMsg('Saved ✓');
    } catch { setSavedMsg('Save failed'); }
    setSaving(false);
  }, [settings]);

  const poll = useCallback((sid: string) => {
    let failStreak = 0;
    pollRef.current = setInterval(async () => {
      try {
        const r = await fetch(`${API}/api/research/status/${sid}`);
        if (!r.ok) {
          // 404 = task hilang (server restart) → nyerah; selain itu anggap transient
          if (r.status === 404) { clearInterval(pollRef.current); setStatus('error'); setError('Sesi research tidak ditemukan (backend restart?)'); }
          else if (++failStreak >= 6) { clearInterval(pollRef.current); setStatus('error'); setError(`Backend error ${r.status} (6× berturut)`); }
          return;
        }
        failStreak = 0;
        const j = await r.json();
        setPhase(j.phase || '');
        setEvents(j.events || []);
        if (j.status === 'done') {
          clearInterval(pollRef.current);
          setStatus('done'); setResult(j.result);
        } else if (j.status === 'error') {
          clearInterval(pollRef.current);
          setStatus('error'); setError(j.error || 'Unknown error');
        }
      } catch {
        // Jangan nyerah di 1 blip — research bisa 150s+, poll sesekali gagal itu wajar.
        // Baru anggap putus kalau gagal 6× berturut-turut (~9 detik).
        if (++failStreak >= 6) {
          clearInterval(pollRef.current);
          setStatus('error'); setError('Lost connection to backend');
        }
      }
    }, 1500);
  }, []);

  const startResearch = useCallback(async () => {
    setStatus('running'); setResult(null); setError(''); setEvents([]); setPhase('planning');
    try {
      const r = await fetch(`${API}/api/research/start`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ th_level: thLevel, account_id: accountId, account_name: accountName, analysis }),
      });
      if (!r.ok) { setStatus('error'); setError(await r.text()); return; }
      const j = await r.json();
      setSessionId(j.session_id);
      poll(j.session_id);
    } catch { setStatus('error'); setError('Cannot reach backend at :5050'); }
  }, [thLevel, accountId, accountName, analysis, poll]);

  const cfgReady = settings && settings.llm_base_url && (settings.llm_model || models.length);

  return (
    <div className="flex flex-col gap-6 animate-in fade-in">
      {/* Header */}
      <div className="flex flex-col md:flex-row items-center justify-center md:justify-between flex-wrap gap-4 text-center md:text-left">
        <div className="flex items-center gap-3">
          {thImg ? (
            <div className="relative w-12 h-12 flex-shrink-0">
              <div className="absolute inset-0 bg-blue-500/25 blur-lg rounded-full" />
              <img src={thImg} alt={`TH${thLevel}`} className="w-full h-full object-contain relative z-10 drop-shadow-lg" onError={e => (e.currentTarget.style.display = 'none')} />
            </div>
          ) : (
            <div className="p-2 bg-blue-500/10 rounded-lg text-blue-400"><Brain className="w-6 h-6" /></div>
          )}
          <div>
            <h2 className="font-grotesk text-2xl text-white tracking-wider">Live AI Research</h2>
            <p className="text-xs text-gray-500 normal-case">LLM + SearXNG · Odysseus IterResearch pattern{thLevel ? ` · TH${thLevel}` : ''}</p>
          </div>
        </div>
        <div className="flex flex-wrap items-center justify-center gap-2">
          <button onClick={() => setShowSettings(s => !s)} className="bg-[var(--panel-bg)] border border-white/10 text-gray-300 px-4 py-2.5 rounded-xl hover:border-blue-500/30 transition-all flex items-center gap-2 text-sm">
            <Settings2 className="w-4 h-4" /> Settings
          </button>
          <button onClick={startResearch} disabled={status === 'running' || !cfgReady}
            className="bg-gradient-to-r from-blue-500 to-blue-600 text-white px-6 py-2.5 rounded-xl hover:opacity-80 transition-opacity font-bold flex items-center gap-2 disabled:opacity-40">
            {status === 'running' ? <><Loader2 className="w-4 h-4 animate-spin" /> Researching…</> : <><Search className="w-4 h-4" /> Start Research</>}
          </button>
        </div>
      </div>

      {/* Settings Panel */}
      {showSettings && (
        <div className="bg-[var(--panel-bg)] border border-blue-500/20 rounded-2xl p-6 flex flex-col gap-4 animate-in fade-in slide-in-from-top-2">
          <div className="flex items-center justify-between">
            <h3 className="font-grotesk text-lg text-blue-300 tracking-wide flex items-center gap-2"><Settings2 className="w-4 h-4" /> Research Configuration</h3>
            <button onClick={() => setShowSettings(false)} className="text-gray-500 hover:text-white"><X className="w-4 h-4" /></button>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <label className="flex flex-col gap-1.5">
              <span className="text-[10px] uppercase tracking-widest text-gray-500">LLM Base URL (OpenAI-compatible)</span>
              <input value={settings.llm_base_url} onChange={e => setSettings({ ...settings, llm_base_url: e.target.value })}
                placeholder="http://localhost:1234/v1" className="bg-black/30 border border-white/10 rounded-lg px-3 py-2 text-sm text-white normal-case focus:border-blue-500/50 outline-none" />
            </label>
            <label className="flex flex-col gap-1.5">
              <span className="text-[10px] uppercase tracking-widest text-gray-500">API Key (kosongkan kalau lokal)</span>
              <input type="password" value={settings.llm_api_key} onChange={e => setSettings({ ...settings, llm_api_key: e.target.value })}
                placeholder={settings.llm_api_key_set ? '•••• (tersimpan)' : 'sk-…'} className="bg-black/30 border border-white/10 rounded-lg px-3 py-2 text-sm text-white normal-case focus:border-blue-500/50 outline-none" />
            </label>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <label className="flex flex-col gap-1.5">
              <span className="text-[10px] uppercase tracking-widest text-gray-500 flex items-center justify-between">
                Model
                <button onClick={fetchModels} className="text-blue-400 hover:underline lowercase tracking-normal flex items-center gap-1">
                  {modelsLoading ? <Loader2 className="w-3 h-3 animate-spin" /> : <RefreshCw className="w-3 h-3" />} fetch
                </button>
              </span>
              {models.length > 0 ? (
                <select value={settings.llm_model} onChange={e => setSettings({ ...settings, llm_model: e.target.value })}
                  className="bg-black/30 border border-white/10 rounded-lg px-3 py-2 text-sm text-white normal-case focus:border-blue-500/50 outline-none">
                  <option value="">— pilih model —</option>
                  {models.map(m => <option key={m} value={m}>{m}</option>)}
                </select>
              ) : (
                <input value={settings.llm_model} onChange={e => setSettings({ ...settings, llm_model: e.target.value })}
                  placeholder="klik fetch, atau ketik manual" className="bg-black/30 border border-white/10 rounded-lg px-3 py-2 text-sm text-white normal-case focus:border-blue-500/50 outline-none" />
              )}
            </label>
            <label className="flex flex-col gap-1.5">
              <span className="text-[10px] uppercase tracking-widest text-gray-500 flex items-center gap-1"><Globe className="w-3 h-3" /> SearXNG URL</span>
              <input value={settings.searxng_url} onChange={e => setSettings({ ...settings, searxng_url: e.target.value })}
                placeholder="http://localhost:8080" className="bg-black/30 border border-white/10 rounded-lg px-3 py-2 text-sm text-white normal-case focus:border-blue-500/50 outline-none" />
            </label>
          </div>

          <div className="flex flex-col md:flex-row items-start md:items-center gap-4">
            <label className="flex flex-col gap-1.5 w-full md:w-52">
              <span className="text-[10px] uppercase tracking-widest text-gray-500">Max Rounds (0 = Auto / AI decides)</span>
              <input type="number" min={0} max={6} value={settings.max_rounds} onChange={e => setSettings({ ...settings, max_rounds: Number(e.target.value) })}
                className="bg-black/30 border border-white/10 rounded-lg px-3 py-2 text-sm text-white focus:border-blue-500/50 outline-none" />
              <span className="text-[10px] text-gray-600 normal-case">{Number(settings.max_rounds) <= 0 ? 'AI berhenti sendiri pas report cukup (cap 6 ronde)' : `Fixed ${settings.max_rounds} ronde`}</span>
            </label>
            <div className="flex-1" />
            {savedMsg && <span className="text-xs text-gray-400 normal-case">{savedMsg}</span>}
            <button onClick={saveSettings} disabled={saving}
              className="bg-blue-500 text-white px-5 py-2.5 rounded-xl hover:opacity-80 transition-opacity font-bold flex items-center gap-2 disabled:opacity-40">
              {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />} Save
            </button>
          </div>
          <p className="text-[11px] text-gray-600 normal-case leading-relaxed">
            Butuh: (1) LLM OpenAI-compatible — LM Studio, Ollama (<code>/v1</code>), OpenRouter, dll.
            (2) SearXNG dengan JSON API aktif (<code>formats: [html, json]</code> di settings.yml).
          </p>
        </div>
      )}

      {/* Progress */}
      {status === 'running' && (
        <div className="bg-[var(--panel-bg)] border border-white/5 rounded-2xl p-6 flex flex-col gap-4">
          <div className="flex items-center gap-3">
            <Loader2 className="w-6 h-6 text-blue-400 animate-spin" />
            <div>
              <div className="font-grotesk text-lg text-blue-300 tracking-wide">{PHASE_LABEL[phase] || phase || 'Working…'}</div>
              <div className="text-xs text-gray-500 normal-case">Iterative research in progress — this can take a minute or two</div>
            </div>
          </div>
          <div className="flex flex-col gap-1.5 max-h-56 overflow-y-auto">
            {events.map((ev, i) => (
              <div key={i} className={`text-xs normal-case flex items-start gap-2 ${ev.phase === 'warning' ? 'text-yellow-500/80' : 'text-gray-400'}`}>
                <span className="mt-0.5">{ev.phase === 'reading' ? '🔗' : ev.phase === 'warning' ? '⚠️' : ev.phase === 'searching' ? '🔍' : '•'}</span>
                <span className="flex-1 min-w-0 truncate">
                  {ev.phase === 'reading' && ev.title ? ev.title : PHASE_LABEL[ev.phase] || ev.phase}
                  {ev.message ? `: ${ev.message}` : ''}{ev.round ? ` (round ${ev.round})` : ''}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Error */}
      {status === 'error' && (
        <div className="bg-red-500/5 border border-red-500/20 rounded-2xl p-6 flex items-start gap-3">
          <AlertCircle className="w-6 h-6 text-red-400 flex-shrink-0" />
          <div className="flex flex-col gap-1">
            <span className="text-red-400 font-bold">Research failed</span>
            <span className="text-sm text-gray-400 normal-case">{error}</span>
            <span className="text-xs text-gray-600 normal-case mt-1">Cek Settings: LLM URL & SearXNG harus jalan dan bisa diakses.</span>
          </div>
        </div>
      )}

      {/* Result */}
      {status === 'done' && result && (
        <div className="flex flex-col gap-4">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            {[
              { label: 'Duration', value: result.stats?.duration, icon: <RefreshCw className="w-4 h-4" /> },
              { label: 'Sources', value: result.stats?.sources, icon: <Globe className="w-4 h-4" /> },
              { label: 'Findings', value: result.stats?.findings, icon: <FileText className="w-4 h-4" /> },
              { label: 'Model', value: result.stats?.model || '—', icon: <Brain className="w-4 h-4" /> },
            ].map(s => (
              <div key={s.label} className="bg-[var(--panel-bg)] border border-white/5 rounded-xl p-4 flex items-center gap-3">
                <div className="text-blue-400">{s.icon}</div>
                <div className="min-w-0">
                  <div className="text-lg font-black text-white truncate">{s.value}</div>
                  <div className="text-[9px] text-gray-500 uppercase tracking-widest">{s.label}</div>
                </div>
              </div>
            ))}
          </div>

          <div className="bg-[var(--panel-bg)] border border-white/5 rounded-2xl p-6 md:p-8">
            <div className="flex items-center gap-2 mb-4 text-green-400">
              <CheckCircle2 className="w-5 h-5" />
              <span className="font-grotesk text-sm uppercase tracking-widest">Research Report</span>
            </div>
            <div className="prose-invert">{renderMarkdown(result.report)}</div>
          </div>

          {result.sources?.length > 0 && (
            <div className="bg-[var(--panel-bg)] border border-white/5 rounded-2xl p-6">
              <h3 className="font-grotesk text-sm uppercase tracking-widest text-gray-400 mb-3">Sources ({result.sources.length})</h3>
              <div className="flex flex-col gap-2">
                {result.sources.map((s: any, i: number) => (
                  <a key={i} href={s.url} target="_blank" rel="noopener noreferrer" className="text-sm text-blue-400 hover:underline normal-case truncate">
                    {i + 1}. {s.title || s.url}
                  </a>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Idle hint */}
      {status === 'idle' && (
        <div className="flex flex-col items-center justify-center py-20 gap-4 text-center">
          <Brain className="w-16 h-16 text-blue-400/40" />
          <p className="text-gray-500 normal-case max-w-md">
            Research beneran pakai LLM + web search (SearXNG). Klik <strong className="text-blue-400">Settings</strong> buat set LLM URL & model,
            terus <strong className="text-blue-400">Start Research</strong>.
          </p>
          {!cfgReady && <p className="text-xs text-yellow-500/70 normal-case">⚠️ Belum ada model dipilih — buka Settings dulu.</p>}
        </div>
      )}

      <div className="text-center py-4 opacity-40 text-xs text-gray-500 normal-case">
        Engine adapted from{' '}
        <a href="https://github.com/pewdiepie-archdaemon/odysseus" target="_blank" rel="noopener noreferrer" className="text-blue-400 hover:underline">Odysseus DeepResearcher</a>
      </div>
    </div>
  );
};

export default LiveResearchView;
