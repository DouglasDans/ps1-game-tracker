// Em produção o front é servido pelo próprio daemon → same-origin, funciona
// com qualquer IP. Em dev (front local via http.server) aponta para o Pi.
const DEV_HOSTS = ['localhost', '127.0.0.1'];
const API_BASE = DEV_HOSTS.includes(location.hostname) ? 'http://192.168.1.150:9876' : '';

export const API_HOST = API_BASE ? new URL(API_BASE).hostname : location.hostname;

async function apiFetch(path) {
  const res = await fetch(`${API_BASE}${path}`);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

export const fetchGames         = ()  => apiFetch('/games');
export const fetchActiveSession = ()  => apiFetch('/sessions/active');
export const fetchStats         = ()  => apiFetch('/stats/summary');
export const fetchActivity      = ()  => apiFetch('/stats/activity');
export const fetchGameDetail    = (id) => apiFetch(`/games/${id}`);
export const fetchLongestSessions = (limit = 8) => apiFetch(`/stats/longest-sessions?limit=${limit}`);
