from dotenv import load_dotenv
load_dotenv()

# ── Risk parameters ──────────────────────────────────────────────
DAILY_PROFIT_TARGET    = 30.0   # £ we want to make per day
DAILY_MAX_LOSS         = 50.0   # £ bot stops if loss exceeds this
MAX_POSITION_PCT       = 0.03   # max 3% of portfolio per trade
MIN_FREE_CASH          = 200.0  # always keep £200 free
MIN_CONFIDENCE         = 0.6    # minimum signal confidence to act

def check_daily_limits(current_ppl: float) -> dict:
    """
    Check if we should keep trading today.
    Returns status and reason.
    """
    if current_ppl >= DAILY_PROFIT_TARGET:
        return {
            "can_trade": False,
            "reason": f"Daily target hit! P&L = £{current_ppl:.2f}"
        }
    if current_ppl <= -DAILY_MAX_LOSS:
        return {
            "can_trade": False,
            "reason": f"Daily loss limit hit! P&L = £{current_ppl:.2f}"
        }
    return {
        "can_trade": True,
        "reason": f"Within limits. P&L = £{current_ppl:.2f}, target = £{DAILY_PROFIT_TARGET}"
    }

def calculate_quantity(ticker: str, direction: str,
                       total_portfolio: float, free_cash: float,
                       current_price: float, suggested_pct: float = 0.02) -> float:
    """
    Calculate safe position size.
    Never risks more than MAX_POSITION_PCT of total portfolio.
    """
    # Max £ we're willing to put in
    max_spend = min(
        total_portfolio * MAX_POSITION_PCT,
        free_cash - MIN_FREE_CASH
    )

    if max_spend <= 0:
        return 0.0

    # Use suggested % but cap at max
    target_spend = min(total_portfolio * suggested_pct, max_spend)

    if current_price <= 0:
        return 0.0

    quantity = target_spend / current_price

    # Round to 2 decimal places
    return round(quantity, 2)

def validate_trade(trade: dict, portfolio: list,
                   cash: dict, signals: list) -> dict:
    """
    Final validation before executing a trade.
    Returns approved trade with quantity, or rejection.
    """
    ticker    = trade.get("ticker")
    direction = trade.get("direction")
    reason    = trade.get("reason", "")

    free_cash      = cash.get("free", 0)
    total_portfolio = cash.get("total", 0)

    # Find signal for this ticker
    signal = next((s for s in signals if s["ticker"] == ticker), None)
    if not signal:
        return {"approved": False, "reason": "No signal found for ticker"}

    # Confidence check
    if signal["confidence"] < MIN_CONFIDENCE:
        return {
            "approved": False,
            "reason": f"Confidence too low: {signal['confidence']}"
        }

    # Cash check
    if free_cash <= MIN_FREE_CASH:
        return {
            "approved": False,
            "reason": f"Not enough free cash: £{free_cash:.2f}"
        }

    # Find current price from portfolio
    position = next((p for p in portfolio if p["ticker"] == ticker), None)
    current_price = position["currentPrice"] if position else 0

    # For BUYs we need a price
    if direction == "BUY" and current_price <= 0:
        return {
            "approved": False,
            "reason": "Could not determine current price"
        }

    # Calculate safe quantity
    suggested_pct = signal.get("suggested_position_size_pct", 0.02)
    quantity = calculate_quantity(
        ticker, direction,
        total_portfolio, free_cash,
        current_price, suggested_pct
    )

    if quantity <= 0:
        return {
            "approved": False,
            "reason": "Quantity calculated to 0 — not enough cash"
        }

    # For SELLs — make sure we own it
    if direction == "SELL":
        if not position:
            return {
                "approved": False,
                "reason": "Cannot sell — not in portfolio"
            }
        # Don't sell more than we own
        quantity = min(quantity, position["quantity"])

    return {
        "approved": True,
        "ticker": ticker,
        "direction": direction,
        "quantity": quantity,
        "current_price": current_price,
        "estimated_value": round(quantity * current_price, 2),
        "reason": reason
    }


# --- TEST ---
if __name__ == "__main__":
    from t212_client import get_account_cash, get_portfolio
    from data_feed import get_portfolio_summary, get_news_sentiment

    cash      = get_account_cash()
    portfolio = get_portfolio()

    print(f"Free cash: £{cash['free']:.2f}")
    print(f"Total:     £{cash['total']:.2f}")
    print(f"P&L:       £{cash['ppl']:.2f}")

    limits = check_daily_limits(cash["ppl"])
    print(f"\nTrading allowed: {limits['can_trade']}")
    print(f"Reason: {limits['reason']}")

    # Test a sample trade validation
    sample_trade = {
        "ticker": "TSLA_US_EQ",
        "direction": "BUY",
        "quantity": 1.0,
        "reason": "Test trade"
    }
    sample_signal = [{
        "ticker": "TSLA_US_EQ",
        "signal": "BUY",
        "sentiment": "BULLISH",
        "confidence": 0.75,
        "suggested_position_size_pct": 0.02
    }]

    result = validate_trade(sample_trade, portfolio, cash, sample_signal)
    print(f"\nSample trade validation:")
    print(f"  Approved: {result['approved']}")
    if result['approved']:
        print(f"  Qty: {result['quantity']} x {result['ticker']}")
        print(f"  Est. value: £{result['estimated_value']}")
    else:
        print(f"  Reason: {result['reason']}")