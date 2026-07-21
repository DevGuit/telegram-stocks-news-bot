"""StockAnalysis.com News Scraper - Fetches latest stock news from StockAnalysis.

Data flow:
  Stock ticker → HTTP request → StockAnalysis HTML → BeautifulSoup parsing → News list
"""

import re
from dataclasses import dataclass
from datetime import datetime, timedelta

import requests
from bs4 import BeautifulSoup


@dataclass
class NewsItem:
    """Single news item from a scraper."""

    timestamp: datetime
    headline: str
    source: str
    url: str
    ticker: str


class StockAnalysisScraper:
    """Scrape latest news for stocks from StockAnalysis.com."""

    def __init__(self, timeout: int = 10):
        """Initialize StockAnalysis scraper.

        Args:
            timeout: HTTP request timeout in seconds.
        """
        self.timeout = timeout
        self.base_url = "https://stockanalysis.com"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        }

    def fetch_news(
        self, ticker: str, max_news: int = 10, asset_type: str = "stocks"
    ) -> list[NewsItem]:
        """Fetch latest news for a ticker.

        Args:
            ticker: Ticker symbol (e.g., "AAPL" for stocks, "INQQ" for ETFs).
            max_news: Maximum number of news items to return.
            asset_type: Asset type - "stocks" or "etf" (default: "stocks").

        Returns:
            List of NewsItem objects sorted by timestamp (newest first).

        Raises:
            requests.RequestException: If HTTP request fails.
            ValueError: If ticker or asset_type is invalid.
        """
        if not ticker or not ticker.strip():
            raise ValueError("Ticker cannot be empty")

        if asset_type not in ["stocks", "etf"]:
            raise ValueError(
                f"Invalid asset_type: {asset_type}. Must be 'stocks' or 'etf'."
            )

        ticker = ticker.strip().lower()  # StockAnalysis uses lowercase URLs

        url = f"{self.base_url}/{asset_type}/{ticker}/"
        response = requests.get(url, headers=self.headers, timeout=self.timeout)
        response.raise_for_status()

        soup = BeautifulSoup(response.content, "html.parser")

        news_items = []

        # Find the "News" heading (H2 tag with "News" text)
        news_heading = soup.find("h2", string=lambda t: t and "news" in t.lower())

        news_links = []
        if news_heading:
            # Get the parent container and find all news links
            # News links have /news/ in href and point to external sources
            container = news_heading.parent
            for _ in range(5):  # Go up parent levels to find the container
                if container:
                    links = container.find_all(
                        "a", href=lambda h: h and "/news/" in h and h.startswith("http")
                    )
                    if links:
                        news_links = links
                        break
                    container = container.parent

        # Fallback: search entire page for news links if heading not found
        if not news_links:
            news_links = soup.find_all(
                "a", href=lambda h: h and "/news/" in h and h.startswith("http")
            )

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

                # Try to find timestamp from relative time text
                timestamp = datetime.now()  # Default to now
                parent = link.find_parent()
                if parent and parent.name == "h3":
                    # Get the flex container (parent of h3)
                    flex_container = parent.parent
                    if flex_container:
                        # Look for div with timestamp text (contains "ago")
                        time_div = flex_container.find(
                            "div", class_=lambda c: c and "text-faded" in c
                        )
                        if time_div:
                            time_text = time_div.get_text(strip=True)
                            # Parse relative time like "1 hour ago - TipRanks"
                            timestamp = self._parse_relative_time(time_text)

                # Extract source from URL domain
                source = "StockAnalysis"
                if url_full.startswith("http"):
                    try:
                        from urllib.parse import urlparse

                        domain = urlparse(url_full).netloc
                        # Remove 'www.' prefix and get main domain name
                        domain = domain.replace("www.", "")
                        # Capitalize first letter
                        source = domain.split(".")[0].capitalize()
                    except Exception:
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

    def _parse_relative_time(self, time_text: str) -> datetime:
        """Parse relative time string like '1 hour ago' or '3 minutes ago' into datetime.

        Args:
            time_text: Text like "1 hour ago - TipRanks" or "3 minutes ago - Invezz"

        Returns:
            datetime object representing the time (in UTC).
        """
        # Default to now if parsing fails
        now = datetime.now()

        # Extract just the time part (before the dash if present)
        if " - " in time_text:
            time_part = time_text.split(" - ")[0].strip()
        else:
            time_part = time_text.strip()

        # Parse patterns like "1 hour ago", "3 minutes ago", "2 days ago"
        pattern = r"(\d+)\s*(second|minute|hour|day|week|month)s?\s*ago"
        match = re.search(pattern, time_part, re.IGNORECASE)

        if not match:
            return now

        amount = int(match.group(1))
        unit = match.group(2).lower()

        # Calculate the datetime
        if unit == "second":
            return now - timedelta(seconds=amount)
        elif unit == "minute":
            return now - timedelta(minutes=amount)
        elif unit == "hour":
            return now - timedelta(hours=amount)
        elif unit == "day":
            return now - timedelta(days=amount)
        elif unit == "week":
            return now - timedelta(weeks=amount)
        elif unit == "month":
            # Approximate: 30 days per month
            return now - timedelta(days=amount * 30)

        return now

    def fetch_multiple_tickers(
        self,
        tickers: list[str] | dict[str, list[str]],
        max_news_per_ticker: int = 10,
    ) -> dict[str, list[NewsItem]]:
        """Fetch news for multiple tickers.

        Args:
            tickers: Either a list of tickers (defaults to "stocks") or a dict
                    mapping asset_type to list of tickers (e.g., {"stocks": ["AAPL"], "etf": ["INQQ"]}).
            max_news_per_ticker: Maximum news items per ticker.

        Returns:
            Dictionary mapping ticker to list of NewsItem objects.
        """
        results = {}

        # If list provided, assume all are stocks for backward compatibility
        if isinstance(tickers, list):
            tickers_dict = {"stocks": tickers}
        else:
            tickers_dict = tickers

        for asset_type, ticker_list in tickers_dict.items():
            for ticker in ticker_list:
                try:
                    news = self.fetch_news(
                        ticker, max_news=max_news_per_ticker, asset_type=asset_type
                    )
                    results[ticker.upper()] = news
                except Exception:
                    results[ticker.upper()] = []

        return results


if __name__ == "__main__":
    """Example usage of StockAnalysisScraper."""
    scraper = StockAnalysisScraper()

    print("Fetching news for MSFT (stock) from StockAnalysis...")
    stock_news = scraper.fetch_news("MSFT", max_news=3, asset_type="stocks")

    for item in stock_news:
        print(f"\n[{item.timestamp}] {item.source}")
        print(f"{item.headline}")
        print(f"{item.url}")

    print(f"\n\nFetched {len(stock_news)} news items for MSFT")

    print("\n\n" + "=" * 60)
    print("Fetching news for INQQ (ETF) from StockAnalysis...")
    etf_news = scraper.fetch_news("INQQ", max_news=3, asset_type="etf")

    for item in etf_news:
        print(f"\n[{item.timestamp}] {item.source}")
        print(f"{item.headline}")
        print(f"{item.url}")

    print(f"\n\nFetched {len(etf_news)} news items for INQQ")
