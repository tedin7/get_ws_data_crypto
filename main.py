import asyncio
import json
import logging
import os
from datetime import datetime, timedelta
from pathlib import Path

from pybit.unified_trading import WebSocket

from config import *


class BybitWebSocketClient:
    def __init__(self):
        self.ws = None
        self.current_file = None
        self.current_date = None
        self.data_buffer = []
        self.ensure_data_directory()

    def ensure_data_directory(self):
        Path(WS_DIR_PATH).mkdir(parents=True, exist_ok=True)

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

            self.data_buffer.clear()
            self.last_flush_time = datetime.now()
            logging.info(f"Saved {len(self.data_buffer)} entries to {current_file}")

        except Exception as e:
            logging.error(f"Error saving price data: {str(e)}")

    async def run(self):
        try:
            self.ws = WebSocket(
                testnet=TESTNET,
                channel_type="linear",
            )
            
            # Subscribe to ticker stream
            self.ws.ticker_stream(symbol=SYMBOL, callback=self.handle_ticker)
            
            while True:
                await asyncio.sleep(1)
        
        except Exception as e:
            logging.error(f"WebSocket error: {str(e)}")
            print(f"WebSocket error: {str(e)}")

if __name__ == "__main__":
    client = BybitWebSocketClient()
    asyncio.run(client.run())