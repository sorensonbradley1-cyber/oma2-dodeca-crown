import subprocess
import time
import os
import shutil
import coherence_bridge
import meridian_east

CHECK_INTERVAL = 30.0
SAMPLER_CMD = ["nohup", "python", os.path.expanduser("~/tengen_sampler.py")]
SAMPLER_LOG = os.path.expanduser("~/sampler.log")


def is_sampler_running():
    res = subprocess.run(["pgrep", "-f", "tengen_sampler.py"], capture_output=True, text=True)
    return res.returncode == 0 and bool(res.stdout.strip())


def restart_sampler():
    subprocess.run(["pkill", "-f", "tengen_sampler.py"], capture_output=True)
    time.sleep(1.0)
    with open(SAMPLER_LOG, "a") as log_f:
        subprocess.Popen(
            ["python", os.path.expanduser("~/tengen_sampler.py")],
            stdout=log_f,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
    time.sleep(2.0)


def notify_commander(title, msg):
    if shutil.which("termux-notification"):
        subprocess.run(["termux-notification", "--title", title, "--content", msg], capture_output=True)
    if shutil.which("termux-tts-speak"):
        subprocess.Popen(["termux-tts-speak", msg], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def run_watchdog():
    print("[*] Phase 2 Watchdog online (30s cycle, WAL-safe, Ctrl+C to stop)...")
    while True:
        try:
            running = is_sampler_running()
            drift, status, _ = meridian_east.audit_and_harden_nodes()

            if not running or status in ("STALE", "OFFLINE") or drift > 2.0:
                reason = "process stopped" if not running else f"status={status}, drift={drift}s"
                restart_sampler()
                msg = f"Watchdog auto-healed sampler ({reason}); 3D-12D phase lock restored."
                meridian_east.log_dispatch(msg)
                notify_commander("OMA2 Legion Hub // Auto-Heal", msg)
            else:
                coherence_bridge.synthesize_coherence()

        except Exception as e:
            print(f"[!] Watchdog cycle warning: {e}")

        time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    run_watchdog()
