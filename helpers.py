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
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

from resources import (
    NewsItem,
    SentimentClassifier,
    SentimentResult,
    StockAnalysisScraper,
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
    "load_news_cache",
    "save_news_cache",
    "filter_new_news",
    "get_user_timezone",
    "validate_portfolio_tickers",
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


def load_portfolio() -> dict[str, list[str]]:
    """Load tickers from portfolio.json organized by asset type.

    Returns:
        Dictionary mapping asset type to list of tickers.
        E.g., {"stocks": ["AAPL", "MSFT"], "etf": ["INQQ"]}

    Raises:
        FileNotFoundError: If portfolio file does not exist.
        json.JSONDecodeError: If JSON is malformed.
    """
    paths = load_paths()
    portfolio_path = Path(paths["portfolio"])

    if not portfolio_path.exists():
        return {"stocks": [], "etf": []}

    with open(portfolio_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Support both old format (list) and new format (dict with asset types)
    if "stocks" in data or "etf" in data:
        return {
            "stocks": data.get("stocks", []),
            "etf": data.get(
                "etf", data.get("etfs", [])
            ),  # Support both "etf" and "etfs"
        }
    else:
        # Old format - assume all are stocks
        return {"stocks": data.get("stocks", []), "etf": []}


def save_portfolio(portfolio: dict[str, list[str]]) -> None:
    """Save tickers to portfolio.json organized by asset type.

    Args:
        portfolio: Dictionary mapping asset type to list of tickers.
                  E.g., {"stocks": ["AAPL"], "etf": ["INQQ"]}
    """
    paths = load_paths()
    portfolio_path = Path(paths["portfolio"])

    data = {
        "stocks": portfolio.get("stocks", []),
        "etf": portfolio.get("etf", []),
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
    tickers: list[str] | dict[str, list[str]],
    max_news_per_ticker: int = 10,
    relevance_threshold: float = 0.5,
) -> list[tuple[NewsItem, SentimentResult]]:
    """Fetch news for tickers from StockAnalysis and classify sentiment.

    Args:
        tickers: Either a list of tickers (assumes stocks) or a dict mapping
                asset type to list of tickers (e.g., {"stocks": ["AAPL"], "etf": ["INQQ"]}).
        max_news_per_ticker: Maximum news items to fetch per ticker.
        relevance_threshold: Minimum confidence for positive/negative sentiment.

    Returns:
        List of (NewsItem, SentimentResult) tuples for relevant news only (today's news only).
        News is fetched from StockAnalysis.
    """
    paths = load_paths()
    model_cache = Path(paths["model_cache"])

    # Initialize scraper and classifier
    stockanalysis_scraper = StockAnalysisScraper()
    classifier = SentimentClassifier(model_cache_dir=model_cache)

    # Fetch news from StockAnalysis
    try:
        all_news = stockanalysis_scraper.fetch_multiple_tickers(
            tickers, max_news_per_ticker=max_news_per_ticker
        )
    except Exception as e:
        logger.warning(f"Failed to fetch from StockAnalysis: {e}")
        all_news = {}

    classified_news = []
    user_tz = get_user_timezone()
    today = datetime.now(user_tz).date()
    seen_headlines = set()  # Track headlines to avoid duplicates within same fetch

    logger.info(f"Filtering news for today: {today} (timezone: {user_tz})")

    for ticker, news_items in all_news.items():
        for news in news_items:
            # Convert news timestamp to user's timezone for comparison
            news_date = news.timestamp.astimezone(user_tz).date()

            # Only process news from today (in user's timezone)
            if news_date != today:
                logger.debug(
                    f"Skipping old news: {news.headline[:50]}... (date: {news_date})"
                )
                continue

            # Skip duplicate headlines within this fetch (from different sources)
            if news.headline in seen_headlines:
                continue

            seen_headlines.add(news.headline)

            sentiment = classifier.classify(news.headline)

            if sentiment.label != "neutral" and sentiment.score >= relevance_threshold:
                classified_news.append((news, sentiment))

    classified_news.sort(key=lambda x: x[0].timestamp, reverse=True)

    return classified_news


def setup_bot(
    portfolio_path: Path,
    bot_token: str,
    model_cache_dir: Path | None = None,
) -> StockNewsBot:
    """Set up Telegram bot instance.

    Args:
        portfolio_path: Path to portfolio.json file.
        bot_token: Telegram bot API token.
        model_cache_dir: Directory to cache ML models (optional).

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
    )

    return bot


def load_news_cache() -> set[str]:
    """Load previously sent news headlines from cache.

    Returns:
        Set of headline strings that have been sent before.
    """
    paths = load_paths()
    cache_path = Path(paths["news_cache"])

    if not cache_path.exists():
        return set()

    try:
        with open(cache_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return set(data.get("sent_headlines", []))
    except Exception as e:
        logger.warning(f"Failed to load news cache: {e}")
        return set()


def save_news_cache(headlines: set[str]) -> None:
    """Save sent news headlines to cache.

    Args:
        headlines: Set of headline strings that have been sent.
    """
    paths = load_paths()
    cache_path = Path(paths["news_cache"])

    # Create directory if it doesn't exist
    cache_path.parent.mkdir(parents=True, exist_ok=True)

    data = {
        "sent_headlines": list(headlines),
        "last_updated": datetime.now().isoformat(),
    }

    try:
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.error(f"Failed to save news cache: {e}")


def filter_new_news(
    news_items: list[tuple[NewsItem, SentimentResult]], sent_headlines: set[str]
) -> list[tuple[NewsItem, SentimentResult]]:
    """Filter out news that has already been sent.

    Args:
        news_items: List of (NewsItem, SentimentResult) tuples.
        sent_headlines: Set of previously sent headlines.

    Returns:
        List of news items with only new headlines.
    """
    new_news = []

    for news, sentiment in news_items:
        if news.headline not in sent_headlines:
            new_news.append((news, sentiment))

    return new_news


def get_user_timezone() -> ZoneInfo:
    """Get user's timezone from environment or default to CEST.

    Returns:
        ZoneInfo object for user's timezone.
    """
    timezone_str = os.getenv("USER_TIMEZONE", "Europe/Paris")
    return ZoneInfo(timezone_str)


def validate_portfolio_tickers(
    portfolio: dict[str, list[str]]
) -> dict[str, dict[str, list[str]]]:
    """Validate all tickers in portfolio by checking StockAnalysis pages.

    Args:
        portfolio: Dictionary with stocks and ETF lists.

    Returns:
        Dictionary with validation results:
        {
            "stocks": {"valid": [...], "invalid": [...]},
            "etf": {"valid": [...], "invalid": [...]}
        }
    """
    results = {"stocks": {"valid": [], "invalid": []}, "etf": {"valid": [], "invalid": []}}
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
