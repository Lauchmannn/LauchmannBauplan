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
import hashlib
import tempfile
import shutil

from litematic import convert_litematic, CONVERTER_VERSION
from textures import TextureLibrary

ROOT = Path(__file__).resolve().parent
PORT = 8770
MAX_UPLOAD = 100 * 1024 * 1024
TEXTURES = TextureLibrary()
IMPORT_LOCK = threading.Lock()

mimetypes.add_type("application/octet-stream", ".bin")


def current_project(project_dir):
    """Refresh legacy generated geometry, keeping the source, slug and browser progress."""
    meta_path = project_dir / "metadata.json"
    with IMPORT_LOCK:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        if meta.get("converterVersion") == CONVERTER_VERSION:
            return meta
        sources = [ROOT / "schematics" / f"{project_dir.name}.litematic"]
        source_name = meta.get("sourceFile")
        if isinstance(source_name, str) and Path(source_name).name == source_name:
            sources.append(ROOT / "schematics" / source_name)
        source = next((p for p in sources if p.resolve().is_relative_to((ROOT / "schematics").resolve()) and p.is_file()), None)
        if source is None:
            return {**meta, "needsReimport": True}
        try:
            with tempfile.TemporaryDirectory(prefix="lauchmann-refresh-") as td:
                updated = convert_litematic(source, Path(td), preferred_slug=project_dir.name)
                updated["sourceFile"] = meta.get("sourceFile", source.name)
                generated = Path(td) / project_dir.name
                # Replace generated data only; preserve any other local files.
                # Metadata is written last so it never advertises partial geometry.
                for path in generated.rglob("*.bin"):
                    target = project_dir / path.relative_to(generated)
                    target.parent.mkdir(parents=True, exist_ok=True)
                    temporary = target.with_suffix(".bin.refresh")
                    shutil.copyfile(path, temporary)
                    os.replace(temporary, target)
                temporary_meta = meta_path.with_suffix(".json.refresh")
                temporary_meta.write_text(json.dumps(updated, ensure_ascii=False, indent=2), encoding="utf-8")
                os.replace(temporary_meta, meta_path)
                return updated
        except (OSError, ValueError, KeyError, TypeError):
            return {**meta, "needsReimport": True}


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
        if parsed.path == "/api/textures":
            return self._json({"names": sorted(TEXTURES.entries), "available": bool(TEXTURES.entries)})
        if parsed.path == "/api/texture":
            data = TEXTURES.read(parse_qs(parsed.query).get("name", [""])[0])
            if data is None:
                return self._json({"error": "Keine lokale Textur"}, 404)
            self.send_response(200)
            self.send_header("Content-Type", "image/png")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return
        # Only serve app assets and generated viewer data, never source schematics,
        # Git metadata, arbitrary local files or directory listings.
        path = Path(self.translate_path(parsed.path)).resolve()
        allowed = any(path.is_relative_to(ROOT / folder) for folder in ("app", "projects"))
        if allowed and path.is_file() and path.suffix in {".html", ".js", ".css", ".json", ".bin"}:
            if path.name == "metadata.json" and path.parent.parent == ROOT / "projects":
                return self._json(current_project(path.parent))
            return super().do_GET()
        return self._json({"error": "Nicht gefunden"}, 404)

    def do_HEAD(self):
        # Do not inherit unrestricted static file handling for this method.
        self.send_error(405)

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path != "/api/import-litematic":
            return self._json({"error": "Unbekannter Endpunkt"}, 404)
        try:
            origin = self.headers.get("Origin")
            if origin and origin != f"http://127.0.0.1:{PORT}":
                return self._json({"error": "Fremder Ursprung nicht erlaubt"}, 403)
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
            if len(data) != length:
                return self._json({"error": "Unvollständige Datei"}, 400)
            schematics = ROOT / "schematics"
            schematics.mkdir(exist_ok=True)
            digest = hashlib.sha256(data).hexdigest()[:16]
            stem = re.sub(r"[^a-z0-9]+", "-", Path(safe_name).stem.lower()).strip("-")[:64] or "litematic"
            slug = f"{stem}-{digest}"
            # Validate and convert in an isolated staging directory before changing
            # persistent data. Different files with the same title cannot collide.
            with IMPORT_LOCK, tempfile.TemporaryDirectory(prefix="lauchmann-import-") as td:
                staged = Path(td) / safe_name
                staged.write_bytes(data)
                meta = convert_litematic(staged, Path(td) / "projects", preferred_slug=slug)
                target = ROOT / "projects" / slug
                target.parent.mkdir(exist_ok=True)
                if not target.exists():
                    shutil.move(str(Path(td) / "projects" / slug), str(target))
                source = schematics / f"{slug}.litematic"
                if not source.exists():
                    source.write_bytes(data)
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
    try:
        with ThreadingHTTPServer(("127.0.0.1", PORT), Handler) as http:
            threading.Thread(target=open_browser, daemon=True).start()
            print("Lauchmann Bauplan läuft.")
            print(f"Öffne im Browser: http://127.0.0.1:{PORT}/")
            print("Litematic-Dateien kannst du direkt im Viewer importieren.")
            print("Zum Beenden dieses Fenster schließen oder Strg+C drücken.")
            http.serve_forever()
    except KeyboardInterrupt:
        pass
    except OSError as exc:
        raise SystemExit(f"Server konnte nicht starten (Port {PORT} muss frei sein): {exc}")
