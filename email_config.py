# Email configuration for API key expiration alerts
# Update these settings with your email credentials

import os

# Enable/disable email notifications
EMAIL_ENABLED = os.environ.get("EMAIL_ENABLED", "False").lower() == "true"

# Email to receive notifications
RECEIVER_EMAIL = os.environ.get("RECEIVER_EMAIL")

# Sender email (must be a Gmail account)
SENDER_EMAIL = os.environ.get("SENDER_EMAIL")

# App password for Gmail
EMAIL_PASSWORD = os.environ.get("EMAIL_PASSWORD")

# For security, use an App Password instead of your regular password
# To generate an App Password:
# 1. Go to your Google Account settings
# 2. Select Security
# 3. Under "Signing in to Google," select 2-Step Verification
# 4. At the bottom of the page, select App passwords
# 5. Generate a new app password for "Mail" and "Other (Custom name)"
# 6. Copy the generated password and paste it below 