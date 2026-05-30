import { fetchGames } from '../data/api.js';
import { fmtTime, cardGradient, PLATFORM_LOGO } from '../utils.js';

const COLS = Math.floor((1920 - 128) / (130 + 14));

export function mount(container, navigate, params = {}) {
  let selectedIndex = 0;
  let platformFilter = 'all';
  let onKeyHandler = null;
  let cancelled = false;

  container.innerHTML = '<div style="padding:40px;color:var(--text-muted);text-align:center">Carregando...</div>';

  fetchGames()
    .then(allGames => {
      if (cancelled) return;

      function filtered() {
        if (platformFilter === 'all') return allGames;
        return allGames.filter(g => g.platform === platformFilter);
      }

      function refreshGrid(games) {
        container.querySelector('.library-grid').innerHTML = gridHTML(games, selectedIndex);
        container.querySelectorAll('.lib-card').forEach(card => {
          card.addEventListener('click', () => navigate('detail', { gameId: Number(card.dataset.id) }));
        });
      }

      function attachChipListeners() {
        container.querySelectorAll('.filter-chip').forEach(chip => {
          chip.addEventListener('click', () => {
            platformFilter = chip.dataset.platform;
            selectedIndex = 0;
            refreshGrid(filtered());
            container.querySelectorAll('.filter-chip').forEach(c =>
              c.classList.toggle('active', c.dataset.platform === platformFilter)
            );
          });
        });
        container.querySelectorAll('.lib-card').forEach(card => {
          card.addEventListener('click', () => navigate('detail', { gameId: Number(card.dataset.id) }));
        });
      }

      container.innerHTML = buildHTML(allGames, filtered(), selectedIndex, platformFilter);
      attachChipListeners();

      function onKey(e) {
        const games = filtered();
        switch (e.key) {
          case 'ArrowRight':
            if (selectedIndex < games.length - 1) { selectedIndex++; refreshGrid(games); }
            break;
          case 'ArrowLeft':
            if (selectedIndex > 0) { selectedIndex--; refreshGrid(games); }
            break;
          case 'ArrowDown':
            if (selectedIndex + COLS < games.length) { selectedIndex += COLS; refreshGrid(games); }
            break;
          case 'ArrowUp':
            if (selectedIndex - COLS >= 0) { selectedIndex -= COLS; refreshGrid(games); }
            break;
          case 'Enter':
            navigate('detail', { gameId: games[selectedIndex].id });
            break;
          case 'Escape':
            navigate('home');
            break;
        }
      }

      onKeyHandler = onKey;
      document.addEventListener('keydown', onKey);
    })
    .catch(err => {
      if (cancelled) return;
      container.innerHTML = `<div style="padding:40px;color:var(--text-muted);text-align:center">Erro ao carregar biblioteca.<br><small>${err.message}</small></div>`;
    });

  return () => {
    cancelled = true;
    if (onKeyHandler) document.removeEventListener('keydown', onKeyHandler);
  };
}

function buildHTML(allGames, games, selectedIndex, platformFilter) {
  const platforms = ['all', ...new Set(allGames.map(g => g.platform))];
  const chips = platforms.map(p => {
    const label = p === 'all' ? 'Todos' : p;
    return `<span class="filter-chip${p === platformFilter ? ' active' : ''}" data-platform="${p}">${label}</span>`;
  }).join('');

  return `<div class="screen-library">
    <div class="library-header">
      <span class="library-title">Biblioteca</span>
      ${chips}
    </div>
    <div class="library-grid">${gridHTML(games, selectedIndex)}</div>
  </div>`;
}

function gridHTML(games, selectedIndex) {
  return games.map((g, i) => {
    const logo = PLATFORM_LOGO[g.platform];
    const cover = g.cover_url
      ? `<img src="${g.cover_url}" alt="" class="cover-img">`
      : `<div class="cover-gradient" style="background:${cardGradient(g.display_name)};width:100%;height:100%;display:flex;align-items:flex-end;padding:10px">
           <span class="card-name-fb" style="font-size:0.65rem">${g.display_name.toUpperCase()}</span>
         </div>`;
    return `<div class="lib-card${i === selectedIndex ? ' selected' : ''}" data-id="${g.id}">
      <div class="lib-card-cover">
        ${cover}
        ${logo ? `<div class="card-platform-badge"><img src="${logo}" alt="${g.platform}"></div>` : ''}
      </div>
      <div class="lib-card-name">${g.display_name}</div>
      <div class="lib-card-time">${fmtTime(g.total_seconds)}</div>
    </div>`;
  }).join('');
}
