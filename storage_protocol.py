"""Cooperative local-POSIX storage protocol; see docs/storage-integrity.md.

Lock files are persistent inode anchors: NEVER unlink or replace them. A pending
append contains the exact bytes of one batch, not a second copy of the history.
Uncooperative writers and filesystems without flock/fsync semantics are unsupported.
"""
from __future__ import annotations

import base64
import fcntl
import hashlib
import json
import os
from pathlib import Path
import stat
import tempfile
from typing import BinaryIO


class StorageConflict(RuntimeError):
    """Refuse to modify bytes whose ownership or identity is uncertain."""


class RollbackFailed(StorageConflict):
    """The intent and caller's buffer must survive; no blind append is allowed."""


def pending_path(source: Path) -> Path:
    return source.with_name(source.name + ".append.pending")


def lock_path(source: Path) -> Path:
    return source.with_name(source.name + ".lock")


def fsync_directory(directory: Path) -> None:
    fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


class FileLock:
    """An advisory lock held by this object until close(), including failed I/O."""

    def __init__(self, path: Path, *, shared: bool = False):
        self.path = Path(path)
        self.file = self.path.open("a+b", buffering=0)
        try:
            mode = fcntl.LOCK_SH if shared else fcntl.LOCK_EX
            fcntl.flock(self.file.fileno(), mode | fcntl.LOCK_NB)
        except BaseException:
            self.file.close()
            raise

    def close(self) -> None:
        # Closing releases flock. Keep the pathname/inode for every participant.
        self.file.close()

    def __enter__(self) -> FileLock:
        return self

    def __exit__(self, *exc) -> None:
        self.close()


# This additional anchor protects the *set* of logical day-locks. Readers hold
# it shared across D/D+1 discovery; a new day cannot appear halfway through a
# snapshot. Existing-day append/compression still use only their per-day lock.
NAMESPACE_LOCK = ".archive.namespace.lock"


def initialize_storage(directory: Path) -> None:
    """Durably create the namespace anchor, without replacing existing inodes."""
    with FileLock(directory / NAMESPACE_LOCK) as anchor:
        os.fsync(anchor.file.fileno())
        fsync_directory(directory)


def source_lock(source: Path) -> FileLock:
    """Acquire a mutation lock; serialize first creation with RO readers.

    Namespace -> day is the only creation order. Existing anchors are NEVER
    removed, so a normal append does not block readers of unrelated old days.
    Every managed source must be created only after this function returns.
    """
    source = Path(source)
    anchor = lock_path(source)
    namespace = source.parent / NAMESPACE_LOCK
    if anchor.exists() and namespace.exists():
        return FileLock(anchor)
    with FileLock(namespace) as gate:
        lock = FileLock(anchor)
        try:
            os.fsync(gate.file.fileno())
            os.fsync(lock.file.fileno())
            fsync_directory(source.parent)
        except BaseException:
            lock.close()
            raise
        return lock


def write_all(file: BinaryIO, payload: bytes) -> None:
    """Handle positive short writes; FileIO has no deferred Python write buffer."""
    view = memoryview(payload)
    while view:
        count = file.write(view)
        if count is None or count <= 0 or count > len(view):
            raise OSError("Storage write made no valid progress")
        view = view[count:]


def atomic_bytes(path: Path, payload: bytes) -> None:
    """Publish bytes only after file close/fsync, then synchronize the directory."""
    fd, name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
    temporary = Path(name)
    try:
        with os.fdopen(fd, "wb", buffering=0) as file:
            write_all(file, payload)
            file.flush()
            os.fsync(file.fileno())
        os.replace(temporary, path)
        fsync_directory(path.parent)
    finally:
        # Before publication this file is never an acknowledged/pending batch.
        temporary.unlink(missing_ok=True)


def _regular_stat(source: Path):
    result = source.lstat()
    if not stat.S_ISREG(result.st_mode):
        raise StorageConflict(f"Not a regular source file: {source}")
    return result


class AppendBatch:
    """A retryable, durable append intent tied to one path/inode/offset/payload.

    The owner keeps this object AND the buffer until commit() returns, removes
    exactly the acknowledged prefix from the buffer, then calls close(). A failed
    commit retains the per-file lock, even when pending-marker cleanup failed.
    """

    def __init__(self, source: Path, payload: bytes, *, record: dict | None = None):
        self.source = Path(source)
        self.payload = payload
        if not payload or not payload.endswith(b"\n"):
            raise ValueError("Append batch must contain complete JSONL lines")
        self.record = record
        self.lock = None
        self.committed = False

    def _acquire(self) -> None:
        if self.lock is None:
            self.lock = source_lock(self.source)
        if self.source.with_name(self.source.name + ".xz").exists():
            raise StorageConflict(f"Refusing to append to an archived day: {self.source}")

    def _prepare(self) -> None:
        self._acquire()
        marker = pending_path(self.source)
        if self.record is None:
            if marker.exists():
                raise StorageConflict(f"Unrecovered append intent: {marker}")
            if not self.source.exists():
                # Exclusive creation; the entry is durable before publishing intent.
                with self.source.open("xb", buffering=0) as file:
                    os.fsync(file.fileno())
                fsync_directory(self.source.parent)
            info = _regular_stat(self.source)
            if info.st_size:
                with self.source.open("rb", buffering=0) as file:
                    file.seek(-1, os.SEEK_END)
                    if file.read(1) != b"\n":
                        raise StorageConflict(f"Existing source has an incomplete tail: {self.source}")
            self.record = {
                "version": 1, "device": info.st_dev, "inode": info.st_ino,
                "offset": info.st_size,
                "payload_b64": base64.b64encode(self.payload).decode("ascii"),
                "sha256": hashlib.sha256(self.payload).hexdigest(),
            }
        if marker.exists():
            disk = json.loads(marker.read_text(encoding="utf-8"))
            if disk != self.record:
                raise StorageConflict(f"Append intent changed: {marker}")
            # A prior publication may have succeeded while its directory fsync failed.
            fsync_directory(marker.parent)
        else:
            atomic_bytes(marker, json.dumps(self.record, sort_keys=True).encode("utf-8") + b"\n")

    def _inspect(self, file: BinaryIO) -> int:
        expected = self.record
        info = os.fstat(file.fileno())
        path_info = _regular_stat(self.source)
        identity = (expected["device"], expected["inode"])
        if (info.st_dev, info.st_ino) != identity or (path_info.st_dev, path_info.st_ino) != identity:
            raise StorageConflict(f"Source identity changed: {self.source}")
        length = info.st_size - expected["offset"]
        if length < 0 or length > len(self.payload):
            raise StorageConflict(f"Unexpected source length: {self.source}")
        file.seek(expected["offset"])
        if file.read(length) != self.payload[:length]:
            raise StorageConflict(f"Unexpected bytes after append boundary: {self.source}")
        return length

    def _rollback(self) -> None:
        # Reopen raw: no buffered close can later re-append bytes after truncate.
        with self.source.open("r+b", buffering=0) as file:
            self._inspect(file)
            os.ftruncate(file.fileno(), self.record["offset"])
            os.fsync(file.fileno())

    def _write_and_sync(self) -> None:
        with self.source.open("r+b", buffering=0) as file:
            existing = self._inspect(file)
            if existing == len(self.payload):
                # Crash/retry after a complete append: sync and acknowledge, no replay.
                file.flush()
                os.fsync(file.fileno())
                return
            if existing:
                # A partial append must be durably rolled back before any new write.
                os.ftruncate(file.fileno(), self.record["offset"])
                os.fsync(file.fileno())
            file.seek(self.record["offset"])
            write_all(file, self.payload)
            file.flush()
            os.fsync(file.fileno())

    def commit(self) -> None:
        self._prepare()  # No mutation of source until the complete intent is durable.
        if not self.committed:
            try:
                self._write_and_sync()
            except Exception as original:
                try:
                    self._rollback()
                except Exception as rollback:
                    raise RollbackFailed(
                        f"Append failed ({original}); rollback failed ({rollback}); "
                        f"retaining intent, lock and buffer for {self.source}"
                    ) from rollback
                raise
            self.committed = True
        else:
            # Cleanup-only retry must still prove the committed batch is intact.
            with self.source.open("rb", buffering=0) as file:
                if self._inspect(file) != len(self.payload):
                    raise StorageConflict(f"Committed append changed: {self.source}")
                os.fsync(file.fileno())
        pending_path(self.source).unlink(missing_ok=True)
        fsync_directory(self.source.parent)

    def close(self) -> None:
        if self.lock is not None:
            self.lock.close()
            self.lock = None

    @classmethod
    def from_pending(cls, marker: Path) -> AppendBatch:
        suffix = ".append.pending"
        if not marker.name.endswith(".jsonl" + suffix):
            raise StorageConflict(f"Invalid intent filename: {marker}")
        source = marker.with_name(marker.name[:-len(suffix)])
        record = json.loads(marker.read_text(encoding="utf-8"))
        if not isinstance(record, dict) or record.get("version") != 1:
            raise StorageConflict(f"Invalid intent version: {marker}")
        for key in ("device", "inode", "offset"):
            if type(record.get(key)) is not int or record[key] < 0:
                raise StorageConflict(f"Invalid intent {key}: {marker}")
        payload = base64.b64decode(record["payload_b64"], validate=True)
        if hashlib.sha256(payload).hexdigest() != record.get("sha256"):
            raise StorageConflict(f"Intent checksum mismatch: {marker}")
        # Validate the intent's records before replaying it; never repair arbitrary history.
        for line in payload.splitlines():
            if not isinstance(json.loads(line), dict):
                raise StorageConflict(f"Invalid intent JSONL: {marker}")
        return cls(source, payload, record=record)


def recover_pending(directory: Path) -> int:
    """Caller MUST own .collector.lock; finish accepted intents before subscription."""
    recovered = 0
    for marker in sorted(directory.glob("*.jsonl.append.pending")):
        batch = AppendBatch.from_pending(marker)
        try:
            batch.commit()
            recovered += 1
        finally:
            batch.close()
    return recovered
