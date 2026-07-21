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

from .sentiment_classifier import SentimentClassifier, SentimentResult
from .stockanalysis_scraper import NewsItem, StockAnalysisScraper

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
    ):
        """Initialize Telegram bot.

        Args:
            bot_token: Telegram bot API token.
            portfolio_path: Path to portfolio.json file.
            on_add_stock: Callback function when stock is added.
            on_remove_stock: Callback function when stock is removed.
            model_cache_dir: Directory to cache ML models.
        """
        self.bot_token = bot_token
        self.portfolio_path = portfolio_path
        self.on_add_stock = on_add_stock
        self.on_remove_stock = on_remove_stock
        self.model_cache_dir = model_cache_dir
        self.polling_enabled = False  # Start with polling disabled
        self.update_task = None  # Track the background update task

        self.application = Application.builder().token(bot_token).build()

        self._setup_handlers()

    def _setup_handlers(self):
        """Set up command and message handlers."""
        self.application.add_handler(CommandHandler("start", self.cmd_start))
        self.application.add_handler(CommandHandler("help", self.cmd_help))
        self.application.add_handler(CommandHandler("list", self.cmd_list))
        self.application.add_handler(CommandHandler("addstock", self.cmd_addstock))
        self.application.add_handler(CommandHandler("addetf", self.cmd_addetf))
        self.application.add_handler(CommandHandler("remove", self.cmd_remove))
        self.application.add_handler(CommandHandler("remove_all", self.cmd_remove_all))
        self.application.add_handler(CommandHandler("remove_invalid", self.cmd_remove_invalid))
        self.application.add_handler(CommandHandler("news", self.cmd_news))
        self.application.add_handler(CommandHandler("status", self.cmd_status))
        self.application.add_handler(CommandHandler("run", self.cmd_run))
        self.application.add_handler(CommandHandler("stop", self.cmd_stop))
        self.application.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message)
        )

    async def cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command."""
        welcome_msg = (
            "📈 Welcome to Stock News Monitor!\n\n"
            "I can help you monitor news for your stock portfolio.\n\n"
            "📋 Main Commands:\n"
            "/status - Show portfolio status with links\n"
            "/list - Show your portfolio\n"
            "/addstock TICKER - Add a stock (e.g., /addstock AAPL)\n"
            "/addetf TICKER - Add an ETF (e.g., /addetf INQQ)\n"
            "/remove TICKER - Remove a ticker\n\n"
            "📰 News Commands:\n"
            "/news - Get latest news now (manual)\n"
            "/run - Start automatic news polling\n"
            "/stop - Stop automatic news polling\n\n"
            "/help - Show full help"
        )
        await update.message.reply_text(welcome_msg)

    async def cmd_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /help command."""
        help_msg = (
            "📊 Stock News Monitor Commands:\n\n"
            "📋 Portfolio Management:\n"
            "/status - Show portfolio status with links\n"
            "/list - View your current portfolio\n"
            "/addstock TICKER - Add stock to portfolio\n"
            "/addetf TICKER - Add ETF to portfolio\n"
            "/remove TICKER - Remove ticker from portfolio\n"
            "/remove_all - Remove all tickers\n"
            "/remove_invalid - Remove all invalid tickers\n\n"
            "📰 News Monitoring:\n"
            "/news - Fetch latest news now (manual)\n"
            "/run - Start automatic news polling (every 30s)\n"
            "/stop - Stop automatic news polling\n\n"
            "/help - Show this help message\n\n"
            "💡 Tip: Use /run to enable automatic news updates, "
            "or use /news to fetch news manually anytime."
        )
        await update.message.reply_text(help_msg)

    async def cmd_list(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /list command - shows portfolio with validation status."""
        portfolio = self._load_portfolio()

        total = len(portfolio.get("stocks", [])) + len(portfolio.get("etf", []))
        if total == 0:
            await update.message.reply_text(
                "📭 Your portfolio is empty.\n\nUse /addstock or /addetf to add tickers."
            )
            return

        # Show loading message
        await update.message.reply_text(
            f"🔍 Loading portfolio and validating {total} tickers...\nThis may take a moment."
        )

        try:
            import asyncio

            def validate_portfolio_sync():
                """Validate portfolio synchronously."""
                from resources.stockanalysis_scraper import StockAnalysisScraper

                results = {
                    "stocks": {"valid": [], "invalid": []},
                    "etf": {"valid": [], "invalid": []},
                }
                scraper = StockAnalysisScraper(timeout=5)

                # Validate stocks
                for ticker in portfolio.get("stocks", []):
                    try:
                        scraper.fetch_news(ticker, max_news=1, asset_type="stocks")
                        results["stocks"]["valid"].append(ticker)
                    except Exception:
                        results["stocks"]["invalid"].append(ticker)

                # Validate ETFs
                for ticker in portfolio.get("etf", []):
                    try:
                        scraper.fetch_news(ticker, max_news=1, asset_type="etf")
                        results["etf"]["valid"].append(ticker)
                    except Exception:
                        results["etf"]["invalid"].append(ticker)

                return results

            # Run validation in thread to avoid blocking
            validation_results = await asyncio.to_thread(validate_portfolio_sync)

            stocks_valid = validation_results["stocks"]["valid"]
            stocks_invalid = validation_results["stocks"]["invalid"]
            etf_valid = validation_results["etf"]["valid"]
            etf_invalid = validation_results["etf"]["invalid"]

            # Build message
            msg = f"📋 Your Portfolio ({total} tickers):\n\n"

            # Show valid stocks
            if stocks_valid:
                msg += f"✅ Valid Stocks ({len(stocks_valid)}):\n"
                msg += "\n".join([f"  • {ticker}" for ticker in stocks_valid])
                msg += "\n\n"

            # Show invalid stocks
            if stocks_invalid:
                msg += f"❌ Invalid Stocks ({len(stocks_invalid)}):\n"
                msg += "\n".join([f"  • {ticker}" for ticker in stocks_invalid])
                msg += "\n\n"

            # Show valid ETFs
            if etf_valid:
                msg += f"✅ Valid ETFs ({len(etf_valid)}):\n"
                msg += "\n".join([f"  • {ticker}" for ticker in etf_valid])
                msg += "\n\n"

            # Show invalid ETFs
            if etf_invalid:
                msg += f"❌ Invalid ETFs ({len(etf_invalid)}):\n"
                msg += "\n".join([f"  • {ticker}" for ticker in etf_invalid])
                msg += "\n\n"

            # Add summary
            total_valid = len(stocks_valid) + len(etf_valid)
            total_invalid = len(stocks_invalid) + len(etf_invalid)

            msg += f"📊 Summary: {total_valid} valid, {total_invalid} invalid"

            if total_invalid > 0:
                msg += "\n\n💡 Tip: Use /remove_invalid to remove all invalid tickers"

            await update.message.reply_text(msg)

        except Exception as e:
            logger.error(f"Error in /list command: {e}")
            await update.message.reply_text(
                f"❌ Error validating portfolio: {str(e)}\nPlease try again later."
            )

    async def cmd_addstock(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /addstock TICKER command."""
        if not context.args or len(context.args) == 0:
            await update.message.reply_text(
                "Usage: /addstock TICKER\nExample: /addstock AAPL"
            )
            return

        ticker = context.args[0].strip().upper()
        await self._add_ticker(update, ticker, "stocks", "stock")

    async def cmd_addetf(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /addetf TICKER command."""
        if not context.args or len(context.args) == 0:
            await update.message.reply_text(
                "Usage: /addetf TICKER\nExample: /addetf INQQ"
            )
            return

        ticker = context.args[0].strip().upper()
        await self._add_ticker(update, ticker, "etf", "ETF")

    async def _add_ticker(
        self, update: Update, ticker: str, asset_type: str, asset_label: str
    ):
        """Add a ticker to portfolio with validation.

        Args:
            update: Telegram update object.
            ticker: Ticker symbol to add.
            asset_type: "stocks" or "etf".
            asset_label: Human-readable label ("stock" or "ETF").
        """
        portfolio = self._load_portfolio()

        # Check if ticker already exists in any category
        if ticker in portfolio.get("stocks", []) or ticker in portfolio.get("etf", []):
            await update.message.reply_text(f"ℹ️ {ticker} is already in your portfolio.")
            return

        await update.message.reply_text(f"🔍 Validating {asset_label} {ticker}...")

        is_valid = await self._validate_ticker(ticker, asset_type)

        if not is_valid:
            error_msg = f"❌ '{ticker}' is not a valid {asset_label} ticker.\n\n"
            error_msg += "Please check the symbol and try again.\n"
            if asset_type == "stocks":
                error_msg += (
                    "Common indices: SPY (S&P 500), QQQ (Nasdaq), DIA (Dow Jones)"
                )

            await update.message.reply_text(error_msg)
            return

        portfolio.setdefault(asset_type, []).append(ticker)
        self._save_portfolio(portfolio)

        if self.on_add_stock:
            self.on_add_stock(ticker)

        await update.message.reply_text(
            f"✅ Added {asset_label} {ticker} to your portfolio!"
        )

    async def cmd_remove(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /remove TICKER command."""
        if not context.args or len(context.args) == 0:
            await update.message.reply_text(
                "Usage: /remove TICKER\nExample: /remove AAPL"
            )
            return

        ticker = context.args[0].strip().upper()
        portfolio = self._load_portfolio()

        # Check which category the ticker is in
        found = False
        if ticker in portfolio.get("stocks", []):
            portfolio["stocks"].remove(ticker)
            found = True
        elif ticker in portfolio.get("etf", []):
            portfolio["etf"].remove(ticker)
            found = True

        if not found:
            await update.message.reply_text(f"ℹ️ {ticker} is not in your portfolio.")
            return

        self._save_portfolio(portfolio)

        if self.on_remove_stock:
            self.on_remove_stock(ticker)

        await update.message.reply_text(f"✅ Removed {ticker} from your portfolio.")

    async def cmd_remove_all(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /remove_all command - remove ALL tickers from portfolio."""
        portfolio = self._load_portfolio()

        total = len(portfolio.get("stocks", [])) + len(portfolio.get("etf", []))
        if total == 0:
            await update.message.reply_text(
                "📭 Your portfolio is already empty.\n\nUse /addstock or /addetf to add tickers."
            )
            return

        # Clear the portfolio
        portfolio["stocks"] = []
        portfolio["etf"] = []
        self._save_portfolio(portfolio)

        await update.message.reply_text(
            f"✅ Removed all {total} tickers from your portfolio.\n\n"
            "Your portfolio is now empty.\n"
            "Use /addstock or /addetf to add tickers."
        )

        # Trigger callbacks
        if self.on_remove_stock:
            # This is a bulk removal, so we don't have individual ticker info
            pass

    async def cmd_remove_invalid(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /remove_invalid command - remove all invalid tickers."""
        portfolio = self._load_portfolio()

        total = len(portfolio.get("stocks", [])) + len(portfolio.get("etf", []))
        if total == 0:
            await update.message.reply_text(
                "📭 Your portfolio is empty.\n\nUse /addstock or /addetf to add tickers."
            )
            return

        await update.message.reply_text(
            f"🔍 Validating {total} tickers to identify invalid ones...\nThis may take a moment."
        )

        try:
            import asyncio

            def validate_portfolio_sync():
                """Validate portfolio synchronously."""
                from resources.stockanalysis_scraper import StockAnalysisScraper

                results = {
                    "stocks": {"valid": [], "invalid": []},
                    "etf": {"valid": [], "invalid": []},
                }
                scraper = StockAnalysisScraper(timeout=5)

                # Validate stocks
                for ticker in portfolio.get("stocks", []):
                    try:
                        scraper.fetch_news(ticker, max_news=1, asset_type="stocks")
                        results["stocks"]["valid"].append(ticker)
                    except Exception:
                        results["stocks"]["invalid"].append(ticker)

                # Validate ETFs
                for ticker in portfolio.get("etf", []):
                    try:
                        scraper.fetch_news(ticker, max_news=1, asset_type="etf")
                        results["etf"]["valid"].append(ticker)
                    except Exception:
                        results["etf"]["invalid"].append(ticker)

                return results

            # Run validation in thread to avoid blocking
            validation_results = await asyncio.to_thread(validate_portfolio_sync)

            stocks_invalid = validation_results["stocks"]["invalid"]
            etf_invalid = validation_results["etf"]["invalid"]

            if not stocks_invalid and not etf_invalid:
                await update.message.reply_text(
                    "✅ All tickers in your portfolio are valid!\nNo tickers to remove."
                )
                return

            # Remove invalid tickers
            removed_stocks = []
            removed_etfs = []

            for ticker in stocks_invalid:
                if ticker in portfolio.get("stocks", []):
                    portfolio["stocks"].remove(ticker)
                    removed_stocks.append(ticker)

            for ticker in etf_invalid:
                if ticker in portfolio.get("etf", []):
                    portfolio["etf"].remove(ticker)
                    removed_etfs.append(ticker)

            self._save_portfolio(portfolio)

            # Build response message
            msg = "✅ Removed all invalid tickers:\n\n"
            if removed_stocks:
                msg += f"**Stocks ({len(removed_stocks)}):**\n"
                msg += ", ".join(removed_stocks) + "\n\n"
            if removed_etfs:
                msg += f"**ETFs ({len(removed_etfs)}):**\n"
                msg += ", ".join(removed_etfs) + "\n\n"

            total_removed = len(removed_stocks) + len(removed_etfs)
            total_remaining = (
                len(portfolio.get("stocks", [])) + len(portfolio.get("etf", []))
            )

            msg += "📊 **Summary:**\n"
            msg += f"  • Removed: {total_removed} invalid tickers\n"
            msg += f"  • Remaining: {total_remaining} valid tickers\n\n"
            msg += "Use /list to view your updated portfolio."

            await update.message.reply_text(msg)

            # Trigger callbacks
            if self.on_remove_stock:
                for ticker in removed_stocks + removed_etfs:
                    self.on_remove_stock(ticker)

        except Exception as e:
            logger.error(f"Error in /remove_all command: {e}")
            await update.message.reply_text(
                f"❌ Error validating tickers: {str(e)}\nPlease try again later."
            )

    async def cmd_news(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /news command - fetch latest news immediately (today only)."""
        portfolio = self._load_portfolio()

        total = len(portfolio.get("stocks", [])) + len(portfolio.get("etf", []))
        if total == 0:
            await update.message.reply_text(
                "📭 Your portfolio is empty.\n\nUse /addstock or /addetf to add tickers first."
            )
            return

        await update.message.reply_text(
            f"🔍 Fetching today's news for {total} tickers...\nThis may take a moment."
        )

        try:
            # Import here to avoid circular imports
            from datetime import datetime
            from zoneinfo import ZoneInfo
            import os

            # Initialize scraper
            stockanalysis_scraper = StockAnalysisScraper()
            classifier = SentimentClassifier(model_cache_dir=self.model_cache_dir)

            # Fetch from StockAnalysis
            try:
                all_news = stockanalysis_scraper.fetch_multiple_tickers(
                    portfolio, max_news_per_ticker=5
                )
            except Exception as e:
                logger.warning(f"Failed to fetch from StockAnalysis: {e}")
                all_news = {}

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

    async def cmd_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /status command - show welcome message with portfolio and links."""
        portfolio = self._load_portfolio()

        total = len(portfolio.get("stocks", [])) + len(portfolio.get("etf", []))

        msg = "📈 Stock News Monitor Status\n\n"

        if total == 0:
            msg += "📭 Your portfolio is empty.\n\n"
            msg += "Use /addstock or /addetf to add tickers and start monitoring!"
            await update.message.reply_text(msg)
            return

        msg += f"✅ Monitoring {total} tickers\n\n"

        # Show polling status
        if self.polling_enabled:
            msg += "🟢 Automatic polling: RUNNING\n"
            msg += "   (Checking for news every 30 seconds)\n\n"
        else:
            msg += "⚪ Automatic polling: STOPPED\n"
            msg += "   Use /run to start automatic updates\n\n"

        # Show stocks with links
        if portfolio.get("stocks"):
            msg += f"📊 Stocks ({len(portfolio['stocks'])}):\n"
            for ticker in portfolio["stocks"]:
                msg += f"  • {ticker}: https://stockanalysis.com/stocks/{ticker.lower()}/\n"
            msg += "\n"

        # Show ETFs with links
        if portfolio.get("etf"):
            msg += f"📈 ETFs ({len(portfolio['etf'])}):\n"
            for ticker in portfolio["etf"]:
                msg += f"  • {ticker}: https://stockanalysis.com/etf/{ticker.lower()}/\n"
            msg += "\n"

        msg += "💡 Quick Actions:\n"
        if not self.polling_enabled:
            msg += "  • /run - Start automatic polling\n"
        else:
            msg += "  • /stop - Stop automatic polling\n"
        msg += "  • /news - Get latest news now\n"
        msg += "  • /list - View portfolio with validation\n"
        msg += "  • /help - Show all commands"

        await update.message.reply_text(msg, disable_web_page_preview=True)

    async def cmd_run(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /run command - start automatic news polling."""
        if self.polling_enabled:
            await update.message.reply_text(
                "⚠️ Automatic news polling is already running!\n\n"
                "Use /stop to stop it."
            )
            return

        self.polling_enabled = True
        await update.message.reply_text(
            "✅ Started automatic news polling!\n\n"
            "I'll check for new news every 30 seconds and send updates automatically.\n\n"
            "Use /stop to stop automatic polling."
        )

    async def cmd_stop(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /stop command - stop automatic news polling."""
        if not self.polling_enabled:
            await update.message.reply_text(
                "ℹ️ Automatic news polling is not running.\n\n"
                "Use /run to start it, or /news to fetch news manually."
            )
            return

        self.polling_enabled = False
        await update.message.reply_text(
            "✅ Stopped automatic news polling!\n\n"
            "You can still use /news to fetch news manually,\n"
            "or /run to restart automatic polling."
        )

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle non-command text messages."""
        await update.message.reply_text(
            "I don't understand that command. Type /help to see available commands."
        )

    def _load_portfolio(self) -> dict[str, list[str]]:
        """Load portfolio from portfolio.json."""
        if not self.portfolio_path.exists():
            return {"stocks": [], "etf": []}

        with open(self.portfolio_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Support both "etf" and "etfs" keys
        return {
            "stocks": data.get("stocks", []),
            "etf": data.get("etf", data.get("etfs", [])),
        }

    def _save_portfolio(self, portfolio: dict[str, list[str]]):
        """Save portfolio to portfolio.json."""
        data = {
            "stocks": portfolio.get("stocks", []),
            "etf": portfolio.get("etf", []),
        }

        with open(self.portfolio_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    async def _validate_ticker(
        self, ticker: str, asset_type: str = "stocks"
    ) -> bool:
        """Validate ticker by checking if news can be fetched.

        Args:
            ticker: Ticker symbol to validate.
            asset_type: Asset type - "stocks" or "etf".

        Returns:
            True if ticker is valid, False otherwise.
        """
        import asyncio

        def validate_sync():
            try:
                scraper = StockAnalysisScraper(timeout=5)
                scraper.fetch_news(ticker, max_news=1, asset_type=asset_type)
                return True
            except Exception as e:
                logger.warning(f"Ticker validation failed for {ticker}: {e}")
                return False

        return await asyncio.to_thread(validate_sync)

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
            msg = f"📰 Latest News for {ticker}\n"
            msg += f"Scraped website: https://stockanalysis.com/stocks/{ticker.lower()}/\n\n"

            for news, sentiment in items[:5]:
                sentiment_emoji = self._get_sentiment_emoji(sentiment.label)

                msg += f"{sentiment_emoji} **{news.headline}**\n"
                msg += f"   _{sentiment.label.capitalize()} ({sentiment.score:.0%})_\n"
                msg += f"   Source: {news.source}\n"
                msg += f"   Link: {news.url}\n"
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
