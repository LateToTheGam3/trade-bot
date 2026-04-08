"""
research.py
-----------
On-demand investment memo for any ticker.
Usage: python3 research.py AAPL
       python3 research.py NVDA TSLA MSFT
"""

import sys
from datetime import date
from data_feed import fetch_news, TICKER_TO_NAME
from claude_brain import generate_memo


def research(ticker: str):
    today = date.today().isoformat()
    ticker = ticker.upper()
    company = TICKER_TO_NAME.get(ticker, ticker)

    print(f"\nResearching {ticker} ({company})...")

    news = fetch_news(ticker)
    if news["error"]:
        print(f"News fetch failed: {news['error']}")
        return

    print(f"Articles found: {len(news['articles'])}")

    result = generate_memo(
        ticker=ticker,
        company=company,
        news_raw=news["raw_text"],
        today=today
    )

    print("\n" + "="*65)
    print(result["memo"])
    print("="*65)
    print(f"\nRecommendation : {result['recommendation']}")
    print(f"Confidence     : {result['confidence']:.0%}")
    if result["error"]:
        print(f"Error          : {result['error']}")


if __name__ == "__main__":
    tickers = sys.argv[1:] if len(sys.argv) > 1 else ["NVDA"]
    for t in tickers:
        research(t)
