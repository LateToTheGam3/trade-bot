import time
import schedule
<<<<<<< HEAD
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

=======
from datetime import datetime
from alpaca_client import get_account, get_positions, get_open_orders, place_order, cancel_all_orders
from data_feed import get_news_sentiment
from claude_brain import decide_trades
from risk_manager import check_daily_limits, validate_trade
from logger import log_trade, get_daily_ppl, print_daily_summary, log_recommendation

RUN_INTERVAL_MINUTES = 30
TRADE_AMOUNT_USD = 500
TICKERS_TO_WATCH = ["AAPL", "NVDA", "TSLA", "MSFT", "AMZN", "APLD", "BYDDY"]
TICKER_TO_NAME = {
    "AAPL": "Apple",
    "NVDA": "Nvidia",
    "TSLA": "Tesla",
    "MSFT": "Microsoft",
    "AMZN": "Amazon",
    "APLD": "Applied Digital",
    "BYDDY": "BYD"
}

def get_portfolio_summary(positions):
    if not positions:
        return "No open positions."
    lines = []
    for p in positions:
        lines.append(
            f"{p['symbol']}: {p['qty']} shares | "
            f"avg=${float(p['avg_entry_price']):.2f} | "
            f"current=${float(p['current_price']):.2f} | "
            f"P&L=${float(p['unrealized_pl']):.2f}"
        )
    return "\n".join(lines)
>>>>>>> bcc8d84f408100ee76f6a59d28995fc9e19dff30

def build_cash_dict(account):
    return {
        "free": float(account["cash"]),
        "total": float(account["portfolio_value"]),
        "ppl": float(account.get("unrealized_pl", 0))
    }

<<<<<<< HEAD

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
=======
def run_trading_cycle():
    print(f"\n{'='*50}")
    print(f"Trading cycle — {datetime.now().strftime('%H:%M:%S')}")
    print(f"{'='*50}")

    try:
        account = get_account()
        positions = get_positions()
>>>>>>> bcc8d84f408100ee76f6a59d28995fc9e19dff30
        cash = build_cash_dict(account)
    except Exception as e:
        print(f"Failed to get account data: {e}")
        return

<<<<<<< HEAD
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
=======
    print(f"Cash: ${cash['free']:,.2f} | Portfolio: ${cash['total']:,.2f}")

    daily_ppl = get_daily_ppl()
    limits = check_daily_limits(daily_ppl)
    print(f"Today's realised P&L: {daily_ppl:.2f}")

    if not limits["can_trade"]:
        print(f"Limit hit: {limits['reason']}")
        print_daily_summary()
        return

    print(f"\nFetching news signals...")
    signals = []
    for ticker in TICKERS_TO_WATCH:
        try:
            signal = get_news_sentiment(ticker)
            signal["ticker"] = ticker
            signals.append(signal)
            print(f"  {ticker}: {signal['signal']} | confidence={signal['confidence']:.2f}")
        except Exception as e:
            print(f"  {ticker}: failed — {e}")

    if not signals:
        print("No signals — skipping cycle")
        return

    print(f"\nAsking Claude for trade decisions...")
    portfolio_summary = get_portfolio_summary(positions)

    try:
        trades = decide_trades(portfolio_summary, cash, signals)
    except Exception as e:
        print(f"Claude brain failed: {e}")
        return

    if not trades:
        print("No trades recommended this cycle.")
        print_daily_summary()
        return

    print(f"{len(trades)} trade(s) suggested")
    print(f"\nExecuting trades...")

    for trade in trades:
        ticker = trade.get("ticker")
        direction = trade.get("direction", "BUY").lower()
        reason = trade.get("reason", "")
        side = "buy" if direction == "buy" else "sell"

        print(f"\n  {side.upper()} {ticker} — {reason}")

        signal = next((s for s in signals if s["ticker"] == ticker), None)

        if not signal or signal["confidence"] < 0.6:
            log_recommendation(
                ticker, side.upper(), reason,
                signal["confidence"] if signal else 0,
                executed=False,
                skip_reason="low confidence"
            )
            print(f"  Skipped — confidence too low")
>>>>>>> bcc8d84f408100ee76f6a59d28995fc9e19dff30
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
<<<<<<< HEAD
            log_recommendation(ticker, recommendation, reason, confidence,
                               executed=False, skip_reason="user decision")
            print(f"  Skipped — logged for tracking")
=======
            log_recommendation(
                ticker, side.upper(), reason,
                signal["confidence"],
                executed=False,
                skip_reason="user skipped"
            )
            print("  Skipped")
>>>>>>> bcc8d84f408100ee76f6a59d28995fc9e19dff30
            continue

        try:
            order = place_order(ticker, TRADE_AMOUNT_USD, side)
            if order.get("id"):
<<<<<<< HEAD
                log_recommendation(ticker, recommendation, reason, confidence, executed=True)
=======
                log_recommendation(
                    ticker, side.upper(), reason,
                    signal["confidence"],
                    executed=True
                )
>>>>>>> bcc8d84f408100ee76f6a59d28995fc9e19dff30
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
<<<<<<< HEAD
            print(f"  Order error: {e}")
=======
            print(f"  Error: {e}")
>>>>>>> bcc8d84f408100ee76f6a59d28995fc9e19dff30

    print_daily_summary()

def run_scheduler():
<<<<<<< HEAD
    print("\n  AI Investment Research Bot")
    print(f"  Tickers: {', '.join(TICKERS_TO_WATCH)}")
    print(f"  Min confidence: {MIN_CONFIDENCE:.0%}")
    print(f"  Trade size: ${TRADE_AMOUNT_USD}")
    print(f"  Runs every {RUN_INTERVAL_MINUTES} minutes")
    print("\n  Press Ctrl+C to stop\n")
=======
    print("Alpaca Day Trading Bot started!")
    print(f"  Watching: {', '.join(TICKERS_TO_WATCH)}")
    print(f"  Trade size: ${TRADE_AMOUNT_USD} per trade")
    print(f"  Daily target: 30")
    print(f"  Max daily loss: 50")
    print(f"  Runs every {RUN_INTERVAL_MINUTES} minutes")
    print("\nPress Ctrl+C to stop\n")
>>>>>>> bcc8d84f408100ee76f6a59d28995fc9e19dff30

    run_trading_cycle()
    schedule.every(RUN_INTERVAL_MINUTES).minutes.do(run_trading_cycle)

    while True:
        schedule.run_pending()
        time.sleep(60)

if __name__ == "__main__":
    run_scheduler()
