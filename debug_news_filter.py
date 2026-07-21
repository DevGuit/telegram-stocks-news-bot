"""Diagnostic script to understand why NVIDIA news isn't showing up."""

import logging
from pathlib import Path
from datetime import datetime

from helpers import (
    fetch_and_classify_news,
    get_user_timezone,
    load_paths,
    setup_logging,
)
from resources import SentimentClassifier, StockAnalysisScraper

setup_logging("INFO")
logger = logging.getLogger(__name__)

print("\n" + "=" * 80)
print("NVIDIA NEWS FILTERING DIAGNOSTIC")
print("=" * 80 + "\n")

# Fetch NVIDIA news
print("📰 Fetching NVIDIA news from StockAnalysis...")
scraper = StockAnalysisScraper()
news_items = scraper.fetch_news("NVDA", max_news=10, asset_type="stocks")

print(f"✅ Found {len(news_items)} total news items\n")

# Initialize classifier
paths = load_paths()
model_cache = Path(paths["model_cache"])
classifier = SentimentClassifier(model_cache_dir=model_cache)

# Get timezone and today's date
user_tz = get_user_timezone()
today = datetime.now(user_tz).date()

print(f"⏰ User timezone: {user_tz}")
print(f"📅 Today's date: {today}\n")

print("=" * 80)
print("ALL NEWS ITEMS WITH SENTIMENT ANALYSIS")
print("=" * 80 + "\n")

for i, news in enumerate(news_items, 1):
    news_date = news.timestamp.astimezone(user_tz).date()
    is_today = news_date == today

    sentiment = classifier.classify(news.headline)

    # Check if it passes the filter
    passes_filter = (
        is_today and sentiment.label != "neutral" and sentiment.score >= 0.5
    )

    status = "✅ SHOWN" if passes_filter else "❌ FILTERED OUT"

    print(f"[{i}] {status}")
    print(f"  📰 {news.headline}")
    print(f"  📅 Date: {news_date} {'(TODAY)' if is_today else '(OLD)'}")
    print(f"  🕒 Time: {news.timestamp.astimezone(user_tz).strftime('%I:%M %p')}")
    print(f"  📊 Source: {news.source}")
    print(
        f"  💭 Sentiment: {sentiment.label.upper()} (confidence: {sentiment.score:.1%})"
    )
    print(f"  📈 Scores: pos={sentiment.label_scores['positive']:.1%}, "
          f"neg={sentiment.label_scores['negative']:.1%}, "
          f"neu={sentiment.label_scores['neutral']:.1%}")

    if not passes_filter:
        reasons = []
        if not is_today:
            reasons.append(f"date is {news_date}, not today")
        if sentiment.label == "neutral":
            reasons.append("sentiment is neutral")
        if sentiment.score < 0.5:
            reasons.append(f"confidence {sentiment.score:.1%} < 50%")
        print(f"  ⚠️  Filtered because: {', '.join(reasons)}")

    print()

print("=" * 80)
print("SUMMARY: What the bot would actually send")
print("=" * 80 + "\n")

# Use the actual filtering function
filtered_news = fetch_and_classify_news({"stocks": ["NVDA"]}, max_news_per_ticker=10)

if len(filtered_news) > 0:
    print(f"✅ Bot would send {len(filtered_news)} news items:\n")
    for i, (news, sentiment) in enumerate(filtered_news, 1):
        print(
            f"  [{i}] {sentiment.label.upper()} ({sentiment.score:.1%}): {news.headline}"
        )
else:
    print("❌ Bot would send ZERO news items!")
    print("\n🔍 DIAGNOSIS:")
    print("  The news is being filtered out because:")
    print("  1. FinBERT classifies it as 'neutral' sentiment, OR")
    print("  2. The positive/negative confidence is below 50%, OR")
    print("  3. The news is not from today")
    print(
        "\n💡 SOLUTION: Consider lowering the relevance_threshold or removing the neutral filter"
    )

print("\n" + "=" * 80 + "\n")
