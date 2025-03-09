#!/usr/bin/env python3
"""
Test script to verify the full API key checker workflow with a mock API response.
This script simulates an API key that is about to expire to test the notification system.
"""

import logging
import os
import sys
import json
from datetime import datetime, timedelta
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# Add parent directory to path so we can import modules from there
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# Import email configuration
try:
    from email_config import EMAIL_ENABLED, RECEIVER_EMAIL, SENDER_EMAIL, EMAIL_PASSWORD
    email_config_exists = True
except ImportError:
    email_config_exists = False
    EMAIL_ENABLED = False
    RECEIVER_EMAIL = ""
    SENDER_EMAIL = ""
    EMAIL_PASSWORD = ""
    logger.error("email_config.py not found. Email notifications are disabled.")

# Constants
EXPIRY_WARNING_DAYS = 7  # Alert when API key has less than this many days left

def mock_api_response(days_until_expiry=5):
    """Generate a mock API response with a key that will expire in X days"""
    expiry_date = (datetime.now() + timedelta(days=days_until_expiry)).strftime("%Y-%m-%dT%H:%M:%SZ")
    
    return {
        "retCode": 0,
        "retMsg": "",
        "result": {
            "id": "12345678",
            "note": "Test API Key",
            "apiKey": "T8ksX7XSqTdefANefT",
            "readOnly": 0,
            "secret": "",
            "permissions": {
                "ContractTrade": ["Order", "Position"],
                "Spot": ["SpotTrade"],
                "Wallet": ["AccountTransfer"],
                "Options": [],
                "Derivatives": [],
                "CopyTrading": [],
                "BlockTrade": [],
                "Exchange": [],
                "NFT": [],
                "Affiliate": [],
                "Earn": []
            },
            "ips": ["*"],
            "type": 1,
            "deadlineDay": days_until_expiry,
            "expiredAt": expiry_date,
            "createdAt": "2023-01-01T00:00:00Z",
            "unified": 0,
            "uta": 0,
            "userID": 12345,
            "inviterID": 0,
            "vipLevel": "No VIP",
            "mktMakerLevel": "0",
            "affiliateID": 0,
            "rsaPublicKey": "",
            "isMaster": True,
            "parentUid": "0",
            "kycLevel": "LEVEL_DEFAULT",
            "kycRegion": ""
        },
        "retExtInfo": {},
        "time": int(datetime.now().timestamp() * 1000)
    }

def send_alert(message):
    """Send an alert about API key expiration via email and log file"""
    # Get the parent directory path
    parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    # Log to file
    log_dir = os.path.join(parent_dir, 'ws_data', 'logs')
    os.makedirs(log_dir, exist_ok=True)
    
    with open(os.path.join(log_dir, 'api_key_alerts.log'), 'a') as f:
        f.write(f"{datetime.now().isoformat()}: {message}\n")
    
    print(f"Alert logged to file: {message}")
    
    # Send email notification if enabled
    if email_config_exists and EMAIL_ENABLED and SENDER_EMAIL and EMAIL_PASSWORD:
        try:
            # Create message
            msg = MIMEMultipart()
            msg["From"] = SENDER_EMAIL
            msg["To"] = RECEIVER_EMAIL
            msg["Subject"] = "Bybit API Key Expiration Alert (TEST)"
            
            # Add hostname to the message body for identification
            hostname = os.uname().nodename
            full_message = f"Host: {hostname}\n\n{message}\n\nThis is a test message from the workflow test script."
            
            msg.attach(MIMEText(full_message, "plain"))
            
            # Send email
            server = smtplib.SMTP("smtp.gmail.com", 587)
            server.starttls()
            server.login(SENDER_EMAIL, EMAIL_PASSWORD)
            server.send_message(msg)
            server.quit()
            print(f"Email alert sent successfully to {RECEIVER_EMAIL}")
            return True
        except Exception as e:
            print(f"Failed to send email alert: {str(e)}")
            return False
    else:
        print("Email notifications are not configured or disabled")
        return False

def test_workflow(days_until_expiry=5):
    """Test the full workflow with a mock API response"""
    print(f"\nSimulating an API key that will expire in {days_until_expiry} days...")
    
    # Generate mock API response
    response = mock_api_response(days_until_expiry)
    
    # Process the response
    if response["retCode"] == 0:
        result = response["result"]
        deadline_days = result.get("deadlineDay")
        expired_at = result.get("expiredAt")
        
        print(f"API Key info retrieved (mock):")
        print(f"- API Key deadline days: {deadline_days}")
        print(f"- API Key expires at: {expired_at}")
        
        if deadline_days is not None and deadline_days <= EXPIRY_WARNING_DAYS:
            message = f"WARNING: API Key will expire in {deadline_days} days (on {expired_at}). Please renew it soon."
            print(f"\nKey expiration detected: {message}")
            
            # Send alert
            print("\nSending alert notification...")
            alert_result = send_alert(message)
            
            if alert_result:
                print("✅ Alert notification sent successfully")
            else:
                print("❌ Failed to send alert notification")
                
            return alert_result
        else:
            print("\nAPI Key is not expiring soon, no alert needed")
            return True
    else:
        print(f"\n❌ API request failed: {response.get('retMsg', 'Unknown error')}")
        return False

if __name__ == "__main__":
    print("\n=== API Key Checker Workflow Test ===\n")
    
    # Print current email configuration
    if email_config_exists:
        print("Email configuration found:")
        print(f"- Notifications enabled: {EMAIL_ENABLED}")
        print(f"- Receiver email: {RECEIVER_EMAIL}")
        print(f"- Sender email: {SENDER_EMAIL}")
        print(f"- Password configured: {'Yes' if EMAIL_PASSWORD else 'No'}")
    else:
        print("Email configuration not found")
    
    # Test with different expiration scenarios
    print("\n1. Testing with a key that will expire soon (5 days)...")
    result1 = test_workflow(days_until_expiry=5)
    
    print("\n2. Testing with a key that will not expire soon (30 days)...")
    result2 = test_workflow(days_until_expiry=30)
    
    # Print overall results
    print("\n=== Test Results ===")
    print(f"Expiring key test: {'PASSED' if result1 else 'FAILED'}")
    print(f"Non-expiring key test: {'PASSED' if result2 else 'FAILED'}")
    print(f"Overall workflow test: {'PASSED' if result1 and result2 else 'FAILED'}") 