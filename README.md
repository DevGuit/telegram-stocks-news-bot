# Stock News Monitor

A Telegram bot that monitors stock news, analyzes sentiment with AI, and sends you real-time alerts.

## Features

- Manage portfolio via Telegram chat (stocks and ETFs)
- Auto-scrapes StockAnalysis news (no API key)
- AI sentiment analysis (FinBERT)
- Smart ticker validation with suggestions
- Portfolio validation on startup (shows valid/invalid tickers)
- On-demand updates with `/status`
- Secure credential management

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
  "etf": ["INQQ", "SGLD"],
  "last_check": null
}
```

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

- `/start` - Initialize bot
- `/list` - View portfolio (stocks and ETFs shown separately)
- `/addstock TICKER` - Add stock (auto-validates against StockAnalysis)
- `/addetf TICKER` - Add ETF (auto-validates against StockAnalysis)
- `/remove TICKER` - Remove stock or ETF
- `/remove_all` - Remove all invalid tickers at once
- `/status` - Get news now
- `/help` - Show help

**Tip**: Invalid tickers will suggest valid alternatives from ticker suggestions file

## How It Works

1. Validates all tickers in portfolio at startup (sends summary to Telegram)
2. Scrapes StockAnalysis.com for latest stock and ETF news
3. FinBERT analyzes headline sentiment
4. Filters relevant news (positive/negative ≥50% confidence)
5. Sends formatted updates to Telegram

## Troubleshooting

**Bot not responding?**
- Check `.env` has correct token and chat ID
- Send `/start` to initialize
- Verify bot is running

**No news?**
- Use `/status` for immediate check
- Tickers are validated when added
- Only significant sentiment is reported

**High memory?**
- FinBERT model uses ~1GB RAM (normal)

## Technical Stack

- **StockAnalysis**: HTML scraping (BeautifulSoup)
- **FinBERT**: Pre-trained financial sentiment model
- **Telegram**: python-telegram-bot (async)
- **Architecture**: Async Python with asyncio

See [DOCUMENTATION.md](DOCUMENTATION.md) for technical details.

## License

MIT