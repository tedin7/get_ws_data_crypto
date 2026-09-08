"""Offline archive recovery checks using only disposable, synthetic data."""

import importlib.util
import lzma
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


class ArchiveRecoveryTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)
        spec = importlib.util.spec_from_file_location(
            "archiver", Path(__file__).resolve().parents[1] / "archiver.py"
        )
        self.archiver = importlib.util.module_from_spec(spec)
        with patch.dict(os.environ, {"WS_DIR_PATH": temporary.name}), patch(
            "logging.basicConfig"
        ) as logging_config:
            spec.loader.exec_module(self.archiver)
        for handler in logging_config.call_args.kwargs.get("handlers", []):
            self.addCleanup(handler.close)
        self.archiver.ARCHIVER_COMPRESSION_LEVEL = 0
        self.source = self.directory / "price_data_2020-01-01.jsonl"
        self.payload = b'{"timestamp":"2020-01-01T00:00:00","price":1}\n'
        self.source.write_bytes(self.payload)
        self.archive = self.source.with_suffix(".jsonl.xz")
        digest, size = self.archiver.compute_sha256(self.source)
        self.archiver.write_hash_file(self.source, digest, size)

    def test_resumes_after_source_manifest_was_written(self):
        self.assertEqual(
            self.archiver.process_file(self.source), "COMPRESSED_AND_DELETED"
        )
        self.assertFalse(self.source.exists())
        with lzma.open(self.archive, "rb") as archive:
            self.assertEqual(archive.read(), self.payload)

    def test_resumes_after_valid_archive_was_renamed(self):
        self.archiver.compress_xz(self.source, self.archive, level=0)
        self.assertEqual(self.archiver.process_file(self.source), "VERIFIED_EXISTING")
        self.assertFalse(self.source.exists())
        self.assertTrue(self.archive.with_suffix(".xz.sha256").exists())

    def test_mismatched_archive_preserves_source(self):
        with lzma.open(self.archive, "wb", preset=0) as archive:
            archive.write(b"different data\n")
        with self.assertLogs(level="ERROR"):
            self.assertEqual(self.archiver.process_file(self.source), "FAILED")
        self.assertEqual(self.source.read_bytes(), self.payload)
        self.assertTrue(self.archive.exists())
        self.assertTrue(self.source.with_suffix(".jsonl.verify_failed").exists())

    def test_stale_manifest_and_archive_preserve_changed_source(self):
        self.archiver.compress_xz(self.source, self.archive, level=0)
        for changed in (self.payload + self.payload, self.payload.replace(b'"price":1', b'"price":2')):
            with self.subTest(size=len(changed)):
                # Restore the old source manifest before each changed-source case.
                self.source.write_bytes(self.payload)
                digest, size = self.archiver.compute_sha256(self.source)
                self.archiver.write_hash_file(self.source, digest, size)
                self.source.write_bytes(changed)
                with self.assertLogs(level="ERROR"):
                    self.assertEqual(self.archiver.process_file(self.source), "FAILED")
                self.assertEqual(self.source.read_bytes(), changed)
                with lzma.open(self.archive, "rb") as archive:
                    self.assertEqual(archive.read(), self.payload)


if __name__ == "__main__":
    unittest.main()
