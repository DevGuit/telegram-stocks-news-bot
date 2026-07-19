# Stock News Monitor 📈

A Telegram bot that monitors stock news, analyzes sentiment with AI, and sends you real-time alerts.

## Features

- Manage portfolio via Telegram chat
- Auto-scrapes Finviz news (no API key)
- AI sentiment analysis (FinBERT)
- Smart ticker validation with suggestions
- On-demand updates with `/status`
- Secure credential management

## Quick Start

```bash
# 1. Install
git clone <your-repo>
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

1. Message [@BotFather](https://t.me/BotFather) → `/newbot`
2. Copy your bot token

### 2. Get Chat ID

1. Message your bot
2. Visit: `https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates`
3. Find `"chat":{"id":123456789}`

### 3. Configure

Create `.env` file:
```env
TELEGRAM_BOT_TOKEN=your_bot_token_here
TELEGRAM_CHAT_ID=your_chat_id_here
```

Edit `json/portfolio.json` with your stocks:
```json
{
  "stocks": ["AAPL", "MSFT", "GOOGL"],
  "last_check": null,
  "check_interval_minutes": 60
}
```

## Commands

- `/start` - Initialize bot
- `/list` - View portfolio
- `/add TICKER` - Add stock (auto-validates)
- `/remove TICKER` - Remove stock
- `/status` - Get news now
- `/help` - Show help

**Tip**: Invalid tickers like "SP500" will suggest valid alternatives (SPY, VOO, IVV)

## How It Works

1. Scrapes Finviz for latest stock news
2. FinBERT analyzes headline sentiment
3. Filters relevant news (positive/negative ≥50% confidence)
4. Sends formatted updates to Telegram

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

- **Finviz**: HTML scraping (BeautifulSoup)
- **FinBERT**: Pre-trained financial sentiment model
- **Telegram**: python-telegram-bot (async)
- **Architecture**: Async Python with asyncio

See [DOCUMENTATION.md](DOCUMENTATION.md) for technical details.

## License

MIT
