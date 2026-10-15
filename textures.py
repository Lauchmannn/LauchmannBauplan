"""Read optional textures from an installed Java Edition JAR, never redistribute them."""
from pathlib import Path
import os
import re
import zipfile


class TextureLibrary:
    def __init__(self):
        self.path = None
        self.entries = {}
        explicit = os.environ.get('MINECRAFT_JAR')
        roots = [Path.home() / 'AppData/Roaming/.minecraft', Path.home() / '.minecraft']
        if os.environ.get('APPDATA'):
            roots.insert(0, Path(os.environ['APPDATA']) / '.minecraft')
        candidates = [Path(explicit).expanduser()] if explicit else []
        if not explicit:
            for root in roots:
                candidates.extend((root / 'versions').glob('*/*.jar'))
            candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        for path in candidates:
            try:
                with zipfile.ZipFile(path) as jar:
                    entries = {}
                    for entry in jar.infolist():
                        match = re.fullmatch(r'assets/minecraft/textures/block/([a-z0-9_]+)\.png', entry.filename)
                        if match and entry.file_size <= 4 * 1024 * 1024:
                            entries[match[1]] = entry.filename
                    if entries:
                        self.path, self.entries = path, entries
                        break
            except (OSError, zipfile.BadZipFile):
                continue

    def read(self, name):
        entry = self.entries.get(name)
        if entry is None:
            return None
        with zipfile.ZipFile(self.path) as jar:
            return jar.read(entry)
