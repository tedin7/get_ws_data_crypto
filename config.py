import logging
import os

# Constants
SYMBOL = "BTCUSDT"

# Bybit API credentials (use testnet for safety)
API_KEY = "T8ksX7XSqTdefANefT"
API_SECRET = "c2MVn4vmpXuf8uyudChEh2bHy3c3WF56B4Ez"
TESTNET = False

# Directory setup
WS_DIR = 'ws_data'
WS_DIR_PATH = os.path.abspath(WS_DIR)
os.makedirs(WS_DIR, exist_ok=True)

# Logging configuration
LOG_DIR = os.path.join(WS_DIR, 'logs')
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, 'ws_log.log')

logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# WebSocket configuration
SAVE_INTERVAL = 1  # Save data every 5 minutes (300 seconds)