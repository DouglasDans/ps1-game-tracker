import { mount as mountHome }    from './screens/home.js';
import { mount as mountDetail }  from './screens/detail.js';
import { mount as mountLibrary } from './screens/library.js';
import { mount as mountStats }   from './screens/stats.js';
import { API_HOST }              from './data/api.js';

const SCREENS = { home: mountHome, detail: mountDetail, library: mountLibrary, stats: mountStats };

let currentCleanup = null;
let currentScreen = null;

// Header pages cycled with L1/R1. Library and detail are sub-screens of
// Games and keep their own shoulder-button behavior.
const TOP_PAGES = ['home', 'stats'];

// Wraps a screen swap in the native View Transitions API so navigation
// gets a default crossfade for free; 'detail-open'/'detail-close' additionally
// get a custom slide via the CSS in style.css keyed off data-transition.
function withViewTransition(updateDOM, kind) {
  if (!document.startViewTransition) { updateDOM(); return; }
  document.documentElement.dataset.transition = kind || '';
  const transition = document.startViewTransition(updateDOM);
  transition.finished.finally(() => { delete document.documentElement.dataset.transition; });
}

export function navigate(screen, params = {}) {
  const kind = screen === 'detail' ? 'detail-open'
    : currentScreen === 'detail' ? 'detail-close'
    : null;

  withViewTransition(() => {
    if (currentCleanup) { currentCleanup(); currentCleanup = null; }
    currentScreen = screen;
    const main = document.getElementById('main');
    currentCleanup = SCREENS[screen](main, navigate, params) ?? null;
    updateNav(screen);
    updateHints(screen);
  }, kind);
}

function initPageSwitcher() {
  document.addEventListener('keydown', (e) => {
    if (e.key !== 'L1' && e.key !== 'R1') return;
    const idx = TOP_PAGES.indexOf(currentScreen);
    if (idx === -1) return;
    const dir = e.key === 'R1' ? 1 : -1;
    navigate(TOP_PAGES[(idx + dir + TOP_PAGES.length) % TOP_PAGES.length]);
  });
}

function updateNav(screen) {
  document.querySelectorAll('.nav-item').forEach(el => {
    el.classList.toggle('active', el.dataset.screen === screen);
  });
}

const SCREEN_HINTS = {
  home: `
    <span class="hint"><span class="hint-btn">✕</span><span class="hint-btn">↓</span> Detalhes</span>
    <span class="hint"><span class="hint-btn">□</span> Library</span>
    <span class="hint"><span class="hint-btn hint-btn-wide">R1</span> Stats</span>`,
  stats: `
    <span class="hint"><span class="hint-btn">○</span> Voltar</span>
    <span class="hint"><span class="hint-btn hint-btn-wide">L1</span> Games</span>
    <span class="hint"><span class="hint-btn">↑</span><span class="hint-btn">↓</span> Abas</span>`,
  library: `
    <span class="hint"><span class="hint-btn">✕</span> Selecionar</span>
    <span class="hint"><span class="hint-btn">○</span> Voltar</span>
    <span class="hint"><span class="hint-btn">←</span> Filtros</span>
    <span class="hint"><span class="hint-btn hint-btn-wide">L1</span><span class="hint-btn hint-btn-wide">R1</span> Filtro</span>`,
  detail: `
    <span class="hint"><span class="hint-btn">○</span> Voltar</span>
    <span class="hint"><span class="hint-btn">↑</span><span class="hint-btn">↓</span> Seções</span>
    <span class="hint"><span class="hint-btn">→</span> Rolar conteúdo</span>`,
};

function updateHints(screen) {
  const el = document.getElementById('bottom-hints');
  if (el) el.innerHTML = SCREEN_HINTS[screen] ?? SCREEN_HINTS.home;
}

function updateClock() {
  const el = document.getElementById('clock');
  if (el) el.textContent = new Date().toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' });
}

function initGamepad() {
  const prev = { buttons: [] };
  const HELD_DELAY = 300, HELD_REPEAT = 120;
  const heldTimers = {};

  function fireKey(key) {
    document.dispatchEvent(new KeyboardEvent('keydown', { key, bubbles: true }));
  }

  function pollGamepad() {
    const gamepads = navigator.getGamepads?.() ?? [];
    const gp = [...gamepads].find(Boolean);
    if (gp) {
      const map = [
        { btn: 0,  key: 'Enter' },
        { btn: 1,  key: 'Escape' },
        { btn: 2,  key: 'Square' },
        { btn: 4,  key: 'L1' },
        { btn: 5,  key: 'R1' },
        { btn: 12, key: 'ArrowUp' },
        { btn: 13, key: 'ArrowDown' },
        { btn: 14, key: 'ArrowLeft' },
        { btn: 15, key: 'ArrowRight' },
      ];
      map.forEach(({ btn, key }) => {
        const pressed = gp.buttons[btn]?.pressed;
        const wasPrev = prev.buttons[btn];
        if (pressed && !wasPrev) {
          fireKey(key);
          heldTimers[btn] = setTimeout(function repeat() {
            fireKey(key);
            heldTimers[btn] = setTimeout(repeat, HELD_REPEAT);
          }, HELD_DELAY);
        }
        if (!pressed && wasPrev) clearTimeout(heldTimers[btn]);
        prev.buttons[btn] = pressed;
      });
      const ax = gp.axes[0] ?? 0;
      if (Math.abs(ax) > 0.5) {
        // handled by buttons[14/15] on most pads
      }
    }
    requestAnimationFrame(pollGamepad);
  }

  window.addEventListener('gamepadconnected', (e) => {
    updateControllerStatus(true, e.gamepad.id);
    requestAnimationFrame(pollGamepad);
  });
  window.addEventListener('gamepaddisconnected', () => updateControllerStatus(false));
}

function updateControllerStatus(connected, id = '') {
  const item = document.querySelector('.status-item.controller');
  const text = document.querySelector('.status-controller-text');
  if (!item || !text) return;
  item.classList.toggle('disconnected', !connected);
  text.textContent = connected ? (id.trim() || 'Controle conectado') : 'Sem controle';
}

function init() {
  document.getElementById('root').innerHTML = `
    <header class="top-bar">
      <div class="top-logo">
        <img src="/assets/psone-pro.svg" alt="PS one Pro">
      </div>
      <nav class="top-nav">
        <span class="nav-item active" data-screen="home"><span class="msr">sports_esports</span>Games</span>
        <span class="nav-item" data-screen="stats"><span class="msr">bar_chart</span>Stats</span>
        <span class="nav-item" data-screen="settings"><span class="msr">settings</span>Settings</span>
      </nav>
      <span class="top-clock" id="clock"></span>
    </header>

    <main id="main"></main>

    <footer class="bottom-bar">
      <div class="bottom-hints" id="bottom-hints"></div>
      <div class="bottom-status">
        <span class="status-item">
          <span class="msr">wifi</span>
          ${API_HOST}
        </span>
        <span class="status-item controller disconnected">
          <span class="msr">stadia_controller</span>
          <span class="status-controller-text">Sem controle</span>
        </span>
      </div>
    </footer>`;

  document.querySelectorAll('.nav-item').forEach(el => {
    el.addEventListener('click', () => {
      const screen = el.dataset.screen;
      if (screen === 'settings') return;
      navigate(screen);
    });
  });

  updateClock();
  setInterval(updateClock, 1000);
  initGamepad();
  initPageSwitcher();
  navigate('home');
}

init();
