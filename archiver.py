import os
import time
import lzma
import hashlib
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional, Tuple

# Configuration via environment variables
ARCHIVER_ENABLED = os.environ.get("ARCHIVER_ENABLED", "true").lower() == "true"
ARCHIVER_SCAN_INTERVAL_SECONDS = int(os.environ.get("ARCHIVER_SCAN_INTERVAL_SECONDS", "3600"))
ARCHIVER_UNCOMPRESSED_DAYS = int(os.environ.get("ARCHIVER_UNCOMPRESSED_DAYS", "2"))
ARCHIVER_MIN_AGE_MINUTES = int(os.environ.get("ARCHIVER_MIN_AGE_MINUTES", "60"))
ARCHIVER_COMPRESSION_LEVEL = int(os.environ.get("ARCHIVER_COMPRESSION_LEVEL", "9"))

# Resolve WS_DIR_PATH from env or fallback to ./ws_data
WS_DIR_PATH = Path(os.environ.get("WS_DIR_PATH", os.path.abspath("ws_data")))

LOGS_DIR = WS_DIR_PATH / "logs"
LOGS_DIR.mkdir(parents=True, exist_ok=True)
ARCHIVER_LOG_FILE = LOGS_DIR / "archiver.log"

logging.basicConfig(
    filename=str(ARCHIVER_LOG_FILE),
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
    # Write alongside target with .sha256 extension
    hash_path = target.with_suffix(target.suffix + ".sha256")
    line = f"{hex_digest}  {target.name}  {size_bytes}\n"
    tmp = hash_path.with_suffix(hash_path.suffix + ".part")
    with tmp.open("w", encoding="utf-8") as f:
        f.write(line)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, hash_path)


def parse_hash_file(hash_file: Path) -> Optional[Tuple[str, int]]:
    try:
        with hash_file.open("r", encoding="utf-8") as f:
            line = f.readline().strip()
        # format: <hex>  <basename>  <size_bytes>
        parts = [p for p in line.split("  ") if p]
        if len(parts) < 3:
            return None
        hex_digest = parts[0].strip()
        size_bytes = int(parts[-1].strip())
        return hex_digest, size_bytes
    except Exception as e:
        logging.error(f"Failed to parse hash file {hash_file}: {e}")
        return None


def compress_xz(src_path: Path, dst_tmp_path: Path, level: int = 9) -> None:
    # Stream compression to tmp file
    with src_path.open("rb") as fin, lzma.open(dst_tmp_path, "wb", preset=level, check=lzma.CHECK_CRC64) as fout:
        while True:
            b = fin.read(CHUNK_SIZE)
            if not b:
                break
            fout.write(b)
        fout.flush()
        # lzma handles its own checksums, but still fsync file descriptor
        fout_fd = getattr(fout, "fileno", None)
        if callable(fout_fd):
            os.fsync(fout.fileno())


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


def process_file(src_jsonl_path: Path) -> str:
    """
    Returns: one of 'COMPRESSED_AND_DELETED', 'VERIFIED_EXISTING', 'SKIPPED', 'FAILED'
    """
    try:
        # Prepare paths
        jsonl_hash_path = src_jsonl_path.with_suffix(src_jsonl_path.suffix + ".sha256")
        xz_path = src_jsonl_path.with_suffix(src_jsonl_path.suffix + ".xz")
        xz_hash_path = xz_path.with_suffix(xz_path.suffix + ".sha256")
        verify_failed_marker = src_jsonl_path.with_suffix(src_jsonl_path.suffix + ".verify_failed")
        xz_tmp_path = xz_path.with_suffix(xz_path.suffix + ".part")

        # Handle stale .part
        if xz_tmp_path.exists():
            try:
                # remove stale .part older than min age
                stat = xz_tmp_path.stat()
                if (_now() - datetime.fromtimestamp(stat.st_mtime)) > timedelta(minutes=ARCHIVER_MIN_AGE_MINUTES):
                    logging.warning(f"Removing stale partial archive {xz_tmp_path}")
                    safe_remove(xz_tmp_path)
            except Exception as e:
                logging.error(f"Error inspecting partial archive {xz_tmp_path}: {e}")

        # Initialize and, if present, load existing digest from the adjacent .sha256 file
        hex_digest = None
        if os.path.exists(jsonl_hash_path):
            with open(jsonl_hash_path, "r") as hf:
                content = hf.read().strip()
                if content:
                    hex_digest = content

        if hex_digest:  # Cached
            logging.debug(f"Using cached hash for {jsonl_hash_path}")
        else:  # Preserve original hex_digest variable name for downstream logic
            parsed = parse_hash_file(jsonl_hash_path)
            if not parsed:
                # re-compute if parse failed
                hex_digest, size_bytes = compute_sha256(src_jsonl_path)
                write_hash_file(src_jsonl_path, hex_digest, size_bytes)
            else:
                hex_digest, _size_bytes = parsed

        # If archive already exists, verify and delete original if valid
        if xz_path.exists():
            if verify_archive(xz_path, hex_digest):
                # ensure we have an archive hash manifest (optional informational)
                if not xz_hash_path.exists():
                    arch_hex, arch_size = compute_sha256(xz_path)
                    write_hash_file(xz_path, arch_hex, arch_size)
                # delete original jsonl
                safe_remove(src_jsonl_path)
                safe_remove(verify_failed_marker)
                logging.info(f"Verified existing archive and removed original: file={src_jsonl_path.name}")
                return "VERIFIED_EXISTING"
            else:
                # mark failure, keep both files
                verify_failed_marker.write_text(f"{_now().isoformat()} hash mismatch\n", encoding="utf-8")
                logging.error(f"Archive verification mismatch for {src_jsonl_path.name}")
                return "FAILED"

        # Create archive
        compress_xz(src_jsonl_path, xz_tmp_path, level=ARCHIVER_COMPRESSION_LEVEL)
        # Atomic rename
        os.replace(xz_tmp_path, xz_path)

        # Verify archive
        if verify_archive(xz_path, hex_digest):
            # Write archive hash manifest (informational)
            arch_hex, arch_size = compute_sha256(xz_path)
            write_hash_file(xz_path, arch_hex, arch_size)
            # Delete original
            safe_remove(src_jsonl_path)
            safe_remove(verify_failed_marker)
            logging.info(f"Compressed and deleted original: file={src_jsonl_path.name} saved_bytes=unknown")
            return "COMPRESSED_AND_DELETED"
        else:
            # Verification failed; keep both
            verify_failed_marker.write_text(f"{_now().isoformat()} hash mismatch\n", encoding="utf-8")
            logging.error(f"Verification failed after compression for {src_jsonl_path.name}")
            return "FAILED"

    except Exception as e:
        logging.error(f"Unexpected error processing {src_jsonl_path}: {e}")
        return "FAILED"


def run_once() -> None:
    ws = WS_DIR_PATH
    ws.mkdir(parents=True, exist_ok=True)
    LOGS_DIR.mkdir(parents=True, exist_ok=True)

    files = list_eligible_files(ws, ARCHIVER_UNCOMPRESSED_DAYS, ARCHIVER_MIN_AGE_MINUTES)
    logging.info(f"Archiver scan: ws_dir={ws} eligible_files={len(files)} keep_days={ARCHIVER_UNCOMPRESSED_DAYS} min_age_minutes={ARCHIVER_MIN_AGE_MINUTES}")
    for p in files:
        start = time.time()
        result = process_file(p)
        elapsed = int((time.time() - start) * 1000)
        logging.info(f"Archiver processed file={p.name} result={result} elapsed_ms={elapsed}")


def main_loop() -> None:
    if not ARCHIVER_ENABLED:
        logging.info("Archiver disabled by ARCHIVER_ENABLED=false. Exiting.")
        return
    logging.info("Archiver starting loop")
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
