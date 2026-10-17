"""Status do console (aba Sistema): leitura ao vivo do /proc, /sys e vcgencmd.

Só leitura e sem root: o daemon roda como douglasdans (grupo video para o
vcgencmd). As funções parse_* recebem o texto já lido, para serem testáveis
sem o sistema real; SystemProbe faz a leitura e guarda a amostra anterior,
porque CPU e rede são taxas (diferença entre duas leituras).
"""
import os
import subprocess
import threading
import time
from pathlib import Path

# Bits do `vcgencmd get_throttled`: 0-3 = acontecendo agora,
# 16-19 = já aconteceu desde o boot (ficam ligados até reiniciar).
_THROTTLE_BITS = [
    (0, "Subtensão"),
    (1, "Frequência limitada"),
    (2, "Limitado (throttling)"),
    (3, "Limite de temperatura"),
]

DISKS = [
    ("Sistema (SD)", "/"),
    ("Retrogaming", "/mnt/usb-flash/Retrogaming"),
    ("PS2SMB", "/mnt/usb-flash/PS2SMB"),
]

INTERFACES = [("eth0", "PS2 (cabo)"), ("wlan0", "Wi-Fi")]

SERVICES = [
    ("ps1-osd-laucher", "Launcher"),
    ("ps1-tracker", "Game Tracker"),
    ("smbd", "Samba (PS2)"),
    ("bluetooth", "Bluetooth"),
    ("log-sentinel", "Sentinela de logs"),
    ("ingame-status", "Métricas em jogo"),
    ("controller-monitor", "Monitor de controles"),
    ("wifi-monitor", "Monitor de Wi-Fi"),
]

_BUS_NAMES = {"0003": "USB", "0005": "Bluetooth", "0006": "Virtual"}


def decode_throttled(raw: str) -> dict:
    try:
        value = int(raw, 16)
    except ValueError:
        return {"raw": raw, "now": [], "since_boot": []}
    return {
        "raw": raw,
        "now": [label for bit, label in _THROTTLE_BITS if value & (1 << bit)],
        "since_boot": [label for bit, label in _THROTTLE_BITS if value & (1 << (bit + 16))],
    }


def parse_cpu_lines(proc_stat: str) -> dict[str, tuple[int, int]]:
    """{"cpu": (total, idle), "cpu0": ..., ...} a partir do /proc/stat."""
    cpus = {}
    for line in proc_stat.splitlines():
        if not line.startswith("cpu"):
            continue
        name, *fields = line.split()
        values = [int(v) for v in fields]
        cpus[name] = (sum(values), values[3] + values[4])  # idle + iowait
    return cpus


class CpuSampler:
    def __init__(self) -> None:
        self._prev: dict[str, tuple[int, int]] | None = None

    def sample(self, proc_stat: str) -> dict | None:
        cur = parse_cpu_lines(proc_stat)
        prev, self._prev = self._prev, cur
        if prev is None:
            return None

        def busy(name: str) -> float:
            total = cur[name][0] - prev[name][0]
            idle = cur[name][1] - prev[name][1]
            return round(100 * (total - idle) / total, 1) if total else 0.0

        cores = sorted((n for n in cur if n != "cpu"), key=lambda n: int(n[3:]))
        return {"total": busy("cpu"), "cores": [busy(n) for n in cores]}


def parse_meminfo(text: str) -> dict:
    info = {}
    for line in text.splitlines():
        key, _, value = line.partition(":")
        info[key] = int(value.split()[0]) // 1024
    total, available = info["MemTotal"], info["MemAvailable"]
    return {"total_mb": total, "available_mb": available, "used_mb": total - available}


def parse_input_devices(text: str) -> list[dict]:
    """Controles (dispositivos com handler jsN) do /proc/bus/input/devices."""
    pads = []
    for block in text.strip().split("\n\n"):
        fields = {}
        for line in block.splitlines():
            kind, _, rest = line.partition(": ")
            fields.setdefault(kind, rest)
        handlers = fields.get("H", "").removeprefix("Handlers=").split()
        if not any(h.startswith("js") for h in handlers):
            continue
        ident = dict(part.split("=", 1) for part in fields.get("I", "").split())
        uniq = fields.get("U", "").removeprefix("Uniq=") or None
        pads.append({
            "name": fields.get("N", "").removeprefix("Name=").strip('"'),
            "bus": _BUS_NAMES.get(ident.get("Bus"), ident.get("Bus")),
            "id": f'{ident.get("Vendor")}:{ident.get("Product")}',
            "uniq": uniq,
        })
    return pads


def friendly_name(comm: str, cmdline: list[str]) -> str:
    """python3 não diz nada na tela: mostra o script (launcher.py, ingame-status.py)."""
    if comm.startswith("python"):
        script = next((arg for arg in cmdline[1:] if arg.endswith(".py")), None)
        if script:
            return Path(script).name
    return comm


def group_processes(cur: dict, prev: dict, dt: float, hz: int) -> list[dict]:
    """Soma CPU e memória por nome: o Chromium (que exibe esta tela) roda
    vários processos, que na TV viravam várias linhas "chromium"."""
    groups: dict[str, dict] = {}
    for pid, (name, ticks, rss) in cur.items():
        before = prev.get(pid)
        cpu = (ticks - before[1]) / hz / dt * 100 if before else 0.0
        g = groups.setdefault(name, {"name": name, "count": 0, "cpu": 0.0, "rss_mb": 0.0})
        g["count"] += 1
        g["cpu"] += cpu
        g["rss_mb"] += rss
    rows = [{**g, "cpu": round(g["cpu"], 1), "rss_mb": round(g["rss_mb"])} for g in groups.values()]
    rows.sort(key=lambda r: (r["cpu"], r["rss_mb"]), reverse=True)
    return rows


def _read(path: str) -> str:
    return Path(path).read_text()


def _vcgencmd(*args: str) -> str:
    try:
        out = subprocess.run(["vcgencmd", *args], capture_output=True, text=True, timeout=2).stdout
        return out.strip().split("=", 1)[-1]
    except (OSError, subprocess.SubprocessError):
        return "?"


def _disk(label: str, mount: str) -> dict:
    if mount != "/" and not os.path.ismount(mount):
        return {"label": label, "mount": mount, "mounted": False}
    try:
        st = os.statvfs(mount)
    except OSError:  # mount "zumbi" (pendrive caiu do barramento): Input/output error
        return {"label": label, "mount": mount, "mounted": False}
    total = st.f_blocks * st.f_frsize
    free = st.f_bavail * st.f_frsize
    return {"label": label, "mount": mount, "mounted": True,
            "total_gb": round(total / 1e9, 1), "used_gb": round((total - free) / 1e9, 1)}


def _services() -> list[dict]:
    names = [name for name, _ in SERVICES]
    try:
        out = subprocess.run(["systemctl", "is-active", *names], capture_output=True, text=True, timeout=3).stdout
        states = out.split()
    except (OSError, subprocess.SubprocessError):
        states = []
    states += ["unknown"] * (len(names) - len(states))
    return [{"unit": name, "label": label, "state": state} for (name, label), state in zip(SERVICES, states)]


class SystemProbe:
    """Lê o estado do console. Taxas (CPU, rede, processos) são calculadas
    contra a leitura anterior: a primeira chamada devolve-as como null."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._cpu = CpuSampler()
        self._prev_net: tuple[float, dict] | None = None
        self._prev_procs: tuple[float, dict] | None = None

    def snapshot(self) -> dict:
        with self._lock:
            now = time.monotonic()
            return {
                "temp_c": round(int(_read("/sys/class/thermal/thermal_zone0/temp")) / 1000, 1),
                "freq_mhz": int(_read("/sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq")) // 1000,
                "throttled": decode_throttled(_vcgencmd("get_throttled")),
                "cpu": self._cpu.sample(_read("/proc/stat")),
                "load": [float(v) for v in _read("/proc/loadavg").split()[:3]],
                "uptime_s": int(float(_read("/proc/uptime").split()[0])),
                "memory": parse_meminfo(_read("/proc/meminfo")),
                "disks": [_disk(label, mount) for label, mount in DISKS],
                "network": self._network(now),
                "controllers": parse_input_devices(_read("/proc/bus/input/devices")),
                "processes": self._processes(now),
                "services": _services(),
            }

    def _network(self, now: float) -> list[dict]:
        counters = {}
        for iface, _ in INTERFACES:
            base = f"/sys/class/net/{iface}"
            try:
                counters[iface] = (int(_read(f"{base}/statistics/rx_bytes")),
                                   int(_read(f"{base}/statistics/tx_bytes")),
                                   _read(f"{base}/operstate").strip())
            except OSError:
                counters[iface] = (0, 0, "ausente")
        prev, self._prev_net = self._prev_net, (now, counters)

        result = []
        for iface, label in INTERFACES:
            rx, tx, state = counters[iface]
            entry = {"iface": iface, "label": label, "up": state == "up", "rx_mbps": None, "tx_mbps": None}
            if prev:
                dt = now - prev[0]
                prx, ptx, _ = prev[1][iface]
                entry["rx_mbps"] = round((rx - prx) * 8 / 1e6 / dt, 2)
                entry["tx_mbps"] = round((tx - ptx) * 8 / 1e6 / dt, 2)
            result.append(entry)
        return result

    def _processes(self, now: float, limit: int = 8) -> list[dict] | None:
        page_mb = os.sysconf("SC_PAGE_SIZE") / 1024 / 1024
        ticks = {}
        for pid in filter(str.isdigit, os.listdir("/proc")):
            try:
                stat = _read(f"/proc/{pid}/stat")
                comm = stat[stat.index("(") + 1:stat.rindex(")")]
                cmdline = _read(f"/proc/{pid}/cmdline").split("\0") if comm.startswith("python") else []
            except OSError:
                continue
            fields = stat[stat.rindex(")") + 2:].split()
            ticks[pid] = (friendly_name(comm, cmdline), int(fields[11]) + int(fields[12]), int(fields[21]) * page_mb)
        prev, self._prev_procs = self._prev_procs, (now, ticks)
        if not prev:
            return None
        return group_processes(ticks, prev[1], now - prev[0], os.sysconf("SC_CLK_TCK"))[:limit]
