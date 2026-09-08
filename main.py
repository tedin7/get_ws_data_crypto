import asyncio
import json
import logging
from logging.handlers import RotatingFileHandler
import os
import signal
import time
from datetime import datetime, timedelta
from pathlib import Path
import threading

from pybit.unified_trading import WebSocket

from config import *
from healthcheck import healthcheck
from storage_protocol import AppendBatch, FileLock, recover_pending

# Setup logging — file + stdout so docker logs works
log_format = '%(asctime)s - %(levelname)s - %(message)s'
log_datefmt = '%Y-%m-%d %H:%M:%S'

logging.basicConfig(
    level=logging.INFO,
    format=log_format,
    datefmt=log_datefmt,
    handlers=[
        RotatingFileHandler(os.path.join(WS_DIR, 'logs', 'ws_log.log'), maxBytes=10 * 1024 * 1024, backupCount=5),
        logging.StreamHandler(),
    ],
)

class BybitWebSocketClient:
    def __init__(self):
        self.ws = None
        self.current_file = None
        self.current_date = None
        self.data_buffer = []
        self.last_flush_time = datetime.now()
        self.next_flush_attempt = 0.0
        self._buffer_lock = threading.RLock()
        self._owner = None
        self._pending = None
        self._pending_count = 0
        self.ensure_data_directory()
        
        # Public mode only
        logging.info("Startup mode: PUBLIC (no API keys)")
        logging.info("Public mode detected. No API key checks or email alerts will be used.")

    def ensure_data_directory(self):
        Path(WS_DIR_PATH).mkdir(parents=True, exist_ok=True)
        log_dir = Path(WS_DIR_PATH) / 'logs'
        log_dir.mkdir(exist_ok=True)

    def get_current_file(self):
        current_date = datetime.now().date()
        if self.current_date != current_date:
            self.current_date = current_date
            file_name = f'price_data_{self.current_date.isoformat()}.jsonl'
            self.current_file = Path(WS_DIR_PATH) / file_name
        return self.current_file

    def handle_ticker(self, message):
        try:
            current_price = float(message['data']['lastPrice'])
            timestamp = datetime.now().isoformat()
            
            price_entry = {
                'timestamp': timestamp,
                'price': current_price,
                'full_data': message
            }
            
            with self._buffer_lock:
                self.data_buffer.append(price_entry)
            
                if time.monotonic() >= self.next_flush_attempt and (
                    len(self.data_buffer) >= BUFFER_SIZE
                    or (datetime.now() - self.last_flush_time).seconds >= FLUSH_INTERVAL
                ):
                    self.save_price_data()
        
        except KeyError:
            logging.error(f"Unexpected message format: {message}")
        except Exception as e:
            logging.error(f"Error in handle_ticker: {str(e)}")

    def _acquire_ownership(self):
        if self._owner is None:
            owner = FileLock(Path(WS_DIR_PATH) / ".collector.lock")
            try:
                recovered = recover_pending(Path(WS_DIR_PATH))
            except BaseException:
                owner.close()
                raise
            self._owner = owner
            if recovered:
                logging.info("Recovered %d durable append batches", recovered)

    def save_price_data(self):
        with self._buffer_lock:
            if not self.data_buffer:
                return
            try:
                self._acquire_ownership()
                # Finish an earlier batch on its ORIGINAL date before rotating.
                # New callbacks are serialized and are never cleared by that commit.
                while self.data_buffer:
                    if self._pending is None:
                        current_file = self.get_current_file()
                        count = len(self.data_buffer)
                        payload = b"".join(
                            (json.dumps(entry, allow_nan=False) + "\n").encode("utf-8")
                            for entry in self.data_buffer[:count]
                        )
                        self._pending = AppendBatch(current_file, payload)
                        self._pending_count = count
                    self._pending.commit()
                    data_count = self._pending_count
                    current_file = self._pending.source
                    completed = self._pending
                    self._pending = None
                    self._pending_count = 0
                    del self.data_buffer[:data_count]
                    completed.close()
                    self.last_flush_time = datetime.now()
                    self.next_flush_attempt = 0.0
                    logging.info("Saved %d entries to %s", data_count, current_file)
            except Exception as e:
                # The batch, buffer and file lock survive even a failed rollback.
                # Memory-only ticks still need a separately authorized backpressure policy.
                self.next_flush_attempt = time.monotonic() + FLUSH_INTERVAL
                logging.error("Error saving price data: %s", e)

    def close(self):
        if self.ws:
            self.ws.exit()
            self.ws.wst.join()
            self.ws = None
        self.save_price_data()
        if self.data_buffer:
            raise RuntimeError(f"Shutdown left {len(self.data_buffer)} unsaved entries")
        if self._owner is not None:
            owner = self._owner
            self._owner = None
            owner.close()

    async def run(self):
        # Public mode: no API key checks
        logging.info("Public mode: starting WebSocket without authentication")

        reconnect_attempts = 0

        while True:
            # Fail closed before connecting when ownership/recovery is unavailable.
            self._acquire_ownership()
            try:
                # Public WebSocket (no credentials)
                logging.info("Initializing public WebSocket (no credentials)")
                self.ws = WebSocket(
                    testnet=TESTNET,
                    channel_type="linear",
                    restart_on_error=False,
                )

                # Subscribe to ticker stream (public topic)
                logging.info(f"Subscribing to public ticker stream for symbol: {SYMBOL}")
                self.ws.ticker_stream(symbol=SYMBOL, callback=self.handle_ticker)

                # Reset reconnect attempts on successful connection
                reconnect_attempts = 0
                last_data_time = datetime.now()

                # Reconnect here so pybit cannot restart a socket during close.
                while True:
                    await asyncio.sleep(5)

                    # Check if pybit still has a live socket
                    if not self.ws.is_connected():
                        logging.warning("WebSocket disconnected (is_connected=False), triggering reconnect")
                        break

                    # Track data freshness — if no data for 60s the stream is stale
                    if self.data_buffer or self.last_flush_time > last_data_time:
                        last_data_time = datetime.now()
                    elif (datetime.now() - last_data_time).total_seconds() > 60:
                        logging.warning("No data received for 60s, triggering reconnect")
                        break

            except Exception as e:
                logging.error(f"WebSocket error: {str(e)}")

            # Clean up old connection before reconnecting
            self.close()

            reconnect_attempts += 1
            if reconnect_attempts <= MAX_RECONNECT_ATTEMPTS:
                wait_time = WS_RECONNECT_DELAY * reconnect_attempts
                logging.info(f"Reconnecting in {wait_time}s (attempt {reconnect_attempts}/{MAX_RECONNECT_ATTEMPTS})")
                await asyncio.sleep(wait_time)
            else:
                logging.error(f"Max reconnect attempts reached. Cooling down for {ERROR_COOLDOWN_TIME}s")
                await asyncio.sleep(ERROR_COOLDOWN_TIME)
                reconnect_attempts = 0

async def main():
    client = BybitWebSocketClient()
    loop = asyncio.get_running_loop()
    loop.add_signal_handler(signal.SIGTERM, asyncio.current_task().cancel)
    try:
        await client.run()
    except asyncio.CancelledError:
        pass
    finally:
        try:
            await asyncio.to_thread(client.close)
        finally:
            loop.remove_signal_handler(signal.SIGTERM)


if __name__ == "__main__":
    asyncio.run(main())
