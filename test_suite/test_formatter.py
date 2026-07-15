# test_suite/test_formatter.py
import os
import sys

# Resolve the absolute path of the project root directory (one level up from this file)
# and append it to sys.path before importing local custom modules.
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from src.formatter import format_alert, format_digest

def run_formatter_test():
    print("====================================")
    print("STARTING FORMATTER ISOLATION TEST")
    print("====================================\n")

    # 1. Mock Data Setup
    mock_prices = [
        {"ticker": "FPT", "percentage_change": 4.52, "price": 135000.0},
        {"ticker": "HPG", "percentage_change": -3.15, "price": 28500.0},
        {"ticker": "VNM", "percentage_change": 0.50, "price": 67000.0}
    ]

    mock_news_items = [
        {
            "title": "FPT announces record high quarterly profits",
            "source": "CafeF"
        },
        {
            "title": "HPG facing structural margin squeeze",
            "source": "VnEconomy"
        },
        {
            "title": "State investigation launched into major real estate developer",
            "source": "Vietstock"
        }
    ]

    mock_gemini_analyses = [
        {
            "summary": "FPT reported exceptional profit margins driven by global IT services expansion.",
            "sentiment": "Positive",
            "importance_score": 4,
            "related_tickers": ["FPT"]
        },
        {
            "summary": "Steel producer HPG faces dynamic margin pressures due to rising raw input costs.",
            "sentiment": "Negative",
            "importance_score": 3,
            "related_tickers": ["HPG"]
        },
        {
            "summary": "Regulatory bodies initiate a formal investigation into compliance issues.",
            "sentiment": "Negative",
            "importance_score": 5,
            "related_tickers": []
        }
    ]

    # 2. Test Section: format_alert() for Price Movements
    print("--- TESTING PRICE ALERT FORMATTING ---")
    price_alert_msg = format_alert(
        alert_type="PRICE_ALERT",
        ticker="FPT",
        detail="Stock FPT is SURGING: +4.52% (Current Price: 135,000 VND)"
    )
    print(price_alert_msg)
    print("\n")

    # 3. Test Section: format_alert() for News Incidents
    print("--- TESTING CRITICAL NEWS ALERT FORMATTING ---")
    news_alert_msg = format_alert(
        alert_type="NEWS_ALERT",
        ticker="MARKET",
        reason="Negative sentiment with high severity (Score: 5/5); Contains sensitive keywords: investigation",
        detail="State investigation launched into major real estate developer. Summary: Regulatory bodies initiate a formal investigation."
    )
    print(news_alert_msg)
    print("\n")

    # 4. Test Section: format_digest() for Daily Newsletter (with Chunking validation)
    print("--- TESTING DAILY DIGEST NEWSLETTER CHUNKING ---")
    digest_chunks = format_digest(
        price_data=mock_prices,
        news_items=mock_news_items,
        gemini_analyses=mock_gemini_analyses
    )

    print(f"Total chunks generated: {len(digest_chunks)}")
    for i, chunk in enumerate(digest_chunks, 1):
        print(f"\n--- Chunk {i} (Length: {len(chunk)} characters) ---")
        print(chunk)
        
    print("\n====================================")
    print("FORMATTER ISOLATION TEST COMPLETE")
    print("====================================")

if __name__ == "__main__":
    run_formatter_test()