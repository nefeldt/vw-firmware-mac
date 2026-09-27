"""Regression tests for the public-source release audit."""
import importlib.util
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('check_release', Path(__file__).resolve().parents[1] / 'scripts/check_release.py')
check_release = importlib.util.module_from_spec(spec)
spec.loader.exec_module(check_release)


class CheckReleaseTests(unittest.TestCase):
    def test_audit_allows_its_own_detection_patterns(self):
        name = 'scripts/check_release.py'
        data = (Path(__file__).resolve().parents[1] / name).read_bytes()

        def fake_run(args, **kwargs):
            if args == ['git', 'ls-files', '-z']:
                return subprocess.CompletedProcess(args, 0, stdout=f'{name}\0'.encode())
            if args[:3] == ['git', 'check-ignore', '--quiet']:
                return subprocess.CompletedProcess(args, 0)
            raise AssertionError(f'unexpected run call: {args!r}')

        def fake_check_output(args, **kwargs):
            if args == ['git', 'show', f':{name}']:
                return data
            raise AssertionError(f'unexpected check_output call: {args!r}')

        with patch.object(check_release.subprocess, 'run', side_effect=fake_run), \
             patch.object(check_release.subprocess, 'check_output', side_effect=fake_check_output):
            check_release.audit()


if __name__ == '__main__':
    unittest.main()
