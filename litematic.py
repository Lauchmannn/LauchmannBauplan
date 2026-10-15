from __future__ import annotations

from pathlib import Path
from collections import Counter, defaultdict
import gzip
import io
import json
import math
import re
import struct


class NBTError(ValueError):
    pass


class _Reader:
    def __init__(self, data: bytes):
        self.data = data
        self.pos = 0

    def read(self, n: int) -> bytes:
        if self.pos + n > len(self.data):
            raise NBTError("Unerwartetes Ende der NBT-Datei")
        out = self.data[self.pos:self.pos + n]
        self.pos += n
        return out

    def u8(self): return self.read(1)[0]
    def i8(self): return struct.unpack(">b", self.read(1))[0]
    def i16(self): return struct.unpack(">h", self.read(2))[0]
    def u16(self): return struct.unpack(">H", self.read(2))[0]
    def i32(self): return struct.unpack(">i", self.read(4))[0]
    def i64(self): return struct.unpack(">q", self.read(8))[0]
    def f32(self): return struct.unpack(">f", self.read(4))[0]
    def f64(self): return struct.unpack(">d", self.read(8))[0]

    def string(self):
        n = self.u16()
        return self.read(n).decode("utf-8", errors="replace")


def _payload(r: _Reader, tag: int):
    if tag == 1: return r.i8()
    if tag == 2: return r.i16()
    if tag == 3: return r.i32()
    if tag == 4: return r.i64()
    if tag == 5: return r.f32()
    if tag == 6: return r.f64()
    if tag == 7:
        n = r.i32()
        return r.read(n)
    if tag == 8: return r.string()
    if tag == 9:
        item_type = r.u8()
        n = r.i32()
        if n < 0: raise NBTError("Negative Listenlänge")
        return [_payload(r, item_type) for _ in range(n)]
    if tag == 10:
        out = {}
        while True:
            item_type = r.u8()
            if item_type == 0:
                return out
            name = r.string()
            out[name] = _payload(r, item_type)
    if tag == 11:
        n = r.i32()
        return [r.i32() for _ in range(n)]
    if tag == 12:
        n = r.i32()
        return [r.i64() for _ in range(n)]
    raise NBTError(f"Unbekannter NBT-Tag: {tag}")


def read_nbt(path: Path) -> dict:
    data = path.read_bytes()
    if data[:2] == b"\x1f\x8b":
        data = gzip.decompress(data)
    r = _Reader(data)
    root_type = r.u8()
    if root_type != 10:
        raise NBTError("Litematic besitzt keinen Compound-Root")
    _ = r.string()
    root = _payload(r, root_type)
    return root


def _canonical_state(state: dict) -> tuple[str, tuple[tuple[str, str], ...]]:
    name = str(state.get("Name", "minecraft:air"))
    props = state.get("Properties") or {}
    return name, tuple(sorted((str(k), str(v)) for k, v in props.items()))


def _state_dict(key: tuple[str, tuple[tuple[str, str], ...]]) -> dict:
    name, props = key
    out = {"name": name}
    if props:
        out["properties"] = dict(props)
    return out


def _decode_states(longs: list[int], palette_size: int, volume: int) -> list[int]:
    bits = max(2, max(0, palette_size - 1).bit_length())
    mask = (1 << bits) - 1
    unsigned = [v & ((1 << 64) - 1) for v in longs]
    out = [0] * volume
    for i in range(volume):
        bit = i * bits
        li = bit >> 6
        off = bit & 63
        if li >= len(unsigned):
            raise NBTError("BlockStates ist kürzer als erwartet")
        value = (unsigned[li] >> off) & mask
        if off + bits > 64:
            if li + 1 >= len(unsigned):
                raise NBTError("BlockStates endet mitten in einem Eintrag")
            value |= (unsigned[li + 1] << (64 - off)) & mask
        if value >= palette_size:
            raise NBTError(f"Ungültiger Palette-Index {value}")
        out[i] = value
    return out


def _slugify(value: str) -> str:
    value = value.strip().lower()
    value = value.replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")
    value = re.sub(r"[^a-z0-9]+", "-", value).strip("-")
    return value or "litematic"


GERMAN_NAMES = {
    "minecraft:smooth_stone": "Glatter Stein",
    "minecraft:hopper": "Trichter",
    "minecraft:lantern": "Laterne",
    "minecraft:green_terracotta": "Grüne Terrakotta",
    "minecraft:lime_terracotta": "Hellgrüne Terrakotta",
    "minecraft:green_wool": "Grüne Wolle",
    "minecraft:green_concrete_powder": "Grüner Trockenbeton",
    "minecraft:green_concrete": "Grüner Beton",
    "minecraft:green_carpet": "Grüner Teppich",
    "minecraft:water": "Wasser",
    "minecraft:sand": "Sand",
    "minecraft:cactus": "Kaktus",
    "minecraft:quartz_block": "Quarzblock",
    "minecraft:oak_fence": "Eichenzaun",
    "minecraft:stone_brick_wall": "Steinziegelmauer",
    "minecraft:oak_door": "Eichentür",
    "minecraft:cobbled_deepslate": "Bruchtiefenschiefer",
    "minecraft:cobblestone": "Bruchstein",
    "minecraft:dirt": "Erde",
    "minecraft:air": "Luft",
}


def display_name(block_name: str) -> str:
    if block_name in GERMAN_NAMES:
        return GERMAN_NAMES[block_name]
    raw = block_name.split(":", 1)[-1].replace("_", " ")
    return raw.title()


def convert_litematic(path: Path, projects_dir: Path, preferred_slug: str | None = None) -> dict:
    root = read_nbt(path)
    regions = root.get("Regions")
    if not isinstance(regions, dict) or not regions:
        raise NBTError("Keine Regionen in der Litematic gefunden")

    metadata = root.get("Metadata") or {}
    file_stem = path.stem
    raw_name = str(metadata.get("Name") or "").strip()
    project_name = raw_name if raw_name and raw_name.lower() != "unnamed" else file_stem.replace("-", " ").replace("_", " ").title()
    slug = preferred_slug or _slugify(file_stem if raw_name.lower() == "unnamed" else raw_name)

    # Merge all regions into one normalized block dictionary.
    # Later regions overwrite earlier blocks when regions overlap.
    blocks: dict[tuple[int, int, int], tuple[str, tuple[tuple[str, str], ...]]] = {}

    for region_name, region in regions.items():
        size = region.get("Size") or {}
        pos = region.get("Position") or {}
        sx, sy, sz = int(size.get("x", 0)), int(size.get("y", 0)), int(size.get("z", 0))
        nx, ny, nz = abs(sx), abs(sy), abs(sz)
        if not nx or not ny or not nz:
            continue
        volume = nx * ny * nz
        palette_raw = region.get("BlockStatePalette") or []
        longs = region.get("BlockStates") or []
        if not palette_raw:
            continue
        palette_keys = [_canonical_state(s) for s in palette_raw]
        values = _decode_states(longs, len(palette_keys), volume)
        px, py, pz = int(pos.get("x", 0)), int(pos.get("y", 0)), int(pos.get("z", 0))
        dx, dy, dz = (1 if sx > 0 else -1), (1 if sy > 0 else -1), (1 if sz > 0 else -1)

        # Litematica stores X fastest, then Z, then Y.
        for ly in range(ny):
            wy = py + ly * dy
            for lz in range(nz):
                wz = pz + lz * dz
                base = (ly * nz + lz) * nx
                for lx in range(nx):
                    state_key = palette_keys[values[base + lx]]
                    if state_key[0] == "minecraft:air":
                        continue
                    wx = px + lx * dx
                    blocks[(wx, wy, wz)] = state_key

    if not blocks:
        raise NBTError("Die Litematic enthält keine sichtbaren Blöcke")

    min_x = min(p[0] for p in blocks); max_x = max(p[0] for p in blocks)
    min_y = min(p[1] for p in blocks); max_y = max(p[1] for p in blocks)
    min_z = min(p[2] for p in blocks); max_z = max(p[2] for p in blocks)
    size_x, size_y, size_z = max_x - min_x + 1, max_y - min_y + 1, max_z - min_z + 1
    if max(size_x, size_y, size_z) > 65535:
        raise NBTError("Bauwerk ist für dieses Viewer-Format zu groß (> 65535 Blöcke pro Achse)")

    # Stable palette, sorted by base name and properties; index 0 is not special here.
    unique_keys = sorted(set(blocks.values()), key=lambda k: (k[0], k[1]))
    key_to_index = {k: i for i, k in enumerate(unique_keys)}
    palette = []
    for key in unique_keys:
        entry = _state_dict(key)
        entry["displayName"] = display_name(entry["name"])
        palette.append(entry)

    normalized: dict[tuple[int, int, int], int] = {}
    state_counts = Counter()
    base_counts = Counter()
    for (wx, wy, wz), key in blocks.items():
        x, y, z = wx - min_x, wy - min_y, wz - min_z
        idx = key_to_index[key]
        normalized[(x, y, z)] = idx
        state_counts[idx] += 1
        base_counts[key[0]] += 1

    project_dir = projects_dir / slug
    if project_dir.exists():
        # Re-importing replaces generated project data but never the user's source file.
        for child in project_dir.rglob("*"):
            if child.is_file():
                child.unlink()
        for child in sorted(project_dir.rglob("*"), reverse=True):
            if child.is_dir():
                child.rmdir()
    (project_dir / "layers").mkdir(parents=True, exist_ok=True)

    # Surface contains only blocks touching air; this keeps full 3D mode much lighter.
    dirs = ((1,0,0),(-1,0,0),(0,1,0),(0,-1,0),(0,0,1),(0,0,-1))
    surface = []
    layers: dict[int, list[tuple[int,int,int]]] = defaultdict(list)
    for (x, y, z), idx in normalized.items():
        layers[y].append((x, z, idx))
        if any((x+dx, y+dy, z+dz) not in normalized for dx,dy,dz in dirs):
            surface.append((x, y, z, idx))

    with (project_dir / "surface.bin").open("wb") as f:
        for x, y, z, idx in sorted(surface, key=lambda r: (r[1], r[2], r[0])):
            f.write(struct.pack("<HHHH", x, y, z, idx))

    nonempty_layers = []
    for y in range(size_y):
        recs = layers.get(y, [])
        if not recs:
            continue
        nonempty_layers.append(y)
        with (project_dir / "layers" / f"y{y:04d}.bin").open("wb") as f:
            for x, z, idx in sorted(recs, key=lambda r: (r[1], r[0])):
                f.write(struct.pack("<HHH", x, z, idx))

    materials = []
    for block_name, count in sorted(base_counts.items(), key=lambda kv: (-kv[1], kv[0])):
        materials.append({"name": block_name, "displayName": display_name(block_name), "count": count})

    out = {
        "format": 2,
        "slug": slug,
        "name": project_name,
        "author": str(metadata.get("Author") or "Unbekannt"),
        "description": str(metadata.get("Description") or ""),
        "sourceFile": path.name,
        "sourceType": "Litematic",
        "minecraftDataVersion": int(root.get("MinecraftDataVersion") or 0),
        "litematicVersion": int(root.get("Version") or 0),
        "regionCount": len(regions),
        "blockCount": len(normalized),
        "surfaceBlockCount": len(surface),
        "totalVolume": size_x * size_y * size_z,
        "bounds": {"minX": 0, "minY": 0, "minZ": 0, "maxX": size_x-1, "maxY": size_y-1, "maxZ": size_z-1},
        "originalBounds": {"minX": min_x, "minY": min_y, "minZ": min_z, "maxX": max_x, "maxY": max_y, "maxZ": max_z},
        "size": {"x": size_x, "y": size_y, "z": size_z},
        "initialY": nonempty_layers[0] if nonempty_layers else 0,
        "nonemptyLayers": nonempty_layers,
        "palette": palette,
        "stateCounts": {str(k): v for k, v in state_counts.items()},
        "materials": materials,
    }
    (project_dir / "metadata.json").write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    return out
