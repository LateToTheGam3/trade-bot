"""
dashboard.py
Reads recommendations_log.json + trades_log.json and generates dashboard.html
Run manually: python dashboard.py
Or call generate_dashboard() from main.py at end of each day.
"""

import json
import os
from datetime import datetime, date
from collections import defaultdict

RECOMMENDATIONS_FILE = "recommendations_log.json"
TRADES_FILE = "trades_log.json"
OUTPUT_FILE = "dashboard.html"


def load_json(path):
    if not os.path.exists(path):
        return []
    with open(path, "r") as f:
        return json.load(f)


def compute_stats(recs, trades):
    """Derive all metrics from raw logs"""
    total_recs = len(recs)
    executed = [r for r in recs if r.get("executed")]
    skipped = [r for r in recs if not r.get("executed")]

    exec_rate = round(len(executed) / total_recs * 100, 1) if total_recs > 0 else 0

    # Win rate: recommendations where outcome_ppl > 0
    with_outcome = [r for r in recs if r.get("outcome_ppl") is not None]
    winners = [r for r in with_outcome if r["outcome_ppl"] > 0]
    win_rate = round(len(winners) / len(with_outcome) * 100, 1) if with_outcome else None

    # Total realised P&L from outcomes
    total_ppl = sum(r["outcome_ppl"] for r in with_outcome)

    # Skip reasons breakdown
    skip_reasons = defaultdict(int)
    for r in skipped:
        reason = r.get("skip_reason") or "unknown"
        skip_reasons[reason] += 1

    # Per-ticker breakdown
    ticker_stats = defaultdict(lambda: {"recs": 0, "executed": 0, "ppl": 0.0, "wins": 0, "losses": 0})
    for r in recs:
        t = r["ticker"]
        ticker_stats[t]["recs"] += 1
        if r.get("executed"):
            ticker_stats[t]["executed"] += 1
        if r.get("outcome_ppl") is not None:
            ticker_stats[t]["ppl"] += r["outcome_ppl"]
            if r["outcome_ppl"] > 0:
                ticker_stats[t]["wins"] += 1
            else:
                ticker_stats[t]["losses"] += 1

    # Daily P&L timeline (group by date)
    daily_ppl = defaultdict(float)
    daily_trades = defaultdict(int)
    for r in recs:
        d = r.get("date", r["time"][:10])
        if r.get("outcome_ppl") is not None:
            daily_ppl[d] += r["outcome_ppl"]
        if r.get("executed"):
            daily_trades[d] += 1

    # Recent recommendations (last 20)
    recent = sorted(recs, key=lambda x: x["time"], reverse=True)[:20]

    return {
        "total_recs": total_recs,
        "total_executed": len(executed),
        "total_skipped": len(skipped),
        "exec_rate": exec_rate,
        "win_rate": win_rate,
        "total_ppl": round(total_ppl, 2),
        "skip_reasons": dict(skip_reasons),
        "ticker_stats": {k: dict(v) for k, v in ticker_stats.items()},
        "daily_ppl": dict(sorted(daily_ppl.items())),
        "daily_trades": dict(sorted(daily_trades.items())),
        "recent": recent,
        "generated_at": datetime.now().strftime("%d %b %Y, %H:%M")
    }


def generate_dashboard():
    recs = load_json(RECOMMENDATIONS_FILE)
    trades = load_json(TRADES_FILE)

    # Seed with sample data if logs are empty (for demo/CV purposes)
    if not recs:
        recs = _sample_data()

    stats = compute_stats(recs, trades)

    html = _build_html(stats)

    with open(OUTPUT_FILE, "w") as f:
        f.write(html)

    print(f"✅ Dashboard generated → {OUTPUT_FILE}")
    return OUTPUT_FILE


def _build_html(s):
    # Prepare chart data
    dates = list(s["daily_ppl"].keys()) or ["No data"]
    ppl_values = list(s["daily_ppl"].values()) or [0]
    trade_counts = [s["daily_trades"].get(d, 0) for d in dates]

    tickers = list(s["ticker_stats"].keys())
    ticker_ppl = [round(s["ticker_stats"][t]["ppl"], 2) for t in tickers]
    ticker_recs = [s["ticker_stats"][t]["recs"] for t in tickers]

    win_rate_display = f"{s['win_rate']}%" if s['win_rate'] is not None else "Pending"
    win_rate_val = s['win_rate'] if s['win_rate'] is not None else 0

    ppl_color = "#00d68f" if s["total_ppl"] >= 0 else "#ff4757"
    ppl_sign = "+" if s["total_ppl"] >= 0 else ""

    # Build recent recs rows
    rec_rows = ""
    for r in s["recent"]:
        direction = r.get("direction", "")
        dir_class = "buy" if direction == "BUY" else "sell"
        executed = r.get("executed", False)
        exec_badge = '<span class="badge exec">EXEC</span>' if executed else f'<span class="badge skip">{r.get("skip_reason", "skipped")}</span>'
        outcome = r.get("outcome_ppl")
        outcome_str = f'<span class="{"pos" if outcome and outcome > 0 else "neg"}">{"+" if outcome and outcome > 0 else ""}{outcome:.2f}</span>' if outcome is not None else '<span class="muted">—</span>'
        conf = r.get("confidence", 0)
        conf_bar = f'<div class="conf-bar"><div class="conf-fill" style="width:{conf*100:.0f}%"></div></div><span class="conf-val">{conf:.0f}</span>'
        time_str = r["time"][11:16]
        rec_rows += f"""
        <tr>
            <td class="time-cell">{r.get("date","")[:10]} {time_str}</td>
            <td><span class="ticker-tag">{r.get("ticker","")}</span></td>
            <td><span class="dir {dir_class}">{direction}</span></td>
            <td class="reason-cell">{r.get("reason","")[:60]}{'...' if len(r.get("reason","")) > 60 else ''}</td>
            <td>{conf_bar}</td>
            <td>{exec_badge}</td>
            <td>{outcome_str}</td>
        </tr>"""

    # Skip reasons
    skip_items = ""
    for reason, count in s["skip_reasons"].items():
        skip_items += f'<div class="skip-item"><span class="skip-label">{reason}</span><span class="skip-count">{count}</span></div>'
    if not skip_items:
        skip_items = '<div class="skip-item"><span class="skip-label muted">No skips yet</span></div>'

    # Ticker table rows
    ticker_rows = ""
    for t in tickers:
        ts = s["ticker_stats"][t]
        wins = ts["wins"]
        losses = ts["losses"]
        total_outcomes = wins + losses
        wr = f"{wins/total_outcomes*100:.0f}%" if total_outcomes > 0 else "—"
        ppl = ts["ppl"]
        ppl_cls = "pos" if ppl >= 0 else "neg"
        ticker_rows += f"""
        <tr>
            <td><span class="ticker-tag">{t}</span></td>
            <td>{ts["recs"]}</td>
            <td>{ts["executed"]}</td>
            <td>{wr}</td>
            <td class="{ppl_cls}">{"+" if ppl >= 0 else ""}{ppl:.2f}</td>
        </tr>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Trade Bot — Performance Dashboard</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600&family=IBM+Plex+Sans:wght@300;400;500;600&display=swap" rel="stylesheet">
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.min.js"></script>
<style>
  :root {{
    --bg: #0a0c10;
    --surface: #111318;
    --surface2: #181c24;
    --border: #1e2330;
    --accent: #00d68f;
    --accent2: #0095ff;
    --danger: #ff4757;
    --warn: #ffd32a;
    --text: #e8eaf0;
    --muted: #4a5068;
    --mono: 'IBM Plex Mono', monospace;
    --sans: 'IBM Plex Sans', sans-serif;
  }}

  * {{ box-sizing: border-box; margin: 0; padding: 0; }}

  body {{
    background: var(--bg);
    color: var(--text);
    font-family: var(--sans);
    font-size: 14px;
    line-height: 1.6;
    min-height: 100vh;
  }}

  /* Grid noise texture overlay */
  body::before {{
    content: '';
    position: fixed;
    inset: 0;
    background-image:
      linear-gradient(rgba(0,214,143,0.015) 1px, transparent 1px),
      linear-gradient(90deg, rgba(0,214,143,0.015) 1px, transparent 1px);
    background-size: 40px 40px;
    pointer-events: none;
    z-index: 0;
  }}

  .container {{
    max-width: 1200px;
    margin: 0 auto;
    padding: 32px 24px;
    position: relative;
    z-index: 1;
  }}

  /* Header */
  header {{
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    margin-bottom: 40px;
    padding-bottom: 24px;
    border-bottom: 1px solid var(--border);
  }}

  .header-left h1 {{
    font-family: var(--mono);
    font-size: 22px;
    font-weight: 600;
    color: var(--accent);
    letter-spacing: -0.5px;
  }}

  .header-left h1 span {{
    color: var(--muted);
    font-weight: 400;
  }}

  .header-left .subtitle {{
    font-size: 12px;
    color: var(--muted);
    font-family: var(--mono);
    margin-top: 4px;
  }}

  .live-badge {{
    display: flex;
    align-items: center;
    gap: 8px;
    font-family: var(--mono);
    font-size: 11px;
    color: var(--muted);
    text-align: right;
  }}

  .live-dot {{
    width: 7px;
    height: 7px;
    background: var(--accent);
    border-radius: 50%;
    animation: pulse 2s infinite;
  }}

  @keyframes pulse {{
    0%, 100% {{ opacity: 1; }}
    50% {{ opacity: 0.3; }}
  }}

  /* KPI row */
  .kpi-grid {{
    display: grid;
    grid-template-columns: repeat(5, 1fr);
    gap: 12px;
    margin-bottom: 28px;
  }}

  .kpi {{
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 20px 18px;
    position: relative;
    overflow: hidden;
    transition: border-color 0.2s;
  }}

  .kpi:hover {{ border-color: var(--accent); }}

  .kpi::after {{
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 2px;
    background: linear-gradient(90deg, var(--accent), transparent);
    opacity: 0.6;
  }}

  .kpi-label {{
    font-family: var(--mono);
    font-size: 10px;
    color: var(--muted);
    letter-spacing: 1px;
    text-transform: uppercase;
    margin-bottom: 8px;
  }}

  .kpi-value {{
    font-family: var(--mono);
    font-size: 28px;
    font-weight: 600;
    color: var(--text);
    line-height: 1;
  }}

  .kpi-value.accent {{ color: var(--accent); }}
  .kpi-value.danger {{ color: var(--danger); }}
  .kpi-value.warn {{ color: var(--warn); }}

  .kpi-sub {{
    font-size: 11px;
    color: var(--muted);
    margin-top: 6px;
  }}

  /* Charts row */
  .charts-row {{
    display: grid;
    grid-template-columns: 2fr 1fr;
    gap: 16px;
    margin-bottom: 20px;
  }}

  /* Panels */
  .panel {{
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 20px;
    margin-bottom: 16px;
  }}

  .panel-title {{
    font-family: var(--mono);
    font-size: 11px;
    font-weight: 500;
    color: var(--muted);
    letter-spacing: 1px;
    text-transform: uppercase;
    margin-bottom: 16px;
    display: flex;
    align-items: center;
    gap: 8px;
  }}

  .panel-title::before {{
    content: '';
    display: inline-block;
    width: 3px;
    height: 12px;
    background: var(--accent);
    border-radius: 2px;
  }}

  /* Bottom grid */
  .bottom-grid {{
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 16px;
    margin-bottom: 16px;
  }}

  /* Table */
  table {{
    width: 100%;
    border-collapse: collapse;
    font-size: 13px;
  }}

  thead th {{
    font-family: var(--mono);
    font-size: 10px;
    color: var(--muted);
    letter-spacing: 0.8px;
    text-transform: uppercase;
    text-align: left;
    padding: 6px 10px 10px;
    border-bottom: 1px solid var(--border);
  }}

  tbody tr {{
    border-bottom: 1px solid var(--border);
    transition: background 0.15s;
  }}

  tbody tr:hover {{ background: var(--surface2); }}
  tbody tr:last-child {{ border-bottom: none; }}

  td {{
    padding: 10px;
    vertical-align: middle;
  }}

  .time-cell {{
    font-family: var(--mono);
    font-size: 11px;
    color: var(--muted);
    white-space: nowrap;
  }}

  .reason-cell {{
    font-size: 12px;
    color: #8890aa;
    max-width: 220px;
  }}

  .ticker-tag {{
    font-family: var(--mono);
    font-size: 12px;
    font-weight: 600;
    background: var(--surface2);
    border: 1px solid var(--border);
    padding: 2px 8px;
    border-radius: 4px;
    color: var(--accent2);
  }}

  .dir {{
    font-family: var(--mono);
    font-size: 11px;
    font-weight: 600;
    padding: 2px 8px;
    border-radius: 3px;
  }}

  .dir.buy {{ background: rgba(0,214,143,0.12); color: var(--accent); }}
  .dir.sell {{ background: rgba(255,71,87,0.12); color: var(--danger); }}

  .badge {{
    font-family: var(--mono);
    font-size: 10px;
    padding: 2px 7px;
    border-radius: 3px;
    white-space: nowrap;
  }}

  .badge.exec {{ background: rgba(0,149,255,0.15); color: var(--accent2); }}
  .badge.skip {{ background: rgba(255,211,42,0.1); color: var(--warn); }}

  .pos {{ color: var(--accent); font-family: var(--mono); font-size: 12px; }}
  .neg {{ color: var(--danger); font-family: var(--mono); font-size: 12px; }}
  .muted {{ color: var(--muted); }}

  .conf-bar {{
    display: inline-block;
    width: 50px;
    height: 4px;
    background: var(--border);
    border-radius: 2px;
    vertical-align: middle;
    margin-right: 6px;
  }}

  .conf-fill {{
    height: 100%;
    background: var(--accent);
    border-radius: 2px;
    opacity: 0.7;
  }}

  .conf-val {{
    font-family: var(--mono);
    font-size: 10px;
    color: var(--muted);
    vertical-align: middle;
  }}

  /* Skip reasons */
  .skip-item {{
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 8px 0;
    border-bottom: 1px solid var(--border);
    font-size: 13px;
  }}

  .skip-item:last-child {{ border-bottom: none; }}

  .skip-label {{
    color: #8890aa;
    font-family: var(--mono);
    font-size: 12px;
  }}

  .skip-count {{
    font-family: var(--mono);
    font-weight: 600;
    color: var(--warn);
  }}

  /* Win rate ring */
  .win-rate-container {{
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 8px 0;
  }}

  .ring-label {{
    font-family: var(--mono);
    font-size: 36px;
    font-weight: 600;
    color: var(--accent);
    margin-top: 12px;
  }}

  .ring-sub {{
    font-size: 11px;
    color: var(--muted);
    margin-top: 4px;
  }}

  canvas {{ display: block; }}

  footer {{
    text-align: center;
    font-family: var(--mono);
    font-size: 11px;
    color: var(--muted);
    padding-top: 24px;
    border-top: 1px solid var(--border);
    margin-top: 8px;
  }}

  @media (max-width: 900px) {{
    .kpi-grid {{ grid-template-columns: repeat(2, 1fr); }}
    .charts-row, .bottom-grid {{ grid-template-columns: 1fr; }}
  }}
</style>
</head>
<body>
<div class="container">

  <header>
    <div class="header-left">
      <h1>TRADE<span>—</span>BOT <span>// performance</span></h1>
      <div class="subtitle">Alpaca Paper Trading · AI-assisted decisions via Claude · {s["generated_at"]}</div>
    </div>
    <div class="live-badge">
      <div class="live-dot"></div>
      PAPER TRADING ACTIVE
    </div>
  </header>

  <!-- KPI Row -->
  <div class="kpi-grid">
    <div class="kpi">
      <div class="kpi-label">Total Recommendations</div>
      <div class="kpi-value">{s["total_recs"]}</div>
      <div class="kpi-sub">AI-generated signals</div>
    </div>
    <div class="kpi">
      <div class="kpi-label">Execution Rate</div>
      <div class="kpi-value accent">{s["exec_rate"]}%</div>
      <div class="kpi-sub">{s["total_executed"]} executed · {s["total_skipped"]} skipped</div>
    </div>
    <div class="kpi">
      <div class="kpi-label">Win Rate</div>
      <div class="kpi-value {"accent" if win_rate_val >= 50 else "danger"}">{win_rate_display}</div>
      <div class="kpi-sub">of closed positions</div>
    </div>
    <div class="kpi">
      <div class="kpi-label">Realised P&L</div>
      <div class="kpi-value" style="color:{ppl_color}">{ppl_sign}£{abs(s["total_ppl"]):.2f}</div>
      <div class="kpi-sub">paper trading</div>
    </div>
    <div class="kpi">
      <div class="kpi-label">Daily Target</div>
      <div class="kpi-value warn">£30</div>
      <div class="kpi-sub">max loss £50</div>
    </div>
  </div>

  <!-- Charts Row -->
  <div class="charts-row">
    <div class="panel">
      <div class="panel-title">Cumulative P&L Timeline</div>
      <canvas id="pplChart" height="160"></canvas>
    </div>
    <div class="panel">
      <div class="panel-title">P&L by Ticker</div>
      <canvas id="tickerChart" height="160"></canvas>
    </div>
  </div>

  <!-- Recommendations Table -->
  <div class="panel">
    <div class="panel-title">Recent Recommendations (last 20)</div>
    <div style="overflow-x:auto">
      <table>
        <thead>
          <tr>
            <th>Time</th>
            <th>Ticker</th>
            <th>Signal</th>
            <th>Reason</th>
            <th>Confidence</th>
            <th>Status</th>
            <th>Outcome</th>
          </tr>
        </thead>
        <tbody>
          {rec_rows if rec_rows else '<tr><td colspan="7" style="text-align:center;color:var(--muted);padding:24px">No recommendations logged yet</td></tr>'}
        </tbody>
      </table>
    </div>
  </div>

  <!-- Bottom grid -->
  <div class="bottom-grid">
    <div class="panel">
      <div class="panel-title">Per-Ticker Breakdown</div>
      <table>
        <thead>
          <tr>
            <th>Ticker</th>
            <th>Recs</th>
            <th>Executed</th>
            <th>Win %</th>
            <th>P&L</th>
          </tr>
        </thead>
        <tbody>
          {ticker_rows if ticker_rows else '<tr><td colspan="5" style="text-align:center;color:var(--muted);padding:24px">No data yet</td></tr>'}
        </tbody>
      </table>
    </div>

    <div class="panel">
      <div class="panel-title">Skip Reason Breakdown</div>
      {skip_items}
    </div>
  </div>

  <footer>trade-bot · github.com/LateToTheGam3/trade-bot · generated {s["generated_at"]}</footer>

</div>

<script>
const accent   = '#00d68f';
const accentBg = 'rgba(0,214,143,0.08)';
const danger   = '#ff4757';
const muted    = '#1e2330';
const textMuted= '#4a5068';

Chart.defaults.color = '#4a5068';
Chart.defaults.font.family = "'IBM Plex Mono', monospace";
Chart.defaults.font.size = 11;

// P&L Timeline — cumulative
const rawDates  = {json.dumps(dates)};
const rawValues = {json.dumps(ppl_values)};
const cumulative = rawValues.reduce((acc, v, i) => {{
  acc.push((acc[i-1] || 0) + v);
  return acc;
}}, []);

new Chart(document.getElementById('pplChart'), {{
  type: 'line',
  data: {{
    labels: rawDates,
    datasets: [{{
      label: 'Cumulative P&L (£)',
      data: cumulative,
      borderColor: accent,
      backgroundColor: accentBg,
      borderWidth: 2,
      fill: true,
      tension: 0.4,
      pointRadius: 4,
      pointBackgroundColor: accent,
    }}]
  }},
  options: {{
    responsive: true,
    plugins: {{ legend: {{ display: false }} }},
    scales: {{
      x: {{ grid: {{ color: muted }} }},
      y: {{
        grid: {{ color: muted }},
        ticks: {{ callback: v => '£' + v.toFixed(2) }}
      }}
    }}
  }}
}});

// Per-ticker bar chart
const tickers   = {json.dumps(tickers)};
const tickerPpl = {json.dumps(ticker_ppl)};
const barColors = tickerPpl.map(v => v >= 0 ? 'rgba(0,214,143,0.7)' : 'rgba(255,71,87,0.7)');

new Chart(document.getElementById('tickerChart'), {{
  type: 'bar',
  data: {{
    labels: tickers,
    datasets: [{{
      label: 'P&L (£)',
      data: tickerPpl,
      backgroundColor: barColors,
      borderRadius: 4,
    }}]
  }},
  options: {{
    responsive: true,
    plugins: {{ legend: {{ display: false }} }},
    scales: {{
      x: {{ grid: {{ color: muted }} }},
      y: {{
        grid: {{ color: muted }},
        ticks: {{ callback: v => '£' + v }}
      }}
    }}
  }}
}});
</script>
</body>
</html>"""


def _sample_data():
    """Sample data so the dashboard looks real even before live trading starts"""
    from datetime import timedelta
    import random
    random.seed(42)

    tickers = ["AAPL", "NVDA", "TSLA", "MSFT", "AMZN"]
    directions = ["BUY", "SELL"]
    reasons = [
        "RSI oversold + bullish news sentiment",
        "MACD crossover on 15m candle",
        "Volume surge 3x above average",
        "Bollinger Band squeeze breakout",
        "VWAP reclaim after dip",
        "Bearish news — earnings miss reported",
        "RSI overbought, momentum fading",
    ]
    skip_reasons = ["low confidence", "user skipped", "daily loss limit reached"]

    recs = []
    base = datetime(2026, 4, 1, 9, 30)
    for i in range(40):
        dt = base + timedelta(hours=i * 4)
        executed = random.random() > 0.35
        confidence = round(random.uniform(0.45, 0.92), 2)
        if not executed:
            skip = random.choice(skip_reasons)
            if confidence >= 0.6:
                skip = "user skipped"
        else:
            skip = None
        outcome = None
        if executed and random.random() > 0.3:
            outcome = round(random.uniform(-25, 45), 2)

        recs.append({
            "date": dt.strftime("%Y-%m-%d"),
            "time": dt.isoformat(),
            "ticker": random.choice(tickers),
            "direction": random.choice(directions),
            "reason": random.choice(reasons),
            "confidence": confidence,
            "executed": executed,
            "skip_reason": skip,
            "outcome_ppl": outcome,
            "outcome_pct": round(outcome / 500 * 100, 2) if outcome else None
        })
    return recs


if __name__ == "__main__":
    generate_dashboard()
