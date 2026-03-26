import json
import os
from datetime import datetime, date

LOG_FILE   = "trades_log.json"
STATE_FILE = "daily_state.json"

def get_today() -> str:
    return date.today().isoformat()

def load_daily_state() -> dict:
    """Load today's trading state — resets automatically each new day"""
    today = get_today()

    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r") as f:
            state = json.load(f)
        # Reset if it's a new day
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
        "realised_ppl": 0.0,       # actual profit from closed trades today
        "trades_executed": 0,
        "trades": []
    }

def save_daily_state(state: dict):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)

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
    state["trades_executed"] += 1
    save_daily_state(state)

    # Also append to master log
    all_trades = []
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE, "r") as f:
            all_trades = json.load(f)
    all_trades.append(entry)
    with open(LOG_FILE, "w") as f:
        json.dump(all_trades, f, indent=2)

    print(f"  ✅ Logged: {trade['direction']} {trade['quantity']} x {trade['ticker']}")

def update_realised_ppl(amount: float):
    """Call this when a position is closed to track real profit"""
    state = load_daily_state()
    state["realised_ppl"] += amount
    save_daily_state(state)

def get_daily_ppl() -> float:
    """Get today's realised P&L"""
    state = load_daily_state()
    return state["realised_ppl"]

def print_daily_summary():
    state = load_daily_state()
    print(f"\n📊 Daily Summary — {state['date']}")
    print(f"   Trades executed : {state['trades_executed']}")
    print(f"   Realised P&L    : £{state['realised_ppl']:.2f}")
    print(f"   Target          : £30.00")
    print(f"   Remaining       : £{max(0, 30 - state['realised_ppl']):.2f}")

# --- TEST ---
if __name__ == "__main__":
    print("Testing logger...")
    state = load_daily_state()
    print(f"Today: {state['date']}")
    print(f"Trades so far: {state['trades_executed']}")
    print(f"Realised P&L: £{state['realised_ppl']:.2f}")
    print_daily_summary()