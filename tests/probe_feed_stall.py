"""Offline characterization of the real run loop; no market connection.

Exit 1 means the connected socket with a residual ticker hid the timeout.
This diagnostic does not certify a fix or replace the regression suite.
"""

import asyncio
from datetime import datetime, timedelta
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import threading
from types import SimpleNamespace
from unittest.mock import patch


class EndProbe(BaseException):
    pass


async def scenario(kind, wall_shift=0, constructor_delay=0, subscription_delay=0):
    with tempfile.TemporaryDirectory() as folder:
        root = Path(folder)
        (root / "logs").mkdir()
        config = SimpleNamespace(
            WS_DIR=folder, WS_DIR_PATH=folder, BUFFER_SIZE=100,
            FLUSH_INTERVAL=60, TESTNET=False, SYMBOL="BTCUSDT",
            MAX_RECONNECT_ATTEMPTS=3, WS_RECONNECT_DELAY=1,
            ERROR_COOLDOWN_TIME=1,
        )
        spec = importlib.util.spec_from_file_location(
            "collector_probe", Path(__file__).resolve().parents[1] / "main.py"
        )
        module = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, {
            "config": config,
            "pybit.unified_trading": SimpleNamespace(WebSocket=None),
            "healthcheck": SimpleNamespace(healthcheck=lambda: True),
        }), patch("logging.basicConfig") as logging_setup:
            spec.loader.exec_module(module)
        handlers = logging_setup.call_args.kwargs["handlers"]
        elapsed = 0
        start = datetime(2026, 10, 19, 12)

        class Clock:
            @staticmethod
            def now():
                shift = wall_shift if elapsed >= 10 else 0
                return start + timedelta(seconds=elapsed + shift)

        client = module.BybitWebSocketClient()
        client.last_flush_time = start
        close_at = None
        ticks = 0
        storage_release = threading.Event()
        storage_held = threading.Event()
        storage_timed_out = []
        storage_worker = None

        def hold_storage():
            with client._buffer_lock:
                storage_held.set()
                storage_timed_out.append(not storage_release.wait(timeout=2))

        def tick():
            nonlocal ticks
            ticks += 1
            client.handle_ticker({"data": {"lastPrice": "42"}})

        def subscribe(**kwargs):
            nonlocal elapsed
            if kind not in ("no_callback", "late_first_ticker"):
                tick()
            elapsed += subscription_delay

        socket = SimpleNamespace(
            ticker_stream=subscribe, is_connected=lambda: True,
            exit=lambda: None, wst=SimpleNamespace(join=lambda: None),
        )

        def websocket(**kwargs):
            nonlocal elapsed
            elapsed += constructor_delay
            return socket

        async def sleep(seconds):
            nonlocal elapsed, storage_worker
            elapsed += seconds
            if kind == "storage_busy" and elapsed == 5:
                storage_worker = threading.Thread(target=hold_storage)
                storage_worker.start()
                if not storage_held.wait(timeout=1):
                    raise AssertionError("storage lock not acquired")
            if kind == "unchanged_price":
                tick()
            if kind == "threaded_price":
                callback = threading.Thread(target=tick)
                callback.start()
                callback.join(timeout=2)
                if callback.is_alive():
                    raise AssertionError("callback did not finish")
            if kind == "late_first_ticker" and elapsed == 20:
                tick()
            if kind == "invalid_messages":
                client.handle_ticker({"data": {"lastPrice": "nan"}})
            if kind == "flush_only" and elapsed == 5:
                client.save_price_data()
            limit = constructor_delay + subscription_delay + (
                100 if kind == "late_first_ticker" else 80
            )
            if elapsed >= limit:
                raise EndProbe()

        def reconnect_close():
            nonlocal close_at
            close_at = elapsed
            raise EndProbe()

        try:
            with patch.object(module, "datetime", Clock), patch.object(
                module.time, "monotonic", side_effect=lambda: float(elapsed)
            ), patch.object(module, "WebSocket", side_effect=websocket), patch.object(
                module.asyncio, "sleep", sleep
            ), patch.object(client, "close", reconnect_close):
                try:
                    await client.run()
                except EndProbe:
                    pass
            result = {
                "case": kind, "ticks": ticks, "elapsed_s": elapsed,
                "reconnect_close_at_s": close_at,
                "buffered": len(client.data_buffer),
                "storage_lock_timed_out": any(storage_timed_out),
            }
            if kind == "residual_ticker":
                # Exercise the actual shutdown path with failed durable append.
                with patch.object(module.os, "fsync", side_effect=OSError("probe disk full")):
                    try:
                        client.close()
                    except RuntimeError as exc:
                        result["failed_flush_reports_unsaved"] = "unsaved entries" in str(exc)
                result["failed_flush_buffered"] = len(client.data_buffer)
                result["failed_flush_pending_batch"] = client._pending is not None
                client.close()
                rows = client.current_file.read_text().splitlines()
                result["retry_saved_prices"] = [json.loads(row)["price"] for row in rows]
            return result
        finally:
            storage_release.set()
            if storage_worker is not None:
                storage_worker.join(timeout=3)
                if storage_worker.is_alive():
                    raise AssertionError("storage worker did not finish")
            client.close()
            for handler in handlers:
                handler.close()


async def main():
    results = [await scenario(kind) for kind in
               ("residual_ticker", "unchanged_price", "flush_only")]
    print(json.dumps(results, indent=2))
    residual, unchanged, flushed = results
    # Controls must hold before interpreting the detected defect.
    assert unchanged["reconnect_close_at_s"] is None
    assert flushed["reconnect_close_at_s"] is not None
    assert residual["failed_flush_reports_unsaved"]
    assert residual["failed_flush_buffered"] == 1
    assert residual["failed_flush_pending_batch"]
    assert residual["retry_saved_prices"] == [42]
    return int(residual["reconnect_close_at_s"] is None)


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
