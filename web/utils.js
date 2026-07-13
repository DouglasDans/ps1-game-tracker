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

export function hueGradient(hue) {
  return `linear-gradient(145deg, hsl(${hue},65%,38%), hsl(${(hue + 50) % 360},55%,18%))`;
}

export function cardGradient(name) {
  let h = 0;
  for (let i = 0; i < name.length; i++) h = (h * 31 + name.charCodeAt(i)) >>> 0;
  return hueGradient(h % 360);
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
