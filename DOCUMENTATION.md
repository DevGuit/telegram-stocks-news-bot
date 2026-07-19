# Stock News Monitor - Technical Documentation

This document provides technical details for developers and AI agents working on this project.

## Architecture Overview

The Stock News Monitor is a Telegram bot that tracks stock news from Finviz, classifies sentiment using FinBERT, and sends updates to users.

```
User Portfolio → Finviz Scraper → News Items → FinBERT Classifier → Sentiment Analysis
                                                                             ↓
User ← Telegram Bot ← Formatted Messages ← Filtered Relevant News ←─────────┘
  ↓
Portfolio Updates (add/remove stocks via chat commands)
```

## Data Flow

### News Monitoring Flow
1. **Portfolio Loading**: `helpers.load_portfolio()` reads stock tickers from `json/portfolio.json`
2. **News Fetching**: `FinvizScraper` sends HTTP requests to Finviz, parses HTML with BeautifulSoup
3. **Sentiment Analysis**: `SentimentClassifier` (FinBERT) classifies each headline as positive/negative/neutral
4. **Filtering**: Only relevant news (positive/negative with confidence ≥ 50%) is kept
5. **Delivery**: Formatted messages sent via Telegram bot to user's chat

### Telegram Bot Flow
1. **User Commands**: `/add TICKER`, `/remove TICKER`, `/list`, `/help`
2. **Portfolio Updates**: Commands modify `json/portfolio.json` in real-time
3. **Periodic Updates**: Background task fetches news every N minutes (configurable)
4. **Message Formatting**: News grouped by ticker, with sentiment emoji and confidence scores

## Module Breakdown

### main.py
- **Purpose**: Entry point - starts Telegram bot with periodic news monitoring
- **Responsibilities**: Orchestration only - no business logic
- **Pattern**: `from helpers import *` for clean access to helper functions
- **Async**: Uses `asyncio` to run bot polling and periodic news fetching concurrently

### helpers.py
- **Purpose**: Bridge between main.py and resources/ classes
- **Key Functions**:
  - `load_paths()`: Loads file paths from `json/paths.json` (ONLY place that hardcodes a path)
  - `setup_logging()`: Configures application logging
  - `load_portfolio()` / `save_portfolio()`: Manage stock ticker list
  - `load_telegram_config()`: Load bot token and chat ID
  - `fetch_and_classify_news()`: Orchestrates scraping + sentiment analysis
  - `setup_bot()`: Initialize Telegram bot with callbacks
- **Pattern**: Functions instantiate classes from `resources/` inside function body
- **Exports**: Defines `__all__` for clean wildcard import in main.py

### resources/finviz_scraper.py
- **Purpose**: Fetch latest stock news from Finviz
- **Class**: `FinvizScraper`
  - `__init__(timeout)`: Initialize with HTTP timeout
  - `fetch_news(ticker, max_news)`: Scrape news for single ticker
  - `fetch_multiple_tickers(tickers, max_news_per_ticker)`: Batch scraping
  - `_parse_timestamp(date_str, time_str)`: Parse Finviz datetime format
- **Data Class**: `NewsItem` - timestamp, headline, source, url, ticker
- **Dependencies**: `requests` for HTTP, `beautifulsoup4` for HTML parsing
- **Runnable**: Contains `if __name__ == "__main__":` example

### resources/sentiment_classifier.py
- **Purpose**: Financial sentiment analysis using FinBERT
- **Class**: `SentimentClassifier`
  - `__init__(model_cache_dir)`: Load FinBERT model (ProsusAI/finbert)
  - `classify(text)`: Classify single headline → SentimentResult
  - `classify_batch(texts)`: Batch classification
  - `is_relevant(text, threshold)`: Filter neutral/low-confidence news
- **Data Class**: `SentimentResult` - label, score, label_scores dict
- **Model**: Pre-trained FinBERT (ProsusAI/finbert) from HuggingFace
- **Device**: Auto-detects CUDA GPU if available, falls back to CPU
- **Dependencies**: `torch`, `transformers` (HuggingFace)
- **Runnable**: Contains `if __name__ == "__main__":` example

### resources/telegram_bot.py
- **Purpose**: Handle user interactions and deliver news updates
- **Class**: `StockNewsBot`
  - `__init__(bot_token, portfolio_path, callbacks, model_cache_dir)`: Initialize with token, path, and model cache
  - Command handlers: `/start`, `/help`, `/list`, `/add`, `/remove`, `/status`
  - `send_news_update(chat_id, news_items)`: Format and send news messages
  - `cmd_status()`: On-demand news fetch (independent of periodic polling)
  - `run_polling()`: Start bot in polling mode
- **Commands**:
  - `/add TICKER` - Add stock to portfolio (validates ticker via Finviz before adding)
  - `/remove TICKER` - Remove stock from portfolio
  - `/list` - View current portfolio
  - `/status` - Fetch latest news immediately (on-demand, independent of polling)
  - `/help` - Show help message
- **Ticker Validation**: Before adding a stock, the bot validates it by checking if Finviz has a page for it
- **Smart Suggestions**: When validation fails, suggests correct alternatives (e.g., SP500 → suggests SPY, VOO, IVV)
- **Message Format**: Grouped by ticker, sentiment emoji, confidence %, source, timestamp
- **Dependencies**: `python-telegram-bot` (async version)
- **Runnable**: Contains `if __name__ == "__main__":` example

### json/portfolio.json
- **Purpose**: User's stock watchlist
- **Fields**:
  - `stocks`: List of ticker symbols (e.g., ["AAPL", "MSFT", "GOOGL"])
  - `last_check`: ISO timestamp of last news fetch
  - `check_interval_minutes`: How often to check for news
- **Modified by**: Telegram bot commands (`/add`, `/remove`)

### json/telegram_config.json
- **Purpose**: Telegram bot credentials and settings
- **Fields**:
  - `bot_token`: Telegram Bot API token (from @BotFather)
  - `chat_id`: Your Telegram chat ID (where messages are sent)
  - `polling_interval_seconds`: How often to poll Telegram API
  - `news_check_interval_minutes`: How often to fetch news
- **Security**: **NEVER commit this file to git** - contains secrets

### json/paths.json
- **Purpose**: Central configuration for all file paths
- **Keys**:
  - `portfolio`: Path to portfolio.json
  - `telegram_config`: Path to telegram_config.json
  - `news_cache`: Path to cached news (future use)
  - `model_cache`: Directory for FinBERT model cache
- **Rule**: ALL file/folder paths in the project come from this file

## Design Decisions

### Why Finviz HTML Scraping (Not API)?
- **No API Key Required**: Free access to news data
- **Real-Time**: Latest news as soon as published
- **Rich Metadata**: Source, timestamp, URL from HTML structure
- **Trade-off**: May break if Finviz changes HTML structure

### Why FinBERT Instead of Generic BERT?
- **Financial Domain**: Pre-trained on financial news corpus
- **Better Accuracy**: Understands financial terminology (bearish, bullish, earnings, etc.)
- **Three Classes**: Positive, negative, neutral (not just positive/negative)
- **Production Ready**: No fine-tuning required

### Why Polling Mode Instead of Webhooks?
- **Simplicity**: No public server or SSL certificate required
- **Local Development**: Can run on laptop without port forwarding
- **Trade-off**: Slight delay in receiving commands (2-second polling interval)

### Why Async (asyncio) Architecture?
- **Concurrent Operations**: Bot polling + periodic news fetching run simultaneously
- **Non-Blocking**: News fetching doesn't block command handling
- **Telegram Library**: `python-telegram-bot` v20+ is async-first

## Dependencies

### Runtime
- `requests`: HTTP client for Finviz scraping
- `beautifulsoup4`: HTML parsing for news extraction
- `python-telegram-bot`: Async Telegram Bot API client
- `transformers`: HuggingFace library for FinBERT
- `torch`: PyTorch (FinBERT backend)

### Development
- `pytest`: Test runner and framework (future)
- `ipykernel`: Jupyter notebook support for interactive testing

## Configuration Setup

### 1. Create Telegram Bot
1. Message @BotFather on Telegram
2. Send `/newbot` and follow prompts
3. Copy bot token to `json/telegram_config.json`

### 2. Get Your Chat ID
1. Message your bot
2. Visit: `https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates`
3. Find your `chat.id` in the JSON response
4. Add to `json/telegram_config.json`

### 3. Configure Portfolio
Edit `json/portfolio.json` and add your stocks:
```json
{
  "stocks": ["AAPL", "MSFT", "GOOGL", "TSLA"],
  "last_check": null,
  "check_interval_minutes": 60
}
```

### 4. Run the Bot
```bash
uv run python main.py
```

## Current Features

### News Monitoring
- Automatic Finviz scraping for multiple tickers
- HTML parsing with BeautifulSoup
- Timestamp extraction and parsing
- Concurrent fetching for all portfolio stocks

### Sentiment Analysis
- FinBERT-based classification (positive/negative/neutral)
- Confidence scores for each prediction
- Relevance filtering (removes neutral news)
- Batch processing support

### Telegram Bot
- Interactive commands for portfolio management
- Real-time stock additions/removals via chat
- Ticker validation before adding to portfolio (prevents invalid symbols)
- Smart suggestions for common ticker mistakes (SP500→SPY, NASDAQ→QQQ, etc.)
- Formatted news updates with emoji indicators
- Periodic background news monitoring (configurable interval)
- On-demand news fetching via `/status` command (independent of polling)
- Graceful error handling and logging

## Future Enhancements

Potential features to add:

- **News Deduplication**: Cache seen news items to avoid repeats
- **Price Alerts**: Integrate price data and alert on movements
- **Custom Filters**: User-defined keywords or sentiment thresholds
- **Historical Analysis**: Track sentiment trends over time
- **Multi-User Support**: Different portfolios per chat_id
- **Database**: Store news history in SQLite for analysis
- **Web Dashboard**: Flask/FastAPI frontend for visualization

When adding features, follow the established patterns documented above.

## Gotchas and Pitfalls

1. **Never hardcode paths**: Even for Telegram config - use `json/paths.json`
2. **All imports at top**: No lazy imports inside functions
3. **No module-level code in helpers.py**: Only function definitions
4. **Async everywhere**: Telegram bot operations must be `async`/`await`
5. **Type hints required**: All public functions must have type hints
6. **FinBERT is large**: ~500MB model download on first run
7. **Rate limiting**: Finviz may rate-limit if too many requests too fast
8. **Telegram tokens are secrets**: Never commit `telegram_config.json`
9. **Ticker symbols must be exact**: "SP500" is invalid, use "SPY" for S&P 500 ETF. Common mistakes:
   - ❌ SP500 → ✅ SPY (S&P 500)
   - ❌ NASDAQ → ✅ QQQ (Nasdaq-100)
   - ❌ DOW → ✅ DIA (Dow Jones)

## Troubleshooting

### Bot doesn't receive messages
- Check bot token is correct
- Verify chat_id matches your Telegram user
- Ensure you've sent `/start` to the bot first

### News not fetching
- Check Finviz is accessible (test scraper standalone)
- Verify ticker symbols are valid
- Check logs for HTTP errors

### Sentiment always neutral
- FinBERT may need warm-up (first prediction slow)
- Some headlines are genuinely neutral
- Adjust `relevance_threshold` if too aggressive

### High memory usage
- FinBERT model stays in RAM (~1GB)
- Reduce batch size or use CPU instead of GPU
- Close other applications

### Invalid ticker error when adding stock
- Bot validates tickers by checking Finviz
- Use exact ticker symbols (e.g., "AAPL" not "Apple")
- For indices, use ETF tickers: SPY (S&P 500), QQQ (Nasdaq), DIA (Dow)
- The bot will suggest correct alternatives for common mistakes:
  - `/add SP500` → Suggests: SPY, VOO, IVV
  - `/add NASDAQ` → Suggests: QQQ, ONEQ
  - `/add BITCOIN` → Suggests: BITO, GBTC
- Search ticker on Yahoo Finance or Finviz first if unsure

## Testing the System

### Test Finviz Scraper
```bash
uv run python resources/finviz_scraper.py
```

### Test Sentiment Classifier
```bash
uv run python resources/sentiment_classifier.py
```

### Test Telegram Bot (Interactive)
```bash
uv run python resources/telegram_bot.py
```

### Full System Test
```bash
uv run python main.py
```

Then interact via Telegram:
1. Send `/start` to your bot
2. Send `/add AAPL`
3. Wait for news update
4. Send `/list` to confirm
5. Press Ctrl+C to stop
