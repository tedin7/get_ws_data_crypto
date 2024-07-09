import asyncio
import logging
import lzma
import os
from datetime import datetime

import msgpack
from pybit.unified_trading import WebSocket

from config import *


class BybitWebSocketClient:
    def __init__(self):
        self.ws = None
        self.price_data_file = os.path.join(WS_DIR_PATH, 'price_data.xz')

    def handle_ticker(self, message):
        try:
            current_price = float(message['data']['lastPrice'])
            timestamp = datetime.now().isoformat()
            
            price_entry = {
                'timestamp': timestamp,
                'price': current_price,
                'full_data': message
            }
            
            self.save_price_data(price_entry)
            


        except KeyError:
            logging.error(f"Unexpected message format: {message}")
        except Exception as e:
            logging.error(f"Error in handle_ticker: {str(e)}")

    def save_price_data(self, price_entry):
        try:
            with lzma.open(self.price_data_file, 'ab') as f:
                packed_data = msgpack.packb(price_entry)
                f.write(packed_data)
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