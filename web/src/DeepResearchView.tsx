import React from 'react';
import { BookOpen, RefreshCw, AlertCircle, Clock, Swords, Shield, Zap, TrendingUp, Target, HeartHandshake } from 'lucide-react';

type DeepResearchViewProps = {
  researchData: any;
  researchLoading: boolean;
  researchError: string;
  onResearch: () => void;
};

const SECTION_ICONS: Record<string, React.ReactNode> = {
  '📋': <BookOpen className="w-5 h-5" />,
  '📊': <TrendingUp className="w-5 h-5" />,
  '⚔️': <Swords className="w-5 h-5" />,
  '🛡️': <Shield className="w-5 h-5" />,
  '👑': <Zap className="w-5 h-5" />,
  '💰': <TrendingUp className="w-5 h-5" />,
  '🏴': <Target className="w-5 h-5" />,
  '⏱️': <Clock className="w-5 h-5" />,
  '💡': <HeartHandshake className="w-5 h-5" />,
};

const fmtDur = (secs: number) => {
  if (!secs) return '0s';
  const y = Math.floor(secs / 31536000);
  const d = Math.floor((secs % 31536000) / 86400);
  const h = Math.floor((secs % 86400) / 3600);
  const m = Math.floor((secs % 3600) / 60);
  let s = [];
  if (y > 0) s.push(`${y}y`);
  if (d > 0) s.push(`${d}d`);
  if (h > 0) s.push(`${h}h`);
  if (m > 0) s.push(`${m}m`);
  return s.length > 0 ? s.join(' ') : '<1m';
};

const fmtNum = (n: number) => (n || 0).toLocaleString();

const DeepResearchView = ({ researchData, researchLoading, researchError, onResearch }: DeepResearchViewProps) => {
  if (!researchData && !researchLoading && !researchError) {
    return (
      <div className="flex flex-col items-center justify-center py-24 gap-8 animate-in fade-in">
        <div className="relative">
          <div className="absolute inset-0 bg-blue-500/20 blur-3xl rounded-full" />
          <BookOpen className="w-24 h-24 text-blue-400 relative z-10" />
        </div>
        <div className="text-center max-w-lg">
          <h3 className="font-grotesk text-[28px] text-blue-400 mb-3">Deep Research</h3>
          <p className="text-gray-400 normal-case leading-relaxed">
            Generate a comprehensive research report about optimal upgrade strategies,
            attack meta, equipment builds, and farming tips tailored to your village's
            Town Hall level — adapted from the <span className="text-blue-400 font-bold">Odysseus DeepResearcher</span> pattern.
          </p>
        </div>
        <button
          onClick={onResearch}
          className="bg-gradient-to-r from-blue-500 to-purple-600 text-white font-bold px-10 py-5 rounded-2xl hover:opacity-90 transition-all flex items-center gap-3 text-lg shadow-[0_0_30px_rgba(59,130,246,0.3)]"
        >
          <BookOpen className="w-6 h-6" />
          START DEEP RESEARCH
        </button>
      </div>
    );
  }

  if (researchLoading) {
    return (
      <div className="flex flex-col items-center justify-center py-24 gap-6 animate-in fade-in">
        <div className="relative">
          <div className="absolute inset-0 bg-blue-500/20 blur-3xl rounded-full animate-pulse" />
          <RefreshCw className="w-20 h-20 text-blue-400 animate-spin relative z-10" />
        </div>
        <div className="text-center">
          <h3 className="font-grotesk text-[24px] text-blue-400 mb-2">Researching...</h3>
          <p className="text-gray-500 normal-case">Analyzing {researchData?.th_level ? `TH ${researchData.th_level}` : ''} strategy data</p>
        </div>
        <div className="flex gap-2 mt-4">
          <span className="w-3 h-3 bg-blue-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
          <span className="w-3 h-3 bg-blue-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
          <span className="w-3 h-3 bg-blue-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
        </div>
      </div>
    );
  }

  if (researchError) {
    return (
      <div className="flex flex-col items-center justify-center py-24 gap-6 animate-in fade-in">
        <AlertCircle className="w-16 h-16 text-red-400" />
        <p className="text-red-400 text-lg">{researchError}</p>
        <button onClick={onResearch} className="bg-blue-500 text-white px-8 py-3 rounded-xl hover:opacity-80 transition-opacity flex items-center gap-2">
          <RefreshCw className="w-4 h-4" /> Retry
        </button>
      </div>
    );
  }

  const sections = researchData?.sections || [];
  const stats = researchData?.stats || {};

  return (
    <div className="flex flex-col gap-6 animate-in fade-in">
      {/* Stats Bar */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
        {[
          { label: 'Upgrades Needed', value: stats.upgrade_count, color: 'text-blue-400' },
          { label: 'Hero Gap', value: `${stats.hero_gap} lvl`, color: 'text-purple-400' },
          { label: 'Equip Gap', value: `${stats.equip_gap} lvl`, color: 'text-yellow-400' },
          { label: 'Strategies Ready', value: `${stats.strategies_ready}/${stats.strategies_available}`, color: 'text-green-400' },
          { label: 'Generated', value: stats.report_generated?.split(' ')[0] || '', color: 'text-gray-400' },
        ].map(s => (
          <div key={s.label} className="bg-[var(--panel-bg)] border border-white/5 rounded-xl p-4 text-center">
            <div className={`text-2xl font-black ${s.color}`}>{s.value}</div>
            <div className="text-[9px] text-gray-500 uppercase tracking-widest mt-1">{s.label}</div>
          </div>
        ))}
      </div>

      {/* Research Sections */}
      {sections.map((section: any) => (
        <SectionCard key={section.id} section={section} />
      ))}

      {/* Odysseus Attribution */}
      <div className="text-center py-6 opacity-40 text-xs text-gray-500 normal-case">
        Research engine adapted from{' '}
        <a href="https://github.com/pewdiepie-archdaemon/odysseus" target="_blank" rel="noopener noreferrer" className="text-blue-400 hover:underline">
          Odysseus DeepResearcher
        </a>
        {' '}— IterResearch-style iterative analysis
      </div>
    </div>
  );
};

const SectionCard = ({ section }: { section: any }) => {
  const iconEl = SECTION_ICONS[section.icon] || <BookOpen className="w-5 h-5" />;

  return (
    <div className="bg-[var(--panel-bg)] border border-white/5 rounded-2xl overflow-hidden hover:border-blue-500/20 transition-all">
      {/* Section Header */}
      <div className="flex items-center gap-3 px-6 py-4 bg-gradient-to-r from-blue-500/5 to-transparent border-b border-white/5">
        <div className="p-2 bg-blue-500/10 rounded-lg text-blue-400">
          {iconEl}
        </div>
        <h3 className="font-grotesk text-xl text-white tracking-wider">{section.title}</h3>
      </div>

      {/* Section Content */}
      <div className="p-6">
        {section.type === 'markdown' && (
          <div className="text-sm text-gray-300 leading-relaxed normal-case whitespace-pre-wrap">
            {section.content}
          </div>
        )}

        {section.type === 'priority_table' && section.priorities && (
          <div className="flex flex-col gap-2">
            {section.priorities.map((p: any, i: number) => (
              <div key={i} className="flex items-center gap-4 bg-black/20 rounded-xl px-5 py-4 border border-white/5 hover:border-blue-500/20 transition-all">
                <span className="text-lg font-black text-blue-400 w-16 flex-shrink-0">{p[0]}</span>
                <div className="flex-1 min-w-0">
                  <span className="font-bold text-white text-sm block truncate">{p[1]}</span>
                  <span className="text-xs text-gray-500 normal-case">{p[2]}</span>
                </div>
              </div>
            ))}
          </div>
        )}

        {section.type === 'strategies' && (
          <div className="flex flex-col gap-6">
            {/* Meta Description */}
            <div className="text-sm text-gray-300 leading-relaxed normal-case">{section.content}</div>
            
            {/* Strategy Cards */}
            {section.strategies?.length > 0 && (
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
                {section.strategies.map((s: any, i: number) => (
                  <div key={i} className="bg-black/30 rounded-xl p-4 border border-white/5 flex flex-col gap-2">
                    <div className="flex items-center justify-between">
                      <span className="font-bold text-sm text-blue-400">{s.name}</span>
                      <span className={`text-[9px] px-2 py-1 rounded-full uppercase font-bold ${s.ready ? 'bg-green-500/20 text-green-400' : 'bg-yellow-500/20 text-yellow-400'}`}>{s.ready ? 'Ready' : 'Missing'}</span>
                    </div>
                    <p className="text-xs text-gray-400 normal-case leading-relaxed">{s.desc}</p>
                  </div>
                ))}
              </div>
            )}

            {/* Key Units & Spells */}
            {(section.key_units?.length > 0 || section.key_spells?.length > 0) && (
              <div className="flex flex-wrap gap-6">
                {section.key_units?.length > 0 && (
                  <div>
                    <div className="text-[10px] text-gray-500 uppercase tracking-widest mb-2 font-bold">Key Units</div>
                    <div className="flex flex-wrap gap-2">
                      {section.key_units.map((u: string, i: number) => (
                        <span key={i} className="text-xs bg-blue-500/10 text-blue-300 px-3 py-1.5 rounded-lg border border-blue-500/10">{u}</span>
                      ))}
                    </div>
                  </div>
                )}
                {section.key_spells?.length > 0 && (
                  <div>
                    <div className="text-[10px] text-gray-500 uppercase tracking-widest mb-2 font-bold">Key Spells</div>
                    <div className="flex flex-wrap gap-2">
                      {section.key_spells.map((s: string, i: number) => (
                        <span key={i} className="text-xs bg-purple-500/10 text-purple-300 px-3 py-1.5 rounded-lg border border-purple-500/10">{s}</span>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        )}

        {section.type === 'equipment' && section.heroes && (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {Object.entries(section.heroes).map(([hero, items]: any) => (
              <div key={hero} className="bg-black/30 rounded-xl p-4 border border-white/5">
                <h4 className="font-bold text-sm text-yellow-400 mb-3 uppercase tracking-wider">{hero}</h4>
                <div className="flex flex-col gap-2">
                  {items.map((eq: any, i: number) => (
                    <div key={i} className={`flex items-start gap-2 p-2 rounded-lg ${eq.top ? 'bg-blue-500/10 border border-blue-500/20' : ''}`}>
                      <span className="text-xs mt-0.5">{eq.top ? '⭐' : '•'}</span>
                      <div>
                        <span className="text-xs font-bold text-white">{eq.name}</span>
                        <p className="text-[10px] text-gray-500 normal-case leading-relaxed">{eq.desc}</p>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        )}

        {section.type === 'tips' && section.tips && (
          <div className="flex flex-col gap-3">
            <div className="text-sm text-gray-300 leading-relaxed normal-case mb-2">{section.content}</div>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
              {section.tips.map((tip: string, i: number) => (
                <div key={i} className="flex items-start gap-3 bg-black/20 rounded-xl p-4 border border-white/5">
                  <span className="text-lg flex-shrink-0 mt-0.5">{tip.charAt(0)}</span>
                  <span className="text-xs text-gray-300 normal-case leading-relaxed">{tip}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {section.type === 'resources' && (
          <div className="flex flex-col gap-4">
            <div className="flex flex-wrap gap-4">
              {section.resources?.map((r: any, i: number) => (
                <div key={i} className="flex items-center gap-3 bg-black/30 rounded-xl px-5 py-4 border border-white/5">
                  <img
                    src={`/assets/resources/${r.r.toLowerCase().replace(' ', '_')}.webp`}
                    className="w-8 h-8 object-contain"
                    onError={e => { (e.target as HTMLImageElement).style.display = 'none' }}
                    alt={r.r}
                  />
                  <div>
                    <div className="text-xs text-gray-500">{r.r}</div>
                    <div className="text-lg font-black text-[#e1c16e]">{fmtNum(r.v)}</div>
                  </div>
                </div>
              ))}
              {section.total_time > 0 && (
                <div className="flex items-center gap-3 bg-black/30 rounded-xl px-5 py-4 border border-blue-500/20">
                  <Clock className="w-8 h-8 text-blue-400" />
                  <div>
                    <div className="text-xs text-gray-500">Total Time (1 Builder)</div>
                    <div className="text-lg font-black text-blue-300">{fmtDur(section.total_time)}</div>
                  </div>
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default DeepResearchView;
