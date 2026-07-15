# test_suite/test_price_collector.py
import os
import sys

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from src.price_collector import get_all_market_tickers, collect_prices, save_data_locally

def run_price_collector_test():
    print("====================================")
    print("STARTING PRICE COLLECTOR ISOLATION TEST")
    print("====================================\n")

    print("Fetching active market tickers from reference layer...")
    try:
        tickers = get_all_market_tickers()
        print(f"Total listed tickers detected: {len(tickers)}")
        
        # Slice down to a mini-watchlist for quick testing execution
        test_watchlist = tickers[:3] if len(tickers) >= 3 else ["VCB", "FPT", "HPG"]
        print(f"Executing pricing snapshot query for test target: {test_watchlist}")
        
        price_data = collect_prices(ticker_list=test_watchlist)
        print(f"Collected records returned: {len(price_data)}")
        
        if price_data:
            print("\nFirst Price Record Format Verification:")
            sample = price_data[0]
            print(f"Ticker: {sample.get('ticker')}")
            print(f"Price: {sample.get('price')}")
            print(f"Percentage Change: {sample.get('percentage_change')}%")
            
            print("\nTesting stock price storage archive formatting...")
            save_data_locally(price_data)
            print("STATUS: SUCCESS - Stock market calculations completed successfully.")
        else:
            print("STATUS: FAILED - Pricing records returned completely empty data arrays.")
            
    except Exception as e:
        print(f"\nSTATUS: FAILED - Market extraction routine failed: {e}")

    print("\n====================================")
    print("PRICE COLLECTOR ISOLATION TEST COMPLETE")
    print("====================================")

if __name__ == "__main__":
    run_price_collector_test()