import { fetchGames } from '../data/api.js';
import { fmtTime, cardGradient, getPlatformLogo } from '../utils.js';

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
  let focus = 'grid';
  let filterIndex = 0;
  let onKeyHandler = null;
  let cancelled = false;

  container.innerHTML = '<div style="padding:40px;color:var(--text-muted);text-align:center">Carregando...</div>';

  fetchGames()
    .then(allGames => {
      if (cancelled) return;

      const platforms = ['all', ...new Set(allGames.map(g => g.platform).filter(Boolean))];

      function filtered() {
        if (platformFilter === 'all') return allGames;
        return allGames.filter(g => g.platform === platformFilter);
      }

      function refreshGrid(games) {
        container.querySelector('.library-grid').innerHTML = gridHTML(games, selectedIndex);
        const selectedCard = container.querySelector('.lib-card.selected');
        if (selectedCard) {
          const cols = computeCols(container);
          if (selectedIndex < cols) {
            container.querySelector('.screen-library').scrollTo({ top: 0, behavior: 'smooth' });
          } else {
            selectedCard.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
          }
        }
        container.querySelectorAll('.lib-card').forEach((card, i) => {
          card.addEventListener('click', () => navigate('detail', { gameId: Number(card.dataset.id), from: 'library', libraryIndex: i, libraryFilter: platformFilter }));
        });
      }

      function refreshFilters() {
        container.querySelectorAll('.filter-chip').forEach((c, i) => {
          c.classList.toggle('active', platforms[i] === platformFilter);
          c.classList.toggle('focused', focus === 'filters' && i === filterIndex);
        });
      }

      function setFilter(platform) {
        platformFilter = platform;
        filterIndex = platforms.indexOf(platform);
        selectedIndex = 0;
        refreshFilters();
        refreshGrid(filtered());
      }

      function attachChipListeners() {
        container.querySelectorAll('.filter-chip').forEach(chip => {
          chip.addEventListener('click', () => setFilter(chip.dataset.platform));
        });
        container.querySelectorAll('.lib-card').forEach((card, i) => {
          card.addEventListener('click', () => navigate('detail', { gameId: Number(card.dataset.id), from: 'library', libraryIndex: i, libraryFilter: platformFilter }));
        });
      }

      container.innerHTML = buildHTML(allGames, filtered(), selectedIndex, platformFilter);
      attachChipListeners();

      if (selectedIndex > 0) {
        requestAnimationFrame(() => {
          container.querySelector('.lib-card.selected')?.scrollIntoView({ block: 'center' });
        });
      }

      function onKey(e) {
        if (focus === 'filters') {
          switch (e.key) {
            case 'ArrowLeft':
              filterIndex = Math.max(0, filterIndex - 1);
              refreshFilters();
              break;
            case 'ArrowRight':
              filterIndex = Math.min(platforms.length - 1, filterIndex + 1);
              refreshFilters();
              break;
            case 'Enter':
              setFilter(platforms[filterIndex]);
              focus = 'grid';
              refreshFilters();
              break;
            case 'ArrowDown':
              focus = 'grid';
              refreshFilters();
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
          case 'ArrowLeft':
            if (selectedIndex > 0) { selectedIndex--; refreshGrid(games); }
            break;
          case 'ArrowDown': {
            const cols = computeCols(container);
            if (selectedIndex + cols < games.length) { selectedIndex += cols; refreshGrid(games); }
            break;
          }
          case 'ArrowUp': {
            const cols = computeCols(container);
            if (selectedIndex - cols >= 0) { selectedIndex -= cols; refreshGrid(games); }
            else {
              focus = 'filters';
              filterIndex = platforms.indexOf(platformFilter);
              refreshFilters();
              container.querySelector('.screen-library')?.scrollTo({ top: 0, behavior: 'smooth' });
            }
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

function buildHTML(allGames, games, selectedIndex, platformFilter) {
  const platforms = ['all', ...new Set(allGames.map(g => g.platform).filter(Boolean))];
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
    const cover = g.cover_url
      ? `<img src="${g.cover_url}" alt="" class="cover-img">`
      : `<div class="cover-gradient" style="background:${cardGradient(g.display_name)};width:100%;height:100%;display:flex;align-items:flex-end;padding:10px">
           <span class="card-name-fb" style="font-size:0.65rem">${g.display_name.toUpperCase()}</span>
         </div>`;
    return `<div class="lib-card${i === selectedIndex ? ' selected' : ''}" data-id="${g.id}">
      <div class="lib-card-cover">
        ${cover}
      </div>
      <div class="lib-card-name">${g.display_name}</div>
      <div class="lib-card-time">${fmtTime(g.total_seconds)}</div>
    </div>`;
  }).join('');
}
