import { fetchGames } from '../data/api.js';
import { fmtTime, cardGradient, platformLogoImg } from '../utils.js';

const SORT_MODES = [
  { key: 'top',    label: 'Mais jogado', cmp: (a, b) => (b.total_seconds ?? 0) - (a.total_seconds ?? 0) },
  { key: 'recent', label: 'Recente',     cmp: (a, b) => new Date(b.last_played ?? 0) - new Date(a.last_played ?? 0) },
  { key: 'az',     label: 'A-Z',         cmp: (a, b) => a.display_name.localeCompare(b.display_name) },
];

function computeCols(container) {
  const cards = container.querySelectorAll('.lib-card');
  if (cards.length === 0) return 1;
  const firstTop = cards[0].offsetTop;
  let cols = 0;
  for (const card of cards) {
    if (card.offsetTop === firstTop) cols++;
    else break;
  }
  return cols || 1;
}

export function mount(container, navigate, params = {}) {
  let selectedIndex = params.selectedIndex ?? 0;
  let platformFilter = params.platformFilter ?? 'all';
  let sortIndex = 0;
  let focus = 'grid';
  let railIndex = 0;
  let onKeyHandler = null;
  let cancelled = false;

  container.innerHTML = '<div style="padding:40px;color:var(--text-muted);text-align:center">Carregando...</div>';

  fetchGames()
    .then(allGames => {
      if (cancelled) return;

      const platforms = ['all', ...new Set(allGames.map(g => g.platform).filter(Boolean))];
      // Rail rows: one per platform filter, then the sort toggle at the end.
      const railCount = platforms.length + 1;

      function filtered() {
        const base = platformFilter === 'all' ? allGames : allGames.filter(g => g.platform === platformFilter);
        return [...base].sort(SORT_MODES[sortIndex].cmp);
      }

      function refreshGrid(games) {
        container.querySelector('.library-grid').innerHTML = gridHTML(games, focus === 'grid' ? selectedIndex : -1);
        const selectedCard = container.querySelector('.lib-card.selected');
        if (selectedCard) {
          const cols = computeCols(container);
          if (selectedIndex < cols) {
            container.querySelector('.library-main').scrollTo({ top: 0, behavior: 'smooth' });
          } else {
            selectedCard.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
          }
        }
        attachCardListeners();
      }

      function refreshRail() {
        container.querySelectorAll('.side-rail .rail-item').forEach((el, i) => {
          const isSort = i === railCount - 1;
          el.classList.toggle('active', !isSort && platforms[i] === platformFilter);
          el.classList.toggle('focused', focus === 'rail' && i === railIndex);
          if (isSort) el.textContent = `Ordenar: ${SORT_MODES[sortIndex].label}`;
        });
      }

      function setFilter(platform) {
        platformFilter = platform;
        selectedIndex = 0;
        refreshRail();
        refreshGrid(filtered());
      }

      function cycleSort() {
        sortIndex = (sortIndex + 1) % SORT_MODES.length;
        selectedIndex = 0;
        refreshRail();
        refreshGrid(filtered());
      }

      function attachCardListeners() {
        container.querySelectorAll('.lib-card').forEach((card, i) => {
          card.addEventListener('click', () => navigate('detail', { gameId: Number(card.dataset.id), from: 'library', libraryIndex: i, libraryFilter: platformFilter }));
        });
      }

      container.innerHTML = buildHTML(platforms, filtered(), selectedIndex, platformFilter, sortIndex);
      container.querySelectorAll('.side-rail .rail-item').forEach((el, i) => {
        el.addEventListener('click', () => {
          if (i === railCount - 1) cycleSort();
          else setFilter(platforms[i]);
        });
      });
      attachCardListeners();

      if (selectedIndex > 0) {
        requestAnimationFrame(() => {
          container.querySelector('.lib-card.selected')?.scrollIntoView({ block: 'center' });
        });
      }

      function onKey(e) {
        if (focus === 'rail') {
          switch (e.key) {
            case 'ArrowUp':
              if (railIndex > 0) { railIndex--; refreshRail(); }
              break;
            case 'ArrowDown':
              if (railIndex < railCount - 1) { railIndex++; refreshRail(); }
              break;
            case 'Enter':
              if (railIndex === railCount - 1) cycleSort();
              else setFilter(platforms[railIndex]);
              break;
            case 'ArrowRight':
              focus = 'grid';
              refreshRail();
              refreshGrid(filtered());
              break;
            case 'Escape':
              navigate('home');
              break;
          }
          return;
        }

        // focus === 'grid'
        const games = filtered();
        switch (e.key) {
          case 'L1': {
            const idx = platforms.indexOf(platformFilter);
            setFilter(platforms[(idx - 1 + platforms.length) % platforms.length]);
            break;
          }
          case 'R1': {
            const idx = platforms.indexOf(platformFilter);
            setFilter(platforms[(idx + 1) % platforms.length]);
            break;
          }
          case 'ArrowRight':
            if (selectedIndex < games.length - 1) { selectedIndex++; refreshGrid(games); }
            break;
          case 'ArrowLeft': {
            const cols = computeCols(container);
            if (selectedIndex % cols === 0) {
              focus = 'rail';
              railIndex = platforms.indexOf(platformFilter);
              refreshRail();
              refreshGrid(games);
            } else {
              selectedIndex--;
              refreshGrid(games);
            }
            break;
          }
          case 'ArrowDown': {
            const cols = computeCols(container);
            if (selectedIndex + cols < games.length) { selectedIndex += cols; refreshGrid(games); }
            break;
          }
          case 'ArrowUp': {
            const cols = computeCols(container);
            if (selectedIndex - cols >= 0) { selectedIndex -= cols; refreshGrid(games); }
            break;
          }
          case 'Enter':
            navigate('detail', { gameId: games[selectedIndex].id, from: 'library', libraryIndex: selectedIndex, libraryFilter: platformFilter });
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

function buildHTML(platforms, games, selectedIndex, platformFilter, sortIndex) {
  const railItems = platforms.map(p => {
    const label = p === 'all'
      ? '<span class="msr">apps</span>Todos'
      : platformLogoImg(p, 'rail-platform-logo');
    return `<div class="rail-item${p === platformFilter ? ' active' : ''}" data-platform="${p}">${label}</div>`;
  }).join('');

  const totalSeconds = games.reduce((a, g) => a + (g.total_seconds ?? 0), 0);

  return `<div class="screen-library">
    <aside class="side-rail">
      ${railItems}
      <div class="rail-separator"></div>
      <div class="rail-item rail-sort"><span class="msr">swap_vert</span>Ordenar: ${SORT_MODES[sortIndex].label}</div>
    </aside>
    <div class="library-main">
      <div class="library-header">
        <h1>Biblioteca</h1>
        <span class="library-header-meta">${games.length} JOGOS · ${fmtTime(totalSeconds)} JOGADAS</span>
      </div>
      <div class="library-grid">${gridHTML(games, selectedIndex)}</div>
    </div>
  </div>`;
}

function gridHTML(games, selectedIndex) {
  return games.map((g, i) => {
    const cover = g.cover_url
      ? `<img src="${g.cover_url}" alt="" class="cover-img">`
      : `<div class="cover-gradient" style="background:${cardGradient(g.display_name)}"></div>`;
    return `<div class="lib-card${i === selectedIndex ? ' selected' : ''}" data-id="${g.id}">
      <div class="lib-card-cover">
        ${cover}
        <div class="card-title-overlay"><span>${g.display_name}</span></div>
      </div>
      <div class="lib-card-name">${g.display_name}</div>
      <div class="lib-card-time"><span class="msr">schedule</span>${fmtTime(g.total_seconds)}</div>
    </div>`;
  }).join('');
}
