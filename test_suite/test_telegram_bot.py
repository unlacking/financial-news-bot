# test_suite/test_telegram_bot.py
import os
import time
import sys
import logging
import httpx
from dotenv import load_dotenv

# Xác định đường dẫn tuyệt đối đến tệp .env ở thư mục gốc của dự án
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
env_path = os.path.join(project_root, ".env")

# Nạp biến môi trường từ đường dẫn chính xác
load_dotenv(dotenv_path=env_path)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_GROUP_CHAT_ID = os.getenv("TELEGRAM_GROUP_CHAT_ID")

# ... Giữ nguyên toàn bộ các hàm send_message và send_bulk_messages ở phía dưới

# Resolve the absolute path of the project root directory (one level up from this file)
# and append it to sys.path before importing local custom modules.
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from src.telegram_bot import send_message, send_bulk_messages

def run_telegram_bot_test():
    print("====================================")
    print("STARTING TELEGRAM BOT ISOLATION TEST")
    print("====================================\n")

    # 1. Test Single Message Delivery (Standard Alert Layout)
    print("--- TESTING SINGLE MESSAGE TRANSMISSION ---")
    single_alert_payload = (
        "===================================\n"
        "MARKET ALERT: FPT\n"
        "===================================\n"
        "Detail: Stock FPT is SURGING: +4.52% at price 135,000 VND\n"
        "Timestamp: 2026-07-15 16:00:00\n"
        "==================================="
    )
    
    print("Dispatching standalone market alert matrix...")
    single_success = send_message(single_alert_payload)
    if single_success:
        print("STATUS: SUCCESS - Standalone target alert transmitted.")
    else:
        print("STATUS: FAILED - Standalone delivery routine failed.")
    print("\n")

    # 2. Test Bulk Message Delivery (Sequential Array Chunks)
    print("--- TESTING BULK/CHUNKED TRANSMISSION ---")
    mock_chunks = [
        (
            "DAILY FINANCIAL DIGEST - DATE: 2026-07-15\n"
            "====================================\n"
            "MARKET SNAPSHOT\n"
            "+ FPT: +4.52%\n"
            "- HPG: -3.15%\n"
            "------------------------------------\n"
            "(Continued in next message...)"
        ),
        (
            "DAILY FINANCIAL DIGEST (CONTINUED) - DATE: 2026-07-15\n"
            "====================================\n"
            "FEATURED ANALYSIS & NEWS\n"
            "Title: FPT announces record high quarterly profits (CafeF)\n"
            "Sentiment: Positive | Importance: 4/5\n"
            "Summary: FPT reported exceptional profit margins driven by global IT services expansion.\n"
            "------------------------------------\n"
            "End of Report. Happy investing!"
        )
    ]

    print(f"Dispatching segmented array database payload ({len(mock_chunks)} chunks)...")
    send_bulk_messages(mock_chunks)
    
    print("\n====================================")
    print("TELEGRAM BOT ISOLATION TEST COMPLETE")
    print("====================================")

if __name__ == "__main__":
    run_telegram_bot_test()