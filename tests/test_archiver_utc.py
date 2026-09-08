"""Separate stale-part UTC regression; no producer timestamp or retention migration."""
from datetime import datetime, timedelta, timezone
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

from test_storage_integrity import load_module
from storage_protocol import FileLock, lock_path


class StalePartUtcTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)
        self.module = load_module("archiver_utc", "archiver.py", self.directory)
        self.module.ARCHIVER_COMPRESSION_LEVEL = 0
        self.source = self.directory / "price_data_2020-01-01.jsonl"
        self.source.write_bytes(b'{"timestamp":"2020-01-01T00:00:00","price":42}\n')
        self.partial = self.source.with_suffix(".jsonl.xz.part")
        self.partial.write_bytes(b"unpublished partial")
        self.now = datetime(2026, 9, 8, 12, tzinfo=timezone.utc)

    def set_age(self, seconds):
        modified = (self.now - timedelta(seconds=seconds)).timestamp()
        os.utime(self.partial, (modified, modified))

    def test_stale_is_independent_of_process_timezone(self):
        self.set_age(3601)
        for zone in ("UTC", "Europe/Rome", "America/Los_Angeles"):
            with self.subTest(zone=zone):
                try:
                    with patch.dict(os.environ, {"TZ": zone}):
                        time.tzset()
                        with patch.object(self.module, "_now", return_value=self.now):
                            self.assertTrue(self.module._partial_is_stale(self.partial))
                finally:
                    time.tzset()

    def test_fresh_and_exact_boundary_are_not_stale(self):
        for seconds in (-1, 0, 3599, 3600):
            with self.subTest(age=seconds):
                self.set_age(seconds)
                with patch.object(self.module, "_now", return_value=self.now):
                    self.assertFalse(self.module._partial_is_stale(self.partial))
                    self.assertEqual(self.module.process_file(self.source), "SKIPPED")
                self.assertEqual(self.partial.read_bytes(), b"unpublished partial")
                self.assertTrue(self.source.exists())

    def test_stale_cleanup_under_lock_completes_archive(self):
        self.set_age(3601)
        with patch.object(self.module, "_now", return_value=self.now):
            self.assertEqual(self.module.process_file(self.source), "COMPRESSED_AND_DELETED")
        self.assertFalse(self.partial.exists())
        self.assertTrue(self.source.with_suffix(".jsonl.xz").exists())

    def test_stale_age_never_overrides_held_lock(self):
        self.set_age(3601)
        with FileLock(lock_path(self.source)), patch.object(self.module, "_now", return_value=self.now):
            self.assertEqual(self.module.process_file(self.source), "SKIPPED")
            self.assertEqual(self.partial.read_bytes(), b"unpublished partial")
            self.assertTrue(self.source.exists())


if __name__ == "__main__":
    unittest.main()
