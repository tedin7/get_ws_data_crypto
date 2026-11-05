"""Freshness checks use synthetic files and no live client or configuration."""

import importlib.util
import os
from pathlib import Path
import sys
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch


class CollectorHealthTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)
        spec = importlib.util.spec_from_file_location(
            "healthcheck", Path(__file__).resolve().parents[1] / "healthcheck.py"
        )
        self.module = importlib.util.module_from_spec(spec)
        config = SimpleNamespace(
            FLUSH_INTERVAL=60, SYMBOL="BTCUSDT", WS_DIR_PATH=temporary.name
        )
        with patch.dict(sys.modules, {"config": config}):
            spec.loader.exec_module(self.module)

    def test_recent_output_is_healthy(self):
        (self.directory / "price_data_2020-01-01.jsonl").touch()
        self.assertTrue(self.module.healthcheck())

    def test_stale_output_is_unhealthy(self):
        output = self.directory / "price_data_2020-01-01.jsonl"
        output.touch()
        os.utime(output, (1, 1))
        self.assertFalse(self.module.healthcheck())

    def test_no_output_is_unhealthy(self):
        (self.directory / "price_data_2020-01-01.jsonl.xz").touch()
        self.assertFalse(self.module.healthcheck())

    def test_threshold_accounts_for_flush_interval(self):
        self.module.FLUSH_INTERVAL = 600
        output = self.directory / "price_data_2020-01-01.jsonl"
        output.touch()
        last_write = time.time() - 1200
        os.utime(output, (last_write, last_write))
        self.assertTrue(self.module.healthcheck())


if __name__ == "__main__":
    unittest.main()
