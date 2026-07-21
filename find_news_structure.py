"""Find the actual HTML structure of news on StockAnalysis."""

import requests
from bs4 import BeautifulSoup

ticker = "NVDA"
url = f"https://stockanalysis.com/stocks/{ticker.lower()}/"

headers = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
}

print(f"Analyzing news structure on: {url}\n")

response = requests.get(url, headers=headers, timeout=10)
response.raise_for_status()

soup = BeautifulSoup(response.content, "html.parser")

# Find the H2 "News" heading
news_heading = soup.find("h2", string=lambda t: t and "news" in t.lower())

if news_heading:
    print(f"✅ Found news heading: {news_heading.get_text()}")
    print(f"   Tag: <{news_heading.name}>")
    print(f"   Classes: {news_heading.get('class', [])}")
    print(f"   ID: {news_heading.get('id', 'none')}")

    # Get the parent container
    parent = news_heading.parent
    print(f"\n📦 Parent container:")
    print(f"   Tag: <{parent.name}>")
    print(f"   Classes: {parent.get('class', [])}")
    print(f"   ID: {parent.get('id', 'none')}")

    # Look for news items after this heading
    print(f"\n🔍 Looking for news items after heading...\n")

    # Find all links with /news/ in href near this heading
    news_links = []

    # Check parent's siblings and children
    current = news_heading
    for _ in range(5):  # Go up 5 levels
        current = current.parent
        if current:
            links = current.find_all("a", href=lambda h: h and "/news/" in h)
            if links:
                news_links = links
                print(f"   Found {len(links)} links with /news/ in parent level")
                break

    if news_links:
        print(f"\n✅ Found {len(news_links)} news links!\n")
        print("=" * 80)
        print("Sample news items:")
        print("=" * 80 + "\n")

        for i, link in enumerate(news_links[:5], 1):
            headline = link.get_text(strip=True)
            href = link.get("href", "")
            classes = " ".join(link.get("class", []))

            print(f"[{i}] {headline}")
            print(f"    URL: {href}")
            print(f"    Classes: {classes if classes else '(none)'}")

            # Check for timestamp nearby
            parent_div = link.parent
            if parent_div:
                # Look for time element
                time_elem = parent_div.find("time") or parent_div.find_next("time")
                if time_elem:
                    print(f"    Time: {time_elem.get('datetime', time_elem.get_text())}")

                # Look for source info
                source_tags = parent_div.find_all(
                    ["span", "div"], class_=lambda c: c and ("source" in str(c).lower())
                )
                if source_tags:
                    print(f"    Source: {source_tags[0].get_text(strip=True)}")

            print()

        # Analyze structure
        print("=" * 80)
        print("HTML Structure Analysis:")
        print("=" * 80 + "\n")

        first_link = news_links[0]
        print("First news link HTML:")
        print(first_link.prettify()[:500])
        print("\nParent structure:")
        print(first_link.parent.name)
        if first_link.parent.parent:
            print(f"  → {first_link.parent.parent.name}")
            if first_link.parent.parent.parent:
                print(f"    → {first_link.parent.parent.parent.name}")

    else:
        print("❌ No news links found")
else:
    print("❌ News heading not found")

# Also check for direct news page
print("\n" + "=" * 80)
print("Checking if there's a dedicated news page...")
print("=" * 80 + "\n")

news_page_url = f"https://stockanalysis.com/stocks/{ticker.lower()}/news/"
try:
    response = requests.get(news_page_url, headers=headers, timeout=10)
    if response.status_code == 200:
        print(f"✅ Dedicated news page exists: {news_page_url}")
        soup2 = BeautifulSoup(response.content, "html.parser")
        news_links_page = soup2.find_all("a", href=lambda h: h and "/news/" in h)
        print(f"   Found {len(news_links_page)} news links on dedicated page")
    else:
        print(f"❌ No dedicated news page (status: {response.status_code})")
except Exception as e:
    print(f"❌ Error checking news page: {e}")
