# PS1 Game Tracker

> Centro de informações do PS1 Pro: daemon + interface única controlada por controle, exibida na TV (1080p). Rastreia sessões de jogo automaticamente (estilo Steam), agrega estatísticas e, no futuro, expõe informações do próprio console. Dados locais em SQLite com espelho no Notion.

Documentação completa do escopo: https://www.notion.so/PS1-Pro-Session-Tracker-Escopo-do-Projeto-36327b83275c80f797e0dfd09e479892
Acesso via MCP: `mcp__claude_ai_Notion__notion-fetch` com a URL acima.

---

## Visão do produto

Tudo numa interface única, navegada 100% por controle, na TV. Dois pilares, nesta ordem de prioridade:

1. **Games** — informações e listas de jogos, horas por jogo, trackeamento completo de sessões, e o máximo de estatísticas qualitativas que os dados permitirem. A integração com **RetroAchievements (Fase 6) é prioridade** para o usuário.
2. **Console** — informações do sistema do PS1 Pro: armazenamento, RAM, uso de CPU/GPU e configurações do sistema (escopo exato ainda a definir).

## O que é o PS1 Pro

Mini console retro construído pelo usuário: um **Raspberry Pi 5** (Debian 13 Trixie, aarch64) montado num case de **PlayStation 1 original (SCPH-9001)**, que boota direto num launcher — sem desktop/X11 — e é operado inteiramente por controle (DualShock 3 via Bluetooth).

- **PS1 OSD Launcher** (`~/ps1-osd-laucher` no Pi): launcher Python/pygame que imita o BIOS do PS1; serviço systemd, sobe no boot.
- **Emuladores**: DuckStation e SwanStation/PCSX-ReARMed (PS1), PPSSPP (PSP), Flycast (Dreamcast), RetroArch (multi) + PS2 real via OPL/SMB numa rede ethernet isolada (192.168.0.0/24).
- **Rede**: WiFi com IP estático `192.168.1.150`.
- **Armazenamento**: SD para o OS + pendrive USB 116GB NTFS para as ROMs (`/mnt/usb-flash`).
- **Extras**: YouTube TV via Chromium kiosk (Wayland/cage), backup de saves via rclone → Google Drive.
- **Este projeto** é a camada de tracking + dashboard desse ecossistema.

---

## Stack

| Camada         | Tecnologia                                   |
| -------------- | -------------------------------------------- |
| Daemon + API   | Python 3.11+ / FastAPI / asyncio             |
| Banco de dados | SQLite 3 (stdlib `sqlite3`)                  |
| Enriquecimento | ScreenScraper API / IGDB API (Fase 3)        |
| Sync           | Notion API / `notion-client` (Fase 5)        |
| Frontend       | HTML5 / CSS3 / Vanilla JS                    |
| Serviço        | systemd (system service, `User=douglasdans`) |
| Browser        | Chromium kiosk via `cage` (Wayland)          |

---

## Comandos essenciais

```bash
# Ambiente de desenvolvimento
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt

# Servidor de desenvolvimento
uvicorn daemon.main:app --reload --port 8080

# Frontend local contra dados de produção (workflow preferido para mexer no web/)
# O web/data/api.js aponta hardcoded para http://192.168.1.150:9876 (Pi de produção)
# e o daemon tem CORS liberado — basta servir a pasta web/ estaticamente:
python3 -m http.server 8000 -d web
# Abrir http://localhost:8000 — alterações no front aparecem no reload, dados reais do Pi

# Testes (obrigatório antes de qualquer commit)
pytest

# Deploy no Pi
./install.sh
sudo systemctl enable ps1-tracker && sudo systemctl start ps1-tracker

# Status / logs do serviço
sudo systemctl status ps1-tracker
journalctl -u ps1-tracker -f
```

---

## Estrutura de pastas

```
ps1-game-tracker/
├── daemon/
│   ├── watchers/
│   │   ├── procfs.py        # DuckStation + PPSSPP via /proc/PID/fd/ [FASE 1]
│   │   ├── samba.py         # PS2 via OPL / smbstatus [FASE 2]
│   │   └── lrtl.py          # RetroArch .lrtl import [FASE 2]
│   ├── enricher.py          # ScreenScraper → IGDB → regex [FASE 3]
│   ├── session_manager.py   # open/close/heartbeat de sessão [FASE 1]
│   ├── db.py                # schema SQLite + funções de acesso [FASE 1]
│   └── main.py              # FastAPI app + threads [FASE 1]
├── sync/
│   └── notion_sync.py       # Notion sync periódico [FASE 5]
├── web/
│   ├── index.html           # shell mínimo: carrega app.js como módulo
│   ├── app.js               # roteador de telas + top/bottom bar + Gamepad API
│   ├── utils.js             # formatação (tempo/data), logos de plataforma, gradientes
│   ├── style.css            # dark theme 10-foot p/ TV 1080p (contraste AA, tipografia grande)
│   ├── screens/
│   │   ├── home.js          # carrossel de recentes + hero + seção de stats globais
│   │   ├── detail.js        # detalhe do jogo: stats estendidas + histórico de sessões
│   │   └── library.js       # grid completo com filtros por plataforma (L1/R1)
│   ├── data/
│   │   ├── api.js           # fetch da API (same-origin em prod; Pi em dev local)
│   │   └── mock.js
│   └── assets/              # logos de plataforma (ps1/ps2/psp/dc/sega)
├── tests/
│   ├── conftest.py
│   ├── test_db.py
│   ├── test_procfs.py
│   └── test_session_manager.py
├── systemd/
│   └── ps1-tracker.service  # gerado pelo install.sh
├── install.sh
├── config.toml              # não versionado (gitignored)
├── config.toml.example      # template versionado
├── pyproject.toml           # pytest config
└── requirements.txt / requirements-dev.txt
```

---

## Padrões de código

- **Tipagem**: type hints obrigatórios em todas as funções públicas
- **Conexão SQLite**: sempre injetada como parâmetro (`conn: sqlite3.Connection`) — nunca singleton global
- **Threads**: polling loop em `threading.Thread(daemon=True)`, parado via `threading.Event`
- **Config**: lida uma vez no startup via `tomllib` (Python 3.11+ stdlib) e passada como `dict`
- **Imports**: stdlib → terceiros → internos, separados por linha em branco

---

## Schema do banco de dados

```
┌─────────────────────────────────────────────────────────┐
│ games                                                   │
├─────────────────────────────────────────────────────────┤
│ id                    INTEGER PK                        │
│ file_path             TEXT UNIQUE  ← chave natural      │
│ file_md5              TEXT                              │
│ display_name          TEXT                              │
│ canonical_name        TEXT  ← normalizado (sem região)  │
│ platform              TEXT  ← PS1 / PS2 / PSP / …      │
│ cover_url             TEXT                              │
│ genre                 TEXT                              │
│ release_year          INTEGER                           │
│ enriched_at           DATETIME                          │
│ notion_page_id        TEXT                              │
│ igdb_id               INTEGER  ← mesmo id p/ CTTR PS2   │
│ screenscraper_id      INTEGER    e CTTR PSP; agrupa UI   │
│ ra_game_id            INTEGER  ← diferente por platform │
│ enrichment_retries    INTEGER  ← falhas acumuladas;      │
│                                   desiste em >= 3        │
└────────────────────────┬────────────────────────────────┘
                         │ 1
                         │
                         │ N
┌────────────────────────▼────────────────────────────────┐
│ sessions                                                │
├─────────────────────────────────────────────────────────┤
│ id               INTEGER PK                             │
│ game_id          INTEGER FK → games.id                  │
│ source           TEXT  ← duckstation / ppsspp / samba / │
│                              retroarch                  │
│ started_at       DATETIME                               │
│ ended_at         DATETIME                               │
│ heartbeat_at     DATETIME                               │
│ duration_s       INTEGER                                │
│ ended_abnormally INTEGER  ← 0 / 1                       │
│ synced_to_notion INTEGER  ← 0 / 1                       │
└─────────────────────────────────────────────────────────┘

VIEW playtime_summary
  Agrega sessions por canonical_name (ou file_path).
  Expõe: id, file_path, display_name, platform, cover_url,
         session_count, total_seconds, last_played.
  Usada pelo endpoint GET /games.
```

---

## Arquitetura — decisões-chave

### Por que procfs para DuckStation?

DuckStation tem `playtime.dat` interno, mas armazena apenas tempo total acumulado + timestamp do último acesso — sem granularidade de sessão. A única forma de capturar sessões individuais (start/end times) é via `/proc/PID/fd/`, detectando o file descriptor da ROM aberta.

### Por que SQLite como fonte da verdade?

Zero latência, zero dependência de rede. Notion é espelho periódico para acesso remoto — falha de rede não quebra o tracking.

### RetroArch é diferente do DuckStation

O `.lrtl` do RetroArch armazena dados por sessão com timestamps. O `lrtl_importer` (Fase 2) lê esses arquivos no encerramento do processo e importa para o SQLite. DuckStation não tem equivalente — procfs é obrigatório.

### Crash recovery

Sessões sem `ended_at` com `heartbeat_at` > 5 minutos atrás são consideradas órfãs e fechadas no último `heartbeat_at` registrado.

---

## Configuração

`config.toml` (não versionado — copiar de `config.toml.example`):

```toml
[daemon]
poll_interval_s = 3
port = 9876          # porta real usada no Pi
db_path = "~/.local/share/ps1-tracker/tracker.db"

[watchers]
process_names = ["duckstation-qt", "duckstation", "DuckStation", "PPSSPPSDL", "ppsspp"]
rom_extensions = [".cue", ".chd", ".bin", ".iso", ".cso", ".pbp"]
rom_dirs = ["/mnt/usb-flash"]   # whitelist — apenas ROMs nestes diretórios são rastreadas
```

**DuckStation AppImage:** o processo que mantém o fd da ROM aberto é `AppRun.wrapped`, não `duckstation`. O watcher resolve isso varrendo todos os fds e subindo a árvore de processos via `PPid` — o pai do `AppRun.wrapped` tem "DuckStation" no cmdline. Não é necessário ajustar `process_names` para o AppImage funcionar.

**rom_dirs (whitelist):** fundamental para evitar que arquivos de cache do emulador com extensão `.bin` (ex: `vulkan_shaders.bin`) sejam registrados como jogos. Adicionar mais diretórios se os ROMs estiverem em outros mounts.

---

## Deploy no Raspberry Pi

```bash
git clone <repo> ~/ps1-game-tracker
cd ~/ps1-game-tracker
./install.sh
cp config.toml.example config.toml
nano config.toml        # configurar tokens e paths
sudo systemctl enable ps1-tracker && sudo systemctl start ps1-tracker
```

O serviço usa `User=douglasdans` e `After=network.target`. Na Fase 2 (samba_watcher), adicionar `After=smbd.service` na unit.

---

## Diagnóstico remoto do Pi

A API está em `http://192.168.1.150:9876`. Comandos úteis para diagnóstico sem SSH:

```bash
# Ver todos os jogos com playtime
curl -s http://192.168.1.150:9876/games | python3 -m json.tool

# Jogos sem cover (enriquecimento pendente ou falhou)
curl -s http://192.168.1.150:9876/games | python3 -c "
import json, sys
games = json.load(sys.stdin)
no_cover = [g for g in games if not g['cover_url']]
with_cover = [g for g in games if g['cover_url']]
print(f'Total: {len(games)} | Com cover: {len(with_cover)} | Sem cover: {len(no_cover)}')
for g in no_cover:
    print(f'  [{g[\"platform\"] or \"?\"}] {g[\"display_name\"]}')
"

# Buscar jogo específico por nome
curl -s http://192.168.1.150:9876/games | python3 -c "
import json, sys
games = json.load(sys.stdin)
for g in games:
    if 'sonic' in g['display_name'].lower():
        print(json.dumps(g, indent=2))
"

# Sessão ativa agora
curl -s http://192.168.1.150:9876/sessions/active | python3 -m json.tool
```

---

## Fases de implementação

| Fase                    | Status | Escopo                                                                                          |
| ----------------------- | ------ | ----------------------------------------------------------------------------------------------- |
| 1 — Core                | ✅     | SQLite + procfs_watcher + session_manager + API mínima                                          |
| 1.5 — Metadados locais  | ✅     | display_name (Path.stem) + platform (por path/source); fix multi-track via select_preferred_rom |
| 1.6 — Dedup multi-disco | ✅     | normalize_game_name strip all trailing `(...)` + canonical_name + session flip fix              |
| 2 — Captura completa    | ✅     | samba_watcher (PS2) + lrtl_importer (RetroArch)                                                 |
| 3 — Enriquecimento      | ✅     | IGDB enricher (background thread, throttle, retry)                                              |
| 4 — Frontend TV         | ✅     | Home/Detail/Library, Gamepad API, dark theme 10-foot, stats globais e por jogo                  |
| 5 — Notion Sync         | ⬜     | Push sessão + cron diário                                                                       |
| 6 — RetroAchievements   | ⬜     | **Prioridade.** Hash PS1 rcheevos-compatible + achievements + progresso                         |
| 7 — Produção            | ⬜     | OSD Launcher integration + config completo                                                      |
| 8 — Console info        | ⬜     | Novo pilar: armazenamento, RAM, uso de CPU/GPU, configs do sistema (escopo a detalhar)          |

### MVP validado no Pi (2026-05-23)

Confirmado em produção com DuckStation AppImage + PPSSPP:

| Jogo                            | Source      | Resultado                 |
| ------------------------------- | ----------- | ------------------------- |
| CTR - Crash Team Racing         | duckstation | ✅ detectado              |
| Gran Turismo 2                  | duckstation | ✅ detectado              |
| Crash Bandicoot                 | duckstation | ✅ detectado              |
| Gran Turismo (PSP)              | ppsspp      | ✅ detectado              |
| Michael Jackson: The Experience | ppsspp      | ✅ detectado              |
| vulkan_shaders.bin              | —           | ✅ filtrado pelo rom_dirs |

**Fase 1.5 concluída (2026-05-23):** `display_name` agora é o stem do filename; `platform` inferido por segmento de path (`/PS1/`, `/PSP/`) com fallback por source. Fix de multi-track: `select_preferred_rom()` em `procfs.py` garante `.chd > .cue > .bin` — evita flip de sessão quando múltiplos fds de faixa estão abertos.

**Fase 1.6 concluída (2026-05-23):** `normalize_game_name` strip iterativo de todos os grupos `(...)` finais — região, versão, track, disco. `SessionManager` compara por `canonical_name` evitando session flip quando DuckStation alterna entre fds de tracks. `playtime_summary` agrega por `canonical_name`. Descoberta relevante: DuckStation não mantém `.cue` aberto — apenas os `.bin` dos tracks ficam nos fds.

**Fase 2 concluída (2026-05-23):** `samba_watcher` parseia `smbstatus -L` para detectar ISOs PS2/OPL abertas via SMB (requer entrada no sudoers). `lrtl_importer` lê `.lrtl` do RetroArch e importa sessões por delta em relação ao acumulado já no DB — disparado no startup e quando o processo RetroArch encerra. Novos campos opcionais no config: `samba_rom_dirs`, `retroarch_playlist_dirs`, `samba_debounce_polls` (default 3 — OPL solta o lock brevemente durante boot). `strip_ps2_serial` em `session_manager.py` remove o prefixo serial OPL (`SLUS_NNN.NN.`) do display_name/canonical_name. `lrtl_importer` aplica `normalize_game_name` no stem do `.lrtl` para que histórico RetroArch e procfs agregem corretamente na `playtime_summary`.

**Fase 4 concluída (2026-05-31, polish TV em 2026-07-09):** frontend em vanilla JS com módulos ES (`app.js` roteia `screens/home|detail|library`). Gamepad API mapeia botões para KeyboardEvents sintéticos (✕=Enter, ○=Escape, □=Square, L1/R1, d-pad). Passe de usabilidade TV (2026-07-09): scroll por setas no detail e na seção de stats, contraste `--text-muted` corrigido para ~6.2:1, escala tipográfica 10-foot, hints de rodapé contextuais por tela, polling de `/sessions/active` a cada 10s, "Mais jogados" com capas reais + % do tempo total, API/host derivados da origem da página (IP do Pi pode mudar sem quebrar).

**Fase 3 concluída (2026-05-30):** `daemon/enricher.py` — IGDB como único enricher (ScreenScraper descartado). `enrich_game` busca por `canonical_name` + filtro de platform (PS1=7, PS2=8, PSP=38); plataformas não mapeadas buscam sem filtro. Thread de background com fila (`enricher_loop`): seeded no startup com todos os jogos `enriched_at IS NULL`, e enfileira novos jogos detectados pelo polling loop. Throttle de 0.3s entre requests para respeitar 4 req/s do IGDB. `RateLimitError` (429): não incrementa `enrichment_retries` — game re-enfileirado após sleep de 10s. Desiste após 3 boots com falha (`enrichment_retries >= 3`). Token Twitch cacheado em `igdb_token.json` ao lado do DB (~62 dias). Schema: campo `enrichment_retries INTEGER DEFAULT 0` adicionado via `ALTER TABLE`. Configurar no Pi: adicionar `[igdb]` com `client_id` e `client_secret` ao `config.toml`.
