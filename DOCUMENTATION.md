# Stock News Monitor - Technical Documentation

This document provides technical details for developers and AI agents working on this project.

## Architecture Overview

The Stock News Monitor is a Telegram bot that tracks stock news from **multiple sources** (Finviz and StockAnalysis), classifies sentiment using FinBERT, and sends updates to users via parallel fetching for better performance.

```
User Portfolio → Multi-Source Scrapers (Finviz + StockAnalysis, parallel) → News Items
                                                                               ↓
                                                            FinBERT Classifier → Sentiment Analysis
                                                                               ↓
User ← Telegram Bot ← Formatted Messages ← Filtered Relevant News ←──────────┘
  ↓
Portfolio Updates (add/remove stocks via chat commands)
```

## Data Flow

### News Monitoring Flow
1. **Portfolio Loading**: `helpers.load_portfolio()` reads stock tickers from `json/portfolio.json`
2. **Cache Loading**: `helpers.load_news_cache()` loads previously sent headlines from `data/news_cache.json`
3. **Multi-Source News Fetching**: Two scrapers fetch news in parallel using ThreadPoolExecutor:
   - `FinvizScraper` - Finviz.com
   - `StockAnalysisScraper` - StockAnalysis.com
   - Both parse HTML with BeautifulSoup, results merged into single stream
   - Parallel execution reduces fetch time to max(finviz_time, stockanalysis_time) instead of sum
4. **Date Filtering**: Only news from today is processed (ignores older news)
5. **Within-Fetch Duplicate Detection**: Same headline from different sources is deduplicated
6. **Sentiment Analysis**: `SentimentClassifier` (FinBERT) classifies each headline as positive/negative/neutral
7. **Relevance Filtering**: Only relevant news (positive/negative with confidence ≥ 50%) is kept
8. **Cross-Time Duplicate Filtering**: `helpers.filter_new_news()` removes headlines that were already sent
9. **Delivery**: Formatted messages sent via Telegram bot to user's chat
10. **Cache Update**: `helpers.save_news_cache()` saves new headlines to prevent future duplicates

### Telegram Bot Flow
1. **User Commands**: `/add TICKER`, `/remove TICKER`, `/list`, `/help`, `/status`
2. **Portfolio Updates**: Commands modify `json/portfolio.json` in real-time
3. **Periodic Updates**: Background task fetches news every N seconds (configurable, default: 30s)
4. **On-Demand Updates**: `/status` command triggers immediate news fetch independent of periodic checks
5. **Message Formatting**: News grouped by ticker, with sentiment emoji and confidence scores

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
  - `load_telegram_config()`: Load bot token and chat ID from environment variables and config file
  - `fetch_and_classify_news()`: Orchestrates multi-source scraping + sentiment analysis + date filtering (today only)
    - Fetches from both sources (Finviz, StockAnalysis) in parallel using ThreadPoolExecutor
    - Deduplicates headlines from different sources within same fetch
    - Filters news to today only (timezone-aware)
    - Classifies sentiment and filters by relevance
  - `setup_bot()`: Initialize Telegram bot with callbacks
  - `load_news_cache()`: Load previously sent headlines from cache
  - `save_news_cache()`: Save sent headlines to cache
  - `filter_new_news()`: Filter out news that was already sent
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

### resources/stockanalysis_scraper.py
- **Purpose**: Fetch latest stock news from StockAnalysis.com
- **Class**: `StockAnalysisScraper`
  - `__init__(timeout)`: Initialize with HTTP timeout
  - `fetch_news(ticker, max_news)`: Scrape news for single ticker
  - `fetch_multiple_tickers(tickers, max_news_per_ticker)`: Batch scraping
- **Data Class**: Reuses `NewsItem` from finviz_scraper
- **URL Pattern**: `https://stockanalysis.com/stocks/{ticker}/` (lowercase ticker)
- **HTML Parsing**: Looks for `<div id="news">` or `<section class="news">`
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
- **Modified by**: Telegram bot commands (`/add`, `/remove`)
- **Note**: Check interval configuration moved to `telegram_config.json`

### json/telegram_config.json
- **Purpose**: Telegram bot settings (credentials now in .env)
- **Fields**:
  - `polling_interval_seconds`: How often to poll Telegram API (default: 2s)
  - `news_check_interval_seconds`: How often to fetch news (default: 30s)
- **Security**: Bot token and chat ID moved to `.env` file for better security

### .env
- **Purpose**: Sensitive credentials (gitignored)
- **Fields**:
  - `TELEGRAM_BOT_TOKEN`: Telegram Bot API token (from @BotFather)
  - `TELEGRAM_CHAT_ID`: Your Telegram chat ID (where messages are sent)
- **Security**: **NEVER commit this file to git** - added to .gitignore
- **Setup**: Copy from `.env.example` and fill in your credentials

### json/paths.json
- **Purpose**: Central configuration for all file paths
- **Keys**:
  - `portfolio`: Path to portfolio.json
  - `telegram_config`: Path to telegram_config.json
  - `ticker_suggestions`: Path to ticker suggestions mapping
  - `news_cache`: Path to cached news headlines (prevents duplicate sending)
  - `model_cache`: Directory for FinBERT model cache
- **Rule**: ALL file/folder paths in the project come from this file

### data/news_cache.json
- **Purpose**: Tracks previously sent news headlines to prevent duplicates
- **Fields**:
  - `sent_headlines`: List of headline strings that have been sent to user
  - `last_updated`: ISO timestamp of last cache update
- **Behavior**:
  - Headlines are compared exactly (case-sensitive)
  - Cache persists across bot restarts
  - Prevents sending same news multiple times when it appears on Finviz
  - Automatically created on first run

## Design Decisions

### Why Multi-Source HTML Scraping (Not APIs)?
- **No API Keys Required**: Free access to news data from Finviz and StockAnalysis
- **Broader Coverage**: Multiple sources reduce chance of missing important updates
- **Real-Time**: Latest news as soon as published
- **Rich Metadata**: Source, timestamp, URL from HTML structure
- **Graceful Degradation**: If one source fails, the other continues working
- **Parallel Fetching**: ThreadPoolExecutor reduces total fetch time significantly
- **Trade-off**: May break if any site changes HTML structure (handled per-source with try-except)

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
- `requests`: HTTP client for multi-source news scraping (Finviz, StockAnalysis)
- `beautifulsoup4`: HTML parsing for news extraction from all sources
- `lxml`: XML/HTML parser backend for BeautifulSoup (faster than default)
- `python-telegram-bot`: Async Telegram Bot API client
- `transformers`: HuggingFace library for FinBERT
- `torch`: PyTorch (FinBERT backend)
- `python-dotenv`: Load environment variables from .env file

### Development
- `pytest`: Test runner and framework
- `ipykernel`: Jupyter notebook support for interactive testing
- `ruff`: Fast Python linter and formatter

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

### 3. Set Up Environment Variables
1. Copy the example file: `cp .env.example .env`
2. Edit `.env` and add your credentials:
   ```env
   TELEGRAM_BOT_TOKEN=your_bot_token_here
   TELEGRAM_CHAT_ID=your_chat_id_here
   ```

### 4. Configure Portfolio
Edit `json/portfolio.json` and add your stocks:
```json
{
  "stocks": ["AAPL", "MSFT", "GOOGL", "TSLA"],
  "last_check": null
}
```

### 5. Configure Check Intervals (Optional)
Edit `json/telegram_config.json`:
```json
{
  "polling_interval_seconds": 2,
  "news_check_interval_seconds": 30
}
```

### 6. Run the Bot
```bash
uv run python main.py
```

## Current Features

### News Monitoring
- **Multi-source scraping**: Fetches news from Finviz and StockAnalysis in parallel
- **Parallel fetching**: ThreadPoolExecutor with 2 workers for faster performance
- HTML parsing with BeautifulSoup for both sources
- Timestamp extraction and parsing
- Concurrent fetching for all portfolio stocks across both sources
- **Graceful error handling**: If one source fails, the other continues working
- **Date filtering**: Only today's news is processed (ignores older news)
- **Two-level duplicate detection**:
  - Within-fetch: Deduplicates same headline from different sources
  - Cross-time: Tracks sent headlines to prevent re-sending same news
- **News cache**: Persistent cache across bot restarts

### Sentiment Analysis
- FinBERT-based classification (positive/negative/neutral)
- Confidence scores for each prediction
- Relevance filtering (removes neutral news with <50% confidence)
- Batch processing support

### Telegram Bot
- Interactive commands for portfolio management
- Real-time stock additions/removals via chat
- Ticker validation before adding to portfolio (prevents invalid symbols)
- Smart suggestions for common ticker mistakes (SP500→SPY, NASDAQ→QQQ, etc.)
- Formatted news updates with emoji indicators
- **Fast periodic updates**: Checks every 30 seconds by default (configurable)
- **Immediate startup check**: Sends news immediately on bot start
- On-demand news fetching via `/status` command (independent of polling)
- Graceful error handling and logging
- Secure credential management via `.env` file

## Future Enhancements

Potential features to add:

- ✅ ~~**News Deduplication**: Cache seen news items to avoid repeats~~ (IMPLEMENTED)
- ✅ ~~**Date Filtering**: Only show today's news~~ (IMPLEMENTED)
- ✅ ~~**Fast Updates**: Check every 30 seconds instead of 60 minutes~~ (IMPLEMENTED)
- ✅ ~~**Multi-Source Scraping**: Aggregate news from multiple sources~~ (IMPLEMENTED - Finviz, StockAnalysis with parallel fetching)
- **Additional News Sources**: Add more scrapers (Bloomberg, Reuters, CNBC, etc.)
- **Price Alerts**: Integrate price data and alert on movements
- **Custom Filters**: User-defined keywords or sentiment thresholds
- **Historical Analysis**: Track sentiment trends over time
- **Multi-User Support**: Different portfolios per chat_id
- **Database**: Store news history in SQLite for analysis
- **Web Dashboard**: Flask/FastAPI frontend for visualization
- **Cache Cleanup**: Auto-clear old headlines from cache (>7 days)

When adding features, follow the established patterns documented above.

## Gotchas and Pitfalls

1. **Never hardcode paths**: Even for Telegram config - use `json/paths.json`
2. **All imports at top**: No lazy imports inside functions
3. **No module-level code in helpers.py**: Only function definitions
4. **Async everywhere**: Telegram bot operations must be `async`/`await`
5. **Type hints required**: All public functions must have type hints
6. **FinBERT is large**: ~500MB model download on first run
7. **Rate limiting**: Finviz may rate-limit if too many requests too fast
8. **Credentials in .env**: Never commit `.env` file - use `.env.example` template
9. **News cache grows**: `data/news_cache.json` accumulates headlines over time (future: auto-cleanup)
10. **Check interval**: Set `news_check_interval_seconds` carefully - too low may hit rate limits
11. **Ticker symbols must be exact**: "SP500" is invalid, use "SPY" for S&P 500 ETF. Common mistakes:
   - ❌ SP500 → ✅ SPY (S&P 500)
   - ❌ NASDAQ → ✅ QQQ (Nasdaq-100)
   - ❌ DOW → ✅ DIA (Dow Jones)
12. **Multi-source scraping trade-offs**: Three sources means more comprehensive coverage but:
   - Three HTTP requests per ticker (slower than single source)
   - Any source HTML change only affects that source (graceful degradation)
   - Duplicate headlines are automatically filtered within each fetch

## Troubleshooting

### Bot doesn't receive messages
- Check bot token is correct
- Verify chat_id matches your Telegram user
- Ensure you've sent `/start` to the bot first

### News not fetching
- Check news sources are accessible (test scrapers standalone):
  - `uv run python resources/finviz_scraper.py`
  - `uv run python resources/stockanalysis_scraper.py`
- Verify ticker symbols are valid
- Check logs for HTTP errors (sources fail gracefully, so check which source is working)

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
- Search ticker on Finviz or StockAnalysis first if unsure

## Testing the System

### Test Individual Scrapers
```bash
# Test Finviz scraper
uv run python resources/finviz_scraper.py

# Test StockAnalysis scraper
uv run python resources/stockanalysis_scraper.py
```

### Test Sentiment Classifier
```bash
uv run python resources/sentiment_classifier.py
```

### Test Telegram Bot (Interactive)
```bash
uv run python resources/telegram_bot.py
```

### Run All Unit Tests
```bash
# Run all tests
uv run pytest -v

# Run specific test files
uv run pytest tests/test_finviz_scraper.py -v
uv run pytest tests/test_stockanalysis_scraper.py -v
uv run pytest tests/test_helpers.py -v
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
