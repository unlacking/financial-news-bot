# test_suite/test_bot.py
import os
import sys
import httpx
from dotenv import load_dotenv

# Resolve the absolute path of the project root directory (one level up from this file)
# and append it to sys.path before importing local custom modules.
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Load credentials from the .env file located in the project root directory
env_path = os.path.join(project_root, ".env")
load_dotenv(dotenv_path=env_path)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_GROUP_CHAT_ID = os.getenv("TELEGRAM_GROUP_CHAT_ID")

def test_telegram_connection() -> bool:
    """
    Sends a test message to verify that the Telegram Token and Chat ID work.
    """
    if not TELEGRAM_TOKEN or not TELEGRAM_GROUP_CHAT_ID:
        print("ERROR: Missing TELEGRAM_BOT_TOKEN or TELEGRAM_GROUP_CHAT_ID in .env file.")
        return False

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    
    # Message body formatted in basic Markdown (No emojis)
    test_message = (
        "*SYSTEM CHECK: SUCCESS*\n"
        "The automated trading alert bot is now online and communicating "
        "successfully with Python from the test suite subfolder."
    )
    
    payload = {
        "chat_id": TELEGRAM_GROUP_CHAT_ID,
        "text": test_message,
        "parse_mode": "Markdown"
    }

    print("Attempting to connect to Telegram API...")
    try:
        response = httpx.post(url, json=payload, timeout=10.0)
        
        if response.status_code == 200:
            print("SUCCESS: Telegram message sent successfully!")
            return True
        else:
            print(f"FAILED: Server returned status code {response.status_code}")
            print(f"Response details: {response.text}")
            return False
            
    except httpx.NetworkError as net_err:
        print(f"FAILED: Connection error. Check your internet connection. Detail: {net_err}")
        return False
    except Exception as e:
        print(f"FAILED: An unexpected error occurred: {e}")
        return False

if __name__ == "__main__":
    test_telegram_connection()