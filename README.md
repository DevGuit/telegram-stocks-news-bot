# Stock News Monitor

A Telegram bot that monitors stock news, analyzes sentiment with AI, and sends you real-time alerts.

## Features

- **Portfolio Management**: Add/remove stocks and ETFs via Telegram chat
- **News Monitoring**: Manual (`/news`) or automatic (`/run`) news updates
- **AI Sentiment Analysis**: FinBERT analyzes news sentiment (positive/negative/neutral)
- **Smart Validation**: Validates tickers against StockAnalysis.com before adding
- **Multiple Sources**: Aggregates news from TipRanks, Invezz, and other financial sources
- **User Control**: Start/stop automatic polling with `/run` and `/stop` commands
- **Secure**: Credentials stored in `.env` file (never committed to git)

## Quick Start

```bash
# 1. Install
git clone https://github.com/DevGuit/Portfolio_Telegram_Bot.git
cd stock-news-monitor
uv sync

# 2. Set up credentials
cp .env.example .env
# Edit .env with your bot token and chat ID

# 3. Run
uv run python main.py
```

## Setup

### 1. Create Telegram Bot

1. Open Telegram and message [@BotFather](https://t.me/BotFather)
2. Send `/newbot` and follow the prompts to create your bot
3. Copy the bot token (looks like `1234567890:ABCdefGHIjklMNOpqrsTUVwxyz`)

### 2. Get Your Chat ID

1. Start a conversation with your bot (send any message)
2. Visit this URL in your browser (replace `<YOUR_TOKEN>` with your bot token):
   ```
   https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates
   ```
3. Look for `"chat":{"id":123456789}` in the response
4. Copy the number after `"id":` (e.g., `123456789`)

### 3. Configure Environment Variables

1. Copy the example file:
   ```bash
   cp .env.example .env
   ```

2. Edit `.env` with your credentials:
   ```bash
   # Open .env in your text editor
   nano .env  # or vim, code, etc.
   ```

3. Replace the placeholder values:
   ```env
   TELEGRAM_BOT_TOKEN=1234567890:ABCdefGHIjklMNOpqrsTUVwxyz
   TELEGRAM_CHAT_ID=123456789
   ```

   **Important**: Use your actual bot token and chat ID, not the examples above.

### 4. Configure Portfolio and Settings

Edit `json/portfolio.json` with your stocks and ETFs:
```json
{
  "stocks": ["AAPL", "MSFT", "GOOGL"],
  "etf": ["INQQ"]
}
```

**Tip**: You can also manage your portfolio entirely via Telegram commands (`/addstock`, `/addetf`, `/remove`)

Edit `json/telegram_config.json` to adjust check intervals:
```json
{
  "polling_interval_seconds": 2,
  "news_check_interval_seconds": 30
}
```

- `polling_interval_seconds`: How often bot checks for Telegram commands (default: 2s)
- `news_check_interval_seconds`: How often to fetch and send news updates (default: 30s)

## Commands

### Portfolio Management
- `/status` - Show portfolio with StockAnalysis links
- `/list` - View portfolio (validates all tickers and shows valid/invalid)
- `/addstock TICKER` - Add stock (e.g., `/addstock NVDA`)
- `/addetf TICKER` - Add ETF (e.g., `/addetf INQQ`)
- `/remove TICKER` - Remove ticker from portfolio
- `/remove_all` - Remove all tickers
- `/remove_invalid` - Remove all invalid tickers automatically

### News Monitoring
- `/news` - Fetch latest news now (manual, on-demand)
- `/run` - Start automatic news polling (checks every 30 seconds)
- `/stop` - Stop automatic news polling

### Help
- `/start` - Show welcome message with quick start guide
- `/help` - Show all commands with descriptions

## How It Works

1. **Startup**: Bot validates all tickers in portfolio and sends welcome message
2. **Manual Mode**: Use `/news` to fetch latest news on demand
3. **Automatic Mode**: Use `/run` to enable automatic news updates every 30 seconds
4. **News Fetching**: Scrapes StockAnalysis.com which aggregates news from multiple sources (TipRanks, Invezz, etc.)
5. **Sentiment Analysis**: FinBERT analyzes each headline for sentiment (positive/negative/neutral)
6. **Filtering**: Only shows news with strong sentiment (≥50% confidence, non-neutral)
7. **Deduplication**: Tracks sent headlines to avoid duplicate notifications
8. **Date Filter**: Only shows news from today (in your timezone)

## Usage Workflow

1. **Start the bot**: `uv run python main.py`
2. **Check welcome message**: Bot sends portfolio summary to Telegram
3. **Manage portfolio**: Use `/addstock` or `/addetf` to add tickers
4. **Get news manually**: Use `/news` to fetch latest news on demand
5. **Enable automatic updates**: Use `/run` to start automatic polling
6. **Stop when done**: Use `/stop` to disable automatic polling

## Troubleshooting

**Bot not responding?**
- Check `.env` has correct `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID`
- Send `/start` to see if bot is connected
- Verify bot is running with `uv run python main.py`

**No news appearing?**
- Use `/news` to manually fetch news (automatic polling is OFF by default)
- Use `/run` to enable automatic news polling
- Check if tickers are valid with `/list` command
- Note: Only news from today with strong sentiment (≥50% confidence) is shown
- Neutral sentiment news is filtered out to reduce noise

**Invalid ticker errors?**
- Use `/list` to see which tickers are invalid
- Use `/remove_invalid` to remove all invalid tickers at once
- Tickers are validated against StockAnalysis.com when added

**High memory usage?**
- FinBERT model uses ~1GB RAM (this is normal for AI models)
- Model is cached in `data/models/` after first download

## Technical Stack

- **News Source**: StockAnalysis.com (scrapes news from TipRanks, Invezz, and other sources)
- **Scraping**: BeautifulSoup4 for HTML parsing
- **Sentiment Analysis**: FinBERT (ProsusAI/finbert) - pre-trained financial sentiment model
- **Bot Framework**: python-telegram-bot (async version)
- **Architecture**: Async Python with asyncio for concurrent news fetching
- **Package Manager**: uv for fast, reliable dependency management

See [DOCUMENTATION.md](DOCUMENTATION.md) for detailed technical documentation.

## Recent Updates

- Fixed StockAnalysis scraper (adapted to new HTML structure)
- Added `/run` and `/stop` commands for controlling automatic news polling
- Changed startup behavior to send welcome message only (no automatic news fetching)
- Removed hardcoded ticker suggestions (simplified validation errors)
- Improved news source attribution (shows actual source: TipRanks, Invezz, etc.)
- Added deduplication to prevent sending the same news twice

## License

MIT