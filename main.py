import asyncio
import gzip
import json
import logging
import os
from datetime import datetime

from pybit.unified_trading import WebSocket

from config import *


class BybitWebSocketClient:
    def __init__(self):
        self.ws = None
        self.price_data_file = os.path.join(WS_DIR_PATH, 'price_data.json.gz')

    def handle_ticker(self, message):
        try:
            current_price = float(message['data']['lastPrice'])
            timestamp = datetime.now().isoformat()
            
            price_entry = {
                'timestamp': timestamp,
                'price': current_price,
                'full_data': message  # Store the full message
            }
            
            self.save_price_data(price_entry)


        except KeyError:
            logging.error(f"Unexpected message format: {message}")
        except Exception as e:
            logging.error(f"Error in handle_ticker: {str(e)}")

    def save_price_data(self, price_entry):
        try:
            with gzip.open(self.price_data_file, 'at') as f:
                json_data = json.dumps(price_entry)
                f.write(json_data + '\n')
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