"""
GEMINI AI PROCESSOR & BATCH MANAGEMENT ENGINE
---------------------------------------------
This module acts as the core AI analysis component for Phase 1 of the pipeline.
It handles Pydantic schema validation, rate-limited Gemini API execution,
ticker symbol filtering, sector extraction, and batch queue management.
"""

import os
import json
import time
import random
import logging
from typing import List, Literal, Tuple, Dict, Any
from pydantic import BaseModel, Field, field_validator
from google import genai
from google.genai.errors import APIError
from dotenv import load_dotenv

from src.price_collector import get_all_market_tickers

# ==============================================================================
# 1. ENVIRONMENT & MARKET TICKER CACHE
# ==============================================================================
try:
    load_dotenv()
except Exception as env_err:
    logging.warning(f"Non-fatal warning: Failed to map .env configuration in ai_processor: {env_err}")

GEMINI_VERSION: str = os.getenv("GEMINI_VERSION", "gemini-3.5-flash")

# Cache official active 3-character ticker pool once at module load
try:
    VALID_VIETNAMESE_TICKERS = set(get_all_market_tickers())
except Exception as ticker_cache_err:
    logging.warning(f"Failed to fetch dynamic ticker list for validation: {ticker_cache_err}. Using fallback pool.")
    VALID_VIETNAMESE_TICKERS = {"VCB", "FPT", "HPG", "VNM", "VIC", "VRE", "MSN", "TCB", "MBB", "ACB"}


# ==============================================================================
# 2. PYDANTIC OUTPUT SCHEMA & VALIDATION
# ==============================================================================
class FinancialAnalysisSchema(BaseModel):
    summary: str = Field(description="A comprehensive 2-3 sentence summary in Vietnamese.")
    sentiment: Literal["Positive", "Negative", "Neutral"] = Field(
        description="Market sentiment direction. 'Positive' for growth/opportunities, 'Negative' for risks/decline. 'Neutral' only if purely informational."
    )
    related_tickers: List[str] = Field(description="List of stock tickers mentioned or related to the news.")
    affected_sectors: List[str] = Field(
        default=[],
        description="List of primary economic/industry sectors impacted (e.g., 'Banking', 'Real Estate', 'Securities', 'Steel', 'Energy', 'Retail', 'Technology', 'Aviation')."
    )
    importance_score: int = Field(
        ge=1, le=5, 
        description="Market importance rating from 1 (very low impact) to 5 (systemic market mover)."
    )

    @field_validator("related_tickers")
    @classmethod
    def filter_and_validate_tickers(cls, tickers: List[str]) -> List[str]:
        """
        Intersects the AI-generated ticker list against live listed market assets.
        Forces uppercase formatting and eliminates hallucinated ticker strings.
        """
        if not tickers:
            return []

        try:
            cleaned_tickers = [str(t).strip().upper() for t in tickers if t]
            validated_pool = list(set(cleaned_tickers).intersection(VALID_VIETNAMESE_TICKERS))
            
            dropped = set(cleaned_tickers) - set(validated_pool)
            if dropped:
                logging.info(f"Validation Note: Filtered out unlisted/invalid tickers: {dropped}")
                
            return validated_pool
        except Exception as val_err:
            logging.warning(f"Failed to validate ticker pool in Pydantic schema: {val_err}")
            return []

    @field_validator("affected_sectors")
    @classmethod
    def sanitize_sectors(cls, sectors: List[str]) -> List[str]:
        """
        Cleans and formats affected industry sector names.
        """
        if not sectors or not isinstance(sectors, list):
            return []
        try:
            cleaned = [str(s).strip().title() for s in sectors if s]
            return list(set(cleaned))
        except Exception as sec_err:
            logging.warning(f"Failed to sanitize affected sectors list: {sec_err}")
            return []

    @field_validator("importance_score")
    @classmethod
    def validate_score(cls, value: int) -> int:
        if not (1 <= value <= 5):
            return 3
        return value


# ==============================================================================
# 3. GEMINI API CALL WITH EXPONENTIAL BACKOFF
# ==============================================================================
def _call_gemini_with_backoff(prompt: str, max_retries: int = 5) -> str:
    """
    Executes raw Gemini API calls handling HTTP 429 rate limits using exponential backoff.
    """
    client = genai.Client()
    base_delay = 2.0

    for attempt in range(max_retries):
        try:
            response = client.models.generate_content(
                model=GEMINI_VERSION,
                contents=prompt,
                config={
                    "response_mime_type": "application/json",
                    "response_schema": FinancialAnalysisSchema,
                    "temperature": 0.0,
                    "system_instruction": (
                        "You are an elite financial analyst monitoring the Vietnamese stock market.\n"
                        "Analyze the provided news article text and extract structural metadata.\n\n"
                        "CRITICAL DIRECTION FOR THE 'sentiment' FIELD:\n"
                        "- Be decisive. If an expert suggests buying or scaling up, it is 'Positive'.\n"
                        "- If foreign investors are pulling out or a stock is losing traction, it is 'Negative'.\n"
                        "- Do not default to 'Neutral' unless the article is completely devoid of financial impact.\n\n"
                        "CRITICAL DIRECTION FOR THE 'affected_sectors' FIELD:\n"
                        "- Identify the primary industry/sector categories impacted by the news article.\n"
                        "- Use standardized sector names such as 'Banking', 'Real Estate', 'Securities', 'Steel', 'Energy', 'Retail', 'Technology', 'Aviation', etc.\n\n"
                        "CRITICAL DIRECTION FOR THE 'summary' FIELD:\n"
                        "Align your output length, dense tone, and style perfectly with this gold-standard example (in Vietnamese):\n\n"
                        "Example Input Summary: Vingroup successfully floated $200 million in international bonds on Tuesday to fund sustainable development projects.\n"
                        "Example Output Summary: Vingroup đã phát hành thành công 200 triệu USD trái phiếu quốc tế nhằm tài trợ cho các dự án phát triển bền vững."
                    )
                }
            )
            return response.text.strip()

        except APIError as e:
            if getattr(e, 'code', None) == 429 or "429" in str(e):
                delay = (base_delay * (2 ** attempt)) + random.random()
                logging.warning(f"Rate limit hit (HTTP 429). Retrying in {delay:.2f} seconds (Attempt {attempt + 1}/{max_retries})...")
                time.sleep(delay)
            else:
                logging.error(f"Gemini API Error encounter: {e}")
                raise e
        except Exception as e:
            logging.error(f"Unexpected error during Gemini API invocation: {e}")
            raise e

    raise Exception("Gemini execution failed: Exceeded maximum retries due to rate limiting.")


# ==============================================================================
# 4. SINGLE ARTICLE ANALYSIS ENTRY POINT
# ==============================================================================
def analyze_article(title: str, summary: str) -> dict:
    """
    Cleans incoming title/summary text, executes Gemini analysis,
    and returns a structured dictionary matching FinancialAnalysisSchema.
    """
    fallback_data = {
        "summary": "Không thể xử lý tóm tắt do quá tải hệ thống hoặc thiếu dữ liệu.",
        "sentiment": "error from ai_processor.py",
        "related_tickers": [],
        "affected_sectors": [],
        "importance_score": 3
    }

    clean_summary = summary.strip() if summary and isinstance(summary, str) else ""
    clean_title = title.strip() if title and isinstance(title, str) else ""

    placeholders = {"no summary text available.", "none", "null", "undefined", ""}
    
    # Check for empty or missing summary text
    if not clean_summary or len(clean_summary) < 10 or clean_summary.lower() in placeholders:
        if len(clean_title) > 10:
            logging.info(f"Missing summary text. Downgrading context scope to Title only for: '{clean_title[:30]}...'")
            summary = "No extended summary text provided. Base your analysis strictly on the headline title."
        else:
            logging.warning(f"Skipping AI analysis for '{clean_title[:30]}' due to missing title and summary context.")
            return fallback_data

    try:
        prompt = f"Title: {title}\nSummary: {summary[:200] if summary else 'None'}..."
        raw_json_output = _call_gemini_with_backoff(prompt)
        parsed_result = json.loads(raw_json_output)
        if isinstance(parsed_result, dict):
            return parsed_result
        return fallback_data
    except json.JSONDecodeError as json_err:
        logging.error(f"Failed to parse Gemini output JSON: {json_err}")
        return fallback_data
    except Exception as final_err:
        logging.error(f"AI Processor failure for '{clean_title[:30]}': {final_err}")
        return fallback_data


# ==============================================================================
# 5. NEWS BATCH QUEUE & RATE-LIMIT COOLDOWN PROCESSOR
# ==============================================================================
def process_news_batch(data: list, local_path_name: str = "") -> Tuple[list, list]:
    """
    Processes articles in sub-batches to remain safely beneath free-tier RPM limits.

    :param data: List of raw news article dictionaries.
    :param local_path_name: File path name string used to infer source publication.
    :return: Tuple containing (news_rows_to_insert, gemini_rows_to_insert).
    """
    if not data or not isinstance(data, list):
        logging.info("No news data provided to process_news_batch. Processing bypassed.")
        return [], []

    news_rows_to_insert = []
    gemini_rows_to_insert = []
    
    BATCH_SIZE = 10  
    COOLDOWN_PERIOD = 65  # Pause duration in seconds between sub-batches
    
    for i in range(0, len(data), BATCH_SIZE):
        batch = data[i:i + BATCH_SIZE]
        logging.info(f"Processing Gemini AI sub-batch {i // BATCH_SIZE + 1} ({len(batch)} articles)...")
        
        for row in batch:
            if not isinstance(row, dict):
                continue

            try:
                # Infer source publisher label
                inferred_source = "Unknown"
                sources_map = ["CafeF", "VnEconomy", "Vietstock"]
                for src in sources_map:
                    if src.lower() in str(local_path_name).lower():
                        inferred_source = src
                        break

                published_at = row.get("published_at")
                link = row.get("url") or row.get("link", "")
                title = row.get("title", "Untitled Article").strip()
                summary = row.get("summary", "").strip()

                news_row = {
                    "source": row.get("source") or inferred_source,
                    "title": title,
                    "link": link,
                    "published_at": published_at,
                    "summary": summary
                }
                news_rows_to_insert.append(news_row)
                
                # Execute AI analysis if valid text is present
                if summary and len(summary) > 10:
                    logging.info(f"Submitting article to Gemini AI layer: '{title[:30]}...'")
                    analysis = analyze_article(title, summary)
                else:
                    logging.info(f"Bypassing AI call for '{title[:30]}' due to missing summary text.")
                    analysis = {
                        "summary": "Full text summary unavailable for analysis.",
                        "sentiment": "error from ai_processor.py",
                        "related_tickers": [],
                        "affected_sectors": [],
                        "importance_score": 1
                    }
                    
                gemini_row = {
                    "link": link,
                    "prompt_input": f"Title: {title}\nSummary: {summary[:200] if summary else 'None'}...",
                    "model_name": GEMINI_VERSION,
                    "summary": analysis.get("summary", ""),
                    "sentiment": analysis.get("sentiment", "error from ai_processor.py"),
                    "related_tickers": analysis.get("related_tickers", []),
                    "affected_sectors": analysis.get("affected_sectors", []),
                    "importance_score": analysis.get("importance_score", 1)
                }
                gemini_rows_to_insert.append(gemini_row)

                time.sleep(1.5)  # Gentle spacing delay between requests

            except Exception as item_err:
                logging.error(f"Error processing news row inside batch: {item_err}")
                continue
        
        # Enforce cooldown pause between sub-batches
        if i + BATCH_SIZE < len(data):
            logging.info(f"Approaching API rate limit threshold. Pausing execution for {COOLDOWN_PERIOD} seconds...")
            time.sleep(COOLDOWN_PERIOD)
            
    return news_rows_to_insert, gemini_rows_to_insert