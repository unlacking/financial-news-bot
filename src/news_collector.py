from datetime import datetime, timezone, timedelta
import feedparser
import json
import email.utils
import os
import re
from dotenv import load_dotenv

# 1. Resolve absolute path of the project directory to load the .env file safely
current_script_dir = os.path.dirname(os.path.abspath(__file__))
env_path = os.path.join(current_script_dir, ".env")
load_dotenv(dotenv_path=env_path)

def clean_html(raw_html):
    if not raw_html:
        return ""
    clean_text = re.sub(r'<a[^>]*>.*?</a>', '', raw_html)
    clean_text = re.sub(r'<[^>]+>', '', clean_text)
    return clean_text.strip()

def collect_news(news_amount=5, timeframe=timedelta(days=1)):
    """
    Scrapes financial news from configured RSS feeds.
    :param news_amount: Maximum number of articles to fetch per source.
    :param timeframe: Lookback window timedelta to filter recent articles.
    :return: List of structured unique article dictionaries.
    """
    # Configure RSS sources using environment variables loaded from .env
    rss_sources = {
        "CafeF": os.getenv("URL_CAFEF"),
        "VnEconomy": os.getenv("URL_VNECONOMY"),
        "Vietstock": os.getenv("URL_VIETSTOCK")
    }
    news = []
    link_got = set()  # In-memory set to filter duplicate articles within the same scraping cycle
    
    timezone_vn = timezone(timedelta(hours=7))
    current_time_vn = datetime.now(timezone_vn)
    
    # Calculate the minimum boundary threshold for allowed articles
    min_allowed_time = current_time_vn - timeframe

    print(f"Starting automated financial news scraping (Timeframe: {timeframe}, Max per source: {news_amount})...")
    print(f"Filtering articles published after: {min_allowed_time.strftime('%Y-%m-%d %H:%M:%S')}")

    # Iterate through each configured news publisher feed
    for source_name, rss_url in rss_sources.items():
        if not rss_url:
            print(f"Warning: Environment variable for {source_name} is not set!")
            continue

        # Spoof a realistic web browser header to bypass basic anti-bot firewall restrictions
        custom_headers = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        feed = feedparser.parse(rss_url, agent=custom_headers)
        
        # Guard clause to check the validity of the returned RSS data payload
        if not getattr(feed, 'entries', None):
            print(f"Warning: Cannot connect or RSS link for {source_name} is broken/empty!")
            continue

        current_news_count = 0
        for entry in feed.entries: 
            # Terminate loop early if target quota is met for the current source
            if current_news_count >= news_amount:
                break

            # Safely extract metadata endpoints
            article_link = getattr(entry, 'link', '').strip()
            published_raw = getattr(entry, 'published', getattr(entry, 'pubDate', None))

            if not article_link:
                continue

            try:
                if not published_raw:
                    raise ValueError
                article_time = email.utils.parsedate_to_datetime(published_raw)
                article_time_vn = article_time.astimezone(timezone_vn)
            except (ValueError, TypeError):
                # Gracefully skip parsing errors without crashing the entire script runtime
                continue

            # Core validation: check if entry falls inside target timeframe and avoids current local set duplication
            if article_time_vn >= min_allowed_time and article_link not in link_got:
                # Strip out junk CDATA or dangling anchor tags often bundled into RSS summaries
                raw_summary = getattr(entry, 'summary', '')
                summary_clean = clean_html(raw_summary)
                news.append({
                    "source": source_name,
                    "title": getattr(entry, 'title', 'Unknown Title'),
                    "link": article_link,
                    "published": article_time_vn.strftime("%Y-%m-%d %H:%M:%S"), 
                    "summary": summary_clean
                })
                
                link_got.add(article_link)
                current_news_count += 1
                
    return news


def save_news_locally(news_list):
    """
    Groups inbound scraped items by publisher and commits incremental patch 
    matrix operations to individual daily JSON files inside a local data folder.
    """
    if not news_list:
        print("\nNo new articles to save within the selected timeframe.")
        return

    # Resolve path to anchor the data folder inside the core project architecture
    base_dir = os.path.join(current_script_dir, "news_data")
    
    timezone_vn = timezone(timedelta(hours=7))
    date_str = datetime.now(timezone_vn).strftime("%Y-%m-%d")
    
    # Build storage subdirectory dynamically if missing
    os.makedirs(base_dir, exist_ok=True)
    print(f"Target system base directory anchored at: {base_dir}")
    
    # Group inbound scraped items by their primary publisher tag
    grouped_news = {}
    for article in news_list:
        publisher = article["source"]
        grouped_news.setdefault(publisher, []).append(article)

    # Execute incremental patch matrix operations per publisher file
    for publisher, incoming_articles in grouped_news.items():
        # Unified daily target naming schema: news_data/Publisher_YYYY-MM-DD.json
        filename = f"{publisher}_{date_str}.json"
        full_file_path = os.path.join(base_dir, filename)
        
        existing_articles = []
        existing_links = set()
        
        # STEP 1: If the archival track exists, read it to index unique hyperlinks already committed to disk
        if os.path.exists(full_file_path):
            try:
                with open(full_file_path, "r", encoding="utf-8") as f:
                    existing_articles = json.load(f)
                    existing_links = {art["link"] for art in existing_articles if "link" in art}
                print(f"Loaded {len(existing_articles)} existing articles from {filename}")
            except (json.JSONDecodeError, IOError) as read_err:
                print(f"Warning: Could not parse existing file {filename}. Initializing fresh. Error: {read_err}")
        
        # STEP 2: Compare incoming data against indexed disk record array, filtering out collisions
        new_additions_count = 0
        for article in incoming_articles:
            if article["link"] not in existing_links:
                existing_articles.append(article)
                existing_links.add(article["link"])
                new_additions_count += 1
        
        # STEP 3: Commit changes to data tracking manifest only if brand new items were verified
        if new_additions_count > 0:
            try:
                with open(full_file_path, "w", encoding="utf-8") as f:
                    json.dump(existing_articles, f, ensure_ascii=False, indent=4)
                print(f"Successfully updated {filename}: Added {new_additions_count} new articles. Total: {len(existing_articles)}.")
            except IOError as write_err:
                print(f"Error writing updates to file {filename}: {write_err}")
        else:
            print(f"No new unique articles found for {publisher}. File {filename} is up to date.")
            
    print("\nIncremental update cycle complete.")


# 3. Execution Runtime Layer & Disk I/O Aggregator 
if __name__ == "__main__":
    # Test execution parameters to fetch articles over the past 24 hours
    test_timeframe = timedelta(days=1)
    test_amount = 1

    news_list = collect_news(news_amount=test_amount, timeframe=test_timeframe)
    save_news_locally(news_list)