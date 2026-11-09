"""Lifetime stats counter PER-AKUN — JSON flat, no DB (ponytail: cukup buat counter).
Dipanggil bot.py tiap battle selesai + tiap siklus (buat akumulasi waktu).
Struktur: {"accounts": {"<nama>": {attacks,gold,elixir,dark,seconds,since,last}}}"""
import json, os
from datetime import datetime

F = os.path.join(os.path.dirname(__file__), "stats.json")
DEFAULT_ACCOUNT = "unknown"


def _now():
    return datetime.now().isoformat(timespec="seconds")


def _blank(name):
    return {"attacks": 0, "gold": 0, "elixir": 0, "dark": 0,
            "seconds": 0, "since": _now(), "last": _now()}


MAX_RAID_GOLD = 2_500_000
MAX_RAID_ELIXIR = 2_500_000
MAX_RAID_DARK = 15_000


def normalize_account_name(name):
    if not name or str(name).strip().lower() in ("unknown", "none", ""):
        return DEFAULT_ACCOUNT
    # standard capitalize, misal "ziP" -> "Zip", "ryu" -> "Ryu"
    return str(name).strip().title()


def load():
    try:
        data = json.load(open(F))
    except (FileNotFoundError, json.JSONDecodeError):
        return {"accounts": {}}
    # migrasi format lama (stats flat global) → taruh di akun "legacy"
    if "accounts" not in data:
        old = {k: data.get(k, 0) for k in ("attacks", "gold", "elixir", "dark")}
        old.update(seconds=0, since=data.get("since", _now()), last=data.get("last", _now()))
        return {"accounts": {"legacy": old}}

    # Deduplicate & normalize account keys (misal "ziP" dan "zip" jadi satu "Zip")
    raw_accs = data.get("accounts", {})
    norm_accs = {}
    for raw_name, val in raw_accs.items():
        nm = normalize_account_name(raw_name) if raw_name != "legacy" else "legacy"
        if nm not in norm_accs:
            norm_accs[nm] = val
        else:
            cur = norm_accs[nm]
            cur["attacks"] += val.get("attacks", 0)
            cur["gold"] += val.get("gold", 0)
            cur["elixir"] += val.get("elixir", 0)
            cur["dark"] += val.get("dark", 0)
            cur["seconds"] += val.get("seconds", 0)
            cur["last"] = max(cur.get("last", ""), val.get("last", ""))
    data["accounts"] = norm_accs
    return data


def _acc(data, name):
    norm = normalize_account_name(name) if name != "legacy" else "legacy"
    return data["accounts"].setdefault(norm, _blank(norm))


def _save(data):
    tmp = F + ".tmp"
    json.dump(data, open(tmp, "w"), indent=2)   # write-tmp+rename: ga korup kalau mati di tengah
    os.replace(tmp, F)


def bump(account=DEFAULT_ACCOUNT, gold=0, elixir=0, dark=0, attack=0):
    account = normalize_account_name(account)
    # Sanity clamping: 1 serangan multiplayer di COC mustahil melebihi batas ini
    g = max(0, min(int(gold), MAX_RAID_GOLD))
    e = max(0, min(int(elixir), MAX_RAID_ELIXIR))
    d = max(0, min(int(dark), MAX_RAID_DARK))

    data = load()
    a = _acc(data, account)
    a["attacks"] += attack
    a["gold"] += g
    a["elixir"] += e
    a["dark"] += d
    a["last"] = _now()
    _save(data)
    return data


def add_time(account=DEFAULT_ACCOUNT, seconds=0):
    """Akumulasi durasi bot jalan buat akun ini (dipanggil tiap siklus)."""
    if seconds <= 0:
        return
    account = normalize_account_name(account)
    data = load()
    a = _acc(data, account)
    a["seconds"] += int(seconds)
    a["last"] = _now()
    _save(data)


if __name__ == "__main__":   # ponytail: self-check — per-akun kepisah, waktu keakumulasi
    import tempfile
    F = tempfile.mktemp(suffix=".json")
    assert load()["accounts"] == {}
    bump("A", gold=1000, attack=1)
    bump("A", gold=500, elixir=200, attack=1)
    bump("B", dark=99, attack=1)
    add_time("A", 120)
    add_time("A", 60)
    s = load()["accounts"]
    assert s["A"]["attacks"] == 2 and s["A"]["gold"] == 1500 and s["A"]["seconds"] == 180, s
    assert s["B"]["dark"] == 99 and s["B"]["gold"] == 0, s
    os.remove(F)
    print("ok")
