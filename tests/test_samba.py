from unittest.mock import patch

from daemon.watchers.samba import parse_smbstatus_output, poll

_ROM_DIRS = ["/srv/samba/ps2"]

_HEADER = """\
Locked files:
Pid          Uid        DenyMode   Access      R/W        Oplock           SharePath   Name   Time
--------------------------------------------------------------------------------------------------------------------------
"""


def _line(name: str) -> str:
    return (
        "2345         1000       DENY_NONE  0x120089    RDONLY     NONE             "
        f"/srv/samba/ps2   {name}   Mon May 23 10:30:00 2026\n"
    )


_OUTPUT_WITH_ISO = _HEADER + _line("DVD/SCES_500.00.Gran Turismo 3.iso")
_OUTPUT_EMPTY = _HEADER
_OUTPUT_NON_ROM = _HEADER + _line("CFG/some_config.txt")


def test_parse_finds_iso_in_output():
    result = parse_smbstatus_output(_OUTPUT_WITH_ISO, _ROM_DIRS)
    assert result == "/srv/samba/ps2/DVD/SCES_500.00.Gran Turismo 3.iso"


def test_parse_finds_iso_in_cd_folder():
    output = _HEADER + _line("CD/SLUS_000.00.Crash Bash.iso")
    assert parse_smbstatus_output(output, _ROM_DIRS) == "/srv/samba/ps2/CD/SLUS_000.00.Crash Bash.iso"


def test_parse_finds_zso():
    output = _HEADER + _line("DVD/SLUS_000.00.Burnout 3.zso")
    assert parse_smbstatus_output(output, _ROM_DIRS) == "/srv/samba/ps2/DVD/SLUS_000.00.Burnout 3.zso"


def test_parse_ignores_vmc_and_game_list_cache():
    # OPL mantém o VMC e o games.bin abertos junto com a ISO — o VMC listado
    # antes não pode "roubar" a sessão do jogo.
    output = (
        _HEADER
        + _line("VMC/SLUS_210.50_0.bin")
        + _line("CD/games.bin")
        + _line("DVD/SLUS_210.50.Burnout 3 - Takedown.iso")
    )
    assert parse_smbstatus_output(output, _ROM_DIRS) == "/srv/samba/ps2/DVD/SLUS_210.50.Burnout 3 - Takedown.iso"


def test_parse_rejects_iso_outside_game_folders():
    assert parse_smbstatus_output(_HEADER + _line("APPS/something.iso"), _ROM_DIRS) is None


def test_parse_rejects_non_opl_extension():
    assert parse_smbstatus_output(_HEADER + _line("DVD/game.bin"), _ROM_DIRS) is None


def test_parse_returns_none_for_empty_locked_section():
    assert parse_smbstatus_output(_OUTPUT_EMPTY, _ROM_DIRS) is None


def test_parse_rejects_non_rom_extension():
    assert parse_smbstatus_output(_OUTPUT_NON_ROM, _ROM_DIRS) is None


def test_parse_rejects_file_outside_rom_dirs():
    other_dirs = ["/other/path"]
    assert parse_smbstatus_output(_OUTPUT_WITH_ISO, other_dirs) is None


def test_parse_returns_none_for_empty_output():
    assert parse_smbstatus_output("", _ROM_DIRS) is None


def test_poll_returns_none_when_rom_dirs_empty():
    file_path, source = poll([])
    assert file_path is None
    assert source is None


def test_poll_returns_game_when_iso_found():
    with patch("daemon.watchers.samba.subprocess.run") as mock_run:
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = _OUTPUT_WITH_ISO
        file_path, source = poll(_ROM_DIRS)
    assert file_path == "/srv/samba/ps2/DVD/SCES_500.00.Gran Turismo 3.iso"
    assert source == "samba"


def test_poll_returns_none_on_nonzero_returncode():
    with patch("daemon.watchers.samba.subprocess.run") as mock_run:
        mock_run.return_value.returncode = 1
        mock_run.return_value.stdout = ""
        file_path, source = poll(_ROM_DIRS)
    assert file_path is None
    assert source is None


def test_poll_returns_none_when_smbstatus_not_found():
    with patch("daemon.watchers.samba.subprocess.run", side_effect=FileNotFoundError):
        file_path, source = poll(_ROM_DIRS)
    assert file_path is None
    assert source is None
