import { fetchGameDetail } from '../data/api.js';
import { fmtTime, fmtDate, fmtDateShort, fmtSource, cardGradient, getPlatformLogo, extractDominantColor } from '../utils.js';

const SCROLL_STEP = 240;
const MAX_SESSIONS = 8;

export function mount(container, navigate, params = {}) {
  let onKeyHandler = null;
  let cancelled = false;

  container.innerHTML = '<div style="padding:40px;color:var(--text-muted);text-align:center">Carregando...</div>';

  function setupNav() {
    const back = params.from ?? 'home';
    const backParams = params.from === 'library'
      ? { selectedIndex: params.libraryIndex, platformFilter: params.libraryFilter }
      : {};
    function onKey(e) {
      if (e.key === 'Escape' || e.key === 'Backspace') { navigate(back, backParams); return; }
      const scroller = container.querySelector('.detail-main');
      if (!scroller) return;
      if (e.key === 'ArrowDown') { e.preventDefault(); scroller.scrollBy({ top: SCROLL_STEP, behavior: 'smooth' }); }
      if (e.key === 'ArrowUp')   { e.preventDefault(); scroller.scrollBy({ top: -SCROLL_STEP, behavior: 'smooth' }); }
    }
    container.querySelector('.detail-back')?.addEventListener('click', () => navigate(back, backParams));
    onKeyHandler = onKey;
    document.addEventListener('keydown', onKey);
  }

  fetchGameDetail(params.gameId)
    .then(detail => {
      if (cancelled) return;
      container.innerHTML = buildHTML(detail);
      setupNav();
      applyBackdrop(container, detail);
    })
    .catch(err => {
      if (cancelled) return;
      container.innerHTML = err.message.includes('404') ? buildNotFound() : buildError(err.message);
      setupNav();
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

function buildHTML(d) {
  const logo = getPlatformLogo(d.platform);
  const cover = d.cover_url
    ? `<img src="${d.cover_url}" alt="" style="width:100%;height:100%;object-fit:cover">`
    : `<div class="cover-gradient" style="background:${cardGradient(d.display_name)};width:100%;height:100%;display:flex;align-items:flex-end;padding:12px">
         <span class="card-name-fb">${d.display_name.toUpperCase()}</span>
       </div>`;

  const recent = d.sessions.slice(0, MAX_SESSIONS);
  const maxDur = Math.max(...recent.map(s => s.duration_s || 0), 1);
  const sessions = recent.map(s => `
    <div class="session-row">
      <span class="session-date">${fmtDateShort(s.started_at)}</span>
      <div class="session-bar">
        <div class="session-bar-fill" style="width:${Math.max(3, Math.round(((s.duration_s || 0) / maxDur) * 100))}%"></div>
      </div>
      <span class="session-dur">${fmtTime(s.duration_s)}</span>
    </div>`).join('');
  const moreCount = d.session_count - recent.length;

  const insights = [
    { label: 'Média por sessão', value: fmtTime(d.avg_session_s ? Math.round(d.avg_session_s) : null) },
    { label: 'Sessão mais longa', value: fmtTime(d.longest_session_s), sub: d.longest_session_date ? fmtDayDate(d.longest_session_date) : null },
    { label: 'Melhor dia', value: fmtDayDate(d.best_day), sub: d.best_day_total_s ? `${fmtTime(d.best_day_total_s)} jogados` : null },
    { label: 'Primeira vez', value: fmtDate(d.first_played) },
    { label: 'Dias jogados', value: countUniqueDays(d.sessions) },
  ].map(i => `
    <div class="insight-row">
      <div class="insight-label">${i.label}</div>
      <div class="insight-value">${i.value}${i.sub ? `<span class="insight-sub">${i.sub}</span>` : ''}</div>
    </div>`).join('');

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
        <div class="detail-insights">
          <div class="section-header">Insights</div>
          ${insights}
        </div>
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

        ${d.summary ? `<div>
          <div class="section-header">Sinopse</div>
          <p class="detail-summary">${d.summary}</p>
        </div>` : ''}

        <div>
          <div class="section-header">Últimas sessões</div>
          <div class="sessions-list">${sessions}</div>
          ${moreCount > 0 ? `<div class="sessions-more">+ ${moreCount} ${moreCount === 1 ? 'sessão anterior' : 'sessões anteriores'}</div>` : ''}
        </div>

        <div>
          <div class="section-header">RetroAchievements</div>
          <div class="ra-placeholder">
            Fase 6 — integração com RetroAchievements não implementada ainda
          </div>
        </div>
      </div>
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
  const days = new Set(sessions.map(s => s.started_at?.slice(0, 10)));
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
