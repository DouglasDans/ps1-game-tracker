"""Leitura do journal para a aba Sistema (Histórico, Alertas, Por sessão).

O journal é a fonte única de logs do Pi (30 dias): sys-monitor (linha de base
a cada 5 min), ingame-status (a cada 30s durante o jogo; chamava session-perf
até 2026-10-17), ps1-tracker (session_start/end) e alert (log-sentinel). Todos
logam no formato chave=valor; aqui só lemos e agregamos — nada é gravado em
banco. O daemon roda como douglasdans, que está no grupo adm (lê o journal).

As funções de agregação recebem entradas já lidas ({ident, msg, t, priority})
para serem testáveis sem journalctl.
"""
import json
import re
import subprocess

from daemon.db import MIN_SESSION_S

IDENTIFIERS = ["sys-monitor", "ingame-status", "session-perf", "ps1-tracker", "alert"]
PERF_IDENTS = ("ingame-status", "session-perf")

_KV_RE = re.compile(r'(\w+)=("(?:[^"\\]|\\.)*"|\S+)')
_NUM_RE = re.compile(r"-?\d+(?:\.\d+)?")
_SESSION_EVENT_RE = re.compile(r"\b(session_start|session_resume|session_end) ")
_SEVERITY = {3: "error", 4: "warning"}


def read_entries(since: str) -> list[dict]:
    """Entradas dos identificadores acima desde `since` (ex.: "-24h")."""
    args = ["journalctl", "-o", "json", "-q", "--no-pager", "--since", since,
            "--output-fields=MESSAGE,SYSLOG_IDENTIFIER,PRIORITY"]
    for ident in IDENTIFIERS:
        args += ["-t", ident]
    out = subprocess.run(args, capture_output=True, text=True, timeout=10).stdout
    entries = []
    for line in out.splitlines():
        try:
            raw = json.loads(line)
        except ValueError:
            continue
        msg = raw.get("MESSAGE")
        if not isinstance(msg, str):  # mensagem binária vem como lista de bytes
            continue
        entries.append({
            "ident": raw.get("SYSLOG_IDENTIFIER", ""),
            "msg": msg,
            "t": int(raw["__REALTIME_TIMESTAMP"]) / 1e6,
            "priority": int(raw.get("PRIORITY", 6)),
        })
    return entries


def parse_kv(msg: str) -> dict[str, str]:
    return {k: v[1:-1].replace('\\"', '"') if v.startswith('"') else v for k, v in _KV_RE.findall(msg)}


def _num(value: str | None) -> float | None:
    """"61.2C" / "38%" / "1.2MB/s" -> número; "1200/4000MB" -> 1200."""
    if not value:
        return None
    m = _NUM_RE.search(value)
    return float(m.group()) if m else None


def _session_id(value: str | None) -> int | None:
    return int(value) if value and value.isdigit() else None


def alerts(entries: list[dict]) -> list[dict]:
    result = []
    for e in entries:
        if e["ident"] != "alert" or not e["msg"].startswith("ALERTA"):
            continue
        kv = parse_kv(e["msg"])
        result.append({
            "t": e["t"],
            "rule": kv.get("rule"),
            "severity": _SEVERITY.get(e["priority"], "warning"),
            "session": _session_id(kv.get("session")),
            "game": kv.get("game"),
            "source": kv.get("source"),
            "src": kv.get("src"),
            "msg": kv.get("msg"),
        })
    return sorted(result, key=lambda a: a["t"], reverse=True)


def _sample(e: dict) -> dict | None:
    """Temperatura, memória usada, CPU e throttling de uma linha de métrica."""
    kv = parse_kv(e["msg"])
    if "temp" not in kv:
        return None
    mem = kv.get("mem", "")
    used = total = None
    if "/" in mem:
        first, rest = mem.split("/", 1)
        total = _num(rest)
        # sys-monitor loga DISPONÍVEL/total; ingame-status loga USADO/total
        used = total - _num(first) if e["ident"] == "sys-monitor" else _num(first)
    return {
        "temp": _num(kv.get("temp")),
        "mem_used_mb": used,
        "cpu": _num(kv.get("cpu")) if e["ident"] in PERF_IDENTS else None,
        "throttled": kv.get("throttled", "0x0") not in ("0x0", "?"),
    }


def _sessions(entries: list[dict], end: float) -> list[dict]:
    """Faixas de sessão (start..end) a partir dos eventos do ps1-tracker.
    Sessões fechadas com menos de MIN_SESSION_S são "abri pra testar" e ficam
    de fora, igual às estatísticas (view played_sessions)."""
    spans, open_ = [], {}
    for e in sorted(entries, key=lambda e: e["t"]):
        if e["ident"] != "ps1-tracker":
            continue
        m = _SESSION_EVENT_RE.search(e["msg"])
        if not m:
            continue
        kv = parse_kv(e["msg"][m.start():])
        sid = _session_id(kv.get("session"))
        if sid is None:
            continue
        if m.group(1) == "session_end":
            started = open_.pop(sid, None)
            if started and e["t"] - started[0] >= MIN_SESSION_S:
                spans.append({"session": sid, "game": started[1], "start": started[0], "end": e["t"]})
        elif sid not in open_:
            open_[sid] = (e["t"], kv.get("game"))
    spans += [{"session": sid, "game": game, "start": t, "end": end} for sid, (t, game) in open_.items()]
    return sorted(spans, key=lambda s: s["start"])


def history(entries: list[dict], start: float, end: float, buckets: int = 240) -> dict:
    """Série em `buckets` baldes iguais: temperatura máxima (pico importa),
    memória e CPU médias, e se houve throttling no balde."""
    width = (end - start) / buckets
    acc = [{"temp": [], "mem": [], "cpu": [], "throttled": False} for _ in range(buckets)]
    for e in entries:
        if e["ident"] not in ("sys-monitor", *PERF_IDENTS) or not start <= e["t"] < end:
            continue
        s = _sample(e)
        if not s:
            continue
        b = acc[min(int((e["t"] - start) / width), buckets - 1)]
        for key, field in (("temp", "temp"), ("mem", "mem_used_mb"), ("cpu", "cpu")):
            if s[field] is not None:
                b[key].append(s[field])
        b["throttled"] |= s["throttled"]

    def avg(values):
        return round(sum(values) / len(values), 1) if values else None

    points = [{
        "t": start + (i + 0.5) * width,
        "temp": max(b["temp"]) if b["temp"] else None,
        "mem_used_mb": avg(b["mem"]),
        "cpu": avg(b["cpu"]),
        "throttled": b["throttled"],
    } for i, b in enumerate(acc)]
    return {"start": start, "end": end, "points": points, "sessions": _sessions(entries, end)}


def _perf_by_session(entries: list[dict]) -> dict[int, list[tuple[dict, dict]]]:
    grouped: dict[int, list] = {}
    for e in entries:
        if e["ident"] not in PERF_IDENTS:
            continue
        kv = parse_kv(e["msg"])
        sid = _session_id(kv.get("session"))
        if sid is not None:
            grouped.setdefault(sid, []).append((e, kv))
    return grouped


def session_list(entries: list[dict]) -> list[dict]:
    """Sessões que têm métricas de desempenho, mais recente primeiro."""
    result = []
    for sid, rows in _perf_by_session(entries).items():
        times = [e["t"] for e, _ in rows]
        temps = [t for t in (_num(kv.get("temp")) for _, kv in rows) if t is not None]
        result.append({
            "session": sid,
            "game": rows[0][1].get("game"),
            "source": rows[0][1].get("source"),
            "start": min(times),
            "end": max(times),
            "samples": len(rows),
            "temp_max": max(temps) if temps else None,
        })
    return sorted(result, key=lambda s: s["start"], reverse=True)


def session_perf(entries: list[dict], session: int) -> dict | None:
    rows = _perf_by_session(entries).get(session)
    if not rows:
        return None
    rows.sort(key=lambda r: r[0]["t"])
    points = []
    for e, kv in rows:
        mem = kv.get("mem", "")
        points.append({
            "t": e["t"],
            "temp": _num(kv.get("temp")),
            "cpu": _num(kv.get("cpu")),
            "emu_cpu": _num(kv.get("emu_cpu")),
            "emu_rss_mb": _num(kv.get("emu_rss")),
            "mem_used_mb": _num(mem.split("/")[0]) if "/" in mem else None,
            "disk_read": _num(kv.get("disk_read")),
            "eth0_tx": _num(kv.get("eth0_tx")),
            "throttled": kv.get("throttled", "0x0") not in ("0x0", "?"),
        })
    first = rows[0][1]
    return {"session": session, "game": first.get("game"), "source": first.get("source"), "points": points}
