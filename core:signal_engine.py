import pandas as pd
from settings import settings
from core.indicators import add_indicators
from core.patterns import detect_patterns

def evaluate_timeframe(df: pd.DataFrame) -> dict:
    df = add_indicators(df)
    if df.empty or len(df) < 30:
        return {
            "signal": "NEUTRAL", "score": 0.0, "confidence": 0.0,
            "price": 0.0, "rsi": 50.0, "adx": 0.0, "atr": 0.0,
            "patterns": [], "df": df,
        }

    row = df.iloc[-1]
    score = 0.0

    if row["Close"] > row["EMA_20"] > row["EMA_50"]:
        score += 40
    elif row["Close"] < row["EMA_20"] < row["EMA_50"]:
        score -= 40
    elif row["Close"] > row["EMA_20"]:
        score += 20
    else:
        score -= 20

    if 55 <= row["RSI"] <= 72:
        score += 25
    elif row["RSI"] > 72:
        score += 10
    elif 28 <= row["RSI"] <= 45:
        score -= 25
    elif row["RSI"] < 28:
        score -= 10

    score += 20 if row["MACD_HIST"] > 0 else -20

    patterns = detect_patterns(df)
    top_pat = patterns[0]
    if top_pat["bias"] == "BULLISH":
        score += 15
    elif top_pat["bias"] == "BEARISH":
        score -= 15

    adx_mult = 1.1 if row["ADX"] >= 25 else 0.9
    raw_conf = min(100.0, abs(score) * adx_mult)

    if score >= 35:
        signal = "STRONG BUY" if score >= 65 else "BUY"
    elif score <= -35:
        signal = "STRONG SELL" if score <= -65 else "SELL"
    else:
        signal = "NEUTRAL"

    return {
        "signal": signal, "score": round(score, 2),
        "confidence": round(raw_conf, 1), "price": round(float(row["Close"]), 2),
        "rsi": round(float(row["RSI"]), 1), "adx": round(float(row["ADX"]), 1),
        "atr": round(float(row["ATR"]), 2), "patterns": patterns, "df": df,
    }

def compute_master_and_risk(
    mtf_results: dict[str, dict], execution_tf: str,
    capital: float = settings.INITIAL_CAPITAL,
    risk_pct: float = settings.MAX_RISK_PER_TRADE_PCT,
) -> dict:
    weighted_score = 0.0
    total_weight = 0.0
    aligned_count = 0

    for tf_label, cfg in settings.TIMEFRAMES.items():
        res = mtf_results.get(tf_label)
        if not res or res["price"] == 0:
            continue
        w = cfg["weight"]
        weighted_score += res["score"] * w
        total_weight += w

    norm_score = (weighted_score / total_weight) if total_weight > 0 else 0.0

    if norm_score >= 55:
        master_signal = "STRONG BUY"
    elif norm_score >= 20:
        master_signal = "BUY"
    elif norm_score <= -55:
        master_signal = "STRONG SELL"
    elif norm_score <= -20:
        master_signal = "SELL"
    else:
        master_signal = "NEUTRAL"

    for res in mtf_results.values():
        if ("BUY" in master_signal and "BUY" in res["signal"]) or (
            "SELL" in master_signal and "SELL" in res["signal"]
        ):
            aligned_count += 1

    confluence_bonus = aligned_count * 4.0
    master_confidence = round(min(99.0, abs(norm_score) + confluence_bonus), 1)

    exec_data = mtf_results[execution_tf]
    entry = exec_data["price"]
    atr = max(exec_data["atr"], entry * 0.002)

    is_short = "SELL" in master_signal
    sl_mult = 1.5
    t1_mult, t2_mult, t3_mult = 1.5, 3.0, 4.5

    if is_short:
        stop_loss = round(entry + sl_mult * atr, 2)
        t1, t2, t3 = round(entry - t1_mult * atr, 2), round(entry - t2_mult * atr, 2), round(entry - t3_mult * atr, 2)
    else:
        stop_loss = round(entry - sl_mult * atr, 2)
        t1, t2, t3 = round(entry + t1_mult * atr, 2), round(entry + t2_mult * atr, 2), round(entry + t3_mult * atr, 2)

    risk_per_unit = max(abs(entry - stop_loss), 1e-6)
    max_risk_amount = capital * (risk_pct / 100.0)
    position_qty = int(max_risk_amount // risk_per_unit)
    position_value = round(position_qty * entry, 2)
    rr_ratio = round(abs(t2 - entry) / risk_per_unit, 2)

    return {
        "master_signal": master_signal, "master_score": round(norm_score, 2),
        "confidence_score": master_confidence, "timeframe_alignment": f"{aligned_count}/{len(mtf_results)}",
        "direction": "SHORT" if is_short else "LONG", "execution_tf": execution_tf,
        "entry": entry, "stop_loss": stop_loss,
        "target_1": t1, "target_2": t2, "target_3": t3, "atr": round(atr, 2),
        "risk_amount": round(max_risk_amount, 2), "position_qty": position_qty,
        "position_value": position_value, "risk_reward_t2": f"1:{rr_ratio}",
    }
