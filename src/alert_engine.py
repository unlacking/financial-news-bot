import os
import re
from typing import List, Dict, Any
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Fetch sensitive keywords from .env
env_keywords = os.getenv("SENSITIVE_KEYWORDS", "")
if env_keywords:
    # Split by comma and strip whitespaces from each keyword
    SENSITIVE_KEYWORDS_LIST = [word.strip().lower() for word in env_keywords.split(",") if word.strip()]
else:
    # Fallback list if not configured in .env
    SENSITIVE_KEYWORDS_LIST = [
        "điều tra", "bắt giam", "vỡ nợ", "phá sản", 
        "thanh tra", "vi phạm", "bán giải chấp", "đình chỉ", 
        "thua lỗ", "khủng hoảng", "vấn đề pháp lý"
    ]

# Alert thresholds configuration
ALERT_CONFIG = {
    "price": {
        "change_threshold_pct": 3.0,  # Alert if price movement exceeds ±3% in a session
    },
    "news": {
        "min_importance_score": 4,     # Alert if importance score is >= 4 (Very Important / Critical)
        "trigger_sentiments": ["Negative"], # Trigger emergency alert on negative sentiment
        "sensitive_keywords": SENSITIVE_KEYWORDS_LIST
    }
}

def analyze_price_alerts(price_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Rule 1: Check for price fluctuations exceeding the configured threshold (e.g., ±3%).
    """
    alerts = []
    threshold = ALERT_CONFIG["price"]["change_threshold_pct"]
    
    for item in price_data:
        ticker = item.get("ticker")
        pct_change = item.get("percentage_change", 0.0)
        price = item.get("price", 0.0)
        
        if abs(pct_change) >= threshold:
            direction = "SURGING" if pct_change > 0 else "PLUMMETING"
            alerts.append({
                "type": "PRICE_ALERT",
                "ticker": ticker,
                "message": f"Stock {ticker} is {direction}: {pct_change:+.2f}% (Current Price: {price:,} VND)"
            })
    return alerts


def analyze_news_alerts(news_items: List[Dict[str, Any]], gemini_analyses: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Rule 2: News with negative sentiment and high importance score.
    Rule 3: Occurrence of sensitive keywords in the title or summary.
    """
    alerts = []
    sensitive_words = ALERT_CONFIG["news"]["sensitive_keywords"]
    min_score = ALERT_CONFIG["news"]["min_importance_score"]
    trigger_sentiments = ALERT_CONFIG["news"]["trigger_sentiments"]

    # Map Gemini analysis results back to the original news articles via their index
    for idx, news in enumerate(news_items):
        if idx >= len(gemini_analyses):
            break
            
        analysis = gemini_analyses[idx]
        title = news.get("title", "")
        summary = analysis.get("summary", "")
        sentiment = analysis.get("sentiment", "Neutral")
        importance = analysis.get("importance_score", 3)
        tickers = analysis.get("related_tickers", [])
        
        # Rule 2 Check: Negative & High Importance
        is_critical_sentiment = (sentiment in trigger_sentiments) and (importance >= min_score)
        
        # Rule 3 Check: Sensitive Keywords
        found_keywords = []
        full_text_to_check = f"{title} {summary}".lower()
        for word in sensitive_words:
            if re.search(r'\b' + re.escape(word) + r'\b', full_text_to_check):
                found_keywords.append(word)
                
        # Trigger alert if either Rule 2 or Rule 3 is satisfied
        if is_critical_sentiment or found_keywords:
            reasons = []
            if is_critical_sentiment:
                reasons.append(f"Negative sentiment ({sentiment}) with high severity (Score: {importance}/5)")
            if found_keywords:
                reasons.append(f"Contains sensitive keywords: {', '.join(found_keywords)}")
                
            ticker_str = f" related to {', '.join(tickers)}" if tickers else ""
            alerts.append({
                "type": "NEWS_ALERT",
                "tickers": tickers,
                "message": (
                    f"**EMERGENCY NEWS ALERT**{ticker_str}\n"
                    f"**Title:** {title}\n"
                    f"**Reason:** {'; '.join(reasons)}\n"
                    f"**Summary:** {summary}"
                )
            })
            
    return alerts


def generate_daily_newsletter(price_data: List[Dict[str, Any]], news_items: List[Dict[str, Any]]) -> str:
    """
    Generate a non-emergency daily market summary report (Daily Newsletter).
    """
    # Extract top 3 gainers and losers for a quick market snapshot
    sorted_prices = sorted(price_data, key=lambda x: x.get("percentage_change", 0.0), reverse=True)
    top_gainers = [f"{x['ticker']} ({x['percentage_change']:+.2f}%)" for x in sorted_prices[:3] if x['percentage_change'] > 0]
    top_losers = [f"{x['ticker']} ({x['percentage_change']:+.2f}%)" for x in sorted_prices[-3:] if x['percentage_change'] < 0]
    
    # Aggregate news headlines
    news_titles = [f"• {item.get('title')} ({item.get('source')})" for item in news_items[:5]]
    news_section = "\n".join(news_titles) if news_titles else "No new articles recorded today."

    newsletter = (
        f"**DAILY FINANCIAL NEWSLETTER**\n"
        f"---------------------------------\n"
        f"**Top Gainers:** {', '.join(top_gainers) if top_gainers else 'None'}\n"
        f"**Top Losers:** {', '.join(top_losers) if top_losers else 'None'}\n\n"
        f"**Featured News Headlines:**\n"
        f"{news_section}\n"
        f"---------------------------------\n"
        f"Have a great evening and happy investing!"
    )
    return newsletter