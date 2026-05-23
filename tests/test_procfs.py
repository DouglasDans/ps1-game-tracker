import os

from daemon.watchers.procfs import find_open_roms_for_pid, get_ppid, is_rom_path, select_preferred_rom


def test_is_rom_path_detects_cue():
    assert is_rom_path("/media/roms/Metal Gear Solid.cue", [".cue", ".chd", ".bin"], [])


def test_is_rom_path_detects_chd():
    assert is_rom_path("/media/roms/crash.chd", [".cue", ".chd", ".bin"], [])


def test_is_rom_path_detects_bin():
    assert is_rom_path("/media/roms/game.bin", [".cue", ".chd", ".bin"], [])


def test_is_rom_path_is_case_insensitive():
    assert is_rom_path("/media/roms/game.CUE", [".cue"], [])
    assert is_rom_path("/media/roms/game.CHD", [".CHD"], [])


def test_is_rom_path_rejects_save_state():
    assert not is_rom_path(
        "/home/pi/.config/duckstation/savestates/mgs.sav", [".cue", ".chd", ".bin"], []
    )


def test_is_rom_path_rejects_shared_lib():
    assert not is_rom_path("/usr/lib/libGL.so", [".cue", ".chd", ".bin"], [])


def test_is_rom_path_rejects_empty_string():
    assert not is_rom_path("", [".cue", ".chd"], [])


def test_is_rom_path_whitelist_accepts_file_inside_rom_dir():
    assert is_rom_path(
        "/mnt/usb-flash/Retrogaming/PS1/CTR - Crash Team Racing (USA).bin",
        [".bin"],
        ["/mnt/usb-flash"],
    )


def test_is_rom_path_whitelist_rejects_file_outside_rom_dir():
    assert not is_rom_path(
        "/home/douglasdans/.local/share/duckstation/vulkan_shaders.bin",
        [".bin"],
        ["/mnt/usb-flash"],
    )


def test_find_open_roms_for_nonexistent_pid_returns_empty():
    result = find_open_roms_for_pid(999999999, [".cue", ".chd"], [])
    assert result == []


def test_get_ppid_matches_os_getppid():
    assert get_ppid(os.getpid()) == os.getppid()


def test_get_ppid_nonexistent_pid_returns_none():
    assert get_ppid(999999999) is None


def test_select_preferred_rom_prefers_chd_over_cue_and_bin():
    roms = [
        "/mnt/usb-flash/PS1/Game (Track 1).bin",
        "/mnt/usb-flash/PS1/Game.cue",
        "/mnt/usb-flash/PS1/Game.chd",
    ]
    assert select_preferred_rom(roms) == "/mnt/usb-flash/PS1/Game.chd"


def test_select_preferred_rom_prefers_cue_over_bin():
    roms = [
        "/mnt/usb-flash/PS1/Game (Track 2).bin",
        "/mnt/usb-flash/PS1/Game (Track 1).bin",
        "/mnt/usb-flash/PS1/Game.cue",
    ]
    assert select_preferred_rom(roms) == "/mnt/usb-flash/PS1/Game.cue"


def test_select_preferred_rom_returns_bin_when_only_option():
    roms = ["/mnt/usb-flash/PSP/Game.iso"]
    assert select_preferred_rom(roms) == "/mnt/usb-flash/PSP/Game.iso"


def test_select_preferred_rom_returns_none_for_empty_list():
    assert select_preferred_rom([]) is None


def test_select_preferred_rom_multiple_bins_returns_alphabetically_first():
    roms = [
        "/mnt/usb-flash/PS1/Dino Crisis (Track 2).bin",
        "/mnt/usb-flash/PS1/Dino Crisis (Track 1).bin",
    ]
    assert select_preferred_rom(roms) == "/mnt/usb-flash/PS1/Dino Crisis (Track 1).bin"
