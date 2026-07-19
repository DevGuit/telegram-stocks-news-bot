"""Resources module for stock news monitoring and sentiment analysis.

Data flow:
  - News fetching: Ticker → FinvizScraper → News items
  - Sentiment: News text → SentimentClassifier (FinBERT) → Sentiment label
  - Bot: Commands → StockNewsBot → Portfolio updates / News delivery
"""

from .finviz_scraper import FinvizScraper, NewsItem
from .sentiment_classifier import SentimentClassifier, SentimentResult
from .telegram_bot import StockNewsBot

__all__ = [
    "FinvizScraper",
    "NewsItem",
    "SentimentClassifier",
    "SentimentResult",
    "StockNewsBot",
]
