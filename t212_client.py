import requests
import base64
import os
from dotenv import load_dotenv

load_dotenv()

API_KEY    = os.getenv("T212_API_KEY")
API_SECRET = os.getenv("T212_API_SECRET")
PAPER_URL  = "https://demo.trading212.com/api/v0"

credentials = base64.b64encode(f"{API_KEY}:{API_SECRET}".encode()).decode()
HEADERS = {
    "Authorization": f"Basic {credentials}",
    "Content-Type": "application/json"
}

def get_account_info():
    r = requests.get(f"{PAPER_URL}/equity/account/info", headers=HEADERS)
    return r.json()

def get_account_cash():
    r = requests.get(f"{PAPER_URL}/equity/account/cash", headers=HEADERS)
    return r.json()

def get_portfolio():
    r = requests.get(f"{PAPER_URL}/equity/portfolio", headers=HEADERS)
    return r.json()

def get_instruments():
    r = requests.get(f"{PAPER_URL}/equity/metadata/instruments", headers=HEADERS)
    return r.json()

def place_order(ticker, quantity, direction="BUY"):
    """
    Place a market order.
    BUY  = positive quantity
    SELL = negative quantity
    No 'type' field — T212 infers market order automatically.
    """
    quantity = abs(float(quantity))
    if direction == "SELL":
        quantity = -quantity

    payload = {
        "ticker": ticker,
        "quantity": quantity
    }

    print(f"  [DEBUG] Sending payload: {payload}")
    r = requests.post(
        f"{PAPER_URL}/equity/orders/market",
        headers=HEADERS,
        json=payload
    )
    print(f"  [DEBUG] Status: {r.status_code} | Response: {r.text}")
    return r.json() if r.text else {"status": r.status_code}

def get_open_orders():
    r = requests.get(f"{PAPER_URL}/equity/orders", headers=HEADERS)
    return r.json()

def cancel_order(order_id):
    r = requests.delete(f"{PAPER_URL}/equity/orders/{order_id}", headers=HEADERS)
    return r.status_code

# --- TEST ---
if __name__ == "__main__":
    print("Account:", get_account_info())
    print("Cash:", get_account_cash())
    print("Portfolio:", get_portfolio())