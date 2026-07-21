"""Debug script to see what's actually on the StockAnalysis page."""

import requests
from bs4 import BeautifulSoup

ticker = "NVDA"
url = f"https://stockanalysis.com/stocks/{ticker.lower()}/"

headers = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
}

print(f"Fetching: {url}\n")

try:
    response = requests.get(url, headers=headers, timeout=10)
    response.raise_for_status()

    print(f"✅ Status: {response.status_code}")
    print(f"✅ Content length: {len(response.content)} bytes\n")

    soup = BeautifulSoup(response.content, "html.parser")

    # Check for news section
    print("=" * 80)
    print("Searching for news sections...")
    print("=" * 80 + "\n")

    news_div = soup.find("div", {"id": "news"})
    print(f"1. div#news: {'FOUND' if news_div else 'NOT FOUND'}")

    news_section = soup.find("section", class_="news")
    print(f"2. section.news: {'FOUND' if news_section else 'NOT FOUND'}")

    news_links = soup.find_all("a", class_="news-link")
    print(f"3. a.news-link: Found {len(news_links)} links")

    # Try to find ANY links that might be news
    all_links = soup.find_all("a", href=True)
    print(f"4. Total <a> tags with href: {len(all_links)}")

    # Look for patterns in URLs
    news_patterns = ["/news/", "/quote/", "article"]
    for pattern in news_patterns:
        matching = [link for link in all_links if pattern in link.get("href", "")]
        print(f"   - Links containing '{pattern}': {len(matching)}")

    # Search for common news-related text
    print("\n" + "=" * 80)
    print("Searching page text for 'news' keyword...")
    print("=" * 80 + "\n")

    page_text = soup.get_text().lower()
    if "news" in page_text:
        print("✅ Found 'news' in page text")
        # Find headings with 'news'
        for tag in ["h1", "h2", "h3", "h4"]:
            headings = soup.find_all(tag)
            for h in headings:
                if "news" in h.get_text().lower():
                    print(f"  - {tag.upper()}: {h.get_text(strip=True)}")
    else:
        print("❌ 'news' not found in page text")

    # Check if page structure changed
    print("\n" + "=" * 80)
    print("Page structure analysis...")
    print("=" * 80 + "\n")

    # Look for main content areas
    main_divs = soup.find_all("div", class_=True, limit=20)
    print("Top-level divs with classes:")
    for div in main_divs[:10]:
        classes = " ".join(div.get("class", []))
        print(f"  - div.{classes[:80]}")

    # Check if it's a paywall or different page
    if "subscribe" in page_text or "premium" in page_text:
        print("\n⚠️  WARNING: Page may have paywall/premium content")

    # Sample some links to see what they look like
    print("\n" + "=" * 80)
    print("Sample of links on the page:")
    print("=" * 80 + "\n")

    sample_links = all_links[:20]
    for i, link in enumerate(sample_links, 1):
        href = link.get("href", "")[:80]
        text = link.get_text(strip=True)[:60]
        if text:  # Only show links with text
            print(f"{i}. {text}")
            print(f"   → {href}\n")

except Exception as e:
    print(f"❌ Error: {e}")
    import traceback

    traceback.print_exc()
