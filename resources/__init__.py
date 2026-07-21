"""Resources module for stock news monitoring and sentiment analysis.

Data flow:
  - News fetching: Ticker → StockAnalysis Scraper → News items
  - Sentiment: News text → SentimentClassifier (FinBERT) → Sentiment label
  - Bot: Commands → StockNewsBot → Portfolio updates / News delivery
"""

from .sentiment_classifier import SentimentClassifier, SentimentResult
from .stockanalysis_scraper import NewsItem, StockAnalysisScraper
from .telegram_bot import StockNewsBot

__all__ = [
    "StockAnalysisScraper",
    "NewsItem",
    "SentimentClassifier",
    "SentimentResult",
    "StockNewsBot",
]
