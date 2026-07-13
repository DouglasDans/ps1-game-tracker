import { fetchGames, fetchActiveSession } from '../data/api.js';
import { fmtTime, fmtDateShort, fmtSource, cardGradient, hueGradient, hueOf, platformLogoImg, extractDominantColor } from '../utils.js';

const CARD_W         = 130;
const CARD_GAP       = 14;
const POLL_ACTIVE_MS = 10000;

let _savedIndex = 0;

export function mount(container, navigate, params = {}) {
  let selectedIndex = params.selectedIndex ?? _savedIndex;
  let onKeyHandler = null;
  let timerInterval = null;
  let pollInterval = null;
  let cancelled = false;

  container.innerHTML = '<div style="padding:40px;color:var(--text-muted);text-align:center">Carregando...</div>';

  Promise.all([fetchGames(), fetchActiveSession()])
    .then(([games, active]) => {
      if (cancelled) return;

      const sorted = [...games].sort((a, b) => new Date(b.last_played) - new Date(a.last_played));
      if (active) {
        const activeIdx = sorted.findIndex(g => g.id === active.game_id);
        if (activeIdx > 0) sorted.unshift(sorted.splice(activeIdx, 1)[0]);
      }
      const items = [...sorted.slice(0, 10), { id: 'library', display_name: 'Library', _lib: true }];
      container.innerHTML = buildHTML(items, selectedIndex, active);
      updateHero(items[selectedIndex], active, games);
      scrollRow(selectedIndex);

      function onKey(e) {
        switch (e.key) {
          case 'ArrowLeft':
            if (selectedIndex > 0) { selectedIndex--; refresh(items, selectedIndex, active, games); }
            break;
          case 'ArrowRight':
            if (selectedIndex < items.length - 1) { selectedIndex++; refresh(items, selectedIndex, active, games); }
            break;
          case 'Square':
            e.preventDefault();
            navigate('library');
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

      onKeyHandler = onKey;
      document.addEventListener('keydown', onKey);

      timerInterval = setInterval(() => {
        if (active && items[selectedIndex].id === active.game_id) updateHero(items[selectedIndex], active, games);
      }, 1000);

      pollInterval = setInterval(() => {
        fetchActiveSession()
          .then(a => {
            if (cancelled) return;
            const changed = a?.id !== active?.id || a?.game_id !== active?.game_id;
            if (!changed) return;
            active = a;
            document.querySelectorAll('.game-card[data-id]').forEach(el => {
              el.classList.toggle('has-active', !!active && Number(el.dataset.id) === active.game_id);
            });
            updateHero(items[selectedIndex], active, games);
          })
          .catch(() => {});
      }, POLL_ACTIVE_MS);
    })
    .catch(err => {
      if (cancelled) return;
      container.innerHTML = `<div style="padding:40px;color:var(--text-muted);text-align:center">Erro ao carregar dados.<br><small>${err.message}</small></div>`;
    });

  return () => {
    cancelled = true;
    if (onKeyHandler) document.removeEventListener('keydown', onKeyHandler);
    if (timerInterval) clearInterval(timerInterval);
    if (pollInterval) clearInterval(pollInterval);
  };
}

function refresh(items, selectedIndex, active, games) {
  document.querySelectorAll('.game-card').forEach((el, i) => {
    el.classList.toggle('selected', i === selectedIndex);
  });
  updateHero(items[selectedIndex], active, games);
  scrollRow(selectedIndex);
}

function buildHTML(items, selectedIndex, active) {
  const cards = items.map((item, i) => {
    const sel = i === selectedIndex ? ' selected' : '';
    if (item._lib) {
      return `<div class="game-card card-library${sel}" data-idx="${i}">
        <div class="card-library-inner">LIBRARY</div>
      </div>`;
    }
    const isActive = active && item.id === active.game_id;
    const cover = item.cover_url
      ? `<img src="${item.cover_url}" alt="" class="cover-img">`
      : `<div class="cover-gradient" style="background:${cardGradient(item.display_name)}">
           <span class="card-name-fb">${item.display_name.toUpperCase()}</span>
         </div>`;
    return `<div class="game-card${sel}${isActive ? ' has-active' : ''}" data-idx="${i}" data-id="${item.id}">
      ${cover}
      <div class="card-active-dot"></div>
    </div>`;
  }).join('');

  return `<div class="screen-home">
    <div class="section-home" id="section-home">
      <div class="home-backdrop" id="home-backdrop"></div>
      <div class="hero">
        <div class="hero-meta">
          <span class="badge badge-active" id="hero-badge" hidden></span>
          <span class="hero-platform-info" id="hero-platform-info"></span>
        </div>
        <h1 class="hero-title" id="hero-title"></h1>
        <div class="hero-stats">
          <div class="hero-stat">
            <div class="stat-label">ÚLTIMA SESSÃO</div>
            <div class="stat-value" id="hero-last-session"></div>
          </div>
          <div class="hero-stat">
            <div class="stat-label">EMULADOR</div>
            <div class="stat-value" id="hero-emulator"></div>
          </div>
          <div class="hero-stat">
            <div class="stat-label">SESSÕES</div>
            <div class="stat-value" id="hero-sessions"></div>
          </div>
        </div>
      </div>
      <div class="game-row-wrapper">
        <div class="game-row" id="game-row">${cards}</div>
      </div>
    </div>
  </div>`;
}

let _backdropToken = 0;

function setBackdropGradient(el, baseGradient) {
  el.style.background =
    `linear-gradient(180deg, rgba(13, 13, 26, 0.55) 0%, rgba(13, 13, 26, 0.85) 55%, var(--bg) 85%), ${baseGradient}`;
  el.classList.add('visible');
}

function updateBackdrop(item) {
  const el = document.getElementById('home-backdrop');
  if (!el) return;
  const token = ++_backdropToken;

  if (item._lib) {
    el.classList.remove('visible');
    return;
  }
  if (!item.cover_url) {
    setBackdropGradient(el, cardGradient(item.display_name));
    return;
  }
  extractDominantColor(item.cover_url).then(c => {
    if (!c || token !== _backdropToken || !el.isConnected) return;
    setBackdropGradient(el, hueGradient(hueOf(c)));
  });
}

function updateHero(item, active, games) {
  updateBackdrop(item);
  const badge        = document.getElementById('hero-badge');
  const platformInfo = document.getElementById('hero-platform-info');
  const title        = document.getElementById('hero-title');
  const lastSession  = document.getElementById('hero-last-session');
  const emulator     = document.getElementById('hero-emulator');
  const sessions     = document.getElementById('hero-sessions');
  if (!badge) return;

  if (item._lib) {
    badge.hidden = true;
    platformInfo.innerHTML = 'TODOS OS JOGOS';
    title.textContent = 'Biblioteca';
    lastSession.textContent = '—';
    emulator.textContent = '—';
    sessions.textContent = `${games.length} jogos`;
    return;
  }

  const isActive = active && item.id === active.game_id;
  if (isActive) {
    const startedAt = active.started_at.endsWith('Z') || active.started_at.includes('+') ? active.started_at : active.started_at + 'Z';
    const elapsed = Math.floor((Date.now() - new Date(startedAt).getTime()) / 1000);
    badge.hidden = false;
    badge.textContent = `SESSÃO ATIVA · ${fmtTime(elapsed)}`;
  } else {
    badge.hidden = true;
  }

  platformInfo.innerHTML = `${item.platform ? `${platformLogoImg(item.platform, 'hero-platform-logo')} · ` : ''}${fmtTime(item.total_seconds)} TOTAL`;
  title.textContent = item.display_name;
  lastSession.textContent = fmtDateShort(item.last_played);
  emulator.textContent = fmtSource(item.last_source);
  sessions.textContent = item.session_count;
}

function scrollRow(selectedIndex) {
  const row = document.getElementById('game-row');
  if (!row) return;
  const offset = selectedIndex <= 1 ? 0 : (selectedIndex - 1) * (CARD_W + CARD_GAP);
  row.style.transform = `translateX(-${offset}px)`;
}
