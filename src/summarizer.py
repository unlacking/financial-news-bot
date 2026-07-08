import os
from google import genai

def generate_summary(title: str, body: str) -> str:
    """
    Analyzes an article's title and body and returns a dense, 
    informative 2-3 sentence summary strictly in Vietnamese.
    """
    if not body or len(body.strip()) < 10:
        return "Không có tóm tắt."

    try:
        # Initialize the official Gemini Client
        client = genai.Client()

        prompt = f"Title: {title}\nBody: {body}"

        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
            config={
                "system_instruction": (
                    "You are a financial analyst summarizing articles into concise Vietnamese briefs.\n"
                    "Align your output length, dense tone, and style perfectly with this gold-standard example:\n\n"
                    "Example Input:\n"
                    "Title: Vingroup issues $200M in international bonds\n"
                    "Body: Vingroup successfully floated $200 million in international bonds on Tuesday to fund sustainable development projects. While global interest rates remain high, strong demand from Asian institutional investors fully covered the book building within four hours.\n\n"
                    "Example Output:\n"
                    "Vingroup đã phát hành thành công 200 triệu USD trái phiếu quốc tế nhằm tài trợ cho các dự án phát triển bền vững. Bất chấp bối cảnh lãi suất toàn cầu neo cao, nhu cầu mạnh mẽ từ các nhà đầu tư tổ chức châu Á đã giúp lấp đầy sổ lệnh chỉ trong vòng 4 giờ."
                )
            }
        )
        return response.text.strip()
    except Exception as gemini_err:
        print(f"Gemini API failed for this article: {gemini_err}")
        return "Không thể xử lý tóm tắt."