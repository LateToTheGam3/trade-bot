"""
claude_brain.py
---------------
Two-pass investment memo system for swing/long-term investors.

ARCHITECTURE (ref: exam guide Domain 1 - Agentic Architecture):
  Pass 1 — News Analyst subagent
    Input : raw news headlines for a ticker
    Output: structured JSON assessment (via tool_use schema)
    Job   : extract facts, identify catalysts, flag risks. No fabrication.

  Pass 2 — Memo Writer subagent
    Input : structured assessment from Pass 1 + ticker context
    Output: full investment memo in the style of a KKR/PE analyst note
    Job   : synthesise into a clear, opinionated, evidence-backed memo

Design principles applied (ref: exam guide Domain 4 - Prompt Engineering):
  - Explicit criteria over vague instructions ("flag only when X" not "be careful")
  - Few-shot examples demonstrate good vs bad output
  - Nullable fields prevent fabrication when data is absent
  - Structured tool_use schema eliminates JSON syntax errors
  - Two-pass beats single-pass: focused sequential steps, not one giant prompt
  - Quality gate between passes: Pass 2 only runs if Pass 1 meets minimum bar
"""

import anthropic
import os
import json
from dotenv import load_dotenv

load_dotenv()

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
MODEL = "claude-sonnet-4-20250514"

# ─────────────────────────────────────────────────────────────────
# TOOL SCHEMA — Pass 1 output structure
# (ref: exam guide Task 4.3 - Enforce structured output using tool use)
#
# Design decisions:
#   - nullable fields (None) prevent fabrication when data is absent
#   - enum fields with "unclear" for genuinely ambiguous signals
#   - explicit required vs optional to match what news can reliably provide
# ─────────────────────────────────────────────────────────────────

NEWS_ASSESSMENT_TOOL = {
    "name": "submit_news_assessment",
    "description": (
        "Submit a structured news assessment for a ticker after analysing provided headlines. "
        "Call this exactly once after completing your analysis. "
        "Do NOT call this if fewer than 2 relevant articles exist — return an error flag instead. "
        "Fields marked nullable may be null if the information is genuinely absent from the news."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "ticker": {
                "type": "string",
                "description": "The ticker symbol being assessed e.g. AAPL"
            },
            "company": {
                "type": "string",
                "description": "Full company name"
            },
            "overall_sentiment": {
                "type": "string",
                "enum": ["BULLISH", "BEARISH", "NEUTRAL", "MIXED", "UNCLEAR"],
                "description": (
                    "BULLISH: majority of news is positive for the stock price. "
                    "BEARISH: majority of news is negative. "
                    "NEUTRAL: no significant news or news with no clear price impact. "
                    "MIXED: roughly equal positive and negative signals. "
                    "UNCLEAR: insufficient information to make a call."
                )
            },
            "confidence": {
                "type": "number",
                "description": (
                    "Confidence in the sentiment call, 0.0 to 1.0. "
                    "Use 0.0-0.4 when signals conflict or news is thin. "
                    "Use 0.5-0.7 when one signal dominates but uncertainty remains. "
                    "Use 0.8-1.0 only when multiple strong, consistent signals align."
                )
            },
            "primary_catalyst": {
                "type": ["string", "null"],
                "description": (
                    "The single most important news event driving the sentiment call. "
                    "Quote the specific event — do not generalise. "
                    "Null if no clear catalyst exists."
                )
            },
            "catalyst_date": {
                "type": ["string", "null"],
                "description": "Date of the primary catalyst in YYYY-MM-DD format. Null if unknown."
            },
            "supporting_signals": {
                "type": "array",
                "items": {"type": "string"},
                "description": (
                    "Up to 3 additional news items that support the sentiment call. "
                    "Each item should reference a specific article, not a vague claim. "
                    "Empty array if no supporting signals."
                )
            },
            "risk_flags": {
                "type": "array",
                "items": {"type": "string"},
                "description": (
                    "Specific risks or counter-signals from the news that could invalidate the thesis. "
                    "Include regulatory issues, earnings misses, management changes, macro headwinds. "
                    "Empty array if none identified — do NOT fabricate risks."
                )
            },
            "time_horizon_signal": {
                "type": "string",
                "enum": ["SHORT_TERM", "MEDIUM_TERM", "LONG_TERM", "UNCLEAR"],
                "description": (
                    "SHORT_TERM: catalyst is time-sensitive, likely plays out in days to weeks. "
                    "MEDIUM_TERM: catalyst plays out over 1-6 months. "
                    "LONG_TERM: structural/fundamental story over 6+ months. "
                    "UNCLEAR: news does not indicate a clear time horizon."
                )
            },
            "data_quality": {
                "type": "string",
                "enum": ["HIGH", "MEDIUM", "LOW"],
                "description": (
                    "HIGH: 5+ relevant, recent, specific articles from credible sources. "
                    "MEDIUM: 2-4 articles or some articles are vague/old. "
                    "LOW: fewer than 2 relevant articles, or articles are generic/irrelevant."
                )
            },
            "insufficient_data": {
                "type": "boolean",
                "description": (
                    "Set true if news is too thin to support a reliable assessment. "
                    "When true, the memo writer will decline to generate a recommendation."
                )
            }
        },
        "required": [
            "ticker", "company", "overall_sentiment", "confidence",
            "primary_catalyst", "catalyst_date", "supporting_signals",
            "risk_flags", "time_horizon_signal", "data_quality", "insufficient_data"
        ]
    }
}


# ─────────────────────────────────────────────────────────────────
# PASS 1: NEWS ANALYST SUBAGENT
# ─────────────────────────────────────────────────────────────────

ANALYST_SYSTEM_PROMPT = """You are a senior equity research analyst at a top-tier investment fund.

YOUR SINGLE JOB IN THIS CALL:
Analyse the provided news headlines for one ticker and submit a structured assessment using the submit_news_assessment tool.

WHAT YOU ARE NOT DOING:
- You are not making a buy/sell recommendation (that happens in a separate step)
- You are not analysing technical indicators
- You are not writing prose — you are filling a structured schema

QUALITY STANDARDS — apply these strictly:

1. ONLY cite specific facts from the provided news. Never invent or infer beyond what is written.
2. If a field is nullable and the information is not present, return null. Do not fabricate plausible-sounding data.
3. Calibrate confidence honestly:
   - A single earnings beat headline = 0.55 confidence, not 0.85
   - Five consistent positive signals from credible sources = 0.80+
4. Flag data_quality as LOW and insufficient_data as true when fewer than 2 relevant articles exist.
5. Risk flags must reference specific articles, not generic sector risks.

FEW-SHOT EXAMPLES:

EXAMPLE A — Strong bullish signal (correct assessment):
News: Apple reports 15% revenue growth, beats EPS by $0.12. Tim Cook raises guidance for Q3. Analysts at Goldman raise PT from $180 to $210. Supply chain concerns resolved per CFO comments.
Correct: overall_sentiment=BULLISH, confidence=0.82, primary_catalyst="Q2 earnings beat with $0.12 EPS outperformance and raised Q3 guidance", supporting_signals=["Goldman Sachs PT upgrade to $210", "Supply chain resolution confirmed by CFO"], risk_flags=[]

EXAMPLE B — Thin news (correct assessment):
News: Apple releases new iPhone colour options. Steve Jobs memorial event held.
Correct: overall_sentiment=NEUTRAL, confidence=0.3, primary_catalyst=null, insufficient_data=true, data_quality=LOW
WRONG: overall_sentiment=BULLISH, confidence=0.6, primary_catalyst="New iPhone release signals product momentum"

EXAMPLE C — Mixed signals (correct assessment):
News: Tesla deliveries miss estimates by 8%. But Elon Musk announces new Gigafactory. Regulatory probe ongoing in Europe.
Correct: overall_sentiment=MIXED, confidence=0.45, risk_flags=["Delivery miss of 8% below consensus", "Ongoing European regulatory probe"], time_horizon_signal=UNCLEAR
WRONG: overall_sentiment=BEARISH, confidence=0.75 (ignores the Gigafactory positive)

Always call submit_news_assessment exactly once. Do not write any prose before or after."""


def run_news_analyst(ticker: str, company: str, news_raw: str) -> dict:
    """
    Pass 1: News Analyst subagent.
    Takes raw news text, returns structured assessment dict.
    Returns None if assessment fails quality gate.
    """
    user_message = f"""Analyse the following news for {company} ({ticker}) and submit your structured assessment.

NEWS HEADLINES:
{news_raw}

Remember: call submit_news_assessment exactly once with your complete assessment."""

    response = client.messages.create(
        model=MODEL,
        max_tokens=1000,
        system=ANALYST_SYSTEM_PROMPT,
        tools=[NEWS_ASSESSMENT_TOOL],
        tool_choice={"type": "tool", "name": "submit_news_assessment"},
        messages=[{"role": "user", "content": user_message}]
    )

    # Extract tool_use result
    for block in response.content:
        if block.type == "tool_use" and block.name == "submit_news_assessment":
            return block.input

    return None


# ─────────────────────────────────────────────────────────────────
# PASS 2: MEMO WRITER SUBAGENT
# ─────────────────────────────────────────────────────────────────

MEMO_SYSTEM_PROMPT = """You are a senior investment analyst writing a memo for a Managing Director at a top PE/VC fund.

YOUR JOB:
Write a concise, opinionated investment memo based on the structured news assessment provided.
This memo will be read by an investor who needs to decide whether to take a position TODAY.

MEMO FORMAT — follow this exactly:

---
INVESTMENT MEMO: {TICKER}
Date: {TODAY}
Analyst: AI Research Assistant
---

THESIS (1 sentence, opinionated)
State clearly whether this is a BUY, SELL, or PASS and the single most important reason why.

MARKET CATALYST
What specific event or development is driving this signal? When did it occur?
If the catalyst is older than 30 days, flag it as potentially stale.

NEWS EVIDENCE
List 2-3 specific supporting facts from the news. Be precise — cite dates and numbers.
Do not use vague language like "positive sentiment" or "market optimism".

RISK FACTORS
What could go wrong? List only risks that appear in the news, not generic sector risks.
If no risks are identified in the news, state: "No material risks identified in current news cycle."

CONVICTION LEVEL
State: HIGH / MEDIUM / LOW
Explain in one sentence why.

TIME HORIZON
State: SHORT-TERM (days-weeks) / MEDIUM-TERM (1-6 months) / LONG-TERM (6+ months)
Briefly explain what determines the timeline.

RECOMMENDATION
BUY / SELL / PASS — with one clear sentence of justification.
PASS is a valid and often correct recommendation. Do not force a BUY or SELL.

---

QUALITY STANDARDS:
1. Every claim must be traceable to the news assessment provided. Do not add external knowledge.
2. If conviction is LOW or data quality is LOW, the recommendation must be PASS.
3. Never recommend BUY or SELL with confidence below 0.6 in the assessment.
4. Be direct. Eliminate hedge words like "potentially", "may", "could suggest". Make a call.
5. The memo should take 60 seconds to read, not 5 minutes.

FEW-SHOT EXAMPLE — what a good memo looks like vs a bad one:

BAD (vague, unactionable):
"NVDA shows positive market sentiment with potential upside driven by AI trends. There may be opportunities for investors with appropriate risk tolerance. The company has been performing well recently."

GOOD (specific, opinionated):
"THESIS: BUY — Nvidia's data centre revenue grew 427% YoY in Q1 2024, dramatically exceeding consensus and establishing clear AI infrastructure dominance.
CATALYST: Q1 2024 earnings beat (reported 22 May 2024) — EPS of $5.98 vs $5.16 expected.
CONVICTION: HIGH — Multiple credible sources confirm the beat, guidance raised, and no material counter-signals in current news."
"""


def run_memo_writer(assessment: dict, today: str) -> str:
    """
    Pass 2: Memo Writer subagent.
    Takes structured assessment, returns full investment memo as string.
    """
    # Quality gate — refuse to write memo on thin data
    if assessment.get("insufficient_data") or assessment.get("data_quality") == "LOW":
        return f"""---
INVESTMENT MEMO: {assessment['ticker']}
Date: {today}
---

RECOMMENDATION: PASS

REASON: Insufficient news data to support a reliable investment thesis.
Data quality: {assessment.get('data_quality', 'LOW')}
Articles assessed: too few to draw conclusions.

Do not take a position based on this signal. Wait for a stronger catalyst or more news coverage.
---"""

    assessment_text = json.dumps(assessment, indent=2)

    user_message = f"""Write an investment memo based on the following structured news assessment.
Today's date: {today}

STRUCTURED ASSESSMENT:
{assessment_text}

Write the memo now, following the format and quality standards from your instructions."""

    response = client.messages.create(
        model=MODEL,
        max_tokens=1200,
        system=MEMO_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_message}]
    )

    return response.content[0].text


# ─────────────────────────────────────────────────────────────────
# COORDINATOR — called by main.py
# ─────────────────────────────────────────────────────────────────

def generate_memo(ticker: str, company: str, news_raw: str, today: str) -> dict:
    """
    Coordinator function. Runs both passes and returns a result dict.

    Returns:
      {
        "ticker": str,
        "company": str,
        "assessment": dict,     # Pass 1 output
        "memo": str,            # Pass 2 output — the full investment memo
        "recommendation": str,  # BUY / SELL / PASS
        "confidence": float,
        "error": str or None
      }
    """
    print(f"\n  [Pass 1] Running news analyst for {ticker}...")

    try:
        assessment = run_news_analyst(ticker, company, news_raw)
    except Exception as e:
        return {
            "ticker": ticker,
            "company": company,
            "assessment": None,
            "memo": None,
            "recommendation": "PASS",
            "confidence": 0.0,
            "error": f"Pass 1 failed: {str(e)}"
        }

    if not assessment:
        return {
            "ticker": ticker,
            "company": company,
            "assessment": None,
            "memo": None,
            "recommendation": "PASS",
            "confidence": 0.0,
            "error": "Pass 1 returned no assessment"
        }

    print(f"  [Pass 1] Complete — sentiment: {assessment.get('overall_sentiment')} | "
          f"confidence: {assessment.get('confidence')} | "
          f"data quality: {assessment.get('data_quality')}")

    print(f"  [Pass 2] Writing investment memo...")

    try:
        memo = run_memo_writer(assessment, today)
    except Exception as e:
        return {
            "ticker": ticker,
            "company": company,
            "assessment": assessment,
            "memo": None,
            "recommendation": "PASS",
            "confidence": assessment.get("confidence", 0.0),
            "error": f"Pass 2 failed: {str(e)}"
        }

    # Extract recommendation from memo
    recommendation = "PASS"
    memo_upper = memo.upper()
    if "RECOMMENDATION: BUY" in memo_upper:
        recommendation = "BUY"
    elif "RECOMMENDATION: SELL" in memo_upper:
        recommendation = "SELL"

    print(f"  [Pass 2] Complete — recommendation: {recommendation}")

    return {
        "ticker": ticker,
        "company": company,
        "assessment": assessment,
        "memo": memo,
        "recommendation": recommendation,
        "confidence": assessment.get("confidence", 0.0),
        "error": None
    }


# --- TEST ---
if __name__ == "__main__":
    from data_feed import fetch_news
    from datetime import date

    today = date.today().isoformat()

    test_ticker = "NVDA"
    print(f"Testing full memo pipeline for {test_ticker}...\n")

    news = fetch_news(test_ticker)
    if news["error"]:
        print(f"News fetch error: {news['error']}")
    else:
        result = generate_memo(
            ticker=test_ticker,
            company=news["company"],
            news_raw=news["raw_text"],
            today=today
        )

        print("\n" + "="*60)
        print(result["memo"])
        print("="*60)
        print(f"\nRecommendation: {result['recommendation']}")
        print(f"Confidence: {result['confidence']}")
        if result["error"]:
            print(f"Error: {result['error']}")
