"""Telegram Bot - Handle user interactions and send news updates.

Data flow:
  User message → Telegram API → Command handler → Portfolio update / News fetch
  News items → Format message → Telegram API → User chat
"""

import json
import logging
from pathlib import Path
from typing import Callable

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from .finviz_scraper import FinvizScraper, NewsItem
from .sentiment_classifier import SentimentClassifier, SentimentResult
from .stockanalysis_scraper import StockAnalysisScraper

logger = logging.getLogger(__name__)


class StockNewsBot:
    """Telegram bot for stock news monitoring."""

    def __init__(
        self,
        bot_token: str,
        portfolio_path: Path,
        on_add_stock: Callable[[str], None] | None = None,
        on_remove_stock: Callable[[str], None] | None = None,
        model_cache_dir: Path | None = None,
        ticker_suggestions_path: Path | None = None,
    ):
        """Initialize Telegram bot.

        Args:
            bot_token: Telegram bot API token.
            portfolio_path: Path to portfolio.json file.
            on_add_stock: Callback function when stock is added.
            on_remove_stock: Callback function when stock is removed.
            model_cache_dir: Directory to cache ML models.
            ticker_suggestions_path: Path to ticker suggestions JSON file.
        """
        self.bot_token = bot_token
        self.portfolio_path = portfolio_path
        self.on_add_stock = on_add_stock
        self.on_remove_stock = on_remove_stock
        self.model_cache_dir = model_cache_dir
        self.ticker_suggestions_path = ticker_suggestions_path

        self.application = Application.builder().token(bot_token).build()

        self._setup_handlers()

    def _setup_handlers(self):
        """Set up command and message handlers."""
        self.application.add_handler(CommandHandler("start", self.cmd_start))
        self.application.add_handler(CommandHandler("help", self.cmd_help))
        self.application.add_handler(CommandHandler("list", self.cmd_list))
        self.application.add_handler(CommandHandler("add", self.cmd_add))
        self.application.add_handler(CommandHandler("remove", self.cmd_remove))
        self.application.add_handler(CommandHandler("status", self.cmd_status))
        self.application.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message)
        )

    async def cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command."""
        welcome_msg = (
            "📈 Welcome to Stock News Monitor!\n\n"
            "I'll keep you updated on the latest news for your portfolio.\n\n"
            "Commands:\n"
            "/list - Show your stocks\n"
            "/add TICKER - Add a stock (e.g., /add AAPL)\n"
            "/remove TICKER - Remove a stock\n"
            "/status - Get latest news now\n"
            "/help - Show this message"
        )
        await update.message.reply_text(welcome_msg)

    async def cmd_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /help command."""
        help_msg = (
            "📊 Stock News Monitor Commands:\n\n"
            "/list - View your current portfolio\n"
            "/add TICKER - Add stock to portfolio\n"
            "/remove TICKER - Remove stock from portfolio\n"
            "/status - Get latest news immediately\n"
            "/help - Show this help message\n\n"
            "I automatically fetch and analyze news for your stocks "
            "using FinBERT sentiment analysis."
        )
        await update.message.reply_text(help_msg)

    async def cmd_list(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /list command."""
        stocks = self._load_portfolio()

        if not stocks:
            await update.message.reply_text(
                "📭 Your portfolio is empty.\n\nUse /add TICKER to add stocks."
            )
            return

        stocks_list = "\n".join([f"• {ticker}" for ticker in stocks])
        msg = f"📋 Your Portfolio ({len(stocks)} stocks):\n\n{stocks_list}"

        await update.message.reply_text(msg)

    async def cmd_add(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /add TICKER command."""
        if not context.args or len(context.args) == 0:
            await update.message.reply_text("Usage: /add TICKER\nExample: /add AAPL")
            return

        ticker = context.args[0].strip().upper()

        stocks = self._load_portfolio()

        if ticker in stocks:
            await update.message.reply_text(f"ℹ️ {ticker} is already in your portfolio.")
            return

        await update.message.reply_text(f"🔍 Validating ticker {ticker}...")

        is_valid, suggestions = await self._validate_ticker(ticker)

        if not is_valid:
            error_msg = f"❌ '{ticker}' is not a valid stock ticker.\n\n"

            if suggestions:
                error_msg += "Did you mean one of these?\n"
                for suggestion in suggestions[:3]:
                    error_msg += f"  • {suggestion}\n"
                error_msg += f"\nUse /add {suggestions[0]} to add it."
            else:
                error_msg += (
                    "Please check the symbol and try again.\n"
                    "Common indices: SPY (S&P 500), QQQ (Nasdaq), DIA (Dow Jones)"
                )

            await update.message.reply_text(error_msg)
            return

        stocks.append(ticker)
        self._save_portfolio(stocks)

        if self.on_add_stock:
            self.on_add_stock(ticker)

        await update.message.reply_text(f"✅ Added {ticker} to your portfolio!")

    async def cmd_remove(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /remove TICKER command."""
        if not context.args or len(context.args) == 0:
            await update.message.reply_text(
                "Usage: /remove TICKER\nExample: /remove AAPL"
            )
            return

        ticker = context.args[0].strip().upper()

        stocks = self._load_portfolio()

        if ticker not in stocks:
            await update.message.reply_text(f"ℹ️ {ticker} is not in your portfolio.")
            return

        stocks.remove(ticker)
        self._save_portfolio(stocks)

        if self.on_remove_stock:
            self.on_remove_stock(ticker)

        await update.message.reply_text(f"✅ Removed {ticker} from your portfolio.")

    async def cmd_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /status command - fetch latest news immediately (today only)."""
        stocks = self._load_portfolio()

        if not stocks:
            await update.message.reply_text(
                "📭 Your portfolio is empty.\n\nUse /add TICKER to add stocks first."
            )
            return

        await update.message.reply_text(
            f"🔍 Fetching today's news for {len(stocks)} stocks...\nThis may take a moment."
        )

        try:
            # Import here to avoid circular imports
            from datetime import datetime
            from zoneinfo import ZoneInfo
            import os

            # Initialize scrapers
            finviz_scraper = FinvizScraper()
            stockanalysis_scraper = StockAnalysisScraper()
            classifier = SentimentClassifier(model_cache_dir=self.model_cache_dir)

            # Fetch from all sources
            all_news = {}

            # Fetch from Finviz
            try:
                finviz_news = finviz_scraper.fetch_multiple_tickers(
                    stocks, max_news_per_ticker=5
                )
                for ticker, news_items in finviz_news.items():
                    if ticker not in all_news:
                        all_news[ticker] = []
                    all_news[ticker].extend(news_items)
            except Exception as e:
                logger.warning(f"Failed to fetch from Finviz: {e}")

            # Fetch from StockAnalysis
            try:
                sa_news = stockanalysis_scraper.fetch_multiple_tickers(
                    stocks, max_news_per_ticker=5
                )
                for ticker, news_items in sa_news.items():
                    if ticker not in all_news:
                        all_news[ticker] = []
                    all_news[ticker].extend(news_items)
            except Exception as e:
                logger.warning(f"Failed to fetch from StockAnalysis: {e}")

            # Get user timezone and today's date
            timezone_str = os.getenv("USER_TIMEZONE", "Europe/Paris")
            user_tz = ZoneInfo(timezone_str)
            today = datetime.now(user_tz).date()

            classified_news = []
            seen_headlines = set()

            for ticker, news_items in all_news.items():
                for news in news_items:
                    # Convert to user timezone and check if today
                    news_date = news.timestamp.astimezone(user_tz).date()
                    if news_date != today:
                        continue

                    # Skip duplicates
                    if news.headline in seen_headlines:
                        continue
                    seen_headlines.add(news.headline)

                    sentiment = classifier.classify(news.headline)

                    if sentiment.label != "neutral" and sentiment.score >= 0.5:
                        classified_news.append((news, sentiment))

            classified_news.sort(key=lambda x: x[0].timestamp, reverse=True)

            if classified_news:
                chat_id = str(update.effective_chat.id)
                await self.send_news_update(chat_id, classified_news)
                await update.message.reply_text(
                    f"✅ Found {len(classified_news)} relevant news items from today!"
                )
            else:
                await update.message.reply_text(
                    f"ℹ️ No significant news found for today ({today}).\n"
                    "Only showing news with strong positive or negative sentiment."
                )

        except Exception as e:
            logger.error(f"Error fetching news: {e}")
            await update.message.reply_text(
                f"❌ Error fetching news: {str(e)}\nPlease try again later."
            )

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle non-command text messages."""
        await update.message.reply_text(
            "I don't understand that command. Type /help to see available commands."
        )

    def _load_portfolio(self) -> list[str]:
        """Load stocks from portfolio.json."""
        if not self.portfolio_path.exists():
            return []

        with open(self.portfolio_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        return data.get("stocks", [])

    def _save_portfolio(self, stocks: list[str]):
        """Save stocks to portfolio.json."""
        data = {"stocks": stocks, "last_check": None, "check_interval_minutes": 60}

        with open(self.portfolio_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    async def _validate_ticker(self, ticker: str) -> tuple[bool, list[str]]:
        """Validate ticker and suggest alternatives if invalid.

        Args:
            ticker: Stock ticker symbol to validate.

        Returns:
            Tuple of (is_valid, suggestions) where suggestions is a list of similar valid tickers.
        """
        import asyncio

        def validate_sync():
            try:
                scraper = FinvizScraper(timeout=5)
                scraper.fetch_news(ticker, max_news=1)
                return True, []
            except Exception as e:
                logger.warning(f"Ticker validation failed for {ticker}: {e}")

                # Try to suggest alternatives based on common patterns
                suggestions = self._get_ticker_suggestions(ticker)
                return False, suggestions

        return await asyncio.to_thread(validate_sync)

    def _get_ticker_suggestions(self, invalid_ticker: str) -> list[str]:
        """Get ticker suggestions for common mistakes.

        Args:
            invalid_ticker: The invalid ticker that was attempted.

        Returns:
            List of suggested valid tickers.
        """
        # Load suggestions from JSON file if available
        suggestions_map = {}

        if self.ticker_suggestions_path and self.ticker_suggestions_path.exists():
            try:
                with open(self.ticker_suggestions_path, "r", encoding="utf-8") as f:
                    suggestions_map = json.load(f)
            except Exception as e:
                logger.warning(f"Failed to load ticker suggestions: {e}")
                suggestions_map = {}

        # Fallback to empty dict if no suggestions file
        if not suggestions_map:
            logger.warning("No ticker suggestions available")
            return []

        upper_ticker = invalid_ticker.upper()

        # Direct match
        if upper_ticker in suggestions_map:
            return suggestions_map[upper_ticker]

        # Partial match (e.g., "SP" in "SP500")
        for key, values in suggestions_map.items():
            if key in upper_ticker or upper_ticker in key:
                return values

        return []

    async def send_news_update(
        self,
        chat_id: str,
        news_items: list[tuple[NewsItem, SentimentResult]],
    ):
        """Send news update to user.

        Args:
            chat_id: Telegram chat ID.
            news_items: List of (NewsItem, SentimentResult) tuples.
        """
        if not news_items:
            return

        grouped_by_ticker = {}
        for news, sentiment in news_items:
            if news.ticker not in grouped_by_ticker:
                grouped_by_ticker[news.ticker] = []
            grouped_by_ticker[news.ticker].append((news, sentiment))

        for ticker, items in grouped_by_ticker.items():
            msg = f"📰 Latest News for {ticker}\n\n"

            for news, sentiment in items[:5]:
                sentiment_emoji = self._get_sentiment_emoji(sentiment.label)

                msg += f"{sentiment_emoji} **{news.headline}**\n"
                msg += f"   _{sentiment.label.capitalize()} ({sentiment.score:.0%})_\n"
                msg += f"   🔗 [{news.source}]({news.url})\n"
                msg += f"   🕒 {news.timestamp.strftime('%b %d, %I:%M%p')}\n\n"

            try:
                await self.application.bot.send_message(
                    chat_id=chat_id,
                    text=msg,
                    parse_mode="Markdown",
                    disable_web_page_preview=True,
                )
            except Exception as e:
                logger.error(f"Failed to send message: {e}")

    def _get_sentiment_emoji(self, label: str) -> str:
        """Get emoji for sentiment label."""
        emoji_map = {"positive": "🟢", "negative": "🔴", "neutral": "⚪"}

        return emoji_map.get(label.lower(), "⚪")

    def run_polling(self):
        """Start bot in polling mode."""
        logger.info("Starting Telegram bot in polling mode...")
        self.application.run_polling()

    def stop(self):
        """Stop the bot."""
        logger.info("Stopping Telegram bot...")
        self.application.stop()


if __name__ == "__main__":
    """Example usage of StockNewsBot."""
    import os

    bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "YOUR_TOKEN_HERE")
    portfolio_path = Path("json/portfolio.json")

    bot = StockNewsBot(bot_token, portfolio_path)

    print("Bot is running. Press Ctrl+C to stop.")
    bot.run_polling()
