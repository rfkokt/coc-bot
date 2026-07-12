import React, { useState, useEffect, useCallback } from 'react';
import { FileText, Trash2, RefreshCw, ChevronRight, ChevronDown, Clock, Globe, AlertCircle, Zap, Target, Swords, Sparkles, Coins, Rocket, ListOrdered } from 'lucide-react';

const API = 'http://localhost:5050';

type Props = { accountId?: string; accountName?: string; thLevel?: number; thImg?: string };

// Accent palette — literal strings biar Tailwind v4 scan.
const ACCENTS = {
  blue: 'bg-blue-500/10 border-blue-500/20', yellow: 'bg-yellow-500/10 border-yellow-500/20',
  red: 'bg-red-500/10 border-red-500/20', purple: 'bg-purple-500/10 border-purple-500/20',
  orange: 'bg-orange-500/10 border-orange-500/20', green: 'bg-green-500/10 border-green-500/20',
  slate: 'bg-white/5 border-white/10',
};
const TITLE_COLORS = {
  blue: 'text-blue-400', yellow: 'text-yellow-400', red: 'text-red-400',
  purple: 'text-purple-400', orange: 'text-orange-400', green: 'text-green-400', slate: 'text-gray-300',
};
function sectionMeta(title: string): { a: keyof typeof ACCENTS; Icon: any } {
  const t = title.toLowerCase();
  if (/tl;?dr|do this now/.test(t)) return { a: 'yellow', Icon: Zap };
  if (/priority/.test(t)) return { a: 'blue', Icon: Target };
  if (/attack|strateg/.test(t)) return { a: 'red', Icon: Swords };
  if (/hero|equipment/.test(t)) return { a: 'purple', Icon: Sparkles };
  if (/farm/.test(t)) return { a: 'orange', Icon: Coins };
  if (/recommend/.test(t)) return { a: 'green', Icon: Rocket };
  return { a: 'slate', Icon: ListOrdered };
}

// markdown → Priority-guide-style: tiap ## jadi colored panel + grid kartu bernomor.
function md(text: string): React.ReactNode {
  if (!text) return null;
  const inline = (t: string): React.ReactNode => {
    const parts: React.ReactNode[] = []; const re = /\[([^\]]+)\]\(([^)]+)\)|\*\*([^*]+)\*\*/g;
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
  const renderBody = (lines: string[]) => {
    const out: React.ReactNode[] = []; let list: string[] = []; let numbered: string[] = [];
    const flushAll = () => {
      if (list.length) { out.push(<ul key={`u${out.length}`} className="list-disc pl-6 my-2 flex flex-col gap-1">{list.map((li, i) => <li key={i} className="text-sm text-gray-300 normal-case leading-relaxed">{inline(li)}</li>)}</ul>); list = []; }
      if (numbered.length) { out.push(<div key={`n${out.length}`} className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3 my-3">{numbered.map((li, i) => <div key={i} className="bg-[#1a1a2e]/60 border border-white/5 rounded-xl p-4 flex gap-3 items-start"><span className="flex-shrink-0 w-6 h-6 rounded-full bg-white/10 text-xs font-black flex items-center justify-center text-white">{i + 1}</span><span className="text-sm text-gray-300 normal-case leading-relaxed">{inline(li)}</span></div>)}</div>); numbered = []; }
    };
    for (const raw of lines) {
      const l = raw.trimEnd();
      if (/^###\s+/.test(l)) { flushAll(); out.push(<h4 key={out.length} className="font-grotesk text-sm uppercase tracking-widest text-gray-400 mt-3 mb-1">{inline(l.replace(/^###\s+/, ''))}</h4>); }
      else if (/^\d+\.\s+/.test(l)) { numbered.push(l.replace(/^\d+\.\s+/, '')); }
      else if (/^[-*]\s+/.test(l)) { list.push(l.replace(/^[-*]\s+/, '')); }
      else if (l.trim() === '') { flushAll(); }
      else { flushAll(); out.push(<p key={out.length} className="text-sm text-gray-300 normal-case my-2 leading-relaxed">{inline(l)}</p>); }
    }
    flushAll(); return out;
  };
  // pecah per ## / # jadi section
  const sections: { title: string; lines: string[] }[] = [];
  let cur: { title: string; lines: string[] } | null = null, preface: string[] = [];
  for (const raw of text.split('\n')) {
    const l = raw.trimEnd();
    const h2 = l.match(/^##\s+(.+)/), h1 = l.match(/^#\s+(.+)/);
    if (h2) { if (cur) sections.push(cur); cur = { title: h2[1].trim(), lines: [] }; }
    else if (h1) { if (cur) sections.push(cur); cur = { title: h1[1].trim(), lines: [] }; }
    else { if (cur) cur.lines.push(l); else preface.push(l); }
  }
  if (cur) sections.push(cur);
  return (
    <div className="flex flex-col gap-6">
      {preface.some(l => l.trim()) && <div className="text-sm text-gray-400 normal-case leading-relaxed flex flex-col gap-1">{preface.filter(l => l.trim()).map((l, i) => <p key={i}>{inline(l)}</p>)}</div>}
      {sections.map((s, idx) => {
        const { a, Icon } = sectionMeta(s.title);
        return (
          <div key={idx} className="flex flex-col gap-3">
            <div className={`${ACCENTS[a]} border p-4 rounded-xl flex items-center gap-3`}>
              <Icon className={`w-5 h-5 flex-shrink-0 ${TITLE_COLORS[a]}`} />
              <h3 className={`font-grotesk text-lg font-bold tracking-wide ${TITLE_COLORS[a]}`}>{inline(s.title)}</h3>
            </div>
            <div className="px-1">{renderBody(s.lines)}</div>
          </div>
        );
      })}
    </div>
  );
}

const RekomendasiView: React.FC<Props> = ({ accountId, accountName, thLevel, thImg }) => {
  const [items, setItems] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [openId, setOpenId] = useState<number | null>(null);
  // Dual-language: per-item lang + translate cache.
  const [lang, setLang] = useState<Record<number, 'en' | 'id'>>({});       // pilihan tampil per item
  const [tr, setTr] = useState<Record<number, { id?: string; loading?: boolean }>>({}); // cache + loading

  const load = useCallback(async () => {
    setLoading(true); setError('');
    try {
      const url = accountId ? `${API}/api/db/research?account_id=${encodeURIComponent(accountId)}` : `${API}/api/db/research`;
      const r = await fetch(url);
      const j = await r.json();
      setItems(j.research || []);
    } catch { setError('Gagal load dari DB (cek backend & koneksi Postgres).'); }
    setLoading(false);
  }, [accountId]);

  useEffect(() => { load(); }, [load]);

  const del = useCallback(async (id: number) => {
    if (!confirm('Hapus rekomendasi ini dari DB?')) return;
    try {
      await fetch(`${API}/api/db/research/delete`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ id }) });
      setItems(prev => prev.filter(x => x.id !== id));
    } catch { setError('Gagal hapus.'); }
  }, []);

  // Translate report ke ID (cache server-side di stats.translations).
  const toId = useCallback(async (id: number) => {
    if (tr[id]?.id || tr[id]?.loading) return;
    setTr(t => ({ ...t, [id]: { ...t[id], loading: true } }));
    try {
      const r = await fetch(`${API}/api/research/translate`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ id, to: 'id' }) });
      const j = await r.json();
      setTr(t => ({ ...t, [id]: { id: j.report, loading: false } }));
    } catch {
      setTr(t => ({ ...t, [id]: { ...t[id], loading: false } }));
      setError('Gagal translate. Cek backend.');
    }
  }, [tr]);

  const pickLang = (id: number, l: 'en' | 'id') => {
    setLang(s => ({ ...s, [id]: l }));
    if (l === 'id' && !tr[id]?.id && !tr[id]?.loading) toId(id);
  };

  return (
    <div className="flex flex-col gap-5 animate-in fade-in">
      <div className="flex flex-col md:flex-row items-center justify-center md:justify-between text-center md:text-left flex-wrap gap-4">
        <div className="flex flex-col md:flex-row items-center gap-3">
          {thImg ? (
            <div className="relative w-12 h-12 flex-shrink-0">
              <div className="absolute inset-0 bg-green-500/25 blur-lg rounded-full" />
              <img src={thImg} alt={`TH${thLevel}`} className="w-full h-full object-contain relative z-10 drop-shadow-lg" onError={e => (e.currentTarget.style.display = 'none')} />
            </div>
          ) : (
            <div className="p-2 bg-green-500/10 rounded-lg text-green-400"><FileText className="w-6 h-6" /></div>
          )}
          <div>
            <h2 className="font-grotesk text-2xl text-white tracking-wider">Rekomendasi</h2>
            <p className="text-xs text-gray-500 normal-case">Riwayat deep research tersimpan di DB{accountName ? ` · ${accountName}` : ' · semua akun'}</p>
          </div>
        </div>
        <button onClick={load} className="bg-[var(--panel-bg)] border border-white/10 text-gray-300 px-4 py-2.5 rounded-xl hover:border-green-500/30 transition-all flex items-center gap-2 text-sm">
          <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} /> Refresh
        </button>
      </div>

      {error && (
        <div className="bg-red-500/5 border border-red-500/20 rounded-2xl p-5 flex items-center gap-3">
          <AlertCircle className="w-5 h-5 text-red-400" /><span className="text-sm text-gray-400 normal-case">{error}</span>
        </div>
      )}

      {!loading && items.length === 0 && !error && (
        <div className="flex flex-col items-center justify-center py-20 gap-3 text-center">
          <FileText className="w-14 h-14 text-green-400/30" />
          <p className="text-gray-500 normal-case max-w-md">Belum ada rekomendasi tersimpan. Jalanin <strong className="text-green-400">Live AI Research</strong> dulu — hasilnya otomatis kesimpen di sini.</p>
        </div>
      )}

      <div className="flex flex-col gap-3">
        {items.map(it => {
          const open = openId === it.id;
          return (
            <div key={it.id} className="bg-[var(--panel-bg)] border border-white/5 rounded-2xl overflow-hidden">
              <div className="flex items-center gap-3 px-5 py-4 cursor-pointer hover:bg-white/[0.02]" onClick={() => setOpenId(open ? null : it.id)}>
                {open ? <ChevronDown className="w-4 h-4 text-green-400 flex-shrink-0" /> : <ChevronRight className="w-4 h-4 text-gray-500 flex-shrink-0" />}
                {it.th_level ? (
                  <div className="relative w-10 h-10 flex-shrink-0">
                    <div className="absolute inset-0 bg-green-500/20 blur-md rounded-full" />
                    <img src={`/assets/buildings/home-village/town_hall/level_${it.th_level}.webp`} alt={`TH${it.th_level}`} className="w-full h-full object-contain relative z-10 drop-shadow" onError={e => (e.currentTarget.style.display = 'none')} />
                  </div>
                ) : null}
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    {it.th_level && <span className="text-xs px-2 py-0.5 rounded-full bg-green-500/15 text-green-400 font-bold">TH{it.th_level}</span>}
                    <span className="text-sm text-white font-bold truncate">{it.account_name || 'Umum'}</span>
                  </div>
                  <p className="text-xs text-gray-500 normal-case truncate mt-0.5">{it.query}</p>
                </div>
                <div className="flex flex-wrap items-center justify-start sm:justify-end gap-3 flex-shrink-0 text-[10px] text-gray-500 w-full sm:w-auto mt-2 sm:mt-0">
                  {it.stats?.sources != null && <span className="flex items-center gap-1"><Globe className="w-3 h-3" />{it.stats.sources}</span>}
                  {it.created_at && <span className="flex items-center gap-1"><Clock className="w-3 h-3" />{it.created_at.slice(0, 16).replace('T', ' ')}</span>}
                  <button onClick={e => { e.stopPropagation(); del(it.id); }} className="text-red-400/60 hover:text-red-400 p-1"><Trash2 className="w-4 h-4" /></button>
                </div>
              </div>
              {open && (
                <div className="px-6 md:px-8 py-5 border-t border-white/5">
                  {/* Lang toggle */}
                  <div className="flex items-center justify-end gap-1 mb-4">
                    <span className="text-[10px] uppercase tracking-widest text-gray-600 mr-1">Bahasa</span>
                    {(['en', 'id'] as const).map(l => (
                      <button key={l} onClick={() => pickLang(it.id, l)} disabled={tr[it.id]?.loading}
                        className={`px-2.5 py-1 rounded-lg text-xs font-bold border transition-all disabled:opacity-50 ${
                          (lang[it.id] || 'en') === l ? 'bg-green-500/20 border-green-500/40 text-green-400' : 'bg-white/5 border-white/10 text-gray-500 hover:text-white'}`}>
                        {l === 'en' ? 'EN' : 'ID'}
                      </button>
                    ))}
                    {tr[it.id]?.loading && <span className="text-[10px] text-gray-500 normal-case animate-pulse ml-1">translating…</span>}
                  </div>
                  {md((lang[it.id] || 'en') === 'id' ? (tr[it.id]?.id ?? it.report) : it.report)}
                  {it.sources?.length > 0 && (
                    <div className="mt-5 pt-4 border-t border-white/5">
                      <h4 className="font-grotesk text-xs uppercase tracking-widest text-gray-500 mb-2">Sources ({it.sources.length})</h4>
                      {it.sources.map((s: any, i: number) => (
                        <a key={i} href={s.url} target="_blank" rel="noopener noreferrer" className="block text-sm text-blue-400 hover:underline normal-case truncate">{i + 1}. {s.title || s.url}</a>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
};

export default RekomendasiView;
