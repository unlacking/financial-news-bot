import os
import json
import time
import random
from typing import List
from pydantic import BaseModel, Field, field_validator
<<<<<<< HEAD
from google import genai
from google.genai.errors import APIError

# 1. Define schema matching the exact datatypes of the gemini_responses table
class FinancialAnalysisSchema(BaseModel):
    summary: str = Field(
        description="A comprehensive 2-3 sentence summary of the article strictly in Vietnamese."
    )
    sentiment: str = Field(
        description="The market sentiment direction of the news toward the target tickers (e.g., 'Positive', 'Negative', 'Neutral')."
    )
    related_tickers: List[str] = Field(
        description="List of stock tickers explicitly mentioned or heavily impacted (e.g., ['PNJ', 'FPT'])."
    )
    importance_score: int = Field(
        description="The market-moving significance of this article graded as an integer score on a scale from 1 (lowest) to 5 (highest)."
    )
=======
from src.price_collector import get_all_market_tickers
from google import genai
from google.genai.errors import APIError

# Cache the official active 3-character ticker pool once at compilation time
try:
    VALID_VIETNAMESE_TICKERS = set(get_all_market_tickers())
except Exception:
    # Fallback to standard high-cap anchors if the network collector goes down
    VALID_VIETNAMESE_TICKERS = {"VCB", "FPT", "HPG", "VNM", "VIC", "VRE", "MSN"}

class FinancialAnalysisSchema(BaseModel):
    summary: str = Field(description="A comprehensive 2-3 sentence summary...")
    sentiment: str = Field(description="The market sentiment direction...")
    related_tickers: List[str] = Field(description="List of stock tickers...")
    importance_score: int = Field(description="Market significance score...")

    @field_validator("related_tickers")
    @classmethod
    def filter_and_validate_tickers(cls, tickers: List[str]) -> List[str]:
        """
        Intersects the AI-generated list against live listed market assets.
        Forces formatting compliance and eliminates out-of-bounds hallucinations.
        """
        # 1. Clean format string structures (Force Uppercase & strip whitespace)
        cleaned_tickers = [str(t).strip().upper() for t in tickers]
        
        # 2. Perform a Set-Intersection to extract ONLY valid listed market assets
        validated_pool = list(set(cleaned_tickers).intersection(VALID_VIETNAMESE_TICKERS))
        
        # 3. Log a warning terminal note if tickers were filtered out
        dropped = set(cleaned_tickers) - set(validated_pool)
        if dropped:
            print(f"Validation Note: Dropped unlisted/invalid tickers: {dropped}")
            
        return validated_pool
>>>>>>> 5efaf08c26bc98c3614640d621f68628e37f0938

    @field_validator("importance_score")
    @classmethod
    def validate_score(cls, value: int) -> int:
<<<<<<< HEAD
        # Enforce that the integer fits gracefully within standard ratings
        if not (1 <= value <= 5):
            return 3  # Default to neutral/medium importance if out of bounds
=======
        if not (1 <= value <= 5):
            return 3
>>>>>>> 5efaf08c26bc98c3614640d621f68628e37f0938
        return value


def _call_gemini_with_backoff(prompt: str, max_retries: int = 5) -> str:
    """Executes the raw Gemini API call handling rate limits (429)."""
    client = genai.Client()
    base_delay = 2.0

    for attempt in range(max_retries):
        try:
            response = client.models.generate_content(
                model='gemini-2.5-flash',
                contents=prompt,
                config={
                    "response_mime_type": "application/json",
                    "response_schema": FinancialAnalysisSchema,
                    "system_instruction": (
                        "You are an elite financial analyst monitoring the Vietnamese stock market.\n"
                        "Analyze the provided news article text and extract structural metadata.\n\n"
                        "CRITICAL DIRECTION FOR THE 'summary' FIELD:\n"
                        "Align your output length, dense tone, and style perfectly with this gold-standard example:\n\n"
                        "Example Input Body: Vingroup successfully floated $200 million in international bonds on Tuesday to fund sustainable development projects.\n"
                        "Example Output Summary: Vingroup đã phát hành thành công 200 triệu USD trái phiếu quốc tế nhằm tài trợ cho các dự án phát triển bền vững."
                    )
                }
            )
            return response.text.strip()

        except APIError as e:
            if e.code == 429:
                delay = (base_delay * (2 ** attempt)) + random.random()
                print(f"Rate Limit Hit (HTTP 429). Retrying in {delay:.2f}s...")
                time.sleep(delay)
            else:
                raise e
        except Exception as e:
            raise e

    raise Exception("Execution failed: Max retries exceeded due to rate limiting.")


def analyze_article(title: str, body: str) -> dict:
    """Processes raw text and guarantees a dictionary conforming to the schema."""
    fallback_data = {
        "summary": "Không thể xử lý tóm tắt do quá tải hệ thống.",
        "sentiment": "Neutral",
        "related_tickers": [],
        "importance_score": 3
    }

    if not body or len(body.strip()) < 10:
        return fallback_data

    try:
        prompt = f"Title: {title}\nBody: {body}"
        raw_json_output = _call_gemini_with_backoff(prompt)
        return json.loads(raw_json_output)
    except Exception as final_err:
        print(f"AI Processor Error: {final_err}")
        return fallback_data