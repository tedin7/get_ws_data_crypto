import asyncio
import json
import logging
import os
from datetime import datetime

from pybit.unified_trading import WebSocket

from config import *


class BybitWebSocketClient:
    def __init__(self):
        self.ws = None
        self.price_data = []
        self.last_save_time = datetime.now()

    def handle_ticker(self, message):
        try:
            current_price = float(message['data']['lastPrice'])
            timestamp = datetime.now().isoformat()
            
            price_entry = {
                'timestamp': timestamp,
                'price': current_price
            }
            
            self.price_data.append(price_entry)

            # Save data every SAVE_INTERVAL seconds
            current_time = datetime.now()
            if (current_time - self.last_save_time).total_seconds() >= SAVE_INTERVAL:
                self.save_price_data()
                self.last_save_time = current_time

        except KeyError:
            logging.error(f"Unexpected message format: {message}")
        except Exception as e:
            logging.error(f"Error in handle_ticker: {str(e)}")

    def save_price_data(self):
        if self.price_data:
            filepath = os.path.join(WS_DIR_PATH, 'price_data.json')

            try:
                # Read existing data
                if os.path.exists(filepath):
                    with open(filepath, 'r') as f:
                        existing_data = json.load(f)
                else:
                    existing_data = []

                # Append new data
                existing_data.extend(self.price_data)

                # Write updated data
                with open(filepath, 'w') as f:
                    json.dump(existing_data, f, indent=2)
                # Clear the price_data list after saving
                self.price_data = []

            except Exception as e:
                logging.error(f"Error saving price data: {str(e)}")
        else:
            logging.warning("No new price data to save")

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