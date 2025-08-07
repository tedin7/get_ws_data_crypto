#!/usr/bin/env python3
"""
Master test script that runs the public-mode compatible tests in sequence.
This suite validates imports and core functionality without API keys or email.
"""

import os
import sys
import subprocess
import time
from datetime import datetime

def print_header(title):
    """Print a formatted header for test sections"""
    print("\n" + "=" * 80)
    print(f" {title} ".center(80, "="))
    print("=" * 80 + "\n")

def run_test(script_name: str) -> tuple[int, str]:
    """
    Run a test script using the current Python executable and return (returncode, combined_output).
    """
    ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    script_path = os.path.join(ROOT, "tests", script_name)
    cmd = [sys.executable, "-u", script_path]
    try:
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, check=False)
        return result.returncode, result.stdout
    except FileNotFoundError as e:
        return 127, f"File not found: {script_path}\n{e}"

def main():
    """Run public-mode tests in sequence"""
    print_header("PUBLIC WEBSOCKET MODE - TEST SUITE")
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("This test suite verifies imports and core functionality without API keys.")
    
    tests_to_run = [
        "test_import.py",
        "test_main.py",
        "test_functionality.py",
]

    all_output = []
    for test in tests_to_run:
        code, out = run_test(test)
        all_output.append((test, code, out))
        status = "OK" if code == 0 else "FAIL"
        print(f"[{status}] {test}")

    print_header("TEST SUMMARY")
    print(f"Completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("\nTest Results:")
    for idx, (test, code, out) in enumerate(all_output, start=1):
        print(f"Test: {test}, Result: {'OK' if code == 0 else 'FAILED'}")

    all_passed = all(code == 0 for _, code, _ in all_output)
    print(f"\nOverall Test Result: {'PASSED' if all_passed else 'FAILED'}")
    if not all_passed:
        print("\nSome tests failed. Please check the output above for details.")
        print("Fix the issues and run the tests again.")
    else:
        print("\nAll tests passed in public mode.")

if __name__ == "__main__":
    main()  
