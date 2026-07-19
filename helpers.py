"""Helper functions for stock news monitoring operations.

Data flow:
  - Config: json/paths.json → load_paths() → path strings
  - Portfolio: json/portfolio.json → load/save functions → stock list
  - News: Ticker list → fetch_and_classify_news() → classified news items
  - Telegram: .env + Config → setup_bot() → StockNewsBot instance
"""

import json
import logging
import os
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

from resources import (
    FinvizScraper,
    NewsItem,
    SentimentClassifier,
    SentimentResult,
    StockNewsBot,
)

# Load environment variables from .env file
load_dotenv()

logger = logging.getLogger(__name__)

__all__ = [
    "load_paths",
    "load_portfolio",
    "save_portfolio",
    "load_telegram_config",
    "setup_logging",
    "fetch_and_classify_news",
    "setup_bot",
]


def load_paths() -> dict:
    """Load file paths from json/paths.json configuration.

    Returns:
        Dictionary mapping path keys to path strings.

    Raises:
        FileNotFoundError: If json/paths.json does not exist.
        json.JSONDecodeError: If JSON is malformed.
    """
    paths_file = Path("json/paths.json")
    if not paths_file.exists():
        raise FileNotFoundError("Configuration file json/paths.json not found")

    with open(paths_file, "r", encoding="utf-8") as f:
        paths = json.load(f)

    return paths


def setup_logging(level: str = "INFO") -> None:
    """Configure logging for the application.

    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL).
    """
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def load_portfolio() -> list[str]:
    """Load stock tickers from portfolio.json.

    Returns:
        List of stock ticker symbols.

    Raises:
        FileNotFoundError: If portfolio file does not exist.
        json.JSONDecodeError: If JSON is malformed.
    """
    paths = load_paths()
    portfolio_path = Path(paths["portfolio"])

    if not portfolio_path.exists():
        return []

    with open(portfolio_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    return data.get("stocks", [])


def save_portfolio(stocks: list[str]) -> None:
    """Save stock tickers to portfolio.json.

    Args:
        stocks: List of stock ticker symbols.
    """
    paths = load_paths()
    portfolio_path = Path(paths["portfolio"])

    data = {
        "stocks": stocks,
        "last_check": datetime.now().isoformat(),
        "check_interval_minutes": 60,
    }

    with open(portfolio_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def load_telegram_config() -> dict:
    """Load Telegram bot configuration from .env and telegram_config.json.

    Returns:
        Dictionary with bot_token, chat_id, and other settings.

    Raises:
        FileNotFoundError: If telegram_config.json does not exist.
        ValueError: If required environment variables are missing.
        json.JSONDecodeError: If JSON is malformed.
    """
    # Load bot token and chat ID from environment variables
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")

    if not bot_token:
        raise ValueError(
            "TELEGRAM_BOT_TOKEN not found in environment. "
            "Please set it in .env file or environment variables."
        )

    if not chat_id:
        raise ValueError(
            "TELEGRAM_CHAT_ID not found in environment. "
            "Please set it in .env file or environment variables."
        )

    # Load other configuration from JSON file
    paths = load_paths()
    config_path = Path(paths["telegram_config"])

    if not config_path.exists():
        raise FileNotFoundError(f"Telegram config not found: {config_path}")

    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)

    # Merge environment variables with config
    config["bot_token"] = bot_token
    config["chat_id"] = chat_id

    return config


def fetch_and_classify_news(
    tickers: list[str], max_news_per_ticker: int = 10, relevance_threshold: float = 0.5
) -> list[tuple[NewsItem, SentimentResult]]:
    """Fetch news for tickers and classify sentiment.

    Args:
        tickers: List of stock ticker symbols.
        max_news_per_ticker: Maximum news items to fetch per ticker.
        relevance_threshold: Minimum confidence for positive/negative sentiment.

    Returns:
        List of (NewsItem, SentimentResult) tuples for relevant news only.
    """
    paths = load_paths()
    model_cache = Path(paths["model_cache"])

    scraper = FinvizScraper()
    classifier = SentimentClassifier(model_cache_dir=model_cache)

    all_news = scraper.fetch_multiple_tickers(
        tickers, max_news_per_ticker=max_news_per_ticker
    )

    classified_news = []

    for ticker, news_items in all_news.items():
        for news in news_items:
            sentiment = classifier.classify(news.headline)

            if sentiment.label != "neutral" and sentiment.score >= relevance_threshold:
                classified_news.append((news, sentiment))

    classified_news.sort(key=lambda x: x[0].timestamp, reverse=True)

    return classified_news


def setup_bot(
    portfolio_path: Path,
    bot_token: str,
    model_cache_dir: Path | None = None,
    ticker_suggestions_path: Path | None = None,
) -> StockNewsBot:
    """Set up Telegram bot instance.

    Args:
        portfolio_path: Path to portfolio.json file.
        bot_token: Telegram bot API token.
        model_cache_dir: Directory to cache ML models (optional).
        ticker_suggestions_path: Path to ticker suggestions JSON (optional).

    Returns:
        Initialized StockNewsBot instance.
    """

    def on_add_stock(ticker: str):
        logger.info(f"Stock added to portfolio: {ticker}")

    def on_remove_stock(ticker: str):
        logger.info(f"Stock removed from portfolio: {ticker}")

    bot = StockNewsBot(
        bot_token=bot_token,
        portfolio_path=portfolio_path,
        on_add_stock=on_add_stock,
        on_remove_stock=on_remove_stock,
        model_cache_dir=model_cache_dir,
        ticker_suggestions_path=ticker_suggestions_path,
    )

    return bot
