print("Check")

from datetime import datetime, timezone, timedelta
import feedparser
import json
import email.utils
import os
import re
from dotenv import load_dotenv

load_dotenv()

def collect_news(news_amount=5, timeframe=timedelta(days=1)):
    """
    Scrapes financial news from RSS sources.
    :param news_amount: Maximum number of articles to fetch per source.
    :param timeframe: A timedelta object defining the lookback window from the current time.
                      Defaults to 1 day (last 24 hours).
    :return: A list of dictionaries containing filtered news articles.
    """
    # 1. Configure RSS sources and parameters (VnEconomy and CafeF)
    rss_sources = {
        "CafeF": os.getenv("URL_CAFEF"),
        "VnEconomy": os.getenv("URL_VNECONOMY")
    }
    news = []
    link_got = set()  # Set to help check and eliminate duplicate articles
    
    timezone_vn = timezone(timedelta(hours=7))
    current_time_vn = datetime.now(timezone_vn)
    
    # Calculate the threshold timestamp based on the provided timeframe parameter
    min_allowed_time = current_time_vn - timeframe

    print(f"Starting automated financial news scraping (Timeframe: {timeframe}, Max per source: {news_amount})...")
    print(f"Filtering articles published after: {min_allowed_time.strftime('%Y-%m-%d %H:%M:%S')}")

    # 2. Loop through each RSS source in the configuration
    for source_name, rss_url in rss_sources.items():
        if not rss_url:
            print(f"⚠ Warning: Environment variable for {source_name} is not set!")
            continue

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
                if not published_raw:
                    raise ValueError
                article_time = email.utils.parsedate_to_datetime(published_raw)
                article_time_vn = article_time.astimezone(timezone_vn)
            except (ValueError, TypeError):
                # Do not crash the program when encountering an article with an invalid date format
                continue

            # Verify the article falls within the timeframe window and is not duplicated
            if article_time_vn >= min_allowed_time and article_link not in link_got:
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
                    # Save exact timestamp string format for precise filtering
                    "published": article_time_vn.strftime("%Y-%m-%d %H:%M:%S"), 
                    "summary": summary_clean
                })
                
                link_got.add(article_link)  # Mark this article link as fetched
                current_news_count += 1
                
    return news

# 3. Run the main function and isolate persistent dynamic file generation
if __name__ == "__main__":
    # Test execution parameters
    test_timeframe = timedelta(days=1)
    test_amount = 5
    news_list = collect_news(news_amount=test_amount, timeframe=test_timeframe)

    if news_list:
        base_dir = "news_data"
        
        # Get current date in Vietnam to group files by date
        timezone_vn = timezone(timedelta(hours=7))
        date_str = datetime.now(timezone_vn).strftime("%Y-%m-%d")
        
        # Automatically create base directory if it doesn't exist
        os.makedirs(base_dir, exist_ok=True)
        
        # Group news by publisher to update individual publisher files
        # Structured as: {"CafeF": [articles...], "VnEconomy": [articles...]}
        grouped_news = {}
        for article in news_list:
            publisher = article["source"]
            grouped_news.setdefault(publisher, []).append(article)

        # Process each publisher's feed incrementally
        for publisher, incoming_articles in grouped_news.items():
            # Target file path format: news_data/Publisher_YYYY-MM-DD.json
            filename = f"{publisher}_{date_str}.json"
            full_file_path = os.path.join(base_dir, filename)
            
            existing_articles = []
            existing_links = set()
            
            # STEP 1: If the file already exists, load existing data to prevent duplicates
            if os.path.exists(full_file_path):
                try:
                    with open(full_file_path, "r", encoding="utf-8") as f:
                        existing_articles = json.load(f)
                        # Track unique links already archived on disk
                        existing_links = {art["link"] for art in existing_articles if "link" in art}
                    print(f"Loaded {len(existing_articles)} existing articles from {filename}")
                except (json.JSONDecodeError, IOError) as read_err:
                    print(f"⚠ Warning: Could not parse existing file {filename}. Initializing fresh. Error: {read_err}")
            
            # STEP 2: Compare and filter out articles that are already inside the file
            new_additions_count = 0
            for article in incoming_articles:
                if article["link"] not in existing_links:
                    existing_articles.append(article)
                    existing_links.add(article["link"])
                    new_additions_count += 1
            
            # STEP 3: Write the updated unified list back to the file if there are new items
            if new_additions_count > 0:
                try:
                    with open(full_file_path, "w", encoding="utf-8") as f:
                        json.dump(existing_articles, f, ensure_ascii=False, indent=4)
                    print(f"Successfully updated {filename}: Added {new_additions_count} new articles. Total: {len(existing_articles)}.")
                except IOError as write_err:
                    print(f"⚠ Error writing updates to file {filename}: {write_err}")
            else:
                print(f"-> No new unique articles found for {publisher}. File {filename} is up to date.")
                
        print("\nIncremental update cycle complete.")
    else:
        print("\nNo new articles found within the selected timeframe.")