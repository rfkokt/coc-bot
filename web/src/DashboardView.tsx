import React from 'react';
import { Play, Square, Settings2, ScrollText, Swords, RefreshCw } from 'lucide-react';
import { AppState, fmtDur, fmtNum } from './types';

// Parsers untuk log
const renderLogLine = (line: string, index: number) => {
  if (!line.trim()) return null;

  // Default style
  let className = "py-1 border-b border-white/5 opacity-80 transition-all hover:opacity-100";
  let content: React.ReactNode = line;

  // 1. Python Warnings (e.g. PyTorch deprecations)
  if (line.includes('UserWarning') || line.includes('FutureWarning') || line.startsWith('  ')) {
    return <div key={index} className="text-yellow-500/60 text-[10px] leading-tight py-0.5">{line}</div>;
  }

  // 2. Bot Started
  if (line.includes('COC Bot started')) {
    className = "py-2 text-neon font-bold text-sm animate-pulse border-none";
    content = <span className="flex items-center gap-2"><span className="w-2 h-2 rounded-full bg-neon animate-ping" /> {line}</span>;
  }

  // 3. Loot Scan
  else if (line.includes('gold=') && line.includes('elixir=')) {
    className = "py-1 border-b border-white/5 opacity-90";

    // Parse loot text to make it colorful
    const match = line.match(/^(\[[^\]]+\](?: \[\d+\])?)(.*)/);
    if (match) {
      const timePrefix = match[1];
      let rest = match[2];

      rest = rest.replace(/gold=([\d,]+)/g, '<span class="text-yellow-400 font-bold">gold=$1</span>');
      rest = rest.replace(/elixir=([\d,]+)/g, '<span class="text-purple-400 font-bold">elixir=$1</span>');
      rest = rest.replace(/dark=([\d,]+)/g, '<span class="text-gray-400 dark:text-gray-300 font-bold">dark=$1</span>');

      content = (
        <span className="flex gap-2">
          <span className="opacity-50">{timePrefix}</span>
          <span dangerouslySetInnerHTML={{ __html: rest }} />
        </span>
      );
    }
  }

  // 4. Searching/Scanning indicator
  else if (line.includes('nyari enemy') || line.includes('cari base')) {
    className = "py-1 border-b border-white/5 text-blue-400";
    content = <span className="flex items-center gap-2"><span className="w-1.5 h-1.5 rounded-full bg-blue-400 animate-pulse" /> {line}</span>;
  }

  // 5. Recovery / Errors
  else if (line.includes('recover') || line.includes('bukan layar battle') || line.includes('error')) {
    className = "py-1 border-b border-red-500/20 text-red-400";
    content = <span className="flex items-center gap-2"><span className="w-2 h-2 rounded-full bg-red-500 animate-ping" /> {line}</span>;
  }

  // Default Time prefix formatting
  else {
    const match = line.match(/^(\[[^\]]+\])(.*)/);
    if (match) {
      content = (
        <span className="flex gap-2">
          <span className="opacity-50">{match[1]}</span>
          <span>{match[2]}</span>
        </span>
      );
    }
  }

  return (
    <div key={index} className={className}>
      {content}
    </div>
  );
};

type Props = {
  state: AppState;
  act: (action: string) => void;
  settings: Record<string, string>;
  setSettings: React.Dispatch<React.SetStateAction<{ GOLD_MIN: string; ELIXIR_MIN: string; DARK_MIN: string; STAR1_DAMAGE: string; BATTLE_SECS: string; }>>;
  saveConfig: (e: React.FormEvent) => void;
  statsEntries: [string, any][];
  log: string;
  logRef: React.RefObject<HTMLDivElement>;
};

const DashboardView = ({ state, act, settings, setSettings, saveConfig, statsEntries, log, logRef }: Props) => {
  return (
    <div className="flex flex-col gap-8 animate-in fade-in duration-500">
      {/* MAIN CONTROLS */}
      <section className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <button
          disabled={state.running}
          onClick={() => act('start')}
          className="liquid-glass hover:bg-neon/20 hover:border-neon transition-all p-6 rounded-[24px] flex flex-col items-center justify-center gap-4 disabled:opacity-50 disabled:pointer-events-none group"
        >
          <Play className="w-12 h-12 text-neon group-hover:scale-110 transition-transform" />
          <span className="font-grotesk text-[24px]">Start Bot</span>
        </button>

        <button
          disabled={state.running}
          onClick={() => act('start_test')}
          className="liquid-glass hover:bg-blue-500/20 hover:border-blue-500 transition-all p-6 rounded-[24px] flex flex-col items-center justify-center gap-4 disabled:opacity-50 disabled:pointer-events-none group"
        >
          <RefreshCw className="w-12 h-12 text-blue-500 group-hover:scale-110 transition-transform" />
          <span className="font-grotesk text-[24px]">Start (Test)</span>
        </button>

        <button
          disabled={!state.running}
          onClick={() => act('stop')}
          className="liquid-glass hover:bg-red-500/20 hover:border-red-500 transition-all p-6 rounded-[24px] flex flex-col items-center justify-center gap-4 disabled:opacity-50 disabled:pointer-events-none group"
        >
          <Square className="w-12 h-12 text-red-500 group-hover:scale-110 transition-transform" />
          <span className="font-grotesk text-[24px]">Stop Bot</span>
        </button>
      </section>

      {/* PER-ACCOUNT STATS */}
      <section className="liquid-glass p-8 rounded-[32px]">
        <div className="flex items-center gap-3 mb-6">
          <Swords className="text-neon w-8 h-8" />
          <h2 className="font-grotesk text-[36px] leading-none">Loot per Akun</h2>
          <span className="ml-auto text-xs opacity-50 bg-[var(--panel-bg)] px-3 py-1 rounded-full normal-case">Auto-deteksi nama akun</span>
        </div>
        {statsEntries.length === 0 ? (
          <p className="opacity-50 normal-case">Belum ada data. Jalanin bot &mdash; nama akun ke-deteksi otomatis dari home village.</p>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {statsEntries.map(([name, s]) => (
              <div key={name} className="bg-[var(--panel-bg)] border border-white/10 rounded-[20px] p-6 flex flex-col gap-4">
                <div className="flex items-center justify-between">
                  <span className="font-grotesk text-[22px] text-neon truncate">{name}</span>
                  <span className="text-xs opacity-60 bg-black/20 px-3 py-1 rounded-full">{fmtDur(s.seconds)}</span>
                </div>
                <div className="grid grid-cols-2 gap-3">
                  {[
                    { l: 'Serangan', v: fmtNum(s.attacks), c: 'text-cream' },
                    { l: 'Gold', v: fmtNum(s.gold), c: 'text-yellow-400' },
                    { l: 'Elixir', v: fmtNum(s.elixir), c: 'text-purple-400' },
                    { l: 'Dark', v: fmtNum(s.dark), c: 'text-gray-400' },
                  ].map(({ l, v, c }) => (
                    <div key={l} className="bg-black/20 rounded-xl p-3 text-center">
                      <div className={`text-lg font-bold ${c}`}>{v}</div>
                      <div className="text-[9px] opacity-50 uppercase tracking-widest mt-1">{l}</div>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        )}
      </section>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        {/* CONFIGURATION */}
        <section className="liquid-glass p-8 rounded-[32px] flex flex-col">
          <div className="flex items-center gap-3 mb-8">
            <Settings2 className="text-neon w-8 h-8" />
            <h2 className="font-grotesk text-[36px] leading-none">Settings</h2>
          </div>

          <form onSubmit={saveConfig} className="flex flex-col gap-6 flex-grow">
            <div className="grid grid-cols-2 gap-6">
              {[
                { k: 'GOLD_MIN', l: 'Min Gold' },
                { k: 'ELIXIR_MIN', l: 'Min Elixir' },
                { k: 'DARK_MIN', l: 'Min Dark' },
                { k: 'STAR1_DAMAGE', l: 'Star 1 DMG (%)' },
                { k: 'BATTLE_SECS', l: 'Battle Timeout (s)' },
              ].map(({ k, l }) => (
                <div key={k} className="flex flex-col gap-2">
                  <label className="text-sm opacity-70">{l}</label>
                  <input
                    type="text"
                    className="bg-[var(--panel-bg)] border border-black/10 dark:border-white/10 rounded-xl px-4 py-3 focus:outline-none focus:border-neon focus:ring-1 focus:ring-neon transition-all text-inherit"
                    value={(settings as any)[k] || ''}
                    onChange={e => setSettings(s => ({ ...s, [k]: e.target.value }))}
                  />
                </div>
              ))}
            </div>

            <button type="submit" className="mt-auto bg-neon text-white dark:text-background font-bold py-4 rounded-xl hover:opacity-80 transition-opacity flex items-center justify-center gap-2">
              SAVE CONFIGURATION
            </button>
          </form>
        </section>

        {/* LOGS */}
        <section className="liquid-glass p-8 rounded-[32px] flex flex-col h-[500px]">
          <div className="flex items-center gap-3 mb-6">
            <ScrollText className="text-neon w-8 h-8" />
            <h2 className="font-grotesk text-[36px] leading-none">Live Logs</h2>
            <span className="ml-auto text-xs opacity-50 bg-[var(--panel-bg)] px-3 py-1 rounded-full">Auto-refresh 3s</span>
          </div>

          <div ref={logRef} className="bg-[var(--panel-bg)] rounded-xl p-4 flex-grow overflow-auto text-xs text-green-600 dark:text-green-400 font-mono leading-relaxed flex flex-col">
            {!log ? "Menunggu log..." : log.split('\n').map((line, i) => renderLogLine(line, i))}
          </div>
        </section>
      </div>
    </div>
  );
};

export default DashboardView;
