import { fetchGameDetail } from '../data/api.js';
import { fmtTime, fmtDate, fmtDateShort, fmtSource, cardGradient, getPlatformLogo, extractDominantColor, localDateKey } from '../utils.js';

const SCROLL_STEP = 240;

const TABS = [
  { key: 'overview', label: 'Visão geral' },
  { key: 'sessions', label: 'Sessões' },
  { key: 'achievements', label: 'Conquistas' },
];

export function mount(container, navigate, params = {}) {
  let tabIndex = 0;
  let focus = 'rail';
  let onKeyHandler = null;
  let cancelled = false;

  container.innerHTML = '<div style="padding:40px;color:var(--text-muted);text-align:center">Carregando...</div>';

  const back = params.from ?? 'home';
  const backParams = params.from === 'library'
    ? { selectedIndex: params.libraryIndex, platformFilter: params.libraryFilter }
    : {};

  fetchGameDetail(params.gameId)
    .then(detail => {
      if (cancelled) return;

      const content = {
        overview: buildOverviewTab(detail),
        sessions: buildSessionsTab(detail),
        achievements: buildAchievementsTab(),
      };

      container.innerHTML = buildHTML(detail, content[TABS[tabIndex].key], tabIndex);
      applyBackdrop(container, detail);
      container.querySelector('.detail-back')?.addEventListener('click', () => navigate(back, backParams));

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
      container.innerHTML = err.message.includes('404') ? buildNotFound() : buildError(err.message);
      container.querySelector('.detail-back')?.addEventListener('click', () => navigate(back, backParams));
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

function applyBackdrop(container, d) {
  const el = container.querySelector('.detail-backdrop');
  if (!el) return;
  if (!d.cover_url) {
    el.style.background =
      `linear-gradient(180deg, rgba(13, 13, 26, 0.5) 0%, rgba(13, 13, 26, 0.8) 45%, var(--bg) 80%), ${cardGradient(d.display_name)}`;
    el.classList.add('visible');
    return;
  }
  extractDominantColor(d.cover_url).then(c => {
    if (!c || !el.isConnected) return;
    el.style.background =
      `linear-gradient(170deg, rgba(${c}, 0.55) 0%, rgba(${c}, 0.18) 45%, transparent 75%)`;
    el.classList.add('visible');
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

  const meta = [logo ? null : d.platform, d.release_year, d.genre, d.developer]
    .filter(Boolean).join(' · ');

  return `<div class="screen-detail">
    <div class="detail-backdrop"></div>

    <div class="detail-topbar">
      <div class="detail-back">
        <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M10 3L5 8l5 5"/>
        </svg>
        Voltar
      </div>
    </div>

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

        <div class="detail-hero-stats">
          <div class="detail-hero-stat">
            <div class="stat-value-xl">${fmtTime(d.total_seconds)}</div>
            <div class="stat-label">Tempo total</div>
          </div>
          <div class="detail-hero-stat">
            <div class="stat-value-lg">${d.session_count}</div>
            <div class="stat-label">Sessões</div>
          </div>
          <div class="detail-hero-stat">
            <div class="stat-value-lg">${fmtDateShort(d.last_played)}</div>
            <div class="stat-label">Último acesso</div>
          </div>
          <div class="detail-hero-stat">
            <div class="stat-value-lg">${d.sessions[0] ? fmtSource(d.sessions[0].source) : '—'}</div>
            <div class="stat-label">Emulador</div>
          </div>
        </div>

        <div id="detail-tab-content" class="detail-tab-content">${tabContent}</div>
      </div>
    </div>
  </div>`;
}

function buildOverviewTab(d) {
  const insights = [
    { label: 'Média por sessão', value: fmtTime(d.avg_session_s ? Math.round(d.avg_session_s) : null) },
    { label: 'Sessão mais longa', value: fmtTime(d.longest_session_s), sub: d.longest_session_date ? fmtDayDate(d.longest_session_date) : null },
    { label: 'Melhor dia', value: fmtDayDate(d.best_day), sub: d.best_day_total_s ? `${fmtTime(d.best_day_total_s)} jogados` : null },
    { label: 'Primeira vez', value: fmtDate(d.first_played) },
    { label: 'Dias jogados', value: countUniqueDays(d.sessions) },
  ].map(i => `
    <div class="insight-card">
      <div class="insight-card-label">${i.label}</div>
      <div class="insight-card-value">${i.value}</div>
      ${i.sub ? `<div class="insight-card-sub">${i.sub}</div>` : ''}
    </div>`).join('');

  return `
    <div class="stat-panel">
      <div class="section-header">Estatísticas</div>
      <div class="insight-cards">${insights}</div>
    </div>
    ${d.summary ? `<div class="stat-panel">
      <div class="section-header">Sinopse</div>
      <p class="detail-summary">${d.summary}</p>
    </div>` : ''}`;
}

function buildSessionsTab(d) {
  const maxDur = Math.max(...d.sessions.map(s => s.duration_s || 0), 1);
  const rows = d.sessions.map(s => `
    <div class="session-row">
      <span class="session-date">${fmtDate(s.started_at)}</span>
      <div class="session-bar">
        <div class="session-bar-fill" style="width:${Math.max(3, Math.round(((s.duration_s || 0) / maxDur) * 100))}%"></div>
      </div>
      <span class="session-dur">${fmtTime(s.duration_s)}</span>
      <span class="session-src">${fmtSource(s.source)}</span>
    </div>`).join('');

  return `
    <div class="stat-panel">
      <div class="section-header">Todas as sessões</div>
      <div class="sessions-list sessions-full">${rows}</div>
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
    <div class="detail-topbar"><div class="detail-back">← Voltar</div></div>
    <p style="color:var(--text-muted);margin:40px var(--side-pad)">Jogo não encontrado.</p>
  </div>`;
}

function buildError(msg) {
  return `<div class="screen-detail">
    <div class="detail-topbar"><div class="detail-back">← Voltar</div></div>
    <p style="color:var(--text-muted);margin:40px var(--side-pad)">Erro ao carregar jogo.<br><small>${msg}</small></p>
  </div>`;
}
