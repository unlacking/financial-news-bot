# Financial News Bot

A system designed to periodically fetch financial news (via RSS) and stock prices, feed the data into Gemini AI for summarization and sentiment analysis, apply alert logic (price fluctuations, negative news, sensitive keywords), and route the final reports to a Telegram channel/group and Email.

---

## Main Features

- **Data Fetching:** Automatically parses financial RSS feeds and updates stock market changes using `vnstock`.
- **AI Processing:** Integrates Google Gen AI SDK (Gemini Flash) to translate, summarize, and score sentiment (Positive / Negative / Neutral).
- **Alert Mechanism:** Triggers immediate alerts if stock prices swing dramatically or if critical/sensitive keywords are detected.
- **Multi-channel Delivery:** - Quick summary and urgent alerts via **Telegram Bot**.
  - Scheduled detailed reports via **Email (Google SMTP)**.

---

## Tech Stack & Tools

| Component | Tool / Library | Purpose |
| :--- | :--- | :--- |
| **Language** | Python 3.11.9 | Core programming language |
| **News Parser** | `feedparser` | Fetching financial RSS streams |
| **Stock Data** | `vnstock` | Fetching stock metrics and charts |
| **AI Processing** | Google Gen AI SDK | Gemini Flash model for automated analysis |
| **Reporting** | `python-telegram-bot` | Sending automated Telegram notifications |
| **Scheduling** | `schedule` / `cron` | Running tasks background periodically |
| **Secrets** | `python-dotenv` | Securing private API keys via `.env` |

---

## Installation & Setup

### 1. Environment Setup
Make sure you have **Python 3.11.9** and **Git** installed on your machine.

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