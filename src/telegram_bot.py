"""
TELEGRAM BOT INTERFACE & NOTIFICATION ENGINE
--------------------------------------------
This module manages outbound message delivery to Telegram channels/groups
and runs the interactive long-polling command interface for CLI commands:
  - /status  : Displays pipeline runtime health and database states.
  - /trigger : Forces immediate execution sweep of the intraday pipeline.
  - /price   : Queries cloud database for recent stock price metrics.
  - /news    : Retrieves recent news articles or ticker-specific analysis.
"""

import os
import sys
import time
import logging
import httpx
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from dotenv import load_dotenv

# Import database read utilities from database_client
try:
    from src.database_client import check_supabase_connection, get_stock_price, get_latest_news
except ImportError as imp_err:
    logging.warning(f"Failed to import database helpers in telegram_bot: {imp_err}")

try:
    load_dotenv()
except Exception as env_err:
    logging.warning(f"Non-fatal warning: Failed to map .env path in telegram_bot: {env_err}")

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_GROUP_CHAT_ID = os.getenv("TELEGRAM_GROUP_CHAT_ID", "")


# ==============================================================================
# SECTION 1: OUTBOUND ALERTS & BULK DELIVERY ENGINE
# ==============================================================================

def send_message(text: str) -> bool:
    """
    Sends a formatted message to the configured Telegram chat or channel.
    Attempts Markdown parsing mode first, with automatic fallback to plain text.
    """
    if not TELEGRAM_TOKEN or not TELEGRAM_GROUP_CHAT_ID:
        logging.error("Telegram delivery aborted: TELEGRAM_BOT_TOKEN or TELEGRAM_GROUP_CHAT_ID missing.")
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
            logging.warning(f"Telegram API Markdown delivery rejected (HTTP {response.status_code}). Executing raw text fallback.")
            payload.pop("parse_mode", None)
            fallback_response = httpx.post(url, json=payload, timeout=10.0)
            return fallback_response.status_code == 200

    except httpx.NetworkError as net_err:
        logging.error(f"Network transport failure communicating with Telegram API: {net_err}")
        return False
    except Exception as e:
        logging.error(f"Unexpected operational failure during Telegram delivery: {e}")
        return False


def send_bulk_messages(messages: list) -> None:
    """
    Delivers a list of string message chunks sequentially with rate-limit pacing delays.
    """
    if not messages or not isinstance(messages, list):
        logging.info("No message payloads provided for bulk distribution.")
        return

    logging.info(f"Initiating bulk delivery sequence for {len(messages)} message blocks.")
    for idx, msg in enumerate(messages, 1):
        if not msg:
            continue
            
        success = send_message(msg)
        if success:
            logging.info(f"Successfully delivered message block {idx}/{len(messages)}")
        else:
            logging.error(f"Failed to deliver message block {idx}/{len(messages)}")
        
        if idx < len(messages):
            time.sleep(1.5)


# ==============================================================================
# SECTION 2: INBOUND INTERACTIVE COMMAND HANDLERS
# ==============================================================================

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /status: Displays system state, pipeline execution timestamps, and database health.
    """
    if not update.message:
        return

    main_mod = sys.modules.get('__main__')
    state = getattr(main_mod, 'SYSTEM_STATE', {
        "last_run_time": "Unknown", 
        "last_run_status": "Offline", 
        "scheduler_active": False
    })
    
    db_status = "Connected" if check_supabase_connection() else "Disconnected"
    scheduler_status = "Active" if state.get("scheduler_active") else "Offline"

    message = (
        f"**SYSTEM ENGINE STATUS DIAGNOSTICS**\n\n"
        f"Last Pipeline Run: {state.get('last_run_time', 'Unknown')}\n"
        f"Last Execution Status: {state.get('last_run_status', 'Unknown')}\n"
        f"Database Status: {db_status}\n"
        f"Scheduler Core: {scheduler_status}"
    )
    await update.message.reply_text(message, parse_mode="Markdown")


async def trigger_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /trigger: Forces an immediate intraday execution sweep of the pipeline.
    """
    if not update.message:
        return

    await update.message.reply_text("Initiating forced pipeline execution sweep...")
    
    main_mod = sys.modules.get('__main__')
    pipeline_func = getattr(main_mod, 'run_pipeline', None)
    
    if pipeline_func:
        try:
            pipeline_func(execution_mode="INTRADAY")
            await update.message.reply_text("Forced pipeline sweep successfully completed.")
        except Exception as e:
            logging.error(f"Forced pipeline execution failed: {e}")
            await update.message.reply_text(f"Execution error encountered: {e}")
    else:
        await update.message.reply_text("System link unresolvable. Pipeline function not exposed in main context.")


async def price_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /price <TICKER>: Queries Supabase for the newest stock price metrics.
    """
    if not update.message:
        return

    if not context.args:
        await update.message.reply_text("Syntax error. Usage: `/price TICKER`", parse_mode="Markdown")
        return
        
    ticker = str(context.args[0]).strip().upper()
    await update.message.reply_text(f"Querying database records for: **{ticker}**...", parse_mode="Markdown")
    
    try:
        data = get_stock_price(ticker)
        if not data or not isinstance(data, dict):
            await update.message.reply_text(f"No recent price records found in database for ticker **{ticker}**.", parse_mode="Markdown")
            return
            
        raw_price = data.get("price", 0)
        price = float(raw_price) if raw_price is not None else 0.0
        
        raw_change = data.get("percentage_change", 0.0)
        change = float(raw_change) if raw_change is not None else 0.0
        
        direction = "Up" if change >= 0 else "Down"
        
        msg = (
            f"**MARKET SNAPSHOT: {ticker}**\n\n"
            f"Last Price: {price:,.0f} VND\n"
            f"Shift: {change:+.2f}% ({direction})"
        )
        await update.message.reply_text(msg, parse_mode="Markdown")
    except Exception as e:
        logging.error(f"Error executing /price command for ticker '{ticker}': {e}")
        await update.message.reply_text(f"Failed to query price metrics for **{ticker}**.", parse_mode="Markdown")


async def news_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /news [TICKER]: Queries recent market articles or ticker-specific analysis with affected sectors.
    """
    if not update.message:
        return

    ticker = str(context.args[0]).strip().upper() if context.args else None
    
    try:
        if ticker:
            await update.message.reply_text(f"Fetching recent articles for: **{ticker}**...", parse_mode="Markdown")
            articles = get_latest_news(ticker=ticker, limit=3)
        else:
            await update.message.reply_text("Fetching latest global market news...", parse_mode="Markdown")
            articles = get_latest_news(limit=5)
            
        if not articles or not isinstance(articles, list):
            await update.message.reply_text("No recent news records found in database.")
            return
            
        response_blocks = []
        for art in articles:
            if not isinstance(art, dict):
                continue

            title = art.get("title", "Untitled Article").strip()
            link = art.get("link", "#")
            source = art.get("source", "Unknown Source").strip()
            sentiment = art.get("sentiment", "Neutral").strip()
            score = art.get("importance_score", 3)
            sectors = art.get("affected_sectors", [])

            sector_text = f" | Sectors: {', '.join(sectors)}" if sectors and isinstance(sectors, list) else ""
            
            block = f"• [{title}]({link})\n   _Source: {source} | Sentiment: {sentiment} ({score}/5){sector_text}_"
            response_blocks.append(block)
            
        if not response_blocks:
            await update.message.reply_text("No valid article records available to display.")
            return

        header = f"**LATEST HEADLINES FOR {ticker}**\n\n" if ticker else "**BROAD MARKET NEWS DIGEST**\n\n"
        await update.message.reply_text(
            header + "\n\n".join(response_blocks), 
            parse_mode="Markdown", 
            disable_web_page_preview=True
        )
    except Exception as e:
        logging.error(f"Error executing /news command: {e}")
        await update.message.reply_text("Failed to retrieve latest news records.", parse_mode="Markdown")


# ==============================================================================
# SECTION 3: BOT ENGINE INITIALIZER
# ==============================================================================

def main():
    if not TELEGRAM_TOKEN:
        logging.error("CRITICAL: Missing TELEGRAM_BOT_TOKEN environment variable.")
        return

    try:
        app = Application.builder().token(TELEGRAM_TOKEN).build()

        app.add_handler(CommandHandler("status", status_command))
        app.add_handler(CommandHandler("trigger", trigger_command))
        app.add_handler(CommandHandler("price", price_command))
        app.add_handler(CommandHandler("news", news_command))
        app.add_handler(CommandHandler("digest", news_command))

        logging.info("Telegram Bot Dashboard initialized. Listening for commands...")
        app.run_polling()
    except Exception as init_err:
        logging.error(f"Failed to initialize Telegram Bot long-polling engine: {init_err}")


if __name__ == "__main__":
    main()