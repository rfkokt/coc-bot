export type Account = {
  id: string;
  name: string;
  tag?: string;
  th_level: number;
  json: string;
  result: any;
  date: number;
};

export type AppState = {
  running: boolean;
  status: string;
  adbcls: string;
  adbmsg: string;
  dotcls: string;
};

export const fmtDur = (secs: number) => {
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

export const fmtNum = (n: number) => (n || 0).toLocaleString();

export const getImageUrl = (name: string, cat?: string, level?: number) => {
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
