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
import httpx
from urllib.parse import urlparse
from datetime import datetime
import threading
import schedule 
from dotenv import load_dotenv

# ==============================================================================
# 1. CORE MODULE & ENGINE IMPORTS
# ==============================================================================
try:
    from src.news_collector import collect_news, save_news_locally
    from src.formatter import format_alert, format_digest
    from src.price_collector import get_all_market_tickers, collect_prices, save_data_locally as save_prices
    from src.database_client import insert_json_to_table, NEWS_TABLE, STOCKS_TABLE, process_news_batch
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
SYSTEM_STATE = {
    "last_run_time": "Never executed yet",
    "last_run_status": "Idle",
    "scheduler_active": True
}

def check_gemini_analysis(articles: list) -> list:
    """
    Queries Supabase in a single HTTP request to fetch existing links.
    Returns only the articles that are either missing from the database 
    or contain an error state requiring a re-run.
    """
    if not articles or not isinstance(articles, list):
        return []

    url_env = os.getenv("SUPABASE_URL")
    key_env = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    gemini_table = os.getenv("SUPABASE_GEMINI_TABLE", "gemini_responses")

    if not url_env or not key_env:
        logging.warning("Supabase configuration missing. Bypassing cloud analysis cache check.")
        return articles

    links = [art.get("url") or art.get("link") for art in articles if (art.get("url") or art.get("link"))]
    if not links:
        return []

    try:
        parsed_url = urlparse(url_env)
        base_url = f"{parsed_url.scheme}://{parsed_url.netloc}"
        endpoint = f"{base_url}/rest/v1/{gemini_table}"

        headers = {
            "Authorization": f"Bearer {key_env}",
            "apiKey": key_env
        }
        
        formatted_links = ",".join([f'"{l}"' for l in links])
        params = {
            "link": f"in.({formatted_links})",
            "select": "link,sentiment"
        }

        response = httpx.get(endpoint, headers=headers, params=params, timeout=8.0)
        
        healthy_links = set()
        if response.status_code == 200 and isinstance(response.json(), list):
            for record in response.json():
                link = record.get("link")
                sentiment = str(record.get("sentiment", "")).lower()
                if link and sentiment and "error" not in sentiment:
                    healthy_links.add(link)

        unprocessed_news = []
        for art in articles:
            art_link = art.get("url") or art.get("link")
            if art_link not in healthy_links:
                unprocessed_news.append(art)

        skipped_count = len(articles) - len(unprocessed_news)
        logging.info(f"Cloud DB cache check complete: {skipped_count} healthy records skipped, {len(unprocessed_news)} queued for processing.")
        return unprocessed_news

    except Exception as db_err:
        logging.error(f"Failed to query Supabase cloud analysis cache: {db_err}")
        return articles

# ==============================================================================
# 3. DIRECTORY STRUCTURE & SYSTEM LOGGER INITIALIZATION
# ==============================================================================
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

            fresh_news = check_gemini_analysis(scraped_news)

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

    # --------------------------------------------------------------------------
    # --- Phase 4: End of Day Broadcast Summary Delivery (EOD Mode Only) ---
    # --------------------------------------------------------------------------
    if execution_mode == "EOD":
        try:
            logging.info("Executing Phase 4: Newsletter Generation and Broadcast")
            
            # Construct macro market overview payload for the morning/EOD digest
            market_macro_payload = {
                "vnindex": "1,245.80",
                "change_points": -12.35,
                "liquidity": "21,500 tỷ VNĐ",
                "foreign_flow": "Bán ròng 185 tỷ VNĐ"
            }

            # 1. Dispatch formatted blocks into Telegram Chat/Channel
            digest_chunks = format_digest(
                price_data=collected_prices, 
                news_items=scraped_news, 
                gemini_analyses=gemini_analyses,
                market_macro=market_macro_payload  # Pass macro market data
            )
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
        if "Error" not in SYSTEM_STATE["last_run_status"] and SYSTEM_STATE["last_run_status"] != "Processing...":
            pass
        else:
            SYSTEM_STATE["last_run_status"] = "Success (Intraday Completed)"


# ==============================================================================
# 5. CORE AUTOMATION TIMELINES & SCHEDULER ENGINE
# ==============================================================================
def schedule_intraday_job():
    current_hour = datetime.now().hour
    if 9 <= current_hour <= 15:
        logging.info("Current time is within trading hours. Initializing intraday scan.")
        try:
            run_pipeline(execution_mode="INTRADAY")
        except Exception as intraday_err:
            logging.error(f"Scheduled Intraday workflow failed to process: {intraday_err}")
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
        try:
            schedule.run_pending()
        except Exception as schedule_runtime_err:
            logging.error(f"Internal scheduling loop caught an unhandled exception: {schedule_runtime_err}")
        time.sleep(1)


# ==============================================================================
# 6. APPLICATION ENTRY SYSTEM BOOTSTRAP
# ==============================================================================
if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--now":
        logging.info("Manual system override detected. Running pipeline immediately.")
        try:
            run_pipeline(execution_mode="EOD")
        except Exception as manual_override_err:
            logging.critical(f"Forced pipeline execution failed entirely: {manual_override_err}")
    else:
        logging.info("Initializing Unified Fin-News Bot Ecosystem...")

        try:
            bot_thread = threading.Thread(target=start_telegram_bot, daemon=True)
            bot_thread.start()
            logging.info("Background thread spinning up internal long-polling listener.")
        except Exception as thread_err:
            logging.critical(f"FATAL OPERATIONAL ERROR: Failed to deploy background thread infrastructure: {thread_err}")
            sys.exit(1)

        try:
            start_scheduler()
        except KeyboardInterrupt:
            logging.info("SIGINT KeyboardInterrupt capture registered. Powering down service nodes gracefully.")
            SYSTEM_STATE["scheduler_active"] = False
            sys.exit(0)