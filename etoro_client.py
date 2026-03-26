import requests
import uuid
import os
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("ETORO_TOKEN")
PUBLIC_KEY = os.getenv("ETORO_PUBLIC_KEY")
BASE_URL = "https://public-api.etoro.com/api/v1"

# Known eToro instrument IDs — no need to search
INSTRUMENT_IDS = {
    "AAPL": 1001,
    "TSLA": 1002,
    "NVDA": 1003,
    "AMZN": 1004,
    "GOOGL": 1005,
    "MSFT": 1006,
}

def get_headers():
    return {
        "x-api-key": PUBLIC_KEY,
        "x-user-key": TOKEN,
        "x-request-id": str(uuid.uuid4()),
        "Content-Type": "application/json"
    }

def get_instrument_price(symbol: str) -> float:
    """Get current price for a symbol"""
    inst_id = INSTRUMENT_IDS.get(symbol)
    if not inst_id:
        raise ValueError(f"Unknown symbol: {symbol}")
    r = requests.get(
        f"{BASE_URL}/market-data/instruments/rates",
        headers=get_headers(),
        params={"instrumentIds": inst_id}
    )
    data = r.json()
    print(f"  [DEBUG] Price response: {str(data)[:300]}")
    return data

def place_order(symbol: str, amount_gbp: float, is_buy: bool,
                take_profit_pct: float = 0.75, stop_loss_pct: float = 0.3):
    """
    Place a demo market order.
    is_buy=True  → LONG  (profit when price goes up)
    is_buy=False → SHORT (profit when price goes down)
    """
    inst_id = INSTRUMENT_IDS.get(symbol)
    if not inst_id:
        raise ValueError(f"Unknown symbol: {symbol}")

    if is_buy:
        tp_rate = 1 + (take_profit_pct / 100)
        sl_rate = 1 - (stop_loss_pct / 100)
    else:
        tp_rate = 1 - (take_profit_pct / 100)
        sl_rate = 1 + (stop_loss_pct / 100)

    payload = {
        "instrumentId": inst_id,
        "isBuy": is_buy,
        "amount": amount_gbp,
        "leverage": 1,
        "takeProfitRate": tp_rate,
        "stopLossRate": sl_rate
    }

    print(f"  [DEBUG] Payload: {payload}")
    r = requests.post(
        f"{BASE_URL}/trading/execution/demo/market-open-orders/by-amount",
        headers=get_headers(),
        json=payload
    )
    print(f"  [DEBUG] Status: {r.status_code} | Response: {r.text[:500]}")
    return r.json() if r.text else {}

def get_open_positions():
    """Get all open demo positions"""
    r = requests.get(
        f"{BASE_URL}/trading/execution/demo/market-open-orders",
        headers=get_headers()
    )
    print(f"  [DEBUG] Status: {r.status_code} | Response: {r.text[:500]}")
    return r.json() if r.text else {}

def close_position(position_id: str):
    """Close an open demo position"""
    r = requests.delete(
        f"{BASE_URL}/trading/execution/demo/market-open-orders/{position_id}",
        headers=get_headers()
    )
    return r.json() if r.text else {}

# --- TEST ---
if __name__ == "__main__":
    print("Testing price fetch for AAPL...")
    get_instrument_price("AAPL")

    print("\nPlacing demo LONG on AAPL (£500)...")
    result = place_order("AAPL", 500, is_buy=True)
    print(f"Result: {result}")

    print("\nFetching open positions...")
    positions = get_open_positions()
    print(f"Positions: {positions}")