#!/usr/bin/env python3
"""
Master test script that runs all the API key checker tests in sequence.
This script provides a comprehensive test of all components of the system.
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

def run_test(script_name, description, is_in_parent_dir=False):
    """Run a test script and return the result"""
    print_header(description)
    
    # Get the absolute path to the script
    if is_in_parent_dir:
        script_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), script_name)
    else:
        script_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), script_name)
    
    # Run the script
    print(f"Running {script_name}...\n")
    result = subprocess.run([sys.executable, script_path], capture_output=False)
    
    # Check the result
    if result.returncode == 0:
        print(f"\n✅ {description} completed successfully")
        return True
    else:
        print(f"\n❌ {description} failed with exit code {result.returncode}")
        return False

def main():
    """Run all tests in sequence"""
    print_header("BYBIT API KEY CHECKER - COMPREHENSIVE TEST SUITE")
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("This test suite will verify all components of the API key checker system.")
    
    # Create results dictionary
    results = {}
    
    # Test 1: API Key Validity
    results["api_key"] = run_test("test_api_key.py", "API Key Validity Test")
    
    # Test 2: Email Functionality
    results["email"] = run_test("test_email.py", "Email Functionality Test")
    
    # Test 3: Full Workflow
    results["workflow"] = run_test("test_workflow.py", "Full Workflow Test")
    
    # Test 4: Manual API Key Check (in parent directory)
    results["manual_check"] = run_test("check_api_key.py", "Manual API Key Check", is_in_parent_dir=True)
    
    # Print summary
    print_header("TEST SUMMARY")
    print(f"Completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("\nTest Results:")
    print(f"1. API Key Validity Test: {'PASSED' if results['api_key'] else 'FAILED'}")
    print(f"2. Email Functionality Test: {'PASSED' if results['email'] else 'FAILED'}")
    print(f"3. Full Workflow Test: {'PASSED' if results['workflow'] else 'FAILED'}")
    print(f"4. Manual API Key Check: {'PASSED' if results['manual_check'] else 'FAILED'}")
    
    # Overall result
    all_passed = all(results.values())
    print(f"\nOverall Test Result: {'PASSED' if all_passed else 'FAILED'}")
    
    if not all_passed:
        print("\nSome tests failed. Please check the output above for details.")
        print("Fix the issues and run the tests again.")
    else:
        print("\nAll tests passed! The API key checker system is working correctly.")

if __name__ == "__main__":
    main() 