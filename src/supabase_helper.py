import os
import json
from pathlib import Path
from dotenv import load_dotenv
import httpx
from urllib.parse import urlparse
from datetime import datetime

load_dotenv()

URL: str = os.getenv("SUPABASE_URL")
KEY: str = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
NEWS_TABLE: str = os.getenv("SUPABASE_NEWS_TABLE", "financial_news")
STOCKS_TABLE: str = os.getenv("SUPABASE_STOCKS_TABLE", "stock_prices")

def insert_json_to_table(local_file_path, table_name):
    """Reads local JSON data, reshapes it to match database columns, and upserts rows."""
    if not URL or not KEY:
        print("Supabase configuration missing from environment.")
        return False

    local_path = Path(local_file_path).resolve()
    if not local_path.exists():
        print(f"Local file not found: {local_file_path}")
        return False
    
    # Extract base URL to bypass PostgREST proxy routing quirks
    parsed_url = urlparse(URL)
    base_url = f"{parsed_url.scheme}://{parsed_url.netloc}"
    
    # PostgREST handles conflicts by appending an explicit resolution query parameter to the URL
    if table_name == NEWS_TABLE:
        endpoint = f"{base_url}/rest/v1/{table_name}?on_conflict=link"
    else:
        endpoint = f"{base_url}/rest/v1/{table_name}"

    headers = {
        "Authorization": f"Bearer {KEY}",
        "apiKey": KEY,
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates"  # Tells Supabase to overwrite fields on conflict
    }

    try:
        with open(local_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        if isinstance(data, dict):
            data = [data]

        # ---------------------------------------------------------
        # DATABASE SCHEMA ALIGNMENT LAYER
        # ---------------------------------------------------------
        # Phase 1: Financial News Table Realignment
        if table_name == NEWS_TABLE:
            # Detect source context based on file name if not already in JSON
            inferred_source = "CafeF" if "CafeF" in local_path.name else "VnEconomy"
            
            for row in data:
                # 1. Map 'published' to 'published_at'
                if "published" in row:
                    row["published_at"] = row.pop("published")
                
                # 2. Map 'url' to 'link' if scraper outputs it as url
                if "url" in row:
                    row["link"] = row.pop("url")
                
                # 3. Handle 'source' if it doesn't exist explicitly in your row data
                if "source" not in row:
                    row["source"] = inferred_source
                
                # 4. Strip keys not present in the friend's schema cache
                allowed_news_columns = {"source", "title", "link", "published_at", "summary"}
                for key in list(row.keys()):
                    if key not in allowed_news_columns:
                        row.pop(key)

        # Phase 2: Stock Prices Table Realignment
        elif table_name == STOCKS_TABLE:
            today_str = datetime.now().strftime("%Y-%m-%d")
            for row in data:
                if "close" in row:
                    row["price"] = row.pop("close")
                if "change" in row:
                    row["percentage_change"] = row.pop("change")
                if "collected_date" not in row:
                    row["collected_date"] = today_str
                    
                allowed_stock_columns = {"ticker", "price", "percentage_change", "collected_date"}
                for key in list(row.keys()):
                    if key not in allowed_stock_columns:
                        row.pop(key)
        # ---------------------------------------------------------

        response = httpx.post(endpoint, headers=headers, json=data)
        
        if response.status_code in [200, 201]:
            print(f"Database Insert Successful into table '{table_name}'")
            return True
        
        print(f"Database Insertion Rejected (HTTP {response.status_code}): {response.text}")
        return False
    except Exception as e:
        print(f"Network error updating Supabase table: {e}")
        return False