#!/usr/bin/env python3
"""Verify that timestamp parsing is working correctly in production."""

import sys
from datetime import datetime, timedelta
from pathlib import Path

# Add parent directory to path to import from resources
sys.path.insert(0, str(Path(__file__).parent.parent))

from resources.stockanalysis_scraper import StockAnalysisScraper


def main():
    """Test timestamp parsing with real data from StockAnalysis."""
    print("=" * 80)
    print("TIMESTAMP PARSING VERIFICATION")
    print("=" * 80 + "\n")

    scraper = StockAnalysisScraper()
    test_tickers = ["NVDA", "AAPL", "MSFT"]

    all_passed = True
    current_time = datetime.now()

    for ticker in test_tickers:
        print(f"\n📊 Testing {ticker}:")
        print("-" * 80)

        try:
            news_items = scraper.fetch_news(ticker, max_news=5, asset_type="stocks")

            if not news_items:
                print(f"  ⚠️  No news found for {ticker}")
                continue

            # Check 1: Timestamps are not all identical
            unique_times = len(set(item.timestamp for item in news_items))
            if unique_times == 1 and len(news_items) > 1:
                print("  ❌ FAIL: All timestamps identical")
                all_passed = False
            else:
                print(f"  ✅ {unique_times} unique timestamps out of {len(news_items)}")

            # Check 2: No future timestamps
            future = [item for item in news_items if item.timestamp > current_time]
            if future:
                print(f"  ❌ FAIL: {len(future)} future timestamps")
                all_passed = False
            else:
                print("  ✅ No future timestamps")

            # Check 3: All within reasonable range (7 days)
            week_ago = current_time - timedelta(days=7)
            old = [item for item in news_items if item.timestamp < week_ago]
            if old:
                print(f"  ℹ️  {len(old)} items older than 7 days")
            else:
                print("  ✅ All within 7 days")

            # Show sample
            if news_items:
                item = news_items[0]
                time_diff = current_time - item.timestamp
                hours = time_diff.total_seconds() / 3600
                print(f"\n  Sample: {item.headline[:60]}...")
                print(f"  Time: {item.timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
                print(f"  Age: {hours:.1f} hours ago")
                print(f"  Source: {item.source}")

        except Exception as e:
            print(f"  ❌ ERROR: {e}")
            all_passed = False

    print("\n" + "=" * 80)
    if all_passed:
        print("✅ ALL CHECKS PASSED - Timestamp parsing is working correctly!")
    else:
        print("❌ SOME CHECKS FAILED - Review errors above")
    print("=" * 80)

    return 0 if all_passed else 1


if __name__ == "__main__":
    exit(main())
