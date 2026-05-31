const PLATFORM_LOGO = {
  PS1: '/assets/ps1.svg',
  PS2: '/assets/ps2.svg',
  PSP: '/assets/psp.svg',
  Dreamcast: '/assets/dc.png',
};

const SEGA_PLATFORMS = new Set([
  'Mega Drive', 'MegaDrive', 'Genesis', 'Sega Genesis',
  'Saturn', 'Sega Saturn',
  'Mega-CD', 'MegaCD', 'Sega CD',
  '32X', 'Sega 32X',
  'Game Gear', 'Master System', 'Mark III', 'SG-1000',
]);

export function getPlatformLogo(platform) {
  if (!platform) return null;
  if (PLATFORM_LOGO[platform]) return PLATFORM_LOGO[platform];
  if (SEGA_PLATFORMS.has(platform) || platform.toLowerCase().startsWith('sega')) {
    return '/assets/sega.png';
  }
  return null;
}

export const SOURCE_LABEL = {
  duckstation: 'DuckStation',
  ppsspp: 'PPSSPP',
  retroarch: 'RetroArch',
  samba: 'PS2/OPL',
};

export function fmtTime(secs) {
  if (!secs) return '—';
  const h = Math.floor(secs / 3600);
  const m = Math.floor((secs % 3600) / 60);
  if (h > 0) return `${h}h ${m}m`;
  if (m > 0) return `${m}m`;
  return `${secs}s`;
}

export function fmtDate(iso) {
  if (!iso) return '—';
  const s = iso.includes('Z') ? iso : iso + 'Z';
  return new Date(s).toLocaleDateString('pt-BR', { day: '2-digit', month: '2-digit', year: 'numeric' });
}

export function fmtDateShort(iso) {
  if (!iso) return '—';
  const s = iso.includes('Z') ? iso : iso + 'Z';
  return new Date(s).toLocaleDateString('pt-BR', { day: '2-digit', month: '2-digit' });
}

export function fmtSource(src) {
  return SOURCE_LABEL[src] || src || '—';
}

export function cardGradient(name) {
  let h = 0;
  for (let i = 0; i < name.length; i++) h = (h * 31 + name.charCodeAt(i)) >>> 0;
  const hue = h % 360;
  return `linear-gradient(145deg, hsl(${hue},65%,38%), hsl(${(hue + 50) % 360},55%,18%))`;
}

export function platformLogoImg(platform, cls = '') {
  const src = getPlatformLogo(platform);
  if (!src) return `<span class="platform-text ${cls}">${platform || ''}</span>`;
  return `<img src="${src}" alt="${platform}" class="platform-logo ${cls}">`;
}
