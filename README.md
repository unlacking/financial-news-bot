# Financial News Bot

An automated, data-driven market intelligence pipeline designed to periodically harvest live financial news and Vietnamese stock market pricing. The system passes raw content through a deterministic AI engine for real-time translation, dense tracking summarization, and sentiment profiling before syncing all datasets to a cloud database and routing alerts directly to Telegram and Email.

---

## Core Features

- **Automated Data Harvesting:** Periodically parses financial news streams (CafeF, VnEconomy) and dynamically tracks targeted stock market metrics.
- **Deterministic AI Extraction:** Evaluates text data using the Google Gen AI SDK to dynamically map structural financial metadata.
- **Dual-Table Cloud Synchronization:** Normalizes unstructured data layouts on-the-fly and pushes payloads via native HTTP streaming directly to Supabase table instances (`financial_news`, `gemini_responses`, `stock_prices`).
- **Telegram Notification Bot:** Processes active pricing thresholds and AI sensitivity metrics to route immediate intraday market alerts and End-of-Day (EOD) newsletter summaries via Telegram.
- **Scheduled Email Distribution:** Engineered to bundle End-of-Day newsletter logs into cleanly formatted summary matrices dispatched directly via secure Email (Google SMTP).

---

## Tech Stack & Core Dependencies

| Component | Technology / Library | Purpose |
| :--- | :--- | :--- |
| **Runtime** | Python 3.11.9 | Core execution environment |
| **News Parser** | `feedparser` | Fetching and parsing live financial RSS streams |
| **Stock Data** | `vnstock` | Interrogating real-time Vietnamese stock market metrics |
| **Database** | Supabase (PostgREST API) | Real-time cloud storage & relational schema hosting |
| **AI Processor** | Google Gen AI SDK (`gemini-2.5-flash`) | Structured metadata analysis and translation |
| **HTTP Transport** | `httpx` | Fast, asynchronous native REST requests to cloud endpoints |
| **Reporting** | `smtplib` / `email` | Secure automated HTML newsletter dispatch via Google SMTP |
| **Validation** | `pydantic` | Enforces runtime structural schema contracts on AI payloads |
| **Scheduling** | `schedule` | Embedded background daemon for precise event loop automation |
| **Secrets** | `python-dotenv` | Safeguards private environment strings via locally managed `.env` |

---

## Installation & Environment Setup

### 1. Repository Initialization
Ensure you have **Python 3.11.9** and **Git** installed on your workstation.

```bash
# Clone the remote repository
git clone [https://github.com/unlacking/financial-news-bot.git](https://github.com/unlacking/financial-news-bot.git)
cd financial-news-bot

# Initialize isolated virtual environment
python -m venv .venv311

# Activate environment (Windows PowerShell)
.venv311\Scripts\Activate.ps1
# Activate environment (Mac/Linux)
source .venv311/bin/activate

# Install locked dependencies
pip install -r requirements.txt