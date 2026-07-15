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

def get_all_market_tickers(max_tickers: int = None):
    """
    Dynamically fetches active stock symbols currently listed on the Vietnamese market.
    :param max_tickers: Optional integer to limit the total number of tickers returned.
    :return: List of validated 3-character stock ticker strings.
    """
    try:
        ref = Reference()
        df_symbols = ref.equity.list()
        if 'symbol' in df_symbols.columns:
            tickers = df_symbols['symbol'].dropna().unique().tolist()
            # Filter down to standard 3-character stock tickers
            clean_tickers = [str(t).strip() for t in tickers if len(str(t).strip()) == 3]
            
            # Apply slicing if max_tickers configuration parameter is specified
            if max_tickers is not None and max_tickers > 0:
                return clean_tickers[:max_tickers]
            
            return clean_tickers
            
    except Exception as e:
        print(f"Warning: Failed to fetch live ticker list dynamically: {e}")
    
    # Absolute minimal fallback if connection fails
    fallback_list = ["VCB", "FPT", "HPG", "VNM"]
    if max_tickers is not None and max_tickers > 0:
        return fallback_list[:max_tickers]
    return fallback_list

def collect_prices(ticker_list=None):
    if ticker_list is None:
        ticker_list = ["VCB", "FPT", "HPG", "VNM"]

    price_data = []
    print(f"Starting automated stock price collection for: {len(ticker_list)} tickers...")

    market = Market()
    has_api_key = os.getenv("VNSTOCK_API_KEY") is not None
    today_str = datetime.now().strftime("%Y-%m-%d")

    for index, ticker in enumerate(ticker_list, 1):
        retries = 0
        while retries < 3:
            try:
                time.sleep(1.5 if has_api_key else 3.5)
                df = market.equity(symbol=ticker).ohlcv(count=5)
                
                if df.empty or len(df) < 2:
                    break 
                
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

                # --- APPEND A FLAT DATABASE-READY ROW ---
                price_data.append({
                    "ticker": ticker,
                    "price": latest_price,
                    "percentage_change": round(pct_change, 2),
                    "collected_date": today_str
                })
                
                if index % 20 == 0 or index == len(ticker_list):
                    print(f"Progress: Profiled {index}/{len(ticker_list)} stocks...")
                
                break 

            except Exception as e:
                error_msg = str(e)
                if "GIỚI HẠN API ĐÃ ĐẠT TỐI ĐA" in error_msg or "Rate Limit Exceeded" in error_msg:
                    print(f"\n[RATE LIMIT HIT] Smart-pausing for 60 seconds before retrying {ticker}...")
                    time.sleep(60)
                    retries += 1
                    continue 
                else:
                    break

    return price_data

def save_data_locally(results: dict):
    "Saves the results dictionary into a dated subfolder anchored explicitly to the script directory."
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