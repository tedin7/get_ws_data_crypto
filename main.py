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
from api_key_checker import check_api_key_expiration

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
        self.last_api_check_time = datetime.now()
        self.ensure_data_directory()
        
        # Start API key check thread
        self.start_api_key_check_thread()

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

    def start_api_key_check_thread(self):
        """Start a thread to check API key expiration daily"""
        def api_key_check_worker():
            while True:
                # Check API key expiration
                logging.info("Running scheduled API key expiration check")
                check_api_key_expiration()
                
                # Sleep for 24 hours (86400 seconds)
                time.sleep(86400)
        
        # Create and start the thread
        api_check_thread = threading.Thread(target=api_key_check_worker, daemon=True)
        api_check_thread.start()
        logging.info("API key check thread started")

    async def run(self):
        # Initial API key check before starting WebSocket
        logging.info("Performing initial API key check before starting WebSocket")
        api_key_valid = check_api_key_expiration()
        
        if not api_key_valid:
            logging.warning("API key validation failed. Continuing anyway but may encounter issues.")
        
        reconnect_attempts = 0
        
        while True:
            try:
                self.ws = WebSocket(
                    testnet=TESTNET,
                    channel_type="linear",
                    api_key=API_KEY,
                    api_secret=API_SECRET,
                )
                
                # Subscribe to ticker stream
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

if __name__ == "__main__":
    client = BybitWebSocketClient()
    asyncio.run(client.run())