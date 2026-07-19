import os
import sys
import time
import logging
import httpx
import datetime
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from dotenv import load_dotenv

# Absolute path import relative to project root execution
from src.supabase_helper import check_supabase_connection, get_stock_price, get_latest_news

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_GROUP_CHAT_ID = os.getenv("TELEGRAM_GROUP_CHAT_ID")

# ==============================================================================
# SECTION 1: OUTBOUND ALERTS & BULK DELIVERY (Your Original Code)
# ==============================================================================

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
        
        if idx < len(messages):
            time.sleep(1.5)

# ==============================================================================
# SECTION 2: INBOUND INTERACTIVE COMMAND HANDLERS
# ==============================================================================

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Dynamically extract tracking variables out of main execution engine
    main_mod = sys.modules.get('__main__')
    state = getattr(main_mod, 'SYSTEM_STATE', {
        "last_run_time": "Unknown", 
        "last_run_status": "Offline", 
        "scheduler_active": False
    })
    
    db_status = "🟢 Connected" if check_supabase_connection() else "🔴 Disconnected"
    scheduler_status = "🟢 Active" if state.get("scheduler_active") else "🔴 Offline"

    message = (
        f"🖥️ **SYSTEM ENGINE STATUS DIAGNOSTICS**\n\n"
        f"🔄 Last Pipeline Run: {state.get('last_run_time')}\n"
        f"📊 Last Execution Status: {state.get('last_run_status')}\n"
        f"🗄️ Supabase DB Track: {db_status}\n"
        f"⏰ Scheduler Core: {scheduler_status}"
    )
    await update.message.reply_text(message, parse_mode="Markdown")

async def trigger_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⚡ Instantly forcing pipeline execution step...")
    
    main_mod = sys.modules.get('__main__')
    pipeline_func = getattr(main_mod, 'run_pipeline', None)
    
    if pipeline_func:
        try:
            pipeline_func(execution_mode="INTRADAY")
            await update.message.reply_text("✅ Forced pipeline sweep successfully completed!")
        except Exception as e:
            await update.message.reply_text(f"❌ Execution crash: {e}")
    else:
        await update.message.reply_text("❌ System tracking link missing. Pipeline unresolvable.")

async def price_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Syntax error. Usage: `/price TICKER`", parse_mode="Markdown")
        return
        
    ticker = context.args[0].upper()
    await update.message.reply_text(f"Checking database matrices for: **{ticker}**...", parse_mode="Markdown")
    
    data = get_stock_price(ticker)
    if not data:
        await update.message.reply_text(f"No recent price tracks found in the database for ticker **{ticker}**.", parse_mode="Markdown")
        return
        
    price = data.get("price", 0)
    change = data.get("percentage_change", 0.0)
    arrow = "🔺" if change >= 0 else "🔻"
    
    msg = (
        f"**MARKET SNAPSHOT: {ticker}**\n\n"
        f"Last Price: {price:,} VND\n"
        f"{arrow} Shift Metrics: {change:+.2f}%"
    )
    await update.message.reply_text(msg, parse_mode="Markdown")

async def news_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ticker = context.args[0].upper() if context.args else None
    
    if ticker:
        await update.message.reply_text(f"Compiling historical article index for: **{ticker}**...", parse_mode="Markdown")
        articles = get_latest_news(ticker=ticker, limit=3)
    else:
        await update.message.reply_text("Compiling latest global market summary news...", parse_mode="Markdown")
        articles = get_latest_news(limit=5)
        
    if not articles:
        await update.message.reply_text("History trace returned empty. No context cataloged yet.")
        return
        
    response_blocks = []
    for art in articles:
        title = art.get("title", "Untitled Context String")
        link = art.get("link", "#")
        source = art.get("source", "Unknown Nodule")
        sentiment = art.get("sentiment", "error from telegram_bot.py")
        
        block = f"• [{title}]({link})\n   _Source: {source} | Bias: {sentiment}_"
        response_blocks.append(block)
        
    header = f"**LATEST HEADLINES FOR {ticker}**\n\n" if ticker else "**BROAD MARKET NEWS DIGEST**\n\n"
    await update.message.reply_text(header + "\n\n".join(response_blocks), parse_mode="Markdown", disable_web_page_preview=True)

# ==============================================================================
# SECTION 3: BOT LONG-POLLING ENGINE INITIALIZER
# ==============================================================================

def main():
    if not TELEGRAM_TOKEN:
        print("CRITICAL: Missing TELEGRAM_BOT_TOKEN environment key configuration.")
        return

    # Build network application leveraging the exact token variable name
    app = Application.builder().token(TELEGRAM_TOKEN).build()

    # Route bot handlers to active command functions
    app.add_handler(CommandHandler("status", status_command))
    app.add_handler(CommandHandler("trigger", trigger_command))
    app.add_handler(CommandHandler("price", price_command))
    app.add_handler(CommandHandler("news", news_command))
    app.add_handler(CommandHandler("digest", news_command))

    print("CLI Dashboard Bot initialized. Listening for messages via active network polling stream...")
    app.run_polling()

if __name__ == "__main__":
    main()