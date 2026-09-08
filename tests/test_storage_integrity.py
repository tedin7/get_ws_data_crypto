"""Fault injection against the real collector/storage/archiver, offline and disposable.

Only the WebSocket import is substituted: no pybit behavior is certified here.
FileIO, flock, LZMA, subprocess termination and the application methods are real.
"""
from __future__ import annotations

from contextlib import contextmanager
import importlib.util
import json
import lzma
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import storage_protocol as storage


def load_module(name, path, directory):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    module = importlib.util.module_from_spec(spec)
    config = SimpleNamespace(WS_DIR=str(directory), WS_DIR_PATH=str(directory),
                             BUFFER_SIZE=100, FLUSH_INTERVAL=60, SYMBOL="BTCUSDT")
    (directory / "logs").mkdir(exist_ok=True)
    with patch.dict(os.environ, {"WS_DIR_PATH": str(directory)}), patch.dict(sys.modules, {
        "config": config, "pybit.unified_trading": SimpleNamespace(WebSocket=None),
        "healthcheck": SimpleNamespace(healthcheck=lambda: True),
    }), patch("logging.basicConfig") as setup:
        spec.loader.exec_module(module)
    for handler in (setup.call_args.kwargs.get("handlers", []) if setup.called else []):
        handler.close()
    return module


class FileProxy:
    def __init__(self, file, state, stage):
        self.file, self.state, self.stage = file, state, stage

    def __getattr__(self, name):
        return getattr(self.file, name)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        result = self.file.__exit__(*args)
        if self.stage == "close" and not self.state["fired"]:
            self.state["fired"] = True
            raise OSError("synthetic close failure after actual close")
        return result

    def write(self, data):
        if self.stage == "write" and not self.state["fired"]:
            self.state["fired"] = True
            self.state["writes"] += 1
            self.file.write(data[:7])
            raise OSError("synthetic partial write")
        self.state["writes"] += 1
        if self.stage == "short":
            return self.file.write(data[:3])
        if self.stage == "zero":
            return 0
        return self.file.write(data)

    def flush(self):
        if self.stage == "flush" and not self.state["fired"]:
            self.state["fired"] = True
            raise OSError("synthetic flush failure")
        return self.file.flush()


@contextmanager
def fail_source(source, stage):
    real_open, real_fsync = Path.open, os.fsync
    state = {"fired": False, "writes": 0}

    def opening(path, mode="r", *args, **kwargs):
        file = real_open(path, mode, *args, **kwargs)
        if path == source and mode == "r+b":
            return FileProxy(file, state, stage)
        return file

    def syncing(fd):
        info = os.fstat(fd)
        if (stage == "fsync" and not state["fired"] and source.exists()
                and info.st_ino == source.stat().st_ino and info.st_size > 0):
            state["fired"] = True
            raise OSError("synthetic fsync failure")
        return real_fsync(fd)

    with patch.object(Path, "open", opening), patch.object(os, "fsync", syncing):
        yield state


class IntegrityTest(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.directory = Path(temp.name)
        self.source = self.directory / "price_data_2020-01-01.jsonl"
        self.payload = b'{"timestamp":"2020-01-01T00:00:00","price":42}\n'
        self.prefix = b'{"timestamp":"2019-12-31T23:59:59","price":41}\n'
        self.source.write_bytes(self.prefix)
        self.archive = self.source.with_suffix(".jsonl.xz")
        self.partial = self.source.with_suffix(".jsonl.xz.part")
        self.archiver = load_module("isolated_archiver", "archiver.py", self.directory)
        self.archiver.ARCHIVER_COMPRESSION_LEVEL = 0

    def batch(self):
        batch = storage.AppendBatch(self.source, self.payload)
        self.addCleanup(batch.close)
        return batch

    def client(self):
        module = load_module("isolated_collector", "main.py", self.directory)
        client = module.BybitWebSocketClient()
        client.get_current_file = lambda: self.source
        def cleanup():
            if client._pending:
                client._pending.close()
            if client._owner:
                client._owner.close()
        self.addCleanup(cleanup)
        return client

    def test_write_flush_fsync_close_failures_rollback_then_retry_once(self):
        for stage in ("write", "flush", "fsync", "close"):
            with self.subTest(stage=stage):
                self.source.write_bytes(self.prefix)
                batch = self.batch()
                with fail_source(self.source, stage) as fault:
                    with self.assertRaises(OSError):
                        batch.commit()
                    self.assertTrue(fault["fired"])
                self.assertEqual(self.source.read_bytes(), self.prefix)
                self.assertTrue(storage.pending_path(self.source).exists())
                batch.commit()
                self.assertEqual(self.source.read_bytes(), self.prefix + self.payload)
                self.assertFalse(storage.pending_path(self.source).exists())
                batch.close()

    def test_short_writes_are_completed_without_duplicates(self):
        batch = self.batch()
        with fail_source(self.source, "short") as fault:
            batch.commit()
        self.assertGreater(fault["writes"], 1)
        self.assertEqual(self.source.read_bytes(), self.prefix + self.payload)

    def test_zero_write_keeps_intent_and_source_prefix(self):
        batch = self.batch()
        with fail_source(self.source, "zero"), self.assertRaises(OSError):
            batch.commit()
        self.assertEqual(self.source.read_bytes(), self.prefix)
        self.assertTrue(storage.pending_path(self.source).exists())
        batch.commit()
        self.assertEqual(self.source.read_bytes(), self.prefix + self.payload)

    def test_failed_rollback_never_blindly_appends_and_preserves_buffer(self):
        client = self.client()
        client.data_buffer = [{"price": 42}]
        with fail_source(self.source, "write") as fault, patch.object(
            os, "ftruncate", side_effect=OSError("synthetic failed rollback")
        ), self.assertLogs(level="ERROR"):
            client.save_price_data()
            first = self.source.read_bytes()
            client.save_price_data()
            self.assertEqual(self.source.read_bytes(), first)
            self.assertEqual(fault["writes"], 1)
            self.assertEqual(client.data_buffer, [{"price": 42}])
            self.assertEqual(self.archiver.process_file(self.source), "SKIPPED")
        client.save_price_data()
        self.assertEqual(client.data_buffer, [])
        rows = [json.loads(line) for line in self.source.read_bytes().splitlines()]
        self.assertEqual([row["price"] for row in rows], [41, 42])

    def test_journal_publish_failure_does_not_append(self):
        batch = self.batch()
        with patch.object(storage, "atomic_bytes", side_effect=OSError("intent failed")):
            with self.assertRaises(OSError):
                batch.commit()
        self.assertEqual(self.source.read_bytes(), self.prefix)
        batch.commit()
        self.assertEqual(self.source.read_bytes(), self.prefix + self.payload)

    def test_cleanup_directory_failure_keeps_lock_and_retry_does_not_replay(self):
        batch = self.batch()
        real_sync = storage.fsync_directory
        def syncing(path):
            if not storage.pending_path(self.source).exists():
                raise OSError("cleanup directory fsync")
            real_sync(path)
        with patch.object(storage, "fsync_directory", syncing), self.assertRaises(OSError):
            batch.commit()
        self.assertEqual(self.source.read_bytes(), self.prefix + self.payload)
        self.assertFalse(storage.pending_path(self.source).exists())
        self.assertEqual(self.archiver.process_file(self.source), "SKIPPED")
        batch.commit()
        self.assertEqual(self.source.read_bytes(), self.prefix + self.payload)

    def test_cleanup_unlink_failure_keeps_batch_buffer_until_ack(self):
        client = self.client()
        client.data_buffer = [{"price": 42}]
        real_unlink = Path.unlink
        def unlink(path, *args, **kwargs):
            if path == storage.pending_path(self.source):
                raise OSError("cleanup unlink failed")
            return real_unlink(path, *args, **kwargs)
        with patch.object(Path, "unlink", unlink), self.assertLogs(level="ERROR"):
            client.save_price_data()
        self.assertEqual(client.data_buffer, [{"price": 42}])
        client.save_price_data()
        self.assertEqual(client.data_buffer, [])
        self.assertEqual(len(self.source.read_bytes().splitlines()), 2)

    def test_retry_across_date_rotation_keeps_original_batch_path(self):
        client = self.client()
        second_day = self.directory / "price_data_2020-01-02.jsonl"
        client.data_buffer = [{"price": 42}]
        with fail_source(self.source, "write"), self.assertLogs(level="ERROR"):
            client.save_price_data()
        client.get_current_file = lambda: second_day
        client.data_buffer.append({"price": 43})
        client.save_price_data()
        self.assertEqual([json.loads(x)["price"] for x in self.source.read_bytes().splitlines()], [41, 42])
        self.assertEqual([json.loads(x)["price"] for x in second_day.read_bytes().splitlines()], [43])
        self.assertEqual(client.data_buffer, [])

    def test_second_collector_cannot_write_until_owner_closes(self):
        first, second = self.client(), self.client()
        first.data_buffer = [{"price": 42}]
        first.save_price_data()
        second.data_buffer = [{"price": 43}]
        with self.assertLogs(level="ERROR"):
            second.save_price_data()
        self.assertEqual(second.data_buffer, [{"price": 43}])
        first.close()
        second.save_price_data()
        self.assertEqual(second.data_buffer, [])
        self.assertEqual([json.loads(x)["price"] for x in self.source.read_bytes().splitlines()], [41, 42, 43])

    def test_threaded_callbacks_and_flush_do_not_lose_buffer_entries(self):
        client = self.client()
        workers = [threading.Thread(target=lambda n=i: client.handle_ticker(
            {"data": {"lastPrice": str(n)}})) for i in range(1, 51)]
        for worker in workers:
            worker.start()
        for worker in workers:
            worker.join(timeout=3)
            self.assertFalse(worker.is_alive())
        client.close()
        actual = [json.loads(line)["price"] for line in self.source.read_bytes().splitlines()[1:]]
        self.assertEqual(sorted(actual), list(range(1, 51)))

    def test_complete_intent_is_not_replayed_after_process_exit(self):
        self._crash_recover("complete")

    def test_partial_intent_is_recovered_after_process_exit(self):
        self._crash_recover("partial")

    def test_prepared_intent_is_recovered_after_process_exit(self):
        self._crash_recover("prepared")

    def _crash_recover(self, stage):
        script = """
import os, sys
from pathlib import Path
from storage_protocol import AppendBatch, FileLock
source = Path(sys.argv[1]); payload = bytes.fromhex(sys.argv[2])
owner = FileLock(source.parent / '.collector.lock')
batch = AppendBatch(source, payload); batch._prepare()
if sys.argv[3] != 'prepared':
    with source.open('ab', buffering=0) as file:
        file.write(payload if sys.argv[3] == 'complete' else payload[:7])
        os.fsync(file.fileno())
os._exit(23)
"""
        result = subprocess.run([sys.executable, "-c", script, str(self.source), self.payload.hex(), stage],
                                env={**os.environ, "PYTHONPATH": str(ROOT)}, timeout=10,
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 23, result.stderr)
        self.assertEqual(self.archiver.process_file(self.source), "SKIPPED")
        with storage.FileLock(self.directory / ".collector.lock"):
            self.assertEqual(storage.recover_pending(self.directory), 1)
        self.assertEqual(self.source.read_bytes(), self.prefix + self.payload)
        self.assertFalse(storage.pending_path(self.source).exists())

    def test_replaced_source_refuses_recovery_without_truncation(self):
        batch = self.batch(); batch._prepare(); batch.close()
        replacement = self.directory / "replacement"
        replacement.write_bytes(b'{"price":99}\n')
        os.replace(replacement, self.source)
        with self.assertRaises(storage.StorageConflict):
            storage.recover_pending(self.directory)
        self.assertEqual(self.source.read_bytes(), b'{"price":99}\n')
        self.assertTrue(storage.pending_path(self.source).exists())

    def test_unexpected_appended_bytes_are_not_truncated(self):
        batch = self.batch(); batch._prepare()
        with self.source.open("ab") as file:
            file.write(b"foreign bytes")
        before = self.source.read_bytes()
        with self.assertRaises(storage.RollbackFailed):
            batch.commit()
        self.assertEqual(self.source.read_bytes(), before)

    def test_incomplete_existing_tail_is_not_repaired_implicitly(self):
        self.source.write_bytes(b'{"price":')
        with self.assertRaises(storage.StorageConflict):
            self.batch().commit()
        self.assertEqual(self.source.read_bytes(), b'{"price":')

    def test_damaged_intent_is_retained_and_blocks_archive(self):
        batch = self.batch(); batch._prepare(); batch.close()
        marker = storage.pending_path(self.source)
        record = json.loads(marker.read_text())
        record["sha256"] = "0" * 64
        marker.write_text(json.dumps(record))
        with self.assertRaises(storage.StorageConflict):
            storage.recover_pending(self.directory)
        self.assertEqual(self.archiver.process_file(self.source), "SKIPPED")
        self.assertTrue(marker.exists())

    def test_archived_path_cannot_be_recreated_by_collector(self):
        self.assertEqual(self.archiver.process_file(self.source), "COMPRESSED_AND_DELETED")
        with self.assertRaises(storage.StorageConflict):
            self.batch().commit()
        self.assertFalse(self.source.exists())
        self.assertEqual(lzma.decompress(self.archive.read_bytes()), self.prefix)

    def test_pending_intent_makes_healthcheck_unhealthy(self):
        module = load_module("isolated_health", "healthcheck.py", self.directory)
        module.SYMBOL = "BTCUSDT"
        self.assertTrue(module.healthcheck())
        storage.pending_path(self.source).write_bytes(b"uncertain")
        self.assertFalse(module.healthcheck())

    def test_lzma_is_finalized_at_first_archive_fsync(self):
        real_sync = os.fsync
        samples = []
        def syncing(fd):
            if self.partial.exists() and os.fstat(fd).st_ino == self.partial.stat().st_ino:
                data = self.partial.read_bytes()
                samples.append((len(data), lzma.decompress(data)))
            real_sync(fd)
        with patch.object(os, "fsync", syncing):
            self.archiver.compress_xz(self.source, self.partial, level=0)
        self.assertEqual(samples, [(self.partial.stat().st_size, self.prefix)])

    def test_archive_order_includes_durable_publication_before_source_unlink(self):
        events = []
        real_sync, real_replace, real_unlink = os.fsync, os.replace, Path.unlink
        real_dir = self.archiver.fsync_directory
        def sync(fd):
            info = os.fstat(fd)
            for path in (self.partial, self.archive):
                if path.exists() and info.st_ino == path.stat().st_ino:
                    self.assertEqual(lzma.decompress(path.read_bytes()), self.prefix)
                    events.append("archive_fsync")
                    break
            real_sync(fd)
        def replace(src, dst):
            if Path(dst) == self.archive:
                events.append("publish")
            return real_replace(src, dst)
        def sync_dir(path):
            events.append("dir_before_unlink" if self.source.exists() else "dir_after_unlink")
            return real_dir(path)
        def unlink(path, *args, **kwargs):
            if path == self.source:
                events.append("source_unlink")
            return real_unlink(path, *args, **kwargs)
        with patch.object(os, "fsync", sync), patch.object(os, "replace", replace), patch.object(
            Path, "unlink", unlink
        ), patch.object(self.archiver, "fsync_directory", sync_dir):
            self.assertEqual(self.archiver.process_file(self.source), "COMPRESSED_AND_DELETED")
        self.assertLess(events.index("archive_fsync"), events.index("publish"))
        self.assertLess(events.index("publish"), events.index("dir_before_unlink"))
        self.assertLess(events.index("dir_before_unlink"), events.index("source_unlink"))
        self.assertLess(events.index("source_unlink"), events.index("dir_after_unlink"))

    def test_compression_and_verification_failures_never_publish_or_delete(self):
        def broken_compress(*args, **kwargs):
            self.partial.write_bytes(b"partial XZ")
            raise OSError("compress failed")
        with patch.object(self.archiver, "compress_xz", broken_compress), self.assertLogs(level="ERROR"):
            self.assertEqual(self.archiver.process_file(self.source), "FAILED")
        self.assertEqual(self.source.read_bytes(), self.prefix)
        self.assertFalse(self.archive.exists())
        self.partial.unlink()
        with patch.object(self.archiver, "verify_archive", return_value=False), self.assertLogs(level="ERROR"):
            self.assertEqual(self.archiver.process_file(self.source), "FAILED")
        self.assertEqual(self.source.read_bytes(), self.prefix)
        self.assertFalse(self.archive.exists())

    def test_archive_fsync_failure_preserves_original(self):
        real_sync = os.fsync
        def sync(fd):
            if self.partial.exists() and os.fstat(fd).st_ino == self.partial.stat().st_ino:
                raise OSError("archive fsync failed")
            return real_sync(fd)
        with patch.object(os, "fsync", sync), self.assertLogs(level="ERROR"):
            self.assertEqual(self.archiver.process_file(self.source), "FAILED")
        self.assertEqual(self.source.read_bytes(), self.prefix)
        self.assertFalse(self.archive.exists())

    def test_archive_rename_failure_preserves_original(self):
        real_replace = os.replace
        def replace(src, dst):
            if Path(dst) == self.archive:
                raise OSError("archive publish failed")
            return real_replace(src, dst)
        with patch.object(os, "replace", replace), self.assertLogs(level="ERROR"):
            self.assertEqual(self.archiver.process_file(self.source), "FAILED")
        self.assertTrue(self.source.exists())
        self.assertFalse(self.archive.exists())
        self.assertEqual(lzma.decompress(self.partial.read_bytes()), self.prefix)

    def test_directory_fsync_failure_before_unlink_is_recoverable(self):
        with patch.object(self.archiver, "fsync_directory", side_effect=OSError("directory failed")), self.assertLogs(level="ERROR"):
            self.assertEqual(self.archiver.process_file(self.source), "FAILED")
        self.assertTrue(self.source.exists())
        self.assertEqual(lzma.decompress(self.archive.read_bytes()), self.prefix)
        self.assertEqual(self.archiver.process_file(self.source), "VERIFIED_EXISTING")

    def test_existing_archive_fsync_failure_preserves_original(self):
        self.archiver.compress_xz(self.source, self.archive, level=0)
        real_sync = os.fsync
        def sync(fd):
            if os.fstat(fd).st_ino == self.archive.stat().st_ino:
                raise OSError("existing archive sync failed")
            return real_sync(fd)
        with patch.object(os, "fsync", sync), self.assertLogs(level="ERROR"):
            self.assertEqual(self.archiver.process_file(self.source), "FAILED")
        self.assertEqual(self.source.read_bytes(), self.prefix)

    def test_manifest_failure_after_publish_preserves_original(self):
        real_hash = self.archiver.write_hash_file
        def write_hash(target, *args):
            if target == self.archive:
                raise OSError("archive manifest failed")
            return real_hash(target, *args)
        with patch.object(self.archiver, "write_hash_file", write_hash), self.assertLogs(level="ERROR"):
            self.assertEqual(self.archiver.process_file(self.source), "FAILED")
        self.assertTrue(self.source.exists())
        self.assertEqual(self.archiver.process_file(self.source), "VERIFIED_EXISTING")

    def test_unlink_failure_is_failed_not_false_success(self):
        real_unlink = Path.unlink
        def unlink(path, *args, **kwargs):
            if path == self.source:
                raise OSError("source unlink failed")
            return real_unlink(path, *args, **kwargs)
        with patch.object(Path, "unlink", unlink), self.assertLogs(level="ERROR"):
            self.assertEqual(self.archiver.process_file(self.source), "FAILED")
        self.assertTrue(self.source.exists())
        self.assertEqual(self.archiver.process_file(self.source), "VERIFIED_EXISTING")

    def test_post_unlink_directory_failure_retains_durable_archive(self):
        real_sync = self.archiver.fsync_directory
        def syncing(path):
            if not self.source.exists():
                raise OSError("post-unlink sync failed")
            return real_sync(path)
        with patch.object(self.archiver, "fsync_directory", syncing), self.assertLogs(level="ERROR"):
            self.assertEqual(self.archiver.process_file(self.source), "FAILED")
        self.assertFalse(self.source.exists())
        self.assertEqual(lzma.decompress(self.archive.read_bytes()), self.prefix)

    def test_source_mutation_during_verification_blocks_deletion(self):
        real_verify = self.archiver.verify_archive
        def verify(*args):
            valid = real_verify(*args)
            self.source.write_bytes(self.prefix + self.payload)
            return valid
        with patch.object(self.archiver, "verify_archive", verify), self.assertLogs(level="ERROR"):
            self.assertEqual(self.archiver.process_file(self.source), "FAILED")
        self.assertEqual(self.source.read_bytes(), self.prefix + self.payload)
        self.assertFalse(self.archive.exists())

    def test_lock_anchor_survives_archiving(self):
        self.assertEqual(self.archiver.process_file(self.source), "COMPRESSED_AND_DELETED")
        self.assertTrue(storage.lock_path(self.source).exists())

    def test_lzma_close_failure_preserves_original(self):
        original_class = self.archiver.lzma.LZMAFile
        class FailingLzma(original_class):
            def close(inner):
                # Fail once on close after the real encoder has finalized.
                result = super(FailingLzma, inner).close()
                if not getattr(inner, "failed_close", False):
                    inner.failed_close = True
                    raise OSError("LZMA close failed")
                return result
        with patch.object(self.archiver.lzma, "LZMAFile", FailingLzma), self.assertLogs(level="ERROR"):
            self.assertEqual(self.archiver.process_file(self.source), "FAILED")
        self.assertEqual(self.source.read_bytes(), self.prefix)
        self.assertFalse(self.archive.exists())

    def test_archive_raw_write_flush_close_failures_preserve_original(self):
        real_open = Path.open
        for stage in ("write", "flush", "close"):
            with self.subTest(stage=stage):
                self.partial.unlink(missing_ok=True)
                fault = {"fired": False, "writes": 0}
                def opening(path, mode="r", *args, **kwargs):
                    file = real_open(path, mode, *args, **kwargs)
                    if path == self.partial and mode == "xb":
                        return FileProxy(file, fault, stage)
                    return file
                with patch.object(Path, "open", opening), self.assertLogs(level="ERROR"):
                    self.assertEqual(self.archiver.process_file(self.source), "FAILED")
                self.assertTrue(fault["fired"])
                self.assertEqual(self.source.read_bytes(), self.prefix)
                self.assertFalse(self.archive.exists())

    def test_unlock_failure_after_ack_does_not_clear_a_later_batch(self):
        client = self.client(); client.data_buffer = [{"price": 42}]
        real_close = storage.FileLock.close
        fired = False
        def closing(lock):
            nonlocal fired
            real_close(lock)
            if lock.path == storage.lock_path(self.source) and not fired:
                fired = True
                raise OSError("unlock close reported an error")
        with patch.object(storage.FileLock, "close", closing), self.assertLogs(level="ERROR"):
            client.save_price_data()
        self.assertEqual(client.data_buffer, [])
        self.assertIsNone(client._pending)
        client.data_buffer = [{"price": 43}]
        client.save_price_data()
        self.assertEqual([json.loads(x)["price"] for x in self.source.read_bytes().splitlines()], [41, 42, 43])

    def test_shared_reader_lock_blocks_append_and_archive(self):
        with storage.FileLock(storage.lock_path(self.source), shared=True):
            with self.assertRaises(BlockingIOError):
                self.batch().commit()
            self.assertEqual(self.archiver.process_file(self.source), "SKIPPED")
        self.assertEqual(self.source.read_bytes(), self.prefix)

    def test_callback_shutdown_join_finishes_before_durable_flush(self):
        client = self.client()
        closing = threading.Event()
        worker = threading.Thread(target=lambda: (
            closing.wait(3), client.handle_ticker({"data": {"lastPrice": "42"}})
        ))
        worker.start()
        client.ws = SimpleNamespace(exit=closing.set, wst=worker)
        client.close()
        self.assertFalse(worker.is_alive())
        self.assertIsNone(client.ws)
        self.assertEqual(client.data_buffer, [])
        self.assertEqual([json.loads(x)["price"] for x in self.source.read_bytes().splitlines()], [41, 42])

    def test_eligibility_is_rechecked_after_scan(self):
        with patch.object(self.archiver, "is_eligible", return_value=False) as eligible:
            self.assertEqual(self.archiver.process_file(self.source, require_eligible=True), "SKIPPED")
        eligible.assert_called_once()
        self.assertTrue(self.source.exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
