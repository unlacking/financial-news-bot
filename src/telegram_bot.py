# src/telegram_bot.py
import os
import time
import logging
import httpx
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_GROUP_CHAT_ID = os.getenv("TELEGRAM_GROUP_CHAT_ID")

def send_message(text: str) -> bool:
    """
    Sends a formatted message to a designated Telegram chat or channel.
    Utilizes Markdown parsing mode for structural bold/italic variations.
    """
    if not TELEGRAM_TOKEN or not TELEGRAM_GROUP_CHAT_ID:
        logging.error("Telegram configuration variables missing in environment setup.")
        return False

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_GROUP_CHAT_ID,
        "text": text,
        "parse_mode": "Markdown"
    }

    try:
        response = httpx.post(url, json=payload, timeout=10.0)
        
        if response.status_code == 200:
            return True
        else:
            logging.warning(f"Telegram API Markdown delivery rejected (HTTP {response.status_code}). Attempting raw text fallback.")
            # Fallback retry removing Markdown formatting parsing restrictions if strings break layout syntax rules
            payload.pop("parse_mode", None)
            fallback_response = httpx.post(url, json=payload, timeout=10.0)
            return fallback_response.status_code == 200

    except httpx.NetworkError as net_err:
        logging.error(f"Network transport fault communicating with Telegram endpoints: {net_err}")
        return False
    except Exception as e:
        logging.error(f"Unexpected operational failure during Telegram message transmission: {e}")
        return False


def send_bulk_messages(messages: list) -> None:
    """
    Transmits an ordered list of string message chunks sequentially.
    Enforces a mandatory safe cooldown delay between targets to prevent rate-limit penalties.
    """
    if not messages:
        logging.info("No text payload sequences provided for bulk distribution.")
        return

    logging.info(f"Initiating bulk delivery sequence for {len(messages)} message blocks.")
    for idx, msg in enumerate(messages, 1):
        success = send_message(msg)
        if success:
            logging.info(f"Successfully delivered message block {idx}/{len(messages)}")
        else:
            logging.error(f"Failed to deliver message block {idx}/{len(messages)}")
        
        # Enforce an explicit 1.5-second pause delay between consecutive delivery tasks
        if idx < len(messages):
            time.sleep(1.5)