#!/usr/bin/env python3
"""
Simple script to manually check the API key expiration status.
Run this script to check if your API key is about to expire.
"""

import logging
import os
from api_key_checker import check_api_key_expiration

# Check if email configuration exists
try:
    from email_config import EMAIL_ENABLED, RECEIVER_EMAIL, SENDER_EMAIL
    email_config_exists = True
except ImportError:
    email_config_exists = False

if __name__ == "__main__":
    # Configure logging to console
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    print("\n=== Bybit API Key Checker ===\n")
    
    # Check email configuration
    if email_config_exists:
        print(f"Email notifications: {'ENABLED' if EMAIL_ENABLED else 'DISABLED'}")
        if EMAIL_ENABLED:
            print(f"Notification recipient: {RECEIVER_EMAIL}")
            print(f"Sender email: {SENDER_EMAIL}")
    else:
        print("Email notifications: NOT CONFIGURED")
        print("To enable email notifications, create email_config.py with your settings.")
    
    print("\nChecking Bybit API key expiration status...")
    result = check_api_key_expiration()
    
    if result:
        print("\n✅ API key is valid and not expiring soon.")
    else:
        print("\n⚠️ API key check failed or key is expiring soon.")
        print("   Check logs for details.")
    
    # Show log file location
    log_dir = os.path.join('ws_data', 'logs')
    log_file = os.path.join(log_dir, 'api_key_alerts.log')
    if os.path.exists(log_file):
        print(f"\nAlert log file: {os.path.abspath(log_file)}")
    
    print("\nDone.") 