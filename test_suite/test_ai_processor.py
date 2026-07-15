# test_suite/test_ai_processor.py
import os
import sys

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from src.ai_processor import analyze_article

def run_ai_processor_test():
    print("====================================")
    print("STARTING AI PROCESSOR ISOLATION TEST")
    print("====================================\n")

    # Mock financial news data
    mock_title = "VinFast secures massive strategic investment from international consortium"
    mock_body = (
        "VinFast Auto officially announced on Tuesday that it has closed a strategic equity investment "
        "worth 500 million USD from a prominent global asset management consortium. The capital injection "
        "will directly fund the scaling of electric vehicle production pipelines across North America and Southeast Asia. "
        "Market analysts expect this move to significantly stabilize VIC stock volatility over the coming quarters."
    )

    print("Sending text to Gemini for structured financial analysis...")
    try:
        result = analyze_article(title=mock_title, body=mock_body)
        
        print("\nAnalysis Result Details:")
        print(f"Summary: {result.get('summary')}")
        print(f"Sentiment: {result.get('sentiment')}")
        print(f"Related Tickers: {result.get('related_tickers')}")
        print(f"Importance Score: {result.get('importance_score')}/5")
        
        # Basic assertion validation
        assert "summary" in result, "Validation failure: missing summary field"
        assert "sentiment" in result, "Validation failure: missing sentiment field"
        print("\nSTATUS: SUCCESS - AI Processor executed and returned valid schema structures.")
        
    except Exception as e:
        print(f"\nSTATUS: FAILED - An error occurred during AI processing: {e}")

    print("\n====================================")
    print("AI PROCESSOR ISOLATION TEST COMPLETE")
    print("====================================")

if __name__ == "__main__":
    run_ai_processor_test()