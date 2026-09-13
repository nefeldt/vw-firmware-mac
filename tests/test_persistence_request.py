"""Protocol boundary tests; the fixture is reconstructed, not a live capture."""
import importlib.util
from pathlib import Path
import struct
import unittest

spec = importlib.util.spec_from_file_location('request', Path(__file__).resolve().parents[1] / 'scripts/decode_persistence_request.py')
request = importlib.util.module_from_spec(spec)
spec.loader.exec_module(request)


class RequestTests(unittest.TestCase):
    def test_reconstructed_navigation_request(self):
        packet = bytes.fromhex('00000000 00000000 00000000 01000000 0a000080 90010000 02000000 11000000 54020000')
        self.assertEqual(request.decode(packet)['requests'], [dict(
            namespace=0x8000000a, key=400, field_08=2, field_0c=17, field_10=596)])

    def test_rejects_short_header(self):
        with self.assertRaisesRegex(ValueError, 'header'):
            request.decode(bytes(15))

    def test_rejects_missing_and_extra_records(self):
        for data in (struct.pack('<4I', 0, 0, 0, 1), bytes(20)):
            with self.assertRaisesRegex(ValueError, 'count'):
                request.decode(data)

    def test_rejects_out_of_range_halfword(self):
        with self.assertRaisesRegex(ValueError, '16-bit'):
            request.decode(struct.pack('<9I', 0, 0, 0, 1, 1, 2, 65536, 4, 5))


if __name__ == '__main__':
    unittest.main()
