import logging
import os

# Bybit API settings
SYMBOL = "BTCUSDT"
API_KEY = os.environ.get("API_KEY")
API_SECRET = os.environ.get("API_SECRET")
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
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# Data saving configuration
BUFFER_SIZE = 100  # Number of entries to buffer before writing
FLUSH_INTERVAL = 60  # Maximum time (in seconds) between writes
MAX_FILE_SIZE = 100 * 1024 * 1024  # 100 MB, adjust as needed

# WebSocket configuration
WS_PING_INTERVAL = 30  # Ping the server every 30 seconds
WS_PING_TIMEOUT = 10  # Wait 10 seconds for a pong before considering the connection dead
WS_RECONNECT_DELAY = 5  # Wait 5 seconds before attempting to reconnect

# Error handling
MAX_RECONNECT_ATTEMPTS = 5  # Maximum number of reconnection attempts before giving up
ERROR_COOLDOWN_TIME = 300  # Wait 5 minutes (300 seconds) after max reconnect attempts before trying again

# Performance monitoring
PERFORMANCE_LOG_INTERVAL = 3600  # Log performance stats every hour (3600 seconds)
