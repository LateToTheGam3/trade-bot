import json
import os
from datetime import datetime, date

LOG_FILE = "trades_log.json"
RECOMMENDATIONS_FILE = "recommendations_log.json"
STATE_FILE = "daily_state.json"


def get_today() -> str:
    return date.today().isoformat()


def load_daily_state() -> dict:
    """Load today's trading state — resets automatically each new day"""
    today = get_today()
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r") as f:
            state = json.load(f)
        if state.get("date") != today:
            state = fresh_state(today)
            save_daily_state(state)
    else:
        state = fresh_state(today)
        save_daily_state(state)
    return state


def fresh_state(today: str) -> dict:
    return {
        "date": today,
        "realised_ppl": 0.0,
        "trades_executed": 0,
        "trades_recommended": 0,
        "trades_skipped": 0,
        "trades": []
    }


def save_daily_state(state: dict):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def log_recommendation(ticker: str, direction: str, reason: str, confidence: float, executed: bool, skip_reason: str = None):
    """
    Log every trade Claude recommends — whether executed or skipped.
    This is what powers win-rate and decision quality metrics in the dashboard.
    """
    state = load_daily_state()

    entry = {
        "date": get_today(),
        "time": datetime.now().isoformat(),
        "ticker": ticker,
        "direction": direction,
        "reason": reason,
        "confidence": confidence,
        "executed": executed,
        "skip_reason": skip_reason,  # e.g. "low confidence", "user skipped", "risk limit"
        "outcome_ppl": None,         # filled in later when position closes
        "outcome_pct": None
    }

    # Update daily state counters
    state["trades_recommended"] += 1
    if executed:
        state["trades_executed"] += 1
    else:
        state["trades_skipped"] += 1
    save_daily_state(state)

    # Append to master recommendations log
    all_recs = []
    if os.path.exists(RECOMMENDATIONS_FILE):
        with open(RECOMMENDATIONS_FILE, "r") as f:
            all_recs = json.load(f)
    all_recs.append(entry)
    with open(RECOMMENDATIONS_FILE, "w") as f:
        json.dump(all_recs, f, indent=2)

    status = "✅ EXECUTED" if executed else f"⏭️  SKIPPED ({skip_reason or 'unknown'})"
    print(f"  📋 Logged rec: {direction} {ticker} | {status}")


def update_recommendation_outcome(ticker: str, entry_time: str, ppl: float, pct: float):
    """
    Call this when a position closes to record the actual outcome against the recommendation.
    entry_time should match the 'time' field in the recommendation.
    """
    if not os.path.exists(RECOMMENDATIONS_FILE):
        return

    with open(RECOMMENDATIONS_FILE, "r") as f:
        all_recs = json.load(f)

    for rec in all_recs:
        if rec["ticker"] == ticker and rec["time"] == entry_time:
            rec["outcome_ppl"] = ppl
            rec["outcome_pct"] = pct
            break

    with open(RECOMMENDATIONS_FILE, "w") as f:
        json.dump(all_recs, f, indent=2)


def log_trade(trade: dict, order_result: dict):
    """Log an executed trade"""
    state = load_daily_state()

    entry = {
        "time": datetime.now().isoformat(),
        "ticker": trade.get("ticker"),
        "direction": trade.get("direction"),
        "quantity": trade.get("quantity"),
        "current_price": trade.get("current_price"),
        "estimated_value": trade.get("estimated_value"),
        "reason": trade.get("reason"),
        "order_result": order_result
    }

    state["trades"].append(entry)
    save_daily_state(state)

    all_trades = []
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE, "r") as f:
            all_trades = json.load(f)
    all_trades.append(entry)
    with open(LOG_FILE, "w") as f:
        json.dump(all_trades, f, indent=2)

    print(f"  ✅ Logged: {trade['direction']} {trade.get('quantity','?')} x {trade['ticker']}")


def update_realised_ppl(amount: float):
    """Call this when a position is closed to track real profit"""
    state = load_daily_state()
    state["realised_ppl"] += amount
    save_daily_state(state)


def get_daily_ppl() -> float:
    state = load_daily_state()
    return state["realised_ppl"]


def print_daily_summary():
    state = load_daily_state()
    recommended = state.get("trades_recommended", state["trades_executed"])
    executed = state["trades_executed"]
    skipped = state.get("trades_skipped", 0)
    exec_rate = (executed / recommended * 100) if recommended > 0 else 0

    print(f"\n📊 Daily Summary — {state['date']}")
    print(f"  Recommended      : {recommended}")
    print(f"  Executed         : {executed}  ({exec_rate:.0f}%)")
    print(f"  Skipped          : {skipped}")
    print(f"  Realised P&L     : £{state['realised_ppl']:.2f}")
    print(f"  Target           : £30.00")
    print(f"  Remaining        : £{max(0, 30 - state['realised_ppl']):.2f}")


# --- TEST ---
if __name__ == "__main__":
    print("Testing logger...")
    log_recommendation("AAPL", "BUY", "RSI oversold + bullish news", 0.82, executed=True)
    log_recommendation("TSLA", "SELL", "MACD crossover", 0.55, executed=False, skip_reason="low confidence")
    log_recommendation("NVDA", "BUY", "Volume surge detected", 0.71, executed=False, skip_reason="user skipped")
    print_daily_summary()
