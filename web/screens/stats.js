import { fetchGames, fetchStats, fetchActivity, fetchLongestSessions, fetchMonthly, fetchMonthlySeries, fetchDailySeries } from '../data/api.js';
import { lineAxes, lineFocus, linePath, lineScales } from '../charts.js';
import { fmtTime, fmtDateShort, cardGradient, platformLogoImg, extractDominantColor, hueOf, hueOfName } from '../utils.js';

const TABS = [
  { key: 'overview', label: 'Visão geral', icon: 'dashboard' },
  { key: 'activity', label: 'Atividade', icon: 'timeline' },
  { key: 'monthly', label: 'Mensal', icon: 'calendar_month' },
  { key: 'evolution', label: 'Evolução', icon: 'timelapse' },
  { key: 'library', label: 'Biblioteca', icon: 'grid_view' },
];

const SCROLL_STEP = 240;

export function mount(container, navigate, params = {}) {
  let tabIndex = Math.max(0, TABS.findIndex(t => t.key === params.tab));
  let focus = 'rail';
  // Evolução: ↑↓ walks both legends as one list (10 + 10); each chart keeps
  // its own highlighted game, the cursor marks which one has the focus.
  let chartCursor = 0;
  let chartSelection = [0, 0];
  let onKeyHandler = null;
  let cancelled = false;

  container.innerHTML = '<div style="padding:40px;color:var(--text-muted);text-align:center">Carregando...</div>';
  const backdrop = document.getElementById('screen-backdrop');
  if (backdrop) backdrop.innerHTML = '<div class="stats-backdrop"></div>';

  // The daily series is optional: a backend not yet restarted with the
  // endpoint drops the month chart instead of the whole screen.
  Promise.all([fetchGames(), fetchStats(), fetchActivity(), fetchLongestSessions(LONGEST_SESSIONS_MAX), fetchMonthly(), fetchMonthlySeries(), fetchDailySeries().catch(() => null)])
    .then(([games, stats, activity, longestSessions, monthly, series, daily]) => {
      if (cancelled) return;
      const charts = [monthChart(daily), historyChart(series)].filter(Boolean);

      const content = {
        overview: buildOverview(stats, games, activity),
        activity: buildActivity(activity, longestSessions),
        monthly: buildMonthly(monthly),
        evolution: buildEvolution(charts),
        library: buildLibraryTab(stats, games),
      };

      const rail = TABS.map((t, i) =>
        `<div class="rail-item${i === tabIndex ? ' active' : ''}" data-tab="${t.key}"><span class="msr">${t.icon}</span>${t.label}</div>`
      ).join('');

      container.innerHTML = `<div class="screen-stats">
        <aside class="side-rail">${rail}</aside>
        <div class="stats-content" id="stats-content">${content[TABS[tabIndex].key]}</div>
      </div>`;
      onTabRendered();

      // Post-render hook per tab: ranked lists render a single row first,
      // then grow to what fits the panel (fitList); month cards pick up
      // their game's color once the cover is sampled (tintByCover).
      function onTabRendered() {
        const key = TABS[tabIndex].key;
        if (key === 'overview') {
          fitList('top-games-cell', 'top-games-list', n => topGamesList(games, n), Math.min(games.length, TOP_GAMES_MAX));
        } else if (key === 'activity') {
          fitList('longest-sessions-cell', 'longest-sessions-list', n => longestSessionsList(longestSessions.slice(0, n)), longestSessions.length);
        } else if (key === 'monthly') {
          tintByCover(document.getElementById('stats-content'));
        } else if (key === 'evolution') {
          renderCharts();
        }
      }

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
        onTabRendered();
      }

      container.querySelectorAll('.rail-item').forEach((el, i) => {
        el.addEventListener('click', () => setTab(i));
      });

      function renderCharts() {
        charts.forEach((chart, k) => {
          if (chart.games.length) highlightSeries(chart, chartSelection[k], focus === 'content' && k === chartCursor);
        });
      }

      // With focus in the content, ↑↓ moves the highlight instead of
      // scrolling; past either end of a legend it crosses into the other chart.
      function moveSelection(delta) {
        const next = chartSelection[chartCursor] + delta;
        const target = chartCursor + (next < 0 ? -1 : next >= charts[chartCursor].games.length ? 1 : 0);
        if (target === chartCursor) {
          chartSelection[chartCursor] = next;
        } else if (charts[target]?.games.length) {
          chartCursor = target;
          chartSelection[target] = delta > 0 ? 0 : charts[target].games.length - 1;
        }
        renderCharts();
      }

      function onKey(e) {
        if (e.key === 'Escape' || e.key === 'Backspace') { navigate('home'); return; }
        const scroller = document.getElementById('stats-content');

        if (focus === 'rail') {
          if (e.key === 'ArrowDown') { e.preventDefault(); if (tabIndex < TABS.length - 1) setTab(tabIndex + 1); }
          if (e.key === 'ArrowUp')   { e.preventDefault(); if (tabIndex > 0) setTab(tabIndex - 1); }
          if (e.key === 'ArrowRight') { focus = 'content'; refreshRail(); if (TABS[tabIndex].key === 'evolution') renderCharts(); }
          return;
        }

        // focus === 'content' — d-pad scrolls the tab body
        if (e.key === 'ArrowLeft') { focus = 'rail'; refreshRail(); if (TABS[tabIndex].key === 'evolution') renderCharts(); return; }
        if (TABS[tabIndex].key === 'evolution' && (e.key === 'ArrowDown' || e.key === 'ArrowUp')) {
          e.preventDefault();
          moveSelection(e.key === 'ArrowDown' ? 1 : -1);
          return;
        }
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
    return panel('Atividade', `<div class="heatmap-empty">Sem dados de atividade diária.</div>`, 'Últimas 13 semanas');
  }
  const maxDay = Math.max(...byDay.map(d => d.total_seconds), 1);
  const cells = byDay.map(d => {
    const opacity = d.total_seconds ? (0.12 + (d.total_seconds / maxDay) * 0.65).toFixed(2) : 0.05;
    return `<div class="heatmap-cell" style="background:rgba(255,255,255,${opacity})" title="${d.date}"></div>`;
  }).join('');
  return panel('Atividade', `<div class="heatmap-grid">${cells}</div>`, 'Últimas 13 semanas');
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

// Upper bound once fitList() fills the panel — plenty for any
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

// The cell's height is set by its surroundings (a taller sibling column on
// Visão geral, the remaining screen height on Atividade), never by the list
// itself — so the list is rendered with a single row first. Rendering it in
// full up front would inflate the cell around its own content instead. Once
// mounted, measure the real gap against that single row and fill it.
function fitList(cellId, listId, renderRows, total) {
  const cell = document.getElementById(cellId);
  const list = document.getElementById(listId);
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
  list.innerHTML = renderRows(Math.min(maxRows, total));
}

function longestSessionsList(sessions) {
  const max = sessions[0]?.duration_s || 1;
  return sessions.map((s, i) => {
    const cover = s.cover_url ? `<img src="${s.cover_url}" alt="" class="cover-img">` : '';
    const pct = Math.max(4, Math.round((s.duration_s / max) * 100));
    return `<div class="top-game-row">
      <span class="top-game-rank">${i + 1}</span>
      <div class="top-game-cover" style="background:${cardGradient(s.display_name)}">${cover}</div>
      <div class="top-game-info">
        <div class="top-game-head">
          <span class="top-game-name">${s.display_name}</span>
          <span class="top-game-date">${fmtDateShort(s.started_at)}</span>
        </div>
        <div class="top-game-bar"><div class="top-game-bar-fill" style="width:${pct}%"></div></div>
      </div>
      <div class="top-game-time">${fmtTime(s.duration_s)}</div>
    </div>`;
  }).join('');
}

// Upper bound once fitList() fills the panel.
const LONGEST_SESSIONS_MAX = 15;

function longestSessionsPanel(sessions) {
  const body = sessions?.length
    ? `<div class="top-games-list" id="longest-sessions-list">${longestSessionsList(sessions.slice(0, 1))}</div>`
    : `<div class="heatmap-empty">Sem sessões registradas.</div>`;
  return panel('Sessões mais longas', body);
}

// Heatmap full width on top; below it two equal columns filling the rest of
// the screen — longest sessions on the left, weekday + period of day
// stretched to the same height on the right.
function buildActivity(activity, longestSessions) {
  return `
    ${heatmapPanel(activity)}
    <div class="stats-activity-row">
      <div class="stats-activity-cell" id="longest-sessions-cell">${longestSessionsPanel(longestSessions)}</div>
      <div class="stats-activity-cell stats-activity-side">
        ${panel('Dia da semana', `<div class="weekday-chart">${weekdayCols(activity)}</div>`)}
        ${panel('Período do dia', `<div class="period-rows">${periodRows(activity)}</div>`)}
      </div>
    </div>`;
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

const MONTH_NAMES = ['Janeiro', 'Fevereiro', 'Março', 'Abril', 'Maio', 'Junho', 'Julho', 'Agosto', 'Setembro', 'Outubro', 'Novembro', 'Dezembro'];
const MONTH_SHORT = ['Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun', 'Jul', 'Ago', 'Set', 'Out', 'Nov', 'Dez'];

function monthParts(key) {
  const [y, m] = key.split('-').map(Number);
  return { year: y, index: m - 1 };
}

function coverBox(game, cls) {
  const img = game.cover_url ? `<img src="${game.cover_url}" alt="" class="cover-img">` : '';
  return `<div class="${cls}" style="background:${cardGradient(game.display_name)}">${img}</div>`;
}

// data-cover/data-name feed tintByCover(): the card's background and accent
// follow the game of the month, same color extraction as Home and Detail.
function tintAttrs(game) {
  return game ? `data-tint data-name="${game.display_name}" data-cover="${game.cover_url ?? ''}"` : '';
}

function monthDelta(current, previous) {
  if (!previous?.total_seconds) return '';
  const pct = Math.round(((current.total_seconds - previous.total_seconds) / previous.total_seconds) * 100);
  const { index } = monthParts(previous.month);
  const arrow = pct >= 0 ? '▲' : '▼';
  return `<div class="month-delta">${arrow} ${Math.abs(pct)}% vs ${MONTH_NAMES[index].toLowerCase()}</div>`;
}

function monthHero(month, previous) {
  const { year, index } = monthParts(month.month);
  const [top, ...others] = month.top_games;
  const label = `JOGO DO MÊS · ${MONTH_NAMES[index].toUpperCase()} ${year}`;

  const main = top
    ? `${coverBox(top, 'month-hero-cover')}
      <div class="month-hero-main">
        <div class="pg-panel-sub">${label}</div>
        <div class="month-hero-name">${top.display_name}</div>
        <div class="month-hero-time">${fmtTime(top.total_seconds)}</div>
        ${others.length ? `<div class="month-hero-others">${others.map((g, i) =>
          `<span>${i + 2}. ${g.display_name} <b>${fmtTime(g.total_seconds)}</b></span>`).join('')}</div>` : ''}
      </div>`
    : `<div class="month-hero-main">
        <div class="pg-panel-sub">${label}</div>
        <div class="month-hero-name month-empty-text">Nenhum jogo ainda este mês</div>
      </div>`;

  return `<div class="pg-panel month-hero" ${tintAttrs(top)}>
    ${main}
    <div class="month-hero-stats">
      <div class="month-stat month-stat-total">
        <div class="stats-card-label"><span class="msr">schedule</span>Tempo no mês</div>
        <div class="stats-card-value">${fmtTime(month.total_seconds)}</div>
        ${monthDelta(month, previous)}
      </div>
      <div class="month-stat">
        <div class="stats-card-label"><span class="msr">videogame_asset</span>Jogos</div>
        <div class="stats-card-value">${month.games_played}</div>
      </div>
      <div class="month-stat">
        <div class="stats-card-label"><span class="msr">new_releases</span>Novos</div>
        <div class="stats-card-value">${month.new_games}</div>
      </div>
      <div class="month-stat">
        <div class="stats-card-label"><span class="msr">event</span>Dias</div>
        <div class="stats-card-value">${month.days_played}</div>
      </div>
    </div>
  </div>`;
}

function monthCard(month) {
  const { year, index } = monthParts(month.month);
  const top = month.top_games[0];
  const label = `<div class="pg-panel-sub">${MONTH_SHORT[index]} ${year}</div>`;
  if (!top) {
    return `<div class="pg-panel month-card month-card-empty">${label}<div class="month-empty-text">Sem jogos</div></div>`;
  }
  return `<div class="pg-panel month-card" ${tintAttrs(top)}>
    ${label}
    <div class="month-card-body">
      ${coverBox(top, 'month-card-cover')}
      <div class="month-card-info">
        <div class="month-card-name">${top.display_name}</div>
        <div class="month-card-time">${fmtTime(top.total_seconds)}</div>
      </div>
    </div>
    <div class="month-card-total">${fmtTime(month.total_seconds)} no mês · ${month.games_played} jogos</div>
  </div>`;
}

// Current month in the spotlight, then the 12 months before it as a 6×2 grid.
function buildMonthly(months) {
  if (!months?.length) return `<div class="heatmap-empty">Sem dados mensais.</div>`;
  const [current, ...past] = months;
  return `<div class="month-tab">
    ${monthHero(current, past[0])}
    <div class="month-grid">${past.map(monthCard).join('')}</div>
  </div>`;
}

// This month day by day on top, the all-time evolution below.
function buildEvolution(charts) {
  return `<div class="month-tab">${charts.map(chartPanel).join('')}</div>`;
}

function tintByCover(root) {
  root?.querySelectorAll('[data-tint]').forEach(el => {
    // Solid, darkened tone of the cover's hue — the raw cover color can be
    // near-white (GT4) and would wash out the white text on top.
    const apply = hue => {
      el.style.background = `hsl(${hue} 45% 24%)`;
      el.style.borderColor = `hsl(${hue} 45% 32%)`;
      el.style.setProperty('--accent-game', `hsl(${hue} 80% 75%)`);
    };
    apply(hueOfName(el.dataset.name));
    extractDominantColor(el.dataset.cover || null).then(c => { if (c) apply(hueOf(c)); });
  });
}

// ── Gráficos de evolução ──────────────────────────────────────────────────
// Emphasis charts: every game is a gray context line; only the selected one
// is drawn in its cover color. One colored line at a time is what keeps
// same-franchise covers (GT2/3/4) from colliding. Both charts share this
// code; a chart is { key, title, sub, n (x slots), xLabels, games[].values,
// dotAt, labelAt } — values may stop before n (the month's future days).
const EVO_BOX = { w: 1100, h: 300, pad: { top: 30, right: 56, bottom: 40, left: 72 } };
const _seriesHue = new Map();

// Top 10 of all time, hours per month, ranked by all-time total.
function historyChart(series) {
  const months = series?.months ?? [];
  return {
    key: 'history',
    title: 'Evolução geral',
    sub: 'Top 10 do histórico · horas por mês',
    n: months.length,
    xLabels: months.map((m, i) => {
      const { year, index } = monthParts(m);
      const showYear = i === 0 || index === 0;
      return { i, text: `${MONTH_SHORT[index]}${showYear ? ` <tspan class="evo-axis-year">${year}</tspan>` : ''}` };
    }),
    games: (series?.games ?? []).map(g => ({ ...g, values: g.monthly })),
    dotAt: () => true,
    labelAt: (values, i) => values[i] > 0,
  };
}

// Top 10 of the current month, cumulative hours day by day: the lines only
// rise on session days, so leads and overtakes read at a glance.
function monthChart(daily) {
  if (!daily) return null;
  const { index } = monthParts(daily.month);
  const n = daily.days_in_month;
  const cumulative = values => { let sum = 0; return values.map(v => (sum += v)); };
  return {
    key: 'month',
    title: `${MONTH_NAMES[index]} dia a dia`,
    sub: 'Top 10 do mês · horas acumuladas',
    empty: 'Nenhum jogo ainda este mês',
    n,
    xLabels: [1, 5, 10, 15, 20, 25, n].map(d => ({ i: d - 1, text: String(d) })),
    games: daily.games.map(g => ({ ...g, values: cumulative(g.daily) })),
    dotAt: (values, i) => values[i] > (i ? values[i - 1] : 0),
    labelAt: (values, i) => i === values.length - 1,
  };
}

function evoScales(chart) {
  return lineScales(chart.games.flatMap(g => g.values), chart.n, EVO_BOX);
}

function chartPanel(chart) {
  const head = `<div class="pg-panel-head"><span class="pg-panel-title">${chart.title}</span><span class="pg-panel-sub">${chart.sub}</span></div>`;
  if (!chart.games.length) {
    return `<div class="pg-panel evo-panel">${head}<div class="evo-empty month-empty-text">${chart.empty ?? 'Sem dados.'}</div></div>`;
  }
  const sc = evoScales(chart);
  const context = chart.games.map((g, i) =>
    `<path class="evo-line" data-series="${i}" d="${linePath(g.values, sc)}"/>`).join('');

  const legend = chart.games.map((g, i) => `
    <div class="evo-legend-row" data-series="${i}">
      <span class="evo-key"></span>
      ${coverBox(g, 'top-game-cover')}
      <span class="evo-legend-name">${g.display_name}</span>
      <span class="evo-legend-time">${fmtTime(g.total_seconds)}</span>
    </div>`).join('');

  return `<div class="pg-panel evo-panel" data-chart="${chart.key}">
    ${head}
    <div class="evo-body">
      <svg class="evo-chart" viewBox="0 0 ${EVO_BOX.w} ${EVO_BOX.h}" role="img" aria-label="${chart.title}">
        ${lineAxes(sc, chart.xLabels, EVO_BOX)}
        <g class="evo-context">${context}</g>
        <g class="evo-focus"></g>
      </svg>
      <div class="evo-legend">${legend}</div>
    </div>
  </div>`;
}

function highlightSeries(chart, index, focused) {
  const root = document.querySelector(`[data-chart="${chart.key}"]`);
  if (!root) return;
  const game = chart.games[index];
  const sc = evoScales(chart);

  root.querySelectorAll('.evo-line').forEach(el => el.classList.toggle('dim', +el.dataset.series !== index));
  root.querySelectorAll('.evo-legend-row').forEach(el => {
    const on = +el.dataset.series === index;
    el.classList.toggle('active', on);
    el.classList.toggle('focused', on && focused);
  });

  const draw = hue => {
    const color = `hsl(${hue} 80% 65%)`;
    root.querySelector('.evo-focus').innerHTML = lineFocus(game.values, sc, color, chart.dotAt, chart.labelAt);
    root.querySelectorAll('.evo-legend-row').forEach(el => {
      if (+el.dataset.series === index) el.style.setProperty('--series-color', color);
    });
  };

  const key = game.cover_url || game.display_name;
  draw(_seriesHue.get(key) ?? hueOfName(game.display_name));
  if (!_seriesHue.has(key)) {
    extractDominantColor(game.cover_url).then(c => {
      if (!c) return;
      _seriesHue.set(key, hueOf(c));
      if (root.querySelector('.evo-legend-row.active')?.dataset.series === String(index)) draw(hueOf(c));
    });
  }
}
