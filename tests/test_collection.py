from daemon.collection import collection_summary, scan_collection

FOLDERS = {"PS1": "PS1", "Dreamcast": "Dreamcast", "Mega Drive": "Mega Drive", "DVD": "PS2"}


def make_tree(root, files):
    for rel in files:
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"")


def test_scan_groups_files_into_games(tmp_path):
    make_tree(tmp_path, [
        "PS1/Crash Bandicoot (USA).chd",
        "PS1/Final Fantasy VII (USA) (Disc 1).chd",
        "PS1/Final Fantasy VII (USA) (Disc 2).chd",          # multi-disco = 1 jogo
        "PS1/Gran Turismo 2 (USA) (Arcade Mode).chd",
        "PS1/Gran Turismo 2 (USA) (Simulation Mode).chd",    # variantes = 1 jogo
        "PS1/Looney Tunes - Sheep Raider.cue",
        "PS1/Looney Tunes - Sheep Raider.bin",               # faixa do .cue: não conta
        "Dreamcast/Looney Tunes Space Race/Looney Tunes Space Race v1.000 (2000)(Infogrames)(NTSC)(US)(M3)[!].gdi",
        "Dreamcast/Looney Tunes Space Race/track01.bin",     # faixas do .gdi: não contam
        "Dreamcast/Looney Tunes Space Race/track02.raw",
        "Mega Drive/Sonic the Hedgehog 2 (World).bin",       # cartucho .bin: conta
        "Mega Drive/Sonic CD.cue",
        "Mega Drive/Sonic CD.bin",
        "DVD/SCUS_973.28.Gran Turismo 4.iso",
        "DVD/games.bin",                                     # lista interna do OPL
        "PS1/readme.txt",
    ])
    games = scan_collection([(str(tmp_path / folder), platform) for folder, platform in FOLDERS.items()])
    assert sorted((g["platform"], g["name"]) for g in games) == [
        ("Dreamcast", "Looney Tunes Space Race"),
        ("Mega Drive", "Sonic the Hedgehog 2"),
        ("Mega-CD - Sega CD", "Sonic CD"),  # .cue na pasta do Mega Drive = jogo de Mega-CD
        ("PS1", "Crash Bandicoot"),
        ("PS1", "Final Fantasy VII"),
        ("PS1", "Gran Turismo 2"),
        ("PS1", "Looney Tunes - Sheep Raider"),
        ("PS2", "Gran Turismo 4"),
    ]


def test_scan_skips_missing_folder(tmp_path):
    assert scan_collection([(str(tmp_path / "nope"), "PS1")]) == []


DISK = [
    {"platform": "PS1", "name": "Crash Bandicoot"},
    {"platform": "PS1", "name": "Gran Turismo"},
    {"platform": "PSP", "name": "Gran Turismo"},
    {"platform": "PSP", "name": "God of War - Ghost of Sparta"},
    {"platform": "PS2", "name": "Shadow of the Colossus"},
]

PLAYED = [
    {"canonical_name": "Crash Bandicoot", "platform": "PS1", "total_seconds": 4000},
    {"canonical_name": "Gran Turismo", "platform": "PS1", "total_seconds": 3000},
    # RetroArch às vezes grava sem plataforma: casa só pelo nome
    {"canonical_name": "God of War - Ghost of Sparta", "platform": None, "total_seconds": 3000},
    {"canonical_name": "drive0", "platform": None, "total_seconds": 60},  # jogado, mas não está no disco
]


def test_collection_summary_matches_by_name_and_platform():
    s = collection_summary(DISK, PLAYED)
    assert (s["on_disk"], s["played"], s["not_played"]) == (5, 3, 2)
    by = {p["platform"]: p for p in s["by_platform"]}
    # o Gran Turismo de PS1 jogado não marca o de PSP como jogado
    assert by["PSP"] == {"platform": "PSP", "on_disk": 2, "played": 1, "total_seconds": 3000}
    assert by["PS1"] == {"platform": "PS1", "on_disk": 2, "played": 2, "total_seconds": 7000}
    assert by["PS2"]["played"] == 0
    assert s["not_played_games"] == [{"platform": "PS2", "name": "Shadow of the Colossus", "opened": False},
                                     {"platform": "PSP", "name": "Gran Turismo", "opened": False}]


def test_collection_summary_separates_opened_briefly_from_never_opened():
    opened = PLAYED + [{"canonical_name": "Shadow of the Colossus", "platform": "PS2"}]  # sessão < 2 min
    s = collection_summary(DISK, PLAYED, opened)
    assert s["opened_only"] == 1
    assert s["not_played_games"][0] == {"platform": "PS2", "name": "Shadow of the Colossus", "opened": True}


def test_collection_summary_orders_platforms_by_games_on_disk():
    s = collection_summary(DISK, PLAYED)
    assert [p["platform"] for p in s["by_platform"]] == ["PS1", "PSP", "PS2"]
