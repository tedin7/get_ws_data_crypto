"""Offline reproducer: injected write/flush/fsync/close failures, no real config."""
import errno
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent


def load_collector(directory):
    (directory / 'logs').mkdir()
    settings = SimpleNamespace(WS_DIR=str(directory), WS_DIR_PATH=str(directory), BUFFER_SIZE=100, FLUSH_INTERVAL=60)
    spec = importlib.util.spec_from_file_location('collector_repro', ROOT / 'main.before.py')
    module = importlib.util.module_from_spec(spec)
    with patch.dict(sys.modules, {'config': settings, 'pybit.unified_trading': SimpleNamespace(WebSocket=None), 'healthcheck': SimpleNamespace(healthcheck=lambda: True)}), patch('logging.basicConfig') as setup:
        spec.loader.exec_module(module)
    return module, setup.call_args.kwargs['handlers']


class FaultingFile:
    def __init__(self, wrapped, stage):
        self.wrapped = wrapped
        self.stage = stage
        self.completed_lines = 0

    def __getattr__(self, key):
        return getattr(self.wrapped, key)

    def __enter__(self):
        self.wrapped.__enter__()
        return self

    def __exit__(self, *args):
        result = self.wrapped.__exit__(*args)
        if self.stage == 'close':
            raise OSError(errno.EIO, 'synthetic close error')
        return result

    def write(self, value):
        if self.stage == 'write' and self.completed_lines:
            self.wrapped.write(value[:1])
            self.wrapped.flush()
            raise OSError(errno.ENOSPC, 'synthetic partial write')
        result = self.wrapped.write(value)
        if value == '\n':
            self.completed_lines += 1
        return result

    def flush(self):
        self.wrapped.flush()
        if self.stage == 'flush':
            raise OSError(errno.ENOSPC, 'synthetic flush error')


for stage in ('write', 'flush', 'fsync', 'close'):
    with tempfile.TemporaryDirectory() as temporary:
        module, handlers = load_collector(Path(temporary))
        try:
            client = module.BybitWebSocketClient()
            client.data_buffer.extend([{'price': 10}, {'price': 20}])
            path = client.get_current_file()
            path.write_text('{"existing":true}\n')
            original_open = Path.open
            def fault_open(open_path, *args, **kwargs):
                opened = original_open(open_path, *args, **kwargs)
                return FaultingFile(opened, stage) if open_path == path else opened
            with patch.object(Path, 'open', fault_open), patch.object(module.os, 'fsync', side_effect=OSError(errno.EIO, 'synthetic fsync error')) if stage == 'fsync' else patch.object(module.os, 'fsync', wraps=module.os.fsync):
                client.save_price_data()
            preserved = len(client.data_buffer)
            partial = path.read_text()
            client.save_price_data()
            raw_lines = path.read_text().splitlines()
            rows, invalid = [], []
            for line in raw_lines:
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    invalid.append(line)
            counts = {str(price): sum(row.get('price') == price for row in rows) for price in (10, 20)}
            assert preserved == 2, (stage, preserved)
            assert invalid or any(count > 1 for count in counts.values()), (stage, raw_lines)
            assert client.data_buffer == [], stage
            print(json.dumps({'stage': stage, 'buffer_after_failure': preserved, 'file_after_failure': partial, 'occurrences_after_retry': counts, 'invalid_lines': invalid, 'buffer_after_retry': len(client.data_buffer)}))
        finally:
            for handler in handlers:
                handler.close()
