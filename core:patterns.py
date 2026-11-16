import pandas as pd

def detect_patterns(df: pd.DataFrame) -> list[dict]:
    if df.empty or len(df) < 25:
        return []

    patterns = []
    curr = df.iloc[-1]
    prev = df.iloc[-2]

    body_curr = abs(curr["Close"] - curr["Open"])
    range_curr = max(curr["High"] - curr["Low"], 1e-9)
    upper_wick = curr["High"] - max(curr["Open"], curr["Close"])
    lower_wick = min(curr["Open"], curr["Close"]) - curr["Low"]

    if body_curr / range_curr <= 0.1:
        patterns.append({"pattern": "Doji Indecision", "bias": "NEUTRAL", "strength": 50})

    if lower_wick >= 2 * body_curr and upper_wick <= 0.3 * body_curr and body_curr > 0:
        patterns.append({"pattern": "Bullish Hammer", "bias": "BULLISH", "strength": 72})

    if upper_wick >= 2 * body_curr and lower_wick <= 0.3 * body_curr and body_curr > 0:
        patterns.append({"pattern": "Bearish Shooting Star", "bias": "BEARISH", "strength": 72})

    if (prev["Close"] < prev["Open"] and curr["Close"] > curr["Open"] and
            curr["Open"] <= prev["Close"] and curr["Close"] >= prev["Open"]):
        patterns.append({"pattern": "Bullish Engulfing", "bias": "BULLISH", "strength": 82})

    if (prev["Close"] > prev["Open"] and curr["Close"] < curr["Open"] and
            curr["Open"] >= prev["Close"] and curr["Close"] <= prev["Open"]):
        patterns.append({"pattern": "Bearish Engulfing", "bias": "BEARISH", "strength": 82})

    recent_high = df["High"].iloc[-21:-1].max()
    recent_low = df["Low"].iloc[-21:-1].min()
    if curr["Close"] > recent_high:
        patterns.append({"pattern": "20-Bar Range Breakout", "bias": "BULLISH", "strength": 85})
    elif curr["Close"] < recent_low:
        patterns.append({"pattern": "20-Bar Range Breakdown", "bias": "BEARISH", "strength": 85})

    if not patterns:
        patterns.append({"pattern": "Consolidation / No Major Pattern", "bias": "NEUTRAL", "strength": 40})

    return patterns
