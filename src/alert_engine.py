"""
RISK EVALUATION & ALERT ANALYSIS ENGINE
---------------------------------------
This module acts as Phase 3 of the pipeline. It evaluates scraped market prices
and Gemini AI sentiment metrics against configurable volatility thresholds and keyword
watchlists to trigger instant emergency alerts for Telegram/Email delivery.
"""

import os
import re
import logging
from typing import List, Dict, Any
from dotenv import load_dotenv

# ==============================================================================
# 1. ENVIRONMENT & THRESHOLD CONFIGURATION
# ==============================================================================
try:
    load_dotenv()
except Exception as env_err:
    logging.warning(f"Non-fatal warning: Failed to map .env path in alert_engine: {env_err}")

# Fetch sensitive trigger keywords dynamically from .env with fallback defaults
env_keywords = os.getenv("SENSITIVE_KEYWORDS", "")
if env_keywords:
    SENSITIVE_KEYWORDS_LIST = [word.strip().lower() for word in env_keywords.split(",") if word.strip()]
else:
    SENSITIVE_KEYWORDS_LIST = [
        "điều tra", "bắt giam", "vỡ nợ", "phá sản", 
        "thanh tra", "vi phạm", "bán giải chấp", "đình chỉ", 
        "thua lỗ", "khủng hoảng", "vấn đề pháp lý"
    ]

# Alert criteria rules matrix
ALERT_CONFIG = {
    "price": {
        "change_threshold_pct": 3.0,  # Trigger alert if price shift exceeds +/- 3.0%
    },
    "news": {
        "min_importance_score": 4,     # Trigger alert if importance score is >= 4
        "trigger_sentiments": ["Negative"], # Trigger emergency alert on negative sentiment
        "sensitive_keywords": SENSITIVE_KEYWORDS_LIST
    }
}


# ==============================================================================
# 2. PRICE VOLATILITY EVALUATION ENGINE
# ==============================================================================
def analyze_price_alerts(price_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Evaluates price records against configured percentage shift limits.

    :param price_data: List of dictionary objects containing ticker price metrics.
    :return: List of structured PRICE_ALERT dictionaries.
    """
    if not price_data or not isinstance(price_data, list):
        logging.info("No price dataset provided to analyze_price_alerts. Evaluation bypassed.")
        return []

    alerts = []
    threshold = ALERT_CONFIG["price"]["change_threshold_pct"]
    
    for item in price_data:
        if not isinstance(item, dict):
            continue

        try:
            ticker = item.get("ticker", "UNKNOWN").strip().upper()
            
            # Safe numeric type casting to protect against invalid string values
            raw_pct = item.get("percentage_change", 0.0)
            pct_change = float(raw_pct) if raw_pct is not None else 0.0
            
            raw_price = item.get("price", 0.0)
            price = float(raw_price) if raw_price is not None else 0.0
            
            # Rule 1 Check: Evaluates whether percentage shift breaches the threshold limit
            if abs(pct_change) >= threshold:
                direction = "SURGING" if pct_change > 0 else "PLUMMETING"
                alerts.append({
                    "type": "PRICE_ALERT",
                    "ticker": ticker,
                    "message": f"Stock {ticker} is {direction}: {pct_change:+.2f}% (Current Price: {price:,.0f} VND)"
                })

        except (ValueError, TypeError) as cast_err:
            logging.warning(f"Failed to process numeric data during price alert evaluation for ticker '{item.get('ticker')}': {cast_err}")
            continue
        except Exception as e:
            logging.error(f"Unexpected error analyzing price alert item: {e}")
            continue

    return alerts


# ==============================================================================
# 3. NEWS SENTIMENT & KEYWORD EVALUATION ENGINE
# ==============================================================================
def analyze_news_alerts(news_items: List[Dict[str, Any]], gemini_analyses: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Evaluates raw news items and Gemini AI outputs for negative sentiment,
    high severity scores, and sensitive keywords.

    :param news_items: List of raw news dictionaries harvested from RSS feeds.
    :param gemini_analyses: List of structured AI analysis outputs from Gemini.
    :return: List of structured NEWS_ALERT dictionaries.
    """
    if not news_items or not gemini_analyses:
        logging.info("Insufficient news or AI analysis objects supplied. Alert scan bypassed.")
        return []

    alerts = []
    sensitive_words = ALERT_CONFIG["news"]["sensitive_keywords"]
    min_score = ALERT_CONFIG["news"]["min_importance_score"]
    trigger_sentiments = ALERT_CONFIG["news"]["trigger_sentiments"]

    # Match raw news records to Gemini outputs by list index
    for idx, news in enumerate(news_items):
        if idx >= len(gemini_analyses):
            break
            
        try:
            analysis = gemini_analyses[idx]
            if not isinstance(analysis, dict):
                continue

            title = news.get("title", "Untitled Article").strip()
            summary = analysis.get("summary", "").strip()
            sentiment = analysis.get("sentiment", "Neutral").strip()
            
            # Safe casting for importance score
            try:
                importance = int(analysis.get("importance_score", 3))
            except (ValueError, TypeError):
                importance = 3

            tickers = analysis.get("related_tickers", [])
            if not isinstance(tickers, list):
                tickers = []

            # Rule 2 Check: Negative Sentiment + High Severity Score
            is_critical_sentiment = (sentiment in trigger_sentiments) and (importance >= min_score)
            
            # Rule 3 Check: Sensitive Keywords Regex Search
            found_keywords = []
            full_text_to_check = f"{title} {summary}".lower()
            for word in sensitive_words:
                try:
                    if re.search(r'\b' + re.escape(word) + r'\b', full_text_to_check):
                        found_keywords.append(word)
                except Exception as regex_err:
                    logging.warning(f"Regex matching error for keyword '{word}': {regex_err}")

            # Trigger alert if either Rule 2 or Rule 3 conditions are satisfied
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

        except Exception as e:
            logging.error(f"Error evaluating news alert item at index {idx}: {e}")
            continue
            
    return alerts


# ==============================================================================
# 4. DAILY NEWSLETTER COMPILER UTILITY
# ==============================================================================
def generate_daily_newsletter(price_data: List[Dict[str, Any]], news_items: List[Dict[str, Any]]) -> str:
    """
    Compiles daily market summary metrics into a structured plaintext newsletter block.

    :param price_data: List of dictionary objects containing stock prices.
    :param news_items: List of raw news article dictionaries.
    :return: Formatted multi-line string report.
    """
    try:
        # Safe sorting of price movements for top gainers and losers
        valid_prices = [
            x for x in price_data 
            if isinstance(x, dict) and isinstance(x.get("percentage_change"), (int, float))
        ]
        
        sorted_prices = sorted(valid_prices, key=lambda x: x.get("percentage_change", 0.0), reverse=True)
        
        top_gainers = [
            f"{x.get('ticker', 'N/A')} ({x.get('percentage_change', 0.0):+.2f}%)" 
            for x in sorted_prices[:3] if x.get('percentage_change', 0.0) > 0
        ]
        
        top_losers = [
            f"{x.get('ticker', 'N/A')} ({x.get('percentage_change', 0.0):+.2f}%)" 
            for x in sorted_prices[-3:] if x.get('percentage_change', 0.0) < 0
        ]
        
        # Aggregate news headlines safely
        news_titles = []
        if isinstance(news_items, list):
            for item in news_items[:5]:
                if isinstance(item, dict):
                    title = item.get('title', 'Untitled')
                    source = item.get('source', 'Unknown')
                    news_titles.append(f"• {title} ({source})")

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

    except Exception as e:
        logging.error(f"Failed to generate daily newsletter block: {e}")
        return "**DAILY FINANCIAL NEWSLETTER**\n\nFailed to compile newsletter content due to data processing error."