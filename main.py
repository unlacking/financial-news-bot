import os
import sys
import time
import logging
from datetime import datetime
import schedule
from dotenv import load_dotenv

# Ensure local custom modules are resolvable
project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)


from src.news_collector import collect_news, save_news_locally
from src.price_collector import get_all_market_tickers, collect_prices, save_data_locally as save_prices
from src.supabase_helper import insert_json_to_table, NEWS_TABLE, STOCKS_TABLE, process_news_batch
from src.alert_engine import analyze_price_alerts, analyze_news_alerts
from src.formatter import format_alert, format_digest
from src.telegram_bot import send_message, send_bulk_messages

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
    logging.info("Pipeline execution started.")

    if datetime.today().weekday() in [5, 6]:
        logging.info("Market is closed on weekends. Pipeline skipped.")
        return

    date_str = datetime.now().strftime("%Y-%m-%d")
    # Initialize empty containers for collected data to feed into the digest and alerting system
    scraped_news = []
    gemini_analyses = []
    collected_prices = []
    # --- Phase 1: Live Financial News Pipeline ---
    try:
        logging.info("Executing Phase 1: Data Collection & AI Analysis")

        scraped_news = collect_news(news_amount=5)
        if scraped_news:
            save_news_locally(scraped_news)
            logging.info(f"Successfully harvested {len(scraped_news)} raw articles.")

            # Identify the target platform for contextual tracing logs
            date_str = datetime.now().strftime("%Y-%m-%d")
            cafef_path = os.path.join("src", "news_data", f"CafeF_{date_str}.json")
            inferred_name = "CafeF" if os.path.exists(cafef_path) else "VnEconomy"

            # ===== THE CORE FIX: Process the live news batch directly here! =====
            logging.info("Running AI Analysis via Gemini and formatting data rows...")
            formatted_news, gemini_analyses = process_news_batch(scraped_news, inferred_name)
            logging.info(f"Generated {len(gemini_analyses)} active Gemini analysis objects.")
            # ====================================================================

            # Sync the processed payloads down to your Supabase tables sequentially
            if formatted_news:
                insert_json_to_table(local_file_path=cafef_path, table_name=NEWS_TABLE)
        else:
            logging.info("No fresh articles harvested during this cycle.")

    except Exception as e:
        logging.error(f"Error executing News Phase: {e}")
        
    # --- Phase 2: Stock Price Pipeline ---
    try:
        watchlist = get_all_market_tickers(max_tickers=20)
        collected_prices = collect_prices(watchlist)
        if collected_prices:
            save_prices(collected_prices)
            logging.info(f"Successfully collected {len(collected_prices)} stock pricing rows.")

        insert_json_to_table(
            local_file_path=os.path.join("stock_data", date_str, "stock_prices.json"),
            table_name=STOCKS_TABLE
        )
    except Exception as e:
        logging.error(f"Error executing Price Phase: {e}")
    
    # --- Phase 3: Evaluation Engine & Alerting ---
    try:
        logging.info("Executing Phase 3: Alert Evaluation")
        
        # Rule 1 Evaluation: Price threshold checks
        if collected_prices:
            price_alerts = analyze_price_alerts(collected_prices)
            logging.info(f"Price alert criteria scanned. Violations detected: {len(price_alerts)}")
            for alert in price_alerts:
                formatted_msg = format_alert(alert_type="PRICE_ALERT", ticker=alert["ticker"], detail=alert["message"])
                send_message(formatted_msg)
                time.sleep(1.0)

        # Rule 2 & 3 Evaluation: News sensitivity analysis
        if scraped_news and gemini_analyses:
            news_alerts = analyze_news_alerts(scraped_news, gemini_analyses)
            logging.info(f"News alert criteria scanned. Violations detected: {len(news_alerts)}")
            for alert in news_alerts:
                # Extract main ticker if present in array list
                target_ticker = alert["tickers"][0] if alert.get("tickers") else "MARKET"
                formatted_msg = format_alert(alert_type="NEWS_ALERT", ticker=target_ticker, detail=alert["message"])
                send_message(formatted_msg)
                time.sleep(1.0)

    except Exception as e:
        logging.error(f"Failed to execute Alert Evaluation Phase: {e}")

    # --- Phase 4: Newsletter Summary Delivery ---
    # Triggered exclusively during end-of-day execution cycle to avoid text flood issues
    if execution_mode == "EOD":
        try:
            logging.info("Executing Phase 4: Newsletter Generation and Broadcast")
            digest_chunks = format_digest(collected_prices, scraped_news, gemini_analyses)
            send_bulk_messages(digest_chunks)
            logging.info("Daily newsletter digest blocks transmitted successfully.")
        except Exception as e:
            logging.error(f"Failed to transmit Daily Newsletter summary: {e}")

    logging.info("Pipeline execution completed.")

# --- AUTOMATION & SCHEDULER LAYER ---

def schedule_intraday_job():
    """Checks if the current system hour falls within the standard trading window before executing."""
    current_hour = datetime.now().hour
    # Active monitoring window: 09:00 - 15:00 (Vietnam Standard Time trading session)
    if 9 <= current_hour <= 15:
        logging.info("Current time is within trading hours. Initializing intraday scan.")
        run_pipeline(execution_mode="INTRADAY")
    else:
        logging.info(f"Hour {current_hour} is outside trading windows. Intraday execution skipped.")

def start_scheduler():
    logging.info("Automated Scheduler Daemon Initialized Successfully.")
    
    # 1. Schedule Intraday Updates: Every 2 hours Monday through Friday
    # The inner method safeguards execution hours automatically
    schedule.every(2).hours.do(schedule_intraday_job)
    
    # 2. Schedule End-of-Day Newsletter Summary: Monday through Friday at 16:00
    schedule.every().monday.at("16:00").do(run_pipeline, execution_mode="EOD")
    schedule.every().tuesday.at("16:00").do(run_pipeline, execution_mode="EOD")
    schedule.every().wednesday.at("16:00").do(run_pipeline, execution_mode="EOD")
    schedule.every().thursday.at("16:00").do(run_pipeline, execution_mode="EOD")
    schedule.every().friday.at("16:00").do(run_pipeline, execution_mode="EOD")
    
    # Persistent loop keeping the scheduler alive indefinitely
    while True:
        schedule.run_pending()
        time.sleep(1)

if __name__ == "__main__":
    import json
    
    # Argument handling parameter parsing
    # Use: 'python main.py' to run the background scheduler process daemon
    # Use: 'python main.py --now' to trigger a manual test cycle immediately
    if len(sys.argv) > 1 and sys.argv[1] == "--now":
        logging.info("Manual system override detected. Running pipeline immediately.")
        run_pipeline(execution_mode="EOD")
    else:
        start_scheduler()