#!/usr/bin/env python3
"""
Test script to verify if the Bybit API key is valid.
This script attempts to make a simple API call that doesn't require any special permissions.
"""

import requests
import time
import hmac
import hashlib
import json
import logging
import os
import sys

# Add parent directory to path so we can import modules from there
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import API_KEY, API_SECRET

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# Constants
API_URL = "https://api.bybit.com"
ENDPOINT = "/v5/market/time"  # Simple endpoint that doesn't require authentication

def generate_signature(timestamp, api_secret, recv_window="5000"):
    """Generate signature for Bybit API authentication"""
    param_str = f"{timestamp}{API_KEY}{recv_window}"
    signature = hmac.new(
        bytes(api_secret, "utf-8"),
        bytes(param_str, "utf-8"),
        hashlib.sha256
    ).hexdigest()
    return signature

def test_api_key_validity():
    """Test if the API key is valid by making a simple authenticated request"""
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
        # First, test a public endpoint without authentication
        public_response = requests.get(f"{API_URL}{ENDPOINT}")
        public_data = public_response.json()
        
        if public_response.status_code == 200 and public_data["retCode"] == 0:
            print("✅ Bybit API is accessible (public endpoint test passed)")
        else:
            print(f"❌ Cannot access Bybit API: {public_data.get('retMsg', 'Unknown error')}")
            return False
        
        # Now test with authentication - try a simpler endpoint first
        auth_endpoint = "/v5/user/query-api"  # Get API key info
        
        # Print debug info
        print(f"Debug - Signature generation:")
        print(f"Timestamp: {timestamp}")
        print(f"API Key: {API_KEY}")
        print(f"Recv Window: {recv_window}")
        print(f"Param String: {timestamp}{API_KEY}{recv_window}")
        print(f"Generated Signature: {signature}")
        
        auth_response = requests.get(f"{API_URL}{auth_endpoint}", headers=headers)
        
        # Print response for debugging
        print(f"Debug - API Response Status: {auth_response.status_code}")
        print(f"Debug - API Response Headers: {auth_response.headers}")
        
        try:
            auth_data = auth_response.json()
            print(f"Debug - API Response Body: {json.dumps(auth_data, indent=2)}")
            
            if auth_response.status_code == 200 and auth_data["retCode"] == 0:
                print("✅ API key is valid and authenticated successfully")
                return True
            else:
                error_msg = auth_data.get("retMsg", "Unknown error")
                print(f"❌ API key authentication failed: {error_msg}")
                
                # Check for specific error codes
                if auth_data.get("retCode") == 10003:
                    print("   This error indicates an invalid API key or signature")
                elif auth_data.get("retCode") == 10004:
                    print("   This error indicates an invalid signature")
                elif auth_data.get("retCode") == 10005:
                    print("   This error indicates permission denied for this endpoint")
                
                return False
        except json.JSONDecodeError:
            print(f"❌ Failed to parse API response: {auth_response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Error testing API key: {str(e)}")
        return False

def print_api_key_info():
    """Print the API key information for debugging"""
    # Only print partial key for security
    masked_key = API_KEY[:4] + "..." + API_KEY[-4:] if len(API_KEY) > 8 else "Invalid key"
    masked_secret = API_SECRET[:4] + "..." + API_SECRET[-4:] if len(API_SECRET) > 8 else "Invalid secret"
    
    print("\nAPI Key Information:")
    print(f"API Key: {masked_key}")
    print(f"API Secret: {masked_secret}")
    print(f"API Key Length: {len(API_KEY)} characters")
    print(f"API Secret Length: {len(API_SECRET)} characters")

if __name__ == "__main__":
    print("\n=== Bybit API Key Validity Test ===\n")
    result = test_api_key_validity()
    print_api_key_info()
    
    print("\nTest result:", "PASSED" if result else "FAILED") 