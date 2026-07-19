"""Tests for FinvizScraper class."""

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from resources import FinvizScraper, NewsItem


@pytest.fixture
def scraper():
    """Create FinvizScraper instance."""
    return FinvizScraper(timeout=5)


@pytest.fixture
def mock_html():
    """Mock Finviz HTML response."""
    return """
    <html>
        <table id="news-table">
            <tr>
                <td>Jan-19-24 10:30AM</td>
                <td>
                    <a href="https://example.com/news1">Apple earnings beat expectations</a>
                    <span>MarketWatch</span>
                </td>
            </tr>
            <tr>
                <td>09:15AM</td>
                <td>
                    <a href="https://example.com/news2">Stock price surges</a>
                    <span>Reuters</span>
                </td>
            </tr>
        </table>
    </html>
    """


def test_scraper_initialization(scraper):
    """Test FinvizScraper initializes correctly."""
    assert scraper.timeout == 5
    assert scraper.base_url == "https://finviz.com/quote.ashx"
    assert "User-Agent" in scraper.headers


def test_parse_timestamp(scraper):
    """Test timestamp parsing."""
    timestamp = scraper._parse_timestamp("Jan-19-24", "10:30AM")
    assert isinstance(timestamp, datetime)
    assert timestamp.month == 1
    assert timestamp.day == 19
    assert timestamp.hour == 10
    assert timestamp.minute == 30


def test_parse_timestamp_today(scraper):
    """Test parsing 'Today' date."""
    timestamp = scraper._parse_timestamp("Today", "10:30AM")
    assert isinstance(timestamp, datetime)
    assert timestamp.hour == 10
    assert timestamp.minute == 30


@patch("resources.finviz_scraper.requests.get")
def test_fetch_news_success(mock_get, scraper, mock_html):
    """Test successful news fetching."""
    mock_response = MagicMock()
    mock_response.content = mock_html.encode()
    mock_response.raise_for_status = MagicMock()
    mock_get.return_value = mock_response

    news = scraper.fetch_news("AAPL", max_news=5)

    assert isinstance(news, list)
    assert len(news) == 2
    assert all(isinstance(item, NewsItem) for item in news)
    assert news[0].ticker == "AAPL"
    assert "Apple earnings" in news[0].headline


@patch("resources.finviz_scraper.requests.get")
def test_fetch_news_empty_ticker(mock_get, scraper):
    """Test fetching news with empty ticker raises error."""
    with pytest.raises(ValueError, match="Ticker cannot be empty"):
        scraper.fetch_news("")


@patch("resources.finviz_scraper.requests.get")
def test_fetch_news_no_table(mock_get, scraper):
    """Test handling missing news table."""
    mock_response = MagicMock()
    mock_response.content = b"<html><body>No news table</body></html>"
    mock_response.raise_for_status = MagicMock()
    mock_get.return_value = mock_response

    with pytest.raises(ValueError, match="Could not find news table"):
        scraper.fetch_news("AAPL")


@patch("resources.finviz_scraper.requests.get")
def test_fetch_news_http_error(mock_get, scraper):
    """Test handling HTTP errors."""
    mock_get.side_effect = Exception("Network error")

    with pytest.raises(Exception, match="Network error"):
        scraper.fetch_news("AAPL")


@patch("resources.finviz_scraper.requests.get")
def test_fetch_multiple_tickers(mock_get, scraper, mock_html):
    """Test fetching news for multiple tickers."""
    mock_response = MagicMock()
    mock_response.content = mock_html.encode()
    mock_response.raise_for_status = MagicMock()
    mock_get.return_value = mock_response

    results = scraper.fetch_multiple_tickers(["AAPL", "MSFT"], max_news_per_ticker=3)

    assert isinstance(results, dict)
    assert "AAPL" in results
    assert "MSFT" in results
    assert isinstance(results["AAPL"], list)
    assert isinstance(results["MSFT"], list)


@patch("resources.finviz_scraper.requests.get")
def test_fetch_multiple_tickers_with_failure(mock_get, scraper):
    """Test fetching multiple tickers when one fails."""

    def side_effect(*args, **kwargs):
        if "AAPL" in str(args):
            raise Exception("Error")
        mock_response = MagicMock()
        mock_response.content = b"<html><table id='news-table'></table></html>"
        mock_response.raise_for_status = MagicMock()
        return mock_response

    mock_get.side_effect = side_effect

    results = scraper.fetch_multiple_tickers(["AAPL", "MSFT"])

    assert results["AAPL"] == []
    assert isinstance(results["MSFT"], list)


def test_news_item_dataclass():
    """Test NewsItem dataclass."""
    news = NewsItem(
        timestamp=datetime(2024, 1, 19, 10, 30),
        headline="Test headline",
        source="Test Source",
        url="https://example.com",
        ticker="AAPL",
    )

    assert news.ticker == "AAPL"
    assert news.headline == "Test headline"
    assert news.source == "Test Source"
    assert news.url == "https://example.com"
    assert isinstance(news.timestamp, datetime)
