import os
import json
from typing import List, Literal
from pydantic import BaseModel, Field
from google import genai

# 1. Define the exact database-ready structured response schema
class FinancialAnalysisSchema(BaseModel):
    summary: str = Field(
        description="A comprehensive 2-3 sentence summary of the article strictly in Vietnamese."
    )
    sentiment: Literal["Positive", "Negative", "Neutral"] = Field(
        description="The market sentiment direction of the news toward the target tickers or sector."
    )
    related_tickers: List[str] = Field(
        description="List of stock tickers explicitly mentioned or heavily impacted (e.g., ['PNJ', 'FPT', 'VIC'])."
    )
    importance: Literal["High", "Medium", "Low"] = Field(
        description="The market-moving significance of this article for an investor."
    )

def analyze_article(title: str, body: str) -> dict:
    """
    Analyzes an article's title and body using Gemini Structured Outputs.
    Returns a unified dict containing summary, sentiment, related_tickers, and importance.
    """
    # Safe default fallback state if processing encounters failures
    fallback_data = {
        "summary": "Không thể xử lý tóm tắt.",
        "sentiment": "Neutral",
        "related_tickers": [],
        "importance": "Low"
    }

    if not body or len(body.strip()) < 10:
        return fallback_data

    try:
        # Initialize the official SDK client
        client = genai.Client()

        prompt = f"Title: {title}\nBody: {body}"

        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
            config={
                "response_mime_type": "application/json",
                "response_schema": FinancialAnalysisSchema,
                "system_instruction": (
                    "You are a financial analyst summarizing and analyzing articles into concise Vietnamese briefs "
                    "with structured metadata metadata tags.\n\n"
                    "CRITICAL DIRECTION FOR THE 'summary' FIELD:\n"
                    "Align your output length, dense tone, and style perfectly with this gold-standard example:\n\n"
                    "Example Input:\n"
                    "Title: Vingroup issues $200M in international bonds\n"
                    "Body: Vingroup successfully floated $200 million in international bonds on Tuesday to fund sustainable development projects. While global interest rates remain high, strong demand from Asian institutional investors fully covered the book building within four hours.\n\n"
                    "Example Output:\n"
                    "Vingroup đã phát hành thành công 200 triệu USD trái phiếu quốc tế nhằm tài trợ cho các dự án phát triển bền vững. Bất chấp bối cảnh lãi suất toàn cầu neo cao, nhu cầu mạnh mẽ từ các nhà đầu tư tổ chức châu Á đã giúp lấp đầy sổ lệnh chỉ trong vòng 4 giờ."
                )
            }
        )
        
        # Parse the guaranteed JSON response directly back into a standard Python dict
        return json.loads(response.text)

    except Exception as gemini_err:
        print(f"⚠️ Enriched AI processing failed for this row: {gemini_err}")
        return fallback_data