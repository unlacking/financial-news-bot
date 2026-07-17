import os
import sys
import time
import logging
import json
from datetime import datetime
import threading
import schedule 
from dotenv import load_dotenv

# Clean, standard imports relative to the project root
from src.news_collector import collect_news, save_news_locally
from src.price_collector import get_all_market_tickers, collect_prices, save_data_locally as save_prices
from src.supabase_helper import insert_json_to_table, NEWS_TABLE, STOCKS_TABLE, process_news_batch
from src.alert_engine import analyze_price_alerts, analyze_news_alerts
from src.formatter import format_alert, format_digest
from src.telegram_bot import main as start_telegram_bot
from src.email_client import send_email_digest

# Global thread-safe state dictionary for your /status command
SYSTEM_STATE = {
    "last_run_time": "Never executed yet",
    "last_run_status": "Idle",
    "scheduler_active": True
}

project_root = os.path.dirname(os.path.abspath(__file__))
log_dir = os.path.join(project_root, "logs")
os.makedirs(log_dir, exist_ok=True)
log_file_path = os.path.join(log_dir, "pipeline.log")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(log_file_path, encoding="utf-8"),
        logging.StreamHandler(sys.stdout)
    ]
)

load_dotenv() 
logging.info("Environment variables loaded successfully.")

def run_pipeline(execution_mode: str = "INTRADAY"):
    logging.info(f"Pipeline execution started in mode: {execution_mode}")
    
    global SYSTEM_STATE
    SYSTEM_STATE["last_run_time"] = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    SYSTEM_STATE["last_run_status"] = "Processing..."

    if datetime.today().weekday() in [5, 6]:
        logging.info("Market is closed on weekends. Pipeline skipped.")
        SYSTEM_STATE["last_run_status"] = "Skipped (Weekend)"
        return

    date_str = datetime.now().strftime("%Y-%m-%d")
    scraped_news = []
    gemini_analyses = []
    collected_prices = []
    
    # --- Phase 1: Live Financial News Pipeline ---
    try:
        logging.info("Executing Phase 1: Data Collection & AI Analysis")
        scraped_news = collect_news(news_amount=5)
        if scraped_news:
            logging.info(f"Successfully harvested {len(scraped_news)} raw articles from RSS feeds.")

            cafef_path = os.path.join(project_root, "src", "news_data", f"CafeF_{date_str}.json")
            inferred_name = "CafeF" if os.path.exists(cafef_path) else "VnEconomy"

            existing_links = set()
            if os.path.exists(cafef_path):
                try:
                    with open(cafef_path, 'r', encoding='utf-8') as f:
                        old_data = json.load(f)
                        if isinstance(old_data, dict):
                            old_data = [old_data]
                        existing_links = {item.get("url") or item.get("link") for item in old_data if item.get("url") or item.get("link")}
                except Exception as cache_err:
                    logging.warning(f"Could not parse local news cache cleanly: {cache_err}. Defaulting to full processing.")

            fresh_news = [art for art in scraped_news if (art.get("url") or art.get("link")) not in existing_links]
            
            if not fresh_news:
                logging.info("All harvested articles already exist in local cache. Wasting 0 Gemini tokens.")
                SYSTEM_STATE["last_run_status"] = "Success (No fresh news)"
            else:
                logging.info(f"Processing {len(fresh_news)} completely new articles through Gemini API...")
                formatted_news, gemini_analyses = process_news_batch(fresh_news, inferred_name)
                logging.info(f"Generated {len(gemini_analyses)} active Gemini analysis objects.")

                save_news_locally(scraped_news)
                logging.info("Local news cache updated successfully.")

                if formatted_news:
                    insert_json_to_table(local_file_path=cafef_path, table_name=NEWS_TABLE)
        else:
            logging.info("No fresh articles harvested during this cycle.")

    except Exception as e:
        logging.error(f"Error executing News Phase: {e}")
        SYSTEM_STATE["last_run_status"] = f"Error (News Phase): {str(e)[:30]}"
        
    # --- Phase 2: Stock Price Pipeline ---
    try:
        watchlist = get_all_market_tickers(max_tickers=20)
        collected_prices = collect_prices(watchlist)
        if collected_prices:
            save_prices(collected_prices)
            logging.info(f"Successfully collected {len(collected_prices)} stock pricing rows.")

        insert_json_to_table(
            local_file_path=os.path.join(project_root, "src", "stock_data", date_str, "stock_prices.json"),
            table_name=STOCKS_TABLE
        )
    except Exception as e:
        logging.error(f"Error executing Price Phase: {e}")
        SYSTEM_STATE["last_run_status"] = f"Error (Price Phase): {str(e)[:30]}"
    
    # --- Phase 3: Evaluation Engine & Alerting ---
    try:
        logging.info("Executing Phase 3: Alert Evaluation")
        if collected_prices:
            price_alerts = analyze_price_alerts(collected_prices)
            logging.info(f"Price alert criteria scanned. Violations detected: {len(price_alerts)}")
            for alert in price_alerts:
                formatted_msg = format_alert(alert_type="PRICE_ALERT", ticker=alert["ticker"], detail=alert["message"])
                send_message(formatted_msg)
                time.sleep(1.0)

        if scraped_news and gemini_analyses:
            news_alerts = analyze_news_alerts(scraped_news, gemini_analyses)
            logging.info(f"News alert criteria scanned. Violations detected: {len(news_alerts)}")
            for alert in news_alerts:
                target_ticker = alert["tickers"][0] if alert.get("tickers") else "MARKET"
                formatted_msg = format_alert(alert_type="NEWS_ALERT", ticker=target_ticker, detail=alert["message"])
                send_message(formatted_msg)
                time.sleep(1.0)

    except Exception as e:
        logging.error(f"Failed to execute Alert Evaluation Phase: {e}")

    # --- Phase 4: Newsletter Summary Delivery ---
    if execution_mode == "EOD":
        try:
            logging.info("Executing Phase 4: Newsletter Generation and Broadcast")
            digest_chunks = format_digest(collected_prices, scraped_news, gemini_analyses)
            send_bulk_messages(digest_chunks)
            logging.info("Daily newsletter digest blocks transmitted successfully to Telegram.")
            
            logging.info("Compiling and dispatching secure HTML SMTP email matrix...")
            send_email_digest(collected_prices, scraped_news, gemini_analyses)
            
            SYSTEM_STATE["last_run_status"] = "Success (EOD Completed)"
        except Exception as e:
            logging.error(f"Failed to transmit Daily Newsletter summary outputs: {e}")
            SYSTEM_STATE["last_run_status"] = "Error (EOD Broadcast)"
    else:
        if "Error" not in SYSTEM_STATE["last_run_status"] and SYSTEM_STATE["last_run_status"] != "Processing...":
            SYSTEM_STATE["last_run_status"] = "Success (Intraday Completed)"

def schedule_intraday_job():
    current_hour = datetime.now().hour
    if 9 <= current_hour <= 15:
        logging.info("Current time is within trading hours. Initializing intraday scan.")
        run_pipeline(execution_mode="INTRADAY")
    else:
        logging.info(f"Hour {current_hour} is outside trading windows. Intraday execution skipped.")

def start_scheduler():
    logging.info("Automated Scheduler Daemon Initialized Successfully.")
    
    schedule.every(2).hours.do(schedule_intraday_job)
    
    schedule.every().monday.at("16:00").do(run_pipeline, execution_mode="EOD")
    schedule.every().tuesday.at("16:00").do(run_pipeline, execution_mode="EOD")
    schedule.every().wednesday.at("16:00").do(run_pipeline, execution_mode="EOD")
    schedule.every().thursday.at("16:00").do(run_pipeline, execution_mode="EOD")
    schedule.every().friday.at("16:00").do(run_pipeline, execution_mode="EOD")
    
    while True:
        schedule.run_pending()
        time.sleep(1)

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--now":
        logging.info("Manual system override detected. Running pipeline immediately.")
        run_pipeline(execution_mode="EOD")
    else:
        logging.info("Initializing Unified Fin-News Bot Ecosystem...")

        # Spin up the Telegram Bot on an isolated background thread cleanly
        bot_thread = threading.Thread(target=start_telegram_bot, daemon=True)
        bot_thread.start()
        logging.info("Background thread spinning up internal long-polling listener.")

        # Fire up the main automation schedule loop
        start_scheduler()