"""Stock News Monitor - Entry point.

Monitors stock portfolio for latest news, classifies sentiment with FinBERT,
and sends updates via Telegram bot.
"""

print("Loading Stock News Monitor... (this may take 10-30 seconds)")

import asyncio
import logging
from pathlib import Path

from helpers import *

print("Modules loaded successfully.")

logger = logging.getLogger(__name__)


async def send_periodic_updates(bot, chat_id: str, check_interval_seconds: int):
    """Periodically fetch and send news updates.

    Args:
        bot: StockNewsBot instance.
        chat_id: Telegram chat ID to send updates to.
        check_interval_seconds: Seconds between news checks.
    """
    # Load cache of previously sent headlines
    sent_headlines = load_news_cache()
    logger.info(f"Loaded {len(sent_headlines)} previously sent headlines from cache")

    # Send initial update immediately on startup
    logger.info("Sending initial news update...")
    try:
        stocks = load_portfolio()

        if stocks:
            logger.info(f"Fetching news for {len(stocks)} stocks...")
            classified_news = fetch_and_classify_news(stocks, max_news_per_ticker=5)

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
                logger.info("No new news found for initial update")

    except Exception as e:
        logger.error(f"Error in initial update: {e}")

    # Then continue with periodic updates
    while True:
        await asyncio.sleep(check_interval_seconds)

        try:
            stocks = load_portfolio()

            if stocks:
                logger.info(f"Fetching news for {len(stocks)} stocks...")
                classified_news = fetch_and_classify_news(stocks, max_news_per_ticker=5)

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
    ticker_suggestions_path = Path(paths["ticker_suggestions"])

    bot = setup_bot(portfolio_path, bot_token, model_cache_dir, ticker_suggestions_path)

    logger.info("Telegram bot initialized")
    logger.info(f"News check interval: {check_interval_seconds} seconds")
    logger.info(f"Chat ID: {chat_id}")

    stocks = load_portfolio()
    logger.info(f"Monitoring {len(stocks)} stocks: {', '.join(stocks)}")

    async def run_bot():
        """Run bot with periodic news updates."""
        update_task = asyncio.create_task(
            send_periodic_updates(bot, chat_id, check_interval_seconds)
        )

        await bot.application.initialize()
        await bot.application.start()
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
