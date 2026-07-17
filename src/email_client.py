import os
import smtplib
import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from dotenv import load_dotenv

load_dotenv()

SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SENDER_EMAIL = os.getenv("SENDER_EMAIL")
SENDER_PASSWORD = os.getenv("SENDER_PASSWORD")
RECEIVER_EMAIL = os.getenv("RECEIVER_EMAIL")

def build_html_template(prices: list, news: list, analyses: list) -> str:
    """Generates a clean, readable HTML layout for email clients."""
    # Format stock table rows
    stock_rows = ""
    for p in prices[:20]:  # Limit rows to keep mail light
        ticker = p.get("ticker", "N/A")
        price = p.get("price", 0)
        pct = p.get("percentage_change", 0)
        color = "#22c55e" if pct >= 0 else "#ef4444"
        stock_rows += f"""
        <tr>
            <td style="padding: 10px; border-bottom: 1px solid #e2e8f0; font-weight: bold;">{ticker}</td>
            <td style="padding: 10px; border-bottom: 1px solid #e2e8f0;">{price:,} VND</td>
            <td style="padding: 10px; border-bottom: 1px solid #e2e8f0; color: {color}; font-weight: bold;">{pct:+.2f}%</td>
        </tr>
        """

    # Format news items matched with their AI summaries
    news_blocks = ""
    for idx, item in enumerate(news):
        title = item.get("title", "Untitled")
        link = item.get("link", "#")
        source = item.get("source", "Unknown")
        
        # Pull associated Gemini analysis metric if matching index exists
        summary = "No analysis summary available."
        sentiment = "Neutral"
        if idx < len(analyses):
            summary = analyses[idx].get("summary", summary)
            sentiment = analyses[idx].get("sentiment", "Neutral")

        senti_color = "#3b82f6"  # Blue for Neutral
        if sentiment.lower() == "positive": senti_color = "#22c55e"
        elif sentiment.lower() == "negative": senti_color = "#ef4444"

        news_blocks += f"""
        <div style="margin-bottom: 20px; padding: 15px; border-left: 4px solid {senti_color}; background-color: #f8fafc;">
            <h4 style="margin: 0 0 5px 0;"><a href="{link}" style="color: #1e3a8a; text-decoration: none;">{title}</a></h4>
            <p style="margin: 0 0 8px 0; font-size: 12px; color: #64748b;">Nguồn: {source} | Thị trường: <span style="color: {senti_color}; font-weight: bold;">{sentiment}</span></p>
            <p style="margin: 0; font-size: 14px; color: #334155; line-height: 1.5;">{summary}</p>
        </div>
        """

    return f"""
    <html>
    <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; color: #1e293b; padding: 20px; max-width: 650px; margin: 0 auto;">
        <h2 style="color: #0f172a; border-bottom: 2px solid #3b82f6; padding-bottom: 10px;">Bản Tin Tài Chính Hàng Ngày</h2>
        <p style="color: #64748b;">Tổng hợp thị trường chứng khoán Việt Nam.</p>
        
        <h3 style="color: #1e3a8a; margin-top: 25px;">1. Biến Động Thị Trường (Top Watchlist)</h3>
        <table style="width: 100%; border-collapse: collapse; margin-bottom: 25px;">
            <thead>
                <tr style="background-color: #f1f5f9; text-align: left;">
                    <th style="padding: 10px;">Mã</th>
                    <th style="padding: 10px;">Giá</th>
                    <th style="padding: 10px;">Thay Đổi</th>
                </tr>
            </thead>
            <tbody>
                {stock_rows if stock_rows else '<tr><td colspan="3" style="padding:10px; text-align:center; color:#64748b;">Không có dữ liệu giá.</td></tr>'}
            </tbody>
        </table>

        <h3 style="color: #1e3a8a;">2. Phân Tích Tin Tức & Tóm Tắt AI</h3>
        {news_blocks if news_blocks else '<p style="color:#64748b;">Không có tin tức mới được xử lý.</p>'}
        
        <hr style="border: 0; border-top: 1px solid #e2e8f0; margin-top: 30px;" />
        <p style="font-size: 11px; color: #94a3b8; text-align: center;">Hệ thống tự động phát triển bởi Financial News Bot Client Daemon.</p>
    </body>
    </html>
    """

def send_email_digest(prices: list, news: list, analyses: list) -> bool:
    if not all([SMTP_SERVER, SENDER_EMAIL, SENDER_PASSWORD, RECEIVER_EMAIL]):
        logging.warning("SMTP Parameters missing. Skipping email dispatch.")
        return False

    # Parse the comma-separated string into a clean Python list
    receiver_list = [email.strip() for email in RECEIVER_EMAIL.split(",") if email.strip()]
    
    if not receiver_list:
        logging.warning("Receiver email list is empty. Skipping dispatch.")
        return False

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"📊 [Bản Tin EOD] Báo Cáo Thị Trường - {logging.datetime.datetime.now().strftime('%d/%m/%Y')}"
    msg["From"] = SENDER_EMAIL
    
    # The "To" header needs to be a clean string for the email UI
    msg["To"] = ", ".join(receiver_list) 

    html_content = build_html_template(prices, news, analyses)
    msg.attach(MIMEText(html_content, "html"))

    try:
        logging.info(f"Connecting to remote secure mailserver via {SMTP_SERVER}:{SMTP_PORT}...")
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
            
            # Pass the parsed Python list directly into sendmail
            server.sendmail(SENDER_EMAIL, receiver_list, msg.as_string())
            
        logging.info(f"HTML Newsletter successfully routed to {len(receiver_list)} recipients.")
        return True
    except Exception as smtp_err:
        logging.error(f"Failed to execute SMTP delivery block protocol: {smtp_err}")
        return False