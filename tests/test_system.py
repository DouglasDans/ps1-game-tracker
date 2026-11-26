from pathlib import Path

import pytest

from daemon.system import (
    CpuSampler,
    decode_throttled,
    parse_cpu_lines,
    parse_input_devices,
    parse_meminfo,
)


def test_decode_throttled_clean():
    assert decode_throttled("0x0") == {"raw": "0x0", "now": [], "since_boot": []}


def test_decode_throttled_splits_current_and_sticky_bits():
    # 0x50005: under-voltage now + throttled now, and both already happened since boot
    result = decode_throttled("0x50005")
    assert result["now"] == ["Subtensão", "Limitado (throttling)"]
    assert result["since_boot"] == ["Subtensão", "Limitado (throttling)"]


def test_decode_throttled_unknown_value_is_kept_raw():
    assert decode_throttled("?") == {"raw": "?", "now": [], "since_boot": []}


PROC_STAT = """cpu  100 0 100 800 0 0 0 0 0 0
cpu0 50 0 50 400 0 0 0 0 0 0
cpu1 50 0 50 400 0 0 0 0 0 0
intr 12345
"""


def test_parse_cpu_lines_keeps_total_and_each_core():
    cpus = parse_cpu_lines(PROC_STAT)
    assert list(cpus) == ["cpu", "cpu0", "cpu1"]
    assert cpus["cpu0"] == (500, 400)  # (total, idle)


def test_cpu_sampler_reports_busy_percentage_between_samples():
    later = PROC_STAT.replace("cpu0 50 0 50 400", "cpu0 125 0 125 450")
    later = later.replace("cpu  100 0 100 800", "cpu  175 0 175 850")
    sampler = CpuSampler()
    assert sampler.sample(PROC_STAT) is None  # first sample: no delta yet
    usage = sampler.sample(later)
    assert usage["total"] == 75.0
    assert usage["cores"] == [75.0, 0.0]


def test_parse_meminfo_in_mb():
    text = "MemTotal:        4087808 kB\nMemFree:          100000 kB\nMemAvailable:    2043904 kB\n"
    assert parse_meminfo(text) == {"total_mb": 3992, "available_mb": 1996, "used_mb": 1996}


INPUT_DEVICES = """I: Bus=0019 Vendor=0001 Product=0001 Version=0100
N: Name="pwr_button"
P: Phys=gpio-keys/input0
U: Uniq=
H: Handlers=kbd event4

I: Bus=0005 Vendor=054c Product=0268 Version=8000
N: Name="Sony PLAYSTATION(R)3 Controller"
P: Phys=2c:cf:67:bc:65:7a
U: Uniq=38:c0:96:91:55:ff
H: Handlers=event9 js0

I: Bus=0003 Vendor=054c Product=09cc Version=8111
N: Name="Sony Interactive Entertainment Wireless Controller"
P: Phys=usb-xhci-hcd.0-1/input3
U: Uniq=
H: Handlers=event6 js1
"""


def test_parse_input_devices_lists_only_joysticks():
    pads = parse_input_devices(INPUT_DEVICES)
    assert pads == [
        {"name": "Sony PLAYSTATION(R)3 Controller", "bus": "Bluetooth", "id": "054c:0268", "uniq": "38:c0:96:91:55:ff"},
        {"name": "Sony Interactive Entertainment Wireless Controller", "bus": "USB", "id": "054c:09cc", "uniq": None},
    ]


def test_friendly_name_shows_python_script():
    from daemon.system import friendly_name
    assert friendly_name("python3", ["/venv/bin/python3", "/home/x/launcher.py"]) == "launcher.py"
    assert friendly_name("python3", ["/usr/bin/python3", "-I", "/home/x/scripts/ingame-status.py"]) == "ingame-status.py"
    assert friendly_name("smbd", ["/usr/sbin/smbd", "--foreground"]) == "smbd"


@pytest.mark.skipif(not Path("/sys/class/thermal/thermal_zone0/temp").exists(),
                    reason="reads the live sensors of the Pi; this machine has no thermal_zone0")
def test_system_live_endpoint_returns_snapshot():
    from fastapi.testclient import TestClient

    from daemon.main import app

    body = TestClient(app).get("/system/live").json()
    assert {"temp_c", "cpu", "memory", "disks", "network", "controllers", "processes", "services"} <= body.keys()


def test_group_processes_sums_same_name_and_sorts_by_cpu():
    from daemon.system import group_processes
    prev = {"1": ("chromium", 100, 0), "2": ("chromium", 100, 0), "3": ("smbd", 100, 0)}
    cur = {"1": ("chromium", 150, 100.0), "2": ("chromium", 130, 50.0), "3": ("smbd", 110, 20.0), "4": ("new", 999, 5.0)}
    rows = group_processes(cur, prev, dt=1.0, hz=100)
    assert rows[0] == {"name": "chromium", "count": 2, "cpu": 80.0, "rss_mb": 150}
    assert rows[1] == {"name": "smbd", "count": 1, "cpu": 10.0, "rss_mb": 20}
    assert rows[2]["cpu"] == 0.0  # processo novo: sem leitura anterior, sem taxa
