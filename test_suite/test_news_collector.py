# test_suite/test_news_collector.py
import os
import sys
from datetime import timedelta

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from src.news_collector import collect_news, save_news_locally

def run_news_collector_test():
    print("====================================")
    print("STARTING NEWS COLLECTOR ISOLATION TEST")
    print("====================================\n")

    # Fetch 2 news items per source over the last 24 hours
    print("Attempting to pull RSS feed streams...")
    try:
        articles = collect_news(news_amount=2, timeframe=timedelta(days=1))
        
        print(f"\nSuccessfully harvested {len(articles)} articles.")
        if articles:
            print("\nSample Sample Metadata (First Entry):")
            sample = articles[0]
            print(f"Title: {sample.get('title')}")
            print(f"Source: {sample.get('source')}")
            print(f"Link: {sample.get('link')}")
            print(f"Published Date: {sample.get('published')}")
            
            # Test local disk persistence serialization
            print("\nTesting local data caching layer...")
            save_news_locally(articles)
            print("STATUS: SUCCESS - News scraped and archived successfully.")
        else:
            print("STATUS: PASSED WITH WARNING - Connection succeeded, but no articles were found within the 24h timeframe.")
            
    except Exception as e:
        print(f"\nSTATUS: FAILED - News extraction pipeline threw an error: {e}")

    print("\n====================================")
    print("NEWS COLLECTOR ISOLATION TEST COMPLETE")
    print("====================================")

if __name__ == "__main__":
    run_news_collector_test()