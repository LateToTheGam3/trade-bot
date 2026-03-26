import yfinance as yf
import pandas as pd
import ta
from datetime import datetime, timedelta

# ── Universe of stocks to scan ────────────────────────────────────
# Mix of large caps, small caps, tech, biotech, AI plays
BASE_WATCHLIST = [
    # Large cap momentum
    "AAPL", "NVDA", "TSLA", "MSFT", "AMZN", "META", "GOOGL",
    # AI / semiconductor small caps
    "APLD", "RGTI", "IONQ", "QBTS", "SMCI", "BBAI", "SOUN",
    # High volatility / momentum plays
    "PLTR", "RKLB", "LUNR", "MSTR", "COIN", "HOOD",
    # Biotech
    "MRNA", "NVAX", "RIOT",
]

def get_stock_data(ticker: str, period: str = "5d", interval: str = "15m") -> pd.DataFrame:
    """Fetch intraday OHLCV data"""
    try:
        df = yf.download(ticker, period=period, interval=interval, progress=False)
        if df.empty or len(df) < 20:
            return None
        df.columns = [c[0].lower() if isinstance(c, tuple) else c.lower() for c in df.columns]
        return df
    except Exception as e:
        return None

def calculate_technicals(df: pd.DataFrame) -> dict:
    """Calculate RSI, MACD, VWAP, Bollinger Bands"""
    try:
        close = df["close"].squeeze()
        high  = df["high"].squeeze()
        low   = df["low"].squeeze()
        vol   = df["volume"].squeeze()

        # RSI
        rsi = ta.momentum.RSIIndicator(close, window=14).rsi().iloc[-1]

        # MACD
        macd_ind  = ta.trend.MACD(close)
        macd      = macd_ind.macd().iloc[-1]
        macd_sig  = macd_ind.macd_signal().iloc[-1]
        macd_hist = macd_ind.macd_diff().iloc[-1]

        # Bollinger Bands
        bb        = ta.volatility.BollingerBands(close, window=20, window_dev=2)
        bb_upper  = bb.bollinger_hband().iloc[-1]
        bb_lower  = bb.bollinger_lband().iloc[-1]
        bb_mid    = bb.bollinger_mavg().iloc[-1]
        bb_pct    = bb.bollinger_pband().iloc[-1]  # 0=lower band, 1=upper band

        # VWAP (approximate using typical price * volume)
        typical_price = (high + low + close) / 3
        vwap = (typical_price * vol).sum() / vol.sum()
        current_price = float(close.iloc[-1])
        vwap_signal = "ABOVE" if current_price > float(vwap) else "BELOW"

        # Volume surge (current vs 20-period average)
        avg_vol     = float(vol.iloc[-20:].mean())
        latest_vol  = float(vol.iloc[-1])
        vol_surge   = round(latest_vol / avg_vol, 2) if avg_vol > 0 else 1.0

        # Price change today
        price_open   = float(df["open"].iloc[-1])
        price_change = round(((current_price - price_open) / price_open) * 100, 2)

        return {
            "price":        round(current_price, 2),
            "price_change": price_change,
            "rsi":          round(float(rsi), 1),
            "macd":         round(float(macd), 4),
            "macd_signal":  round(float(macd_sig), 4),
            "macd_hist":    round(float(macd_hist), 4),
            "bb_upper":     round(float(bb_upper), 2),
            "bb_lower":     round(float(bb_lower), 2),
            "bb_pct":       round(float(bb_pct), 2),
            "vwap":         round(float(vwap), 2),
            "vwap_signal":  vwap_signal,
            "vol_surge":    vol_surge,
        }
    except Exception as e:
        return None

def score_ticker(technicals: dict) -> dict:
    """
    Score a ticker 0-100 for trading opportunity.
    Returns score, direction (LONG/SHORT), and reasons.
    """
    score   = 0
    reasons = []
    direction = "NEUTRAL"

    rsi      = technicals["rsi"]
    macd_h   = technicals["macd_hist"]
    bb_pct   = technicals["bb_pct"]
    vwap_sig = technicals["vwap_signal"]
    vol_surge = technicals["vol_surge"]
    change   = technicals["price_change"]

    # ── LONG signals ──────────────────────────────────────────────
    long_score  = 0
    short_score = 0

    # RSI
    if rsi < 35:
        long_score += 25
        reasons.append(f"RSI oversold ({rsi})")
    elif rsi < 45:
        long_score += 10
        reasons.append(f"RSI low ({rsi})")
    elif rsi > 65:
        short_score += 25
        reasons.append(f"RSI overbought ({rsi})")
    elif rsi > 55:
        short_score += 10
        reasons.append(f"RSI high ({rsi})")

    # MACD histogram
    if macd_h > 0:
        long_score += 20
        reasons.append("MACD bullish crossover")
    elif macd_h < 0:
        short_score += 20
        reasons.append("MACD bearish crossover")

    # Bollinger Bands
    if bb_pct < 0.2:
        long_score += 20
        reasons.append("Price near lower Bollinger Band")
    elif bb_pct > 0.8:
        short_score += 20
        reasons.append("Price near upper Bollinger Band")

    # VWAP
    if vwap_sig == "ABOVE":
        long_score += 15
        reasons.append("Price above VWAP")
    else:
        short_score += 15
        reasons.append("Price below VWAP")

    # Volume surge (confirms signal)
    if vol_surge > 1.5:
        bonus = min(20, int(vol_surge * 5))
        if long_score > short_score:
            long_score += bonus
        else:
            short_score += bonus
        reasons.append(f"Volume surge {vol_surge}x")

    # Momentum (price change)
    if abs(change) > 1.5:
        if change > 0:
            long_score += 10
            reasons.append(f"Strong upward move +{change}%")
        else:
            short_score += 10
            reasons.append(f"Strong downward move {change}%")

    # Determine direction and final score
    if long_score > short_score:
        direction = "LONG"
        score = min(100, long_score)
    elif short_score > long_score:
        direction = "SHORT"
        score = min(100, short_score)

    return {
        "score":     score,
        "direction": direction,
        "reasons":   reasons
    }

def scan_market(min_score: int = 50) -> list:
    """
    Scan all tickers and return ranked opportunities.
    Only returns tickers with score >= min_score.
    """
    print(f"🔍 Scanning {len(BASE_WATCHLIST)} tickers...")
    results = []

    for ticker in BASE_WATCHLIST:
        df = get_stock_data(ticker)
        if df is None:
            continue

        techs = calculate_technicals(df)
        if techs is None:
            continue

        scored = score_ticker(techs)
        if scored["score"] >= min_score:
            results.append({
                "ticker":    ticker,
                **techs,
                **scored
            })

    # Sort by score descending
    results.sort(key=lambda x: x["score"], reverse=True)
    return results

# --- TEST ---
if __name__ == "__main__":
    print(f"Market scan — {datetime.now().strftime('%H:%M:%S')}\n")
    opportunities = scan_market(min_score=30)

    if not opportunities:
        print("No strong opportunities found right now.")
    else:
        print(f"Found {len(opportunities)} opportunities:\n")
        for o in opportunities[:10]:
            arrow = "📈" if o["direction"] == "LONG" else "📉"
            print(f"{arrow} {o['ticker']:6} | Score: {o['score']:3} | {o['direction']:5} | "
                  f"${o['price']:8.2f} | RSI:{o['rsi']:5.1f} | "
                  f"Vol surge:{o['vol_surge']}x | Change:{o['price_change']}%")
            for r in o["reasons"][:3]:
                print(f"         → {r}")
            print()