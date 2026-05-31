import { fetchGames, fetchActiveSession, fetchStats } from '../data/api.js';
import { fmtTime, fmtDate, fmtDateShort, fmtSource, cardGradient, platformLogoImg, PLATFORM_LOGO } from '../utils.js';

const CARD_W   = 130;
const CARD_GAP = 14;

let _savedIndex = 0;

export function mount(container, navigate, params = {}) {
  let selectedIndex = params.selectedIndex ?? _savedIndex;
  let focus = 'row';
  let onKeyHandler = null;
  let timerInterval = null;
  let cancelled = false;

  container.innerHTML = '<div style="padding:40px;color:var(--text-muted);text-align:center">Carregando...</div>';

  Promise.all([fetchGames(), fetchActiveSession(), fetchStats()])
    .then(([games, active, stats]) => {
      if (cancelled) return;

      const sorted = [...games].sort((a, b) => new Date(b.last_played) - new Date(a.last_played));
      const items = [...sorted, { id: 'library', display_name: 'Library', _lib: true }];
      container.innerHTML = buildHTML(items, selectedIndex, active, stats, games);
      updateHero(items[selectedIndex], active, games);
      scrollRow(selectedIndex);

      if (params.scrollToStats) {
        requestAnimationFrame(() =>
          document.getElementById('section-stats')?.scrollIntoView({ behavior: 'smooth' })
        );
        focus = 'stats';
      }

      function onKey(e) {
        if (focus === 'row') {
          switch (e.key) {
            case 'ArrowLeft':
              if (selectedIndex > 0) { selectedIndex--; refresh(items, selectedIndex, active, games); }
              break;
            case 'ArrowRight':
              if (selectedIndex < items.length - 1) { selectedIndex++; refresh(items, selectedIndex, active, games); }
              break;
            case 'ArrowDown':
              e.preventDefault();
              focus = 'stats';
              document.getElementById('section-stats')?.scrollIntoView({ behavior: 'smooth' });
              break;
            case 'Enter':
            case ' ':
              e.preventDefault();
              _savedIndex = selectedIndex;
              if (items[selectedIndex]._lib) { navigate('library'); }
              else { navigate('detail', { gameId: items[selectedIndex].id }); }
              break;
          }
        } else {
          if (e.key === 'ArrowUp') {
            e.preventDefault();
            focus = 'row';
            document.getElementById('section-home')?.scrollIntoView({ behavior: 'smooth' });
          }
        }
      }

      onKeyHandler = onKey;
      document.addEventListener('keydown', onKey);

      if (active) {
        timerInterval = setInterval(() => {
          if (items[selectedIndex].id === active.game_id) updateHero(items[selectedIndex], active, games);
        }, 1000);
      }
    })
    .catch(err => {
      if (cancelled) return;
      container.innerHTML = `<div style="padding:40px;color:var(--text-muted);text-align:center">Erro ao carregar dados.<br><small>${err.message}</small></div>`;
    });

  return () => {
    cancelled = true;
    if (onKeyHandler) document.removeEventListener('keydown', onKeyHandler);
    if (timerInterval) clearInterval(timerInterval);
  };
}

function refresh(items, selectedIndex, active, games) {
  document.querySelectorAll('.game-card').forEach((el, i) => {
    el.classList.toggle('selected', i === selectedIndex);
  });
  updateHero(items[selectedIndex], active, games);
  scrollRow(selectedIndex);
}

function buildHTML(items, selectedIndex, active, stats, games) {
  const cards = items.map((item, i) => {
    const sel = i === selectedIndex ? ' selected' : '';
    if (item._lib) {
      return `<div class="game-card card-library${sel}" data-idx="${i}">
        <div class="card-library-inner">LIBRARY</div>
      </div>`;
    }
    const isActive = active && item.id === active.game_id;
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
    <div class="section-home" id="section-home">
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
    <div class="section-stats" id="section-stats">
      ${buildStatsHTML(stats, games)}
    </div>
  </div>`;
}

function buildStatsHTML(stats, games) {
  const s = stats;
  const topGames = [...games].sort((a, b) => b.total_seconds - a.total_seconds).slice(0, 5);

  const bars = s.by_platform.map(p => `
    <div class="platform-bar-row">
      <div class="platform-bar-logo">${platformLogoImg(p.platform)}</div>
      <div class="platform-bar-track">
        <div class="platform-bar-fill" style="width:${p.pct}%"></div>
      </div>
      <div class="platform-bar-value">${fmtTime(p.total_seconds)}</div>
    </div>`).join('');

  const topList = topGames.map((g, i) => {
    const logo = PLATFORM_LOGO[g.platform];
    return `<div class="top-game-row">
      <span class="top-game-rank">${i + 1}</span>
      <div class="top-game-cover" style="background:${cardGradient(g.display_name)}">
        ${logo ? `<img src="${logo}" alt="${g.platform}" class="top-game-platform-logo">` : ''}
      </div>
      <div class="top-game-info">
        <div class="top-game-name">${g.display_name}</div>
        <div class="top-game-meta">${g.platform} · ${g.session_count} sessões</div>
      </div>
      <div class="top-game-time">${fmtTime(g.total_seconds)}</div>
    </div>`;
  }).join('');

  return `
    <div class="stats-scroll-hint">↑ <span>GAMES</span></div>

    <div class="stats-summary-cards">
      <div class="stats-card">
        <div class="stats-card-label">Tempo total</div>
        <div class="stats-card-value">${fmtTime(s.total_seconds)}</div>
        <div class="stats-card-sub">em todas as plataformas</div>
      </div>
      <div class="stats-card">
        <div class="stats-card-label">Jogos jogados</div>
        <div class="stats-card-value">${s.total_games}</div>
        <div class="stats-card-sub">com pelo menos 1 sessão</div>
      </div>
      <div class="stats-card">
        <div class="stats-card-label">Sessão mais longa</div>
        <div class="stats-card-value">${fmtTime(s.longest_session?.duration_s)}</div>
        <div class="stats-card-sub">${s.longest_session?.display_name ?? '—'} · ${fmtDate(s.longest_session?.started_at)}</div>
      </div>
    </div>

    <div class="stats-columns">
      <div class="stats-col">
        <div class="section-header">Por plataforma</div>
        <div class="platform-bars" style="margin-top:16px">${bars}</div>
      </div>
      <div class="stats-col">
        <div class="section-header">Mais jogados</div>
        <div class="top-games-list" style="margin-top:16px">${topList}</div>
      </div>
    </div>`;
}

function updateHero(item, active, games) {
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
    const elapsed = Math.floor((Date.now() - new Date(active.started_at).getTime()) / 1000);
    badge.hidden = false;
    badge.textContent = `SESSÃO ATIVA · ${fmtTime(elapsed)}`;
  } else {
    badge.hidden = true;
  }

  platformInfo.innerHTML = `${platformLogoImg(item.platform, 'hero-platform-logo')} ${item.platform || ''} · ${fmtTime(item.total_seconds)} TOTAL`;
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
