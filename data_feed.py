"""
data_feed.py
------------
Single responsibility: fetch raw news headlines for a given company.
No AI calls here. Clean input for the memo writer subagent in claude_brain.py.

Design principle (ref: exam guide Domain 2 - Tool Design):
  Each tool does one thing clearly. Ambiguous multi-purpose tools degrade reliability.
"""

import requests
import os
from dotenv import load_dotenv

load_dotenv()

NEWS_API_KEY = os.getenv("NEWS_API_KEY")

# Master ticker map — covers Alpaca-supported US tickers
TICKER_TO_NAME = {
    "AAPL":  "Apple Inc",
    "NVDA":  "Nvidia",
    "TSLA":  "Tesla",
    "MSFT":  "Microsoft",
    "AMZN":  "Amazon",
    "APLD":  "Applied Digital Corporation",
    "BYDDY": "BYD Company",
}


def fetch_news(ticker: str, max_articles: int = 7) -> dict:
    """
    Fetch latest news headlines for a ticker.

    Returns a dict with:
      - ticker: str
      - company: str
      - articles: list of {date, title, description, source}
      - raw_text: formatted string for passing to Claude
      - error: str or None

    Use raw_text when passing to Claude.
    Use articles when you need structured access to individual items.

    Do NOT use this to generate signals — pass output to claude_brain.generate_memo().
    """
    company = TICKER_TO_NAME.get(ticker, ticker)

    url = "https://newsapi.org/v2/everything"
    params = {
        "q": f'"{company}" OR "{ticker}"',
        "sortBy": "publishedAt",
        "pageSize": max_articles,
        "language": "en",
        "apiKey": NEWS_API_KEY
    }

    try:
        r = requests.get(url, params=params, timeout=10)
        data = r.json()
    except Exception as e:
        return {
            "ticker": ticker,
            "company": company,
            "articles": [],
            "raw_text": "News fetch failed — network error.",
            "error": str(e)
        }

    if data.get("status") != "ok":
        return {
            "ticker": ticker,
            "company": company,
            "articles": [],
            "raw_text": "No news available.",
            "error": data.get("message", "Unknown error")
        }

    articles = data.get("articles", [])
    if not articles:
        return {
            "ticker": ticker,
            "company": company,
            "articles": [],
            "raw_text": "No recent news found for this ticker.",
            "error": None
        }

    structured = []
    lines = []
    for a in articles:
        title = a.get("title", "").strip()
        desc = a.get("description", "").strip()
        date = a.get("publishedAt", "")[:10]
        source = a.get("source", {}).get("name", "Unknown")

        structured.append({
            "date": date,
            "title": title,
            "description": desc,
            "source": source
        })
        lines.append(f"[{date}] [{source}] {title}\n  {desc}")

    return {
        "ticker": ticker,
        "company": company,
        "articles": structured,
        "raw_text": "\n\n".join(lines),
        "error": None
    }


# --- TEST ---
if __name__ == "__main__":
    for ticker in ["AAPL", "APLD", "NVDA"]:
        print(f"\n{'='*50}")
        print(f"Fetching news for {ticker}...")
        result = fetch_news(ticker)
        print(f"Company: {result['company']}")
        print(f"Articles found: {len(result['articles'])}")
        print(f"Error: {result['error']}")
        print(f"\nRaw text preview:\n{result['raw_text'][:500]}...")
