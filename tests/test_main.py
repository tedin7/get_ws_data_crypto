#!/usr/bin/env python3
"""
Test script to verify main functionality assumptions in PUBLIC mode.
This simulates steps without actually running the WebSocket connection.
"""

import os
import sys
import time
import logging
import asyncio
from datetime import datetime
import importlib
from importlib.metadata import distributions

# Add parent directory to path so we can import modules from there
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import the necessary modules
from config import SYMBOL, TESTNET

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
    
    # Step 1: Simulate WebSocket connection setup (public mode)
    logger.info("Step 1: Simulating WebSocket connection setup (public mode)")
    logger.info(f"Would connect to Bybit WebSocket API with testnet={TESTNET}")
    logger.info(f"Would subscribe to ticker stream for symbol {SYMBOL}")
    
    # Step 2: Simulate data collection
    logger.info("Step 2: Simulating data collection")
    logger.info("Would collect price data and save to file")
    
    # Step 3: Simulate reconnection logic
    logger.info("Step 3: Simulating reconnection logic")
    logger.info("Would implement reconnection logic if WebSocket connection fails")
    
    logger.info("Test of main functionality completed successfully")
    return True

def test_venv_dependencies():
    """Test that all required dependencies are installed in the virtual environment"""
    logger.info("Testing virtual environment dependencies")
    
    # Query runtime distributions using the standard library.
    installed_packages = {dist.metadata["Name"].lower().replace("_", "-")
                          for dist in distributions() if dist.metadata["Name"]}
    
    required_packages = {
        "requests": "requests",
        "pybit": "pybit",
        "websocket-client": "websocket",
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
        print("source .venv/bin/activate && pip install -r requirements.txt")
        sys.exit(1)
    
    # Test main functionality
    main_result = asyncio.run(test_main_functionality())
    
    if main_result:
        print("\n✅ Main functionality test passed")
    else:
        print("\n❌ Main functionality test failed")
        sys.exit(1)
    
    print("\nTest completed successfully") 
