import unittest

from d64put import ts_off
from d64read import prg_entries, read_file, sector


class D64ReadTests(unittest.TestCase):
    def setUp(self):
        self.disk = bytearray(174848)

    def test_chained_file_and_partial_final_sector(self):
        first, last = ts_off(1, 0), ts_off(1, 1)
        self.disk[first:first + 256] = bytes([1, 1]) + bytes(range(254))
        self.disk[last:last + 5] = b'\x00\x04XYZ'
        self.assertEqual(read_file(self.disk, 1, 0), bytes(range(254)) + b'XYZ')

    def test_full_final_sector(self):
        offset = ts_off(1, 0)
        self.disk[offset:offset + 256] = b'\x00\xff' + b'x' * 254
        self.assertEqual(read_file(self.disk, 1, 0), b'x' * 254)

    def test_file_cycle_is_rejected(self):
        offset = ts_off(1, 0)
        self.disk[offset:offset + 2] = b'\x01\x00'
        with self.assertRaisesRegex(ValueError, 'cyclic'):
            read_file(self.disk, 1, 0)

    def test_invalid_or_truncated_sector_is_rejected(self):
        for disk, track, number in [(self.disk, 1, 21), (self.disk, 0, 0), (b'', 1, 0)]:
            with self.subTest(track=track, number=number), self.assertRaises(ValueError):
                sector(disk, track, number)

    def test_directory_names_types_and_cycle(self):
        offset = ts_off(18, 1)
        self.disk[offset + 2:offset + 21] = b'\x82\x01\x00' + b'MX'.ljust(16, b'\xa0')
        self.disk[offset + 34] = 0x81  # SEQ, not a PRG
        self.assertEqual(list(prg_entries(self.disk)), [('mx', 1, 0)])
        self.disk[offset:offset + 2] = b'\x12\x01'
        with self.assertRaisesRegex(ValueError, 'cyclic'):
            list(prg_entries(self.disk))


if __name__ == '__main__':
    unittest.main()
