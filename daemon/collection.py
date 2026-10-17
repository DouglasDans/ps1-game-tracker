"""Coleção no disco (Estatísticas › Biblioteca): os jogos que existem nos
pendrives, jogados ou não — o polling só enxerga o que roda.

Um jogo pode ter vários arquivos (cue+bin, gdi+faixas, vários discos,
variantes como GT2 Arcade/Simulation): conta-se só o arquivo "principal" e
agrupa-se pelo mesmo nome normalizado que o tracker usa (canonical_name),
que é também a chave para cruzar com o que foi jogado.
"""
from pathlib import Path

from daemon.session_manager import normalize_game_name, strip_ps2_serial

# Pasta do pendrive -> plataforma, com os mesmos nomes da tabela games.
COLLECTION_FOLDERS = [
    ("/mnt/usb-flash/Retrogaming/PS1", "PS1"),
    ("/mnt/usb-flash/PS2SMB/DVD", "PS2"),
    ("/mnt/usb-flash/PS2SMB/CD", "PS2"),
    ("/mnt/usb-flash/Retrogaming/PSP", "PSP"),
    ("/mnt/usb-flash/Retrogaming/Dreamcast", "Dreamcast"),
    ("/mnt/usb-flash/Retrogaming/Super Nintendo", "SNES"),
    ("/mnt/usb-flash/Retrogaming/Mega Drive", "Mega Drive"),
    ("/mnt/usb-flash/Retrogaming/N64", "N64"),
    ("/mnt/usb-flash/Retrogaming/GB - GBA", "GBA"),
    ("/mnt/usb-flash/Retrogaming/NeoGeo", "Neo Geo"),
    ("/mnt/usb-flash/Retrogaming/MAME", "Arcade"),
]

# Um arquivo destes = um jogo (disco ou cartucho).
_GAME_EXTS = {".chd", ".cue", ".gdi", ".iso", ".cso", ".zso", ".pbp", ".m3u",
              ".sfc", ".smc", ".md", ".gen", ".gba", ".gb", ".gbc",
              ".n64", ".z64", ".v64", ".neo", ".zip", ".7z"}
# .bin é cartucho (Mega Drive) ou faixa de um .cue/.gdi; .raw é sempre faixa.
_TRACK_EXTS = {".bin", ".raw"}


def _is_game_file(path: Path) -> bool:
    ext = path.suffix.lower()
    if ext in _GAME_EXTS:
        return True
    if ext != ".bin" or path.name.lower() == "games.bin":  # games.bin = lista interna do OPL
        return False
    siblings = list(path.parent.iterdir())
    if any(p.suffix.lower() == ".gdi" for p in siblings):  # pasta de jogo .gdi: tudo faixa
        return False
    return not any(p.suffix.lower() == ".cue" and p.stem == path.stem for p in siblings)


def scan_collection(folders: list[tuple[str, str]] = COLLECTION_FOLDERS) -> list[dict]:
    games: dict[tuple[str, str], dict] = {}
    for folder, platform in folders:
        root = Path(folder)
        if not root.is_dir():
            continue
        for path in root.rglob("*"):
            if not path.is_file() or not _is_game_file(path):
                continue
            # .cue na pasta do Mega Drive é um jogo de Mega-CD (Sonic CD)
            plat = "Mega-CD - Sega CD" if platform == "Mega Drive" and path.suffix.lower() == ".cue" else platform
            name = normalize_game_name(strip_ps2_serial(path.stem))
            games.setdefault((plat, name), {"platform": plat, "name": name})
    return list(games.values())


def _index(games: list[dict]) -> dict[str, list[dict]]:
    by_name: dict[str, list[dict]] = {}
    for g in games:
        by_name.setdefault(g["canonical_name"], []).append(g)
    return by_name


def _match(index: dict[str, list[dict]], game: dict) -> dict | None:
    return next((g for g in index.get(game["name"], []) if g["platform"] in (game["platform"], None)), None)


def collection_summary(disk: list[dict], played: list[dict], opened: list[dict] = ()) -> dict:
    """Cruza o disco com os jogos jogados (playtime_summary): mesmo
    canonical_name e mesma plataforma — ou plataforma vazia, que é como
    alguns jogos do RetroArch ficaram gravados. `opened` (qualquer sessão,
    mesmo < 2 min) separa "nunca aberto" de "só abriu pra testar"."""
    played_index, opened_index = _index(played), _index(list(opened))

    platforms: dict[str, dict] = {}
    not_played = []
    for game in disk:
        match = _match(played_index, game)
        p = platforms.setdefault(game["platform"],
                                 {"platform": game["platform"], "on_disk": 0, "played": 0, "total_seconds": 0})
        p["on_disk"] += 1
        if match:
            p["played"] += 1
            p["total_seconds"] += match["total_seconds"] or 0
        else:
            not_played.append({**game, "opened": _match(opened_index, game) is not None})

    played_count = sum(p["played"] for p in platforms.values())
    return {
        "on_disk": len(disk),
        "played": played_count,
        "not_played": len(disk) - played_count,
        "opened_only": sum(1 for g in not_played if g["opened"]),
        "by_platform": sorted(platforms.values(), key=lambda p: (-p["on_disk"], p["platform"])),
        "not_played_games": sorted(not_played, key=lambda g: (g["platform"], g["name"])),
    }
