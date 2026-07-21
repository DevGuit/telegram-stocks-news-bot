"""Tests for StockNewsBot class."""

import json
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from resources import NewsItem, SentimentResult, StockNewsBot


@pytest.fixture
def temp_portfolio(tmp_path):
    """Create temporary portfolio file."""
    portfolio_file = tmp_path / "portfolio.json"
    portfolio_file.write_text(
        json.dumps(
            {
                "stocks": ["AAPL", "MSFT"],
                "etf": [],
                "last_check": None,
                "check_interval_minutes": 60,
            }
        )
    )
    return portfolio_file


@pytest.fixture
def bot(temp_portfolio):
    """Create StockNewsBot instance."""
    with patch("resources.telegram_bot.Application"):
        bot = StockNewsBot(bot_token="test_token", portfolio_path=temp_portfolio)
        return bot


def test_bot_initialization(temp_portfolio):
    """Test bot initializes correctly."""
    with patch("resources.telegram_bot.Application") as mock_app:
        bot = StockNewsBot(
            bot_token="test_token",
            portfolio_path=temp_portfolio,
            on_add_stock=lambda x: None,
            on_remove_stock=lambda x: None,
        )

        assert bot.bot_token == "test_token"
        assert bot.portfolio_path == temp_portfolio
        assert bot.on_add_stock is not None
        assert bot.on_remove_stock is not None
        mock_app.builder.assert_called_once()


def test_load_portfolio(bot, temp_portfolio):
    """Test loading portfolio from file."""
    portfolio = bot._load_portfolio()

    assert portfolio == {"stocks": ["AAPL", "MSFT"], "etf": []}


def test_load_portfolio_empty(bot, tmp_path):
    """Test loading non-existent portfolio."""
    bot.portfolio_path = tmp_path / "nonexistent.json"
    portfolio = bot._load_portfolio()

    assert portfolio == {"stocks": [], "etf": []}


def test_save_portfolio(bot, temp_portfolio):
    """Test saving portfolio to file."""
    bot._save_portfolio({"stocks": ["AAPL", "GOOGL", "TSLA"], "etf": ["INQQ"]})

    with open(temp_portfolio, "r") as f:
        data = json.load(f)

    assert data["stocks"] == ["AAPL", "GOOGL", "TSLA"]
    assert data["etf"] == ["INQQ"]
    assert "last_check" in data
    assert "check_interval_minutes" in data


@pytest.mark.asyncio
async def test_cmd_start(bot):
    """Test /start command."""
    mock_update = MagicMock()
    mock_update.message.reply_text = AsyncMock()

    await bot.cmd_start(mock_update, None)

    mock_update.message.reply_text.assert_called_once()
    call_args = mock_update.message.reply_text.call_args[0][0]
    assert "Welcome" in call_args
    assert "/list" in call_args


@pytest.mark.asyncio
async def test_cmd_help(bot):
    """Test /help command."""
    mock_update = MagicMock()
    mock_update.message.reply_text = AsyncMock()

    await bot.cmd_help(mock_update, None)

    mock_update.message.reply_text.assert_called_once()
    call_args = mock_update.message.reply_text.call_args[0][0]
    assert "/list" in call_args
    assert "/addstock" in call_args
    assert "/remove" in call_args


@pytest.mark.asyncio
async def test_cmd_list_with_stocks(bot):
    """Test /list command with stocks in portfolio."""
    mock_update = MagicMock()
    mock_update.message.reply_text = AsyncMock()

    await bot.cmd_list(mock_update, None)

    mock_update.message.reply_text.assert_called_once()
    call_args = mock_update.message.reply_text.call_args[0][0]
    assert "AAPL" in call_args
    assert "MSFT" in call_args
    assert "2 tickers" in call_args


@pytest.mark.asyncio
async def test_cmd_list_empty(bot, tmp_path):
    """Test /list command with empty portfolio."""
    empty_portfolio = tmp_path / "empty.json"
    empty_portfolio.write_text(json.dumps({"stocks": []}))
    bot.portfolio_path = empty_portfolio

    mock_update = MagicMock()
    mock_update.message.reply_text = AsyncMock()

    await bot.cmd_list(mock_update, None)

    mock_update.message.reply_text.assert_called_once()
    call_args = mock_update.message.reply_text.call_args[0][0]
    assert "empty" in call_args.lower()


@pytest.mark.asyncio
async def test_cmd_addstock_new_stock(bot):
    """Test /addstock command with new stock."""
    mock_update = MagicMock()
    mock_update.message.reply_text = AsyncMock()
    mock_context = MagicMock()
    mock_context.args = ["GOOGL"]

    # Mock the validation to return True (valid ticker)
    bot._validate_ticker = AsyncMock(return_value=(True, []))

    await bot.cmd_addstock(mock_update, mock_context)

    portfolio = bot._load_portfolio()
    assert "GOOGL" in portfolio["stocks"]

    # Should be called at least twice: "Validating..." and "Added stock GOOGL"
    assert mock_update.message.reply_text.call_count >= 2

    # Check the last call contains the success message
    last_call = mock_update.message.reply_text.call_args_list[-1][0][0]
    assert "Added stock GOOGL" in last_call


@pytest.mark.asyncio
async def test_cmd_addstock_existing_stock(bot):
    """Test /addstock command with existing stock."""
    mock_update = MagicMock()
    mock_update.message.reply_text = AsyncMock()
    mock_context = MagicMock()
    mock_context.args = ["AAPL"]

    await bot.cmd_addstock(mock_update, mock_context)

    mock_update.message.reply_text.assert_called_once()
    assert "already in" in mock_update.message.reply_text.call_args[0][0]


@pytest.mark.asyncio
async def test_cmd_addstock_no_args(bot):
    """Test /addstock command without arguments."""
    mock_update = MagicMock()
    mock_update.message.reply_text = AsyncMock()
    mock_context = MagicMock()
    mock_context.args = []

    await bot.cmd_addstock(mock_update, mock_context)

    mock_update.message.reply_text.assert_called_once()
    assert "Usage:" in mock_update.message.reply_text.call_args[0][0]


@pytest.mark.asyncio
async def test_cmd_addstock_with_callback(temp_portfolio):
    """Test /addstock command triggers callback."""
    callback_called = []

    def on_add(ticker):
        callback_called.append(ticker)

    with patch("resources.telegram_bot.Application"):
        bot = StockNewsBot(
            bot_token="test_token", portfolio_path=temp_portfolio, on_add_stock=on_add
        )

    # Mock the validation to return True (valid ticker)
    bot._validate_ticker = AsyncMock(return_value=(True, []))

    mock_update = MagicMock()
    mock_update.message.reply_text = AsyncMock()
    mock_context = MagicMock()
    mock_context.args = ["TSLA"]

    await bot.cmd_addstock(mock_update, mock_context)

    assert "TSLA" in callback_called


@pytest.mark.asyncio
async def test_cmd_remove_existing_stock(bot):
    """Test /remove command with existing stock."""
    mock_update = MagicMock()
    mock_update.message.reply_text = AsyncMock()
    mock_context = MagicMock()
    mock_context.args = ["AAPL"]

    await bot.cmd_remove(mock_update, mock_context)

    portfolio = bot._load_portfolio()
    assert "AAPL" not in portfolio["stocks"]
    assert "MSFT" in portfolio["stocks"]
    mock_update.message.reply_text.assert_called_once()
    assert "Removed AAPL" in mock_update.message.reply_text.call_args[0][0]


@pytest.mark.asyncio
async def test_cmd_remove_nonexistent_stock(bot):
    """Test /remove command with non-existent stock."""
    mock_update = MagicMock()
    mock_update.message.reply_text = AsyncMock()
    mock_context = MagicMock()
    mock_context.args = ["GOOGL"]

    await bot.cmd_remove(mock_update, mock_context)

    mock_update.message.reply_text.assert_called_once()
    assert "not in" in mock_update.message.reply_text.call_args[0][0]


@pytest.mark.asyncio
async def test_cmd_remove_no_args(bot):
    """Test /remove command without arguments."""
    mock_update = MagicMock()
    mock_update.message.reply_text = AsyncMock()
    mock_context = MagicMock()
    mock_context.args = []

    await bot.cmd_remove(mock_update, mock_context)

    mock_update.message.reply_text.assert_called_once()
    assert "Usage:" in mock_update.message.reply_text.call_args[0][0]


@pytest.mark.asyncio
async def test_handle_message(bot):
    """Test handling unknown messages."""
    mock_update = MagicMock()
    mock_update.message.reply_text = AsyncMock()

    await bot.handle_message(mock_update, None)

    mock_update.message.reply_text.assert_called_once()
    assert "don't understand" in mock_update.message.reply_text.call_args[0][0].lower()


@pytest.mark.asyncio
async def test_send_news_update(bot):
    """Test sending news updates."""
    news1 = NewsItem(
        timestamp=datetime(2024, 1, 19, 10, 30),
        headline="Apple stock surges",
        source="MarketWatch",
        url="https://example.com/news1",
        ticker="AAPL",
    )

    sentiment1 = SentimentResult(
        label="positive",
        score=0.92,
        label_scores={"positive": 0.92, "negative": 0.05, "neutral": 0.03},
    )

    news_items = [(news1, sentiment1)]

    bot.application.bot.send_message = AsyncMock()

    await bot.send_news_update("123456", news_items)

    bot.application.bot.send_message.assert_called_once()
    call_args = bot.application.bot.send_message.call_args

    assert call_args[1]["chat_id"] == "123456"
    assert "AAPL" in call_args[1]["text"]
    assert "positive" in call_args[1]["text"].lower()
    assert "92%" in call_args[1]["text"]


@pytest.mark.asyncio
async def test_send_news_update_empty(bot):
    """Test sending empty news update."""
    bot.application.bot.send_message = AsyncMock()

    await bot.send_news_update("123456", [])

    bot.application.bot.send_message.assert_not_called()


def test_get_sentiment_emoji(bot):
    """Test sentiment emoji mapping."""
    assert bot._get_sentiment_emoji("positive") == "🟢"
    assert bot._get_sentiment_emoji("negative") == "🔴"
    assert bot._get_sentiment_emoji("neutral") == "⚪"
    assert bot._get_sentiment_emoji("unknown") == "⚪"
