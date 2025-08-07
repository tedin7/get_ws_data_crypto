#!/usr/bin/env python3
"""
Master test script that runs the public-mode compatible tests in sequence.
This suite validates imports and core functionality without API keys or email.
"""

import os
import subprocess
import sys
import time
from datetime import datetime

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def print_header(title):
    """Print a formatted header for test sections"""
    print("\n" + "=" * 80)
    print(f" {title} ".center(80, "="))
    print("=" * 80 + "\n")

def run_test(script_name, description, is_python=True, is_in_parent_dir=False):
    """Run a test script and return the result"""
    print_header(description)
    
    # Get the absolute path to the script
    if is_in_parent_dir:
        script_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), script_name)
    else:
        script_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), script_name)
    
    # Run the script
    print(f"Running {script_name}...\n")
    if is_python:
        cmd = [sys.executable, script_path]
    else:
        # Run as executable script (e.g., .sh)
        cmd = [script_path]
    result = subprocess.run(cmd, capture_output=False)
    
    # Check the result
    if result.returncode == 0:
        print(f"\n✅ {description} completed successfully")
        return True
    else:
        print(f"\n❌ {description} failed with exit code {result.returncode}")
        return False

def main():
    """Run public-mode tests in sequence"""
    print_header("PUBLIC WEBSOCKET MODE - TEST SUITE")
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("This test suite verifies imports and core functionality without API keys.")
    
    results = {}
    # Import test (directly run python test_import.py)
    results["import"] = run_test("test_import.py", "Import Test (python)", is_python=True)
    # Functionality test (directly run python test_functionality.py)
    results["functionality"] = run_test("test_functionality.py", "Functionality Test (mock data save)", is_python=True)
    
    print_header("TEST SUMMARY")
    print(f"Completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("\nTest Results:")
    print(f"1. Import Test: {'PASSED' if results['import'] else 'FAILED'}")
    print(f"2. Functionality Test: {'PASSED' if results['functionality'] else 'FAILED'}")
    
    all_passed = all(results.values())
    print(f"\nOverall Test Result: {'PASSED' if all_passed else 'FAILED'}")
    if not all_passed:
        print("\nSome tests failed. Please check the output above for details.")
        print("Fix the issues and run the tests again.")
    else:
        print("\nAll tests passed in public mode.")

if __name__ == "__main__":
    main()  
