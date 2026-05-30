import { GAME_DETAIL } from '../data/mock.js';
import { fmtTime, fmtDate, fmtSource, cardGradient, platformLogoImg, PLATFORM_LOGO } from '../utils.js';

export function mount(container, navigate, params = {}) {
  const detail = GAME_DETAIL[params.gameId];
  container.innerHTML = detail ? buildHTML(detail) : buildNotFound();

  function onKey(e) {
    if (e.key === 'Escape' || e.key === 'Backspace') navigate('home');
  }

  container.querySelector('.detail-back')?.addEventListener('click', () => navigate('home'));
  document.addEventListener('keydown', onKey);
  return () => document.removeEventListener('keydown', onKey);
}

function buildHTML(d) {
  const logo = PLATFORM_LOGO[d.platform];
  const cover = d.cover_url
    ? `<img src="${d.cover_url}" alt="" style="width:100%;height:100%;object-fit:cover">`
    : `<div class="cover-gradient" style="background:${cardGradient(d.display_name)};width:100%;height:100%;display:flex;align-items:flex-end;padding:12px">
         <span class="card-name-fb">${d.display_name.toUpperCase()}</span>
       </div>`;

  const sessions = d.sessions.map(s => `
    <div class="session-row">
      <span class="session-date">${fmtDate(s.started_at)}</span>
      <span class="session-dur">${fmtTime(s.duration_s)}</span>
      <span class="session-src">${fmtSource(s.source)}</span>
    </div>`).join('');

  return `<div class="screen-detail">
    <div class="detail-back">
      <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="2">
        <path d="M10 3L5 8l5 5"/>
      </svg>
      Voltar
    </div>

    <div class="detail-header">
      <div class="detail-cover"><div class="detail-cover-inner">${cover}</div></div>
      <div class="detail-info">
        <div class="detail-platform-row">
          ${logo ? `<img src="${logo}" alt="${d.platform}" class="detail-platform-logo">` : ''}
          <span class="detail-meta-text">${[d.platform, d.release_year, d.genre].filter(Boolean).join(' · ')}</span>
        </div>
        <h1 class="detail-title">${d.display_name}</h1>
        <div class="detail-stats-row">
          <div class="hero-stat">
            <div class="stat-label">TEMPO TOTAL</div>
            <div class="stat-value">${fmtTime(d.total_seconds)}</div>
          </div>
          <div class="hero-stat">
            <div class="stat-label">SESSÕES</div>
            <div class="stat-value">${d.session_count}</div>
          </div>
          <div class="hero-stat">
            <div class="stat-label">ÚLTIMO ACESSO</div>
            <div class="stat-value">${fmtDate(d.last_played)}</div>
          </div>
          <div class="hero-stat">
            <div class="stat-label">EMULADOR</div>
            <div class="stat-value">${d.sessions[0] ? fmtSource(d.sessions[0].source) : '—'}</div>
          </div>
        </div>
      </div>
    </div>

    <div>
      <div class="section-header">Sessões</div>
      <div class="sessions-list" style="margin-top:12px">${sessions}</div>
    </div>

    <div>
      <div class="section-header">RetroAchievements</div>
      <div class="ra-placeholder" style="margin-top:12px">
        Fase 6 — integração com RetroAchievements não implementada ainda
      </div>
    </div>
  </div>`;
}

function buildNotFound() {
  return `<div class="screen-detail">
    <div class="detail-back">← Voltar</div>
    <p style="color:var(--text-muted);margin-top:40px">Jogo não encontrado.</p>
  </div>`;
}
