#!/usr/bin/env python3
"""
Test script to verify if email notifications are working correctly.
This script sends a test email using the configured email settings.
"""

import logging
import smtplib
import os
import sys
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime

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

def test_email():
    """Test sending an email with the configured settings"""
    if not email_config_exists:
        print("❌ Email configuration file (email_config.py) not found")
        return False
    
    if not EMAIL_ENABLED:
        print("❌ Email notifications are disabled in email_config.py")
        return False
    
    if not SENDER_EMAIL or not EMAIL_PASSWORD:
        print("❌ Sender email or password is missing in email_config.py")
        return False
    
    if not RECEIVER_EMAIL:
        print("❌ Receiver email is missing in email_config.py")
        return False
    
    try:
        # Create message
        msg = MIMEMultipart()
        msg["From"] = SENDER_EMAIL
        msg["To"] = RECEIVER_EMAIL
        msg["Subject"] = "Bybit API Key Checker - Test Email"
        
        # Add hostname and timestamp to the message body
        hostname = os.uname().nodename
        timestamp = datetime.now().isoformat()
        message = f"""
This is a test email from the Bybit API Key Checker.

Host: {hostname}
Time: {timestamp}

If you received this email, the email notification system is working correctly.
        """
        
        msg.attach(MIMEText(message, "plain"))
        
        # Send email
        print(f"Attempting to send test email to {RECEIVER_EMAIL}...")
        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(SENDER_EMAIL, EMAIL_PASSWORD)
        server.send_message(msg)
        server.quit()
        
        print(f"✅ Test email sent successfully to {RECEIVER_EMAIL}")
        return True
        
    except Exception as e:
        print(f"❌ Failed to send test email: {str(e)}")
        
        # Provide troubleshooting tips based on the error
        if "Authentication" in str(e):
            print("\nTroubleshooting tips for authentication errors:")
            print("1. Make sure you're using an App Password, not your regular Gmail password")
            print("2. Verify that 2-Step Verification is enabled for your Google account")
            print("3. Check that you've copied the App Password correctly")
        elif "SMTP" in str(e):
            print("\nTroubleshooting tips for SMTP errors:")
            print("1. Check your internet connection")
            print("2. Make sure port 587 is not blocked by your firewall")
            print("3. Verify that your Gmail account allows less secure apps")
        
        return False

if __name__ == "__main__":
    print("\n=== Email Notification Test ===\n")
    
    # Print current email configuration
    if email_config_exists:
        print("Email configuration found:")
        print(f"- Notifications enabled: {EMAIL_ENABLED}")
        print(f"- Receiver email: {RECEIVER_EMAIL}")
        print(f"- Sender email: {SENDER_EMAIL}")
        print(f"- Password configured: {'Yes' if EMAIL_PASSWORD else 'No'}")
    else:
        print("Email configuration not found")
    
    print("\nRunning email test...")
    result = test_email()
    
    print("\nTest result:", "PASSED" if result else "FAILED") 