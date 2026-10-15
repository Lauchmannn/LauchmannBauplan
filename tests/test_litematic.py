import json
from pathlib import Path
import struct
import tempfile
import unittest

from litematic import convert_litematic, read_nbt, NBTError, _decode_states
from fixtures import schematic, region, compound, tag


class LitematicTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.addCleanup(self.tmp.cleanup)

    def convert(self, data):
        source = self.root / 'input.litematic'
        source.write_bytes(data)
        return convert_litematic(source, self.root / 'projects')

    def test_negative_sizes_all_axes_are_min_corner_order_not_mirrored(self):
        palette = [(f'minecraft:test_{i}', {}) for i in range(8)]
        meta = self.convert(schematic(region(size=(-2, -2, -2), position=(10, 20, 30), palette=palette, states=list(range(8)))))
        self.assertEqual(meta['originalBounds'], dict(minX=9, minY=19, minZ=29, maxX=10, maxY=20, maxZ=30))
        records = list(struct.iter_unpack('<HHHH', (self.root / 'projects' / meta['slug'] / 'surface.bin').read_bytes()))
        self.assertEqual(records, [(0,0,0,0),(1,0,0,1),(0,0,1,2),(1,0,1,3),(0,1,0,4),(1,1,0,5),(0,1,1,6),(1,1,1,7)])

    def test_cross_long_boundary_and_signed_longs(self):
        palette = [(f'minecraft:block_{i}', {}) for i in range(17)]
        values = list(range(17)) * 3
        data = schematic(region(size=(51,1,1), palette=palette, states=values))
        path = self.root / 'packed.litematic'; path.write_bytes(data)
        packed = read_nbt(path)['Regions']['main']['BlockStates']
        self.assertTrue(any(v < 0 for v in packed))
        self.assertEqual(_decode_states(packed,17,51),values)

    def test_overlapping_air_clears_previous_region(self):
        data = schematic(region('a', size=(2,1,1)) + region('b', palette=[('minecraft:air', {})]))
        meta = self.convert(data)
        self.assertEqual(meta['blockCount'],1)
        self.assertEqual(meta['originalBounds']['minX'],1)

    def test_solid_interior_removed_partial_geometry_preserved(self):
        meta = self.convert(schematic(region(size=(3,3,3))))
        self.assertEqual(meta['blockCount'],27)
        self.assertEqual(meta['surfaceBlockCount'],26)
        states = [0]*27; states[13]=1
        meta = self.convert(schematic(region(size=(3,3,3),palette=[('minecraft:stone',{}),('minecraft:oak_slab',{'type':'bottom'})],states=states)))
        self.assertEqual(meta['surfaceBlockCount'],27)
        self.assertEqual(sum(m['count'] for m in meta['materials']),27)

    def test_raw_nbt_and_empty_model_error(self):
        self.assertEqual(self.convert(schematic(compressed=False))['blockCount'],1)
        with self.assertRaises(NBTError):
            self.convert(schematic(region(palette=[('minecraft:cave_air',{})])))

    def test_truncated_invalid_palette_and_negative_lengths(self):
        for data in [b'\x0a', compound('', tag(12,'bad',struct.pack('>i',-1)))]:
            path=self.root/'bad.litematic';path.write_bytes(data)
            with self.assertRaises(NBTError):read_nbt(path)
        with self.assertRaises(NBTError):_decode_states([3],2,1)
        with self.assertRaises(NBTError):_decode_states([],2,1)


if __name__ == '__main__':
    unittest.main()
