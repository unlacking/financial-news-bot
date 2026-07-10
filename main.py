import os
from datetime import datetime
from dotenv import load_dotenv

from src.news_collector import collect_news, save_news_locally
from src.price_collector import get_all_market_tickers, collect_prices, save_data_locally as save_prices
from src.supabase_helper import insert_json_to_table, NEWS_TABLE, STOCKS_TABLE

def run_pipeline():
    print(f"\n====================================================")
    print(f"PIPELINE TRIGGERED: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"====================================================")

    if datetime.today().weekday() in [5, 6]:
        print("Market is closed on weekends. Pipeline skipped.")
        return

    date_str = datetime.now().strftime("%Y-%m-%d")

    # --- Phase 1: Live Financial News Pipeline inside main.py ---
    try:
        news_results = collect_news(news_amount=5)
        save_news_locally(news_results)
        
        cafef_path = os.path.join("src", "news_data", f"CafeF_{date_str}.json")
        vneconomy_path = os.path.join("src", "news_data", f"VnEconomy_{date_str}.json")

        # Only attempt database insertion if the file was actually generated/updated
        if os.path.exists(cafef_path):
            print(f"Syncing local cache data to cloud for CafeF...")
            insert_json_to_table(local_file_path=cafef_path, table_name=NEWS_TABLE)
        else:
            print("CafeF local file not found. Skipping.")

        if os.path.exists(vneconomy_path):
            print(f"Syncing local cache data to cloud for VnEconomy...")
            insert_json_to_table(local_file_path=vneconomy_path, table_name=NEWS_TABLE)
        else:
            print("VnEconomy local file not found. Skipping.")

    except Exception as e:
        print(f"Error executing News Phase: {e}")

    # --- Phase 2: Stock Price Pipeline ---
    try:
        watchlist = get_all_market_tickers()
        price_results = collect_prices(watchlist)
        save_prices(price_results)
        
        insert_json_to_table(
            local_file_path=os.path.join("stock_data", date_str, "stock_prices.json"),
            table_name=STOCKS_TABLE
        )
    except Exception as e:
        print(f"Error executing Price Phase: {e}")

    print(f"\n====================================================")
    print(f"INTEGRATED PIPELINE RUN COMPLETED")
    print(f"====================================================\n")

if __name__ == "__main__":
    load_dotenv()
    run_pipeline()