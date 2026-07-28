const PLATFORM_LOGO = {
  PS1: '/assets/ps1.svg',
  PS2: '/assets/ps2.svg',
  PSP: '/assets/psp.svg',
  Dreamcast: '/assets/dc.svg',
  SNES: '/assets/snes.svg',
  'Game Boy': '/assets/gb.svg',
  GBC: '/assets/gb.svg',
  GBA: '/assets/gba.png',
  'Mega Drive': '/assets/md.svg',
  'Sega CD': '/assets/scd.svg',
  'Mega-CD': '/assets/scd.svg',
  MegaCD: '/assets/scd.svg',
  N64: '/assets/n64.png',
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

export function localDateKey(iso) {
  if (!iso) return null;
  const s = iso.includes('Z') ? iso : iso + 'Z';
  const d = new Date(s);
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${y}-${m}-${day}`;
}

export function localHour(iso) {
  if (!iso) return null;
  const s = iso.includes('Z') ? iso : iso + 'Z';
  return new Date(s).getHours();
}

// Monday=0 .. Sunday=6, matching the daemon's Python weekday() convention.
export function localWeekdayMon0(iso) {
  if (!iso) return null;
  const s = iso.includes('Z') ? iso : iso + 'Z';
  return (new Date(s).getDay() + 6) % 7;
}

export function fmtSource(src) {
  return SOURCE_LABEL[src] || src || '—';
}

export function hueGradient(hue) {
  return `linear-gradient(160deg, hsl(${hue},60%,42%), hsl(${hue},40%,16%))`;
}

const GLOW_S = 60, GLOW_L = 42;

// The mock's g.glowC formula (two radial washes tinted by the game's hue) —
// shared by Home and Detail backdrops so they read as the same visual language.
export function glowCGradient(hue) {
  const triplet = `${hue} ${GLOW_S}% ${GLOW_L}%`;
  return `radial-gradient(70% 55% at 62% 0%, hsl(${triplet} / .34), transparent 68%), ` +
    `radial-gradient(50% 40% at 12% 8%, hsl(${hue} 45% 30% / .35), transparent 70%)`;
}

// The mock's g.artB formula — the blurred glow blob used on Home's carousel row.
export function artBGradient(hue) {
  const triplet = `${hue} ${GLOW_S}% ${GLOW_L}%`;
  return `radial-gradient(50% 100% at 20% 0%, hsl(${triplet} / .8), transparent 70%)`;
}

export function hueOfName(name) {
  let h = 0;
  for (let i = 0; i < name.length; i++) h = (h * 31 + name.charCodeAt(i)) >>> 0;
  return h % 360;
}

export function cardGradient(name) {
  return hueGradient(hueOfName(name));
}

// Hue (0-360) of an "r, g, b" string produced by extractDominantColor.
export function hueOf(c) {
  const [r, g, b] = c.split(',').map(v => Number(v) / 255);
  const max = Math.max(r, g, b), min = Math.min(r, g, b), d = max - min;
  if (!d) return 0;
  let h;
  if (max === r) h = ((g - b) / d) % 6;
  else if (max === g) h = (b - r) / d + 2;
  else h = (r - g) / d + 4;
  return Math.round((h * 60 + 360) % 360);
}

const _colorCache = new Map();

// Extracts a representative vibrant color from a cover image.
// Requires CORS on the image host (images.igdb.com sends ACAO: *).
// Resolves to "r, g, b" (for use in rgba()) or null on any failure.
export function extractDominantColor(url) {
  if (!url) return Promise.resolve(null);
  if (_colorCache.has(url)) return Promise.resolve(_colorCache.get(url));
  return new Promise(resolve => {
    const img = new Image();
    img.crossOrigin = 'anonymous';
    img.onload = () => {
      try {
        const size = 24;
        const canvas = document.createElement('canvas');
        canvas.width = size;
        canvas.height = size;
        const ctx = canvas.getContext('2d');
        ctx.drawImage(img, 0, 0, size, size);
        const { data } = ctx.getImageData(0, 0, size, size);
        let r = 0, g = 0, b = 0, n = 0;
        let ra = 0, ga = 0, ba = 0, na = 0;
        for (let i = 0; i < data.length; i += 4) {
          const R = data[i], G = data[i + 1], B = data[i + 2];
          const max = Math.max(R, G, B), min = Math.min(R, G, B);
          const sat = max - min, lum = (max + min) / 2;
          ra += R; ga += G; ba += B; na++;
          if (sat > 40 && lum > 40 && lum < 215) { r += R; g += G; b += B; n++; }
        }
        const [pr, pg, pb] = n > size ? [r / n, g / n, b / n] : [ra / na, ga / na, ba / na];
        const color = `${Math.round(pr)}, ${Math.round(pg)}, ${Math.round(pb)}`;
        _colorCache.set(url, color);
        resolve(color);
      } catch {
        resolve(null);
      }
    };
    img.onerror = () => resolve(null);
    img.src = url;
  });
}

export function platformLogoImg(platform, cls = '') {
  const src = getPlatformLogo(platform);
  if (!src) return `<span class="platform-text ${cls}">${platform || ''}</span>`;
  return `<img src="${src}" alt="${platform}" class="platform-logo ${cls}">`;
}
