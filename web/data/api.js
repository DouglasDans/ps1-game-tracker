const API_BASE = 'http://192.168.1.150:9876';

async function apiFetch(path) {
  const res = await fetch(`${API_BASE}${path}`);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

export const fetchGames         = ()  => apiFetch('/games');
export const fetchActiveSession = ()  => apiFetch('/sessions/active');
export const fetchStats         = ()  => apiFetch('/stats/summary');
export const fetchGameDetail    = (id) => apiFetch(`/games/${id}`);
