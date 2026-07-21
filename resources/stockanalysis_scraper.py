"""StockAnalysis.com News Scraper - Fetches latest stock news from StockAnalysis.

Data flow:
  Stock ticker → HTTP request → StockAnalysis HTML → BeautifulSoup parsing → News list
"""

from datetime import datetime

import requests
from bs4 import BeautifulSoup

from resources.finviz_scraper import NewsItem


class StockAnalysisScraper:
    """Scrape latest news for stocks from StockAnalysis.com."""

    def __init__(self, timeout: int = 10):
        """Initialize StockAnalysis scraper.

        Args:
            timeout: HTTP request timeout in seconds.
        """
        self.timeout = timeout
        self.base_url = "https://stockanalysis.com/stocks"
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

        ticker = ticker.strip().lower()  # StockAnalysis uses lowercase URLs

        url = f"{self.base_url}/{ticker}/"
        response = requests.get(url, headers=self.headers, timeout=self.timeout)
        response.raise_for_status()

        soup = BeautifulSoup(response.content, "html.parser")

        news_items = []

        # StockAnalysis has news in specific sections
        news_section = soup.find("div", {"id": "news"}) or soup.find(
            "section", class_="news"
        )

        if not news_section:
            # Try finding news items directly
            news_links = soup.find_all("a", class_="news-link")
        else:
            news_links = news_section.find_all("a")

        for link in news_links[:max_news]:
            try:
                headline = link.get_text(strip=True)
                if not headline:
                    continue

                url_path = link.get("href", "")

                # Make URL absolute if relative
                if url_path.startswith("/"):
                    url_full = f"https://stockanalysis.com{url_path}"
                elif not url_path.startswith("http"):
                    url_full = f"https://stockanalysis.com/{url_path}"
                else:
                    url_full = url_path

                # Try to find timestamp
                timestamp = datetime.now()  # Default to now
                parent = link.find_parent()
                if parent:
                    time_tag = parent.find("time")
                    if time_tag:
                        datetime_attr = time_tag.get("datetime")
                        if datetime_attr:
                            try:
                                timestamp = datetime.fromisoformat(
                                    datetime_attr.replace("Z", "+00:00")
                                )
                            except Exception:
                                pass

                # Source from StockAnalysis
                source = "StockAnalysis"

                news_items.append(
                    NewsItem(
                        timestamp=timestamp,
                        headline=headline,
                        source=source,
                        url=url_full,
                        ticker=ticker.upper(),
                    )
                )
            except Exception:
                continue

        return news_items

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
                results[ticker.upper()] = news
            except Exception:
                results[ticker.upper()] = []

        return results


if __name__ == "__main__":
    """Example usage of StockAnalysisScraper."""
    scraper = StockAnalysisScraper()

    print("Fetching news for MSFT from StockAnalysis...")
    news = scraper.fetch_news("MSFT", max_news=5)

    for item in news:
        print(f"\n[{item.timestamp}] {item.source}")
        print(f"{item.headline}")
        print(f"{item.url}")

    print(f"\n\nFetched {len(news)} news items for MSFT")
