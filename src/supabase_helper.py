import os
import json
import time
from pathlib import Path
from dotenv import load_dotenv
import httpx
from urllib.parse import urlparse
from datetime import datetime
from ai_processor import analyze_article

load_dotenv()

URL: str = os.getenv("SUPABASE_URL")
KEY: str = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
NEWS_TABLE: str = os.getenv("SUPABASE_NEWS_TABLE", "financial_news")
STOCKS_TABLE: str = os.getenv("SUPABASE_STOCKS_TABLE", "stock_prices")
GEMINI_TABLE: str = os.getenv("SUPABASE_GEMINI_TABLE", "gemini_responses")

def process_news_batch(data: list, title_field: str, body_field: str) -> list:
    """
    Processes articles in explicit sub-batches to guarantee we stay 
    safely beneath the 15 Requests Per Minute (RPM) threshold.
    """
    gemini_rows_to_insert = []
    # Set sub-batch size safely below the 15 RPM ceiling
    BATCH_SIZE = 10  
    COOLDOWN_PERIOD = 65  # Seconds to let the RPM window fully reset
    
    for i in range(0, len(data), BATCH_SIZE):
        batch = data[i:i + BATCH_SIZE]
        print(f"Processing sub-batch {i // BATCH_SIZE + 1} ({len(batch)} articles)...")
        
        for row in batch:
            title = row.get(title_field, "Untitled")
            body = row.get(body_field, "")
            
            # (Your existing extraction & analyze_article logic runs here)
            analysis = analyze_article(title, body)
            
            gemini_rows_to_insert.append(analysis)
            
            # Short intra-batch pacing to not look like a sudden burst
            time.sleep(1.5) 
        
        # If there are more articles left after this batch, force a hard reset sleep
        if i + BATCH_SIZE < len(data):
            print(f"Approaching RPM ceiling. Enforcement cooling down for {COOLDOWN_PERIOD}s...")
            time.sleep(COOLDOWN_PERIOD)
            
    return gemini_rows_to_insert

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
        # Phase 1: Dual-Table Execution via Native HTTP Rest Calls
        # Enforce entry if it matches either the config variable or the string name
        if table_name == NEWS_TABLE or table_name == "financial_news":
            
            print(f"DEBUG: Successfully entered Phase 1 processing loop for table: {table_name}")
            
            news_rows_to_insert, gemini_rows_to_insert = process_news_batch(data, local_path.name)

            # 3. Execute HTTP Posts sequentially using the native httpx client engine
            if table_name == NEWS_TABLE:
                print(f"DEBUG: NEWS_TABLE value is '{NEWS_TABLE}'")
                print(f"DEBUG: GEMINI_TABLE value is '{GEMINI_TABLE}'")
            
            from src.ai_processor import analyze_article

            try:
                news_endpoint = f"{base_url}/rest/v1/{NEWS_TABLE}?on_conflict=link"
                gemini_endpoint = f"{base_url}/rest/v1/{GEMINI_TABLE}"

                if news_rows_to_insert:
                    news_res = httpx.post(news_endpoint, headers=headers, json=news_rows_to_insert)
                    if news_res.status_code in [200, 201]:
                        print(f"Successfully uploaded {len(news_rows_to_insert)} records to '{NEWS_TABLE}'.")
                    else:
                        print(f"'{NEWS_TABLE}' upload rejected (HTTP {news_res.status_code}): {news_res.text}")
                
                if gemini_rows_to_insert:
                    gemini_res = httpx.post(gemini_endpoint, headers=headers, json=gemini_rows_to_insert)
                    if gemini_res.status_code in [200, 201]:
                        print(f"Successfully uploaded {len(gemini_rows_to_insert)} records to '{GEMINI_TABLE}'.")
                    else:
                        print(f"'{GEMINI_TABLE}' upload rejected (HTTP {gemini_res.status_code}): {gemini_res.text}")
                    
            except Exception as upload_err:
                print(f"Supabase REST endpoint execution failed: {upload_err}")
                
            # Intercept execution chain so it doesn't fall through to the global endpoint fallback
            return True

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

        # Global fallback endpoint delivery loop for stock datasets
        response = httpx.post(endpoint, headers=headers, json=data)
        
        if response.status_code in [200, 201]:
            print(f"Database Insert Successful into table '{table_name}'")
            return True
        
        print(f"Database Insertion Rejected (HTTP {response.status_code}): {response.text}")
        return False
    except Exception as e:
        print(f"Network error updating Supabase table: {e}")
        return False