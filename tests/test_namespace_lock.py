"""Offline namespace/rotation lock tests, including configured mount paths."""
import fcntl
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import storage_protocol as storage


class NamespaceTest(unittest.TestCase):
    def test_reader_blocks_new_day_but_not_unrelated_existing_day(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            old = root / 'price_data_2020-01-01.jsonl'
            with storage.source_lock(old):
                pass
            anchor = root / storage.NAMESPACE_LOCK
            identity = anchor.stat().st_ino
            with anchor.open('rb') as reader:
                fcntl.flock(reader, fcntl.LOCK_SH | fcntl.LOCK_NB)
                with storage.source_lock(old):
                    pass
                with self.assertRaises(BlockingIOError):
                    storage.source_lock(root / 'price_data_2020-01-02.jsonl')
                self.assertFalse((root / 'price_data_2020-01-02.jsonl.lock').exists())
            with storage.source_lock(root / 'price_data_2020-01-02.jsonl'):
                pass
            self.assertEqual(anchor.stat().st_ino, identity)

    def test_configured_directory_is_the_only_writer_and_healthcheck_store(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            target = root / 'mounted'
            repo = Path(__file__).resolve().parents[1]
            result = subprocess.run([sys.executable, '-c',
                'import config, healthcheck; print(config.WS_DIR_PATH); print(healthcheck.WS_DIR_PATH)'],
                cwd=root, env={**os.environ, 'PYTHONPATH': str(repo), 'WS_DIR_PATH': str(target)},
                text=True, capture_output=True, check=True)
            self.assertEqual(result.stdout.splitlines(), [str(target), str(target)])
            self.assertTrue((target / 'logs').is_dir())
            self.assertFalse((root / 'ws_data').exists())


if __name__ == '__main__':
    unittest.main(verbosity=2)
