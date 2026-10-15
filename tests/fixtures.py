"""Synthetic, redistributable NBT fixtures generated in memory (no user schematics)."""
import gzip
import struct


def string(value):
    data = value.encode('utf-8')
    return struct.pack('>H', len(data)) + data


def tag(kind, name, payload):
    return bytes([kind]) + string(name) + payload


def compound(name, payload):
    return tag(10, name, payload + b'\0')


def vector(name, values):
    return compound(name, b''.join(tag(3, axis, struct.pack('>i', value)) for axis, value in zip('xyz', values)))


def region(name='main', size=(1, 1, 1), position=(0, 0, 0), palette=None, states=None):
    palette = palette or [('minecraft:stone', {})]
    states = states if states is not None else [0] * abs(size[0] * size[1] * size[2])
    bits = max(2, (len(palette) - 1).bit_length())
    packed = sum(value << (i * bits) for i, value in enumerate(states))
    longs = [(packed >> (i * 64)) & ((1 << 64) - 1) for i in range((len(states) * bits + 63) // 64)]
    entries = []
    for block, props in palette:
        entries.append(tag(8, 'Name', string(block)) + (compound('Properties', b''.join(tag(8, k, string(v)) for k, v in props.items())) if props else b'') + b'\0')
    return compound(name, vector('Size', size) + vector('Position', position) + tag(9, 'BlockStatePalette', b'\x0a' + struct.pack('>i', len(palette)) + b''.join(entries)) + tag(12, 'BlockStates', struct.pack('>i', len(longs)) + b''.join(struct.pack('>Q', n) for n in longs)))


def schematic(regions=None, name='Synthetic fixture', compressed=True):
    data = compound('', tag(3, 'Version', struct.pack('>i', 6)) + tag(3, 'MinecraftDataVersion', struct.pack('>i', 3955)) + compound('Metadata', tag(8, 'Name', string(name))) + compound('Regions', regions if regions is not None else region()))
    return gzip.compress(data) if compressed else data
