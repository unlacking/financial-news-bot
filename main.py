"""
MAIN UTILITY ENGINE & ORCHESTRATION PIPELINE
-------------------------------------------
This script acts as the primary orchestrator for the entire financial news bot ecosystem.
It executes two primary concurrent flows:
  1. An asynchronous background worker thread running a long-polling Telegram Bot command listener.
  2. A synchronous clock-based scheduler that handles automated intraday scans and End-of-Day (EOD) digest distributions.

Architecture Flow Overview:
  [News RSS & Ticker Prices] ──> [Gemini AI Filter] ──> [Supabase Cloud Database] ──> [Telegram/Email Alerts]
"""

import os
import sys
import time
import logging
import json
from datetime import datetime
import threading
import schedule 
from dotenv import load_dotenv

# ==============================================================================
# 1. CORE MODULE & ENGINE IMPORTS
# ==============================================================================
# These internal dependencies are split into specialized processing modules:
# - news_collector / price_collector: Raw data harvesting from exterior streams.
# - supabase_helper: The data persistence layer interfacing with the cloud tables.
# - alert_engine / formatter: Evaluates financial logic criteria and constructs typography elements.
# - telegram_bot / email_client: Outbound delivery nodes transmitting data back to humans.

try:
    from src.news_collector import collect_news, save_news_locally
    from src.price_collector import get_all_market_tickers, collect_prices, save_data_locally as save_prices
    from src.supabase_helper import insert_json_to_table, NEWS_TABLE, STOCKS_TABLE, process_news_batch
    from src.alert_engine import analyze_price_alerts, analyze_news_alerts
    from src.formatter import format_alert, format_digest
    from src.telegram_bot import send_message, send_bulk_messages, main as start_telegram_bot
    from src.email_client import send_email_digest
except ImportError as import_err:
    print(f"CRITICAL CONFIGURATION FAULT: Internal 'src/' project module unresolvable: {import_err}")
    sys.exit(1)

# ==============================================================================
# 2. RUNTIME ENVIRONMENT STATE
# ==============================================================================
# Global thread-safe dictionary context that caches system execution data.
# The interactive /status command handler inside 'telegram_bot.py' cross-references
# this state variable directly via memory mapping to print live system dashboards.
SYSTEM_STATE = {
    "last_run_time": "Never executed yet",
    "last_run_status": "Idle",
    "scheduler_active": True
}

# ==============================================================================
# 3. DIRECTORY STRUCTURE & SYSTEM LOGGER INITIALIZATION
# ==============================================================================
# Locates paths and spins up log streams that copy events to both the terminal (stdout)
# and a local disk storage log file ('logs/pipeline.log') simultaneously.
try:
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
except Exception as log_init_err:
    print(f"CRITICAL CORE ERROR: Failed to deploy system logging architecture: {log_init_err}")
    sys.exit(1)

# Attempts to load secret API access credentials and connection endpoints out of your local '.env' file.
try:
    load_dotenv() 
    logging.info("Environment variables loaded successfully.")
except Exception as env_err:
    logging.error(f"Non-fatal configuration error: Failed to map .env variables cleanly: {env_err}")


# ==============================================================================
# 4. PRIMARY PROCESSING ENGINE (THE CORE PIPELINE LOOP)
# ==============================================================================
def run_pipeline(execution_mode: str = "INTRADAY"):
    """
    Executes data collection, filters duplication parameters, invokes Gemini AI evaluations,
    synchronizes rows with Supabase, evaluates alert triggers, and delivers requested broadcasts.
    """
    global SYSTEM_STATE

    logging.info(f"Pipeline execution started in mode: {execution_mode}")
    
    SYSTEM_STATE["last_run_time"] = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    SYSTEM_STATE["last_run_status"] = "Processing..."

    # Financial market safeguard: Instantly short-circuit out of execution if it is Saturday or Sunday.
    if datetime.today().weekday() in [5, 6] and execution_mode != "EOD":
        logging.info("Market is closed on weekends. Pipeline skipped.")
        SYSTEM_STATE["last_run_status"] = "Skipped (Weekend)"
        return

    date_str = datetime.now().strftime("%Y-%m-%d")
    scraped_news = []
    gemini_analyses = []
    collected_prices = []
    
    # --------------------------------------------------------------------------
    # --- Phase 1: Live Financial News & AI Analysis Loop ---
    # --------------------------------------------------------------------------
    try:
        logging.info("Executing Phase 1: Data Collection & AI Analysis")
        scraped_news = collect_news(news_amount=5)
        
        if scraped_news:
            logging.info(f"Successfully harvested {len(scraped_news)} raw articles from RSS feeds.")

            cafef_path = os.path.join(project_root, "src", "news_data", f"CafeF_{date_str}.json")
            inferred_name = "CafeF" if os.path.exists(cafef_path) else "VnEconomy"

            # Optimization Step: Read today's local JSON cache file to skip processing things we already have.
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

            # Filter step: Only keep items that do NOT match links currently logged inside the cache.
            fresh_news = [art for art in scraped_news if (art.get("url") or art.get("link")) not in existing_links]
            
            if not fresh_news:
                logging.info("All harvested articles already exist in local cache. Wasting 0 Gemini tokens.")
                SYSTEM_STATE["last_run_status"] = "Success (No fresh news)"
            else:
                logging.info(f"Processing {len(fresh_news)} completely new articles through Gemini API...")
                # process_news_batch executes AI text parsing and formats individual target records
                formatted_news, gemini_analyses = process_news_batch(fresh_news, inferred_name)
                logging.info(f"Generated {len(gemini_analyses)} active Gemini analysis objects.")

                # Persist down to local file arrays before pushing out to the cloud
                save_news_locally(scraped_news)
                logging.info("Local news cache updated successfully.")

                if formatted_news:
                    insert_json_to_table(local_file_path=cafef_path, table_name=NEWS_TABLE)
        else:
            logging.info("No fresh articles harvested during this cycle.")

    except Exception as e:
        logging.error(f"Error executing News Phase: {e}")
        SYSTEM_STATE["last_run_status"] = f"Error (News Phase): {str(e)[:30]}"
        
    # --------------------------------------------------------------------------
    # --- Phase 2: Live Asset Stock Price Extraction Loop ---
    # --------------------------------------------------------------------------
    try:
        logging.info("Executing Phase 2: Stock Price Pipeline")
        watchlist = get_all_market_tickers(max_tickers=20)
        collected_prices = collect_prices(watchlist)
        
        if collected_prices:
            save_prices(collected_prices)
            logging.info(f"Successfully collected {len(collected_prices)} stock pricing rows.")

        # Sync the generated stock tracking JSON file directly into your cloud data matrix tables
        insert_json_to_table(
            local_file_path=os.path.join(project_root, "src", "stock_data", date_str, "stock_prices.json"),
            table_name=STOCKS_TABLE
        )
    except Exception as e:
        logging.error(f"Error executing Price Phase: {e}")
        SYSTEM_STATE["last_run_status"] = f"Error (Price Phase): {str(e)[:30]}"
    
    # --------------------------------------------------------------------------
    # --- Phase 3: Mathematical Assessment Engine & Instant Alerting ---
    # --------------------------------------------------------------------------
    try:
        logging.info("Executing Phase 3: Alert Evaluation")
        
        # Evaluate price movement thresholds
        if collected_prices:
            price_alerts = analyze_price_alerts(collected_prices)
            logging.info(f"Price alert criteria scanned. Violations detected: {len(price_alerts)}")
            for alert in price_alerts:
                formatted_msg = format_alert(alert_type="PRICE_ALERT", ticker=alert["ticker"], detail=alert["message"])
                send_message(formatted_msg)
                time.sleep(1.0) # Graceful delay step to respect Telegram API payload pacing limits

        # Evaluate sentiment volatility warnings generated via Gemini AI
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

    # --------------------------------------------------------------------------
    # --- Phase 4: End of Day Broadcast Summary Delivery (EOD Mode Only) ---
    # --------------------------------------------------------------------------
    if execution_mode == "EOD":
        try:
            logging.info("Executing Phase 4: Newsletter Generation and Broadcast")
            
            # 1. Dispatch formatted blocks into Telegram Chat/Channel
            digest_chunks = format_digest(collected_prices, scraped_news, gemini_analyses)
            send_bulk_messages(digest_chunks)
            logging.info("Daily newsletter digest blocks transmitted successfully to Telegram.")
            
            # 2. Dispatch data arrays to enterprise email workflows
            logging.info("Compiling and dispatching secure HTML SMTP email matrix...")
            send_email_digest(collected_prices, scraped_news, gemini_analyses)
            
            SYSTEM_STATE["last_run_status"] = "Success (EOD Completed)"
        except Exception as e:
            logging.error(f"Failed to transmit Daily Newsletter summary outputs: {e}")
            SYSTEM_STATE["last_run_status"] = "Error (EOD Broadcast)"
    else:
        # If no severe phase anomalies occurred during an intraday execution, mark it as successful
        if "Error" not in SYSTEM_STATE["last_run_status"] and SYSTEM_STATE["last_run_status"] != "Processing...":
            pass
        else:
            SYSTEM_STATE["last_run_status"] = "Success (Intraday Completed)"


# ==============================================================================
# 5. CORE AUTOMATION TIMELINES & SCHEDULER ENGINE
# ==============================================================================
def schedule_intraday_job():
    """Safety wrapper that prevents intraday scraping loops from launching outside trading hours."""
    current_hour = datetime.now().hour
    # Active operational bounds set between 09:00 and 15:59 daily
    if 9 <= current_hour <= 15:
        logging.info("Current time is within trading hours. Initializing intraday scan.")
        try:
            run_pipeline(execution_mode="INTRADAY")
        except Exception as intraday_err:
            logging.error(f"Scheduled Intraday workflow failed to process: {intraday_err}")
    else:
        logging.info(f"Hour {current_hour} is outside trading windows. Intraday execution skipped.")

def start_scheduler():
    """Synchronous infinite evaluation loop tracking timeline execution parameters."""
    logging.info("Automated Scheduler Daemon Initialized Successfully.")
    
    # Intraday scanning step: Fires off a health telemetry pull every 2 hours
    schedule.every(2).hours.do(schedule_intraday_job)
    
    # End-of-Day (EOD) compilation step: Fires exactly at 16:00 VST Monday through Friday
    schedule.every().monday.at("16:00").do(run_pipeline, execution_mode="EOD")
    schedule.every().tuesday.at("16:00").do(run_pipeline, execution_mode="EOD")
    schedule.every().wednesday.at("16:00").do(run_pipeline, execution_mode="EOD")
    schedule.every().thursday.at("16:00").do(run_pipeline, execution_mode="EOD")
    schedule.every().friday.at("16:00").do(run_pipeline, execution_mode="EOD")
    
    # The heartbeat clock loop of the orchestration engine
    while True:
        try:
            schedule.run_pending()
        except Exception as schedule_runtime_err:
            logging.error(f"Internal scheduling loop caught an unhandled exception: {schedule_runtime_err}")
        time.sleep(1)


# ==============================================================================
# 6. APPLICATION ENTRY SYSTEM BOOTSTRAP
# ==============================================================================
if __name__ == "__main__":
    # Developer Option: Run 'python main.py --now' to force execution instantly instead of waiting for a schedule slot
    if len(sys.argv) > 1 and sys.argv[1] == "--now":
        logging.info("Manual system override detected. Running pipeline immediately.")
        try:
            run_pipeline(execution_mode="EOD")
        except Exception as manual_override_err:
            logging.critical(f"Forced pipeline execution failed entirely: {manual_override_err}")
    else:
        logging.info("Initializing Unified Fin-News Bot Ecosystem...")

        # CONCURRENT EXECUTION LAYER:
        # Allocates an isolated execution thread for the incoming Telegram Bot command processor.
        # Setting 'daemon=True' binds the thread lifecycle to the primary script.
        # If main.py is terminated (Ctrl+C), this background bot thread dies cleanly along with it.
        try:
            bot_thread = threading.Thread(target=start_telegram_bot, daemon=True)
            bot_thread.start()
            logging.info("Background thread spinning up internal long-polling listener.")
        except Exception as thread_err:
            logging.critical(f"FATAL OPERATIONAL ERROR: Failed to deploy background thread infrastructure: {thread_err}")
            sys.exit(1)

        # Transition the primary main execution thread into the continuous scheduler loop clock
        try:
            start_scheduler()
        except KeyboardInterrupt:
            logging.info("SIGINT KeyboardInterrupt capture registered. Powering down service nodes gracefully.")
            SYSTEM_STATE["scheduler_active"] = False
            sys.exit(0)