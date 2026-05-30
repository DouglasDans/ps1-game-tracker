export const ACTIVE = {
  id: 1,
  game_id: 1,
  source: 'duckstation',
  started_at: new Date(Date.now() - 83 * 60 * 1000).toISOString(),
  display_name: 'Crash Team Racing',
};

export const GAMES = [
  { id: 1, display_name: 'Crash Team Racing',  platform: 'PS1', cover_url: null, session_count: 8, total_seconds: 45600, last_played: '2026-05-30 20:00:00', last_source: 'duckstation' },
  { id: 4, display_name: 'Gran Turismo 2',      platform: 'PS2', cover_url: null, session_count: 5, total_seconds: 32400, last_played: '2026-05-28 19:30:00', last_source: 'samba' },
  { id: 2, display_name: 'Metal Gear Solid',    platform: 'PS1', cover_url: null, session_count: 3, total_seconds: 29700, last_played: '2026-05-28 20:15:00', last_source: 'duckstation' },
  { id: 5, display_name: 'Gran Turismo',        platform: 'PSP', cover_url: null, session_count: 4, total_seconds: 21600, last_played: '2026-05-26 18:00:00', last_source: 'ppsspp' },
  { id: 3, display_name: 'Silent Hill',         platform: 'PS1', cover_url: null, session_count: 2, total_seconds: 18000, last_played: '2026-05-25 21:00:00', last_source: 'duckstation' },
  { id: 6, display_name: 'Castlevania: SotN',   platform: 'PS1', cover_url: null, session_count: 1, total_seconds: 14400, last_played: '2026-05-20 20:00:00', last_source: 'retroarch' },
  { id: 7, display_name: 'Tekken 3',            platform: 'PS1', cover_url: null, session_count: 2, total_seconds: 7200,  last_played: '2026-05-18 20:00:00', last_source: 'duckstation' },
  { id: 8, display_name: 'Final Fantasy VII',   platform: 'PS1', cover_url: null, session_count: 1, total_seconds: 3600,  last_played: '2026-05-15 20:00:00', last_source: 'duckstation' },
];

export const GAME_DETAIL = {
  1: { id: 1, display_name: 'Crash Team Racing', platform: 'PS1', cover_url: null, genre: 'Racing', release_year: 1999, total_seconds: 45600, session_count: 8, last_played: '2026-05-30 20:00:00', sessions: [
    { id: 8, started_at: '2026-05-30 20:00:00', ended_at: '2026-05-30 21:23:00', duration_s: 4980,  source: 'duckstation' },
    { id: 6, started_at: '2026-05-28 14:00:00', ended_at: '2026-05-28 14:45:00', duration_s: 2700,  source: 'duckstation' },
    { id: 4, started_at: '2026-05-26 20:00:00', ended_at: '2026-05-26 22:10:00', duration_s: 7800,  source: 'duckstation' },
    { id: 2, started_at: '2026-05-24 19:00:00', ended_at: '2026-05-24 20:30:00', duration_s: 5400,  source: 'duckstation' },
    { id: 1, started_at: '2026-05-23 21:00:00', ended_at: '2026-05-23 22:00:00', duration_s: 3600,  source: 'duckstation' },
  ]},
  2: { id: 2, display_name: 'Metal Gear Solid', platform: 'PS1', cover_url: null, genre: 'Action-Adventure', release_year: 1998, total_seconds: 29700, session_count: 3, last_played: '2026-05-28 20:15:00', sessions: [
    { id: 7, started_at: '2026-05-28 20:15:00', ended_at: '2026-05-28 22:15:00', duration_s: 7200,  source: 'duckstation' },
    { id: 5, started_at: '2026-05-25 19:00:00', ended_at: '2026-05-25 21:45:00', duration_s: 9900,  source: 'duckstation' },
    { id: 3, started_at: '2026-05-23 19:00:00', ended_at: '2026-05-23 22:25:00', duration_s: 12600, source: 'duckstation' },
  ]},
  3: { id: 3, display_name: 'Silent Hill', platform: 'PS1', cover_url: null, genre: 'Survival Horror', release_year: 1999, total_seconds: 18000, session_count: 2, last_played: '2026-05-25 21:00:00', sessions: [
    { id: 10, started_at: '2026-05-25 21:00:00', ended_at: '2026-05-25 22:00:00', duration_s: 3600,  source: 'duckstation' },
    { id: 9,  started_at: '2026-05-22 20:00:00', ended_at: '2026-05-23 00:00:00', duration_s: 14400, source: 'duckstation' },
  ]},
  4: { id: 4, display_name: 'Gran Turismo 2', platform: 'PS2', cover_url: null, genre: 'Racing', release_year: 2000, total_seconds: 32400, session_count: 5, last_played: '2026-05-28 19:30:00', sessions: [
    { id: 15, started_at: '2026-05-28 19:30:00', ended_at: '2026-05-28 22:10:00', duration_s: 9600, source: 'samba' },
    { id: 13, started_at: '2026-05-26 18:00:00', ended_at: '2026-05-26 20:00:00', duration_s: 7200, source: 'samba' },
    { id: 11, started_at: '2026-05-23 19:00:00', ended_at: '2026-05-23 21:00:00', duration_s: 7200, source: 'samba' },
  ]},
  5: { id: 5, display_name: 'Gran Turismo', platform: 'PSP', cover_url: null, genre: 'Racing', release_year: 2009, total_seconds: 21600, session_count: 4, last_played: '2026-05-26 18:00:00', sessions: [
    { id: 14, started_at: '2026-05-26 18:00:00', ended_at: '2026-05-26 19:30:00', duration_s: 5400, source: 'ppsspp' },
    { id: 12, started_at: '2026-05-24 18:00:00', ended_at: '2026-05-24 19:30:00', duration_s: 5400, source: 'ppsspp' },
  ]},
  6: { id: 6, display_name: 'Castlevania: SotN', platform: 'PS1', cover_url: null, genre: 'Action-RPG', release_year: 1997, total_seconds: 14400, session_count: 1, last_played: '2026-05-20 20:00:00', sessions: [
    { id: 16, started_at: '2026-05-20 20:00:00', ended_at: '2026-05-21 00:00:00', duration_s: 14400, source: 'retroarch' },
  ]},
  7: { id: 7, display_name: 'Tekken 3', platform: 'PS1', cover_url: null, genre: 'Fighting', release_year: 1998, total_seconds: 7200, session_count: 2, last_played: '2026-05-18 20:00:00', sessions: [
    { id: 18, started_at: '2026-05-18 20:00:00', ended_at: '2026-05-18 21:00:00', duration_s: 3600, source: 'duckstation' },
    { id: 17, started_at: '2026-05-16 20:00:00', ended_at: '2026-05-16 21:00:00', duration_s: 3600, source: 'duckstation' },
  ]},
  8: { id: 8, display_name: 'Final Fantasy VII', platform: 'PS1', cover_url: null, genre: 'RPG', release_year: 1997, total_seconds: 3600, session_count: 1, last_played: '2026-05-15 20:00:00', sessions: [
    { id: 19, started_at: '2026-05-15 20:00:00', ended_at: '2026-05-15 21:00:00', duration_s: 3600, source: 'duckstation' },
  ]},
};

export const STATS = {
  total_seconds: 172800,
  total_games: 8,
  most_played: { id: 1, display_name: 'Crash Team Racing', total_seconds: 45600 },
  longest_session: { duration_s: 14400, started_at: '2026-05-20 20:00:00', display_name: 'Castlevania: SotN' },
  by_platform: [
    { platform: 'PS1', total_seconds: 118800, pct: 69 },
    { platform: 'PS2', total_seconds: 32400,  pct: 19 },
    { platform: 'PSP', total_seconds: 21600,  pct: 13 },
  ],
};
