import sqlite3
import time
import math
import os
from datetime import datetime

HUB_DB = os.path.expanduser("~/meridian_east.db")
MAX_SNAPSHOTS = 1000

TIERS = [
    {"tier": "3D",  "db": "~/tengen_telemetry.db", "table": "mesh_telemetry",    "ts_col": "timestamp"},
    {"tier": "4D",  "db": "~/tesseract_tengen.db", "table": "mesh_4d_telemetry", "ts_col": "timestamp"},
    {"tier": "5D",  "db": "~/penta_tengen.db",     "table": "mesh_5d",           "ts_col": "ts"},
    {"tier": "6D",  "db": "~/hexa_tengen.db",      "table": "mesh_6d",           "ts_col": "ts"},
    {"tier": "7D",  "db": "~/hepta_tengen.db",     "table": "mesh_7d",           "ts_col": "ts"},
    {"tier": "8D",  "db": "~/octa_tengen.db",      "table": "mesh_8d",           "ts_col": "ts"},
    {"tier": "9D",  "db": "~/nona_tengen.db",      "table": "mesh_9d",           "ts_col": "ts"},
    {"tier": "10D", "db": "~/deca_tengen.db",      "table": "mesh_10d",          "ts_col": "ts"},
    {"tier": "11D", "db": "~/hendeca_tengen.db",   "table": "mesh_11d",          "ts_col": "ts"},
    {"tier": "12D", "db": "~/dodeca_tengen.db",    "table": "mesh_12d",          "ts_col": "ts"},
]


def init_coherence_table():
    conn = sqlite3.connect(HUB_DB, timeout=5.0)
    cur = conn.cursor()
    cur.execute("PRAGMA journal_mode=WAL;")
    cur.execute("PRAGMA synchronous=NORMAL;")
    cur.execute("PRAGMA busy_timeout=5000;")
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS coherence_bridge (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts REAL NOT NULL,
            local_time TEXT NOT NULL,
            active_tiers INTEGER NOT NULL,
            drift_sec REAL NOT NULL,
            torus_mean REAL NOT NULL,
            torus_std REAL NOT NULL,
            coherence_pct REAL NOT NULL,
            state TEXT NOT NULL
        );
        """
    )
    cur.execute("CREATE INDEX IF NOT EXISTS idx_coherence_ts ON coherence_bridge(ts);")
    conn.commit()
    conn.close()


def read_tier_latest(node):
    path = os.path.expanduser(node["db"])
    if not os.path.exists(path):
        return None
    uri = f"file:{path}?mode=ro"
    conn = sqlite3.connect(uri, uri=True, timeout=5.0)
    cur = conn.cursor()
    cols = [r[1] for r in cur.execute(f"PRAGMA table_info({node['table']});").fetchall()]
    torus_col = next((c for c in cols if "torus" in c), None)
    if not torus_col:
        conn.close()
        return None
    row = cur.execute(
        f"SELECT {node['ts_col']}, {torus_col} FROM {node['table']} ORDER BY {node['ts_col']} DESC LIMIT 1;"
    ).fetchone()
    conn.close()
    if not row or row[0] is None or row[1] is None:
        return None
    return {"tier": node["tier"], "ts": float(row[0]), "torus": float(row[1])}


def synthesize_coherence():
    init_coherence_table()
    now = time.time()
    local_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    readings = [r for node in TIERS if (r := read_tier_latest(node))]

    if not readings:
        print("[!] No active tiers found.")
        return None

    timestamps = [r["ts"] for r in readings]
    torus_vals = [r["torus"] for r in readings]

    drift = round(max(timestamps) - min(timestamps), 3)
    age = round(now - max(timestamps), 1)
    n = len(torus_vals)
    t_mean = round(sum(torus_vals) / n, 4)
    variance = sum((v - t_mean) ** 2 for v in torus_vals) / n
    t_std = round(math.sqrt(variance), 4)

    # Combine temporal lock score (penalizes drift > 0 or stale age > 20s)
    # and harmonic tightness across the 10 torus vectors
    time_factor = max(0.0, 1.0 - (drift / 5.0) - max(0.0, (age - 20.0) / 30.0))
    harmonic_factor = max(0.0, 1.0 - (t_std / 0.50))
    coherence_pct = round((0.6 * time_factor + 0.4 * harmonic_factor) * 100.0, 2)

    if len(readings) == 10 and coherence_pct >= 85.0 and age <= 25.0:
        state = "HARMONIC_LOCK"
    elif age > 25.0:
        state = "STALE"
    else:
        state = "CONVERGING"

    conn = sqlite3.connect(HUB_DB, timeout=5.0)
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO coherence_bridge (ts, local_time, active_tiers, drift_sec, torus_mean, torus_std, coherence_pct, state)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?);
        """,
        (now, local_str, len(readings), drift, t_mean, t_std, coherence_pct, state),
    )
    cur.execute(
        f"DELETE FROM coherence_bridge WHERE id NOT IN "
        f"(SELECT id FROM coherence_bridge ORDER BY id DESC LIMIT {MAX_SNAPSHOTS});"
    )
    conn.commit()
    conn.close()

    print(f"[{local_str}] BRIDGE // {state} | Coherence: {coherence_pct}% | Tiers: {len(readings)}/10 | Drift: {drift}s")
    print(f"  Torus Mean: {t_mean:+.4f} | Harmonic Spread (σ): {t_std:.4f}")
    bar = " ".join(f"{r['tier']}:{r['torus']:+.3f}" for r in readings)
    print(f"  Vector Bar: {bar}")
    return coherence_pct


if __name__ == "__main__":
    synthesize_coherence()
