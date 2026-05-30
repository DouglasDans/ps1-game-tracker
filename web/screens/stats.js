import { STATS } from '../data/mock.js';
import { fmtTime, fmtDate, platformLogoImg } from '../utils.js';

export function mount(container, navigate, _params = {}) {
  container.innerHTML = buildHTML(STATS);

  function onKey(e) {
    if (e.key === 'Escape') navigate('home');
  }

  document.addEventListener('keydown', onKey);
  return () => document.removeEventListener('keydown', onKey);
}

function buildHTML(s) {
  const bars = s.by_platform.map(p => `
    <div class="platform-bar-row">
      <div class="platform-bar-logo">${platformLogoImg(p.platform)}</div>
      <div class="platform-bar-track">
        <div class="platform-bar-fill" style="width:${p.pct}%"></div>
      </div>
      <div class="platform-bar-value">${fmtTime(p.total_seconds)}</div>
    </div>`).join('');

  return `<div class="screen-stats">
    <div class="stats-page-title">Estatísticas</div>

    <div class="stats-cards">
      <div class="stats-card">
        <div class="stats-card-label">Tempo total</div>
        <div class="stats-card-value">${fmtTime(s.total_seconds)}</div>
        <div class="stats-card-sub">em todas as plataformas</div>
      </div>
      <div class="stats-card">
        <div class="stats-card-label">Jogos na biblioteca</div>
        <div class="stats-card-value">${s.total_games}</div>
        <div class="stats-card-sub">com pelo menos 1 sessão</div>
      </div>
      <div class="stats-card">
        <div class="stats-card-label">Mais jogado</div>
        <div class="stats-card-value" style="font-size:1.1rem;line-height:1.3">${s.most_played?.display_name ?? '—'}</div>
        <div class="stats-card-sub">${fmtTime(s.most_played?.total_seconds)}</div>
      </div>
      <div class="stats-card">
        <div class="stats-card-label">Sessão mais longa</div>
        <div class="stats-card-value">${fmtTime(s.longest_session?.duration_s)}</div>
        <div class="stats-card-sub">${s.longest_session?.display_name ?? '—'} · ${fmtDate(s.longest_session?.started_at)}</div>
      </div>
    </div>

    <div>
      <div class="section-header">Por plataforma</div>
      <div class="platform-bars" style="margin-top:16px">${bars}</div>
    </div>
  </div>`;
}
