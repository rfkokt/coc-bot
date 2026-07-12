import React, { useEffect, useState, useRef, useMemo, useCallback } from 'react';
import { Play, Square, Settings2, ScrollText, Swords, AlertCircle, RefreshCw, Sun, Moon, BookOpen } from 'lucide-react';
import DeepResearchView from './DeepResearchView';
import LiveResearchView from './LiveResearchView';
import RekomendasiView from './RekomendasiView';

const App = () => {
  const [theme, setTheme] = useState('dark');
  const [state, setState] = useState<any>({ running: false, status: 'Loading...', adbcls: 'off', adbmsg: '...', dotcls: 'off' });
  const [log, setLog] = useState('');
  const [statsAccounts, setStatsAccounts] = useState<Record<string, any>>({});
  const [settings, setSettings] = useState({
    GOLD_MIN: '', ELIXIR_MIN: '', DARK_MIN: '', STAR1_DAMAGE: '', BATTLE_SECS: ''
  });
  type Account = { id: string; name: string; tag?: string; th_level: number; json: string; result: any; date: number };
  const [accounts, setAccounts] = useState<Account[]>(() => {
    try {
      const saved = localStorage.getItem('coc_accounts');
      if (saved) return JSON.parse(saved);
      // Migrate old data
      const oldJson = localStorage.getItem('coc_analyze_json');
      const oldRes = localStorage.getItem('coc_analyze_result');
      if (oldJson && oldRes) {
        const res = JSON.parse(oldRes);
        const acc = { id: Date.now().toString(), name: `Town Hall ${res.th_level} (Migrated)`, th_level: res.th_level, json: oldJson, result: res, date: Date.now() };
        localStorage.setItem('coc_accounts', JSON.stringify([acc]));
        localStorage.removeItem('coc_analyze_json');
        localStorage.removeItem('coc_analyze_result');
        return [acc];
      }
    } catch {}
    return [];
  });
  const [activeAccountId, setActiveAccountId] = useState<string | null>(() => {
    try { return localStorage.getItem('coc_active_account') || null; } catch { return null; }
  });
  
  useEffect(() => {
    if (activeAccountId) localStorage.setItem('coc_active_account', activeAccountId);
    else localStorage.removeItem('coc_active_account');
  }, [activeAccountId]);
  
  const activeAccount = accounts.find(a => a.id === activeAccountId);
  const analyzeJson = activeAccount?.json || '';
  const analyzeResult = activeAccount?.result || null;
  const [uploadJsonStr, setUploadJsonStr] = useState('');
  const [updateJsonStr, setUpdateJsonStr] = useState('');
  const [showUpdateJson, setShowUpdateJson] = useState(false);
  
  const [analyzeLoading, setAnalyzeLoading] = useState(false);
  const [analyzeError, setAnalyzeError] = useState('');
  const [selectedUpgrade, setSelectedUpgrade] = useState<any>(null);
  const [researchData, setResearchData] = useState<any>(null);
  const [researchLoading, setResearchLoading] = useState(false);
  const [researchError, setResearchError] = useState('');
  
  const logRef = useRef<HTMLDivElement>(null);

  const [builderCount, setBuilderCount] = useState<number>(() => {
    try {
      const saved = localStorage.getItem('coc_builder_count');
      if (saved) return parseInt(saved);
    } catch {}
    return 5;
  });
  
  useEffect(() => {
    localStorage.setItem('coc_builder_count', builderCount.toString());
  }, [builderCount]);

  useEffect(() => {
    document.documentElement.classList.toggle('light', theme === 'light');
  }, [theme]);

  // auto-sync akun + loot ke DB (VPS Postgres) tiap akun berubah — best-effort, ga blok UI
  useEffect(() => {
    if (!accounts.length) return;
    const t = setTimeout(() => {
      fetch('http://localhost:5050/api/db/sync', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ accounts }),
      }).catch(() => {});
    }, 1500);
    return () => clearTimeout(t);
  }, [accounts]);

  // Poll state and log
  useEffect(() => {
    const fetchState = async () => {
      try {
        const [resState, resLog, resStats] = await Promise.all([
          fetch('http://localhost:5050/state').then(r => r.json()),
          fetch('http://localhost:5050/log').then(r => r.text()),
          fetch('http://localhost:5050/stats.json').then(r => r.json()).catch(() => ({ accounts: {} }))
        ]);
        setState(resState);
        setLog(resLog);
        setStatsAccounts(resStats.accounts || {});
      } catch (e) {
        console.error('API Error:', e);
      }
    };
    
    fetchState();
    const iv = setInterval(fetchState, 3000);
    return () => clearInterval(iv);
  }, []);

  const [staticData, setStaticData] = useState<any>(null);
  
  useEffect(() => {
    fetch('/assets/static_data.json')
      .then(r => r.json())
      .then(d => setStaticData(d))
      .catch(e => console.error("Failed to load static data", e));
  }, []);

  useEffect(() => {
    fetch('http://localhost:5050/')
      .then(r => r.text())
      .then(html => {
        const doc = new DOMParser().parseFromString(html, 'text/html');
        const inputs = doc.querySelectorAll('input[name]');
        const s: any = {};
        inputs.forEach((i: any) => s[i.name] = i.value);
        setSettings(prev => ({ ...prev, ...s }));
      });
  }, []);

  useEffect(() => {
    if (logRef.current) {
      logRef.current.scrollTop = logRef.current.scrollHeight;
    }
  }, [log]);

  const act = async (action: string) => {
    setState((s: any) => ({ ...s, status: 'Processing...' }));
    await fetch(`http://localhost:5050/action?a=${action}`, { method: 'POST' });
  };

  const saveConfig = async (e: React.FormEvent) => {
    e.preventDefault();
    const formData = new URLSearchParams();
    Object.entries(settings).forEach(([k, v]) => formData.append(k, String(v)));
    await fetch('http://localhost:5050/save', { method: 'POST', body: formData });
    alert('Config Tersimpan!');
  };

  const doAnalyze = async (jsonStr: string) => {
    if (!jsonStr) return;
    setAnalyzeLoading(true);
    setAnalyzeError('');
    try {
      const res = await fetch('http://localhost:5050/api/analyze', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: jsonStr
      });
      if (!res.ok) throw new Error(await res.text());
      const data = await res.json();

      // Lookup nama akun asli dari player tag (via ClashKing proxy) — biar match sama stats bot (OCR nama).
      let accName = `Town Hall ${data.th_level}`;
      let accTag: string | undefined;
      try {
        const parsed = JSON.parse(jsonStr);
        if (parsed.tag) {
          accTag = parsed.tag;
          const p = await fetch(`http://localhost:5050/api/player?tag=${encodeURIComponent(parsed.tag)}`).then(r => r.json()).catch(() => null);
          if (p && p.name) accName = p.name;
        }
      } catch {}

      const newAcc: Account = {
        id: Date.now().toString(),
        name: accName,
        tag: accTag,
        th_level: data.th_level,
        json: jsonStr,
        result: data,
        date: Date.now()
      };
      
      setAccounts(prev => {
        const updated = [newAcc, ...prev];
        localStorage.setItem('coc_accounts', JSON.stringify(updated));
        return updated;
      });
      setActiveAccountId(newAcc.id);
      setUploadJsonStr('');
    } catch (e: any) {
      setAnalyzeError(e.message);
    }
    setAnalyzeLoading(false);
  };

  // Re-analyze akun tersimpan pakai JSON yg sudah ada -> update hasil di tempat (bukan bikin akun baru).
  // Re-analyze akun tersimpan. Kalau newJson diisi -> replace JSON village akun itu (load JSON baru),
  // kalau tidak -> analisis ulang JSON lama dengan data terbaru. Update di tempat (bukan bikin akun baru).
  const reanalyzeAccount = async (acc: Account, newJson?: string) => {
    const jsonStr = newJson ?? acc?.json;
    if (!jsonStr) { setAnalyzeError('Tidak ada JSON untuk dianalisis.'); return; }

    // Guard: kalau load JSON BARU, pastikan player tag-nya cocok dengan akun ini.
    if (newJson) {
      let newTag: string | undefined;
      try {
        newTag = JSON.parse(newJson)?.tag;
      } catch {
        setAnalyzeError('JSON tidak valid — gagal di-parse.');
        return;
      }
      if (!newTag) {
        setAnalyzeError('JSON tidak punya player tag. Pastikan ini export village yang benar.');
        return;
      }
      const norm = (t?: string) => (t || '').toUpperCase().replace(/^#/, '').trim();
      if (acc.tag && norm(newTag) !== norm(acc.tag)) {
        setAnalyzeError(`JSON ini milik akun lain (${newTag}), bukan ${acc.tag}. Update dibatalkan.`);
        return;
      }
    }

    setAnalyzeLoading(true);
    setAnalyzeError('');
    try {
      const res = await fetch('http://localhost:5050/api/analyze', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: jsonStr
      });
      if (!res.ok) throw new Error(await res.text());
      const data = await res.json();
      setAccounts(prev => {
        const updated = prev.map(a => a.id === acc.id
          ? { ...a, th_level: data.th_level, json: jsonStr, tag: (() => { try { return JSON.parse(jsonStr)?.tag || a.tag; } catch { return a.tag; } })(), result: data, date: Date.now() }
          : a);
        localStorage.setItem('coc_accounts', JSON.stringify(updated));
        return updated;
      });
      setUpdateJsonStr('');
      setShowUpdateJson(false);
    } catch (e: any) {
      setAnalyzeError(e.message);
    }
    setAnalyzeLoading(false);
  };

  const doDeepResearch = useCallback(async (acc: Account) => {
    if (!acc?.json) { setResearchError('No village data to research.'); return; }
    setResearchLoading(true);
    setResearchError('');
    setResearchData(null);
    try {
      const res = await fetch('http://localhost:5050/api/research', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ village: JSON.parse(acc.json) })
      });
      if (!res.ok) throw new Error(await res.text());
      setResearchData(await res.json());
    } catch (e: any) {
      setResearchError(e.message);
    }
    setResearchLoading(false);
  }, []);

  const handleFile = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = (ev) => {
      const result = ev.target?.result as string;
      setUploadJsonStr(result);
      doAnalyze(result);
    };
    reader.readAsText(file);
    e.target.value = ''; // allow picking same file again
  };

  const deleteAccount = (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    setAccounts(prev => {
      const updated = prev.filter(a => a.id !== id);
      localStorage.setItem('coc_accounts', JSON.stringify(updated));
      return updated;
    });
    if (activeAccountId === id) setActiveAccountId(null);
  };

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

  const [view, setView] = useState<'dashboard' | 'analyze'>(
    (window.location.hash.replace('#', '') as any) === 'analyze' ? 'analyze' : 'dashboard'
  );

  useEffect(() => {
    window.location.hash = view;
  }, [view]);

  useEffect(() => {
    const handleHash = () => {
      const hash = window.location.hash.replace('#', '');
      if (hash === 'dashboard' || hash === 'analyze') setView(hash);
    };
    window.addEventListener('hashchange', handleHash);
    return () => window.removeEventListener('hashchange', handleHash);
  }, []);

  const [activeTab, setActiveTab] = useState(() => {
    try { return localStorage.getItem('coc_active_tab') || 'Heroes'; } catch { return 'Heroes'; }
  });

  useEffect(() => {
    localStorage.setItem('coc_active_tab', activeTab);
  }, [activeTab]);

  const fmtDur = (secs: number) => {
    if (!secs) return '0s';
    const y = Math.floor(secs / 31536000); // 365 days
    const mo = Math.floor((secs % 31536000) / 2592000); // 30 days
    const d = Math.floor((secs % 2592000) / 86400);
    const h = Math.floor((secs % 86400) / 3600);
    const m = Math.floor((secs % 3600) / 60);
    
    let s = [];
    if (y > 0) s.push(`${y}y`);
    if (mo > 0) s.push(`${mo}mo`);
    if (d > 0) s.push(`${d}d`);
    if (h > 0 && y === 0 && mo === 0) s.push(`${h}h`); // Only show hours if it's less than a month
    if (m > 0 && y === 0 && mo === 0 && d === 0) s.push(`${m}m`); // Only show mins if less than a day
    
    return s.length > 0 ? s.join(' ') : '0s';
  };
  const fmtNum = (n: number) => (n || 0).toLocaleString();
  const statsEntries = Object.entries(statsAccounts);

  const getUpgradePath = (rec: any) => {
    if (!staticData || !rec.id) return null;
    let itemData = null;
    for (const key of Object.keys(staticData)) {
      itemData = staticData[key].find((x: any) => x._id === rec.id);
      if (itemData) break;
    }
    
    if (!itemData && rec.name) {
      for (const key of Object.keys(staticData)) {
        itemData = staticData[key].find((x: any) => x.name === rec.name);
        if (itemData) break;
      }
    }

    if (!itemData) return null;

    // Cap the max level based on the user's Town Hall level
    let actualMax = 0;
    if (itemData.levels && analyzeResult?.th_level) {
        for (const l of itemData.levels) {
            const req = l.required_townhall || l.village_townhall_level || 1;
            if (req <= analyzeResult.th_level && l.level > actualMax) {
                actualMax = l.level;
            }
        }
    }
    if (actualMax > 0) rec.max = actualMax;

    let path: any[] = [];
    let totalCost: Record<string, number> = { 'Gold': 0, 'Elixir': 0, 'Dark Elixir': 0 };
    let totalTime = 0;
    const rootRes = itemData.upgrade_resource;

    const isBuilding = !!rec.levels;
    const levelsDict = isBuilding ? rec.levels : { [rec.cur]: 1 };

    for (const [lvlStr, count] of Object.entries(levelsDict)) {
      const curLvl = parseInt(lvlStr);
      const cnt = count as number;
      if (curLvl >= rec.max) continue;

      for (let l = curLvl + 1; l <= rec.max; l++) {
        const lvlData = itemData.levels.find((x: any) => x.level === l);
        if (!lvlData) continue;
        
        const cost = lvlData.build_cost || lvlData.upgrade_cost || 0;
        const time = lvlData.build_time || lvlData.upgrade_time || 0;
        let res = lvlData.upgrade_resource || rootRes || 'Gold';
        if (res === 'DarkElixir' || res === 'Dark') res = 'Dark Elixir';

        if (cost && totalCost[res] !== undefined) totalCost[res] += cost * cnt;
        totalTime += time * cnt;
        
        path.push({ from: l - 1, to: l, cost, time, res });
      }
    }
    const uniquePath = path.filter((v, i, a) => a.findIndex(t => t.to === v.to) === i).sort((a,b) => a.to - b.to);
    return { path: uniquePath, totalCost, totalTime, itemData };
  };

  const villageTotals = useMemo(() => {
    if (!staticData || !analyzeResult?.recs) return null;
    let t: any = { 'Gold': 0, 'Elixir': 0, 'Dark Elixir': 0, time: 0 };
    for (const rec of analyzeResult.recs) {
       const u = getUpgradePath(rec);
       if (u) {
          t['Gold'] += (u.totalCost['Gold'] || 0);
          t['Elixir'] += (u.totalCost['Elixir'] || 0);
          t['Dark Elixir'] += (u.totalCost['Dark Elixir'] || 0);
          t.time += (u.totalTime || 0);
       }
    }
    return t;
  }, [staticData, analyzeResult]);

  const getImageUrl = (name: string, cat?: string, level?: number) => {
    let slug = name.toLowerCase().replace(/ /g, '_').replace(/\./g, '');
    if (name === 'L.A.S.S.I') slug = 'lassi';
    
    // Handle Altars (map to hero image)
    if (name.includes('Altar')) {
      const heroSlug = slug.replace('_altar', '');
      return `/assets/heroes/${heroSlug}/icon.webp`;
    }

    if (name === 'Town Hall') return `/assets/buildings/home-village/town_hall/level_${level || 1}.webp`;
    if (name === 'Builder Hall') return `/assets/buildings/builder-base/builder_hall/level_${level || 1}.webp`;

    // Hardcode unknown building IDs and weaponized huts
    if (name === 'Building 1000093' || name === 'Helper Hut' || name.startsWith("Builder's Hut")) return `/assets/buildings/home-village/builder's_hut/level_${level || 1}.webp`;

    if (cat === 'hero') return `/assets/heroes/${slug}/icon.webp`;
    if (cat === 'equipment') {
      slug = slug.replace('_(epic)', '');
      return `/assets/equipment/${slug}.webp`;
    }
    if (cat === 'pet') return `/assets/pets/${slug}/icon.webp`;
    if (cat === 'troop' || cat === 'dark_troop' || cat === 'siege') return `/assets/troops/${slug}/icon.webp`;
    
    if (cat === 'spell') {
      if (slug === 'heal') slug = 'healing';
      if (!slug.endsWith('_spell')) slug += '_spell';
      return `/assets/spells/${slug}.webp`;
    }

    // Handle Traps explicitly
    if (cat === 'trap') return `/assets/traps/home-village/${slug}/level_${level || 1}.webp`;

    // Handle Builder's hut apostrophe if slug removed it (though ClashKing left it)
    if (name === "Builder's Hut") return `/assets/buildings/home-village/builder's_hut/level_${level || 1}.webp`;

    // Handle special buildings
    if (name === 'Poison Tower') return `/assets/buildings/home-village/spell_tower/level_${level || 1}.webp`;
    if (name.includes('(BB2)')) {
      const bbSlug = slug.replace('_(bb2)', '');
      return `/assets/buildings/builder-base/${bbSlug}/level_${level || 1}.webp`;
    }

    // Try fallback for buildings
    return `/assets/buildings/home-village/${slug}/level_${level || 1}.webp`;
  };

  const tabs = analyzeResult ? [
    { id: 'LiveResearch', title: 'Live AI Research', data: ['x'] },
    { id: 'Rekomendasi', title: 'Rekomendasi', data: ['x'] },
    { id: 'Priority', title: 'Priority Guide', data: analyzeResult.recs },
    { id: 'TownHall', title: 'Town Hall', data: analyzeResult.recs?.filter((r: any) => r.cat === 'townhall') },
    { id: 'Defenses', title: 'Defenses', data: analyzeResult.recs?.filter((r: any) => r.cat === 'defense') },
    { id: 'Traps', title: 'Traps', data: analyzeResult.recs?.filter((r: any) => r.cat === 'trap') },
    { id: 'ArmyBldg', title: 'Army', data: analyzeResult.recs?.filter((r: any) => r.cat === 'army_bldg') },
    { id: 'Resources', title: 'Resources', data: analyzeResult.recs?.filter((r: any) => r.cat === 'resource') },
    { id: 'Troops', title: 'Troops', data: analyzeResult.recs?.filter((r: any) => r.cat === 'troop') },
    { id: 'Spells', title: 'Spells', data: analyzeResult.recs?.filter((r: any) => r.cat === 'spell') },
    { id: 'DarkTroops', title: 'Dark Troops', data: analyzeResult.recs?.filter((r: any) => r.cat === 'dark_troop') },
    { id: 'Sieges', title: 'Sieges', data: analyzeResult.recs?.filter((r: any) => r.cat === 'siege') },
    { id: 'Heroes', title: 'Heroes', data: analyzeResult.recs?.filter((r: any) => r.cat === 'hero') },
    { id: 'Equipment', title: 'Equipment', data: analyzeResult.equip_recs },
    { id: 'Pets', title: 'Pets', data: analyzeResult.pet_recs },
    { id: 'Walls', title: 'Walls', data: analyzeResult.recs?.filter((r: any) => r.cat === 'wall') },
    { id: 'Strategies', title: 'Strategies', data: analyzeResult.strategies },
    { id: 'DeepResearch', title: 'Deep Research', data: [] }
  ].filter(t => t.data && t.data.length > 0) : [];

  const PRIORITY_TIERS = [
    { tier: 1, title: "Tier 1: Core Offense & Heroes", desc: "Prioritize these first to boost your attacking power and farm loot faster.", items: ["Town Hall", "Laboratory", "Clan Castle", "Army Camp", "Spell Factory", "Dark Spell Factory", "Pet House", "Barbarian King", "Archer Queen", "Grand Warden", "Royal Champion"] },
    { tier: 2, title: "Tier 2: Resources", desc: "Keep storages maxed to afford expensive upgrades later.", items: ["Gold Storage", "Elixir Storage", "Dark Elixir Storage", "Gold Mine", "Elixir Collector", "Dark Elixir Drill"] },
    { tier: 3, title: "Tier 3: Heavy Defenses", desc: "High impact defenses that change the tide of a battle.", items: ["Eagle Artillery", "Scattershot", "Monolith", "Inferno Tower", "X-Bow", "Air Defense"] },
    { tier: 4, title: "Tier 4: Splash Defenses", desc: "Great against swarms of small troops.", items: ["Wizard Tower", "Bomb Tower"] },
    { tier: 5, title: "Tier 5: Point Defenses", desc: "Basic defensive structures to deal consistent damage.", items: ["Archer Tower", "Cannon", "Mortar", "Hidden Tesla", "Air Sweeper"] },
    { tier: 6, title: "Tier 6: Traps & Walls", desc: "Upgrade these with excess resources while waiting for builders.", items: [] } // Fallback for traps and walls
  ];

  return (
    <div className="bg-background min-h-screen text-cream relative selection:bg-neon selection:text-background font-mono uppercase pb-20 transition-colors duration-300">
      <div 
        className="fixed inset-0 z-0 pointer-events-none bg-cover bg-center transition-all duration-300"
        style={{ backgroundImage: 'url(/texture.png)', mixBlendMode: 'var(--texture-blend)' as any, opacity: 'var(--texture-op)' as any }}
      />

      <div className="relative z-10 w-full max-w-[1400px] mx-auto px-6 py-12 flex flex-col gap-8">
        
        {/* HEADER */}
        <header className="flex flex-col md:flex-row justify-between items-center md:items-end gap-6 md:gap-0 liquid-glass p-6 rounded-[24px]">
          <div className="text-center md:text-left">
            <h1 className="font-grotesk text-[32px] md:text-[32px] text-neon tracking-wider">COC.BOT // DASHBOARD</h1>
            <div className="flex justify-center md:justify-start gap-6 mt-4 font-bold tracking-widest text-sm">
              <button 
                onClick={() => setView('dashboard')} 
                className={`transition-colors ${view === 'dashboard' ? 'text-neon border-b-2 border-neon pb-1' : 'opacity-50 hover:opacity-100'}`}
              >
                CONTROLS & LOGS
              </button>
              <button 
                onClick={() => setView('analyze')} 
                className={`transition-colors ${view === 'analyze' ? 'text-blue-400 border-b-2 border-blue-400 pb-1' : 'opacity-50 hover:opacity-100'}`}
              >
                VILLAGE ANALYZER
              </button>
            </div>
          </div>
          <div className="text-center md:text-right flex flex-col items-center md:items-end gap-2">
             <div className="flex flex-wrap items-center justify-center md:justify-end gap-4">
                <button onClick={() => setTheme(t => t === 'dark' ? 'light' : 'dark')} className="p-2 liquid-glass rounded-full hover:scale-110 transition-transform">
                  {theme === 'dark' ? <Sun className="w-5 h-5" /> : <Moon className="w-5 h-5" />}
                </button>
                <div className={`w-3 h-3 rounded-full ${state.dotcls === 'on' ? 'bg-neon' : state.dotcls === 'sleep' ? 'bg-yellow-400' : 'bg-red-500'}`} />
                <span className="text-lg font-bold">{state.status}</span>
                <div className="w-px h-6 bg-white/10" />
                <div className={`w-3 h-3 rounded-full ${state.adbcls === 'on' ? 'bg-neon' : 'bg-red-500'}`} />
                <span className={`text-base font-bold ${state.adbcls === 'on' ? '' : 'text-red-400'}`}>
                  ADB {state.adbcls === 'on' ? '✓' : '✗'}
                </span>
             </div>
             {state.adbcls !== 'on' && (
               <div className="text-xs text-red-400/80 bg-red-500/10 px-4 py-1.5 rounded-full flex items-center gap-2">
                 <AlertCircle className="w-3 h-3 flex-shrink-0" />
                 {state.adbmsg?.includes('timeout') ? 'BlueStacks mati? Nyalain dulu.' :
                  state.adbmsg?.includes('ADB tidak ada') ? 'ADB path salah di config.py.' :
                  state.adbmsg || 'ADB disconnect — cek BlueStacks + port.'}
               </div>
             )}
          </div>
        </header>

        {view === 'dashboard' && (
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
                    ].map(({k, l}) => (
                      <div key={k} className="flex flex-col gap-2">
                        <label className="text-sm opacity-70">{l}</label>
                        <input 
                          type="text" 
                          className="bg-[var(--panel-bg)] border border-black/10 dark:border-white/10 rounded-xl px-4 py-3 focus:outline-none focus:border-neon focus:ring-1 focus:ring-neon transition-all text-inherit"
                          value={(settings as any)[k] || ''}
                          onChange={e => setSettings(s => ({...s, [k]: e.target.value}))}
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
        )}

        {view === 'analyze' && (
          <div className="animate-in fade-in duration-500">
            {!activeAccount ? (
              <div className="max-w-5xl mx-auto flex flex-col gap-8">
                {/* Upload Form */}
                <section className="liquid-glass p-12 rounded-[32px] text-center flex flex-col items-center justify-center gap-6">
                  <Swords className="text-blue-400 w-16 h-16 mb-4" />
                  <h2 className="font-grotesk text-[48px] leading-none text-blue-400">Village Analyzer</h2>
                  <p className="opacity-70 normal-case text-lg max-w-lg">Paste JSON village export dari akun COC lu buat dianalisis.</p>
                  <textarea 
                    className="w-full max-w-3xl bg-[var(--panel-bg)] border border-black/10 dark:border-white/10 rounded-xl p-4 h-[120px] focus:outline-none focus:border-blue-400 focus:ring-1 focus:ring-blue-400 transition-all normal-case font-mono text-sm text-inherit text-center"
                    placeholder="Paste JSON here..."
                    value={uploadJsonStr}
                    onChange={e => setUploadJsonStr(e.target.value)}
                  />
                  <div className="flex gap-4 w-full max-w-3xl">
                    <button 
                      id="analyzeBtn"
                      onClick={() => doAnalyze(uploadJsonStr)}
                      disabled={analyzeLoading || !uploadJsonStr}
                      className="flex-1 bg-blue-500 text-white font-bold px-8 py-4 rounded-xl hover:opacity-80 transition-opacity disabled:opacity-50 text-lg"
                    >
                      {analyzeLoading ? 'ANALYZING...' : 'ANALYZE JSON'}
                    </button>
                    <label className="flex-1 bg-[var(--panel-bg)] text-center px-8 py-4 rounded-xl cursor-pointer hover:bg-black/20 dark:hover:bg-white/10 transition-colors text-lg flex items-center justify-center">
                      LOAD FILE
                      <input type="file" accept=".json" className="hidden" onChange={handleFile} />
                    </label>
                  </div>
                  {analyzeError && <p className="text-red-500 text-sm mt-2 flex items-center gap-2"><AlertCircle className="w-4 h-4" /> {analyzeError}</p>}
                </section>

                {/* Saved Accounts List */}
                {accounts.length > 0 && (
                  <section className="liquid-glass p-8 rounded-[32px]">
                    <h2 className="font-grotesk text-[32px] mb-6">Saved Accounts</h2>
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                      {accounts.map(acc => (
                        <div 
                          key={acc.id} 
                          onClick={() => setActiveAccountId(acc.id)}
                          className="bg-[var(--panel-bg)] border border-transparent hover:border-blue-500/50 p-6 rounded-2xl cursor-pointer transition-all flex flex-col gap-4 group relative"
                        >
                          <button 
                            onClick={(e) => deleteAccount(acc.id, e)}
                            className="absolute top-4 right-4 text-red-500 opacity-0 group-hover:opacity-100 hover:scale-110 transition-all bg-red-500/10 p-2 rounded-lg"
                          >
                            <Square className="w-4 h-4" />
                          </button>
                          <button
                            onClick={(e) => { e.stopPropagation(); reanalyzeAccount(acc); }}
                            disabled={analyzeLoading}
                            title="Load ulang (analisis ulang JSON tersimpan)"
                            className="absolute top-4 right-14 text-blue-400 opacity-0 group-hover:opacity-100 hover:scale-110 transition-all bg-blue-500/10 p-2 rounded-lg disabled:opacity-30"
                          >
                            <RefreshCw className={`w-4 h-4 ${analyzeLoading ? 'animate-spin' : ''}`} />
                          </button>
                          <div className="flex items-center gap-4">
                            <div className="w-16 h-16">
                              <img src={getImageUrl('Town Hall', 'other', acc.th_level)} alt="TH" className="w-full h-full object-contain filter drop-shadow-md" />
                            </div>
                            <div>
                              <h3 className="font-bold text-lg">{acc.name}</h3>
                              <p className="text-xs opacity-50">{new Date(acc.date).toLocaleDateString()}</p>
                            </div>
                          </div>
                          <div className="grid grid-cols-3 gap-2 mt-2 pt-4 border-t border-white/5 text-center">
                            <div><div className="font-bold">{acc.result?.summary?.heroes_gap || 0}</div><div className="text-[9px] opacity-50">HERO GAP</div></div>
                            <div><div className="font-bold">{acc.result?.summary?.equip_gap || 0}</div><div className="text-[9px] opacity-50">EQ GAP</div></div>
                            <div><div className="font-bold text-green-400">{acc.result?.summary?.upgrading_count || 0}</div><div className="text-[9px] opacity-50">UPGRADING</div></div>
                          </div>
                          {statsAccounts[acc.name] && (
                            <div className="grid grid-cols-3 gap-2 pt-3 border-t border-neon/20 text-center">
                              <div><div className="font-bold text-yellow-400 text-sm">{fmtNum(statsAccounts[acc.name].gold)}</div><div className="text-[9px] opacity-50">GOLD</div></div>
                              <div><div className="font-bold text-purple-400 text-sm">{fmtNum(statsAccounts[acc.name].elixir)}</div><div className="text-[9px] opacity-50">ELIXIR</div></div>
                              <div><div className="font-bold text-neon text-sm">{fmtDur(statsAccounts[acc.name].seconds)}</div><div className="text-[9px] opacity-50">BOT TIME</div></div>
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  </section>
                )}
              </div>
            ) : (
              <section className="liquid-glass p-8 rounded-[32px] flex flex-col gap-8">
                {/* Header Summary */}
                <div className="flex flex-col xl:flex-row items-center justify-between gap-6">
                  <div className="flex items-center gap-6 bg-[var(--panel-bg)] p-4 rounded-2xl pr-8 w-full xl:w-auto">
                    <div className="w-20 h-20 flex-shrink-0">
                      <img src={getImageUrl('Town Hall', 'other', analyzeResult.th_level)} alt="TH" className="w-full h-full object-contain filter drop-shadow-lg" />
                    </div>
                    <div>
                      <h3 className="font-grotesk text-[32px] text-blue-400 uppercase mb-1">Town Hall {analyzeResult.th_level}</h3>
                      <div className="flex gap-6">
                        <div><div className="text-xl font-bold">{analyzeResult.summary?.heroes_gap}</div><div className="text-[10px] opacity-60 uppercase">Hero Gap</div></div>
                        <div><div className="text-xl font-bold">{analyzeResult.summary?.equip_gap}</div><div className="text-[10px] opacity-60 uppercase">Equip Gap</div></div>
                        <div><div className="text-xl font-bold text-green-500">{analyzeResult.summary?.upgrading_count}</div><div className="text-[10px] opacity-60 uppercase">Upgrading</div></div>
                      </div>
                    </div>
                  </div>
                  
                  <div className="flex flex-wrap items-center justify-center xl:justify-end gap-3 w-full xl:w-auto">
                    <button
                      onClick={() => activeAccount && reanalyzeAccount(activeAccount)}
                      disabled={analyzeLoading}
                      title="Analisis ulang JSON tersimpan dengan data terbaru"
                      className="bg-[var(--panel-bg)] hover:bg-blue-500/20 text-blue-400 px-6 py-3 rounded-xl transition-colors font-bold flex items-center gap-2 disabled:opacity-40"
                    >
                      <RefreshCw className={`w-4 h-4 ${analyzeLoading ? 'animate-spin' : ''}`} />
                      {analyzeLoading ? 'Loading...' : 'Load Ulang'}
                    </button>
                    <button
                      onClick={() => { activeAccount && doDeepResearch(activeAccount); setActiveTab('DeepResearch'); }}
                      disabled={researchLoading}
                      title="Generate Deep Research report (Odysseus pattern)"
                      className="bg-gradient-to-r from-blue-500 to-blue-600 text-white px-6 py-3 rounded-xl hover:opacity-80 transition-opacity font-bold flex-shrink-0 disabled:opacity-40 flex items-center gap-2 shadow-[0_0_15px_rgba(59,130,246,0.2)]"
                    >
                      <BookOpen className="w-4 h-4" />
                      {researchLoading ? 'Researching...' : '🔬 Deep Research'}
                    </button>
                    <button
                      onClick={() => setShowUpdateJson(v => !v)}
                      disabled={analyzeLoading}
                      title="Ganti JSON village dengan export terbaru"
                      className="bg-blue-500 text-white px-6 py-3 rounded-xl hover:opacity-80 transition-opacity font-bold flex-shrink-0 disabled:opacity-40"
                    >
                      Update JSON
                    </button>
                    <button 
                      onClick={() => setActiveAccountId(null)} 
                      className="bg-[var(--panel-bg)] hover:bg-blue-500/20 text-blue-400 px-6 py-3 rounded-xl transition-colors font-bold flex-shrink-0"
                  >
                    ← Back to Accounts
                  </button>
                  </div>
                </div>

                {showUpdateJson && (
                  <div className="flex flex-col gap-3 p-5 bg-[var(--panel-bg)] rounded-2xl border border-blue-500/20">
                    <p className="text-sm opacity-70 normal-case">Paste JSON village terbaru untuk akun <b>{activeAccount?.name}</b>. Hasil lama akan ditimpa.</p>
                    <textarea
                      className="w-full bg-black/20 border border-white/10 rounded-xl p-4 h-[120px] focus:outline-none focus:border-blue-400 normal-case font-mono text-sm text-inherit"
                      placeholder="Paste JSON baru di sini..."
                      value={updateJsonStr}
                      onChange={e => setUpdateJsonStr(e.target.value)}
                    />
                    <div className="flex gap-3">
                      <button
                        onClick={() => activeAccount && reanalyzeAccount(activeAccount, updateJsonStr)}
                        disabled={analyzeLoading || !updateJsonStr}
                        className="bg-blue-500 text-white font-bold px-6 py-3 rounded-xl hover:opacity-80 transition-opacity disabled:opacity-50"
                      >
                        {analyzeLoading ? 'ANALYZING...' : 'ANALYZE JSON BARU'}
                      </button>
                      <button
                        onClick={() => { setShowUpdateJson(false); setUpdateJsonStr(''); }}
                        className="bg-[var(--panel-bg)] px-6 py-3 rounded-xl hover:bg-white/10 transition-colors font-bold"
                      >
                        Batal
                      </button>
                    </div>
                    {analyzeError && <p className="text-red-500 text-sm flex items-center gap-2"><AlertCircle className="w-4 h-4" /> {analyzeError}</p>}
                  </div>
                )}

                {/* Remaining Upgrades Summary Panel */}
                {villageTotals && (
                  <div className="p-6 bg-[#1a1a2e] border border-white/10 rounded-2xl flex flex-col lg:flex-row lg:flex-wrap items-center lg:justify-between gap-6 shadow-xl relative overflow-hidden text-center lg:text-left">
                    <div className="absolute top-0 right-0 w-64 h-64 bg-blue-500/10 rounded-full blur-3xl pointer-events-none" />
                    <div className="z-10">
                      <h3 className="text-xl font-bold text-white mb-1 font-['Supercell_Magic'] tracking-wider">Remaining Upgrades</h3>
                      <p className="text-sm text-gray-400">Total resources & time required to max out TH {analyzeResult.th_level}.</p>
                    </div>
                    <div className="flex flex-wrap gap-4 z-10">
                      <div className="flex items-center gap-2 bg-black/30 px-4 py-2 rounded-lg border border-white/5 shadow-inner">
                        <img src="/assets/resources/gold.webp" className="w-6 h-6 object-contain" alt="Gold" onError={e => e.currentTarget.style.display='none'} />
                        <span className="text-white font-mono font-bold text-lg">{fmtNum(villageTotals['Gold'])}</span>
                      </div>
                      <div className="flex items-center gap-2 bg-black/30 px-4 py-2 rounded-lg border border-white/5 shadow-inner">
                        <img src="/assets/resources/elixir.webp" className="w-6 h-6 object-contain" alt="Elixir" onError={e => e.currentTarget.style.display='none'} />
                        <span className="text-white font-mono font-bold text-lg">{fmtNum(villageTotals['Elixir'])}</span>
                      </div>
                      <div className="flex items-center gap-2 bg-black/30 px-4 py-2 rounded-lg border border-white/5 shadow-inner">
                        <img src="/assets/resources/dark_elixir.webp" className="w-6 h-6 object-contain" alt="Dark Elixir" onError={e => e.currentTarget.style.display='none'} />
                        <span className="text-white font-mono font-bold text-lg">{fmtNum(villageTotals['Dark Elixir'])}</span>
                      </div>
                      <div className="flex flex-col justify-center bg-black/30 px-4 py-1.5 rounded-lg border border-white/5 shadow-inner" title="Total Time with 1 Builder">
                        <div className="flex items-center gap-2">
                          <svg className="w-5 h-5 text-blue-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
                          <span className="text-white font-mono font-bold text-lg">{fmtDur(villageTotals.time)}</span>
                        </div>
                        <span className="text-[10px] text-gray-400 text-center mt-0.5 uppercase tracking-wider font-bold">1 Builder Time</span>
                      </div>
                      
                      {/* Builder Count Selector */}
                      <div className="flex flex-col justify-center bg-black/30 px-4 py-2 rounded-lg border border-blue-500/20 shadow-[0_0_15px_rgba(59,130,246,0.1)]">
                        <div className="flex items-center justify-between gap-4 mb-1">
                          <span className="text-[10px] text-gray-400 uppercase tracking-wider font-bold">Active Builders</span>
                          <div className="flex items-center gap-0.5 bg-black/50 p-0.5 rounded-md border border-white/10">
                            {[1, 2, 3, 4, 5, 6].map(num => (
                              <button 
                                key={num}
                                onClick={() => setBuilderCount(num)}
                                className={`w-6 h-5 rounded flex items-center justify-center text-[10px] font-bold transition-all ${builderCount === num ? 'bg-blue-500 text-white shadow-[0_0_8px_rgba(59,130,246,0.5)]' : 'text-gray-500 hover:text-white hover:bg-white/10'}`}
                              >
                                {num}
                              </button>
                            ))}
                          </div>
                        </div>
                        <div className="flex justify-between items-center mt-1 pt-1 border-t border-white/5">
                          <span className="text-[10px] text-blue-400 font-bold uppercase tracking-wider">Real Time:</span>
                          <div className="flex items-center gap-1.5 text-white font-mono font-bold text-sm">
                            <svg className="w-4 h-4 text-blue-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
                            {fmtDur(Math.floor(villageTotals.time / builderCount))}
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>
                )}

                {/* Tabs Navigation (Clash Ninja Style) */}
                <div className="flex gap-2 overflow-x-auto pb-2 scrollbar-hide border-b border-black/10 dark:border-white/10">
                  {tabs.map(tab => (
                    <button
                      key={tab.id}
                      onClick={() => setActiveTab(tab.id)}
                      className={`px-6 py-3 font-bold text-sm whitespace-nowrap transition-colors ${
                        activeTab === tab.id 
                          ? 'bg-blue-500 text-white rounded-t-lg' 
                          : 'opacity-50 hover:opacity-100 hover:bg-black/5 dark:hover:bg-white/5 rounded-t-lg'
                      }`}
                    >
                      {tab.title}
                    </button>
                  ))}
                </div>

                {/* Tab Content */}
                <div className="min-h-[400px]">
                  {activeTab === 'Priority' ? (
                    <div className="flex flex-col gap-8">
                      {PRIORITY_TIERS.map(tier => {
                        const tierItems = analyzeResult.recs.filter((r: any) => {
                           if (tier.items.length === 0) return r.cat === 'wall' || r.cat === 'trap';
                           return tier.items.includes(r.name);
                        });
                        
                        const unmaxedItems = tierItems.filter((r: any) => r.cur < r.max);
                        if (unmaxedItems.length === 0) return null;

                        // Deduplicate by name so we don't show 7 cannons
                        const uniqueUnmaxed = unmaxedItems.filter((v: any, i: number, a: any) => a.findIndex((t: any) => t.name === v.name) === i);

                        return (
                          <div key={tier.tier} className="flex flex-col gap-4">
                             <div className="bg-blue-500/10 border border-blue-500/20 p-4 rounded-xl">
                               <h3 className="text-xl font-bold text-blue-400">{tier.title}</h3>
                               <p className="text-sm text-gray-400 mt-1 normal-case">{tier.desc}</p>
                             </div>
                             <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-4">
                                {uniqueUnmaxed.map((r: any, idx: number) => (
                                   <div key={idx} className="bg-[#1a1a2e]/60 backdrop-blur-sm border border-white/5 shadow-lg rounded-xl p-4 flex flex-col items-center justify-center text-center hover:border-blue-500/50 transition-all">
                                      <div className="relative mb-3">
                                        <div className="absolute inset-0 bg-blue-500/20 blur-md rounded-full"></div>
                                        <img src={getImageUrl(r.name, r.cat, r.max)} className="w-14 h-14 object-contain relative z-10 drop-shadow-lg" onError={e=>e.currentTarget.style.display='none'} />
                                      </div>
                                      <span className="text-xs font-bold text-white leading-tight">{r.name}</span>
                                      <span className="text-[10px] text-yellow-500 mt-1 font-bold">Needs Upgrade</span>
                                   </div>
                                ))}
                             </div>
                          </div>
                        )
                      })}
                    </div>
                  ) : activeTab === 'Strategies' ? (
                    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                      {analyzeResult.strategies.map((s: any, i: number) => (
                        <div key={i} className="bg-[var(--panel-bg)] p-6 rounded-xl border border-black/5 dark:border-white/5 flex flex-col gap-3">
                          <div className="flex justify-between items-start gap-4">
                            <span className="font-bold text-lg leading-tight text-blue-400">{s.name}</span>
                            <span className={`text-[10px] px-3 py-1.5 rounded-full uppercase whitespace-nowrap font-bold tracking-wider ${s.ready ? 'bg-green-500/20 text-green-600 dark:text-green-400' : 'bg-yellow-500/20 text-yellow-600 dark:text-yellow-400'}`}>{s.status}</span>
                          </div>
                          <p className="text-sm opacity-70 leading-relaxed normal-case">{s.desc}</p>
                        </div>
                      ))}
                    </div>
                  ) : activeTab === 'DeepResearch' ? (
                    <DeepResearchView
                      researchData={researchData}
                      researchLoading={researchLoading}
                      researchError={researchError}
                      onResearch={() => activeAccount && doDeepResearch(activeAccount)}
                    />
                  ) : activeTab === 'LiveResearch' ? (
                    <LiveResearchView thLevel={analyzeResult?.th_level} accountId={activeAccount?.id} accountName={activeAccount?.name} thImg={analyzeResult?.th_level ? getImageUrl('Town Hall', 'other', analyzeResult.th_level) : undefined} analysis={analyzeResult} />
                  ) : activeTab === 'Rekomendasi' ? (
                    <RekomendasiView accountId={activeAccount?.id} accountName={activeAccount?.name} thLevel={analyzeResult?.th_level} thImg={analyzeResult?.th_level ? getImageUrl('Town Hall', 'other', analyzeResult.th_level) : undefined} />
                  ) : (
                    <div className="flex flex-col gap-12">
                      {/* Detailed Table (Clash Ninja Style) */}
                      <div className="flex flex-col gap-4">
                        <h3 className="font-grotesk text-[24px] text-neon uppercase border-b border-white/10 pb-2 mb-2">Detailed Upgrades</h3>
                        <div className="flex flex-col gap-6">
                          {(() => {
                             const currentData = tabs.find(t => t.id === activeTab)?.data || [];
                             if (currentData.length === 0) return null;
                             
                             const grouped = currentData.reduce((acc: any, r: any) => {
                               if (!acc[r.name]) acc[r.name] = [];
                               acc[r.name].push(r);
                               return acc;
                             }, {});

                             const catMap: any = { 
                               'Heroes': 'hero', 'Equipment': 'equipment', 'Pets': 'pet', 
                               'Defenses': 'defense', 'ArmyBldg': 'army_bldg', 'Resources': 'resource', 
                               'Troops': 'troop', 'DarkTroops': 'dark_troop', 'Sieges': 'siege', 
                               'Spells': 'spell', 'Traps': 'trap', 'Walls': 'wall' 
                             };

                             return Object.entries(grouped).map(([name, items]: any) => {
                               const expandedItems: any[] = [];
                               items.forEach((r: any) => {
                                 if (r.levels) {
                                   const sortedLevels = Object.entries(r.levels).sort((a: any, b: any) => Number(b[0]) - Number(a[0]));
                                   sortedLevels.forEach(([lvl, count]: any) => {
                                     for (let i = 0; i < count; i++) {
                                       expandedItems.push({ ...r, cur: Number(lvl) });
                                     }
                                   });
                                 } else {
                                   expandedItems.push(r);
                                 }
                               });

                               let groupUpgrades = 0;
                               let groupTime = 0;
                               let groupCost: any = {};
                               
                               expandedItems.forEach((r: any) => {
                                 const singleItemRec = { ...r, levels: null };
                                 const u = getUpgradePath(singleItemRec);
                                 if (u) {
                                   groupUpgrades += u.path.length;
                                   groupTime += u.totalTime;
                                   for (const res in u.totalCost) {
                                     groupCost[res] = (groupCost[res] || 0) + u.totalCost[res];
                                   }
                                 }
                               });
                               
                               const sortedRes = Object.entries(groupCost).sort((a: any, b: any) => b[1] - a[1]);
                               const topRes = sortedRes.length > 0 ? sortedRes[0] : null;

                               return (
                               <div key={name} className="bg-[#1a1a2e]/60 backdrop-blur-md border border-white/10 rounded-2xl overflow-hidden shadow-2xl relative">
                                 {/* Header Section */}
                                 <div className="relative p-6 flex flex-col md:flex-row items-center gap-6 bg-gradient-to-br from-black/40 to-transparent border-b border-white/5">
                                   <div className="relative">
                                     <div className="absolute inset-0 bg-blue-500/20 blur-xl rounded-full"></div>
                                     <img src={getImageUrl(name, catMap[activeTab], expandedItems[0].max)} className="w-24 h-24 object-contain relative z-10 drop-shadow-2xl" onError={e=>e.currentTarget.style.display='none'} />
                                   </div>
                                   
                                   <div className="flex-1 text-center md:text-left">
                                     <h3 className="text-2xl font-black text-transparent bg-clip-text bg-gradient-to-r from-blue-400 to-blue-500 uppercase tracking-widest">{name}</h3>
                                     <div className="flex flex-wrap items-center justify-center md:justify-start gap-3 mt-3">
                                       <div className="flex items-center gap-2 bg-black/40 px-4 py-1.5 rounded-full border border-white/10 text-sm">
                                         <span className="text-gray-400">Total Upgrades:</span>
                                         <span className="text-white font-bold">{groupUpgrades}</span>
                                       </div>
                                       {topRes && (
                                         <div className="flex items-center gap-2 bg-black/40 px-4 py-1.5 rounded-full border border-yellow-500/20 text-sm">
                                           <img src={`/assets/resources/${topRes[0].toLowerCase().replace(' ', '_')}.webp`} className="w-4 h-4" onError={e=>e.currentTarget.style.display='none'}/>
                                           <span className="text-yellow-400 font-bold">{fmtNum(topRes[1])}</span>
                                         </div>
                                       )}
                                       {groupTime > 0 && (
                                         <div className="flex items-center gap-2 bg-black/40 px-4 py-1.5 rounded-full border border-blue-500/20 text-sm">
                                           <svg className="w-4 h-4 text-blue-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
                                           <span className="text-blue-300 font-bold">{fmtDur(groupTime)}</span>
                                         </div>
                                       )}
                                     </div>
                                   </div>
                                 </div>

                                 {/* Instances List */}
                                 <div className="p-6 flex flex-col gap-4 bg-black/10">
                                   {(() => {
                                      const groupedInstances = expandedItems.reduce((acc: any, r: any, idx: number) => {
                                        if (!acc[r.cur]) acc[r.cur] = { ...r, ids: [] };
                                        acc[r.cur].ids.push(idx + 1);
                                        return acc;
                                      }, {});
                                      const instances = Object.values(groupedInstances).sort((a: any, b: any) => a.cur - b.cur);

                                      return instances.map((r: any, idx: number) => {
                                        const singleItemRec = { ...r, levels: null };
                                        const u = getUpgradePath(singleItemRec);
                                        const isMax = r.cur >= r.max;
                                        
                                        return (
                                          <div key={idx} className="bg-white/5 rounded-xl p-4 border border-white/5 hover:border-white/10 transition-all flex flex-col xl:flex-row gap-6 items-start xl:items-center">
                                            
                                            {/* Instance Info Badge */}
                                            <div className="flex items-center gap-4 min-w-[200px]">
                                              {r.ids.length > 1 && (
                                                <div className="px-3 py-1.5 rounded-lg bg-white/10 flex items-center justify-center font-bold text-white text-sm border border-white/5">
                                                  {r.ids.length}x
                                                </div>
                                              )}
                                              <div>
                                                <div className="text-[10px] text-gray-500 uppercase tracking-wider mb-0.5">Current Level</div>
                                                <div className="flex items-baseline gap-1">
                                                  <span className="text-2xl font-black text-white">{r.cur}</span>
                                                  <span className="text-sm font-bold text-gray-500">/ {r.max}</span>
                                                </div>
                                              </div>
                                            </div>

                                         {/* Upgrades */}
                                         <div className="flex-1 w-full">
                                           {isMax ? (
                                             <div className="flex items-center gap-3 text-green-400 bg-green-500/10 px-4 py-3 rounded-lg border border-green-500/20">
                                               <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" /></svg>
                                               <span className="font-bold text-sm">Maxed out for this Town Hall level</span>
                                             </div>
                                           ) : (
                                             <div className="flex flex-wrap gap-2">
                                               {u?.path.map((p: any, i: number) => (
                                                 <div key={i} className="flex flex-col bg-black/40 border border-white/5 rounded-lg px-3 py-2 flex-grow sm:flex-grow-0 hover:bg-white/10 transition-colors shadow-inner">
                                                   <div className="text-[10px] uppercase font-bold text-blue-400 mb-1">Level {p.to}</div>
                                                   <div className="flex items-center gap-3">
                                                     <div className="flex items-center gap-1.5">
                                                       <img src={`/assets/resources/${p.res.toLowerCase().replace(' ', '_')}.webp`} className="w-3.5 h-3.5" onError={e=>e.currentTarget.style.display='none'}/>
                                                       <span className="text-sm font-bold text-[#e1c16e]">{fmtNum(p.cost)}</span>
                                                     </div>
                                                     <div className="flex items-center gap-1">
                                                       <svg className="w-3.5 h-3.5 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
                                                       <span className="text-xs font-bold text-gray-300">{fmtDur(p.time)}</span>
                                                     </div>
                                                   </div>
                                                 </div>
                                               ))}
                                             </div>
                                           )}
                                         </div>
                                       </div>
                                     )
                                   })
                                 })()}
                                 </div>
                               </div>
                             );
                             })
                          })()}
                        </div>
                      </div>
                    </div>
                  )}
                </div>

                {/* Upgrade Details Modal */}
                {selectedUpgrade && (
                  <div className="fixed inset-0 z-[100] flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm" onClick={() => setSelectedUpgrade(null)}>
                    <div className="bg-[#1a1a2e] border border-white/10 rounded-2xl shadow-2xl max-w-lg w-full max-h-[80vh] overflow-y-auto flex flex-col relative" onClick={e => e.stopPropagation()}>
                      <div className="p-4 border-b border-white/10 flex justify-between items-center sticky top-0 bg-[#1a1a2e] z-10">
                        <h3 className="text-xl font-bold text-white font-['Supercell_Magic'] uppercase tracking-wider">{selectedUpgrade.name}</h3>
                        <button onClick={() => setSelectedUpgrade(null)} className="text-gray-400 hover:text-white">&times;</button>
                      </div>
                      <div className="p-4 flex-1">
                        {(() => {
                          const u = getUpgradePath(selectedUpgrade);
                          if (!u || u.path.length === 0) return <div className="text-gray-400 text-center py-8">No remaining upgrades or missing data.</div>;
                          return (
                            <div className="space-y-2">
                              {u.path.map((step: any, idx: number) => (
                                <div key={idx} className="flex items-center justify-between bg-black/30 p-3 rounded-lg border border-white/5">
                                  <div className="text-white font-bold">Lvl {step.to}</div>
                                  <div className="flex gap-4">
                                    <div className="flex items-center gap-1 text-sm font-mono text-gray-300">
                                      <img src={`/assets/resources/${step.res.toLowerCase().replace(' ', '_')}.webp`} className="w-4 h-4 object-contain" onError={e=>e.currentTarget.style.display='none'}/>
                                      {fmtNum(step.cost)}
                                    </div>
                                    <div className="flex items-center gap-1 text-sm font-mono text-blue-300">
                                      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
                                      {fmtDur(step.time)}
                                    </div>
                                  </div>
                                </div>
                              ))}
                              
                              <div className="mt-4 pt-4 border-t border-white/10 space-y-2">
                                <div className="text-gray-400 text-sm font-bold uppercase tracking-wider mb-2">Total for this item</div>
                                {Object.entries(u.totalCost).map(([res, amount]: any) => amount > 0 && (
                                  <div key={res} className="flex justify-between items-center text-sm font-mono">
                                    <span className="text-gray-300 flex items-center gap-2">
                                      <img src={`/assets/resources/${res.toLowerCase().replace(' ', '_')}.webp`} className="w-5 h-5 object-contain" onError={e=>e.currentTarget.style.display='none'}/>
                                      {res}
                                    </span>
                                    <span className="text-white font-bold">{fmtNum(amount)}</span>
                                  </div>
                                ))}
                                <div className="flex justify-between items-center text-sm font-mono pt-1">
                                  <span className="text-blue-300 flex items-center gap-2">
                                    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
                                    Total Time (1 Builder)
                                  </span>
                                  <span className="text-white font-bold">{fmtDur(u.totalTime)}</span>
                                </div>
                              </div>
                            </div>
                          );
                        })()}
                      </div>
                    </div>
                  </div>
                )}
              </section>
            )}
          </div>
        )}

      </div>
    </div>
  );
};

export default App;
