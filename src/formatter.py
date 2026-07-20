"""
MESSAGE & REPORT FORMATTING ENGINE
----------------------------------
This module formats emergency alerts and aggregate market digests for distribution.
It formats structured text outputs and splits long newsletter digests into blocks 
conforming strictly to Telegram's 4096-character limit.
"""

import logging
from typing import List, Dict, Any
from datetime import datetime

# ==============================================================================
# 1. EMERGENCY ALERT FORMATTING UTILITY
# ==============================================================================
def format_alert(alert_type: str, ticker: str, detail: str, reason: str = "") -> str:
    """
    Formats emergency price movement or critical news alerts using standardized ASCII borders.

    :param alert_type: Type identifier ('PRICE_ALERT', 'NEWS_ALERT', or fallback).
    :param ticker: Stock ticker symbol or comma-separated tickers.
    :param detail: Detailed alert description or article content.
    :param reason: Specific condition or keyword trigger reason.
    :return: Formatted ASCII text block.
    """
    separator = "=" * 35
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    clean_ticker = str(ticker).strip().upper() if ticker else "GENERAL"

    if alert_type == "PRICE_ALERT":
        message = (
            f"{separator}\n"
            f"MARKET ALERT: {clean_ticker}\n"
            f"{separator}\n"
            f"Detail: {detail}\n"
            f"Timestamp: {current_time}\n"
            f"{separator}"
        )
    elif alert_type == "NEWS_ALERT":
        message = (
            f"{separator}\n"
            f"CRITICAL NEWS ALERT: {clean_ticker}\n"
            f"{separator}\n"
            f"Reason: {reason}\n\n"
            f"Content: {detail}\n"
            f"Timestamp: {current_time}\n"
            f"{separator}"
        )
    else:
        message = (
            f"{separator}\n"
            f"SYSTEM ALERT: {clean_ticker}\n"
            f"{separator}\n"
            f"{detail}\n"
            f"Timestamp: {current_time}\n"
            f"{separator}"
        )
    return message


# ==============================================================================
# 2. DAILY DIGEST COMPILER & CHUNK SPLITTER
# ==============================================================================
def format_digest(price_data: List[Dict[str, Any]], news_items: List[Dict[str, Any]], gemini_analyses: List[Dict[str, Any]]) -> List[str]:
    """
    Formats the daily market summary newsletter into message chunks.
    Guarantees no individual string exceeds Telegram's 4096-character API limit.

    :param price_data: List of dictionary objects containing ticker price metrics.
    :param news_items: List of raw news article dictionaries.
    :param gemini_analyses: List of structured AI analysis outputs from Gemini.
    :return: List of string chunks safely beneath character thresholds.
    """
    chunks = []
    current_chunk = []
    
    # 1. Header Section
    header = (
        "DAILY FINANCIAL DIGEST\n"
        "====================================\n"
    )
    current_chunk.append(header)
    
    # 2. Market Snapshot Section
    if price_data and isinstance(price_data, list):
        try:
            valid_prices = [
                x for x in price_data 
                if isinstance(x, dict) and isinstance(x.get("percentage_change"), (int, float))
            ]
            
            sorted_prices = sorted(valid_prices, key=lambda x: x.get("percentage_change", 0.0), reverse=True)
            gainers = [f"+ {x.get('ticker', 'N/A')}: {x.get('percentage_change', 0.0):+.2f}%" for x in sorted_prices if x.get('percentage_change', 0.0) > 0][:3]
            losers = [f"- {x.get('ticker', 'N/A')}: {x.get('percentage_change', 0.0):+.2f}%" for x in sorted_prices if x.get('percentage_change', 0.0) < 0][-3:]
            
            price_section = "MARKET SNAPSHOT\n"
            price_section += "Top Gainers:\n" + ("\n".join(gainers) if gainers else "  None") + "\n"
            price_section += "Top Losers:\n" + ("\n".join(losers) if losers else "  None") + "\n"
            price_section += "------------------------------------\n"
            current_chunk.append(price_section)
        except Exception as price_err:
            logging.error(f"Failed to format market snapshot block in digest: {price_err}")

    # 3. News & AI Analysis Section
    if news_items and isinstance(news_items, list):
        current_chunk.append("FEATURED ANALYSIS & NEWS\n")
        
        # Map analyses by article URL to prevent index-mismatch and title/summary shifting
        analysis_map = {}
        if gemini_analyses and isinstance(gemini_analyses, list):
            for item in gemini_analyses:
                if isinstance(item, dict):
                    link_key = str(item.get("link") or item.get("url") or "").strip()
                    if link_key:
                        analysis_map[link_key] = item

        for news in news_items:
            if not isinstance(news, dict):
                continue

            try:
                title = news.get("title", "Untitled Article").strip()
                source = news.get("source", "Unknown Source").strip()
                news_link = str(news.get("link") or news.get("url") or "").strip()

                # Perform exact URL lookup instead of index matching
                analysis = analysis_map.get(news_link, {})
                
                try:
                    score = int(analysis.get("importance_score", 3))
                except (ValueError, TypeError):
                    score = 3

                # Filter out non-financial noise / low-importance articles (Importance < 2)
                if score < 2:
                    continue

                summary = analysis.get("summary", "No AI summary available.").strip()
                sentiment = analysis.get("sentiment", "Neutral").strip()
                
                item_text = (
                    f"Title: {title} ({source})\n"
                    f"Sentiment: {sentiment} | Importance: {score}/5\n"
                    f"Summary: {summary}\n"
                    f"------------------------------------\n"
                )
                
                # Check character length before appending (Safe threshold set at 3800 chars)
                temp_message = "".join(current_chunk) + item_text
                if len(temp_message) > 3800:
                    current_chunk.append("\n(Continued in next message...)")
                    chunks.append("".join(current_chunk))
                    current_chunk = [
                        "DAILY FINANCIAL DIGEST (CONTINUED)\n====================================\n", 
                        item_text
                    ]
                else:
                    current_chunk.append(item_text)

            except Exception as item_err:
                logging.error(f"Error formatting digest news item '{news.get('title')}': {item_err}")
                continue

    # 4. Footer Section
    current_chunk.append("End of Report.")
    chunks.append("".join(current_chunk))
    
    return chunks