import os
import subprocess

def get_vitals():
    # 1. Real RAM usage % (/proc/meminfo with 'free' fallback)
    ram_pct = 0.0
    try:
        mem = {}
        with open("/proc/meminfo") as f:
            for line in f:
                parts = line.split()
                if len(parts) >= 2:
                    mem[parts[0].rstrip(":")] = int(parts[1])
        total_ram = mem.get("MemTotal", 1)
        avail_ram = mem.get("MemAvailable", total_ram)
        ram_pct = round(((total_ram - avail_ram) / total_ram) * 100.0, 2)
    except Exception:
        try:
            out = subprocess.check_output(["free", "-m"], text=True).splitlines()[1].split()
            ram_pct = round((float(out[2]) / float(out[1])) * 100.0, 2)
        except Exception:
            pass

    # 2. Real 1-min CPU load (/proc/loadavg with 'uptime' fallback)
    load_1m = 0.0
    try:
        with open("/proc/loadavg") as f:
            load_1m = round(float(f.read().split()[0]), 2)
    except Exception:
        try:
            up = subprocess.check_output(["uptime"], text=True)
            load_1m = round(float(up.split("load average:")[1].split(",")[0].strip()), 2)
        except Exception:
            load_1m = float(os.cpu_count() or 0)

    # 3. Real storage usage %
    st = os.statvfs(os.path.expanduser("~"))
    disk_pct = round(((st.f_blocks - st.f_bavail) / st.f_blocks) * 100.0, 2)

    # 4. Real network ping latency (ms)
    ping_ms = -1.0
    try:
        out = subprocess.check_output(
            ["ping", "-c", "1", "-W", "1", "1.1.1.1"],
            stderr=subprocess.DEVNULL, text=True
        )
        for token in out.split():
            if token.startswith("time="):
                ping_ms = round(float(token.split("=")[1]), 2)
    except Exception:
        pass

    return {
        "ram_pct": ram_pct,
        "load_1m": load_1m,
        "disk_pct": disk_pct,
        "ping_ms": ping_ms,
    }

if __name__ == "__main__":
    print(get_vitals())
