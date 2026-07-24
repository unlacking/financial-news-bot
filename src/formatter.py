from typing import List, Dict, Any
from datetime import datetime
import logging

def format_alert(
    alert_type: str, 
    ticker: str, 
    title: str = "", 
    summary: str = "", 
    reason: str = ""
) -> str:
    """
    Format emergency alerts (price variations or critical news).
    Uses professional ASCII layouts instead of emojis.
    """
    separator = "=" * 35
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    if alert_type == "PRICE_ALERT":
        summary_line = f"Detail: {summary}\n" if summary else ""
        message = (
            f"{separator}\n"
            f"MARKET ALERT: {ticker}\n"
            f"{separator}\n"
            f"{summary_line}"
            f"Timestamp: {current_time}\n"
            f"{separator}"
        )
    elif alert_type == "NEWS_ALERT":
        reason_line = f"Reason: {reason}\n" if reason else ""
        title_line = f"Title: {title}\n" if title else ""
        summary_line = f"Summary: {summary}\n" if summary else ""
        
        message = (
            f"{separator}\n"
            f"CRITICAL NEWS ALERT: {ticker}\n"
            f"{separator}\n"
            f"{reason_line}"
            f"{title_line}"
            f"{summary_line}"
            f"Timestamp: {current_time}\n"
            f"{separator}"
        )
    else:
        summary_line = f"Detail: {summary}\n" if summary else ""
        message = (
            f"{separator}\n"
            f"SYSTEM ALERT: {ticker}\n"
            f"{separator}\n"
            f"{summary_line}"
            f"Timestamp: {current_time}\n"
            f"{separator}"
        )
    return message


def format_digest(
    price_data: List[Dict[str, Any]], 
    news_items: List[Dict[str, Any]], 
    gemini_analyses: List[Dict[str, Any]],
    market_macro: Dict[str, Any] = None
) -> List[str]:
    """
    Formats the pre-market Morning Financial Briefing.
    Guarantees that no block exceeds the 4096-character limit by splitting into chunks.
    """
    chunks = []
    current_chunk = []
    
    # 1. Header Section
    current_date = datetime.now().strftime("%d/%m/%Y")
    header = (
        f"MORNING FINANCIAL BRIEF - {current_date}\n"
        "====================================\n\n"
    )
    current_chunk.append(header)

    # 2. Previous Session Macro Summary
    if market_macro and isinstance(market_macro, dict):
        vnindex = market_macro.get("vnindex", "N/A")
        change_pts = market_macro.get("change_points", 0.0)
        liquidity = market_macro.get("liquidity", "N/A")
        foreign_flow = market_macro.get("foreign_flow", "N/A")
        
        macro_text = (
            "1. PREVIOUS SESSION RECAP\n"
            f"• VN-Index Close: {vnindex} ({change_pts:+.2f} pts)\n"
            f"• Market Liquidity: {liquidity}\n"
            f"• Foreign Investor Flow: {foreign_flow}\n"
            "------------------------------------\n"
        )
        current_chunk.append(macro_text)
    
    # 3. Market Prices / Stock Movers Section
    if price_data and isinstance(price_data, list):
        try:
            valid_prices = [
                x for x in price_data 
                if isinstance(x, dict) and isinstance(x.get("percentage_change"), (int, float))
            ]
            
            sorted_prices = sorted(valid_prices, key=lambda x: x.get("percentage_change", 0.0), reverse=True)
            gainers = [f"+ {x.get('ticker', 'N/A')}: {x.get('percentage_change', 0.0):+.2f}%" for x in sorted_prices if x.get('percentage_change', 0.0) > 0][:3]
            losers = [f"- {x.get('ticker', 'N/A')}: {x.get('percentage_change', 0.0):+.2f}%" for x in sorted_prices if x.get('percentage_change', 0.0) < 0][-3:]
            
            price_section = "Top Previous Gainers:\n" + ("\n".join(gainers) if gainers else "  None") + "\n"
            price_section += "Top Previous Losers:\n" + ("\n".join(losers) if losers else "  None") + "\n"
            price_section += "------------------------------------\n"
            current_chunk.append(price_section)
        except Exception as price_err:
            logging.error(f"Failed to format price section: {price_err}")

    # 4. Market Sentiment & Sector Focus Synthesis
    sector_summary = {}
    sentiments_count = {"Positive": 0, "Negative": 0, "Neutral": 0}

    if gemini_analyses and isinstance(gemini_analyses, list):
        for item in gemini_analyses:
            if isinstance(item, dict):
                senti = str(item.get("sentiment", "Neutral")).capitalize()
                if senti in sentiments_count:
                    sentiments_count[senti] += 1
                
                sectors = item.get("affected_sectors", [])
                if isinstance(sectors, list):
                    for sec in sectors:
                        sector_summary[sec] = sector_summary.get(sec, 0) + 1

    total_news = sum(sentiments_count.values()) or 1
    pos_pct = (sentiments_count["Positive"] / total_news) * 100
    neg_pct = (sentiments_count["Negative"] / total_news) * 100

    if pos_pct > 60:
        overall_bias = "Bullish / Positive Sentiment Accumulation"
    elif neg_pct > 60:
        overall_bias = "Bearish / Caution Advised"
    else:
        overall_bias = "Neutral / Mixed Divergence"

    current_chunk.append("2. PRE-MARKET OUTLOOK\n")
    current_chunk.append(f"• Sentiment Bias: {overall_bias}\n")
    if sector_summary:
        top_sectors = sorted(sector_summary.items(), key=lambda x: x[1], reverse=True)[:3]
        sec_str = ", ".join([f"{sec}" for sec, _ in top_sectors])
        current_chunk.append(f"• Key Sectors to Watch: {sec_str}\n")
    else:
        current_chunk.append("• Key Sectors to Watch: Banking, Real Estate, Securities\n")
    current_chunk.append("------------------------------------\n")

    # 5. Overnight Featured News & Analysis
    if news_items and isinstance(news_items, list):
        current_chunk.append("3. OVERNIGHT NEWS & ANALYSIS\n")
        
        analysis_map = {}
        if gemini_analyses and isinstance(gemini_analyses, list):
            for item in gemini_analyses:
                if isinstance(item, dict):
                    key = str(item.get("link") or item.get("url") or "").strip()
                    if key:
                        analysis_map[key] = item
        
        for idx, news in enumerate(news_items):
            if not isinstance(news, dict):
                continue

            news_link = str(news.get("link") or news.get("url") or "").strip()
            
            analysis = analysis_map.get(news_link)
            if not analysis and idx < len(gemini_analyses):
                analysis = gemini_analyses[idx]
            if not isinstance(analysis, dict):
                analysis = {}

            title = news.get("title", "Untitled Article").strip()
            source = news.get("source", "Unknown").strip()
            summary = analysis.get("summary", "No summary available.").strip()
            sentiment = analysis.get("sentiment", "Neutral").strip()
            
            try:
                score = int(analysis.get("importance_score", 3))
            except (ValueError, TypeError):
                score = 3
            
            # Skip noise
            if score < 2:
                continue

            item_text = (
                f"Title: {title} ({source})\n"
                f"Sentiment: {sentiment} | Importance: {score}/5\n"
                f"Summary: {summary}\n"
                f"------------------------------------\n"
            )
            
            # Check length safety (3800 char buffer)
            temp_message = "".join(current_chunk) + item_text
            if len(temp_message) > 3800:
                current_chunk.append("\n(Continued in next message...)")
                chunks.append("".join(current_chunk))
                current_chunk = ["MORNING FINANCIAL BRIEF (CONTINUED)\n====================================\n", item_text]
            else:
                current_chunk.append(item_text)
                
    # Footer
    current_chunk.append("Have a successful trading session!")
    chunks.append("".join(current_chunk))
    
    return chunks