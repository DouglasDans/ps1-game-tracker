from daemon.watchers.procfs import is_rom_path, find_open_roms_for_pid


def test_is_rom_path_detects_cue():
    assert is_rom_path("/media/roms/Metal Gear Solid.cue", [".cue", ".chd", ".bin"])


def test_is_rom_path_detects_chd():
    assert is_rom_path("/media/roms/crash.chd", [".cue", ".chd", ".bin"])


def test_is_rom_path_detects_bin():
    assert is_rom_path("/media/roms/game.bin", [".cue", ".chd", ".bin"])


def test_is_rom_path_is_case_insensitive():
    assert is_rom_path("/media/roms/game.CUE", [".cue"])
    assert is_rom_path("/media/roms/game.CHD", [".CHD"])


def test_is_rom_path_rejects_save_state():
    assert not is_rom_path(
        "/home/pi/.config/duckstation/savestates/mgs.sav", [".cue", ".chd", ".bin"]
    )


def test_is_rom_path_rejects_shared_lib():
    assert not is_rom_path("/usr/lib/libGL.so", [".cue", ".chd", ".bin"])


def test_is_rom_path_rejects_empty_string():
    assert not is_rom_path("", [".cue", ".chd"])


def test_find_open_roms_for_nonexistent_pid_returns_empty():
    # PID 999999999 will never exist
    result = find_open_roms_for_pid(999999999, [".cue", ".chd"])
    assert result == []
