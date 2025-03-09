import requests
import time
import hmac
import hashlib
import json
import logging
import os
from datetime import datetime
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from config import API_KEY, API_SECRET
# Import email configuration
try:
    from email_config import EMAIL_ENABLED, RECEIVER_EMAIL, SENDER_EMAIL, EMAIL_PASSWORD
except ImportError:
    # Default values if email_config.py doesn't exist
    EMAIL_ENABLED = False
    RECEIVER_EMAIL = "tommasoderosa94@gmail.com"
    SENDER_EMAIL = ""
    EMAIL_PASSWORD = ""
    logging.warning("email_config.py not found. Email notifications are disabled.")

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# Constants
API_URL = "https://api.bybit.com"
ENDPOINT = "/v5/user/query-api"
EXPIRY_WARNING_DAYS = 7  # Alert when API key has less than this many days left

def generate_signature(timestamp, api_secret, recv_window="5000"):
    """Generate signature for Bybit API authentication"""
    param_str = f"{timestamp}{API_KEY}{recv_window}"
    signature = hmac.new(
        bytes(api_secret, "utf-8"),
        bytes(param_str, "utf-8"),
        hashlib.sha256
    ).hexdigest()
    return signature

def check_api_key_expiration():
    """Check the API key expiration status using Bybit API"""
    timestamp = str(int(time.time() * 1000))
    recv_window = "5000"
    signature = generate_signature(timestamp, API_SECRET, recv_window)
    
    headers = {
        "X-BAPI-API-KEY": API_KEY,
        "X-BAPI-TIMESTAMP": timestamp,
        "X-BAPI-RECV-WINDOW": recv_window,
        "X-BAPI-SIGN": signature
    }
    
    try:
        response = requests.get(f"{API_URL}{ENDPOINT}", headers=headers)
        data = response.json()
        
        if data["retCode"] == 0:
            result = data["result"]
            deadline_days = result.get("deadlineDay")
            expired_at = result.get("expiredAt")
            
            logger.info(f"API Key info retrieved successfully")
            logger.info(f"API Key deadline days: {deadline_days}")
            logger.info(f"API Key expires at: {expired_at}")
            
            if deadline_days is not None and deadline_days <= EXPIRY_WARNING_DAYS:
                message = f"WARNING: API Key will expire in {deadline_days} days (on {expired_at}). Please renew it soon."
                logger.warning(message)
                send_alert(message)
                return False
            else:
                logger.info(f"API Key is valid for {deadline_days} more days")
                return True
        else:
            error_message = f"Failed to check API key: {data['retMsg']}"
            logger.error(error_message)
            send_alert(error_message)
            return False
    
    except Exception as e:
        error_message = f"Error checking API key: {str(e)}"
        logger.error(error_message)
        send_alert(error_message)
        return False

def send_alert(message):
    """
    Send an alert about API key expiration via email and log file
    """
    # Log to file as a basic alert method
    log_dir = os.path.join('ws_data', 'logs')
    os.makedirs(log_dir, exist_ok=True)
    
    with open(os.path.join(log_dir, 'api_key_alerts.log'), 'a') as f:
        f.write(f"{datetime.now().isoformat()}: {message}\n")
    
    # Send email notification if enabled
    if EMAIL_ENABLED and SENDER_EMAIL and EMAIL_PASSWORD:
        try:
            # Create message
            msg = MIMEMultipart()
            msg["From"] = SENDER_EMAIL
            msg["To"] = RECEIVER_EMAIL
            msg["Subject"] = "Bybit API Key Expiration Alert"
            
            # Add hostname to the message body for identification
            hostname = os.uname().nodename
            full_message = f"Host: {hostname}\n\n{message}"
            
            msg.attach(MIMEText(full_message, "plain"))
            
            # Send email
            server = smtplib.SMTP("smtp.gmail.com", 587)
            server.starttls()
            server.login(SENDER_EMAIL, EMAIL_PASSWORD)
            server.send_message(msg)
            server.quit()
            logger.info(f"Email alert sent successfully to {RECEIVER_EMAIL}")
        except Exception as e:
            logger.error(f"Failed to send email alert: {str(e)}")
    elif EMAIL_ENABLED:
        logger.warning("Email notifications are enabled but sender email or password is missing.")

if __name__ == "__main__":
    logger.info("Checking API key expiration status...")
    check_api_key_expiration() 