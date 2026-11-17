import sqlite3
import time
import math
import random
import os

TIER_CONFIGS = [
    {"db": "~/tengen_telemetry.db", "table": "mesh_telemetry",    "amp": 0.35, "jit": 0.018, "is_3d": True},
    {"db": "~/tesseract_tengen.db", "table": "mesh_4d_telemetry", "amp": 0.32, "jit": 0.016},
    {"db": "~/penta_tengen.db",     "table": "mesh_5d",           "amp": 0.30, "jit": 0.015},
    {"db": "~/hexa_tengen.db",      "table": "mesh_6d",           "amp": 0.28, "jit": 0.012},
    {"db": "~/hepta_tengen.db",     "table": "mesh_7d",           "amp": 0.25, "jit": 0.010},
    {"db": "~/octa_tengen.db",      "table": "mesh_8d",           "amp": 0.22, "jit": 0.008},
    {"db": "~/nona_tengen.db",      "table": "mesh_9d",           "amp": 0.18, "jit": 0.006},
    {"db": "~/deca_tengen.db",      "table": "mesh_10d",          "amp": 0.15, "jit": 0.005},
    {"db": "~/hendeca_tengen.db",   "table": "mesh_11d",          "amp": 0.12, "jit": 0.004},
    {"db": "~/dodeca_tengen.db",    "table": "mesh_12d",          "amp": 0.10, "jit": 0.003},
]

MAX_ROWS = 1000
INTERVAL = 10.0

def inspect_tier(cfg):
    path = os.path.expanduser(cfg["db"])
    if not os.path.exists(path):
        return None
    conn = sqlite3.connect(path, timeout=5.0)
    cur = conn.cursor()
    cur.execute("PRAGMA journal_mode=WAL;")
    cur.execute("PRAGMA synchronous=NORMAL;")
    cur.execute("PRAGMA busy_timeout=5000;")
    cols = [row[1] for row in cur.execute(f"PRAGMA table_info({cfg['table']});").fetchall()]
    conn.close()
    if not cols:
        return None
    ts_col = "timestamp" if "timestamp" in cols else "ts"
    torus_col = next((c for c in cols if "torus" in c), None)
    pulse_col = next((c for c in cols if "pulse" in c or "perturbation" in c), None)
    skip = {ts_col, torus_col, pulse_col, "id", "active_workers"}
    vec_cols = [c for c in cols if c not in skip]
    return {**cfg, "path": path, "ts_col": ts_col, "vec_cols": vec_cols, "torus_col": torus_col, "pulse_col": pulse_col}

TIERS = [t for cfg in TIER_CONFIGS if (t := inspect_tier(cfg))]
print(f"[*] Loaded {len(TIERS)} tiers (3D–11D WAL sync, Ctrl+C to stop)...")

try:
    while True:
        now = time.time()
        for tier in TIERS:
            conn = sqlite3.connect(tier["path"], timeout=5.0)
            cur = conn.cursor()

            if tier.get("is_3d"):
                tensor_mean = round(math.sin(now / 10.0) * tier["amp"] + random.uniform(-tier["jit"], tier["jit"]), 4)
                torus = round(tensor_mean + random.uniform(-tier["jit"], tier["jit"]), 4)
                insert_cols = [tier["ts_col"], "active_workers", "tensor_mean", tier["torus_col"], tier["pulse_col"]]
                values = [now, 8, tensor_mean, torus, 0]
            else:
                n = len(tier["vec_cols"])
                vec = [round(math.sin(now / 10.0 + k) * tier["amp"] + random.uniform(-tier["jit"], tier["jit"]), 4) for k in range(n)]
                torus = round((sum(vec) / max(n, 1)) + random.uniform(-tier["jit"], tier["jit"]), 4)
                insert_cols = [tier["ts_col"]] + tier["vec_cols"] + [tier["torus_col"], tier["pulse_col"]]
                values = [now, *vec, torus, 0]

            col_names = ", ".join(insert_cols)
            placeholders = ", ".join(["?"] * len(insert_cols))
            cur.execute(f"INSERT OR REPLACE INTO {tier['table']} ({col_names}) VALUES ({placeholders});", values)

            ts_col = tier["ts_col"]
            cur.execute(
                f"DELETE FROM {tier['table']} WHERE {ts_col} NOT IN "
                f"(SELECT {ts_col} FROM {tier['table']} ORDER BY {ts_col} DESC LIMIT {MAX_ROWS});"
            )
            conn.commit()
            conn.close()

        time.sleep(INTERVAL)
except KeyboardInterrupt:
    print("\n[+] Sampler stopped cleanly.")
