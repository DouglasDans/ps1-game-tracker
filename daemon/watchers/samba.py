import logging
import os
import re
import subprocess

from daemon.watchers.procfs import is_rom_path

logger = logging.getLogger(__name__)

# smbstatus -L timestamp suffix: "Mon May 23 10:30:00 2026"
_TIMESTAMP_RE = re.compile(r"\s+\w{3}\s+\w{3}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2}\s+\d{4}\s*$")


def parse_smbstatus_output(
    output: str,
    rom_dirs: list[str],
    extensions: list[str],
) -> str | None:
    past_header = False
    for line in output.splitlines():
        if line.startswith("---"):
            past_header = True
            continue
        if not past_header or not line.strip():
            continue
        for share_path in rom_dirs:
            idx = line.find(share_path)
            if idx == -1:
                continue
            rest = line[idx + len(share_path):]
            filename = _TIMESTAMP_RE.sub("", rest).strip()
            if not filename:
                continue
            full_path = os.path.join(share_path, filename)
            if is_rom_path(full_path, extensions, rom_dirs):
                return full_path
    return None


def poll(rom_dirs: list[str], extensions: list[str]) -> tuple[str | None, str | None]:
    if not rom_dirs:
        return None, None
    try:
        result = subprocess.run(
            ["sudo", "smbstatus", "-L"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode != 0:
            return None, None
        path = parse_smbstatus_output(result.stdout, rom_dirs, extensions)
        if path:
            return path, "samba"
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        logger.debug("smbstatus unavailable or timed out")
    return None, None
