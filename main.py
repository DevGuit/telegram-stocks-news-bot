"""Stock News Monitor - Entry point.

Monitors stock portfolio for latest news, classifies sentiment with FinBERT,
and sends updates via Telegram bot.
"""

# ruff: noqa: E402, F403, F405

print("Loading Stock News Monitor... (this may take 10-30 seconds)")

import asyncio
import logging
from pathlib import Path

from helpers import *

print("Modules loaded successfully.")

logger = logging.getLogger(__name__)


async def send_periodic_updates(
    bot, chat_id: str, check_interval_seconds: int, valid_portfolio: dict[str, list[str]]
):
    """Periodically fetch and send news updates when polling is enabled.

    Args:
        bot: StockNewsBot instance.
        chat_id: Telegram chat ID to send updates to.
        check_interval_seconds: Seconds between news checks.
        valid_portfolio: Dictionary with only valid tickers.
    """
    # Load cache of previously sent headlines
    sent_headlines = load_news_cache()
    logger.info(f"Loaded {len(sent_headlines)} previously sent headlines from cache")

    # Continuous loop, but only fetch when polling_enabled is True
    while True:
        await asyncio.sleep(check_interval_seconds)

        # Only fetch news if polling is enabled
        if not bot.polling_enabled:
            continue

        try:
            total_tickers = len(valid_portfolio.get("stocks", [])) + len(
                valid_portfolio.get("etf", [])
            )

            if total_tickers > 0:
                logger.info(f"Fetching news for {total_tickers} valid tickers...")
                classified_news = fetch_and_classify_news(
                    valid_portfolio, max_news_per_ticker=5
                )

                # Filter out already sent news
                new_news = filter_new_news(classified_news, sent_headlines)

                if new_news:
                    logger.info(
                        f"Found {len(new_news)} new news items (filtered {len(classified_news) - len(new_news)} duplicates)"
                    )
                    await bot.send_news_update(chat_id, new_news)

                    # Update cache with new headlines
                    for news, _ in new_news:
                        sent_headlines.add(news.headline)
                    save_news_cache(sent_headlines)
                else:
                    logger.info("No new news found")

        except Exception as e:
            logger.error(f"Error in periodic update: {e}")


def main():
    """Main application entry point."""
    setup_logging()

    print("Stock News Monitor starting...")  # Immediate feedback
    logger.info("Starting Stock News Monitor...")

    telegram_config = load_telegram_config()
    bot_token = telegram_config["bot_token"]
    chat_id = telegram_config["chat_id"]
    check_interval_seconds = telegram_config.get("news_check_interval_seconds", 30)

    paths = load_paths()
    portfolio_path = Path(paths["portfolio"])
    model_cache_dir = Path(paths["model_cache"])

    bot = setup_bot(portfolio_path, bot_token, model_cache_dir)

    logger.info("Telegram bot initialized")
    logger.info(f"News check interval: {check_interval_seconds} seconds")
    logger.info(f"Chat ID: {chat_id}")

    portfolio = load_portfolio()
    total_stocks = len(portfolio.get("stocks", []))
    total_etfs = len(portfolio.get("etf", []))
    logger.info(f"Monitoring {total_stocks} stocks and {total_etfs} ETFs")

    # Validate all tickers in portfolio at startup
    print("Validating portfolio tickers...")
    logger.info("Validating portfolio tickers against StockAnalysis...")
    validation_results = validate_portfolio_tickers(portfolio)

    # Log validation results
    stocks_valid = validation_results["stocks"]["valid"]
    stocks_invalid = validation_results["stocks"]["invalid"]
    etf_valid = validation_results["etf"]["valid"]
    etf_invalid = validation_results["etf"]["invalid"]

    logger.info(f"Stocks: {len(stocks_valid)} valid, {len(stocks_invalid)} invalid")
    logger.info(f"ETFs: {len(etf_valid)} valid, {len(etf_invalid)} invalid")

    if stocks_valid:
        logger.info(f"Valid stocks: {', '.join(stocks_valid)}")
    if stocks_invalid:
        logger.warning(f"Invalid stocks: {', '.join(stocks_invalid)}")
    if etf_valid:
        logger.info(f"Valid ETFs: {', '.join(etf_valid)}")
    if etf_invalid:
        logger.warning(f"Invalid ETFs: {', '.join(etf_invalid)}")

    async def run_bot():
        """Run bot with periodic news updates."""
        # Initialize and start bot first
        await bot.application.initialize()
        await bot.application.start()

        # Send welcome message to Telegram
        print("Sending welcome message to Telegram...")
        welcome_msg = (
            "📈 Stock News Monitor Started!\n\n"
            "✅ Bot is ready and connected.\n\n"
        )

        if stocks_valid or etf_valid:
            welcome_msg += f"📊 Portfolio: {len(stocks_valid)} stocks, {len(etf_valid)} ETFs\n"
            if stocks_invalid or etf_invalid:
                welcome_msg += f"⚠️ {len(stocks_invalid) + len(etf_invalid)} invalid tickers found\n"
        else:
            welcome_msg += "📭 Portfolio is empty.\n"

        welcome_msg += (
            "\n📰 News Monitoring:\n"
            "  • /news - Get latest news now (manual)\n"
            "  • /run - Start automatic news polling\n"
            "  • /stop - Stop automatic polling\n\n"
            "📋 Portfolio:\n"
            "  • /status - Show portfolio with links\n"
            "  • /list - View portfolio (validates tickers)\n"
            "  • /addstock TICKER - Add a stock\n"
            "  • /addetf TICKER - Add an ETF\n\n"
            "/help - Show all commands"
        )

        try:
            await bot.application.bot.send_message(chat_id=chat_id, text=welcome_msg)
            print("✅ Welcome message sent successfully")
            logger.info("Welcome message sent to Telegram")
        except Exception as e:
            print(f"❌ Failed to send welcome message: {e}")
            logger.error(f"Failed to send welcome message: {e}")
            # Don't proceed if we can't send messages
            raise

        # Create portfolio with only valid tickers for monitoring
        valid_portfolio = {"stocks": stocks_valid, "etf": etf_valid}
        print(f"Starting monitoring for {len(stocks_valid)} stocks and {len(etf_valid)} ETFs")

        update_task = asyncio.create_task(
            send_periodic_updates(bot, chat_id, check_interval_seconds, valid_portfolio)
        )

        await bot.application.updater.start_polling()

        try:
            await update_task
        except asyncio.CancelledError:
            logger.info("Shutting down...")
        finally:
            await bot.application.updater.stop()
            await bot.application.stop()
            await bot.application.shutdown()

    try:
        asyncio.run(run_bot())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")


if __name__ == "__main__":
    main()
