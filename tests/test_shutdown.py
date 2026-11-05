"""Offline shutdown checks with a real callback thread and synthetic ticks."""

import asyncio
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from pybit._websocket_stream import _WebSocketManager
from websocket import WebSocketConnectionClosedException


class CollectorShutdownTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)
        (self.directory / "logs").mkdir()
        config = SimpleNamespace(
            WS_DIR=temporary.name, WS_DIR_PATH=temporary.name,
            BUFFER_SIZE=100, FLUSH_INTERVAL=60,
        )
        spec = importlib.util.spec_from_file_location(
            "collector", Path(__file__).resolve().parents[1] / "main.py"
        )
        self.module = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, {
            "config": config,
            "pybit.unified_trading": SimpleNamespace(WebSocket=None),
            "healthcheck": SimpleNamespace(healthcheck=lambda: True),
        }), patch("logging.basicConfig") as logging_config:
            spec.loader.exec_module(self.module)
        for handler in logging_config.call_args.kwargs["handlers"]:
            self.addCleanup(handler.close)
        self.client = self.module.BybitWebSocketClient()

    async def test_cancellation_waits_for_last_callback_before_flush(self):
        closing = threading.Event()
        self.addCleanup(closing.set)

        def callback():
            if closing.wait(timeout=5):
                self.client.handle_ticker({"data": {"lastPrice": "42"}})

        worker = threading.Thread(target=callback, daemon=True)
        worker.start()
        websocket = SimpleNamespace(exit=closing.set, wst=worker)
        self.client.ws = websocket
        running = asyncio.Event()

        async def run():
            running.set()
            await asyncio.Event().wait()

        with patch.object(self.client, "run", run), patch.object(
            self.module, "BybitWebSocketClient", return_value=self.client
        ):
            task = asyncio.create_task(self.module.main())
            await running.wait()
            task.cancel()
            await asyncio.wait_for(task, timeout=3)
        self.assertFalse(worker.is_alive())
        self.assertIsNone(self.client.ws)
        self.assertEqual(self.client.data_buffer, [])
        records = self.client.current_file.read_text().splitlines()
        self.assertEqual(len(records), 1)
        self.assertEqual(json.loads(records[0])["price"], 42)

    async def test_failed_flush_preserves_buffer_and_reports_failure(self):
        self.client.handle_ticker({"data": {"lastPrice": "42"}})
        with patch.object(os, "fsync", side_effect=OSError("disk full")), self.assertLogs(
            level="ERROR"
        ), self.assertRaisesRegex(RuntimeError, "1 unsaved entries"):
            self.client.close()
        self.assertEqual(len(self.client.data_buffer), 1)
        self.assertEqual(self.client.data_buffer[0]["price"], 42)

    async def test_pybit_close_error_cannot_reconnect_after_shutdown_or_cleanup(self):
        for reconnect in (False, True):
            with self.subTest(reconnect=reconnect):
                self.client = self.module.BybitWebSocketClient()
                managers = []

                def websocket(**kwargs):
                    manager = _WebSocketManager(
                        self.client.handle_ticker, "offline", kwargs["testnet"],
                        restart_on_error=kwargs.get("restart_on_error", True),
                    )
                    manager.endpoint = "offline"
                    manager._connect = Mock()
                    closing = threading.Event()
                    finish_callback = threading.Event()

                    def close_transport():
                        manager.ws.sock = None
                        closing.set()

                    def callback():
                        if closing.wait(3) and finish_callback.wait(3):
                            manager.callback({"data": {"lastPrice": "42"}})
                            manager._on_error(WebSocketConnectionClosedException("closing"))

                    manager.ws = SimpleNamespace(sock=object(), close=close_transport)
                    manager.wst = threading.Thread(target=callback, daemon=True)
                    join = manager.wst.join

                    def finish_and_join(*args, **kwargs):
                        finish_callback.set()
                        join(*args, **kwargs)

                    manager.wst.join = finish_and_join
                    self.addCleanup(lambda: (closing.set(), finish_and_join(3)))
                    manager.wst.start()
                    manager.ticker_stream = Mock()
                    manager.is_connected = lambda: False
                    managers.append(manager)
                    return manager

                sleeps = 0

                async def sleep(_delay):
                    nonlocal sleeps
                    sleeps += 1
                    if reconnect and sleeps == 1:
                        return
                    if reconnect:
                        self.assertFalse(managers[0].wst.is_alive())
                        self.assertEqual(self.client.data_buffer, [])
                    raise asyncio.CancelledError

                settings = dict(TESTNET=False, SYMBOL="BTCUSDT", MAX_RECONNECT_ATTEMPTS=2,
                                WS_RECONNECT_DELAY=1, ERROR_COOLDOWN_TIME=1)
                with patch.multiple(self.module, create=True, **settings), patch.object(
                    self.module, "WebSocket", websocket
                ), patch.object(self.module, "BybitWebSocketClient", return_value=self.client), patch.object(
                    self.module.asyncio, "sleep", sleep
                ):
                    await self.module.main()
                managers[0]._connect.assert_not_called()
                self.assertFalse(managers[0].wst.is_alive())
                self.assertEqual(self.client.data_buffer, [])
                self.assertEqual(json.loads(self.client.current_file.read_text().splitlines()[-1])["price"], 42)


if __name__ == "__main__":
    unittest.main()
