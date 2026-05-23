import logging
from pathlib import Path

logger = logging.getLogger(__name__)

_EXT_PRIORITY: dict[str, int] = {
    ".chd": 0,
    ".cue": 1,
    ".iso": 2,
    ".pbp": 3,
    ".cso": 4,
    ".bin": 5,
}


def select_preferred_rom(roms: list[str]) -> str | None:
    if not roms:
        return None
    return min(roms, key=lambda p: _EXT_PRIORITY.get(Path(p).suffix.lower(), 99))


def is_rom_path(path: str, extensions: list[str], rom_dirs: list[str]) -> bool:
    if not path:
        return False
    lower = path.lower()
    if not any(lower.endswith(ext.lower()) for ext in extensions):
        return False
    if rom_dirs:
        return any(path.startswith(d) for d in rom_dirs)
    return True


def find_open_roms_for_pid(pid: int, extensions: list[str], rom_dirs: list[str]) -> list[str]:
    """Returns resolved paths of ROM files currently open by the given PID."""
    roms: list[str] = []
    try:
        for fd in Path(f"/proc/{pid}/fd").iterdir():
            try:
                target = str(fd.resolve())
                if is_rom_path(target, extensions, rom_dirs):
                    roms.append(target)
            except (OSError, PermissionError):
                continue
    except (OSError, PermissionError):
        pass
    return roms


def get_ppid(pid: int) -> int | None:
    """Read the parent PID from /proc/{pid}/status."""
    try:
        for line in Path(f"/proc/{pid}/status").read_text().splitlines():
            if line.startswith("PPid:"):
                return int(line.split()[1])
    except (OSError, PermissionError):
        pass
    return None


_SOURCE_MAP: dict[str, str] = {
    "duckstation-qt": "duckstation",
    "duckstation":    "duckstation",
    "PPSSPPSDL":      "ppsspp",
    "ppsspp":         "ppsspp",
}


def identify_source(pid: int, process_names: list[str]) -> str | None:
    """
    Walk the process tree upward from pid, looking for a known emulator name
    anywhere in the cmdline. Needed because AppImage processes (AppRun.wrapped)
    don't have the emulator name in their own executable name.
    """
    visited: set[int] = set()
    current: int | None = pid
    while current and current > 1 and current not in visited:
        visited.add(current)
        try:
            cmdline = (
                Path(f"/proc/{current}/cmdline")
                .read_bytes()
                .decode("utf-8", errors="replace")
                .lower()
            )
            for name in process_names:
                if name.lower() in cmdline:
                    return _SOURCE_MAP.get(name, name.lower())
        except (OSError, PermissionError):
            pass
        current = get_ppid(current)
    return None


def poll(
    process_names: list[str],
    extensions: list[str],
    rom_dirs: list[str],
) -> tuple[str | None, str | None]:
    """
    Scan all /proc entries for open ROM file descriptors, then identify the
    emulator source by walking the process tree upward via cmdline inspection.

    Inverting the original name-first approach makes this work with AppImage
    processes (DuckStation), where the process holding the ROM fd is
    AppRun.wrapped — not a process with a recognisable emulator name.
    """
    try:
        for entry in Path("/proc").iterdir():
            if not entry.name.isdigit():
                continue
            pid = int(entry.name)
            roms = find_open_roms_for_pid(pid, extensions, rom_dirs)
            if not roms:
                continue
            source = identify_source(pid, process_names)
            if source:
                rom = select_preferred_rom(roms)
                logger.debug("ROM detected: %s (pid %d, source %s)", rom, pid, source)
                return rom, source
    except OSError:
        pass
    return None, None
