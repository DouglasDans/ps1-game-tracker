from daemon.journal import alerts, history, parse_kv, session_list, session_perf

T0 = 1_792_000_000  # epoch em segundos


def entry(ident, msg, t, priority=6):
    return {"ident": ident, "msg": msg, "t": float(t), "priority": priority}


def test_parse_kv_handles_quotes_and_units():
    kv = parse_kv('ALERTA rule=usb_reset session=7 game="Gran Turismo 4" src=kernel msg="usb 4-1: reset"')
    assert kv == {"rule": "usb_reset", "session": "7", "game": "Gran Turismo 4", "src": "kernel", "msg": "usb 4-1: reset"}


def test_alerts_newest_first_with_session_context():
    entries = [
        entry("alert", "log-sentinel iniciando (17 regras, sessão=None)", T0),
        entry("alert", 'ALERTA rule=wifi_drop session=- src=wifi-monitor msg="DEAUTH: x"', T0 + 10, 4),
        entry("alert", 'ALERTA rule=usb_reset session=7 game="GT4" source=samba src=kernel msg="usb reset"', T0 + 20, 4),
    ]
    result = alerts(entries)
    assert [a["rule"] for a in result] == ["usb_reset", "wifi_drop"]
    assert result[0] == {"t": T0 + 20, "rule": "usb_reset", "severity": "warning", "session": 7,
                         "game": "GT4", "source": "samba", "src": "kernel", "msg": "usb reset"}
    assert result[1]["session"] is None


def test_history_merges_both_monitors_into_buckets():
    entries = [
        # sys-monitor: mem é DISPONÍVEL/total
        entry("sys-monitor", "temp=55.0C throttled=0x0 mem=3000/4000MB load=0.5 0.4 0.3", T0 + 10),
        # ingame-status: mem é USADO/total, e tem cpu
        entry("ingame-status", 'session=7 game="GT4" source=samba temp=61.0C throttled=0x0 cpu=40% mem=1200/4000MB', T0 + 20),
        entry("ingame-status", 'session=7 game="GT4" source=samba temp=63.0C throttled=0x50000 cpu=60% mem=1400/4000MB', T0 + 80),
        # começou antes da janela (e dura mais que MIN_SESSION_S)
        entry("ps1-tracker", 'INFO daemon.session_manager: session_start session=7 game="GT4" platform=PS2 source=samba file=/x.iso', T0 - 100),
        entry("ps1-tracker", 'INFO daemon.session_manager: session_end session=7 game="GT4" platform=PS2 source=samba', T0 + 90),
    ]
    h = history(entries, start=T0, end=T0 + 100, buckets=2)  # 2 baldes de 50s
    assert h["start"] == T0 and h["end"] == T0 + 100
    first, second = h["points"]
    assert first == {"t": T0 + 25.0, "temp": 61.0, "mem_used_mb": 1100.0, "cpu": 40.0, "throttled": False}
    assert second == {"t": T0 + 75.0, "temp": 63.0, "mem_used_mb": 1400.0, "cpu": 60.0, "throttled": True}
    assert h["sessions"] == [{"session": 7, "game": "GT4", "start": T0 - 100, "end": T0 + 90}]


def test_history_open_session_ends_at_window_end():
    entries = [entry("ps1-tracker", 'session_start session=8 game="CTR" platform=PS1 source=duckstation file=/a.cue', T0 + 5)]
    assert history(entries, start=T0, end=T0 + 60, buckets=1)["sessions"] == [
        {"session": 8, "game": "CTR", "start": T0 + 5, "end": T0 + 60}]


def test_history_empty_bucket_is_none():
    h = history([entry("sys-monitor", "temp=50.0C throttled=0x0 mem=3000/4000MB", T0 + 70)], start=T0, end=T0 + 100, buckets=2)
    assert h["points"][0] == {"t": T0 + 25.0, "temp": None, "mem_used_mb": None, "cpu": None, "throttled": False}


PERF = [
    entry("ingame-status", 'session=7 game="Gran Turismo 4" source=samba temp=58.0C throttled=0x0 cpu=16% freq=2400MHz mem=976/3991MB emu_cpu=2% emu_rss=58MB disk_read=1.2MB/s eth0_rx=0.0MB/s eth0_tx=0.7MB/s', T0),
    entry("session-perf", 'session=7 game="Gran Turismo 4" source=samba temp=56.0C throttled=0x0 cpu=13% freq=2400MHz mem=997/3991MB emu_cpu=0% emu_rss=58MB disk_read=0.0MB/s eth0_rx=0.0MB/s eth0_tx=0.0MB/s', T0 + 30),
    entry("ingame-status", 'session=9 game="CTR" source=duckstation temp=60.0C throttled=0x0 cpu=50% freq=2400MHz mem=1500/3991MB emu_cpu=95% emu_rss=600MB disk_read=0.0MB/s eth0_rx=0.0MB/s eth0_tx=0.0MB/s', T0 + 500),
]


def test_session_list_summarizes_each_session_newest_first():
    assert session_list(PERF) == [
        {"session": 9, "game": "CTR", "source": "duckstation", "start": T0 + 500, "end": T0 + 500, "samples": 1, "temp_max": 60.0},
        {"session": 7, "game": "Gran Turismo 4", "source": "samba", "start": T0, "end": T0 + 30, "samples": 2, "temp_max": 58.0},
    ]


def test_session_perf_returns_numeric_series():
    perf = session_perf(PERF, 7)
    assert perf["game"] == "Gran Turismo 4"
    assert perf["points"][0] == {"t": T0, "temp": 58.0, "cpu": 16.0, "emu_cpu": 2.0, "emu_rss_mb": 58.0,
                                 "mem_used_mb": 976.0, "disk_read": 1.2, "eth0_tx": 0.7, "throttled": False}
    assert len(perf["points"]) == 2
    assert session_perf(PERF, 123) is None


def test_system_endpoints_read_from_journal(monkeypatch):
    from fastapi.testclient import TestClient

    from daemon import journal as journal_mod
    from daemon.main import app

    monkeypatch.setattr(journal_mod, "read_entries", lambda since: PERF)
    client = TestClient(app)
    assert client.get("/system/history?hours=5").status_code == 400
    assert client.get("/system/history?hours=24").json()["points"]
    assert [s["session"] for s in client.get("/system/sessions").json()] == [9, 7]
    assert client.get("/system/sessions/7").json()["game"] == "Gran Turismo 4"
    assert client.get("/system/sessions/123").status_code == 404
    assert client.get("/system/alerts").json() == []


def test_history_drops_closed_sessions_shorter_than_min_session():
    entries = [
        entry("ps1-tracker", 'session_start session=1 game="Teste" platform=PS1 source=duckstation file=/x', T0),
        entry("ps1-tracker", 'session_end session=1 game="Teste" platform=PS1 source=duckstation', T0 + 5),
    ]
    assert history(entries, start=T0, end=T0 + 600, buckets=1)["sessions"] == []
