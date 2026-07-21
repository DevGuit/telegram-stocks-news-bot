"""Tests for helper functions."""

import json
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

import helpers
from resources import NewsItem, SentimentResult


@pytest.fixture
def temp_paths_file(tmp_path):
    """Create temporary paths.json file."""
    json_dir = tmp_path / "json"
    json_dir.mkdir()

    portfolio_file = json_dir / "portfolio.json"
    portfolio_file.write_text(json.dumps({"stocks": ["AAPL", "MSFT"]}))

    telegram_config = json_dir / "telegram_config.json"
    telegram_config.write_text(
        json.dumps(
            {
                "bot_token": "test_token",
                "chat_id": "123456",
                "polling_interval_seconds": 2,
                "news_check_interval_minutes": 60,
            }
        )
    )

    paths_file = json_dir / "paths.json"
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    paths_data = {
        "portfolio": str(portfolio_file),
        "telegram_config": str(telegram_config),
        "model_cache": str(tmp_path / "models"),
        "news_cache": str(data_dir / "news_cache.json"),
    }
    paths_file.write_text(json.dumps(paths_data))

    return json_dir / "paths.json"


def test_load_paths(temp_paths_file, monkeypatch):
    """Test loading paths from json/paths.json."""
    monkeypatch.chdir(temp_paths_file.parent.parent)

    paths = helpers.load_paths()

    assert isinstance(paths, dict)
    assert "portfolio" in paths
    assert "telegram_config" in paths
    assert "model_cache" in paths


def test_load_paths_missing_file(tmp_path, monkeypatch):
    """Test loading paths when file doesn't exist."""
    monkeypatch.chdir(tmp_path)

    with pytest.raises(FileNotFoundError, match="json/paths.json not found"):
        helpers.load_paths()


def test_setup_logging():
    """Test logging setup."""
    import logging

    # Reset logging to ensure clean state
    for handler in logging.root.handlers[:]:
        logging.root.removeHandler(handler)

    helpers.setup_logging("DEBUG")

    logger = logging.getLogger()
    assert logger.level == logging.DEBUG


def test_load_portfolio(temp_paths_file, monkeypatch):
    """Test loading portfolio."""
    monkeypatch.chdir(temp_paths_file.parent.parent)

    stocks = helpers.load_portfolio()

    assert stocks == ["AAPL", "MSFT"]


def test_load_portfolio_empty(tmp_path, monkeypatch):
    """Test loading empty portfolio."""
    json_dir = tmp_path / "json"
    json_dir.mkdir()

    paths_file = json_dir / "paths.json"
    portfolio_file = json_dir / "portfolio.json"

    paths_file.write_text(json.dumps({"portfolio": str(portfolio_file)}))

    monkeypatch.chdir(tmp_path)

    stocks = helpers.load_portfolio()

    assert stocks == []


def test_save_portfolio(temp_paths_file, monkeypatch):
    """Test saving portfolio."""
    monkeypatch.chdir(temp_paths_file.parent.parent)

    new_stocks = ["AAPL", "GOOGL", "TSLA"]
    helpers.save_portfolio(new_stocks)

    paths = helpers.load_paths()
    portfolio_path = Path(paths["portfolio"])

    with open(portfolio_path, "r") as f:
        data = json.load(f)

    assert data["stocks"] == new_stocks
    assert "last_check" in data
    assert isinstance(data["last_check"], str)


def test_load_telegram_config(temp_paths_file, monkeypatch):
    """Test loading Telegram configuration."""
    monkeypatch.chdir(temp_paths_file.parent.parent)

    # Mock environment variables
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test_token")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "123456")

    config = helpers.load_telegram_config()

    assert config["bot_token"] == "test_token"
    assert config["chat_id"] == "123456"
    assert config["polling_interval_seconds"] == 2
    assert config["news_check_interval_minutes"] == 60


def test_load_telegram_config_missing(tmp_path, monkeypatch):
    """Test loading missing Telegram config."""
    json_dir = tmp_path / "json"
    json_dir.mkdir()

    paths_file = json_dir / "paths.json"
    paths_file.write_text(
        json.dumps({"telegram_config": str(json_dir / "nonexistent.json")})
    )

    monkeypatch.chdir(tmp_path)

    with pytest.raises(FileNotFoundError, match="Telegram config not found"):
        helpers.load_telegram_config()


@patch("helpers.StockAnalysisScraper")
@patch("helpers.FinvizScraper")
@patch("helpers.SentimentClassifier")
def test_fetch_and_classify_news(
    mock_classifier_class,
    mock_finviz_class,
    mock_stockanalysis_class,
    temp_paths_file,
    monkeypatch,
):
    """Test fetching and classifying news from multiple sources."""
    monkeypatch.chdir(temp_paths_file.parent.parent)

    # Use today's date so news passes the date filter
    today = datetime.now()
    news1 = NewsItem(
        timestamp=datetime(today.year, today.month, today.day, 10, 30),
        headline="Apple stock surges",
        source="Finviz",
        url="https://example.com/1",
        ticker="AAPL",
    )
    news2 = NewsItem(
        timestamp=datetime(today.year, today.month, today.day, 9, 15),
        headline="Microsoft earnings beat",
        source="StockAnalysis",
        url="https://example.com/2",
        ticker="MSFT",
    )
    news3 = NewsItem(
        timestamp=datetime(today.year, today.month, today.day, 11, 0),
        headline="Google announces AI breakthrough",
        source="StockAnalysis",
        url="https://example.com/3",
        ticker="GOOGL",
    )

    # Mock both scrapers
    mock_finviz = MagicMock()
    mock_finviz.fetch_multiple_tickers.return_value = {"AAPL": [news1]}
    mock_finviz_class.return_value = mock_finviz

    mock_stockanalysis = MagicMock()
    mock_stockanalysis.fetch_multiple_tickers.return_value = {
        "MSFT": [news2],
        "GOOGL": [news3],
    }
    mock_stockanalysis_class.return_value = mock_stockanalysis

    mock_classifier = MagicMock()
    sentiment1 = SentimentResult(
        label="positive",
        score=0.92,
        label_scores={"positive": 0.92, "negative": 0.05, "neutral": 0.03},
    )
    sentiment2 = SentimentResult(
        label="neutral",
        score=0.85,
        label_scores={"positive": 0.10, "negative": 0.05, "neutral": 0.85},
    )
    sentiment3 = SentimentResult(
        label="positive",
        score=0.88,
        label_scores={"positive": 0.88, "negative": 0.03, "neutral": 0.09},
    )
    mock_classifier.classify.side_effect = [sentiment1, sentiment2, sentiment3]
    mock_classifier_class.return_value = mock_classifier

    tickers = ["AAPL", "MSFT", "GOOGL"]
    results = helpers.fetch_and_classify_news(tickers, max_news_per_ticker=5)

    assert len(results) == 2
    assert results[0][0].headline == "Google announces AI breakthrough"
    assert results[0][1].label == "positive"
    assert results[1][0].headline == "Apple stock surges"
    assert results[1][1].label == "positive"


@patch("helpers.StockAnalysisScraper")
@patch("helpers.FinvizScraper")
@patch("helpers.SentimentClassifier")
def test_fetch_and_classify_news_filters_neutral(
    mock_classifier_class,
    mock_finviz_class,
    mock_stockanalysis_class,
    temp_paths_file,
    monkeypatch,
):
    """Test that neutral news is filtered out."""
    monkeypatch.chdir(temp_paths_file.parent.parent)

    # Use today's date so news passes the date filter
    today = datetime.now()
    news1 = NewsItem(
        timestamp=datetime(today.year, today.month, today.day, 10, 30),
        headline="Company announces quarterly report",
        source="Finviz",
        url="https://example.com",
        ticker="AAPL",
    )

    # Mock both scrapers
    mock_finviz = MagicMock()
    mock_finviz.fetch_multiple_tickers.return_value = {"AAPL": [news1]}
    mock_finviz_class.return_value = mock_finviz

    mock_stockanalysis = MagicMock()
    mock_stockanalysis.fetch_multiple_tickers.return_value = {}
    mock_stockanalysis_class.return_value = mock_stockanalysis

    mock_classifier = MagicMock()
    sentiment = SentimentResult(
        label="neutral",
        score=0.90,
        label_scores={"positive": 0.05, "negative": 0.05, "neutral": 0.90},
    )
    mock_classifier.classify.return_value = sentiment
    mock_classifier_class.return_value = mock_classifier

    results = helpers.fetch_and_classify_news(["AAPL"])

    assert len(results) == 0


@patch("helpers.StockAnalysisScraper")
@patch("helpers.FinvizScraper")
@patch("helpers.SentimentClassifier")
def test_fetch_and_classify_news_filters_low_confidence(
    mock_classifier_class,
    mock_finviz_class,
    mock_stockanalysis_class,
    temp_paths_file,
    monkeypatch,
):
    """Test that low confidence news is filtered out."""
    monkeypatch.chdir(temp_paths_file.parent.parent)

    # Use today's date so news passes the date filter
    today = datetime.now()
    news1 = NewsItem(
        timestamp=datetime(today.year, today.month, today.day, 10, 30),
        headline="Weak signal",
        source="Finviz",
        url="https://example.com",
        ticker="AAPL",
    )

    # Mock both scrapers
    mock_finviz = MagicMock()
    mock_finviz.fetch_multiple_tickers.return_value = {"AAPL": [news1]}
    mock_finviz_class.return_value = mock_finviz

    mock_stockanalysis = MagicMock()
    mock_stockanalysis.fetch_multiple_tickers.return_value = {}
    mock_stockanalysis_class.return_value = mock_stockanalysis

    mock_classifier = MagicMock()
    sentiment = SentimentResult(
        label="positive",
        score=0.40,
        label_scores={"positive": 0.40, "negative": 0.35, "neutral": 0.25},
    )
    mock_classifier.classify.return_value = sentiment
    mock_classifier_class.return_value = mock_classifier

    results = helpers.fetch_and_classify_news(["AAPL"], relevance_threshold=0.5)

    assert len(results) == 0


@patch("helpers.StockNewsBot")
def test_setup_bot(mock_bot_class, temp_paths_file, monkeypatch):
    """Test bot setup."""
    monkeypatch.chdir(temp_paths_file.parent.parent)

    paths = helpers.load_paths()
    portfolio_path = Path(paths["portfolio"])

    helpers.setup_bot(portfolio_path, "test_token")

    mock_bot_class.assert_called_once()
    call_kwargs = mock_bot_class.call_args[1]
    assert call_kwargs["bot_token"] == "test_token"
    assert call_kwargs["portfolio_path"] == portfolio_path
    assert callable(call_kwargs["on_add_stock"])
    assert callable(call_kwargs["on_remove_stock"])


def test_news_cache(temp_paths_file, monkeypatch):
    """Test news cache load and save."""
    monkeypatch.chdir(temp_paths_file.parent.parent)

    # Initially cache should be empty
    sent_headlines = helpers.load_news_cache()
    assert sent_headlines == set()

    # Save some headlines
    test_headlines = {"Headline 1", "Headline 2", "Headline 3"}
    helpers.save_news_cache(test_headlines)

    # Load and verify
    loaded_headlines = helpers.load_news_cache()
    assert loaded_headlines == test_headlines


def test_filter_new_news():
    """Test filtering duplicate news."""
    today = datetime.now()

    news1 = NewsItem(
        timestamp=datetime(today.year, today.month, today.day, 10, 30),
        headline="Apple stock surges",
        source="MarketWatch",
        url="https://example.com/1",
        ticker="AAPL",
    )
    news2 = NewsItem(
        timestamp=datetime(today.year, today.month, today.day, 11, 0),
        headline="Microsoft earnings beat",
        source="Reuters",
        url="https://example.com/2",
        ticker="MSFT",
    )
    news3 = NewsItem(
        timestamp=datetime(today.year, today.month, today.day, 11, 30),
        headline="Apple stock surges",  # Duplicate headline
        source="Bloomberg",
        url="https://example.com/3",
        ticker="AAPL",
    )

    sentiment = SentimentResult(
        label="positive",
        score=0.9,
        label_scores={"positive": 0.9, "negative": 0.05, "neutral": 0.05},
    )

    all_news = [(news1, sentiment), (news2, sentiment), (news3, sentiment)]

    # No sent headlines - all news should be returned
    sent_headlines = set()
    filtered = helpers.filter_new_news(all_news, sent_headlines)
    assert len(filtered) == 3

    # Mark first headline as sent - should filter out news1 and news3 (duplicate)
    sent_headlines = {"Apple stock surges"}
    filtered = helpers.filter_new_news(all_news, sent_headlines)
    assert len(filtered) == 1
    assert filtered[0][0].headline == "Microsoft earnings beat"

    # Mark all as sent - should return empty
    sent_headlines = {"Apple stock surges", "Microsoft earnings beat"}
    filtered = helpers.filter_new_news(all_news, sent_headlines)
    assert len(filtered) == 0
