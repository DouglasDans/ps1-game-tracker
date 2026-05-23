import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def is_rom_path(path: str, extensions: list[str]) -> bool:
    if not path:
        return False
    lower = path.lower()
    return any(lower.endswith(ext.lower()) for ext in extensions)


def find_pids_by_name(process_names: list[str]) -> dict[str, int]:
    """Returns {matched_name: pid} for running processes matching any entry in process_names."""
    found: dict[str, int] = {}
    try:
        for entry in Path("/proc").iterdir():
            if not entry.name.isdigit():
                continue
            try:
                cmdline = (entry / "cmdline").read_bytes().decode("utf-8", errors="replace")
                parts = cmdline.split("\x00")
                if not parts or not parts[0]:
                    continue
                exe_name = Path(parts[0]).name
                for name in process_names:
                    if name.lower() in exe_name.lower():
                        found[name] = int(entry.name)
                        break
            except (OSError, PermissionError):
                continue
    except OSError:
        pass
    return found


def find_open_roms_for_pid(pid: int, extensions: list[str]) -> list[str]:
    """Returns resolved paths of ROM files currently open by the given PID."""
    roms: list[str] = []
    try:
        for fd in Path(f"/proc/{pid}/fd").iterdir():
            try:
                target = str(fd.resolve())
                if is_rom_path(target, extensions):
                    roms.append(target)
            except (OSError, PermissionError):
                continue
    except (OSError, PermissionError):
        pass
    return roms


_SOURCE_MAP: dict[str, str] = {
    "duckstation-qt": "duckstation",
    "duckstation":    "duckstation",
    "DuckStation":    "duckstation",
    "PPSSPPSDL":      "ppsspp",
    "ppsspp":         "ppsspp",
}


def poll(process_names: list[str], extensions: list[str]) -> tuple[str | None, str | None]:
    """
    Single poll cycle.
    Returns (file_path, source) if a ROM fd is open in any watched process, else (None, None).
    """
    pids = find_pids_by_name(process_names)
    for proc_name, pid in pids.items():
        roms = find_open_roms_for_pid(pid, extensions)
        if roms:
            source = _SOURCE_MAP.get(proc_name, proc_name.lower())
            logger.debug("ROM detected: %s via %s (pid %d)", roms[0], source, pid)
            return roms[0], source
    return None, None
