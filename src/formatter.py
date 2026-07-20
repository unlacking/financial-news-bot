"""
MESSAGE & REPORT FORMATTING ENGINE
----------------------------------
Formats morning and EOD market digests conforming strictly to Telegram guidelines.
"""

import logging
from typing import List, Dict, Any
from datetime import datetime

def format_digest(
    price_data: List[Dict[str, Any]], 
    news_items: List[Dict[str, Any]], 
    gemini_analyses: List[Dict[str, Any]],
    market_macro: Dict[str, Any] = None
) -> List[str]:
    """
    Formats the morning market report to satisfy all 4 boss requirements:
      1. Previous session recap (Prices + Liquidity + Foreign Flow)
      2. General market evaluation
      3. Upcoming trend assessment
      4. Affected industry sectors
    """
    chunks = []
    current_chunk = []
    
    # --------------------------------------------------------------------------
    # HEADER SECTION
    # --------------------------------------------------------------------------
    current_time = datetime.now().strftime("%d/%m/%Y")
    header = (
        f"MORNING FINANCIAL DIGEST - {current_time}\n"
        "====================================\n\n"
    )
    current_chunk.append(header)

    # --------------------------------------------------------------------------
    # REQUIREMENT 1: PREVIOUS SESSION RECAP (Những gì đã diễn ra)
    # --------------------------------------------------------------------------
    current_chunk.append("1. PREVIOUS SESSION RECAP\n")
    
    # Macro Index / Liquidity details if available
    if market_macro and isinstance(market_macro, dict):
        vnindex = market_macro.get("vnindex", "N/A")
        change_pts = market_macro.get("change_points", 0.0)
        liquidity = market_macro.get("liquidity", "N/A")
        foreign_flow = market_macro.get("foreign_flow", "N/A")
        
        current_chunk.append(
            f"• VN-Index: {vnindex} ({change_pts:+.2f} pts)\n"
            f"• Market Liquidity: {liquidity}\n"
            f"• Foreign Investor Flow: {foreign_flow}\n\n"
        )

    if price_data and isinstance(price_data, list):
        try:
            valid_prices = [
                x for x in price_data 
                if isinstance(x, dict) and isinstance(x.get("percentage_change"), (int, float))
            ]
            
            sorted_prices = sorted(valid_prices, key=lambda x: x.get("percentage_change", 0.0), reverse=True)
            gainers = [f"+ {x.get('ticker', 'N/A')}: {x.get('percentage_change', 0.0):+.2f}%" for x in sorted_prices if x.get('percentage_change', 0.0) > 0][:3]
            losers = [f"- {x.get('ticker', 'N/A')}: {x.get('percentage_change', 0.0):+.2f}%" for x in sorted_prices if x.get('percentage_change', 0.0) < 0][-3:]
            
            current_chunk.append("Top Gainers:\n" + ("\n".join(gainers) if gainers else "  None") + "\n")
            current_chunk.append("Top Losers:\n" + ("\n".join(losers) if losers else "  None") + "\n")
            current_chunk.append("------------------------------------\n")
        except Exception as price_err:
            logging.error(f"Failed to format price section: {price_err}")

    # --------------------------------------------------------------------------
    # MAP AI ANALYSES BY URL (Prevents list mismatch bugs)
    # --------------------------------------------------------------------------
    analysis_map = {}
    sector_summary = {}
    sentiments_count = {"Positive": 0, "Negative": 0, "Neutral": 0}

    if gemini_analyses and isinstance(gemini_analyses, list):
        for item in gemini_analyses:
            if isinstance(item, dict):
                link_key = str(item.get("link") or item.get("url") or "").strip()
                if link_key:
                    analysis_map[link_key] = item
                
                # Collect sentiment balance
                senti = str(item.get("sentiment", "Neutral")).capitalize()
                if senti in sentiments_count:
                    sentiments_count[senti] += 1
                
                # Collect sector impacts
                sectors = item.get("affected_sectors", [])
                if isinstance(sectors, list):
                    for sec in sectors:
                        sector_summary[sec] = sector_summary.get(sec, 0) + 1

    # --------------------------------------------------------------------------
    # REQUIREMENT 2 & 3: MARKET EVALUATION & UPCOMING TRENDS (Nhận định & Xu hướng)
    # --------------------------------------------------------------------------
    current_chunk.append("2. MARKET EVALUATION & UPCOMING TREND\n")
    
    total_news = sum(sentiments_count.values()) or 1
    pos_pct = (sentiments_count["Positive"] / total_news) * 100
    neg_pct = (sentiments_count["Negative"] / total_news) * 100
    
    if pos_pct > 60:
        overall_bias = "Bullish / Positive Accumulation"
        trend_outlook = "Market expected to test upper resistance zones on selective capital inflows."
    elif neg_pct > 60:
        overall_bias = "Bearish / High Selling Pressure"
        trend_outlook = "Short-term consolidation or retesting lower support levels expected."
    else:
        overall_bias = "Neutral / Mixed Divergence"
        trend_outlook = "Sideways movement likely; high stock-picking selectivity required."

    current_chunk.append(f"• Overall Sentiment Bias: {overall_bias}\n")
    current_chunk.append(f"• Trend Outlook: {trend_outlook}\n")
    current_chunk.append("------------------------------------\n")

    # --------------------------------------------------------------------------
    # REQUIREMENT 4: AFFECTED SECTORS (Ngành nghề nhận tác động)
    # --------------------------------------------------------------------------
    current_chunk.append("3. SECTOR IMPACT ANALYSIS\n")
    if sector_summary:
        top_sectors = sorted(sector_summary.items(), key=lambda x: x[1], reverse=True)[:4]
        sec_str = ", ".join([f"{sec}" for sec, _ in top_sectors])
        current_chunk.append(f"• Key Sectors in Focus: {sec_str}\n")
    else:
        current_chunk.append("• Key Sectors in Focus: Banking, Real Estate, Securities\n")
    current_chunk.append("------------------------------------\n")

    # --------------------------------------------------------------------------
    # FEATURED NEWS BREAKDOWN
    # --------------------------------------------------------------------------
    if news_items and isinstance(news_items, list):
        current_chunk.append("4. FEATURED ANALYSIS & NEWS\n")
        
        for news in news_items:
            if not isinstance(news, dict):
                continue

            try:
                title = news.get("title", "Untitled Article").strip()
                source = news.get("source", "Unknown Source").strip()
                news_link = str(news.get("link") or news.get("url") or "").strip()

                analysis = analysis_map.get(news_link, {})
                
                try:
                    score = int(analysis.get("importance_score", 3))
                except (ValueError, TypeError):
                    score = 3

                # Filter out low importance noise
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
                
                # Check character length (Telegram limit buffer at 3800)
                temp_message = "".join(current_chunk) + item_text
                if len(temp_message) > 3800:
                    current_chunk.append("\n(Continued in next message...)")
                    chunks.append("".join(current_chunk))
                    current_chunk = [
                        "MORNING FINANCIAL DIGEST (CONTINUED)\n====================================\n", 
                        item_text
                    ]
                else:
                    current_chunk.append(item_text)

            except Exception as item_err:
                logging.error(f"Error formatting news item '{news.get('title')}': {item_err}")
                continue

    # Footer
    current_chunk.append("End of Report.")
    chunks.append("".join(current_chunk))
    
    return chunks