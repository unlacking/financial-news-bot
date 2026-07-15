from typing import List, Dict, Any
from datetime import datetime

def format_alert(alert_type: str, ticker: str, detail: str, reason: str = "") -> str:
    """
    Format emergency alerts (price variations or critical news).
    Uses professional ASCII layouts instead of emojis.
    """
    separator = "=" * 35
    # Generate an explicit timestamp at the time of formatting
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    if alert_type == "PRICE_ALERT":
        message = (
            f"{separator}\n"
            f"MARKET ALERT: {ticker}\n"
            f"{separator}\n"
            f"Detail: {detail}\n"
            f"Timestamp: {current_time}\n"
            f"{separator}"
        )
    elif alert_type == "NEWS_ALERT":
        message = (
            f"{separator}\n"
            f"CRITICAL NEWS ALERT: {ticker}\n"
            f"{separator}\n"
            f"Reason: {reason}\n\n"
            f"Content: {detail}\n"
            f"Timestamp: {current_time}\n"
            f"{separator}"
        )
    else:
        message = (
            f"{separator}\n"
            f"SYSTEM ALERT: {ticker}\n"
            f"{separator}\n"
            f"{detail}\n"
            f"Timestamp: {current_time}\n"
            f"{separator}"
        )
    return message


def format_digest(price_data: List[Dict[str, Any]], news_items: List[Dict[str, Any]], gemini_analyses: List[Dict[str, Any]]) -> List[str]:
    """
    Formats the daily aggregate newsletter.
    Guarantees that no block exceeds the 4096-character limit by splitting into chunks.
    """
    chunks = []
    current_chunk = []
    
    # 1. Header Section
    header = (
        "DAILY FINANCIAL DIGEST\n"
        "====================================\n"
    )
    current_chunk.append(header)
    
    # 2. Market Prices Section
    if price_data:
        sorted_prices = sorted(price_data, key=lambda x: x.get("percentage_change", 0.0), reverse=True)
        gainers = [f"+ {x['ticker']}: {x['percentage_change']:+.2f}%" for x in sorted_prices if x['percentage_change'] > 0][:3]
        losers = [f"- {x['ticker']}: {x['percentage_change']:+.2f}%" for x in sorted_prices if x['percentage_change'] < 0][-3:]
        
        price_section = "MARKET SNAPSHOT\n"
        price_section += "Top Gainers:\n" + ("\n".join(gainers) if gainers else "  None") + "\n"
        price_section += "Top Losers:\n" + ("\n".join(losers) if losers else "  None") + "\n"
        price_section += "------------------------------------\n"
        current_chunk.append(price_section)
        
    # 3. News & Analysis Section
    if news_items:
        current_chunk.append("FEATURED ANALYSIS & NEWS\n")
        
        for idx, news in enumerate(news_items):
            analysis = gemini_analyses[idx] if idx < len(gemini_analyses) else {}
            title = news.get("title", "No Title")
            source = news.get("source", "Unknown")
            summary = analysis.get("summary", "No summary available.")
            sentiment = analysis.get("sentiment", "Neutral")
            score = analysis.get("importance_score", 3)
            
            item_text = (
                f"Title: {title} ({source})\n"
                f"Sentiment: {sentiment} | Importance: {score}/5\n"
                f"Summary: {summary}\n"
                f"------------------------------------\n"
            )
            
            # Check length before appending to prevent breaking the 4096 limit
            temp_message = "".join(current_chunk) + item_text
            if len(temp_message) > 4000:
                # Close current chunk
                current_chunk.append("\n(Continued in next message...)")
                chunks.append("".join(current_chunk))
                # Start new chunk
                current_chunk = ["DAILY FINANCIAL DIGEST (CONTINUED)\n====================================\n", item_text]
            else:
                current_chunk.append(item_text)
                
    # Footer Section
    current_chunk.append("End of Report.")
    chunks.append("".join(current_chunk))
    
    return chunks