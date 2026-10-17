import { fetchSystemLive } from '../data/api.js';

const TABS = [
  { key: 'live', label: 'Agora', icon: 'monitor_heart' },
];

// CPU, rede e processos são taxas calculadas entre duas leituras do daemon:
// o intervalo é o "passo" delas.
const REFRESH_MS = 2000;
const SCROLL_STEP = 240;
const TEMP_WARN = 70;
const TEMP_BAD = 80;

export function mount(container, navigate) {
  let tabIndex = 0;
  let focus = 'rail';
  let timer = null;
  let cancelled = false;

  const backdrop = document.getElementById('screen-backdrop');
  if (backdrop) backdrop.innerHTML = '<div class="stats-backdrop"></div>';

  const rail = TABS.map((t, i) =>
    `<div class="rail-item${i === tabIndex ? ' active' : ''}" data-tab="${t.key}"><span class="msr">${t.icon}</span>${t.label}</div>`
  ).join('');

  container.innerHTML = `<div class="screen-stats">
    <aside class="side-rail">${rail}</aside>
    <div class="stats-content" id="stats-content">
      <div style="padding:40px;color:var(--text-muted);text-align:center">Carregando...</div>
    </div>
  </div>`;

  function refreshRail() {
    container.querySelectorAll('.rail-item').forEach((el, j) => {
      el.classList.toggle('active', j === tabIndex);
      el.classList.toggle('focused', focus === 'rail' && j === tabIndex);
    });
  }

  // Re-renders in place every REFRESH_MS; the scroll position survives the
  // innerHTML swap so the d-pad scroll doesn't jump back to the top.
  async function refresh() {
    try {
      const s = await fetchSystemLive();
      if (cancelled) return;
      const el = document.getElementById('stats-content');
      const top = el.scrollTop;
      el.innerHTML = buildLive(s);
      el.scrollTop = top;
    } catch (err) {
      if (cancelled) return;
      document.getElementById('stats-content').innerHTML =
        `<div style="padding:40px;color:var(--text-muted);text-align:center">Erro ao ler o sistema.<br><small>${err.message}</small></div>`;
    }
    if (!cancelled) timer = setTimeout(refresh, REFRESH_MS);
  }

  function onKey(e) {
    if (e.key === 'Escape' || e.key === 'Backspace') { navigate('home'); return; }
    if (focus === 'rail') {
      if (e.key === 'ArrowRight') { focus = 'content'; refreshRail(); }
      return;
    }
    if (e.key === 'ArrowLeft') { focus = 'rail'; refreshRail(); return; }
    const scroller = document.getElementById('stats-content');
    if (e.key === 'ArrowDown') { e.preventDefault(); scroller.scrollBy({ top: SCROLL_STEP, behavior: 'smooth' }); }
    if (e.key === 'ArrowUp')   { e.preventDefault(); scroller.scrollBy({ top: -SCROLL_STEP, behavior: 'smooth' }); }
  }

  document.addEventListener('keydown', onKey);
  refreshRail();
  refresh();

  return () => {
    cancelled = true;
    clearTimeout(timer);
    document.removeEventListener('keydown', onKey);
  };
}

// ── Formatação ────────────────────────────────────────────────────────────

const num = (v, digits = 0) => v.toLocaleString('pt-BR', { minimumFractionDigits: digits, maximumFractionDigits: digits });
const gb = mb => num(mb / 1024, 1);

function fmtUptime(secs) {
  const d = Math.floor(secs / 86400);
  const h = Math.floor((secs % 86400) / 3600);
  const m = Math.floor((secs % 3600) / 60);
  return d ? `${d}d ${h}h` : h ? `${h}h ${m}min` : `${m}min`;
}

function fmtRate(mbps) {
  if (mbps == null) return '—';
  return mbps < 1 ? `${num(mbps * 1000)} kbit/s` : `${num(mbps, 1)} Mbit/s`;
}

function tempLevel(c) {
  return c >= TEMP_BAD ? 'bad' : c >= TEMP_WARN ? 'warn' : 'ok';
}

// ── Componentes (mesmas primitivas da tela de Estatísticas) ──────────────

function panel(title, body, sub) {
  return `<div class="pg-panel">
    ${sub
      ? `<div class="pg-panel-head"><span class="pg-panel-title">${title}</span><span class="pg-panel-sub">${sub}</span></div>`
      : `<div class="pg-panel-title">${title}</div>`}
    ${body}
  </div>`;
}

function card(icon, label, value, sub, level) {
  return `<div class="stats-card">
    <div class="stats-card-label"><span class="msr">${icon}</span>${label}</div>
    <div class="stats-card-value${level ? ` sys-${level}` : ''}">${value}</div>
    ${sub ? `<div class="sys-card-sub">${sub}</div>` : ''}
  </div>`;
}

function bar(label, pct, value, level) {
  return `<div class="platform-bar-row">
    <div class="platform-bar-logo stat-label-wide"><span class="platform-text">${label}</span></div>
    <div class="platform-bar-track">
      <div class="platform-bar-fill${level ? ` sys-fill-${level}` : ''}" style="width:${Math.max(1, Math.min(100, pct))}%"></div>
    </div>
    <div class="platform-bar-value sys-bar-value">${value}</div>
  </div>`;
}

function statusRow(level, label, detail) {
  return `<div class="sys-status-row">
    <span class="sys-dot sys-dot-${level}"></span>
    <span class="sys-status-label">${label}</span>
    <span class="sys-status-detail">${detail}</span>
  </div>`;
}

// ── Aba "Agora" ───────────────────────────────────────────────────────────

function summaryCards(s) {
  const t = s.throttled;
  const throttle = t.now.length
    ? { value: 'Limitando', sub: t.now.join(' · '), level: 'bad' }
    : t.since_boot.length
      ? { value: 'Atenção', sub: `Desde o boot: ${t.since_boot.join(' · ')}`, level: 'warn' }
      : { value: 'Normal', sub: 'Sem limitação desde o boot', level: 'ok' };
  const cpu = s.cpu ? `${num(s.cpu.total)}%` : '—';
  return `<div class="stats-summary-cards sys-summary-cards">
    ${card('thermostat', 'Temperatura', `${num(s.temp_c, 1)} °C`, null, tempLevel(s.temp_c))}
    ${card('developer_board', 'Processador', cpu, `${num(s.freq_mhz)} MHz`)}
    ${card('memory', 'Memória', `${gb(s.memory.used_mb)} GB`, `de ${gb(s.memory.total_mb)} GB`)}
    ${card('speed', 'Energia e clock', throttle.value, throttle.sub, throttle.level)}
  </div>`;
}

function cpuPanel(s) {
  const cores = s.cpu
    ? s.cpu.cores.map((c, i) => bar(`Núcleo ${i + 1}`, c, `${num(c)}%`)).join('')
    : '<div class="heatmap-empty">Medindo...</div>';
  const load = s.load.map(v => num(v, 2)).join(' · ');
  return panel('Processador', `<div class="platform-bars">${cores}</div>`, `Carga ${load} · ligado há ${fmtUptime(s.uptime_s)}`);
}

function diskPanel(s) {
  const rows = s.disks.map(d => {
    if (!d.mounted) return bar(d.label, 0, 'Desmontado', 'bad');
    const pct = (d.used_gb / d.total_gb) * 100;
    return bar(d.label, pct, `${num(d.used_gb)} / ${num(d.total_gb)} GB`, pct >= 90 ? 'bad' : pct >= 80 ? 'warn' : null);
  }).join('');
  return panel('Armazenamento', `<div class="platform-bars sys-disk-bars">${rows}</div>`);
}

function processPanel(s) {
  if (!s.processes) return panel('Processos', '<div class="heatmap-empty">Medindo...</div>');
  const max = Math.max(...s.processes.map(p => p.cpu), 1);
  const rows = s.processes.map(p => `<div class="sys-proc-row">
    <span class="sys-proc-name">${p.name}${p.count > 1 ? ` <span class="sys-proc-count">×${p.count}</span>` : ''}</span>
    <div class="platform-bar-track"><div class="platform-bar-fill" style="width:${Math.max(1, (p.cpu / Math.max(max, 100)) * 100)}%"></div></div>
    <span class="sys-proc-value">${num(p.cpu)}%</span>
    <span class="sys-proc-value">${num(p.rss_mb)} MB</span>
  </div>`).join('');
  return panel('Processos', `<div class="sys-proc-list">${rows}</div>`, 'CPU por núcleo · memória');
}

function networkPanel(s) {
  const rows = s.network.map(n => statusRow(
    n.up ? 'ok' : 'off',
    n.label,
    n.up ? `↓ ${fmtRate(n.rx_mbps)} · ↑ ${fmtRate(n.tx_mbps)}` : 'Desconectado',
  )).join('');
  return panel('Rede', `<div class="sys-status-list">${rows}</div>`);
}

function controllerPanel(s) {
  const rows = s.controllers.length
    ? s.controllers.map(c => statusRow('ok', c.name, c.bus)).join('')
    : '<div class="heatmap-empty">Nenhum controle conectado</div>';
  return panel('Controles', `<div class="sys-status-list">${rows}</div>`);
}

function servicePanel(s) {
  const rows = s.services.map(sv => statusRow(
    sv.state === 'active' ? 'ok' : 'bad',
    sv.label,
    sv.state === 'active' ? 'Rodando' : sv.state === 'inactive' ? 'Parado' : sv.state === 'failed' ? 'Falhou' : sv.state,
  )).join('');
  return panel('Serviços', `<div class="sys-status-list sys-status-grid">${rows}</div>`);
}

function buildLive(s) {
  return `<div class="stats-overview-grid sys-grid">
    <div class="span-4">${summaryCards(s)}</div>
    <div class="span-2">${cpuPanel(s)}</div>
    <div class="span-2">${diskPanel(s)}</div>
    <div class="span-2">${processPanel(s)}</div>
    <div class="span-2 stats-overview-side">
      ${networkPanel(s)}
      ${controllerPanel(s)}
    </div>
    <div class="span-4">${servicePanel(s)}</div>
  </div>`;
}
