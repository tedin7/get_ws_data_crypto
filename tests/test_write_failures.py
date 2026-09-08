"""Offline retry pacing checks using synthetic ticks and storage failures."""

import importlib.util
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch


class CollectorWriteFailureTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        directory = Path(temporary.name)
        (directory / "logs").mkdir()
        config = SimpleNamespace(
            WS_DIR=temporary.name, WS_DIR_PATH=temporary.name,
            BUFFER_SIZE=1, FLUSH_INTERVAL=60,
        )
        spec = importlib.util.spec_from_file_location(
            "collector_retry", Path(__file__).resolve().parents[1] / "main.py"
        )
        self.module = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, {
            "config": config,
            "pybit.unified_trading": SimpleNamespace(WebSocket=None),
            "healthcheck": SimpleNamespace(healthcheck=lambda: True),
        }), patch("logging.basicConfig") as setup:
            spec.loader.exec_module(self.module)
        for handler in setup.call_args.kwargs["handlers"]:
            self.addCleanup(handler.close)
        self.client = self.module.BybitWebSocketClient()

    def tick(self, price):
        self.client.handle_ticker({"data": {"lastPrice": str(price)}})

    def test_invalid_message_cannot_poison_later_valid_ticks(self):
        with self.assertLogs(level="ERROR"):
            for price in (float("nan"), float("inf"), float("-inf")):
                self.tick(price)
            self.client.handle_ticker({"data": {"lastPrice": "1"}, "other": float("nan")})
        self.assertEqual(self.client.data_buffer, [])
        self.tick(42)
        self.client.close()
        rows = [json.loads(line) for line in self.client.current_file.read_text().splitlines()]
        self.assertEqual([row["price"] for row in rows], [42])

    def test_failed_writes_wait_for_deadline_and_then_recover(self):
        with patch.object(self.module.time, "monotonic", return_value=100) as now, patch.object(
            self.client, "get_current_file", side_effect=OSError("synthetic disk error")
        ) as open_file, self.assertLogs(level="ERROR"):
            self.tick(1)
            self.assertEqual(open_file.call_count, 1)
            for price in range(2, 12):
                self.tick(price)
            now.return_value = 159.999
            self.tick(12)
            self.assertEqual(open_file.call_count, 1)
            self.assertEqual(len(self.client.data_buffer), 12)
            now.return_value = 160
            self.tick(13)
            self.assertEqual(open_file.call_count, 2)
            now.return_value = 161
            self.tick(14)
            self.assertEqual(open_file.call_count, 2)

        with patch.object(self.module.time, "monotonic", return_value=220):
            self.tick(15)
            self.assertEqual(self.client.data_buffer, [])
            self.tick(16)
        self.assertEqual(self.client.data_buffer, [])
        rows = [json.loads(line) for line in self.client.current_file.read_text().splitlines()]
        self.assertEqual([row["price"] for row in rows], list(range(1, 17)))

    def test_close_retries_before_deadline_and_reports_unsaved_buffer(self):
        with patch.object(self.module.time, "monotonic", return_value=100), patch.object(
            self.module.os, "fsync", side_effect=OSError("synthetic disk error")
        ) as sync_file, self.assertLogs(level="ERROR"):
            self.tick(42)
            self.tick(43)
            self.assertEqual(sync_file.call_count, 1)
            with self.assertRaisesRegex(RuntimeError, "2 unsaved entries"):
                self.client.close()
            self.assertEqual(sync_file.call_count, 2)
            self.assertEqual([row["price"] for row in self.client.data_buffer], [42, 43])


if __name__ == "__main__":
    unittest.main()
