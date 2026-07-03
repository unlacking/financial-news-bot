import os
import sys
from datetime import datetime
from dotenv import load_dotenv

# Import the clean components from your feature branches
from news_collector import collect_news, save_news_locally
from price_collector import get_all_market_tickers, collect_prices, save_data_locally as save_prices

def run_pipeline():
    print(f"\n====================================================")
    print(f"PIPELINE TRIGGERED: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"====================================================")

    # 1. Weekend Guard Check (Vietnam Timezone)
    if datetime.today().weekday() in [5, 6]:
        print("Market is closed on weekends. Pipeline skipped.")
        return

    # ----------------------------------------------------
    # PHASE 1: Financial News Collection Pipeline (Swapped to First)
    # ----------------------------------------------------
    print("\n--- Phase 1: Gathering Live Financial News ---")
    try:
        # Pull the latest media releases and newspaper headlines
        news_results = collect_news(news_amount=5)
        
        # Save articles out into your structured /news_data/ publisher formats
        save_news_locally(news_results)
        print("Phase 1 Complete: Financial news archived.")
    except Exception as e:
        print(f"Critical Error in Phase 1 (News): {e}")

    # ----------------------------------------------------
    # PHASE 2: Stock Price Collection Pipeline (Swapped to Second)
    # ----------------------------------------------------
    print("\n--- Phase 2: Gathering Whole-Market Stock Prices ---")
    try:
        # Dynamically fetch the ~1,500 listed tickers
        watchlist = get_all_market_tickers()
        
        # Pull prices with built-in 1.5s rate-limit intervals and auto-retry
        price_results = collect_prices(watchlist)
        
        # Save metrics out into the absolute /stock_data/YYYY-MM-DD/ directory
        save_prices(price_results)
        print("Phase 2 Complete: All stock metrics archived.")
    except Exception as e:
        print(f"Critical Error in Phase 2 (Prices): {e}")

    print(f"\n====================================================")
    print(f"PIPELINE RUN COMPLETED SUCCESSFULLY")
    print(f"====================================================\n")

if __name__ == "__main__":
    # Load all keys (like VNSTOCK_API_KEY or URL targets) globally once
    load_dotenv()
    
    # Run the streamline loop
    run_pipeline()