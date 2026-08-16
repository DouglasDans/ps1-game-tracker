import { fetchGameDetail } from '../data/api.js';
import { fmtTime, fmtDate, fmtDateShort, fmtSource, cardGradient, getPlatformLogo, extractDominantColor, localDateKey, localHour, localWeekdayMon0, hueOf, hueOfName, glowCGradient } from '../utils.js';

const SCROLL_STEP = 240;
const HEATMAP_DAYS = 91;
const MONTH_LABELS = ['JAN', 'FEV', 'MAR', 'ABR', 'MAI', 'JUN', 'JUL', 'AGO', 'SET', 'OUT', 'NOV', 'DEZ'];
const WEEKDAY_LABELS = ['SEG', 'TER', 'QUA', 'QUI', 'SEX', 'SÁB', 'DOM'];

const TABS = [
  { key: 'overview', label: 'Visão geral' },
  { key: 'stats', label: 'Estatísticas' },
  { key: 'achievements', label: 'Conquistas' },
];

export function mount(container, navigate, params = {}) {
  let tabIndex = 0;
  let focus = 'rail';
  let onKeyHandler = null;
  let cancelled = false;

  container.innerHTML = '<div style="padding:40px;color:var(--text-muted);text-align:center">Carregando...</div>';
  const globalBackdrop = document.getElementById('screen-backdrop');
  if (globalBackdrop) globalBackdrop.innerHTML = '';

  const back = params.from ?? 'home';
  const backParams = params.from === 'library'
    ? { selectedIndex: params.libraryIndex, platformFilter: params.libraryFilter }
    : {};

  fetchGameDetail(params.gameId)
    .then(detail => {
      if (cancelled) return;

      const content = {
        overview: buildOverviewTab(detail),
        stats: buildStatsTab(detail),
        achievements: buildAchievementsTab(),
      };

      container.innerHTML = buildHTML(detail, content[TABS[tabIndex].key], tabIndex);
      applyBackdrop(container, detail);

      function refreshRail() {
        container.querySelectorAll('.detail-rail .rail-item').forEach((el, i) => {
          el.classList.toggle('active', i === tabIndex);
          el.classList.toggle('focused', focus === 'rail' && i === tabIndex);
        });
      }

      function setTab(i) {
        tabIndex = i;
        refreshRail();
        const el = document.getElementById('detail-tab-content');
        if (el) el.innerHTML = content[TABS[tabIndex].key];
        container.querySelector('.detail-main')?.scrollTo({ top: 0 });
      }

      container.querySelectorAll('.detail-rail .rail-item').forEach((el, i) => {
        el.addEventListener('click', () => setTab(i));
      });

      function onKey(e) {
        if (e.key === 'Escape' || e.key === 'Backspace') { navigate(back, backParams); return; }
        const scroller = container.querySelector('.detail-main');

        if (focus === 'rail') {
          if (e.key === 'ArrowDown') { e.preventDefault(); if (tabIndex < TABS.length - 1) setTab(tabIndex + 1); }
          if (e.key === 'ArrowUp') {
            e.preventDefault();
            // Header reads "↑ VOLTAR AOS JOGOS" — pressing up past the first
            // section exits Detail, matching that affordance.
            if (tabIndex > 0) setTab(tabIndex - 1);
            else navigate(back, backParams);
          }
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
      container.innerHTML = err.message.includes('404') ? buildNotFound() : buildError(err.message);
      function onKey(e) {
        if (e.key === 'Escape' || e.key === 'Backspace') navigate(back, backParams);
      }
      onKeyHandler = onKey;
      document.addEventListener('keydown', onKey);
    });

  return () => {
    cancelled = true;
    if (onKeyHandler) document.removeEventListener('keydown', onKeyHandler);
  };
}

// Matches the mock's Estado 2/3 treatment: glowC wash at .5 opacity plus a
// static vignette fading to solid bg by 40% down — same glowC formula as
// Home's backdrop (shared via utils.glowCGradient), not an invented one.
function applyBackdrop(container, d) {
  const root = document.getElementById('screen-backdrop');
  if (!root) return;
  root.innerHTML = `
    <div class="detail-backdrop" id="detail-backdrop"></div>
    <div class="detail-vignette"></div>`;
  const el = document.getElementById('detail-backdrop');
  if (!d.cover_url) {
    const hue = hueOfName(d.display_name);
    el.style.background = glowCGradient(hue);
    el.classList.add('visible');
    container.querySelector('.screen-detail')?.style.setProperty('--accent-game', `hsl(${hue}, 70%, 66%)`);
    return;
  }
  extractDominantColor(d.cover_url).then(c => {
    if (!c || !el.isConnected) return;
    const hue = hueOf(c);
    el.style.background = glowCGradient(hue);
    el.classList.add('visible');
    container.querySelector('.screen-detail')?.style.setProperty('--accent-game', `hsl(${hue}, 70%, 66%)`);
  });
}

function buildHTML(d, tabContent, tabIndex) {
  const logo = getPlatformLogo(d.platform);
  const cover = d.cover_url
    ? `<img src="${d.cover_url}" alt="" style="width:100%;height:100%;object-fit:cover">`
    : `<div class="cover-gradient" style="background:${cardGradient(d.display_name)};width:100%;height:100%;display:flex;align-items:flex-end;padding:12px">
         <span class="card-name-fb">${d.display_name.toUpperCase()}</span>
       </div>`;

  const rail = TABS.map((t, i) =>
    `<div class="rail-item${i === tabIndex ? ' active' : ''}" data-tab="${t.key}">${t.label}</div>`
  ).join('');

  const meta = [logo ? null : d.platform, d.genre].filter(Boolean).join(' · ');

  return `<div class="screen-detail">
    <div class="detail-body">
      <aside class="detail-side">
        <div class="detail-cover"><div class="detail-cover-inner">${cover}</div></div>
        <div class="side-rail detail-rail">${rail}</div>
      </aside>

      <div class="detail-main">
        <div class="detail-platform-row">
          ${logo ? `<img src="${logo}" alt="${d.platform}" class="detail-platform-logo">` : ''}
          <span class="detail-meta-text">${meta}</span>
        </div>
        <h1 class="detail-title">${d.display_name}</h1>

        <div id="detail-tab-content" class="detail-tab-content">${tabContent}</div>
      </div>
    </div>
  </div>`;
}

function buildOverviewTab(d) {
  const meta = [
    { label: 'Desenvolvedora', value: d.developer || '—' },
    { label: 'Publicadora', value: d.publisher || '—' },
    { label: 'Lançamento', value: d.release_year || '—' },
    { label: 'Modos', value: d.game_modes || '—' },
  ].map(m => `
    <div class="insight-card">
      <div class="insight-card-label">${m.label}</div>
      <div class="insight-card-value">${m.value}</div>
    </div>`).join('');

  const quickFacts = [
    { label: 'Tempo total', value: fmtTime(d.total_seconds), accent: true },
    { label: 'Primeira vez', value: fmtDate(d.first_played) },
    { label: 'Último acesso', value: fmtDateShort(d.last_played) },
    { label: 'Emulador', value: d.sessions[0] ? fmtSource(d.sessions[0].source) : '—' },
  ].map(i => `
    <div class="insight-card insight-card-lg${i.accent ? ' insight-card-accent' : ''}">
      <div class="insight-card-label">${i.label}</div>
      <div class="insight-card-value">${i.value}</div>
    </div>`).join('');

  return `
    <div class="insight-cards">${meta}</div>
    ${d.summary ? `<div class="detail-synopsis-panel">
      <div class="detail-synopsis-head"><span>Sinopse</span><span class="detail-synopsis-source">Fonte: IGDB</span></div>
      <p class="detail-summary">${d.summary}</p>
    </div>` : ''}
    <div class="insight-cards-loose">${quickFacts}</div>`;
}

function dayKey(date) {
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`;
}

function toLocalDate(iso) {
  return new Date(iso.includes('Z') ? iso : iso + 'Z');
}

function computeMonths(sessions, year) {
  const totals = Array(12).fill(0);
  for (const s of sessions) {
    if (!s.started_at || !s.duration_s) continue;
    const dt = toLocalDate(s.started_at);
    if (dt.getFullYear() !== year) continue;
    totals[dt.getMonth()] += s.duration_s;
  }
  const max = Math.max(...totals, 1);
  return MONTH_LABELS.map((label, i) => ({ label, pct: Math.max(2, Math.round((totals[i] / max) * 100)) }));
}

function computeWeekdays(sessions) {
  const totals = Array(7).fill(0);
  for (const s of sessions) {
    if (!s.started_at || !s.duration_s) continue;
    totals[localWeekdayMon0(s.started_at)] += s.duration_s;
  }
  const max = Math.max(...totals, 1);
  return WEEKDAY_LABELS.map((label, i) => ({
    label,
    total_seconds: totals[i],
    peak: totals[i] === max && max > 0,
    pct: Math.max(2, Math.round((totals[i] / max) * 100)),
  }));
}

function computeHours(sessions) {
  const totals = Array(24).fill(0);
  for (const s of sessions) {
    if (!s.started_at || !s.duration_s) continue;
    totals[localHour(s.started_at)] += s.duration_s;
  }
  const max = Math.max(...totals, 1);
  return totals.map(t => ({ pct: Math.max(2, Math.round((t / max) * 100)) }));
}

function computeHeatmap(sessions, days) {
  const byDay = new Map();
  for (const s of sessions) {
    if (!s.started_at || !s.duration_s) continue;
    const key = localDateKey(s.started_at);
    byDay.set(key, (byDay.get(key) ?? 0) + s.duration_s);
  }
  const max = Math.max(...byDay.values(), 1);
  const today = new Date();
  const cells = [];
  for (let i = days - 1; i >= 0; i--) {
    const d = new Date(today);
    d.setDate(d.getDate() - i);
    const total = byDay.get(dayKey(d)) ?? 0;
    cells.push({ opacity: total ? (0.12 + (total / max) * 0.65).toFixed(2) : 0.05 });
  }
  return cells;
}

function computeStreaks(sessions) {
  const daySet = new Set();
  for (const s of sessions) {
    if (!s.started_at) continue;
    daySet.add(localDateKey(s.started_at));
  }
  if (daySet.size === 0) return { current: 0, longest: 0 };

  const sortedDates = [...daySet].map(k => new Date(`${k}T00:00:00`)).sort((a, b) => a - b);
  let longest = 1, run = 1;
  for (let i = 1; i < sortedDates.length; i++) {
    const diff = Math.round((sortedDates[i] - sortedDates[i - 1]) / 86400000);
    if (diff === 1) { run++; longest = Math.max(longest, run); } else { run = 1; }
  }

  const today = new Date();
  const yesterday = new Date(today);
  yesterday.setDate(yesterday.getDate() - 1);
  let anchorKey;
  if (daySet.has(dayKey(today))) anchorKey = dayKey(today);
  else if (daySet.has(dayKey(yesterday))) anchorKey = dayKey(yesterday);
  else return { current: 0, longest };

  let current = 0;
  let d = new Date(`${anchorKey}T00:00:00`);
  while (daySet.has(dayKey(d))) {
    current++;
    d.setDate(d.getDate() - 1);
  }
  return { current, longest };
}

// Average sessions/week across the game's playing lifespan (first → last session).
function computePerWeek(d) {
  if (!d.session_count || !d.first_played || !d.last_played) return '0.0';
  const first = toLocalDate(d.first_played);
  const last = toLocalDate(d.last_played);
  const days = Math.max(1, Math.round((last - first) / 86400000) + 1);
  return (d.session_count / Math.max(1, days / 7)).toFixed(1);
}

function computeLongestSessions(sessions, limit) {
  const top = sessions
    .filter(s => s.duration_s)
    .sort((a, b) => b.duration_s - a.duration_s)
    .slice(0, limit);
  const max = top[0]?.duration_s || 1;
  return top.map(s => ({
    date: fmtDateShort(s.started_at),
    duration_s: s.duration_s,
    pct: Math.max(4, Math.round((s.duration_s / max) * 100)),
  }));
}

function buildStatsTab(d) {
  const sessions = d.sessions ?? [];
  const year = new Date().getFullYear();
  const months = computeMonths(sessions, year);
  const heat = computeHeatmap(sessions, HEATMAP_DAYS);
  const weekdays = computeWeekdays(sessions);
  const hours = computeHours(sessions);
  const { current, longest } = computeStreaks(sessions);
  const perWeek = computePerWeek(d);
  const longestSessions = computeLongestSessions(sessions, 5);

  const monthBars = months.map(m => `
    <div class="wd-col">
      <div class="wd-bar-wrap"><div class="wd-bar month-bar" style="height:${m.pct}%"></div></div>
      <div class="wd-label">${m.label}</div>
    </div>`).join('');

  const heatCells = heat.map(h => `<div class="heatmap-cell" style="background:rgba(255,255,255,${h.opacity})"></div>`).join('');

  const weekdayCols = weekdays.map(w => `
    <div class="wd-col${w.peak ? ' peak' : ''}">
      <div class="wd-value">${w.total_seconds ? fmtTime(w.total_seconds) : ''}</div>
      <div class="wd-bar-wrap"><div class="wd-bar" style="height:${w.pct}%"></div></div>
      <div class="wd-label">${w.label}</div>
    </div>`).join('');

  const hourBars = hours.map(h => `<div class="hour-bar" style="height:${h.pct}%"></div>`).join('');

  const longestSessionRows = longestSessions.map(s => `
    <div class="platform-bar-row">
      <div class="platform-bar-logo stat-label-wide"><span class="platform-text">${s.date}</span></div>
      <div class="platform-bar-track"><div class="platform-bar-fill" style="width:${s.pct}%"></div></div>
      <div class="platform-bar-value">${fmtTime(s.duration_s)}</div>
    </div>`).join('');

  return `
    <div class="stats-grid-detail">
      <div class="pg-panel span-2">
        <div class="pg-panel-head"><span class="pg-panel-title">Tempo por mês</span><span class="pg-panel-sub">${year}</span></div>
        <div class="month-chart">${monthBars}</div>
      </div>
      <div class="pg-panel pg-panel-flex">
        <div class="pg-panel-title">Tempo total</div>
        <div class="pg-total-value">${fmtTime(d.total_seconds)}</div>
        <div class="pg-panel-sub">${d.session_count} SESSÕES · ${countUniqueDays(sessions)} DIAS</div>
      </div>
      <div class="pg-panel span-2">
        <div class="pg-panel-head"><span class="pg-panel-title">Frequência</span><span class="pg-panel-sub">ÚLTIMAS 13 SEMANAS</span></div>
        <div class="heatmap-grid">${heatCells}</div>
      </div>
      <div class="pg-panel pace-panel">
        <div class="pg-panel-title">Ritmo</div>
        <div class="pace-value">${longest} dias</div>
        <div class="pg-panel-sub">MAIOR SEQUÊNCIA</div>
        <div class="pace-value">${perWeek}×</div>
        <div class="pg-panel-sub">SESSÕES POR SEMANA</div>
      </div>
      <div class="pg-panel">
        <div class="pg-panel-title">Dia da semana</div>
        <div class="weekday-chart weekday-chart-sm">${weekdayCols}</div>
      </div>
      <div class="pg-panel">
        <div class="pg-panel-title">Hora do dia</div>
        <div class="hour-chart">${hourBars}</div>
        <div class="hour-chart-axis"><span>00h</span><span>12h</span><span>23h</span></div>
      </div>
      <div class="pg-panel">
        <div class="pg-panel-title">Sessões</div>
        <div class="stat-rows">
          <div class="stat-row"><span>Mais longa</span><span>${fmtTime(d.longest_session_s)}</span></div>
          <div class="stat-row"><span>Média</span><span>${fmtTime(d.avg_session_s ? Math.round(d.avg_session_s) : null)}</span></div>
          <div class="stat-row"><span>Melhor dia</span><span>${fmtDayDate(d.best_day)}</span></div>
          <div class="stat-row"><span>Primeira vez</span><span>${fmtDate(d.first_played)}</span></div>
        </div>
      </div>
      <div class="pg-panel span-3">
        <div class="pg-panel-title">Sessões mais longas</div>
        ${longestSessions.length
          ? `<div class="platform-bars">${longestSessionRows}</div>`
          : `<div class="heatmap-empty">Sem sessões registradas.</div>`}
      </div>
    </div>`;
}

function buildAchievementsTab() {
  return `
    <div class="stat-panel">
      <div class="section-header">RetroAchievements</div>
      <div class="ra-placeholder">
        Fase 6 — integração com RetroAchievements não implementada ainda
      </div>
    </div>`;
}

function fmtDayDate(dateStr) {
  if (!dateStr) return '—';
  const [y, m, d] = dateStr.split('-');
  return `${d}/${m}/${y}`;
}

function countUniqueDays(sessions) {
  if (!sessions?.length) return '—';
  const days = new Set(sessions.map(s => localDateKey(s.started_at)));
  return days.size;
}

function buildNotFound() {
  return `<div class="screen-detail">
    <p style="color:var(--text-muted);margin:40px var(--side-pad)">Jogo não encontrado.</p>
  </div>`;
}

function buildError(msg) {
  return `<div class="screen-detail">
    <p style="color:var(--text-muted);margin:40px var(--side-pad)">Erro ao carregar jogo.<br><small>${msg}</small></p>
  </div>`;
}
