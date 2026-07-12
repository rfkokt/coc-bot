#!/usr/bin/env python3
"""Persistensi ke Postgres (VPS Oracle, via Tailscale). psycopg v3.

Nyimpen 3 hal:
  - accounts    : akun COC (dari localStorage frontend) + village json + analysis
  - loot_stats  : loot lifetime per akun (mirror stats.json)
  - research    : hasil deep research per akun/TH

DSN dibaca dari research_config (key "db_dsn"). Kalau DB unreachable,
fungsi save* nelan error (return None) biar app tetap jalan tanpa DB.
"""
import json
from datetime import datetime

from research_config import load_config

try:
    import psycopg
    _HAS_PG = True
except ImportError:
    _HAS_PG = False

_SCHEMA = """
CREATE TABLE IF NOT EXISTS accounts (
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    tag         TEXT,
    th_level    INT,
    village     JSONB,
    analysis    JSONB,
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS loot_stats (
    account     TEXT PRIMARY KEY,
    attacks     BIGINT DEFAULT 0,
    gold        BIGINT DEFAULT 0,
    elixir      BIGINT DEFAULT 0,
    dark        BIGINT DEFAULT 0,
    seconds     BIGINT DEFAULT 0,
    since       TIMESTAMPTZ,
    last        TIMESTAMPTZ,
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS research (
    id          BIGSERIAL PRIMARY KEY,
    account_id  TEXT,
    account_name TEXT,
    th_level    INT,
    query       TEXT,
    report      TEXT,
    sources     JSONB,
    stats       JSONB,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_research_account ON research(account_id, created_at DESC);
"""


def _dsn():
    return load_config().get("db_dsn", "")


def available() -> bool:
    return _HAS_PG and bool(_dsn())


def _conn():
    return psycopg.connect(_dsn(), connect_timeout=8)


def init_db() -> bool:
    """Bikin tabel kalau belum ada. Return True kalau sukses."""
    if not available():
        return False
    try:
        with _conn() as c:
            c.execute(_SCHEMA)
            c.commit()
        return True
    except Exception as e:
        print(f"[db] init failed: {e}")
        return False


def _parse_ts(v):
    if not v:
        return None
    try:
        return datetime.fromisoformat(v)
    except (ValueError, TypeError):
        return None


# ── Accounts ─────────────────────────────────────────────────────────────

def upsert_accounts(accounts: list) -> int:
    """Simpan/replace daftar akun (dari frontend localStorage). Return jumlah tersimpan."""
    if not available() or not accounts:
        return 0
    try:
        with _conn() as c:
            for a in accounts:
                village = a.get("json")
                if isinstance(village, str):
                    try:
                        village = json.loads(village)
                    except (ValueError, TypeError):
                        village = None
                c.execute(
                    """INSERT INTO accounts (id, name, tag, th_level, village, analysis, updated_at)
                       VALUES (%s,%s,%s,%s,%s,%s, now())
                       ON CONFLICT (id) DO UPDATE SET
                         name=EXCLUDED.name, tag=EXCLUDED.tag, th_level=EXCLUDED.th_level,
                         village=EXCLUDED.village, analysis=EXCLUDED.analysis, updated_at=now()""",
                    (str(a.get("id")), a.get("name", "?"), a.get("tag"),
                     a.get("th_level"),
                     psycopg.types.json.Jsonb(village) if village is not None else None,
                     psycopg.types.json.Jsonb(a.get("result")) if a.get("result") is not None else None),
                )
            c.commit()
        return len(accounts)
    except Exception as e:
        print(f"[db] upsert_accounts failed: {e}")
        return 0


def list_accounts() -> list:
    if not available():
        return []
    try:
        with _conn() as c:
            rows = c.execute(
                "SELECT id,name,tag,th_level,updated_at FROM accounts ORDER BY name"
            ).fetchall()
        return [{"id": r[0], "name": r[1], "tag": r[2], "th_level": r[3],
                 "updated_at": r[4].isoformat() if r[4] else None} for r in rows]
    except Exception as e:
        print(f"[db] list_accounts failed: {e}")
        return []


# ── Loot stats ───────────────────────────────────────────────────────────

def sync_loot(stats_accounts: dict) -> int:
    """Mirror stats.json['accounts'] ke DB. Return jumlah akun."""
    if not available() or not stats_accounts:
        return 0
    try:
        with _conn() as c:
            for name, s in stats_accounts.items():
                c.execute(
                    """INSERT INTO loot_stats (account,attacks,gold,elixir,dark,seconds,since,last,updated_at)
                       VALUES (%s,%s,%s,%s,%s,%s,%s,%s, now())
                       ON CONFLICT (account) DO UPDATE SET
                         attacks=EXCLUDED.attacks, gold=EXCLUDED.gold, elixir=EXCLUDED.elixir,
                         dark=EXCLUDED.dark, seconds=EXCLUDED.seconds, since=EXCLUDED.since,
                         last=EXCLUDED.last, updated_at=now()""",
                    (name, s.get("attacks", 0), s.get("gold", 0), s.get("elixir", 0),
                     s.get("dark", 0), s.get("seconds", 0),
                     _parse_ts(s.get("since")), _parse_ts(s.get("last"))),
                )
            c.commit()
        return len(stats_accounts)
    except Exception as e:
        print(f"[db] sync_loot failed: {e}")
        return 0


def list_loot() -> list:
    if not available():
        return []
    try:
        with _conn() as c:
            rows = c.execute(
                """SELECT account,attacks,gold,elixir,dark,seconds,since,last
                   FROM loot_stats ORDER BY gold DESC"""
            ).fetchall()
        return [{"account": r[0], "attacks": r[1], "gold": r[2], "elixir": r[3],
                 "dark": r[4], "seconds": r[5],
                 "since": r[6].isoformat() if r[6] else None,
                 "last": r[7].isoformat() if r[7] else None} for r in rows]
    except Exception as e:
        print(f"[db] list_loot failed: {e}")
        return []


# ── Research ─────────────────────────────────────────────────────────────

def save_research(account_id, account_name, th_level, query, result) -> int:
    """Simpan 1 hasil research. Return id baris, atau None."""
    if not available() or not result:
        return None
    try:
        with _conn() as c:
            row = c.execute(
                """INSERT INTO research (account_id,account_name,th_level,query,report,sources,stats)
                   VALUES (%s,%s,%s,%s,%s,%s,%s) RETURNING id""",
                (account_id, account_name, th_level, query,
                 result.get("report", ""),
                 psycopg.types.json.Jsonb(result.get("sources", [])),
                 psycopg.types.json.Jsonb(result.get("stats", {}))),
            ).fetchone()
            c.commit()
        return row[0]
    except Exception as e:
        print(f"[db] save_research failed: {e}")
        return None


def list_research(account_id=None, limit=50) -> list:
    if not available():
        return []
    try:
        with _conn() as c:
            if account_id:
                rows = c.execute(
                    """SELECT id,account_name,th_level,query,report,sources,stats,created_at
                       FROM research WHERE account_id=%s ORDER BY created_at DESC LIMIT %s""",
                    (account_id, limit)).fetchall()
            else:
                rows = c.execute(
                    """SELECT id,account_name,th_level,query,report,sources,stats,created_at
                       FROM research ORDER BY created_at DESC LIMIT %s""",
                    (limit,)).fetchall()
        return [{"id": r[0], "account_name": r[1], "th_level": r[2], "query": r[3],
                 "report": r[4], "sources": r[5], "stats": r[6],
                 "created_at": r[7].isoformat() if r[7] else None} for r in rows]
    except Exception as e:
        print(f"[db] list_research failed: {e}")
        return []


def update_research(rid, query=None, report=None) -> bool:
    """UPDATE report/query 1 baris research. Return True kalau ada yg keupdate."""
    if not available() or not rid:
        return False
    sets, vals = [], []
    if query is not None:
        sets.append("query=%s"); vals.append(query)
    if report is not None:
        sets.append("report=%s"); vals.append(report)
    if not sets:
        return False
    vals.append(rid)
    try:
        with _conn() as c:
            cur = c.execute(f"UPDATE research SET {', '.join(sets)} WHERE id=%s", vals)
            c.commit()
            return cur.rowcount > 0
    except Exception as e:
        print(f"[db] update_research failed: {e}")
        return False


def get_research_by_id(rid) -> dict | None:
    """Fetch 1 row research by id."""
    if not available() or not rid:
        return None
    try:
        with _conn() as c:
            r = c.execute(
                """SELECT id,account_name,th_level,query,report,sources,stats,created_at
                   FROM research WHERE id=%s""", (rid,)).fetchone()
        if not r:
            return None
        return {"id": r[0], "account_name": r[1], "th_level": r[2], "query": r[3],
                "report": r[4], "sources": r[5], "stats": r[6] or {},
                "created_at": r[7].isoformat() if r[7] else None}
    except Exception as e:
        print(f"[db] get_research_by_id failed: {e}")
        return None

def set_translation(rid, lang: str, text: str) -> bool:
    """Cache translation di stats.translations[lang] (JSONB, no migration)."""
    if not available() or not rid:
        return False
    try:
        with _conn() as c:
            row = c.execute("SELECT stats FROM research WHERE id=%s", (rid,)).fetchone()
            if not row:
                return False
            stats = row[0] or {}
            stats.setdefault("translations", {})[lang] = text
            c.execute("UPDATE research SET stats=%s WHERE id=%s",
                      (psycopg.types.json.Jsonb(stats), rid))
            c.commit()
            return True
    except Exception as e:
        print(f"[db] set_translation failed: {e}")
        return False

def delete_research(rid) -> bool:
    if not available() or not rid:
        return False
    try:
        with _conn() as c:
            cur = c.execute("DELETE FROM research WHERE id=%s", (rid,))
            c.commit()
            return cur.rowcount > 0
    except Exception as e:
        print(f"[db] delete_research failed: {e}")
        return False


def delete_account(account_id) -> bool:
    if not available() or not account_id:
        return False
    try:
        with _conn() as c:
            cur = c.execute("DELETE FROM accounts WHERE id=%s", (str(account_id),))
            c.commit()
            return cur.rowcount > 0
    except Exception as e:
        print(f"[db] delete_account failed: {e}")
        return False


if __name__ == "__main__":
    print("db available:", available())
    print("init:", init_db())
    print("accounts:", len(list_accounts()))
    print("loot:", len(list_loot()))
    print("research:", len(list_research()))
