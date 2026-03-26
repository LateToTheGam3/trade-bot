import requests
import os
import json
import re
from dotenv import load_dotenv

load_dotenv()

OPENROUTER_KEY = os.getenv("OPENROUTER_KEY")
MODEL = "anthropic/claude-sonnet-4-5-20250929"

def analyse_ticker(ticker: str, technicals: dict, news_headlines: str) -> dict:
    prompt = f"""You are a professional intraday trader analysing {ticker} for a day trade.

TECHNICAL DATA:
- Price: ${technicals['price']}
- Price change today: {technicals['price_change']}%
- RSI (14): {technicals['rsi']} 
- MACD histogram: {technicals['macd_hist']} ({'bullish' if technicals['macd_hist'] > 0 else 'bearish'})
- Bollinger Band position: {technicals['bb_pct']} (0=lower band, 1=upper band)
- VWAP: ${technicals['vwap']} (price is {technicals['vwap_signal']} VWAP)
- Volume surge: {technicals['vol_surge']}x average
- Technical score: {technicals['score']}/100 ({technicals['direction']})
- Technical reasons: {', '.join(technicals['reasons'])}

RECENT NEWS:
{news_headlines}

TASK:
Based on ALL of the above, provide a precise intraday trade recommendation.
Return ONLY a JSON object, no markdown, no explanation:
{{
    "ticker": "{ticker}",
    "action": "LONG" or "SHORT" or "SKIP",
    "confidence": 0.0 to 1.0,
    "entry_price": current price or slightly better entry,
    "take_profit": target exit price,
    "stop_loss": maximum loss price,
    "expected_return_pct": expected % gain,
    "reasoning": "2 sentence max explanation",
    "hold_time": "estimated hold time e.g. 15min, 1hr, 2hr"
}}

Rules:
- SKIP if signals conflict or confidence < 0.6
- Take profit should be 0.5-1.5% from entry
- Stop loss should be 0.3-0.5% from entry
- Risk/reward ratio must be at least 1.5:1"""

    response = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {OPENROUTER_KEY}",
            "Content-Type": "application/json"
        },
        json={
            "model": MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 400
        }
    )

    data = response.json()
    raw = data["choices"][0]["message"]["content"]
    clean = re.sub(r"```json|```", "", raw).strip()
    return json.loads(clean)


def rank_opportunities(opportunities: list, news_map: dict) -> list:
    ranked = []

    for opp in opportunities:
        ticker = opp["ticker"]
        headlines = news_map.get(ticker, "No recent news available.")

        try:
            analysis = analyse_ticker(ticker, opp, headlines)
            if analysis["action"] == "SKIP":
                print(f"  ⏭️  {ticker}: SKIP — {analysis['reasoning'][:60]}")
                continue

            combined_score = (opp["score"] * 0.4) + (analysis["confidence"] * 100 * 0.6)

            ranked.append({
                **opp,
                **analysis,
                "combined_score": round(combined_score, 1)
            })

            arrow = "📈" if analysis["action"] == "LONG" else "📉"
            print(f"  {arrow} {ticker}: {analysis['action']} | "
                  f"confidence={analysis['confidence']} | "
                  f"TP=${analysis['take_profit']} | "
                  f"SL=${analysis['stop_loss']} | "
                  f"hold={analysis['hold_time']}")

        except Exception as e:
            print(f"  ⚠️  {ticker}: analysis failed — {e}")

    ranked.sort(key=lambda x: x["combined_score"], reverse=True)
    return ranked


# --- TEST ---
if __name__ == "__main__":
    from screener import scan_market
    from data_feed import fetch_news

    print("Running screener...")
    opportunities = scan_market(min_score=30)
    print(f"Found {len(opportunities)} opportunities\n")

    print("Adding news analysis...")
    news_map = {}
    for opp in opportunities:
        ticker = opp["ticker"]
        try:
            news_map[ticker] = fetch_news(ticker, max_articles=3)
        except:
            news_map[ticker] = "No news available."

    print("\nRanking with Claude...\n")
    ranked = rank_opportunities(opportunities, news_map)

    print(f"\n=== TOP TRADES ===")
    for t in ranked[:5]:
        print(f"\n{t['ticker']}: {t['action']}")
        print(f"  Entry: ${t['entry_price']} | TP: ${t['take_profit']} | SL: ${t['stop_loss']}")
        print(f"  Expected return: {t['expected_return_pct']}% | Hold: {t['hold_time']}")
        print(f"  Reasoning: {t['reasoning']}")
        print(f"  Combined score: {t['combined_score']}")