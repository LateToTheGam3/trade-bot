import time
import schedule
from datetime import datetime

from alpaca_client import get_account, get_positions, get_open_orders, place_order, cancel_all_orders
from data_feed import get_news_sentiment
from claude_brain import decide_trades
from risk_manager import check_daily_limits, validate_trade
from logger import log_trade, get_daily_ppl, print_daily_summary

# ── Settings ─────────────────────────────────────────────────────
RUN_INTERVAL_MINUTES = 30
TRADE_AMOUNT_USD     = 500      # per trade
TICKERS_TO_WATCH     = ["AAPL", "NVDA", "TSLA", "MSFT", "AMZN"]

TICKER_TO_NAME = {
    "AAPL":  "Apple",
    "NVDA":  "Nvidia",
    "TSLA":  "Tesla",
    "MSFT":  "Microsoft",
    "AMZN":  "Amazon"
}

def get_portfolio_summary(positions: list) -> str:
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

def build_cash_dict(account: dict) -> dict:
    return {
        "free": float(account["cash"]),
        "total": float(account["portfolio_value"]),
        "ppl": float(account.get("unrealized_pl", 0))
    }

def run_trading_cycle():
    print(f"\n{'='*50}")
    print(f"🤖 Trading cycle — {datetime.now().strftime('%H:%M:%S')}")
    print(f"{'='*50}")

    # ── 1. Get account state ──────────────────────────────────────
    try:
        account   = get_account()
        positions = get_positions()
        cash      = build_cash_dict(account)
    except Exception as e:
        print(f"❌ Failed to get account data: {e}")
        return

    print(f"💰 Cash: ${cash['free']:,.2f} | Portfolio: ${cash['total']:,.2f}")

    # ── 2. Check daily limits ─────────────────────────────────────
    daily_ppl = get_daily_ppl()
    limits    = check_daily_limits(daily_ppl)
    print(f"📈 Today's realised P&L: £{daily_ppl:.2f}")

    if not limits["can_trade"]:
        print(f"🛑 {limits['reason']}")
        print_daily_summary()
        return

    # ── 3. Get news signals ───────────────────────────────────────
    print(f"\n📰 Fetching news signals...")
    signals = []
    for ticker in TICKERS_TO_WATCH:
        try:
            signal = get_news_sentiment(ticker)
            # Normalise ticker name for Alpaca
            signal["ticker"] = ticker
            signals.append(signal)
            emoji = "🟢" if signal["signal"] == "BUY" else "🔴" if signal["signal"] == "SELL" else "⚪"
            print(f"  {emoji} {ticker}: {signal['signal']} | {signal['sentiment']} | confidence={signal['confidence']:.2f}")
        except Exception as e:
            print(f"  ⚠️  {ticker}: failed — {e}")

    if not signals:
        print("❌ No signals — skipping cycle")
        return

    # ── 4. Ask Claude brain for decisions ─────────────────────────
    print(f"\n🧠 Asking Claude for trade decisions...")
    portfolio_summary = get_portfolio_summary(positions)

    try:
        trades = decide_trades(portfolio_summary, cash, signals)
    except Exception as e:
        print(f"❌ Claude brain failed: {e}")
        return

    if not trades:
        print("  No trades recommended this cycle.")
        print_daily_summary()
        return

    print(f"  {len(trades)} trade(s) suggested")

    # ── 5. Validate and execute ───────────────────────────────────
    print(f"\n⚡ Executing trades...")
    for trade in trades:
        ticker    = trade.get("ticker")
        direction = trade.get("direction", "BUY").lower()
        reason    = trade.get("reason", "")

        # Map direction to Alpaca side
        side = "buy" if direction == "buy" else "sell"

        print(f"\n  {side.upper()} {ticker} — {reason}")

        # Validate signal confidence
        signal = next((s for s in signals if s["ticker"] == ticker), None)
        if not signal or signal["confidence"] < 0.6:
            print(f"  ❌ Skipped — confidence too low")
            continue

        confirm = input(f"  Execute? (y/n): ").strip().lower()
        if confirm != "y":
            print("  ⏭️  Skipped")
            continue

        try:
            order = place_order(ticker, TRADE_AMOUNT_USD, side)
            if order.get("id"):
                print(f"  ✅ Order placed: {order['id']} | {order.get('status')}")
                log_trade({
                    "ticker": ticker,
                    "direction": side.upper(),
                    "quantity": order.get("qty"),
                    "current_price": 0,
                    "estimated_value": TRADE_AMOUNT_USD,
                    "reason": reason
                }, order)
            else:
                print(f"  ❌ Order failed: {order}")
        except Exception as e:
            print(f"  ❌ Error: {e}")

    print_daily_summary()


def run_scheduler():
    print("🚀 Alpaca Day Trading Bot started!")
    print(f"   Watching: {', '.join(TICKERS_TO_WATCH)}")
    print(f"   Trade size: ${TRADE_AMOUNT_USD} per trade")
    print(f"   Daily target: £30")
    print(f"   Max daily loss: £50")
    print(f"   Runs every {RUN_INTERVAL_MINUTES} minutes")
    print("\nPress Ctrl+C to stop\n")

    run_trading_cycle()

    schedule.every(RUN_INTERVAL_MINUTES).minutes.do(run_trading_cycle)

    while True:
        schedule.run_pending()
        time.sleep(60)


if __name__ == "__main__":
    run_scheduler()