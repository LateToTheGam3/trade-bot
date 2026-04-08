import time
import schedule
from datetime import datetime, date
from alpaca_client import get_account, get_positions, place_order
from data_feed import fetch_news, TICKER_TO_NAME
from claude_brain import generate_memo
from risk_manager import check_daily_limits
from logger import log_trade, get_daily_ppl, print_daily_summary, log_recommendation

# ── Settings ──────────────────────────────────────────────────────
RUN_INTERVAL_MINUTES = 30
TRADE_AMOUNT_USD = 500
TICKERS_TO_WATCH = ["AAPL", "NVDA", "TSLA", "MSFT", "AMZN", "APLD", "BYDDY"]
MIN_CONFIDENCE = 0.6


def build_cash_dict(account: dict) -> dict:
    return {
        "free": float(account["cash"]),
        "total": float(account["portfolio_value"]),
        "ppl": float(account.get("unrealized_pl", 0))
    }


def display_memo(result: dict):
    print("\n" + "="*65)
    print(result["memo"])
    print("="*65)
    print(f"\n  Ticker      : {result['ticker']}")
    print(f"  Signal      : {result['recommendation']}")
    print(f"  Confidence  : {result['confidence']:.0%}")
    a = result.get("assessment", {})
    print(f"  Sentiment   : {a.get('overall_sentiment', 'N/A')}")
    print(f"  Data quality: {a.get('data_quality', 'N/A')}")
    print(f"  Time horizon: {a.get('time_horizon_signal', 'N/A')}")


def run_trading_cycle():
    today = date.today().isoformat()

    print(f"\n{'='*65}")
    print(f"  Investment Research Cycle — {datetime.now().strftime('%d %b %Y %H:%M')}")
    print(f"{'='*65}")

    try:
        account = get_account()
        cash = build_cash_dict(account)
    except Exception as e:
        print(f"Failed to get account data: {e}")
        return

    print(f"\n  Cash: ${cash['free']:,.2f} | Portfolio: ${cash['total']:,.2f}")

    daily_ppl = get_daily_ppl()
    limits = check_daily_limits(daily_ppl)
    print(f"  Today's P&L: £{daily_ppl:.2f}")

    if not limits["can_trade"]:
        print(f"  Limit hit: {limits['reason']}")
        print_daily_summary()
        return

    print(f"\n  Generating investment memos for {len(TICKERS_TO_WATCH)} tickers...")
    print(f"  (Two-pass AI: news assessment then investment memo)\n")

    results = []
    for ticker in TICKERS_TO_WATCH:
        company = TICKER_TO_NAME.get(ticker, ticker)
        print(f"\n── {ticker} ({company}) ──")

        news = fetch_news(ticker)
        if news["error"]:
            print(f"  News fetch failed: {news['error']}")
            log_recommendation(ticker, "N/A", "News fetch failed", 0.0,
                               executed=False, skip_reason="news fetch error")
            continue

        articles_found = len(news["articles"])
        print(f"  Articles found: {articles_found}")

        if articles_found == 0:
            print(f"  No news — skipping")
            log_recommendation(ticker, "N/A", "No news available", 0.0,
                               executed=False, skip_reason="no news")
            continue

        result = generate_memo(
            ticker=ticker,
            company=company,
            news_raw=news["raw_text"],
            today=today
        )
        results.append(result)

        if result["error"]:
            print(f"  Memo error: {result['error']}")

    if not results:
        print("\n  No memos generated this cycle.")
        print_daily_summary()
        return

    print(f"\n\n{'='*65}")
    print(f"  RESEARCH COMPLETE — {len(results)} memos generated")
    print(f"{'='*65}")

    actionable = [r for r in results if r["recommendation"] in ("BUY", "SELL")
                  and r["confidence"] >= MIN_CONFIDENCE]
    passes = [r for r in results if r not in actionable]

    if passes:
        print(f"\n  PASS ({len(passes)} tickers):")
        for r in passes:
            reason = r.get("error") or f"confidence {r['confidence']:.0%}"
            print(f"    {r['ticker']}: {r['recommendation']} — {reason}")

    if not actionable:
        print(f"\n  No actionable signals this cycle.")
        print_daily_summary()
        return

    print(f"\n  ACTIONABLE SIGNALS ({len(actionable)} tickers):")

    for result in actionable:
        display_memo(result)

        recommendation = result["recommendation"]
        side = "buy" if recommendation == "BUY" else "sell"
        ticker = result["ticker"]
        confidence = result["confidence"]
        reason = result.get("assessment", {}).get("primary_catalyst", "See memo")

        print(f"\n  AI recommends: {recommendation} {ticker}")
        print(f"  Trade size: ${TRADE_AMOUNT_USD} | Side: {side.upper()}")
        print(f"\n  Read the memo above carefully before deciding.")
        confirm = input(f"  Execute {side.upper()} {ticker}? (y/n): ").strip().lower()

        if confirm != "y":
            log_recommendation(ticker, recommendation, reason, confidence,
                               executed=False, skip_reason="user decision")
            print(f"  Skipped — logged for tracking")
            continue

        try:
            order = place_order(ticker, TRADE_AMOUNT_USD, side)
            if order.get("id"):
                log_recommendation(ticker, recommendation, reason, confidence, executed=True)
                print(f"  Order placed: {order['id']} | {order.get('status')}")
                log_trade({
                    "ticker": ticker,
                    "direction": recommendation,
                    "quantity": order.get("qty"),
                    "current_price": 0,
                    "estimated_value": TRADE_AMOUNT_USD,
                    "reason": reason
                }, order)
            else:
                print(f"  Order failed: {order}")
        except Exception as e:
            print(f"  Order error: {e}")

    print_daily_summary()


def run_scheduler():
    print("\n  AI Investment Research Bot")
    print(f"  Tickers: {', '.join(TICKERS_TO_WATCH)}")
    print(f"  Min confidence: {MIN_CONFIDENCE:.0%}")
    print(f"  Trade size: ${TRADE_AMOUNT_USD}")
    print(f"  Runs every {RUN_INTERVAL_MINUTES} minutes")
    print("\n  Press Ctrl+C to stop\n")

    run_trading_cycle()
    schedule.every(RUN_INTERVAL_MINUTES).minutes.do(run_trading_cycle)

    while True:
        schedule.run_pending()
        time.sleep(60)


if __name__ == "__main__":
    run_scheduler()
