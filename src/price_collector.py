"""
STOCK PRICE COLLECTOR & MARKET DATA EXTRACTION ENGINE
-----------------------------------------------------
This module serves as the primary Extract-Transform (ET) component for Phase 2 of the pipeline.
It leverages the 'vnstock' API framework to dynamically fetch listed market tickers,
retrieve historical/intraday OHLCV price series, calculate percentage shifts across sessions,
extract dynamic macro-level index statistics for morning briefs, and write data rows locally.
"""

import os
import sys
import json
import time
import logging
from dotenv import load_dotenv
from datetime import datetime
from pathlib import Path

# Load official vnstock SDK modules for market reference and price data
try:
    from vnstock import Market, Reference, Quote
except ImportError as vnstock_err:
    logging.critical(f"CRITICAL DEPENDENCY FAULT: Failed to import 'vnstock' framework: {vnstock_err}")
    sys.exit(1)

# ==============================================================================
# 1. ENVIRONMENT & PATH RESOLUTION
# ==============================================================================
try:
    script_dir = Path(__file__).resolve().parent
    env_path = script_dir.parent / ".env"
    load_dotenv(dotenv_path=env_path)
except Exception as env_load_err:
    logging.warning(f"Failed to map .env path in price_collector: {env_load_err}")


# ==============================================================================
# 2. DYNAMIC TICKER WATCHLIST RESOLVER
# ==============================================================================
def get_all_market_tickers(max_tickers: int = None) -> list:
    """
    Queries the reference data layer of the Vietnamese market to pull active symbols.
    Filters the returned list to retain valid 3-character stock tickers.

    :param max_tickers: Optional integer cap for maximum symbols returned.
    :return: List of clean 3-character stock ticker strings.
    """
    fallback_list = ["VCB", "FPT", "HPG", "VNM", "SSI", "MBB", "TCB", "VIC"]
    
    try:
        logging.info("Querying reference market layer for active listed symbols...")
        ref = Reference()
        df_symbols = ref.equity.list()

        # Validate DataFrame output structure
        if df_symbols is not None and not df_symbols.empty and 'symbol' in df_symbols.columns:
            tickers = df_symbols['symbol'].dropna().unique().tolist()
            # Retain standard 3-character stock tickers
            clean_tickers = [str(t).strip().upper() for t in tickers if len(str(t).strip()) == 3]
            
            if clean_tickers:
                if max_tickers is not None and max_tickers > 0:
                    return clean_tickers[:max_tickers]
                return clean_tickers
        
        logging.warning("Reference market query returned empty dataset. Falling back to default watchlist.")

    except Exception as e:
        logging.error(f"Failed to dynamically retrieve live ticker list: {e}. Defaulting to fallback watchlist.")
    
    # Safe Fallback Output
    if max_tickers is not None and max_tickers > 0:
        return fallback_list[:max_tickers]
    return fallback_list


# ==============================================================================
# 3. DYNAMIC MACRO MARKET SUMMARY FETCHER (FOR MORNING NEWSLETTER)
# ==============================================================================
def get_market_macro_summary() -> dict:
    """
    Dynamically fetches the latest session summary for the VN-Index (closing points, 
    point change, total traded liquidity, and foreign flow status).
    
    This supplies Phase 4 of main.py with live macro market stats for the morning digest.
    :return: Dictionary containing formatted macro metrics.
    """
    logging.info("Fetching dynamic macro market indicators for VN-INDEX...")
    
    # Fallback default values in case of API failure
    fallback_macro = {
        "vnindex": "1,245.80",
        "change_points": 0.00,
        "liquidity": "N/A",
        "foreign_flow": "Đang cập nhật"
    }

    try:
        market = Market()
        # Fetch OHLCV data for the VNINDEX symbol (last 3 sessions to ensure comparison)
        df_index = market.equity(symbol="VNINDEX").ohlcv(count=3)

        if df_index is not None and not df_index.empty and len(df_index) >= 2:
            # Sort chronologically
            if 'time' in df_index.columns:
                df_index = df_index.sort_values(by='time', ascending=True)
            elif 'date' in df_index.columns:
                df_index = df_index.sort_values(by='date', ascending=True)

            latest_session = df_index.iloc[-1]
            prev_session = df_index.iloc[-2]

            latest_close = float(latest_session.get("close", 0))
            prev_close = float(prev_session.get("close", 0))
            point_change = latest_close - prev_close

            # Format liquidity (Volume or Value)
            volume = float(latest_session.get("volume", 0))
            if volume > 0:
                liquidity_str = f"{volume:,.0f} cổ phiếu"
            else:
                liquidity_str = "Ổn định"

            return {
                "vnindex": f"{latest_close:,.2f}",
                "change_points": round(point_change, 2),
                "liquidity": liquidity_str,
                "foreign_flow": "Theo dõi phiên KDL"
            }
        else:
            logging.warning("Insufficient macro index data returned by vnstock. Using default macro fallback.")

    except Exception as macro_err:
        logging.error(f"Failed to fetch dynamic macro market indicators: {macro_err}")

    return fallback_macro


# ==============================================================================
# 4. OHLCV PRICE HARVESTING ENGINE
# ==============================================================================
def collect_prices(ticker_list: list = None) -> list:
    """
    Iterates over a list of stock tickers to pull OHLCV session records,
    sorts session timestamps, and calculates session-over-session percentage change.

    :param ticker_list: List of 3-character ticker strings.
    :return: List of dictionaries containing ticker price metrics.
    """
    if not ticker_list or not isinstance(ticker_list, list):
        logging.warning("No valid ticker list supplied to price collector. Utilizing default watchlist.")
        ticker_list = ["VCB", "FPT", "HPG", "VNM"]

    price_data = []
    logging.info(f"Starting automated price collection for {len(ticker_list)} market symbols...")

    try:
        market = Market()
    except Exception as market_init_err:
        logging.error(f"Failed to initialize vnstock Market client: {market_init_err}")
        return []

    has_api_key = os.getenv("VNSTOCK_API_KEY") is not None
    today_str = datetime.now().strftime("%Y-%m-%d")

    for index, ticker in enumerate(ticker_list, 1):
        retries = 0
        max_retries = 3

        while retries < max_retries:
            try:
                # Enforce safe delay between API requests to prevent rate limits
                time.sleep(1.5 if has_api_key else 3.5)
                
                # Fetch recent daily session data
                df = market.equity(symbol=ticker).ohlcv(count=5)
                
                # Validation: Ensure dataframe contains sufficient rows for change calculation
                if df is None or df.empty or len(df) < 2:
                    logging.warning(f"Insufficient session data returned for ticker '{ticker}'. Skipping.")
                    break 

                # Normalize dataframe row ordering by date/time columns
                if 'time' in df.columns:
                    df = df.sort_values(by='time', ascending=True)
                elif 'date' in df.columns:
                    df = df.sort_values(by='date', ascending=True)
                else:
                    df = df.sort_index(ascending=True)

                # Extract the last two trading sessions
                prev_session = df.iloc[-2]
                latest_session = df.iloc[-1]

                # Cast close prices safely to float values
                latest_price = float(latest_session.get('close', 0))
                prev_price = float(prev_session.get('close', 0))

                # Calculate percentage shift
                if prev_price > 0:
                    pct_change = ((latest_price - prev_price) / prev_price) * 100
                else:
                    pct_change = 0.0

                price_data.append({
                    "ticker": str(ticker).strip().upper(),
                    "price": latest_price,
                    "percentage_change": round(pct_change, 2),
                    "collected_date": today_str
                })
                
                if index % 20 == 0 or index == len(ticker_list):
                    logging.info(f"Price Collection Progress: Processed {index}/{len(ticker_list)} tickers.")
                
                # Break out of retry loop on success
                break 

            except Exception as e:
                error_msg = str(e)
                # Handle API rate-limiting errors gracefully with a backoff delay
                if "GIỚI HẠN API ĐÃ ĐẠT TỐI ĐA" in error_msg or "Rate Limit Exceeded" in error_msg:
                    logging.warning(f"Rate limit hit during fetch for '{ticker}'. Pausing 60 seconds before retry (Attempt {retries + 1}/{max_retries})...")
                    time.sleep(60)
                    retries += 1
                else:
                    logging.error(f"Unexpected error fetching price metrics for '{ticker}': {error_msg}")
                    break

    return price_data


# ==============================================================================
# 5. LOCAL DISK ARCHIVAL ENGINE
# ==============================================================================
def save_data_locally(results: list) -> None:
    """
    Saves price dictionary records into a dated folder inside 'src/stock_data/'.

    :param results: List or dictionary of collected price records.
    """
    if not results:
        logging.info("No price data supplied to save_data_locally. Storage operation skipped.")
        return

    try:
        # Establish absolute directory routing relative to script file position
        script_dir = Path(__file__).resolve().parent
        base_dir = script_dir / "stock_data"
        
        current_date = datetime.now().strftime("%Y-%m-%d")
        target_folder = base_dir / current_date
        
        # Ensure target folder structure exists on disk
        target_folder.mkdir(parents=True, exist_ok=True)
        file_path = target_folder / "stock_prices.json"

        # Commit price records to JSON format on disk
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=4)
        logging.info(f"Successfully archived stock price data to path: {file_path}")

    except Exception as write_err:
        logging.error(f"Failed to write stock price records to local disk: {write_err}")


# ==============================================================================
# 6. ISOLATED STANDALONE TEST ENTRY POINT
# ==============================================================================
if __name__ == "__main__":
    # Configure basic logger formatting for standalone execution testing
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

    if datetime.today().weekday() in [5, 6]:
        logging.info("Market is closed on weekends. Exiting standalone collector process.")
        sys.exit(0)

    logging.info("Executing standalone price collector & macro summary test run...")
    
    # Test Macro Indicator Extraction
    macro_summary = get_market_macro_summary()
    logging.info(f"Macro Market Summary fetched: {macro_summary}")
    
    # Test Ticker Price Harvesting
    watchlist = get_all_market_tickers(max_tickers=5)
    results = collect_prices(watchlist)
    save_data_locally(results)
    
    logging.info(f"Standalone execution completed. Collected {len(results)} ticker price records.")