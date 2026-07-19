"""
FINANCIAL NEWS COLLECTOR & RSS INGESTION ENGINE
----------------------------------------------
This module serves as the primary Extract-Transform (ET) component for Phase 1 of the pipeline.
It connects to external financial news RSS endpoints, cleans HTML markup from raw feeds,
normalizes publication timestamps into ICT (UTC+7 / Vietnam Timezone), and commits unique
articles incrementally to daily JSON file caches on disk.
"""

from datetime import datetime, timezone, timedelta
import feedparser
import json
import httpx
import email.utils
import os
import re
import logging
from dotenv import load_dotenv

# ==============================================================================
# 1. ENVIRONMENT & PATH RESOLUTION
# ==============================================================================
# Resolves the absolute path to the parent directory to safely locate the local .env configuration file
try:
    current_script_dir = os.path.dirname(os.path.abspath(__file__))
    env_path = os.path.join(current_script_dir, "..", ".env")
    load_dotenv(dotenv_path=env_path)
except Exception as env_load_err:
    print(f"CRITICAL WARNING: Failed to resolve .env configuration file path in news_collector: {env_load_err}")


# ==============================================================================
# 2. HTML CLEANING & TEXT NORMALIZATION UTILITY
# ==============================================================================
def clean_html(raw_html: str) -> str:
    """
    Strips hyperlinked anchor tags, embedded HTML tags, and trailing whitespace
    from raw RSS description strings to yield plain text for downstream NLP processing.
    """
    if not raw_html or not isinstance(raw_html, str):
        return ""
    
    try:
        # Step 1: Strip out anchor tags and their internal text/links entirely
        clean_text = re.sub(r'<a[^>]*>.*?</a>', '', raw_html, flags=re.DOTALL)
        # Step 2: Strip all remaining XML/HTML markup tags (e.g., <p>, <br>, <div>)
        clean_text = re.sub(r'<[^>]+>', '', clean_text)
        # Step 3: Normalize space sequences and trim surrounding whitespace
        return clean_text.strip()
    except Exception as regex_err:
        logging.warning(f"Failed to strip HTML markup cleanly from news summary: {regex_err}")
        return str(raw_html).strip()


# ==============================================================================
# 3. RSS FEED HARVESTING ENGINE
# ==============================================================================
def collect_news(news_amount: int = 5, timeframe: timedelta = timedelta(days=1)) -> list:
    """
    Connects to external RSS feeds, extracts recent articles within a designated lookback window,
    normalizes localized publication dates, and returns structured dictionaries.

    :param news_amount: Maximum number of articles to extract per individual publisher endpoint.
    :param timeframe: Lookback timedelta threshold (defaults to 24 hours).
    :return: List of unique dictionary records formatted for pipeline consumption.
    """
    # Fetch RSS source URLs dynamically from environment variables
    rss_sources = {
        "CafeF": os.getenv("URL_CAFEF"),
        "VnEconomy": os.getenv("URL_VNECONOMY"),
        "Vietstock": os.getenv("URL_VIETSTOCK")
    }
    
    news = []
    link_got = set()  # In-memory deduplication set tracking links seen during the current scraping pass
    
    # Define standardized Vietnam ICT Timezone (UTC+7)
    timezone_vn = timezone(timedelta(hours=7))
    
    try:
        current_time_vn = datetime.now(timezone_vn)
        min_allowed_time = current_time_vn - timeframe
    except Exception as time_calc_err:
        logging.error(f"Failed to calculate target evaluation timezone window: {time_calc_err}")
        min_allowed_time = datetime.now(timezone.utc) - timeframe

    logging.info(f"Starting financial news scraping cycle (Window: {timeframe}, Max per source: {news_amount})...")
    logging.info(f"Filtering articles published after: {min_allowed_time.strftime('%Y-%m-%d %H:%M:%S')} ICT")

    # Spoof browser request headers to prevent HTTP 403 Forbidden responses from RSS endpoints
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    # Initialize an HTTPX client with a strict 8-second timeout to prevent dead connection hangs
    try:
        with httpx.Client(timeout=8.0, follow_redirects=True, headers=headers) as client:
            for source_name, url in rss_sources.items():
                if not url:
                    logging.warning(f"Skipping RSS collection for '{source_name}': URL environment variable is not defined.")
                    continue
                
                try:
                    # Request raw XML payload from external news source
                    response = client.get(url)
                    if response.status_code != 200:
                        logging.warning(f"Source '{source_name}' returned unexpected HTTP status code {response.status_code}. Endpoint skipped.")
                        continue
                    
                    # Parse the raw RSS string into structured feed objects
                    feed = feedparser.parse(response.text)
                    
                except httpx.RequestError as req_err:
                    logging.error(f"Network transport failure connecting to source '{source_name}': {req_err}")
                    continue
                except Exception as parse_err:
                    logging.error(f"Failed to parse raw RSS feed content from source '{source_name}': {parse_err}")
                    continue

                # Verify feed structure validity
                if not getattr(feed, 'entries', None):
                    logging.warning(f"RSS payload received from source '{source_name}' contains zero entries or invalid XML structures.")
                    continue

                # Iterate through extracted feed items and apply time/uniqueness filters
                current_news_count = 0
                for entry in feed.entries: 
                    # Stop processing entries once target article count is reached for this source
                    if current_news_count >= news_amount:
                        break

                    try:
                        article_link = getattr(entry, 'link', '').strip()
                        published_raw = getattr(entry, 'published', getattr(entry, 'pubDate', None))

                        if not article_link:
                            continue

                        # Parse localized RFC-2822 date strings into standard Python datetime objects
                        if not published_raw:
                            # Fallback: Assign current time if date tag is omitted in XML feed
                            article_time_vn = datetime.now(timezone_vn)
                        else:
                            parsed_tuple = email.utils.parsedate_to_datetime(published_raw)
                            article_time_vn = parsed_tuple.astimezone(timezone_vn)

                    except Exception as entry_parse_err:
                        logging.warning(f"Failed to parse metadata for article entry from source '{source_name}': {entry_parse_err}")
                        continue

                    # Filter Step: Retain article if within lookback window AND not previously seen in current cycle
                    if article_time_vn >= min_allowed_time and article_link not in link_got:
                        try:
                            raw_summary = getattr(entry, 'summary', '') or getattr(entry, 'description', '')
                            summary_clean = clean_html(raw_summary)
                            title_clean = getattr(entry, 'title', 'Untitled Context String').strip()

                            news.append({
                                "source": source_name,
                                "title": title_clean,
                                "link": article_link,
                                "published_at": article_time_vn.strftime("%Y-%m-%d %H:%M:%S"), 
                                "summary": summary_clean
                            })
                            
                            link_got.add(article_link)
                            current_news_count += 1
                        except Exception as build_err:
                            logging.error(f"Failed to assemble article record dictionary: {build_err}")
                            continue

    except Exception as client_err:
        logging.error(f"Fatal HTTP client session failure during news collection phase: {client_err}")
        return []

    return news


# ==============================================================================
# 4. LOCAL DISK PERSISTENCE ENGINE
# ==============================================================================
def save_news_locally(news_list: list) -> None:
    """
    Groups inbound scraped records by publisher and incrementally writes
    unseen articles into localized daily JSON cache files on disk.

    :param news_list: List of article dictionaries returned by collect_news().
    """
    if not news_list or not isinstance(news_list, list):
        logging.info("No news article records provided for disk caching.")
        return

    try:
        # Determine target path for local file storage: 'src/news_data/'
        base_dir = os.path.join(current_script_dir, "news_data")
        
        timezone_vn = timezone(timedelta(hours=7))
        date_str = datetime.now(timezone_vn).strftime("%Y-%m-%d")
        
        # Ensure target storage subdirectory exists on disk
        os.makedirs(base_dir, exist_ok=True)
    except Exception as dir_init_err:
        logging.error(f"Failed to initialize news storage directory structure: {dir_init_err}")
        return
    
    # Group articles by their publisher source name
    grouped_news = {}
    for article in news_list:
        try:
            publisher = article.get("source", "Unknown_Source")
            grouped_news.setdefault(publisher, []).append(article)
        except Exception as group_err:
            logging.warning(f"Skipping malformed article record during grouping: {group_err}")

    # Process each publisher group and perform incremental file updates
    for publisher, incoming_articles in grouped_news.items():
        filename = f"{publisher}_{date_str}.json"
        full_file_path = os.path.join(base_dir, filename)
        
        existing_articles = []
        existing_links = set()
        
        # Read existing JSON file from disk to load known article links
        if os.path.exists(full_file_path):
            try:
                with open(full_file_path, "r", encoding="utf-8") as f:
                    file_contents = json.load(f)
                    if isinstance(file_contents, list):
                        existing_articles = file_contents
                    elif isinstance(file_contents, dict):
                        existing_articles = [file_contents]
                    
                    existing_links = {art["link"] for art in existing_articles if isinstance(art, dict) and "link" in art}
                logging.info(f"Loaded {len(existing_articles)} existing articles from disk cache: '{filename}'")
            except (json.JSONDecodeError, IOError) as read_err:
                logging.warning(f"Could not parse existing cache file '{filename}'. Initializing new record set. Error: {read_err}")
                existing_articles = []
                existing_links = set()

        # Append incoming articles if their URL is not in the existing set
        new_additions_count = 0
        for article in incoming_articles:
            try:
                article_link = article.get("link")
                if article_link and article_link not in existing_links:
                    existing_articles.append(article)
                    existing_links.add(article_link)
                    new_additions_count += 1
            except Exception as append_err:
                logging.warning(f"Failed to validate article URL during disk cache merge: {append_err}")

        # Write merged record array back to disk if new items were added
        if new_additions_count > 0:
            try:
                with open(full_file_path, "w", encoding="utf-8") as f:
                    json.dump(existing_articles, f, ensure_ascii=False, indent=4)
                logging.info(f"Successfully updated '{filename}': Added {new_additions_count} new records (Total: {len(existing_articles)}).")
            except IOError as write_err:
                logging.error(f"Disk write operation failed for target cache file '{filename}': {write_err}")
        else:
            logging.info(f"No new unique articles found for publisher '{publisher}'. Cache file '{filename}' remains current.")
            
    logging.info("Incremental disk storage update cycle completed successfully.")