import asyncio
import json
import logging
import os
from datetime import datetime
from pathlib import Path

from pybit.unified_trading import WebSocket

from config import *


class BybitWebSocketClient:
    def __init__(self):
        self.ws = None
        self.price_data_file = Path(WS_DIR_PATH) / 'price_data.jsonl'
        self.temp_file = Path(WS_DIR_PATH) / 'price_data_temp.jsonl'
        self.last_flush_time = datetime.now()
        self.data_buffer = []

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
            # Append to the main file
            with open(self.price_data_file, 'a') as f:
                for entry in self.data_buffer:
                    json.dump(entry, f)
                    f.write('\n')
                f.flush()
                os.fsync(f.fileno())

            # Check if rotation is needed
            if self.price_data_file.stat().st_size > MAX_FILE_SIZE:
                self.rotate_files()

            self.data_buffer.clear()
            self.last_flush_time = datetime.now()
            logging.info(f"Saved {len(self.data_buffer)} entries to {self.price_data_file}")

        except Exception as e:
            logging.error(f"Error saving price data: {str(e)}")

    def rotate_files(self):
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        new_file = self.price_data_file.with_name(f"price_data_{timestamp}.jsonl")
        self.price_data_file.rename(new_file)
        logging.info(f"Rotated file to {new_file}")

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