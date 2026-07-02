print("Check")

from datetime import datetime, timezone, timedelta
import feedparser
import json
import email.utils
import os
from dotenv import load_dotenv

load_dotenv()

def Scrape():
    # 1. Configure RSS sources and parameters (VnEconomy and CafeF)
    rss_sources = {
        "CafeF": os.getenv("URL_CAFEF"),
        "VnEconomy": os.getenv("URL_VNECONOMY")
    }
    news = []
    link_got = set()  # Set to help check and eliminate duplicate articles
    news_amount = 5  # Maximum number of articles to fetch per source
    timezone_vn = timezone(timedelta(hours=7))
    today_vn = datetime.now(timezone_vn).date()

    print("Starting automated financial news scraping...")

    # 2. Loop through each RSS source in the configuration
    for source_name, rss_url in rss_sources.items():
        feed = feedparser.parse(rss_url, agent="Mozilla/5.0")
        
        # Safety check to see if the feed has valid entries
        if not getattr(feed, 'entries', None):
            print(f"⚠ Warning: Cannot connect or RSS link for {source_name} is broken/empty!")
            continue

        current_news_count = 0
        for entry in feed.entries: 
            # Stop if the required number of articles for this source is met
            if current_news_count >= news_amount:
                break

            # Safely fetch the link and published_raw to prevent missing fields in RSS
            article_link = getattr(entry, 'link', '').strip()
            published_raw = getattr(entry, 'published', getattr(entry, 'pubDate', None))

            # Skip the article if it lacks a valid link (junk data)
            if not article_link:
                continue

            try:
                # If there is no publication date, treat it as invalid for today's filter
                if not published_raw:
                    raise ValueError
                article_time = email.utils.parsedate_to_datetime(published_raw)
                article_time_vn = article_time.astimezone(timezone_vn)
                pub_date_vn = article_time_vn.date()
            except (ValueError, TypeError):
                # Do not crash the program when encountering an article with an invalid date format
                continue

            # Must be published today AND the article link has not been fetched yet
            if pub_date_vn == today_vn and article_link not in link_got:
                summary_clean = getattr(entry, 'summary', '')
                
                # Handle cutting redundant HTML strings from RSS feed
                if "/>" in summary_clean:
                    summary_clean = summary_clean.split("/>")[-1].replace("</a>", "").strip()
                elif "</a>" in summary_clean:
                    summary_clean = summary_clean.split("</a>")[-1].strip()
                
                news.append({
                    "source": source_name,
                    "title": getattr(entry, 'title', 'Unknown Title'),
                    "link": article_link,
                    "published": pub_date_vn.isoformat(), # Convert to String "YYYY-MM-DD" for JSON
                    "summary": summary_clean
                })
                
                link_got.add(article_link) # Mark this article link as fetched
                current_news_count += 1
                
    return news

# 3. Run the main function and save results to a JSON file
if __name__ == "__main__":
    news_list = Scrape()

    # Safety check before printing and saving
    if news_list:
        # Convert list/dict data into a JSON string format (Day 2 technique)
        json_string = json.dumps(news_list, ensure_ascii=False, indent=4)
        
        with open("tin_tuc_cuoi_ngay.json", "w", encoding="utf-8") as f:
            f.write(json_string)
        print("💾 Successfully saved today's product to file: tin_tuc_cuoi_ngay.json")

        print(f"\nCollected a total of {len(news_list)} new articles.\n")
        print("================ NEWS ARTICLES LIST ================")
        
        for index, article in enumerate(news_list, start=1):
            print(f"[{index}] Source: {article['source']}")
            print(f"Title: {article['title']}")
            print(f"Published Date: {article['published']}")
            print(f"Summary: {article['summary']}")
            print(f"Link: {article['link']}")
            print("-" * 50) 
            
    else:
        print("\nNo new articles found for today.")