"""Check collector output freshness without importing the WebSocket client."""

from pathlib import Path
import sys
import time

from config import FLUSH_INTERVAL, SYMBOL, WS_DIR_PATH


def healthcheck():
    if not SYMBOL:
        return False
    try:
        if any(Path(WS_DIR_PATH).glob("*.jsonl.append.pending")):
            return False
        latest_write = max(
            (path.stat().st_mtime for path in Path(WS_DIR_PATH).glob("price_data_*.jsonl")),
            default=0,
        )
        return latest_write > 0 and time.time() - latest_write <= max(180, 3 * FLUSH_INTERVAL)
    except OSError:
        return False


if __name__ == "__main__":
    sys.exit(0 if healthcheck() else 1)
