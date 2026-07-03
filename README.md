# Financial News Bot

[Tiếng Việt bên dưới]

A system designed to periodically fetch financial news (via RSS) and stock prices, feed the data into Gemini AI for summarization and sentiment analysis, apply alert logic (price fluctuations, negative news, sensitive keywords), and route the final reports to a Telegram channel/group and Email.

Hệ thống định kỳ thu thập tin tức tài chính (qua RSS) và giá cổ phiếu, đưa tin vào Gemini để tóm tắt và đánh giá cảm xúc thị trường, áp dụng các luật cảnh báo (biến động giá, tin tiêu cực, từ khóa nhạy cảm), rồi tự động gửi kết quả về một kênh/nhóm Telegram và Email.

---

## Main Features | Tính Năng Chính

- **Data Fetching / Thu thập dữ liệu:** Automatically parses financial RSS feeds and updates stock market changes using `vnstock`. (Tự động quét các luồng RSS tài chính và cập nhật biến động thị trường).
- **AI Processing / Xử lý AI:** Integrates Google Gen AI SDK (Gemini Flash) to translate, summarize, and score sentiment (Positive / Negative / Neutral). (Sử dụng Gemini Flash để tóm tắt và phân tích sắc thái tin tức).
- **Alert Mechanism / Hệ thống cảnh báo:** Triggers immediate alerts if stock prices swing dramatically or if critical/sensitive keywords are detected. (Kích hoạt cảnh báo tức thời khi giá biến động mạnh hoặc gặp từ khóa nhạy cảm).
- **Multi-channel Delivery / Báo cáo đa kênh:** - Quick summary and urgent alerts via **Telegram Bot**. (Gửi báo cáo nhanh và cảnh báo qua Telegram).
  - Scheduled detailed reports via **Email (Google SMTP)**. (Gửi báo cáo chi tiết theo lịch qua Email).

---

## Tech Stack & Tools | Công Cụ Kỹ Thuật

| Component / Thành phần | Tool / Library (Công cụ) | Purpose / Mục đích |
| :--- | :--- | :--- |
| **Language / Ngôn ngữ** | Python 3.11+ | Core programming language |
| **News Parser / Đọc tin tức** | `feedparser` | Fetching financial RSS streams |
| **Stock Data / Giá cổ phiếu** | `vnstock` | Fetching stock metrics and charts |
| **AI Processing / Xử lý AI** | Google Gen AI SDK | Gemini Flash model for automated analysis |
| **Reporting / Báo cáo kết quả** | `python-telegram-bot` | Sending automated Telegram notifications |
| **Scheduling / Lập lịch** | `schedule` / `cron` | Running tasks background periodically |
| **Secrets / Quản lý khóa** | `python-dotenv` | Securing private API keys via `.env` |

---

## Installation & Setup | Hướng Dẫn Cài Đặt

### 1. Environment Setup | Chuẩn bị môi trường
Make sure you have **Python 3.11+** and **Git** installed on your machine.

```bash
# Clone the repository
git clone [https://github.com/unlacking/financial-news-bot.git](https://github.com/unlacking/financial-news-bot.git)
# Move to the application folder
cd .\financial-news-bot

# Create and activate virtual environment
python -m venv .venv311
# Windows:
.venv311\Scripts\Activate.ps1
# Mac/Linux:
source .venv311/bin/activate

# Install dependencies
pip install -r requirements.txt