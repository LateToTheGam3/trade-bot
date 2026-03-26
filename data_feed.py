import requests
import os
import json
import re
from dotenv import load_dotenv

load_dotenv()

OPENROUTER_KEY = os.getenv("OPENROUTER_KEY")
NEWS_API_KEY = os.getenv("NEWS_API_KEY")

WATCH_LIST = {
    "US_STOCKS": ["TSLA_US_EQ", "SQ_US_EQ", "AAPL_US_EQ", "NVDA_US_EQ"],
    "UK_ETFS": ["EEDGl_EQ", "EDG2l_EQ", "SGLNl_EQ", "IGUSl_EQ"],
}

TICKER_TO_NAME = {
    "TSLA_US_EQ": "Tesla",
    "SQ_US_EQ": "Block Square fintech",
    "AAPL_US_EQ": "Apple",
    "NVDA_US_EQ": "Nvidia",
    "EEDGl_EQ": "iShares MSCI Europe",
    "EDG2l_EQ": "iShares Edge MSCI",
    "SGLNl_EQ": "iShares Gold",
    "IGUSl_EQ": "iShares US Equity",
}

def fetch_news(company_name: str, max_articles: int = 5) -> str:
    """Fetch latest news headlines for a company"""
    url = "https://newsapi.org/v2/everything"
    params = {
        "q": company_name,
        "sortBy": "publishedAt",
        "pageSize": max_articles,
        "language": "en",
        "apiKey": NEWS_API_KEY
    }
    r = requests.get(url, params=params)
    data = r.json()

    if data.get("status") != "ok":
        return "No news available."

    articles = data.get("articles", [])
    if not articles:
        return "No recent news found."

    headlines = []
    for a in articles:
        title = a.get("title", "")
        desc = a.get("description", "")
        published = a.get("publishedAt", "")[:10]
        headlines.append(f"[{published}] {title} — {desc}")

    return "\n".join(headlines)

def get_news_sentiment(ticker: str) -> dict:
    """Fetch news and ask Claude to analyse sentiment"""
    company_name = TICKER_TO_NAME.get(ticker, ticker)
    news = fetch_news(company_name)

    prompt = f"""You are a professional trading signal analyst.

Here are the latest news headlines for {company_name} ({ticker}):

{news}

Based on this news, provide a trading signal.
Return ONLY a JSON object in this exact format, nothing else, no markdown:
{{
    "ticker": "{ticker}",
    "sentiment": "BULLISH" or "BEARISH" or "NEUTRAL",
    "confidence": 0.0 to 1.0,
    "reason": "one sentence explanation",
    "signal": "BUY" or "SELL" or "HOLD",
    "suggested_position_size_pct": 0.01 to 0.05
}}"""

    response = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {OPENROUTER_KEY}",
            "Content-Type": "application/json"
        },
        json={
            "model": "anthropic/claude-sonnet-4-5",
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 300
        }
    )

    data = response.json()
    raw = data["choices"][0]["message"]["content"]
    clean = re.sub(r"```json|```", "", raw).strip()
    return json.loads(clean)

def get_portfolio_summary(portfolio: list) -> str:
    """Format portfolio for Claude to analyse"""
    lines = []
    for p in portfolio:
        ppl = p.get("ppl", 0)
        lines.append(
            f"{p['ticker']}: qty={p['quantity']:.2f}, "
            f"avg=£{p['averagePrice']:.2f}, "
            f"current=£{p['currentPrice']:.2f}, "
            f"ppl=£{ppl:.2f}"
        )
    return "\n".join(lines)

# --- TEST ---
if __name__ == "__main__":
    print("Fetching live news + sentiment for TSLA...")
    result = get_news_sentiment("TSLA_US_EQ")
    print(json.dumps(result, indent=2))

    print("\nFetching live news + sentiment for NVDA...")
    result2 = get_news_sentiment("NVDA_US_EQ")
    print(json.dumps(result2, indent=2))