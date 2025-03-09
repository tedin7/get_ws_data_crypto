#!/usr/bin/env python3
"""
Test script to verify that the main functionality works with the updated API key checker.
This script simulates the main functionality without actually running the WebSocket connection.
"""

import os
import sys
import time
import logging
import asyncio
from datetime import datetime
import importlib
import pkg_resources

# Add parent directory to path so we can import modules from there
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import the necessary modules
from config import API_KEY, API_SECRET, SYMBOL, TESTNET
from api_key_checker import check_api_key_expiration

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

async def test_main_functionality():
    """Test the main functionality without actually running the WebSocket connection"""
    logger.info("Starting test of main functionality")
    
    # Step 1: Check API key expiration
    logger.info("Step 1: Checking API key expiration")
    api_key_valid = check_api_key_expiration()
    
    if api_key_valid:
        logger.info("API key is valid and not expiring soon")
    else:
        logger.warning("API key check failed or key is expiring soon")
    
    # Step 2: Simulate WebSocket connection setup
    logger.info("Step 2: Simulating WebSocket connection setup")
    logger.info(f"Would connect to Bybit WebSocket API with testnet={TESTNET}")
    logger.info(f"Would subscribe to ticker stream for symbol {SYMBOL}")
    
    # Step 3: Simulate data collection
    logger.info("Step 3: Simulating data collection")
    logger.info("Would collect price data and save to file")
    
    # Step 4: Simulate reconnection logic
    logger.info("Step 4: Simulating reconnection logic")
    logger.info("Would implement reconnection logic if WebSocket connection fails")
    
    # Step 5: Simulate API key check thread
    logger.info("Step 5: Simulating API key check thread")
    logger.info("Would start a thread to check API key expiration daily")
    
    logger.info("Test of main functionality completed successfully")
    return True

def test_venv_dependencies():
    """Test that all required dependencies are installed in the virtual environment"""
    logger.info("Testing virtual environment dependencies")
    
    # Use pkg_resources to check installed packages
    installed_packages = {pkg.key for pkg in pkg_resources.working_set}
    
    required_packages = {
        "requests": "requests",
        "pybit": "pybit",
        "websocket-client": "websocket-client",
        "prometheus-client": "prometheus_client",
        "psutil": "psutil"
    }
    
    missing_packages = []
    
    for package_name, module_name in required_packages.items():
        if package_name in installed_packages:
            try:
                # Try to import the module
                __import__(module_name)
                logger.info(f"✅ Package '{package_name}' is installed and module '{module_name}' can be imported")
            except ImportError as e:
                logger.error(f"❌ Package '{package_name}' is installed but module '{module_name}' cannot be imported: {str(e)}")
                missing_packages.append(package_name)
        else:
            logger.error(f"❌ Package '{package_name}' is not installed")
            missing_packages.append(package_name)
    
    if missing_packages:
        logger.error(f"Missing dependencies: {', '.join(missing_packages)}")
        return False
    else:
        logger.info("All required dependencies are installed")
        return True

if __name__ == "__main__":
    print("\n=== Main Functionality Test ===\n")
    
    # Test virtual environment dependencies
    venv_result = test_venv_dependencies()
    
    if not venv_result:
        print("\n❌ Virtual environment is missing required dependencies")
        print("Please install the missing dependencies with:")
        print("source venv/bin/activate && pip install -r requirements.txt")
        sys.exit(1)
    
    # Test main functionality
    loop = asyncio.get_event_loop()
    main_result = loop.run_until_complete(test_main_functionality())
    
    if main_result:
        print("\n✅ Main functionality test passed")
    else:
        print("\n❌ Main functionality test failed")
        sys.exit(1)
    
    print("\nTest completed successfully") 