"""
SUPABASE CLOUD DATABASE INTERFACE & DATA PERSISTENCE LAYER
----------------------------------------------------------
This module handles all database communication with Supabase via direct HTTP REST calls.
It performs two core responsibilities:
  1. Reshapes and upserts localized JSON arrays into target cloud database tables.
  2. Provides read-only query utilities for interactive Telegram CLI bot handlers (/price, /news, /status).
"""

import os
import json
import logging
from pathlib import Path
from dotenv import load_dotenv
import httpx
from urllib.parse import urlparse
from datetime import datetime

# Import the batch processor from its new location in ai_processor
try:
    from src.ai_processor import process_news_batch
except ImportError as imp_err:
    logging.warning(f"Failed to import 'process_news_batch' from src.ai_processor: {imp_err}")

# ==============================================================================
# 1. ENVIRONMENT & SUPABASE CREDENTIAL CONFIGURATION
# ==============================================================================
try:
    load_dotenv()
except Exception as env_err:
    logging.warning(f"Non-fatal warning: Failed to map .env configuration in supabase_helper: {env_err}")

URL: str = os.getenv("SUPABASE_URL", "")
KEY: str = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
NEWS_TABLE: str = os.getenv("SUPABASE_NEWS_TABLE", "financial_news")
STOCKS_TABLE: str = os.getenv("SUPABASE_STOCKS_TABLE", "stock_prices")
GEMINI_TABLE: str = os.getenv("SUPABASE_GEMINI_TABLE", "gemini_responses")


# ==============================================================================
# 2. SCHEMA REALIGNMENT HELPERS
# ==============================================================================
def realign_gemini_payload(gemini_row: dict) -> dict:
    """
    Ensures all keys expected by Supabase gemini_responses table exist and are typed correctly.
    Prevents missing array key exceptions or null column errors during PostgREST upserts.
    """
    if not isinstance(gemini_row, dict):
        return {}
    clean_link = str(gemini_row.get("link") or gemini_row.get("url") or "").strip()
    return {
        "link": clean_link,
        "prompt_input": str(gemini_row.get("prompt_input", "")),
        "model_name": str(gemini_row.get("model_name", os.getenv("GEMINI_VERSION", "gemini-3.5-flash"))),
        "summary": str(gemini_row.get("summary", "")),
        "sentiment": str(gemini_row.get("sentiment", "errorDTBASE")),
        "related_tickers": gemini_row.get("related_tickers") if isinstance(gemini_row.get("related_tickers"), list) else [],
        "affected_sectors": gemini_row.get("affected_sectors") if isinstance(gemini_row.get("affected_sectors"), list) else [],
        "importance_score": int(gemini_row.get("importance_score", 3))
    }


# ==============================================================================
# 3. DATABASE SCHEMA REALIGNMENT & HTTP UPSERT ENGINE
# ==============================================================================
def insert_gemini_analyses_direct(gemini_analyses: list) -> bool:
    """Directly uploads in-memory Gemini analysis objects to Supabase."""
    if not URL or not KEY or not gemini_analyses:
        return False

    parsed_url = urlparse(URL)
    base_url = f"{parsed_url.scheme}://{parsed_url.netloc}"
    gemini_endpoint = f"{base_url}/rest/v1/{GEMINI_TABLE}?on_conflict=link"

    headers = {
        "Authorization": f"Bearer {KEY}",
        "apiKey": KEY,
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates",
    }

    payload = [realign_gemini_payload(row) for row in gemini_analyses]

    try:
        res = httpx.post(
            gemini_endpoint, headers=headers, json=payload, timeout=10.0
        )
        if res.status_code in [200, 201]:
            logging.info(
                f"Successfully uploaded {len(payload)} Gemini records to '{GEMINI_TABLE}'."
            )
            return True
        else:
            logging.error(
                f"Gemini upload rejected (HTTP {res.status_code}): {res.text}"
            )
            return False
    except Exception as e:
        logging.error(f"Failed to upload Gemini analyses: {e}")
        return False
    
def insert_json_to_table(local_file_path: str, table_name: str) -> bool:
    """
    Reads local JSON datasets, realigns column schemas for target database tables,
    and upserts rows into Supabase using HTTP POST requests.

    :param local_file_path: Relative or absolute string path to target local JSON file.
    :param table_name: Database table identifier name.
    :return: Boolean indicating whether database sync succeeded.
    """
    if not URL or not KEY:
        logging.error("Database sync halted: Supabase URL or SERVICE_ROLE_KEY missing from environment.")
        return False

    try:
        local_path = Path(local_file_path).resolve()
        if not local_path.exists():
            logging.error(f"Local file target not found on disk: {local_file_path}")
            return False
        
        parsed_url = urlparse(URL)
        base_url = f"{parsed_url.scheme}://{parsed_url.netloc}"
    except Exception as path_err:
        logging.error(f"Failed to parse database environment URL or local file path: {path_err}")
        return False

    headers = {
        "Authorization": f"Bearer {KEY}",
        "apiKey": KEY,
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates"  # Directs Supabase PostgREST engine to overwrite on key conflict
    }

    try:
        with open(local_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        if isinstance(data, dict):
            data = [data]

        if not isinstance(data, list):
            logging.error(f"Invalid JSON data structure loaded from '{local_path}'. Expected array or object.")
            return False

        # Phase 1: Dual-Table Execution for News and Gemini Datasets
        if table_name == NEWS_TABLE or table_name == "financial_news":
            logging.info(f"Executing Phase 1 database sync for table: '{table_name}'")
            
            # Smart Check: Handle pre-structured arrays directly from memory
            if len(data) > 0 and isinstance(data[0], dict) and "prompt_input" in data[0]:
                gemini_rows_to_insert = [realign_gemini_payload(row) for row in data]
                news_rows_to_insert = []
            elif len(data) > 0 and isinstance(data[0], dict) and "link" in data[0] and "prompt_input" not in data[0]:
                news_rows_to_insert = data
                gemini_rows_to_insert = []
            else:
                # Fallback safeguard sequence using the AI processor module
                raw_news, raw_gemini = process_news_batch(data, local_path.name)
                news_rows_to_insert = raw_news
                gemini_rows_to_insert = [realign_gemini_payload(row) for row in raw_gemini]

            try:
                news_endpoint = f"{base_url}/rest/v1/{NEWS_TABLE}?on_conflict=link"
                gemini_endpoint = f"{base_url}/rest/v1/{GEMINI_TABLE}?on_conflict=link"

                if news_rows_to_insert:
                    news_res = httpx.post(news_endpoint, headers=headers, json=news_rows_to_insert, timeout=10.0)
                    if news_res.status_code in [200, 201]:
                        logging.info(f"Successfully uploaded {len(news_rows_to_insert)} records to table '{NEWS_TABLE}'.")
                    else:
                        logging.error(f"Upload to '{NEWS_TABLE}' rejected (HTTP {news_res.status_code}): {news_res.text}")
                
                if gemini_rows_to_insert:
                    try:
                        gemini_res = httpx.post(
                            gemini_endpoint, 
                            headers=headers, 
                            json=gemini_rows_to_insert, 
                            timeout=10.0
                        )
                        if gemini_res.status_code in [200, 201]:
                            logging.info(f"Successfully upserted {len(gemini_rows_to_insert)} Gemini analysis records to '{GEMINI_TABLE}'.")
                        else:
                            logging.error(f"'{GEMINI_TABLE}' upload rejected (HTTP {gemini_res.status_code}): {gemini_res.text}")
                            
                    except httpx.RequestError as req_err:
                        logging.error(f"Network error during bulk upsert to '{GEMINI_TABLE}': {req_err}")
                
            except httpx.RequestError as req_err:
                logging.error(f"Network transport error executing Supabase news endpoints: {req_err}")
                return False
                
            return True

        # Phase 2: Stock Prices Table Column Realignment
        elif table_name == STOCKS_TABLE:
            today_str = datetime.now().strftime("%Y-%m-%d")
            cleaned_stock_rows = []

            for row in data:
                if not isinstance(row, dict):
                    continue

                # Align legacy column names with database schema
                if "close" in row:
                    row["price"] = row.pop("close")
                if "change" in row:
                    row["percentage_change"] = row.pop("change")
                if "collected_date" not in row:
                    row["collected_date"] = today_str
                    
                # Retain only allowed database columns
                allowed_stock_columns = {"ticker", "price", "percentage_change", "collected_date"}
                cleaned_row = {k: v for k, v in row.items() if k in allowed_stock_columns}
                cleaned_stock_rows.append(cleaned_row)

            endpoint = f"{base_url}/rest/v1/{STOCKS_TABLE}"
            response = httpx.post(endpoint, headers=headers, json=cleaned_stock_rows, timeout=10.0)
            
            if response.status_code in [200, 201]:
                logging.info(f"Successfully uploaded stock prices into table '{table_name}'.")
                return True
            
            logging.error(f"Stock database upload rejected (HTTP {response.status_code}): {response.text}")
            return False

    except json.JSONDecodeError as json_err:
        logging.error(f"Failed to parse target JSON file '{local_file_path}': {json_err}")
        return False
    except Exception as e:
        logging.error(f"Unexpected error executing Supabase table update: {e}")
        return False


# ==============================================================================
# 4. READ-ONLY INTERACTIVE TELEGRAM CLI READ LAYERS
# ==============================================================================
def check_supabase_connection() -> bool:
    """
    Verifies database connection health by pinging the REST root endpoint.
    Used by the Telegram bot's /status command handler.
    """
    if not URL or not KEY:
        return False
    try:
        parsed_url = urlparse(URL)
        base_url = f"{parsed_url.scheme}://{parsed_url.netloc}"
        
        headers = {
            "Authorization": f"Bearer {KEY}",
            "apiKey": KEY
        }
        response = httpx.get(f"{base_url}/rest/v1/", headers=headers, timeout=5.0)
        return response.status_code == 200
    except Exception as e:
        logging.error(f"Supabase health check connection failed: {e}")
        return False


def get_stock_price(ticker: str) -> dict | None:
    """
    Queries the stock table for the latest pricing entry of a given ticker symbol.
    Used by the Telegram bot's /price <ticker> command handler.
    """
    if not URL or not KEY or not ticker:
        return None
    try:
        parsed_url = urlparse(URL)
        base_url = f"{parsed_url.scheme}://{parsed_url.netloc}"
        
        headers = {
            "Authorization": f"Bearer {KEY}",
            "apiKey": KEY
        }
        params = {
            "ticker": f"eq.{ticker.strip().upper()}",
            "order": "collected_date.desc",
            "limit": 1
        }
        
        url = f"{base_url}/rest/v1/{STOCKS_TABLE}"
        response = httpx.get(url, headers=headers, params=params, timeout=5.0)
        
        if response.status_code == 200 and response.json():
            data = response.json()
            if isinstance(data, list) and len(data) > 0:
                return data[0]
        return None
    except Exception as e:
        logging.error(f"Failed to query on-demand stock metrics for ticker '{ticker}': {e}")
        return None


def get_latest_news(ticker: str = None, limit: int = 3) -> list:
    """Queries the latest news articles from Supabase and merges Gemini analysis."""
    if not URL or not KEY:
        return []
    try:
        parsed_url = urlparse(URL)
        base_url = f"{parsed_url.scheme}://{parsed_url.netloc}"

        headers = {"Authorization": f"Bearer {KEY}", "apiKey": KEY}

        # Case 1: Selected ticker news (Take from GEMINI_TABLE directly)
        if ticker:
            clean_ticker = ticker.strip().upper()
            url = f"{base_url}/rest/v1/{GEMINI_TABLE}"
            params = {
                "select": "link,summary,sentiment,related_tickers,affected_sectors,importance_score",
                "related_tickers": f"cs.{{{clean_ticker}}}",
                "limit": limit,
            }
            response = httpx.get(url, headers=headers, params=params, timeout=5.0)
            if response.status_code == 200:
                return response.json() if isinstance(response.json(), list) else []
            return []

        # Case 2: General news (Fetch from NEWS_TABLE and merge with Gemini analysis)
        else:
            news_url = f"{base_url}/rest/v1/{NEWS_TABLE}"
            news_params = {"order": "published_at.desc", "limit": limit}
            news_res = httpx.get(
                news_url, headers=headers, params=news_params, timeout=5.0
            )

            if news_res.status_code != 200:
                return []

            articles = news_res.json()
            if not isinstance(articles, list) or not articles:
                return []

            # Get links from the articles to query Gemini table
            links = [
                art.get("link")
                for art in articles
                if isinstance(art, dict) and art.get("link")
            ]
            if not links:
                return articles

            formatted_links = ",".join([f'"{l}"' for l in links])
            gemini_url = f"{base_url}/rest/v1/{GEMINI_TABLE}"
            gemini_params = {
                "select": "link,sentiment,importance_score,affected_sectors",
                "link": f"in.({formatted_links})",
            }
            gemini_res = httpx.get(
                gemini_url, headers=headers, params=gemini_params, timeout=5.0
            )

            # Build a mapping of link to Gemini analysis for quick lookup
            gemini_map = {}
            if gemini_res.status_code == 200 and isinstance(
                gemini_res.json(), list
            ):
                for item in gemini_res.json():
                    if item.get("link"):
                        gemini_map[item["link"]] = item

            merged_articles = []
            for art in articles:
                link = art.get("link")
                gemini_info = gemini_map.get(link, {})

                art["sentiment"] = gemini_info.get("sentiment", "Neutral")
                art["importance_score"] = gemini_info.get(
                    "importance_score", 3
                )
                art["affected_sectors"] = gemini_info.get(
                    "affected_sectors", []
                )
                merged_articles.append(art)

            return merged_articles

    except Exception as e:
        logging.error(
            f"Failed to query latest news articles from Supabase: {e}"
        )
        return []