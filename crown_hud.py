import http.server
import socketserver
import json
import sqlite3
import os
import time
import coherence_bridge
import meridian_east
import device_vitals

PORT = 8088
HUB_DB = os.path.expanduser("~/meridian_east.db")
HTML_FILE = os.path.expanduser("~/hud.html")

def get_payload():
    readings = [r for node in coherence_bridge.TIERS if (r := coherence_bridge.read_tier_latest(node))]
    bridge_row, logs = None, []
    if os.path.exists(HUB_DB):
        conn = sqlite3.connect(f"file:{HUB_DB}?mode=ro", uri=True, timeout=5.0)
        cur = conn.cursor()
        try:
            bridge_row = cur.execute(
                "SELECT coherence_pct, state, drift_sec, torus_std FROM coherence_bridge ORDER BY id DESC LIMIT 1;"
            ).fetchone()
            rows = cur.execute(
                "SELECT local_time, status, dispatch_note FROM outpost_log ORDER BY id DESC LIMIT 6;"
            ).fetchall()
            logs = [{"local_time": r[0], "status": r[1], "dispatch_note": r[2]} for r in rows]
        except sqlite3.Error:
            pass
        conn.close()

    return {
        "ts": time.time(),
        "coherence_pct": bridge_row[0] if bridge_row else 0.0,
        "state": bridge_row[1] if bridge_row else "SYNCING",
        "drift_sec": bridge_row[2] if bridge_row else 0.0,
        "torus_std": bridge_row[3] if bridge_row else 0.0,
        "vitals": device_vitals.get_vitals(),
        "tiers": readings,
        "logs": logs,
    }

class HUDHandler(http.server.BaseHTTPRequestHandler):
    def _send(self, code, body, ctype):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/api/telemetry":
            self._send(200, json.dumps(get_payload()).encode("utf-8"), "application/json")
        else:
            page = open(HTML_FILE, "rb").read() if os.path.exists(HTML_FILE) else b"<h1>Missing ~/hud.html</h1>"
            self._send(200, page, "text/html; charset=utf-8")

    def do_POST(self):
        if self.path == "/api/dispatch":
            length = int(self.headers.get("Content-Length", 0))
            raw = self.rfile.read(length).decode("utf-8")
            note = json.loads(raw).get("note", "").strip()
            if note:
                meridian_east.log_dispatch(note)
            self._send(200, json.dumps({"ok": True}).encode("utf-8"), "application/json")

    def log_message(self, format, *args):
        return

class ReusableTCPServer(socketserver.TCPServer):
    allow_reuse_address = True

if __name__ == "__main__":
    with ReusableTCPServer(("127.0.0.1", PORT), HUDHandler) as httpd:
        print(f"[*] Phase 3 Visual HUD live at http://127.0.0.1:{PORT}")
        httpd.serve_forever()
