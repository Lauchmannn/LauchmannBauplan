from __future__ import annotations

from pathlib import Path
import io
import shutil
import tempfile
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parent
REPO = "Lauchmannn/LauchmannBauplan"
BRANCH = "main"
RAW_BASE = f"https://raw.githubusercontent.com/{REPO}/{BRANCH}"
ARCHIVE_URL = f"https://github.com/{REPO}/archive/refs/heads/{BRANCH}.zip"
PROTECTED = {"projects", "schematics", "user-data", "worlds", "local", ".git"}
SKIP_FILES = {"start.bat", ".gitignore"}


def local_version() -> str:
    try:
        return (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    except Exception:
        return "0.0.0"


def remote_version() -> str:
    req = urllib.request.Request(f"{RAW_BASE}/VERSION", headers={"User-Agent": "LauchmannBauplan-Updater"})
    with urllib.request.urlopen(req, timeout=5) as r:
        return r.read().decode("utf-8").strip()


def download_archive() -> bytes:
    req = urllib.request.Request(ARCHIVE_URL, headers={"User-Agent": "LauchmannBauplan-Updater"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read()


def install_archive(data: bytes) -> None:
    with tempfile.TemporaryDirectory(prefix="lauchmann-update-") as td:
        tdir = Path(td)
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            zf.extractall(tdir)
        roots = [p for p in tdir.iterdir() if p.is_dir()]
        if len(roots) != 1:
            raise RuntimeError("Update-Archiv hat ein unerwartetes Format.")
        src_root = roots[0]
        for src in src_root.rglob("*"):
            rel = src.relative_to(src_root)
            if not rel.parts:
                continue
            if rel.parts[0] in PROTECTED:
                continue
            if len(rel.parts) == 1 and rel.name in SKIP_FILES:
                continue
            if ".github" in rel.parts:
                continue
            dst = ROOT / rel
            if src.is_dir():
                dst.mkdir(parents=True, exist_ok=True)
            else:
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dst)


def main() -> int:
    print("Prüfe auf Updates …")
    try:
        lv = local_version()
        rv = remote_version()
        if lv == rv:
            print(f"Version {lv} ist aktuell.")
            return 0
        print(f"Update gefunden: {lv} -> {rv}")
        install_archive(download_archive())
        print(f"Update auf Version {rv} abgeschlossen.")
    except Exception as e:
        print(f"Updateprüfung übersprungen: {e}")
        print("Die vorhandene lokale Version wird gestartet.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
