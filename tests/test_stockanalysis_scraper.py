"""Tests for StockAnalysisScraper class."""

from unittest.mock import MagicMock, patch

import pytest

from resources import StockAnalysisScraper, NewsItem


@pytest.fixture
def scraper():
    """Create StockAnalysisScraper instance."""
    return StockAnalysisScraper(timeout=5)


@pytest.fixture
def mock_html():
    """Mock StockAnalysis HTML response."""
    return """
    <html>
        <body>
            <div id="news">
                <a href="/news/article1">Microsoft announces new AI features</a>
                <time datetime="2024-01-19T10:30:00Z"></time>
                <a href="https://stockanalysis.com/news/article2">Tech stock rallies</a>
                <time datetime="2024-01-19T09:15:00Z"></time>
            </div>
        </body>
    </html>
    """


def test_scraper_initialization(scraper):
    """Test StockAnalysisScraper initializes correctly."""
    assert scraper.timeout == 5
    assert scraper.base_url == "https://stockanalysis.com/stocks"
    assert "User-Agent" in scraper.headers


@patch("resources.stockanalysis_scraper.requests.get")
def test_fetch_news_success(mock_get, scraper, mock_html):
    """Test successful news fetching."""
    mock_response = MagicMock()
    mock_response.content = mock_html.encode()
    mock_response.raise_for_status = MagicMock()
    mock_get.return_value = mock_response

    news = scraper.fetch_news("MSFT", max_news=5)

    assert isinstance(news, list)
    assert len(news) == 2
    assert all(isinstance(item, NewsItem) for item in news)
    assert news[0].ticker == "MSFT"
    assert "Microsoft" in news[0].headline
    assert news[0].source == "StockAnalysis"


@patch("resources.stockanalysis_scraper.requests.get")
def test_fetch_news_empty_ticker(mock_get, scraper):
    """Test fetching news with empty ticker raises error."""
    with pytest.raises(ValueError, match="Ticker cannot be empty"):
        scraper.fetch_news("")


@patch("resources.stockanalysis_scraper.requests.get")
def test_fetch_news_no_news_section(mock_get, scraper):
    """Test handling missing news section."""
    mock_response = MagicMock()
    mock_response.content = b"<html><body>No news section</body></html>"
    mock_response.raise_for_status = MagicMock()
    mock_get.return_value = mock_response

    news = scraper.fetch_news("MSFT")

    assert isinstance(news, list)
    assert len(news) == 0


@patch("resources.stockanalysis_scraper.requests.get")
def test_fetch_news_http_error(mock_get, scraper):
    """Test handling HTTP errors."""
    mock_get.side_effect = Exception("Network error")

    with pytest.raises(Exception, match="Network error"):
        scraper.fetch_news("MSFT")


@patch("resources.stockanalysis_scraper.requests.get")
def test_fetch_multiple_tickers(mock_get, scraper, mock_html):
    """Test fetching news for multiple tickers."""
    mock_response = MagicMock()
    mock_response.content = mock_html.encode()
    mock_response.raise_for_status = MagicMock()
    mock_get.return_value = mock_response

    results = scraper.fetch_multiple_tickers(["MSFT", "AAPL"], max_news_per_ticker=3)

    assert isinstance(results, dict)
    assert "MSFT" in results
    assert "AAPL" in results
    assert isinstance(results["MSFT"], list)
    assert isinstance(results["AAPL"], list)


@patch("resources.stockanalysis_scraper.requests.get")
def test_fetch_multiple_tickers_with_failure(mock_get, scraper):
    """Test fetching multiple tickers when one fails."""

    def side_effect(*args, **kwargs):
        if "msft" in str(args).lower():
            raise Exception("Error")
        mock_response = MagicMock()
        mock_response.content = b"<html><body></body></html>"
        mock_response.raise_for_status = MagicMock()
        return mock_response

    mock_get.side_effect = side_effect

    results = scraper.fetch_multiple_tickers(["MSFT", "AAPL"])

    assert results["MSFT"] == []
    assert isinstance(results["AAPL"], list)


@patch("resources.stockanalysis_scraper.requests.get")
def test_fetch_news_url_formatting(mock_get, scraper):
    """Test URL formatting for relative and absolute paths."""
    mock_html = """
    <html>
        <div id="news">
            <a href="/news/relative">Relative URL</a>
            <a href="https://stockanalysis.com/news/absolute">Absolute URL</a>
        </div>
    </html>
    """
    mock_response = MagicMock()
    mock_response.content = mock_html.encode()
    mock_response.raise_for_status = MagicMock()
    mock_get.return_value = mock_response

    news = scraper.fetch_news("MSFT")

    assert len(news) == 2
    assert news[0].url.startswith("https://stockanalysis.com")
    assert news[1].url.startswith("https://stockanalysis.com")


@patch("resources.stockanalysis_scraper.requests.get")
def test_fetch_news_lowercase_ticker(mock_get, scraper):
    """Test that ticker is converted to lowercase for URL."""
    mock_response = MagicMock()
    mock_response.content = b"<html><body></body></html>"
    mock_response.raise_for_status = MagicMock()
    mock_get.return_value = mock_response

    scraper.fetch_news("MSFT")

    mock_get.assert_called_once()
    call_args = mock_get.call_args[0][0]
    assert "/msft/" in call_args
