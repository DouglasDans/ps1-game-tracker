import { GAMES, ACTIVE } from '../data/mock.js';
import { fmtTime, fmtDateShort, fmtSource, cardGradient, platformLogoImg, PLATFORM_LOGO } from '../utils.js';

const CARD_W   = 130;
const CARD_GAP = 14;

let _savedIndex = 0;

export function mount(container, navigate, params = {}) {
  let selectedIndex = params.selectedIndex ?? _savedIndex;
  const items = [...GAMES, { id: 'library', display_name: 'Library', _lib: true }];

  container.innerHTML = buildHTML(items, selectedIndex);
  updateHero(items[selectedIndex]);
  scrollRow(selectedIndex);

  function onKey(e) {
    switch (e.key) {
      case 'ArrowLeft':
        if (selectedIndex > 0) { selectedIndex--; refresh(items, selectedIndex); }
        break;
      case 'ArrowRight':
        if (selectedIndex < items.length - 1) { selectedIndex++; refresh(items, selectedIndex); }
        break;
      case 'Enter':
      case ' ':
        e.preventDefault();
        _savedIndex = selectedIndex;
        if (items[selectedIndex]._lib) { navigate('library'); }
        else { navigate('detail', { gameId: items[selectedIndex].id }); }
        break;
    }
  }

  document.addEventListener('keydown', onKey);

  let timerInterval = null;
  if (ACTIVE) {
    timerInterval = setInterval(() => {
      if (items[selectedIndex].id === ACTIVE.game_id) updateHero(items[selectedIndex]);
    }, 1000);
  }

  return () => {
    document.removeEventListener('keydown', onKey);
    if (timerInterval) clearInterval(timerInterval);
  };
}

function refresh(items, selectedIndex) {
  document.querySelectorAll('.game-card').forEach((el, i) => {
    el.classList.toggle('selected', i === selectedIndex);
  });
  updateHero(items[selectedIndex]);
  scrollRow(selectedIndex);
}

function buildHTML(items, selectedIndex) {
  const cards = items.map((item, i) => {
    const sel = i === selectedIndex ? ' selected' : '';
    if (item._lib) {
      return `<div class="game-card card-library${sel}" data-idx="${i}">
        <div class="card-library-inner">LIBRARY</div>
      </div>`;
    }
    const isActive = ACTIVE && item.id === ACTIVE.game_id;
    const logo = PLATFORM_LOGO[item.platform];
    const cover = item.cover_url
      ? `<img src="${item.cover_url}" alt="" class="cover-img">`
      : `<div class="cover-gradient" style="background:${cardGradient(item.display_name)}">
           <span class="card-name-fb">${item.display_name.toUpperCase()}</span>
         </div>`;
    return `<div class="game-card${sel}${isActive ? ' has-active' : ''}" data-idx="${i}" data-id="${item.id}">
      ${cover}
      ${logo ? `<div class="card-platform-badge"><img src="${logo}" alt="${item.platform}"></div>` : ''}
      <div class="card-active-dot"></div>
    </div>`;
  }).join('');

  return `<div class="screen-home">
    <div class="hero" id="hero"></div>
    <div class="game-row-wrapper">
      <div class="game-row" id="game-row">${cards}</div>
    </div>
  </div>`;
}

function updateHero(item) {
  const hero = document.getElementById('hero');
  if (!hero) return;

  if (item._lib) {
    hero.innerHTML = `
      <div class="hero-meta"><span class="hero-platform-info">TODOS OS JOGOS</span></div>
      <h1 class="hero-title">Biblioteca</h1>
      <div class="hero-stats">
        <div class="hero-stat">
          <div class="stat-label">TOTAL DE JOGOS</div>
          <div class="stat-value">${GAMES.length}</div>
        </div>
      </div>`;
    return;
  }

  const isActive = ACTIVE && item.id === ACTIVE.game_id;
  let elapsed = 0;
  if (isActive) elapsed = Math.floor((Date.now() - new Date(ACTIVE.started_at).getTime()) / 1000);

  hero.innerHTML = `
    <div class="hero-meta">
      ${isActive ? `<span class="badge badge-active" id="active-timer">SESSÃO ATIVA · ${fmtTime(elapsed)}</span>` : ''}
      <span class="hero-platform-info">
        ${platformLogoImg(item.platform, 'hero-platform-logo')}
        ${item.platform || ''} · ${fmtTime(item.total_seconds)} TOTAL
      </span>
    </div>
    <h1 class="hero-title">${item.display_name}</h1>
    <div class="hero-stats">
      <div class="hero-stat">
        <div class="stat-label">ÚLTIMA SESSÃO</div>
        <div class="stat-value">${fmtDateShort(item.last_played)}</div>
      </div>
      <div class="hero-stat">
        <div class="stat-label">EMULADOR</div>
        <div class="stat-value">${fmtSource(item.last_source)}</div>
      </div>
      <div class="hero-stat">
        <div class="stat-label">CONQUISTAS</div>
        <div class="stat-value">— / —</div>
      </div>
      <div class="hero-stat">
        <div class="stat-label">SESSÕES</div>
        <div class="stat-value">${item.session_count}</div>
      </div>
    </div>`;
}

function scrollRow(selectedIndex) {
  const row = document.getElementById('game-row');
  if (!row) return;
  const offset = selectedIndex <= 1 ? 0 : (selectedIndex - 1) * (CARD_W + CARD_GAP);
  row.style.transform = `translateX(-${offset}px)`;
}
