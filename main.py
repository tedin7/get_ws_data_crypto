import asyncio
import json
import logging
import os
import time
from datetime import datetime, timedelta
from pathlib import Path
import threading

from pybit.unified_trading import WebSocket

from config import *

# Setup logging
logging.basicConfig(
    filename=os.path.join(WS_DIR, 'logs', 'ws_log.log'),
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

class BybitWebSocketClient:
    def __init__(self):
        self.ws = None
        self.current_file = None
        self.current_date = None
        self.data_buffer = []
        self.last_flush_time = datetime.now()
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
            
            self.data_buffer.append(price_entry)
            
            if len(self.data_buffer) >= BUFFER_SIZE or (datetime.now() - self.last_flush_time).seconds >= FLUSH_INTERVAL:
                self.save_price_data()
        
        except KeyError:
            logging.error(f"Unexpected message format: {message}")
        except Exception as e:
            logging.error(f"Error in handle_ticker: {str(e)}")

    def save_price_data(self):
        if not self.data_buffer:
            return

        try:
            current_file = self.get_current_file()
            with current_file.open('a') as f:
                for entry in self.data_buffer:
                    json.dump(entry, f)
                    f.write('\n')
                f.flush()
                os.fsync(f.fileno())

            data_count = len(self.data_buffer)
            self.data_buffer.clear()
            self.last_flush_time = datetime.now()
            logging.info(f"Saved {data_count} entries to {current_file}")

        except Exception as e:
            logging.error(f"Error saving price data: {str(e)}")

    async def run(self):
        # Public mode: no API key checks
        logging.info("Public mode: starting WebSocket without authentication")

        reconnect_attempts = 0
        
        while True:
            try:
                # Public WebSocket (no credentials)
                logging.info("Initializing public WebSocket (no credentials)")
                self.ws = WebSocket(
                    testnet=TESTNET,
                    channel_type="linear",
                )
                
                # Subscribe to ticker stream (public topic)
                logging.info(f"Subscribing to public ticker stream for symbol: {SYMBOL}")
                self.ws.ticker_stream(symbol=SYMBOL, callback=self.handle_ticker)
                
                # Reset reconnect attempts on successful connection
                reconnect_attempts = 0
                
                # Keep the connection alive
                while True:
                    await asyncio.sleep(1)
            
            except Exception as e:
                logging.error(f"WebSocket error: {str(e)}")
                print(f"WebSocket error: {str(e)}")
                
                # Implement reconnection logic
                reconnect_attempts += 1
                
                if reconnect_attempts <= MAX_RECONNECT_ATTEMPTS:
                    wait_time = WS_RECONNECT_DELAY
                    logging.info(f"Attempting to reconnect in {wait_time} seconds (attempt {reconnect_attempts}/{MAX_RECONNECT_ATTEMPTS})")
                    await asyncio.sleep(wait_time)
                else:
                    logging.error(f"Maximum reconnection attempts reached. Waiting for {ERROR_COOLDOWN_TIME} seconds before trying again")
                    await asyncio.sleep(ERROR_COOLDOWN_TIME)
                    reconnect_attempts = 0

def healthcheck():
    # Return True if runtime appears healthy; minimal check:
    # - data directory exists
    # - SYMBOL is a non-empty string
    # More elaborate checks would require internal state.
    try:
        import os
        from config import WS_DIR_PATH, SYMBOL
        return bool(SYMBOL) and os.path.isdir(WS_DIR_PATH)
    except Exception:
        return False

if __name__ == "__main__":
    client = BybitWebSocketClient()
    asyncio.run(client.run())
