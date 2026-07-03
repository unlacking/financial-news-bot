import os
import sys
import json
import time
from dotenv import load_dotenv
from datetime import datetime
from pathlib import Path
# Use the clean, official unified vnstock package
from vnstock import Market, Reference

load_dotenv()

def get_all_market_tickers():
    """
    Dynamically fetches all active stock symbols currently listed on the Vietnamese market.
    """
    try:
        ref = Reference()
        df_symbols = ref.equity.list()
        if 'symbol' in df_symbols.columns:
            tickers = df_symbols['symbol'].dropna().unique().tolist()
            # Filter down to standard 3-character stock tickers
            return [str(t).strip() for t in tickers if len(str(t).strip()) == 3]
    except Exception as e:
        print(f"Warning: Failed to fetch live ticker list dynamically: {e}")
    
    # Absolute minimal fallback fallback if connection fails
    return ["VCB", "FPT", "HPG", "VNM"]

def collect_prices(ticker_list=None):
    if ticker_list is None:
        ticker_list = ["VCB", "FPT", "HPG", "VNM"]

    price_data = {}
    print(f"Starting automated stock price collection for: {len(ticker_list)} tickers...")

    market = Market()
    has_api_key = os.getenv("VNSTOCK_API_KEY") is not None

    for index, ticker in enumerate(ticker_list, 1):
        # We use a while loop for a single ticker to allow retrying if rate limited
        retries = 0
        while retries < 3:
            try:
                # Bumping base safety slightly to 1.5s for Community tier (40 reqs/min max)
                time.sleep(1.5 if has_api_key else 3.5)
                
                df = market.equity(symbol=ticker).ohlcv(count=5)
                
                if df.empty or len(df) < 2:
                    break # Not enough data, break out of retry loop to move to next ticker
                
                if 'time' in df.columns:
                    df = df.sort_values(by='time', ascending=True)
                elif 'date' in df.columns:
                    df = df.sort_values(by='date', ascending=True)
                else:
                    df = df.sort_index(ascending=True)

                prev_session = df.iloc[-2]
                latest_session = df.iloc[-1]

                latest_price = float(latest_session['close'])
                prev_price = float(prev_session['close'])

                if prev_price > 0:
                    pct_change = ((latest_price - prev_price) / prev_price) * 100
                else:
                    pct_change = 0.0

                price_data[ticker] = {
                    "price": latest_price,
                    "percentage_change": round(pct_change, 2)
                }
                
                if index % 20 == 0 or index == len(ticker_list):
                    print(f"Progress: Profiled {index}/{len(ticker_list)} stocks...")
                
                break # Successfully processed, exit the retry loop for this ticker

            except Exception as e:
                error_msg = str(e)
                # Check if the error print or response contains the rate limit keyword
                if "GIỚI HẠN API ĐÃ ĐẠT TỐI ĐA" in error_msg or "Rate Limit Exceeded" in error_msg:
                    print(f"\n[RATE LIMIT HIT] Smart-pausing for 60 seconds before retrying {ticker}...")
                    time.sleep(60)
                    retries += 1
                    continue # Retry the exact same ticker again
                else:
                    # It's a normal error (like your delisted DDM/AGF stocks), skip it cleanly
                    break

    return price_data

def save_data_locally(results: dict):
    """
    Saves the results dictionary into a dated subfolder anchored explicitly to the script directory.
    Example path: stock_data/2026-07-03/stock_prices.json
    """
    # Force absolute routing by mapping paths down from where the script is hosted
    script_dir = Path(__file__).resolve().parent
    base_dir = script_dir / "stock_data"
    
    # Get the current date in YYYY-MM-DD format
    current_date = datetime.now().strftime("%Y-%m-%d")
    
    # Combine them to create the target folder path
    target_folder = base_dir / current_date
    
    # Create the folder automatically if it doesn't exist yet
    target_folder.mkdir(parents=True, exist_ok=True)
    
    # Define the full path for the file inside that folder
    file_path = target_folder / "stock_prices.json"
    
    # Write out the data (using indentation to keep the JSON readable)
    try:
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=4)
        print(f"Successfully archived data to absolute path: {file_path}")
    except Exception as e:
        print(f"Failed to write file locally: {e}")

if __name__ == "__main__":
    if datetime.today().weekday() in [5, 6]:
        print("Market is closed on weekends. Exiting collector pipeline.")
        sys.exit()

    # Dynamically query all listed market companies from the reference layer
    watchlist = get_all_market_tickers()
    
    results = collect_prices(watchlist)
    save_data_locally(results)
    
    print("\n================ RETURNED DICTIONARY RESULTS ================")
    import pprint
    pprint.pprint(results)