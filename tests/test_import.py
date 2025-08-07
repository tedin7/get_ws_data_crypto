#!/usr/bin/env python3
"""
Simple script to test if the main script can be imported and run without errors.
This is a minimal test to verify that the virtual environment has all the necessary dependencies.
"""

import os
import sys
import importlib.util
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

def test_import(module_name):
    """Test if a module can be imported"""
    try:
        importlib.import_module(module_name)
        logger.info(f"✅ Successfully imported {module_name}")
        return True
    except ImportError as e:
        logger.error(f"❌ Failed to import {module_name}: {str(e)}")
        return False

def test_file_import(file_path, module_name):
    """Test if a file can be imported as a module"""
    try:
        # Get the absolute path to the file
        abs_path = os.path.abspath(file_path)
        
        # Check if the file exists
        if not os.path.exists(abs_path):
            logger.error(f"❌ File not found: {abs_path}")
            return False
        
        # Import the file as a module
        spec = importlib.util.spec_from_file_location(module_name, abs_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        
        logger.info(f"✅ Successfully imported {file_path} as {module_name}")
        return True
    except Exception as e:
        logger.error(f"❌ Failed to import {file_path}: {str(e)}")
        return False

if __name__ == "__main__":
    print("\n=== Testing Imports ===\n")
    
    # Ensure project root is on sys.path to import config and main
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
    
    # Test importing required modules
    required_modules = [
        "requests",
        "pybit",
        "websocket",  # websocket-client module is imported as 'websocket'
        "prometheus_client",
        "psutil",
        "json",
        "datetime",
    ]
    
    all_modules_imported = True
    for module in required_modules:
        if not test_import(module):
            all_modules_imported = False
    
    # Test importing our own modules
    our_modules = [
        ("config.py", "config"),
        ("main.py", "main")
    ]
    
    all_files_imported = True
    for file_path, module_name in our_modules:
        if not test_file_import(file_path, module_name):
            all_files_imported = False
    
    # Print summary
    print("\n=== Import Test Summary ===")
    print(f"Required modules: {'PASSED' if all_modules_imported else 'FAILED'}")
    print(f"Our modules: {'PASSED' if all_files_imported else 'FAILED'}")
    
    if all_modules_imported and all_files_imported:
        print("\n✅ All imports successful! The virtual environment has all the necessary dependencies.")
        sys.exit(0)
    else:
        print("\n❌ Some imports failed. Please check the logs for details.")
        sys.exit(1)