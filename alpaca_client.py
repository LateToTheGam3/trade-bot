import requests
import os
from dotenv import load_dotenv

load_dotenv()

HEADERS = {
    "APCA-API-KEY-ID": os.getenv("ALPACA_API_KEY"),
    "APCA-API-SECRET-KEY": os.getenv("ALPACA_SECRET_KEY"),
    "Content-Type": "application/json"
}

TRADE_URL = "https://paper-api.alpaca.markets/v2"
DATA_URL  = "https://data.alpaca.markets/v2"

def get_account():
    r = requests.get(f"{TRADE_URL}/account", headers=HEADERS)
    return r.json()

def get_positions():
    r = requests.get(f"{TRADE_URL}/positions", headers=HEADERS)
    return r.json()

def get_open_orders():
    r = requests.get(f"{TRADE_URL}/orders", headers=HEADERS)
    return r.json()

def get_latest_price(symbol: str) -> float:
    """Get latest trade price for a symbol"""
    r = requests.get(
        f"{DATA_URL}/stocks/{symbol}/trades/latest",
        headers=HEADERS
    )
    data = r.json()
    return data["trade"]["p"]

def place_order(symbol: str, notional_usd: float, side: str,
                take_profit_pct: float = 2.0, stop_loss_pct: float = 1.0):
    """
    Place a bracket order with built-in take profit and stop loss.
    side: 'buy' (long) or 'sell' (short)
    notional_usd: amount in USD to spend e.g. 500
    """
    # Get current price to calculate quantity and TP/SL
    price = get_latest_price(symbol)
    qty = max(1, int(notional_usd / price))  # whole shares only
    base = price * 1.02  # buffer above latest price to avoid rejection

    if side == "buy":
        tp_price = round(base * (1 + take_profit_pct / 100), 2)
        sl_price = round(price * (1 - stop_loss_pct / 100), 2)
    else:
        tp_price = round(base * (1 - take_profit_pct / 100), 2)
        sl_price = round(price * (1 + stop_loss_pct / 100), 2)

    payload = {
        "symbol": symbol,
        "qty": str(qty),
        "side": side,
        "type": "market",
        "time_in_force": "day",
        "order_class": "bracket",
        "take_profit": {"limit_price": str(tp_price)},
        "stop_loss": {"stop_price": str(sl_price)}
    }

    print(f"  [DEBUG] Placing {side.upper()} {qty} shares of {symbol} | TP: ${tp_price} | SL: ${sl_price}")
    r = requests.post(f"{TRADE_URL}/orders", headers=HEADERS, json=payload)
    print(f"  [DEBUG] Status: {r.status_code} | Response: {r.text[:300]}")
    return r.json()

def close_position(symbol: str):
    """Close an entire position"""
    r = requests.delete(f"{TRADE_URL}/positions/{symbol}", headers=HEADERS)
    return r.json() if r.text else {}

def cancel_all_orders():
    """Cancel all open orders"""
    r = requests.delete(f"{TRADE_URL}/orders", headers=HEADERS)
    return r.status_code

# --- TEST ---
if __name__ == "__main__":
    print("Account info:")
    acc = get_account()
    print(f"  Cash: ${float(acc['cash']):,.2f}")
    print(f"  Buying power: ${float(acc['buying_power']):,.2f}")

    print("\nFetching AAPL price...")
    price = get_latest_price("AAPL")
    print(f"  AAPL: ${price}")

    print("\nPlacing paper LONG on AAPL ($500)...")
    order = place_order("AAPL", 500, "buy")
    print(f"  Order: {order.get('id')} | Status: {order.get('status')}")

    print("\nOpen positions:")
    positions = get_positions()
    for p in positions:
        print(f"  {p['symbol']}: {p['qty']} shares | P&L: ${p['unrealized_pl']}")