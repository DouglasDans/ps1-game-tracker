import { fetchGames, fetchStats, fetchActivity } from '../data/api.js';
import { fmtTime, cardGradient, platformLogoImg } from '../utils.js';

const TABS = [
  { key: 'overview', label: 'Visão geral', icon: 'dashboard' },
  { key: 'activity', label: 'Atividade', icon: 'timeline' },
  { key: 'library', label: 'Biblioteca', icon: 'grid_view' },
];

const SCROLL_STEP = 240;

export function mount(container, navigate, params = {}) {
  let tabIndex = Math.max(0, TABS.findIndex(t => t.key === params.tab));
  let focus = 'rail';
  let onKeyHandler = null;
  let cancelled = false;

  container.innerHTML = '<div style="padding:40px;color:var(--text-muted);text-align:center">Carregando...</div>';
  const backdrop = document.getElementById('screen-backdrop');
  if (backdrop) backdrop.innerHTML = '<div class="stats-backdrop"></div>';

  Promise.all([fetchGames(), fetchStats(), fetchActivity()])
    .then(([games, stats, activity]) => {
      if (cancelled) return;

      const content = {
        overview: buildOverview(stats, games, activity),
        activity: buildActivity(activity),
        library: buildLibraryTab(stats, games),
      };

      const rail = TABS.map((t, i) =>
        `<div class="rail-item${i === tabIndex ? ' active' : ''}" data-tab="${t.key}"><span class="msr">${t.icon}</span>${t.label}</div>`
      ).join('');

      container.innerHTML = `<div class="screen-stats">
        <aside class="side-rail">${rail}</aside>
        <div class="stats-content" id="stats-content">${content[TABS[tabIndex].key]}</div>
      </div>`;
      if (TABS[tabIndex].key === 'overview') fitTopGamesList(games);

      function refreshRail() {
        container.querySelectorAll('.rail-item').forEach((el, j) => {
          el.classList.toggle('active', j === tabIndex);
          el.classList.toggle('focused', focus === 'rail' && j === tabIndex);
        });
      }

      function setTab(i) {
        tabIndex = i;
        refreshRail();
        const el = document.getElementById('stats-content');
        el.innerHTML = content[TABS[tabIndex].key];
        el.scrollTo({ top: 0 });
        if (TABS[tabIndex].key === 'overview') fitTopGamesList(games);
      }

      container.querySelectorAll('.rail-item').forEach((el, i) => {
        el.addEventListener('click', () => setTab(i));
      });

      function onKey(e) {
        if (e.key === 'Escape' || e.key === 'Backspace') { navigate('home'); return; }
        const scroller = document.getElementById('stats-content');

        if (focus === 'rail') {
          if (e.key === 'ArrowDown') { e.preventDefault(); if (tabIndex < TABS.length - 1) setTab(tabIndex + 1); }
          if (e.key === 'ArrowUp')   { e.preventDefault(); if (tabIndex > 0) setTab(tabIndex - 1); }
          if (e.key === 'ArrowRight') { focus = 'content'; refreshRail(); }
          return;
        }

        // focus === 'content' — d-pad scrolls the tab body
        if (e.key === 'ArrowLeft') { focus = 'rail'; refreshRail(); return; }
        if (!scroller) return;
        if (e.key === 'ArrowDown') { e.preventDefault(); scroller.scrollBy({ top: SCROLL_STEP, behavior: 'smooth' }); }
        if (e.key === 'ArrowUp')   { e.preventDefault(); scroller.scrollBy({ top: -SCROLL_STEP, behavior: 'smooth' }); }
      }
      onKeyHandler = onKey;
      document.addEventListener('keydown', onKey);
      refreshRail();
    })
    .catch(err => {
      if (cancelled) return;
      container.innerHTML = `<div style="padding:40px;color:var(--text-muted);text-align:center">Erro ao carregar estatísticas.<br><small>${err.message}</small></div>`;
    });

  return () => {
    cancelled = true;
    if (onKeyHandler) document.removeEventListener('keydown', onKeyHandler);
  };
}

// keyFn returns an array of tokens (or null): a game whose field holds a
// joined IGDB string ("Racing, Simulator") credits every token, not the
// composite label. Bar width is normalized to the largest entry.
function aggregateBy(games, keyFn, fallbackLabel) {
  const totals = new Map();
  for (const g of games) {
    const tokens = keyFn(g) ?? [fallbackLabel];
    for (const t of tokens) totals.set(t, (totals.get(t) ?? 0) + (g.total_seconds ?? 0));
  }
  const entries = [...totals.entries()]
    .map(([label, total_seconds]) => ({ label, total_seconds }))
    .sort((a, b) => b.total_seconds - a.total_seconds);
  const max = entries[0]?.total_seconds || 1;
  return entries.map(e => ({ ...e, pct: Math.round((e.total_seconds / max) * 100) }));
}

function splitField(value) {
  if (!value) return null;
  const tokens = value.split(',').map(s => s.trim()).filter(Boolean);
  return tokens.length ? tokens : null;
}

function decadeOf(year) {
  if (!year) return null;
  return `${Math.floor(year / 10) * 10}s`;
}

const DAY_PERIODS = [
  { label: 'Madrugada', icon: '🌙', from: 0, to: 5 },
  { label: 'Manhã', icon: '🌅', from: 6, to: 11 },
  { label: 'Tarde', icon: '☀️', from: 12, to: 17 },
  { label: 'Noite', icon: '🌆', from: 18, to: 23 },
];

function panel(title, body, sub) {
  return `<div class="pg-panel">
    ${sub
      ? `<div class="pg-panel-head"><span class="pg-panel-title">${title}</span><span class="pg-panel-sub">${sub}</span></div>`
      : `<div class="pg-panel-title">${title}</div>`}
    ${body}
  </div>`;
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

function topGamesList(games, limit) {
  const topGames = [...games].sort((a, b) => b.total_seconds - a.total_seconds).slice(0, limit);
  const maxTop = topGames[0]?.total_seconds || 1;
  return topGames.map((g, i) => {
    const cover = g.cover_url ? `<img src="${g.cover_url}" alt="" class="cover-img">` : '';
    const pct = Math.max(4, Math.round((g.total_seconds / maxTop) * 100));
    return `<div class="top-game-row">
      <span class="top-game-rank">${i + 1}</span>
      <div class="top-game-cover" style="background:${cardGradient(g.display_name)}">${cover}</div>
      <div class="top-game-info">
        <div class="top-game-name">${g.display_name}</div>
        <div class="top-game-bar"><div class="top-game-bar-fill" style="width:${pct}%"></div></div>
      </div>
      <div class="top-game-time">${fmtTime(g.total_seconds)}</div>
    </div>`;
  }).join('');
}

function summaryCards(s) {
  return `<div class="stats-summary-cards">
    <div class="stats-card">
      <div class="stats-card-label"><span class="msr">schedule</span>Tempo total</div>
      <div class="stats-card-value">${fmtTime(s.total_seconds)}</div>
    </div>
    <div class="stats-card">
      <div class="stats-card-label"><span class="msr">videogame_asset</span>Jogos</div>
      <div class="stats-card-value">${s.total_games}</div>
    </div>
    <div class="stats-card">
      <div class="stats-card-label"><span class="msr">replay</span>Sessões</div>
      <div class="stats-card-value">${s.total_sessions ?? '—'}</div>
    </div>
    <div class="stats-card">
      <div class="stats-card-label"><span class="msr">calendar_month</span>Dias jogados</div>
      <div class="stats-card-value">${s.total_days_played ?? '—'}</div>
    </div>
  </div>`;
}

function platformBars(s) {
  const maxPlatform = Math.max(...s.by_platform.map(p => p.total_seconds), 1);
  return s.by_platform.map(p => `
    <div class="platform-bar-row">
      <div class="platform-bar-logo">${platformLogoImg(p.platform)}</div>
      <div class="platform-bar-track">
        <div class="platform-bar-fill" style="width:${Math.round((p.total_seconds / maxPlatform) * 100)}%"></div>
      </div>
      <div class="platform-bar-value">${fmtTime(p.total_seconds)}</div>
    </div>`).join('');
}

function genreBars(games, limit) {
  return aggregateBy(games, g => splitField(g.genre), 'Sem gênero')
    .slice(0, limit)
    .map(g => barRow(g.label, g.total_seconds, g.pct))
    .join('');
}

// The daemon's /stats/activity doesn't always ship `by_day` yet (older
// deploys) — show an explicit empty state instead of a blank grid.
function heatmapPanel(activity) {
  const byDay = activity?.by_day ?? [];
  if (!byDay.length) {
    return panel('Atividade', `<div class="heatmap-empty">Sem dados de atividade diária.</div>`, 'ÚLTIMAS 13 SEMANAS');
  }
  const maxDay = Math.max(...byDay.map(d => d.total_seconds), 1);
  const cells = byDay.map(d => {
    const opacity = d.total_seconds ? (0.12 + (d.total_seconds / maxDay) * 0.65).toFixed(2) : 0.05;
    return `<div class="heatmap-cell" style="background:rgba(255,255,255,${opacity})" title="${d.date}"></div>`;
  }).join('');
  return panel('Atividade', `<div class="heatmap-grid">${cells}</div>`, 'ÚLTIMAS 13 SEMANAS');
}

// Matches the mock: a label/value line with a thin progress bar underneath —
// not the icon card-tiles an earlier pass invented.
function periodRows(activity) {
  const byHour = activity?.by_hour ?? [];
  const periodTotals = DAY_PERIODS.map(p => ({
    ...p,
    total: byHour
      .filter(h => h.hour >= p.from && h.hour <= p.to)
      .reduce((a, h) => a + h.total_seconds, 0),
  }));
  const maxPeriod = Math.max(...periodTotals.map(p => p.total), 1);
  return periodTotals.map(p => `
    <div class="period-row">
      <div class="period-row-head"><span>${p.label}</span><span>${p.total ? fmtTime(p.total) : '—'}</span></div>
      <div class="period-row-track">
        <div class="period-row-fill" style="width:${Math.max(2, Math.round((p.total / maxPeriod) * 100))}%"></div>
      </div>
    </div>`).join('');
}

function weekdayCols(activity) {
  const weekdays = activity?.by_weekday ?? [];
  const maxWeekday = Math.max(...weekdays.map(d => d.total_seconds), 1);
  return weekdays.map(d => `
    <div class="wd-col${d.total_seconds === maxWeekday ? ' peak' : ''}">
      <div class="wd-value">${d.total_seconds ? fmtTime(d.total_seconds) : ''}</div>
      <div class="wd-bar-wrap">
        <div class="wd-bar" style="height:${Math.max(1, Math.round((d.total_seconds / maxWeekday) * 100))}%"></div>
      </div>
      <div class="wd-label">${d.day}</div>
    </div>`).join('');
}

// Upper bound once fitTopGamesList() fills the panel — plenty for any
// realistic 1080p panel height.
const TOP_GAMES_MAX = 20;

// Matches the mock's 5c dashboard: everything on one screen in a 4-col grid —
// summary strip, top games + platform/genre side by side, then activity
// heatmap + period-of-day. Atividade/Biblioteca tabs stay as deeper drill-downs.
function buildOverview(s, games, activity) {
  return `<div class="stats-overview-grid">
    <div class="span-4">${summaryCards(s)}</div>
    <div class="span-2" id="top-games-cell">${panel('Mais jogados', `<div class="top-games-list top-games-wide" id="top-games-list">${topGamesList(games, 1)}</div>`)}</div>
    <div class="span-2 stats-overview-side">
      ${panel('Por plataforma', `<div class="platform-bars">${platformBars(s)}</div>`)}
      ${panel('Por gênero', `<div class="platform-bars">${genreBars(games, 6)}</div>`)}
    </div>
    <div class="span-3">${heatmapPanel(activity)}</div>
    <div>${panel('Período do dia', `<div class="period-rows">${periodRows(activity)}</div>`)}</div>
  </div>`;
}

// Grid stretches #top-games-cell's panel to match its taller sibling column
// (Por plataforma + Por gênero stacked). buildOverview only renders a single
// row so that stretch is driven by the sibling, not by the list itself —
// rendering the full list up front would make "Mais jogados" the tallest
// item and inflate the row height around its own content instead. Once
// mounted, measure the real gap against that single row and fill it.
function fitTopGamesList(games) {
  const cell = document.getElementById('top-games-cell');
  const list = document.getElementById('top-games-list');
  if (!cell || !list || !list.children.length) return;

  const panelEl = cell.firstElementChild;
  const panelRect = panelEl.getBoundingClientRect();
  const listRect = list.getBoundingClientRect();
  const paddingBottom = parseFloat(getComputedStyle(panelEl).paddingBottom) || 0;
  const available = panelRect.bottom - paddingBottom - listRect.top;

  const rowHeight = list.children[0].getBoundingClientRect().height;
  const gap = parseFloat(getComputedStyle(list).rowGap) || 0;
  const rowStep = rowHeight + gap;
  if (rowStep <= 0) return;

  const maxRows = Math.max(1, Math.floor(available / rowStep));
  const count = Math.min(maxRows, games.length, TOP_GAMES_MAX);
  list.innerHTML = topGamesList(games, count);
}

function buildActivity(activity) {
  return `
    ${heatmapPanel(activity)}
    ${panel('Dia da semana', `<div class="weekday-chart">${weekdayCols(activity)}</div>`)}
    ${panel('Período do dia', `<div class="period-rows">${periodRows(activity)}</div>`)}`;
}

function buildLibraryTab(s, games) {
  const decadeBars = aggregateBy(games, g => { const d = decadeOf(g.release_year); return d ? [d] : null; }, 'Desconhecida')
    .map(d => barRow(d.label, d.total_seconds, d.pct))
    .join('');

  const developerBars = aggregateBy(games, g => splitField(g.developer), 'Desconhecida')
    .slice(0, 6)
    .map(d => barRow(d.label, d.total_seconds, d.pct))
    .join('');

  const gameModeBars = aggregateBy(games, g => splitField(g.game_modes), 'Desconhecido')
    .map(m => barRow(m.label, m.total_seconds, m.pct))
    .join('');

  return `
    <div class="stats-columns">
      <div class="stats-col">
        ${panel('Por plataforma', `<div class="platform-bars">${platformBars(s)}</div>`)}
        ${panel('Por gênero', `<div class="platform-bars">${genreBars(games, 6)}</div>`)}
      </div>
      <div class="stats-col">
        ${panel('Por desenvolvedora', `<div class="platform-bars">${developerBars}</div>`)}
        ${panel('Por década', `<div class="platform-bars">${decadeBars}</div>`)}
        ${panel('Por modo de jogo', `<div class="platform-bars">${gameModeBars}</div>`)}
      </div>
    </div>`;
}
