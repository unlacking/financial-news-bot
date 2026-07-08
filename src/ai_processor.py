import os
import json
import time
import random
from typing import List
from pydantic import BaseModel, Field, field_validator
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

    @field_validator("importance_score")
    @classmethod
    def validate_score(cls, value: int) -> int:
        # Enforce that the integer fits gracefully within standard ratings
        if not (1 <= value <= 5):
            return 3  # Default to neutral/medium importance if out of bounds
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