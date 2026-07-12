import { fetchGames, fetchStats, fetchActivity } from '../data/api.js';
import { fmtTime, fmtDate, cardGradient, platformLogoImg } from '../utils.js';

const TABS = [
  { key: 'overview', label: 'Visão geral' },
  { key: 'activity', label: 'Atividade' },
  { key: 'library', label: 'Biblioteca' },
];

export function mount(container, navigate, params = {}) {
  let tabIndex = Math.max(0, TABS.findIndex(t => t.key === params.tab));
  let onKeyHandler = null;
  let cancelled = false;

  container.innerHTML = '<div style="padding:40px;color:var(--text-muted);text-align:center">Carregando...</div>';

  Promise.all([fetchGames(), fetchStats(), fetchActivity()])
    .then(([games, stats, activity]) => {
      if (cancelled) return;

      const content = {
        overview: buildOverview(stats, games, activity),
        activity: buildActivity(activity),
        library: buildLibraryTab(stats, games),
      };

      const rail = TABS.map((t, i) =>
        `<div class="rail-item${i === tabIndex ? ' active' : ''}" data-tab="${t.key}">${t.label}</div>`
      ).join('');

      container.innerHTML = `<div class="screen-stats">
        <aside class="side-rail">${rail}</aside>
        <div class="stats-content" id="stats-content">${content[TABS[tabIndex].key]}</div>
      </div>`;

      function setTab(i) {
        tabIndex = i;
        container.querySelectorAll('.rail-item').forEach((el, j) => {
          el.classList.toggle('active', j === tabIndex);
        });
        document.getElementById('stats-content').innerHTML = content[TABS[tabIndex].key];
      }

      container.querySelectorAll('.rail-item').forEach((el, i) => {
        el.addEventListener('click', () => setTab(i));
      });

      function onKey(e) {
        if (e.key === 'Escape' || e.key === 'Backspace') { navigate('home'); return; }
        if (e.key === 'ArrowDown') { e.preventDefault(); if (tabIndex < TABS.length - 1) setTab(tabIndex + 1); }
        if (e.key === 'ArrowUp')   { e.preventDefault(); if (tabIndex > 0) setTab(tabIndex - 1); }
      }
      onKeyHandler = onKey;
      document.addEventListener('keydown', onKey);
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

function panel(title, body) {
  return `<div class="stat-panel">
    <div class="section-header">${title}</div>
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

function buildOverview(s, games, activity) {
  const topGames = [...games].sort((a, b) => b.total_seconds - a.total_seconds).slice(0, 8);
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

  return `
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

    ${panel('Mais jogados', `<div class="top-games-list top-games-wide">${topList}</div>`)}`;
}

function buildActivity(activity) {
  const weekdays = activity?.by_weekday ?? [];
  const maxWeekday = Math.max(...weekdays.map(d => d.total_seconds), 1);
  const weekdayCols = weekdays.map(d => `
    <div class="wd-col${d.total_seconds === maxWeekday ? ' peak' : ''}">
      <div class="wd-value">${d.total_seconds ? fmtTime(d.total_seconds) : ''}</div>
      <div class="wd-bar-wrap">
        <div class="wd-bar" style="height:${Math.max(1, Math.round((d.total_seconds / maxWeekday) * 100))}%"></div>
      </div>
      <div class="wd-label">${d.day}</div>
    </div>`).join('');

  const byHour = activity?.by_hour ?? [];
  const periodTotals = DAY_PERIODS.map(p => ({
    ...p,
    total: byHour
      .filter(h => h.hour >= p.from && h.hour <= p.to)
      .reduce((a, h) => a + h.total_seconds, 0),
  }));
  const periodGrand = periodTotals.reduce((a, p) => a + p.total, 0);
  const maxPeriod = Math.max(...periodTotals.map(p => p.total), 1);
  const periodCards = periodTotals.map(p => `
    <div class="period-card${p.total === maxPeriod ? ' peak' : ''}">
      <div class="period-head"><span class="period-icon">${p.icon}</span>${p.label}</div>
      <div class="period-value">${p.total ? fmtTime(p.total) : '—'}</div>
      <div class="period-sub">${periodGrand ? Math.round((p.total / periodGrand) * 100) : 0}% do total</div>
    </div>`).join('');

  return `
    ${panel('Dia da semana', `<div class="weekday-chart">${weekdayCols}</div>`)}
    ${panel('Período do dia', `<div class="period-cards period-cards-row">${periodCards}</div>`)}`;
}

function buildLibraryTab(s, games) {
  const maxPlatform = Math.max(...s.by_platform.map(p => p.total_seconds), 1);
  const bars = s.by_platform.map(p => `
    <div class="platform-bar-row">
      <div class="platform-bar-logo">${platformLogoImg(p.platform)}</div>
      <div class="platform-bar-track">
        <div class="platform-bar-fill" style="width:${Math.round((p.total_seconds / maxPlatform) * 100)}%"></div>
      </div>
      <div class="platform-bar-value">${fmtTime(p.total_seconds)}</div>
    </div>`).join('');

  const genreBars = aggregateBy(games, g => splitField(g.genre), 'Sem gênero')
    .slice(0, 6)
    .map(g => barRow(g.label, g.total_seconds, g.pct))
    .join('');

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
        ${panel('Por plataforma', `<div class="platform-bars">${bars}</div>`)}
        ${panel('Por gênero', `<div class="platform-bars">${genreBars}</div>`)}
      </div>
      <div class="stats-col">
        ${panel('Por desenvolvedora', `<div class="platform-bars">${developerBars}</div>`)}
        ${panel('Por década', `<div class="platform-bars">${decadeBars}</div>`)}
        ${panel('Por modo de jogo', `<div class="platform-bars">${gameModeBars}</div>`)}
      </div>
    </div>`;
}
