import { mount as mountHome }    from './screens/home.js';
import { mount as mountDetail }  from './screens/detail.js';
import { mount as mountLibrary } from './screens/library.js';
import { mount as mountStats }   from './screens/stats.js';

const SCREENS = { home: mountHome, detail: mountDetail, library: mountLibrary, stats: mountStats };
const NAV_SCREENS = ['home', 'stats'];

let currentCleanup = null;

export function navigate(screen, params = {}) {
  if (currentCleanup) { currentCleanup(); currentCleanup = null; }
  const main = document.getElementById('main');
  currentCleanup = SCREENS[screen](main, navigate, params) ?? null;
  updateNav(screen);
}

function updateNav(screen) {
  document.querySelectorAll('.nav-item').forEach(el => {
    el.classList.toggle('active', el.dataset.screen === screen);
  });
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

  window.addEventListener('gamepadconnected', () => {
    updateControllerStatus(true);
    requestAnimationFrame(pollGamepad);
  });
  window.addEventListener('gamepaddisconnected', () => updateControllerStatus(false));
}

function updateControllerStatus(connected) {
  const dot  = document.querySelector('.status-dot.controller');
  const text = document.querySelector('.status-controller-text');
  if (dot)  dot.style.opacity  = connected ? '1' : '0.3';
  if (text) text.textContent   = connected ? 'Controle conectado' : 'Sem controle';
}

function init() {
  document.getElementById('root').innerHTML = `
    <header class="top-bar">
      <div class="top-logo">
        <img src="/assets/psone-pro.svg" alt="PS one Pro">
      </div>
      <nav class="top-nav">
        <span class="nav-item active" data-screen="home">Games</span>
        <span class="nav-item" data-screen="stats">Stats</span>
        <span class="nav-item" data-screen="settings">Settings</span>
      </nav>
      <span class="top-clock" id="clock"></span>
    </header>

    <main id="main"></main>

    <footer class="bottom-bar">
      <div class="bottom-hints">
        <span class="hint"><span class="hint-btn">✕</span> Selecionar</span>
        <span class="hint"><span class="hint-btn">○</span> Voltar</span>
        <span class="hint"><span class="hint-btn">□</span> Filtrar</span>
        <span class="hint"><span class="hint-btn">△</span> Opções</span>
      </div>
      <div class="bottom-status">
        <span class="status-item">
          <span class="status-dot network"></span>
          Rede local
        </span>
        <span class="status-item">
          <span class="status-dot controller"></span>
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
  navigate('home');
}

init();
