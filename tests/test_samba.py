from unittest.mock import patch

from daemon.watchers.samba import parse_smbstatus_output, poll

_EXTENSIONS = [".iso", ".chd", ".bin", ".cue"]
_ROM_DIRS = ["/srv/samba/ps2"]

_OUTPUT_WITH_ISO = """\
Locked files:
Pid          Uid        DenyMode   Access      R/W        Oplock           SharePath   Name   Time
--------------------------------------------------------------------------------------------------------------------------
2345         1000       DENY_NONE  0x120089    RDONLY     NONE             /srv/samba/ps2   Gran Turismo 3 (Europe).iso   Mon May 23 10:30:00 2026
"""

_OUTPUT_EMPTY = """\
Locked files:
Pid          Uid        DenyMode   Access      R/W        Oplock           SharePath   Name   Time
--------------------------------------------------------------------------------------------------------------------------
"""

_OUTPUT_NON_ROM = """\
Locked files:
Pid          Uid        DenyMode   Access      R/W        Oplock           SharePath   Name   Time
--------------------------------------------------------------------------------------------------------------------------
2345         1000       DENY_NONE  0x120089    RDONLY     NONE             /srv/samba/ps2   some_config.txt   Mon May 23 10:30:00 2026
"""


def test_parse_finds_iso_in_output():
    result = parse_smbstatus_output(_OUTPUT_WITH_ISO, _ROM_DIRS, _EXTENSIONS)
    assert result == "/srv/samba/ps2/Gran Turismo 3 (Europe).iso"


def test_parse_returns_none_for_empty_locked_section():
    assert parse_smbstatus_output(_OUTPUT_EMPTY, _ROM_DIRS, _EXTENSIONS) is None


def test_parse_rejects_non_rom_extension():
    assert parse_smbstatus_output(_OUTPUT_NON_ROM, _ROM_DIRS, _EXTENSIONS) is None


def test_parse_rejects_file_outside_rom_dirs():
    other_dirs = ["/other/path"]
    assert parse_smbstatus_output(_OUTPUT_WITH_ISO, other_dirs, _EXTENSIONS) is None


def test_parse_returns_none_for_empty_output():
    assert parse_smbstatus_output("", _ROM_DIRS, _EXTENSIONS) is None


def test_poll_returns_none_when_rom_dirs_empty():
    file_path, source = poll([], _EXTENSIONS)
    assert file_path is None
    assert source is None


def test_poll_returns_game_when_iso_found():
    with patch("daemon.watchers.samba.subprocess.run") as mock_run:
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = _OUTPUT_WITH_ISO
        file_path, source = poll(_ROM_DIRS, _EXTENSIONS)
    assert file_path == "/srv/samba/ps2/Gran Turismo 3 (Europe).iso"
    assert source == "samba"


def test_poll_returns_none_on_nonzero_returncode():
    with patch("daemon.watchers.samba.subprocess.run") as mock_run:
        mock_run.return_value.returncode = 1
        mock_run.return_value.stdout = ""
        file_path, source = poll(_ROM_DIRS, _EXTENSIONS)
    assert file_path is None
    assert source is None


def test_poll_returns_none_when_smbstatus_not_found():
    with patch("daemon.watchers.samba.subprocess.run", side_effect=FileNotFoundError):
        file_path, source = poll(_ROM_DIRS, _EXTENSIONS)
    assert file_path is None
    assert source is None
