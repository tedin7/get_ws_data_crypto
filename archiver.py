import os
import time
import lzma
import hashlib
import logging
from logging.handlers import RotatingFileHandler
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Tuple

from storage_protocol import FileLock, atomic_bytes, fsync_directory, lock_path, pending_path

# Configuration via environment variables
ARCHIVER_ENABLED = os.environ.get("ARCHIVER_ENABLED", "true").lower() == "true"
ARCHIVER_SCAN_INTERVAL_SECONDS = int(os.environ.get("ARCHIVER_SCAN_INTERVAL_SECONDS", "3600"))
ARCHIVER_UNCOMPRESSED_DAYS = int(os.environ.get("ARCHIVER_UNCOMPRESSED_DAYS", "2"))
ARCHIVER_MIN_AGE_MINUTES = int(os.environ.get("ARCHIVER_MIN_AGE_MINUTES", "60"))
ARCHIVER_COMPRESSION_LEVEL = int(os.environ.get("ARCHIVER_COMPRESSION_LEVEL", "6"))

# Resolve WS_DIR_PATH from env or fallback to ./ws_data
WS_DIR_PATH = Path(os.environ.get("WS_DIR_PATH", os.path.abspath("ws_data")))

LOGS_DIR = WS_DIR_PATH / "logs"
LOGS_DIR.mkdir(parents=True, exist_ok=True)
ARCHIVER_LOG_FILE = LOGS_DIR / "archiver.log"

logging.basicConfig(
    handlers=[RotatingFileHandler(ARCHIVER_LOG_FILE, maxBytes=10 * 1024 * 1024, backupCount=5)],
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

CHUNK_SIZE = 4 * 1024 * 1024  # 4 MiB


def _now():
    return datetime.now(timezone.utc)


def compute_sha256(path: Path) -> Tuple[str, int]:
    h = hashlib.sha256()
    total = 0
    with path.open("rb") as f:
        while True:
            b = f.read(CHUNK_SIZE)
            if not b:
                break
            h.update(b)
            total += len(b)
    return h.hexdigest(), total


def write_hash_file(target: Path, hex_digest: str, size_bytes: int) -> None:
    hash_path = target.with_suffix(target.suffix + ".sha256")
    line = f"{hex_digest}  {target.name}  {size_bytes}\n"
    atomic_bytes(hash_path, line.encode("utf-8"))


def compress_xz(src_path: Path, dst_tmp_path: Path, level: int = 6) -> None:
    # LZMA.close() emits the footer. Keep the underlying file open until AFTER
    # that close, then flush/fsync all compressed bytes; propagate close failures.
    with src_path.open("rb") as fin, dst_tmp_path.open("xb") as raw:
        with lzma.LZMAFile(raw, "wb", preset=level, check=lzma.CHECK_CRC64) as encoded:
            while True:
                block = fin.read(CHUNK_SIZE)
                if not block:
                    break
                encoded.write(block)
        raw.flush()
        os.fsync(raw.fileno())


def verify_archive(archive_path: Path, expected_hash_hex: str) -> bool:
    h = hashlib.sha256()
    try:
        with lzma.open(archive_path, "rb") as fin:
            while True:
                b = fin.read(CHUNK_SIZE)
                if not b:
                    break
                h.update(b)
        return h.hexdigest() == expected_hash_hex
    except Exception as e:
        logging.error(f"Verification failed for {archive_path}: {e}")
        return False


def is_eligible(jsonl_path: Path, keep_days: int, min_age_minutes: int) -> bool:
    try:
        stat = jsonl_path.stat()
    except FileNotFoundError:
        return False
    mtime = datetime.fromtimestamp(stat.st_mtime, timezone.utc)
    age = _now() - mtime
    if age < timedelta(minutes=min_age_minutes):
        return False
    # If file has date in name price_data_YYYY-MM-DD.jsonl we can be precise
    # else fallback to age vs keep_days
    try:
        parts = jsonl_path.name.split("_")
        if len(parts) >= 3:
            date_part = parts[-1].split(".")[0]  # YYYY-MM-DD
            file_date = datetime.strptime(date_part, "%Y-%m-%d").date()
            cutoff = (_now().date() - timedelta(days=keep_days))
            if file_date >= cutoff:
                return False
    except Exception:
        # Fallback to age-based rule: older than keep_days
        if age < timedelta(days=keep_days):
            return False
    return True


def list_eligible_files(ws_dir_path: Path, keep_days: int, min_age_minutes: int) -> list:
    files = []
    for p in ws_dir_path.glob("*.jsonl"):
        if is_eligible(p, keep_days, min_age_minutes):
            files.append(p)
    return sorted(files)


def safe_remove(path: Path) -> None:
    try:
        path.unlink(missing_ok=True)  # Python 3.8+: emulate
    except TypeError:
        try:
            if path.exists():
                path.unlink()
        except Exception as e:
            logging.error(f"Failed to remove {path}: {e}")
    except Exception as e:
        logging.error(f"Failed to remove {path}: {e}")


def _source_signature(path: Path) -> tuple:
    info = path.stat()
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)


def _partial_is_stale(path: Path) -> bool:
    modified = datetime.fromtimestamp(path.stat().st_mtime, timezone.utc)
    return (_now() - modified) > timedelta(minutes=ARCHIVER_MIN_AGE_MINUTES)


def _process_locked(src_jsonl_path: Path) -> str:
    xz_path = src_jsonl_path.with_suffix(src_jsonl_path.suffix + ".xz")
    marker = src_jsonl_path.with_suffix(src_jsonl_path.suffix + ".verify_failed")
    temporary = xz_path.with_suffix(xz_path.suffix + ".part")
    if pending_path(src_jsonl_path).exists():
        return "SKIPPED"
    if src_jsonl_path.is_symlink() or not src_jsonl_path.is_file():
        return "SKIPPED"
    # The age check is NOT ownership: the shared per-file lock is held throughout.
    # Do not truncate a recent partial or an archive left by an unknown participant.
    if temporary.exists() and not xz_path.exists():
        if not _partial_is_stale(temporary):
            return "SKIPPED"
        temporary.unlink()
        fsync_directory(temporary.parent)

    signature = _source_signature(src_jsonl_path)
    expected, size = compute_sha256(src_jsonl_path)
    write_hash_file(src_jsonl_path, expected, size)
    existing = xz_path.exists()
    candidate = xz_path if existing else temporary
    if not existing:
        compress_xz(src_jsonl_path, temporary, level=ARCHIVER_COMPRESSION_LEVEL)
    # Verify complete decompression before making a NEW archive visible.
    if not verify_archive(candidate, expected):
        atomic_bytes(marker, f"{_now().isoformat()} hash mismatch\n".encode("utf-8"))
        logging.error("Archive verification mismatch for %s", src_jsonl_path.name)
        return "FAILED"
    if _source_signature(src_jsonl_path) != signature or compute_sha256(src_jsonl_path) != (expected, size):
        logging.error("Source changed during archive; keeping original: %s", src_jsonl_path)
        return "FAILED"
    if not existing:
        os.replace(temporary, xz_path)
    # Existing archives also need a successful fsync before deleting their source.
    with xz_path.open("rb") as archive:
        os.fsync(archive.fileno())
    fsync_directory(xz_path.parent)
    archive_digest, archive_size = compute_sha256(xz_path)
    write_hash_file(xz_path, archive_digest, archive_size)
    if pending_path(src_jsonl_path).exists() or _source_signature(src_jsonl_path) != signature:
        logging.error("Source ownership changed; keeping original: %s", src_jsonl_path)
        return "FAILED"
    # Unlike safe_remove(), deletion failures must not be reported as success.
    src_jsonl_path.unlink()
    try:
        fsync_directory(src_jsonl_path.parent)
    except OSError:
        logging.error("Source removed but directory sync failed; durable archive retained: %s", xz_path)
        raise
    safe_remove(marker)
    return "VERIFIED_EXISTING" if existing else "COMPRESSED_AND_DELETED"


def process_file(src_jsonl_path: Path, *, require_eligible: bool = False) -> str:
    """Serialize archive/append/read operations; never archive an uncertain batch."""
    try:
        with FileLock(lock_path(src_jsonl_path)):
            # run_once's directory scan is only a hint; recheck after acquiring lock.
            if require_eligible and not is_eligible(
                src_jsonl_path, ARCHIVER_UNCOMPRESSED_DAYS, ARCHIVER_MIN_AGE_MINUTES
            ):
                return "SKIPPED"
            return _process_locked(src_jsonl_path)
    except BlockingIOError:
        return "SKIPPED"
    except Exception as error:
        logging.error("Error processing %s: %s", src_jsonl_path, error)
        return "FAILED"


def run_once() -> None:
    ws = WS_DIR_PATH
    ws.mkdir(parents=True, exist_ok=True)
    LOGS_DIR.mkdir(parents=True, exist_ok=True)

    files = list_eligible_files(ws, ARCHIVER_UNCOMPRESSED_DAYS, ARCHIVER_MIN_AGE_MINUTES)
    logging.info(f"Archiver scan: ws_dir={ws} eligible_files={len(files)} keep_days={ARCHIVER_UNCOMPRESSED_DAYS} min_age_minutes={ARCHIVER_MIN_AGE_MINUTES}")
    for p in files:
        start = time.time()
        result = process_file(p, require_eligible=True)
        elapsed = int((time.time() - start) * 1000)
        logging.info(f"Archiver processed file={p.name} result={result} elapsed_ms={elapsed}")


def main_loop() -> None:
    if not ARCHIVER_ENABLED:
        logging.info("Archiver disabled by ARCHIVER_ENABLED=false. Exiting.")
        return
    logging.info(f"Archiver starting loop compression_level={ARCHIVER_COMPRESSION_LEVEL}")
    while True:
        try:
            run_once()
        except Exception as e:
            logging.error(f"Archiver run_once error: {e}")
        time.sleep(ARCHIVER_SCAN_INTERVAL_SECONDS)


if __name__ == "__main__":
    # One-shot if ARCHIVER_SCAN_INTERVAL_SECONDS <= 0, else loop
    if ARCHIVER_SCAN_INTERVAL_SECONDS <= 0:
        run_once()
    else:
        main_loop()
