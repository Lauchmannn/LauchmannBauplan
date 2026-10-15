from __future__ import annotations

from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse, parse_qs
import json
import mimetypes
import os
import re
import threading
import time
import webbrowser

from litematic import convert_litematic

ROOT = Path(__file__).resolve().parent
PORT = 8770
MAX_UPLOAD = 100 * 1024 * 1024

mimetypes.add_type("application/octet-stream", ".bin")


def project_summaries():
    rows = []
    for meta_path in sorted((ROOT / "projects").glob("*/metadata.json")):
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            rows.append({
                "slug": meta.get("slug", meta_path.parent.name),
                "name": meta.get("name", meta_path.parent.name),
                "author": meta.get("author", ""),
                "blockCount": meta.get("blockCount", 0),
                "size": meta.get("size", {}),
                "sourceType": meta.get("sourceType", "Litematic"),
            })
        except Exception:
            pass
    return rows


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def _json(self, obj, status=200):
        data = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/" or parsed.path == "":
            self.path = "/app/index.html"
            return super().do_GET()
        if parsed.path == "/api/projects":
            return self._json(project_summaries())
        return super().do_GET()

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path != "/api/import-litematic":
            return self._json({"error": "Unbekannter Endpunkt"}, 404)
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0:
                return self._json({"error": "Keine Datei empfangen"}, 400)
            if length > MAX_UPLOAD:
                return self._json({"error": "Datei ist größer als 100 MB"}, 413)
            q = parse_qs(parsed.query)
            raw_name = q.get("filename", ["import.litematic"])[0]
            safe_name = re.sub(r"[^A-Za-z0-9._ -]+", "_", Path(raw_name).name)
            if not safe_name.lower().endswith(".litematic"):
                safe_name += ".litematic"
            data = self.rfile.read(length)
            schematics = ROOT / "schematics"
            schematics.mkdir(exist_ok=True)
            target = schematics / safe_name
            target.write_bytes(data)
            meta = convert_litematic(target, ROOT / "projects")
            return self._json({"ok": True, "project": {"slug": meta["slug"], "name": meta["name"], "blockCount": meta["blockCount"]}})
        except Exception as exc:
            return self._json({"error": str(exc)}, 400)

    def end_headers(self):
        if self.path.endswith((".json", ".bin", ".js", ".css", ".html")):
            self.send_header("Cache-Control", "no-cache")
        super().end_headers()

    def log_message(self, fmt, *args):
        if args and len(args) > 1 and str(args[1]).startswith(("4", "5")):
            super().log_message(fmt, *args)


def open_browser():
    time.sleep(0.8)
    webbrowser.open(f"http://127.0.0.1:{PORT}/")


if __name__ == "__main__":
    os.chdir(ROOT)
    (ROOT / "projects").mkdir(exist_ok=True)
    (ROOT / "schematics").mkdir(exist_ok=True)
    (ROOT / "user-data").mkdir(exist_ok=True)
    threading.Thread(target=open_browser, daemon=True).start()
    print("Lauchmann Bauplan läuft.")
    print(f"Öffne im Browser: http://127.0.0.1:{PORT}/")
    print("Litematic-Dateien kannst du direkt im Viewer importieren.")
    print("Zum Beenden dieses Fenster schließen oder Strg+C drücken.")
    try:
        ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
    except KeyboardInterrupt:
        pass
