import os
from datetime import datetime
from dotenv import load_dotenv

from src.news_collector import collect_news, save_news_locally
from src.price_collector import get_all_market_tickers, collect_prices, save_data_locally as save_prices
from src.supabase_helper import upload_to_supabase

def run_pipeline():
    print(f"\n====================================================")
    print(f"PIPELINE TRIGGERED: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"====================================================")

    # 1. Weekend Guard Check (Market is closed)
    if datetime.today().weekday() in [5, 6]:
        print("Market is closed on weekends. Pipeline skipped.")
        return

    date_str = datetime.now().strftime("%Y-%m-%d")

    # ----------------------------------------------------
    # PHASE 1: Financial News Scraping & Backup
    # ----------------------------------------------------
    print("\n--- Phase 1: Live Financial News Pipeline ---")
    try:
        news_results = collect_news(news_amount=5)
        save_news_locally(news_results)
        
        # Stream archives cleanly up to your friend's storage cluster
        upload_to_supabase(
            local_file_path=os.path.join("news_data", f"CafeF_{date_str}.json"),
            remote_destination_path=f"news/CafeF_{date_str}.json"
        )
        upload_to_supabase(
            local_file_path=os.path.join("news_data", f"VnEconomy_{date_str}.json"),
            remote_destination_path=f"news/VnEconomy_{date_str}.json"
        )
    except Exception as e:
        print(f"Error executing News Phase: {e}")

    # ----------------------------------------------------
    # PHASE 2: Market Ticker Price Snapshot & Backup
    # ----------------------------------------------------
    print("\n--- Phase 2: Stock Price Pipeline ---")
    try:
        watchlist = get_all_market_tickers()
        price_results = collect_prices(watchlist)
        save_prices(price_results)
        
        # Stream stock asset tables up to storage
        upload_to_supabase(
            local_file_path=os.path.join("stock_data", date_str, "stock_prices.json"),
            remote_destination_path=f"stocks/{date_str}_prices.json"
        )
    except Exception as e:
        print(f"Error executing Price Phase: {e}")

    print(f"\n====================================================")
    print(f"INTEGRATED PIPELINE RUN COMPLETED")
    print(f"====================================================\n")

if __name__ == "__main__":
    load_dotenv()
    run_pipeline()