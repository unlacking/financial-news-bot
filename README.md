# Financial News Bot

An automated, data-driven market intelligence pipeline designed to periodically harvest live financial news and Vietnamese stock market pricing. The system passes raw content through a deterministic AI engine for real-time translation, dense tracking summarization, and sentiment profiling before syncing all datasets to a cloud database and routing alerts directly to Telegram and Email.

---

## Architecture Overview

```text
[ External RSS / Price Sources ]
         │
         ▼
  [ news_collector.py ] & [ price_collector.py ]
         │
         ▼
   [ main.py / Orchestrator ]
         │
         ├── 1. Cloud DB Cache Inspector (filter_unprocessed_news)
         │      └── Fast bulk query via PostgREST to filter healthy processed links
         │
         ├── 2. Gemini AI Analysis Engine (ai_processor.py)
         │      └── process_news_batch() --> Rate-limited execution via gemini-3.5-flash
         │      └── Pydantic Schema Validation (Validation against live listed tickers)
         │
         ├── 3. Database Persistence Layer (database_client.py)
         │      └── Single HTTP Bulk POST Upsert (?on_conflict=link) to Supabase
         │
         └── 4. Outbound Alert & Report Delivery
                ├── [ formatter.py ] --> Formats clean ASCII digests (< 3800 chars)
                ├── [ telegram_bot.py ] --> Outbound Telegram Alerts & Long-polling CLI Bot
                └── [ email_client.py ] --> Renders Responsive HTML Email via SMTP TLS (Port 587)

```

---

## Core Features

* **Automated Data Harvesting:** Periodically parses financial news feeds (CafeF, VnEconomy, Vietstock) and dynamically tracks stock price metrics using `vnstock`.
* **Deterministic AI Extraction:** Evaluates text data using the Google Gen AI SDK (`gemini-3.5-flash`) to dynamically map structural financial metadata and sentiment direction.
* **Smart Cloud Cache Filtering:** Uses single-request PostgREST `in.()` queries to skip previously analyzed articles while automatically re-queuing historical error rows for healing.
* **Dual-Table Cloud Synchronization:** Normalizes schema columns on-the-fly and pushes bulk payloads via native HTTP POST upserts (`?on_conflict=link`) directly to Supabase (`financial_news`, `gemini_responses`, `stock_prices`).
* **Telegram Notification Bot:** Sends intraday price/news alerts and supports interactive CLI commands (`/status`, `/trigger`, `/price`, `/news`).
* **Scheduled Email Distribution:** Bundles End-of-Day (EOD) summary matrices into clean, responsive HTML templates dispatched securely via Google SMTP TLS (Port 587).

---

## Tech Stack & Core Dependencies

| Component | Technology / Library | Purpose |
| --- | --- | --- |
| **Runtime** | Python 3.11+ | Core execution environment |
| **News Parser** | `feedparser` | Fetching and parsing live financial RSS streams |
| **Stock Data** | `vnstock` | Interrogating real-time Vietnamese stock market metrics |
| **Database** | Supabase (PostgREST API) | Real-time cloud storage & relational schema hosting |
| **AI Processor** | Google Gen AI SDK (`gemini-3.5-flash`) | Structured metadata analysis, ticker validation, and summary translation |
| **HTTP Transport** | `httpx` | Fast, native REST requests to Supabase and Telegram endpoints |
| **Reporting** | `smtplib` / `email` | Secure automated HTML newsletter dispatch via Google SMTP (Port 587) |
| **Validation** | `pydantic` | Enforces runtime structural schema contracts on AI payloads |
| **Telegram Bot** | `python-telegram-bot` | Outbound alerts & interactive long-polling command handlers |
| **Secrets** | `python-dotenv` | Safeguards private environment strings via locally managed `.env` |

---

## Module Structure

* `main.py` — Central pipeline orchestrator and execution scheduler.
* `src/ai_processor.py` — Gemini API integration, Pydantic output validation, ticker set intersection, and sub-batch queue pacing engine.
* `src/database_client.py` — Supabase database interface handling schema realignment, bulk PostgREST upserts, and read queries.
* `src/news_collector.py` — RSS feed scraper and text cleaner.
* `src/price_collector.py` — Stock price metric scraper powered by `vnstock`.
* `src/formatter.py` — ASCII emergency alert builder and newsletter chunk-splitter.
* `src/telegram_bot.py` — Outbound message dispatcher and interactive Telegram CLI bot handlers (`/status`, `/trigger`, `/price`, `/news`).
* `src/email_client.py` — HTML template generator and SMTP email sender.

---

## Installation & Environment Setup

### 1. Repository Initialization

Ensure you have **Python 3.11.9** and **Git** installed on your workstation.

```bash
# Clone the remote repository
git clone [https://github.com/unlacking/financial-news-bot.git](https://github.com/unlacking/financial-news-bot.git)
cd financial-news-bot

# Initialize isolated virtual environment
python -m venv .venv

# Activate environment (Windows PowerShell)
.venv\Scripts\Activate.ps1
# Activate environment (Mac/Linux)
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

```

### 2. Environment Configuration (.env)

Create a `.env` file in the project root with the following keys (there is a '.env.example' included to help you):

```env
GEMINI_VERSION=gemini-3.5-flash
SUPABASE_URL=[https://your-supabase-project.supabase.co](https://your-supabase-project.supabase.co)
SUPABASE_SERVICE_ROLE_KEY=your_service_role_key
SUPABASE_NEWS_TABLE=financial_news
SUPABASE_STOCKS_TABLE=stock_prices
SUPABASE_GEMINI_TABLE=gemini_responses
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
TELEGRAM_GROUP_CHAT_ID=your_telegram_chat_id
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SENDER_EMAIL=your_email@gmail.com
SENDER_PASSWORD=your_app_password
RECEIVER_EMAIL=recipient1@gmail.com,recipient2@gmail.com

```

### 3. Running the Pipeline

```bash
# Run the main pipeline execution loop
python main.py

# Run the interactive Telegram CLI bot listener
python -m src.telegram_bot

```

```

For quick reference on setting up Gemini API calls in Python, check out this [Gemini 3.5 API Python Tutorial](https://www.youtube.com/watch?v=I4kAgfEbmTk).

This video provides a straightforward walkthrough of initializing the SDK, handling environment keys, and making requests with the Gemini 3.5 model series in Python.
http://googleusercontent.com/youtube_content/1

```