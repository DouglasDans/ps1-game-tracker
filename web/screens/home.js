import { fetchGames, fetchActiveSession, fetchStats, fetchActivity } from '../data/api.js';
import { fmtTime, fmtDate, fmtDateShort, fmtSource, cardGradient, platformLogoImg } from '../utils.js';

const CARD_W         = 130;
const CARD_GAP       = 14;
const SCROLL_STEP    = 240;
const POLL_ACTIVE_MS = 10000;

let _savedIndex = 0;

export function mount(container, navigate, params = {}) {
  let selectedIndex = params.selectedIndex ?? _savedIndex;
  let focus = 'row';
  let onKeyHandler = null;
  let timerInterval = null;
  let pollInterval = null;
  let cancelled = false;

  container.innerHTML = '<div style="padding:40px;color:var(--text-muted);text-align:center">Carregando...</div>';

  Promise.all([fetchGames(), fetchActiveSession(), fetchStats(), fetchActivity()])
    .then(([games, active, stats, activity]) => {
      if (cancelled) return;

      const sorted = [...games].sort((a, b) => new Date(b.last_played) - new Date(a.last_played));
      if (active) {
        const activeIdx = sorted.findIndex(g => g.id === active.game_id);
        if (activeIdx > 0) sorted.unshift(sorted.splice(activeIdx, 1)[0]);
      }
      const items = [...sorted.slice(0, 10), { id: 'library', display_name: 'Library', _lib: true }];
      container.innerHTML = buildHTML(items, selectedIndex, active, stats, games, activity);
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
        } else {
          if (e.key === 'ArrowUp') {
            e.preventDefault();
            const scroller = container.querySelector('.screen-home');
            const stats = document.getElementById('section-stats');
            if (scroller && stats && scroller.scrollTop > stats.offsetTop + 10) {
              scroller.scrollBy({ top: -SCROLL_STEP, behavior: 'smooth' });
            } else {
              focus = 'row';
              document.getElementById('section-home')?.scrollIntoView({ behavior: 'smooth' });
            }
          } else if (e.key === 'ArrowDown') {
            e.preventDefault();
            container.querySelector('.screen-home')?.scrollBy({ top: SCROLL_STEP, behavior: 'smooth' });
          }
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

function buildHTML(items, selectedIndex, active, stats, games, activity) {
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
      ${buildStatsHTML(stats, games, activity)}
    </div>
  </div>`;
}

function aggregateBy(games, keyFn, fallbackLabel) {
  const totals = new Map();
  for (const g of games) {
    const key = keyFn(g) ?? fallbackLabel;
    totals.set(key, (totals.get(key) ?? 0) + (g.total_seconds ?? 0));
  }
  const grandTotal = [...totals.values()].reduce((a, b) => a + b, 0);
  return [...totals.entries()]
    .map(([label, total_seconds]) => ({
      label,
      total_seconds,
      pct: grandTotal ? Math.round((total_seconds / grandTotal) * 100) : 0,
    }))
    .sort((a, b) => b.total_seconds - a.total_seconds);
}

function decadeOf(year) {
  if (!year) return null;
  return `${Math.floor(year / 10) * 10}s`;
}

function barRow(label, total_seconds, pct) {
  return `<div class="platform-bar-row">
    <div class="platform-bar-logo stat-label-wide"><span class="platform-text" title="${label}">${label}</span></div>
    <div class="platform-bar-track">
      <div class="platform-bar-fill" style="width:${pct}%"></div>
    </div>
    <div class="platform-bar-value">${fmtTime(total_seconds)}</div>
  </div>`;
}

function buildStatsHTML(stats, games, activity) {
  const s = stats;
  const topGames = [...games].sort((a, b) => b.total_seconds - a.total_seconds).slice(0, 8);

  const bars = s.by_platform.map(p => `
    <div class="platform-bar-row">
      <div class="platform-bar-logo">${platformLogoImg(p.platform)}</div>
      <div class="platform-bar-track">
        <div class="platform-bar-fill" style="width:${p.pct}%"></div>
      </div>
      <div class="platform-bar-value">${fmtTime(p.total_seconds)}</div>
    </div>`).join('');

  const topList = topGames.map((g, i) => {
    const cover = g.cover_url ? `<img src="${g.cover_url}" alt="" class="cover-img">` : '';
    const pct = s.total_seconds ? Math.round((g.total_seconds / s.total_seconds) * 100) : 0;
    return `<div class="top-game-row">
      <span class="top-game-rank">${i + 1}</span>
      <div class="top-game-cover" style="background:${cardGradient(g.display_name)}">${cover}</div>
      <div class="top-game-info">
        <div class="top-game-name">${g.display_name}</div>
        <div class="top-game-meta">${g.platform ?? ''} · ${g.session_count} sessões</div>
      </div>
      <div class="top-game-time">${fmtTime(g.total_seconds)}<div class="top-game-pct">${pct}%</div></div>
    </div>`;
  }).join('');

  const genreBars = aggregateBy(games, g => g.genre, 'Sem gênero')
    .slice(0, 6)
    .map(g => barRow(g.label, g.total_seconds, g.pct))
    .join('');

  const decadeBars = aggregateBy(games, g => decadeOf(g.release_year), 'Desconhecida')
    .map(d => barRow(d.label, d.total_seconds, d.pct))
    .join('');

  const weekdayBars = (activity?.by_weekday ?? []).map(d => {
    const grand = activity.by_weekday.reduce((a, b) => a + b.total_seconds, 0);
    const pct = grand ? Math.round((d.total_seconds / grand) * 100) : 0;
    return barRow(d.day, d.total_seconds, pct);
  }).join('');

  const developerBars = aggregateBy(games, g => g.developer, 'Desconhecida')
    .slice(0, 6)
    .map(d => barRow(d.label, d.total_seconds, d.pct))
    .join('');

  const gameModeBars = aggregateBy(games, g => g.game_modes, 'Desconhecido')
    .map(m => barRow(m.label, m.total_seconds, m.pct))
    .join('');

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
      <div class="stats-card">
        <div class="stats-card-label">Sequência</div>
        <div class="stats-card-value">${activity?.current_streak ?? 0}d</div>
        <div class="stats-card-sub">recorde: ${activity?.longest_streak ?? 0} dias seguidos</div>
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
    </div>

    <div class="stats-columns stats-columns-3">
      <div class="stats-col">
        <div class="section-header">Por gênero</div>
        <div class="platform-bars" style="margin-top:16px">${genreBars}</div>
      </div>
      <div class="stats-col">
        <div class="section-header">Por década</div>
        <div class="platform-bars" style="margin-top:16px">${decadeBars}</div>
      </div>
      <div class="stats-col">
        <div class="section-header">Dia da semana</div>
        <div class="platform-bars" style="margin-top:16px">${weekdayBars}</div>
      </div>
    </div>

    <div class="stats-columns">
      <div class="stats-col">
        <div class="section-header">Por desenvolvedora</div>
        <div class="platform-bars" style="margin-top:16px">${developerBars}</div>
      </div>
      <div class="stats-col">
        <div class="section-header">Por modo de jogo</div>
        <div class="platform-bars" style="margin-top:16px">${gameModeBars}</div>
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
    const startedAt = active.started_at.endsWith('Z') || active.started_at.includes('+') ? active.started_at : active.started_at + 'Z';
    const elapsed = Math.floor((Date.now() - new Date(startedAt).getTime()) / 1000);
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
