"""Boundary checks for binary, length-delimited persistence records."""
import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('vault', Path(__file__).resolve().parents[1] / 'scripts/inspect_persistence_vault.py')
vault = importlib.util.module_from_spec(spec)
spec.loader.exec_module(vault)


class PersistenceVaultTests(unittest.TestCase):
    def test_binary_value_does_not_split_records(self):
        self.assertEqual(list(vault.records(b'1 2 4 a\n\x00b\n3 4 0 \n')),
                         [(1, 2, b'a\n\x00b'), (3, 4, b'')])

    def test_truncated_value(self):
        with self.assertRaisesRegex(ValueError, 'Truncated'):
            list(vault.records(b'1 2 5 abc'))

    def test_missing_separator(self):
        with self.assertRaisesRegex(ValueError, 'delimiter'):
            list(vault.records(b'1 2 1 a3 4 1 b'))

    def test_duplicate_key(self):
        with self.assertRaisesRegex(ValueError, 'Duplicate'):
            list(vault.records(b'1 2 1 a\n1 2 1 b'))


if __name__ == '__main__':
    unittest.main()
