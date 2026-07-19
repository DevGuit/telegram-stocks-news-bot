"""Finviz News Scraper - Fetches latest stock news from Finviz.

Data flow:
  Stock ticker → HTTP request → Finviz HTML → BeautifulSoup parsing → News list
"""

from dataclasses import dataclass
from datetime import datetime

import requests
from bs4 import BeautifulSoup


@dataclass
class NewsItem:
    """Single news item from Finviz."""

    timestamp: datetime
    headline: str
    source: str
    url: str
    ticker: str


class FinvizScraper:
    """Scrape latest news for stocks from Finviz."""

    def __init__(self, timeout: int = 10):
        """Initialize Finviz scraper.

        Args:
            timeout: HTTP request timeout in seconds.
        """
        self.timeout = timeout
        self.base_url = "https://finviz.com/quote.ashx"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        }

    def fetch_news(self, ticker: str, max_news: int = 10) -> list[NewsItem]:
        """Fetch latest news for a stock ticker.

        Args:
            ticker: Stock ticker symbol (e.g., "AAPL").
            max_news: Maximum number of news items to return.

        Returns:
            List of NewsItem objects sorted by timestamp (newest first).

        Raises:
            requests.RequestException: If HTTP request fails.
            ValueError: If ticker is invalid or page parsing fails.
        """
        if not ticker or not ticker.strip():
            raise ValueError("Ticker cannot be empty")

        ticker = ticker.strip().upper()

        params = {"t": ticker}
        response = requests.get(
            self.base_url, params=params, headers=self.headers, timeout=self.timeout
        )
        response.raise_for_status()

        soup = BeautifulSoup(response.content, "html.parser")

        news_table = soup.find("table", {"id": "news-table"})
        if not news_table:
            raise ValueError(f"Could not find news table for ticker {ticker}")

        news_items = []
        rows = news_table.find_all("tr")

        current_date = None

        for row in rows[:max_news]:
            cols = row.find_all("td")
            if len(cols) < 2:
                continue

            time_cell = cols[0]
            news_cell = cols[1]

            time_text = time_cell.get_text(strip=True)

            if len(time_text.split()) == 2:
                current_date = time_text.split()[0]
                time_str = time_text.split()[1]
            else:
                time_str = time_text

            if not current_date:
                continue

            link_tag = news_cell.find("a")
            if not link_tag:
                continue

            headline = link_tag.get_text(strip=True)
            url = link_tag.get("href", "")

            source_span = news_cell.find("span")
            source = source_span.get_text(strip=True) if source_span else "Unknown"

            try:
                timestamp = self._parse_timestamp(current_date, time_str)
            except Exception:
                continue

            news_items.append(
                NewsItem(
                    timestamp=timestamp,
                    headline=headline,
                    source=source,
                    url=url,
                    ticker=ticker,
                )
            )

        return news_items

    def _parse_timestamp(self, date_str: str, time_str: str) -> datetime:
        """Parse Finviz date and time strings into datetime object.

        Args:
            date_str: Date string (e.g., "Jan-19-24" or "Today").
            time_str: Time string (e.g., "10:30AM").

        Returns:
            Parsed datetime object.
        """
        if date_str.lower() == "today":
            date_str = datetime.now().strftime("%b-%d-%y")

        datetime_str = f"{date_str} {time_str}"

        return datetime.strptime(datetime_str, "%b-%d-%y %I:%M%p")

    def fetch_multiple_tickers(
        self, tickers: list[str], max_news_per_ticker: int = 10
    ) -> dict[str, list[NewsItem]]:
        """Fetch news for multiple tickers.

        Args:
            tickers: List of stock ticker symbols.
            max_news_per_ticker: Maximum news items per ticker.

        Returns:
            Dictionary mapping ticker to list of NewsItem objects.
        """
        results = {}

        for ticker in tickers:
            try:
                news = self.fetch_news(ticker, max_news=max_news_per_ticker)
                results[ticker] = news
            except Exception:
                results[ticker] = []

        return results


if __name__ == "__main__":
    """Example usage of FinvizScraper."""
    scraper = FinvizScraper()

    print("Fetching news for AAPL...")
    news = scraper.fetch_news("AAPL", max_news=5)

    for item in news:
        print(f"\n[{item.timestamp}] {item.source}")
        print(f"{item.headline}")
        print(f"{item.url}")

    print(f"\n\nFetched {len(news)} news items for AAPL")

    print("\n" + "=" * 60)
    print("Fetching news for multiple tickers...")
    multi_news = scraper.fetch_multiple_tickers(["AAPL", "MSFT"], max_news_per_ticker=3)

    for ticker, items in multi_news.items():
        print(f"\n{ticker}: {len(items)} news items")
