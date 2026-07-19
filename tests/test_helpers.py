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
    paths_data = {
        "portfolio": str(portfolio_file),
        "telegram_config": str(telegram_config),
        "model_cache": str(tmp_path / "models"),
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


@patch("helpers.FinvizScraper")
@patch("helpers.SentimentClassifier")
def test_fetch_and_classify_news(
    mock_classifier_class, mock_scraper_class, temp_paths_file, monkeypatch
):
    """Test fetching and classifying news."""
    monkeypatch.chdir(temp_paths_file.parent.parent)

    mock_scraper = MagicMock()
    news1 = NewsItem(
        timestamp=datetime(2024, 1, 19, 10, 30),
        headline="Apple stock surges",
        source="MarketWatch",
        url="https://example.com",
        ticker="AAPL",
    )
    news2 = NewsItem(
        timestamp=datetime(2024, 1, 19, 9, 15),
        headline="Microsoft earnings beat",
        source="Reuters",
        url="https://example.com",
        ticker="MSFT",
    )
    mock_scraper.fetch_multiple_tickers.return_value = {
        "AAPL": [news1],
        "MSFT": [news2],
    }
    mock_scraper_class.return_value = mock_scraper

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
    mock_classifier.classify.side_effect = [sentiment1, sentiment2]
    mock_classifier_class.return_value = mock_classifier

    tickers = ["AAPL", "MSFT"]
    results = helpers.fetch_and_classify_news(tickers, max_news_per_ticker=5)

    assert len(results) == 1
    assert results[0][0].ticker == "AAPL"
    assert results[0][1].label == "positive"


@patch("helpers.FinvizScraper")
@patch("helpers.SentimentClassifier")
def test_fetch_and_classify_news_filters_neutral(
    mock_classifier_class, mock_scraper_class, temp_paths_file, monkeypatch
):
    """Test that neutral news is filtered out."""
    monkeypatch.chdir(temp_paths_file.parent.parent)

    mock_scraper = MagicMock()
    news1 = NewsItem(
        timestamp=datetime(2024, 1, 19, 10, 30),
        headline="Company announces quarterly report",
        source="MarketWatch",
        url="https://example.com",
        ticker="AAPL",
    )
    mock_scraper.fetch_multiple_tickers.return_value = {"AAPL": [news1]}
    mock_scraper_class.return_value = mock_scraper

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


@patch("helpers.FinvizScraper")
@patch("helpers.SentimentClassifier")
def test_fetch_and_classify_news_filters_low_confidence(
    mock_classifier_class, mock_scraper_class, temp_paths_file, monkeypatch
):
    """Test that low confidence news is filtered out."""
    monkeypatch.chdir(temp_paths_file.parent.parent)

    mock_scraper = MagicMock()
    news1 = NewsItem(
        timestamp=datetime(2024, 1, 19, 10, 30),
        headline="Weak signal",
        source="MarketWatch",
        url="https://example.com",
        ticker="AAPL",
    )
    mock_scraper.fetch_multiple_tickers.return_value = {"AAPL": [news1]}
    mock_scraper_class.return_value = mock_scraper

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

    bot = helpers.setup_bot(portfolio_path, "test_token")

    mock_bot_class.assert_called_once()
    call_kwargs = mock_bot_class.call_args[1]
    assert call_kwargs["bot_token"] == "test_token"
    assert call_kwargs["portfolio_path"] == portfolio_path
    assert callable(call_kwargs["on_add_stock"])
    assert callable(call_kwargs["on_remove_stock"])
