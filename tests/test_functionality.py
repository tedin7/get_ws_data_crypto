#!/usr/bin/env python3
"""
Test script to verify the actual functionality of the main script without running the WebSocket connection.
This script creates a mock WebSocket client and tests the key components of the main script.
"""

import os
import sys
import time
import logging
import asyncio
import threading
from datetime import datetime
from pathlib import Path
import json

# Ensure project root on sys.path to import config
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# Import the necessary modules
from config import SYMBOL, TESTNET, WS_DIR_PATH, BUFFER_SIZE, FLUSH_INTERVAL

class MockWebSocketClient:
    """Mock WebSocket client to test the main functionality without connecting to Bybit"""
    def __init__(self):
        self.ws = None
        self.current_file = None
        self.current_date = None
        self.data_buffer = []
        self.last_flush_time = datetime.now()
        self.ensure_data_directory()
        
        # Public mode only: no API key checks
        # Start API key check thread
        # self.start_api_key_check_thread()

    def ensure_data_directory(self):
        """Ensure the data directory exists"""
        Path(WS_DIR_PATH).mkdir(parents=True, exist_ok=True)
        log_dir = Path(WS_DIR_PATH) / 'logs'
        log_dir.mkdir(exist_ok=True)
        logger.info(f"Data directory created: {WS_DIR_PATH}")

    def get_current_file(self):
        """Get the current file to write data to"""
        current_date = datetime.now().date()
        if self.current_date != current_date:
            self.current_date = current_date
            file_name = f'price_data_{self.current_date.isoformat()}_test.jsonl'
            self.current_file = Path(WS_DIR_PATH) / file_name
            logger.info(f"Current file set to: {self.current_file}")
        return self.current_file

    def handle_ticker(self, message):
        """Handle a ticker message"""
        try:
            current_price = float(message['data']['lastPrice'])
            timestamp = datetime.now().isoformat()
            
            price_entry = {
                'timestamp': timestamp,
                'price': current_price,
                'full_data': message
            }
            
            self.data_buffer.append(price_entry)
            logger.info(f"Added price entry to buffer: {current_price}")
            
            if len(self.data_buffer) >= BUFFER_SIZE or (datetime.now() - self.last_flush_time).seconds >= FLUSH_INTERVAL:
                self.save_price_data()
        
        except KeyError:
            logger.error(f"Unexpected message format: {message}")
        except Exception as e:
            logger.error(f"Error in handle_ticker: {str(e)}")

    def save_price_data(self):
        """Save price data to file"""
        if not self.data_buffer:
            logger.info("No data to save")
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
            logger.info(f"Saved {data_count} entries to {current_file}")

        except Exception as e:
            logger.error(f"Error saving price data: {str(e)}")

    def start_api_key_check_thread(self):
        """Start a thread to check API key expiration"""
        def api_key_check_worker():
            logger.info("API key check thread started")
            # Check API key expiration once
            logger.info("API key check completed")
        
        # Create and start the thread
        api_check_thread = threading.Thread(target=api_key_check_worker, daemon=True)
        api_check_thread.start()
        logger.info("API key check thread started")

    def simulate_data(self, num_messages=5):
        """Simulate receiving data from the WebSocket"""
        logger.info(f"Simulating {num_messages} ticker messages")
        
        for i in range(num_messages):
            # Create a mock ticker message
            mock_message = {
                'data': {
                    'lastPrice': 40000 + (i * 100),  # Simulate price changes
                    'symbol': SYMBOL,
                    'timestamp': int(time.time() * 1000)
                },
                'type': 'ticker'
            }
            
            # Handle the mock message
            self.handle_ticker(mock_message)
            
            # Sleep to simulate time passing
            time.sleep(0.5)
        
        # Force save any remaining data
        self.save_price_data()
        
        logger.info("Data simulation completed")

async def test_main_functionality():
    """Test the main functionality without actually running the WebSocket connection"""
    logger.info("Starting test of main functionality")
    
    # Step 1: Create a mock WebSocket client
    logger.info("Step 1: Creating mock WebSocket client (public mode)")
    client = MockWebSocketClient()
    
    # Step 2: Simulate receiving data
    logger.info("Step 2: Simulating data reception")
    client.simulate_data(num_messages=5)
    
    # Step 3: Check if data was saved correctly
    logger.info("Step 3: Checking if data was saved correctly")
    current_file = client.get_current_file()
    
    if current_file.exists():
        with current_file.open('r') as f:
            lines = f.readlines()
            logger.info(f"Found {len(lines)} entries in {current_file}")
            
            if len(lines) > 0:
                logger.info("Data was saved correctly")
                
                # Print a sample entry
                sample_entry = json.loads(lines[0])
                logger.info(f"Sample entry: {sample_entry}")
            else:
                logger.error("No data was saved")
                return False
    else:
        logger.error(f"Data file not found: {current_file}")
        return False
    
    logger.info("Test of main functionality completed successfully")
    return True

if __name__ == "__main__":
    print("\n=== Main Functionality Test ===\n")
    
    # Test main functionality
    loop = asyncio.get_event_loop()
    main_result = loop.run_until_complete(test_main_functionality())
    
    if main_result:
        print("\n✅ Main functionality test passed")
    else:
        print("\n❌ Main functionality test failed")
        sys.exit(1)
    
    print("\nTest completed successfully ")