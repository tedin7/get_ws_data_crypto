# API Key Expiration Checker

This tool checks the expiration status of your Bybit API key and sends notifications when the key is about to expire.

## Features

- Automatically checks API key expiration status daily
- Sends email notifications to tommasoderosa94@gmail.com when the key is about to expire
- Logs alerts to a file for reference
- Can be run manually to check the current status

## Setup Email Notifications

To enable email notifications, you need to configure the email settings in `email_config.py`:

1. Make sure you have a Gmail account to send notifications from
2. Generate an App Password for your Gmail account:
   - Go to your Google Account settings
   - Select Security
   - Under "Signing in to Google," select 2-Step Verification
   - At the bottom of the page, select App passwords
   - Generate a new app password for "Mail" and "Other (Custom name)"
   - Copy the generated password
3. Edit the `email_config.py` file:
   - Set `EMAIL_ENABLED = True`
   - Set `SENDER_EMAIL` to your Gmail address
   - Set `EMAIL_PASSWORD` to the App Password you generated

## Running the Checker Manually

You can run the API key checker manually to test it:

```bash
cd get_ws_data_crypto
./check_api_key.py
```

This will:
1. Check your API key expiration status
2. Display the results in the console
3. Send an email notification if the key is about to expire (if email is configured)

## Automatic Checking

The API key checker runs automatically once per day as part of the main WebSocket client. You don't need to do anything to enable this.

## Troubleshooting

If you're not receiving email notifications:

1. Make sure `EMAIL_ENABLED` is set to `True` in `email_config.py`
2. Check that you've entered the correct Gmail address and App Password
3. Check the logs in `ws_data/logs/api_key_alerts.log` for any error messages
4. Run the checker manually with `./check_api_key.py` to see if there are any errors

## Log Files

- API key alerts are logged to: `ws_data/logs/api_key_alerts.log`
- General application logs are in: `ws_data/logs/ws_log.log` 