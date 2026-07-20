"""
EMAIL NOTIFICATION & NEWSLETTER DELIVERY ENGINE
------------------------------------------------
This module builds and transmits HTML market digests via SMTP.
It formats market prices and AI news analysis into clean, responsive HTML emails 
and dispatches them securely to configured recipient email lists.
"""

import os
import smtplib
import logging
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from dotenv import load_dotenv

# ==============================================================================
# 1. ENVIRONMENT & SMTP CREDENTIAL CONFIGURATION
# ==============================================================================
try:
    load_dotenv()
except Exception as env_err:
    logging.warning(f"Non-fatal warning: Failed to map .env path in email_client: {env_err}")

SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")

# Safe integer casting for SMTP port configuration
try:
    SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
except (ValueError, TypeError):
    logging.warning("Invalid SMTP_PORT specified in environment. Defaulting to 587.")
    SMTP_PORT = 587

SENDER_EMAIL = os.getenv("SENDER_EMAIL", "")
SENDER_PASSWORD = os.getenv("SENDER_PASSWORD", "")
RECEIVER_EMAIL = os.getenv("RECEIVER_EMAIL", "")


# ==============================================================================
# 2. HTML TEMPLATE BUILDER & DATA FORMATTER
# ==============================================================================
def build_html_template(prices: list, news: list, analyses: list) -> str:
    """
    Generates a responsive HTML email layout populated with market prices 
    and Gemini AI news summaries.

    :param prices: List of stock price dictionaries.
    :param news: List of raw news article dictionaries.
    :param analyses: List of structured AI analysis dictionaries from Gemini.
    :return: Formatted HTML string ready for email transmission.
    """
    # 1. Format stock price table rows safely
    stock_rows = ""
    if prices and isinstance(prices, list):
        for p in prices[:20]:  # Limit rows to keep payload size light
            if not isinstance(p, dict):
                continue

            try:
                ticker = str(p.get("ticker", "N/A")).strip().upper()
                
                raw_price = p.get("price", 0)
                price = float(raw_price) if raw_price is not None else 0.0
                
                raw_pct = p.get("percentage_change", 0.0)
                pct = float(raw_pct) if raw_pct is not None else 0.0

                color = "#22c55e" if pct >= 0 else "#ef4444"
                
                stock_rows += f"""
                <tr>
                    <td style="padding: 10px; border-bottom: 1px solid #e2e8f0; font-weight: bold;">{ticker}</td>
                    <td style="padding: 10px; border-bottom: 1px solid #e2e8f0;">{price:,.0f} VND</td>
                    <td style="padding: 10px; border-bottom: 1px solid #e2e8f0; color: {color}; font-weight: bold;">{pct:+.2f}%</td>
                </tr>
                """
            except (ValueError, TypeError) as cast_err:
                logging.warning(f"Failed to format stock row in email template for item '{p.get('ticker')}': {cast_err}")
                continue

    # 2. Format news items paired with Gemini AI analysis
    news_blocks = ""
    if news and isinstance(news, list):
        for idx, item in enumerate(news):
            if not isinstance(item, dict):
                continue

            try:
                title = str(item.get("title", "Untitled Article")).strip()
                link = str(item.get("link") or item.get("url") or "#").strip()
                source = str(item.get("source", "Unknown Source")).strip()
                
                # Extract matching Gemini analysis payload
                summary = "No analysis summary available."
                sentiment = "Neutral"
                
                if (
                    analyses 
                    and isinstance(analyses, list) 
                    and idx < len(analyses) 
                    and isinstance(analyses[idx], dict)
                ):
                    summary = str(analyses[idx].get("summary", summary)).strip()
                    sentiment = str(analyses[idx].get("sentiment", sentiment)).strip()

                senti_color = "#3b82f6"  # Neutral (Blue)
                if sentiment.lower() == "positive":
                    senti_color = "#22c55e"  # Positive (Green)
                elif sentiment.lower() == "negative":
                    senti_color = "#ef4444"  # Negative (Red)

                news_blocks += f"""
                <div style="margin-bottom: 20px; padding: 15px; border-left: 4px solid {senti_color}; background-color: #f8fafc;">
                    <h4 style="margin: 0 0 5px 0;"><a href="{link}" style="color: #1e3a8a; text-decoration: none;">{title}</a></h4>
                    <p style="margin: 0 0 8px 0; font-size: 12px; color: #64748b;">Nguồn: {source} | Thị trường: <span style="color: {senti_color}; font-weight: bold;">{sentiment}</span></p>
                    <p style="margin: 0; font-size: 14px; color: #334155; line-height: 1.5;">{summary}</p>
                </div>
                """
            except Exception as item_err:
                logging.error(f"Error formatting news block at index {idx} in email template: {item_err}")
                continue

    # 3. Assemble complete HTML layout
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


# ==============================================================================
# 3. SMTP DISPATCH & EMAIL TRANSMISSION ENGINE
# ==============================================================================
def send_email_digest(prices: list, news: list, analyses: list) -> bool:
    """
    Builds the HTML newsletter payload and delivers it via SMTP TLS protocol.

    :param prices: List of stock price dictionaries.
    :param news: List of raw news article dictionaries.
    :param analyses: List of AI analysis dictionaries from Gemini.
    :return: Boolean indicating whether email delivery succeeded.
    """
    if not all([SMTP_SERVER, SENDER_EMAIL, SENDER_PASSWORD, RECEIVER_EMAIL]):
        logging.warning("SMTP configuration parameters missing in environment. Skipping email dispatch.")
        return False

    # Parse comma-separated string into a clean recipient email list
    receiver_list = [email.strip() for email in RECEIVER_EMAIL.split(",") if email.strip()]
    
    if not receiver_list:
        logging.warning("Recipient email list is empty after parsing. Skipping dispatch.")
        return False

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"[Bản Tin EOD] Báo Cáo Thị Trường - {datetime.now().strftime('%d/%m/%Y')}"
        msg["From"] = SENDER_EMAIL
        msg["To"] = ", ".join(receiver_list) 

        html_content = build_html_template(prices, news, analyses)
        msg.attach(MIMEText(html_content, "html"))

        logging.info(f"Connecting to remote SMTP mail server at {SMTP_SERVER}:{SMTP_PORT}...")
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT, timeout=15.0) as server:
            server.starttls()
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
            server.sendmail(SENDER_EMAIL, receiver_list, msg.as_string())
            
        logging.info(f"HTML Newsletter successfully dispatched to {len(receiver_list)} recipient(s).")
        return True

    except smtplib.SMTPAuthenticationError as auth_err:
        logging.error(f"SMTP authentication failed. Verify SENDER_EMAIL and SENDER_PASSWORD credentials: {auth_err}")
        return False
    except smtplib.SMTPException as smtp_err:
        logging.error(f"SMTP protocol error during email dispatch: {smtp_err}")
        return False
    except Exception as e:
        logging.error(f"Unexpected operational error during email transmission: {e}")
        return False