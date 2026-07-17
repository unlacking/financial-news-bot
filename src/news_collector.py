from datetime import datetime, timezone, timedelta
import feedparser
import json
import httpx
import email.utils
import os
import re
import logging
from dotenv import load_dotenv

# Resolve absolute path of the project directory to load the .env file safely
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

    logging.info(f"Starting automated financial news scraping (Timeframe: {timeframe}, Max per source: {news_amount})...")
    logging.info(f"Filtering articles published after: {min_allowed_time.strftime('%Y-%m-%d %H:%M:%S')}")

    # Set up HTTP headers to mimic a standard browser request for better compatibility with RSS feeds
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    with httpx.Client(timeout=8.0, follow_redirects=True, headers=headers) as client:
        for source_name, url in rss_sources.items():
            if not url:
                logging.warning(f"Environment variable for {source_name} is not set!")
                continue
            
            try:
                # Download RSS feed content using httpx with proper error handling
                response = client.get(url)
                if response.status_code != 200:
                    logging.warning(f"{source_name} returned status code {response.status_code} (Maintenance?)")
                    continue
                
                # Parse the RSS feed content using feedparser
                feed = feedparser.parse(response.text)
                
            except httpx.RequestError as req_err:
                # Catch network-related errors and log them without crashing the entire scraping process
                logging.error(f"Error: Connection failed for {source_name}: {req_err}")
                continue
            except Exception as e:
                logging.error(f"Error parsing feed from {source_name}: {e}")
                continue

            # Check if the feed has valid entries; if not, log a warning and skip to the next source
            if not getattr(feed, 'entries', None):
                logging.warning(f"Warning: RSS entries empty or invalid for {source_name}")
                continue

            # Iterate through feed entries and filter based on time and uniqueness
            current_news_count = 0
            for entry in feed.entries: 
                # Stop processing if we have already collected the maximum allowed articles for this source
                if current_news_count >= news_amount:
                    break

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
                    continue

                # Check time and uniqueness conditions
                if article_time_vn >= min_allowed_time and article_link not in link_got:
                    raw_summary = getattr(entry, 'summary', '') or getattr(entry, 'description', '')
                    summary_clean = clean_html(raw_summary)
                    news.append({
                        "source": source_name,
                        "title": getattr(entry, 'title', 'Unknown Title'),
                        "link": article_link,
                        "published_at": article_time_vn.strftime("%Y-%m-%d %H:%M:%S"), 
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
        logging.info("\nNo new articles to save within the selected timeframe.")
        return

    # Resolve path to anchor the data folder inside the core project architecture
    base_dir = os.path.join(current_script_dir, "news_data")
    
    timezone_vn = timezone(timedelta(hours=7))
    date_str = datetime.now(timezone_vn).strftime("%Y-%m-%d")
    
    # Build storage subdirectory dynamically if missing
    os.makedirs(base_dir, exist_ok=True)
    logging.info(f"Target system base directory anchored at: {base_dir}")
    
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
        
        # If the archival track exists, read it to index unique hyperlinks already committed to disk
        if os.path.exists(full_file_path):
            try:
                with open(full_file_path, "r", encoding="utf-8") as f:
                    existing_articles = json.load(f)
                    existing_links = {art["link"] for art in existing_articles if "link" in art}
                logging.info(f"Loaded {len(existing_articles)} existing articles from {filename}")
            except (json.JSONDecodeError, IOError) as read_err:
                logging.warning(f"Warning: Could not parse existing file {filename}. Initializing fresh. Error: {read_err}")
        
        # Compare incoming data against indexed disk record array, filtering out collisions
        new_additions_count = 0
        for article in incoming_articles:
            if article["link"] not in existing_links:
                existing_articles.append(article)
                existing_links.add(article["link"])
                new_additions_count += 1
        
        # Commit changes to data tracking manifest only if brand new items were verified
        if new_additions_count > 0:
            try:
                with open(full_file_path, "w", encoding="utf-8") as f:
                    json.dump(existing_articles, f, ensure_ascii=False, indent=4)
                logging.info(f"Successfully updated {filename}: Added {new_additions_count} new articles. Total: {len(existing_articles)}.")
            except IOError as write_err:
                logging.error(f"Error writing updates to file {filename}: {write_err}")
        else:
            logging.info(f"No new unique articles found for {publisher}. File {filename} is up to date.")
            
    logging.info("\nIncremental update cycle complete.")
