"""Resources module for stock news monitoring and sentiment analysis.

Data flow:
  - News fetching: Ticker → Multiple Scrapers (Finviz/StockAnalysis) → News items
  - Sentiment: News text → SentimentClassifier (FinBERT) → Sentiment label
  - Bot: Commands → StockNewsBot → Portfolio updates / News delivery
"""

from .finviz_scraper import FinvizScraper, NewsItem
from .sentiment_classifier import SentimentClassifier, SentimentResult
from .stockanalysis_scraper import StockAnalysisScraper
from .telegram_bot import StockNewsBot

__all__ = [
    "FinvizScraper",
    "StockAnalysisScraper",
    "NewsItem",
    "SentimentClassifier",
    "SentimentResult",
    "StockNewsBot",
]
