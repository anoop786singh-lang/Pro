import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import plotly.graph_objects as go
from plotly.subplots import make_subplots

st.set_page_config(page_title="MTF Institutional Trading Terminal", layout="wide")

# --- CONFIGURATION ---
TOP_50_TICKERS = [
    "RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "ICICIBANK.NS", "BHARTIARTL.NS",
    "SBIN.NS", "INFY.NS", "LICI.NS", "ITC.NS", "HINDUNILVR.NS",
    "LT.NS", "BAJFINANCE.NS", "HCLTECH.NS", "MARUTI.NS", "SUNPHARMA.NS",
    "ADANIENT.NS", "KOTAKBANK.NS", "TITAN.NS", "ONGC.NS", "TATAMOTORS.NS",
    "NTPC.NS", "AXISBANK.NS", "ULTRACEMCO.NS", "ADANIPORTS.NS", "ASIANPAINT.NS",
    "COALINDIA.NS", "BAJAJFINSV.NS", "DMART.NS", "POWERGRID.NS", "NESTLEIND.NS",
    "WIPRO.NS", "M&M.NS", "IOC.NS", "JIOFIN.NS", "HAL.NS",
    "DLF.NS", "IRFC.NS", "VBL.NS", "ZOMATO.NS", "TRENT.NS",
    "BEL.NS", "SIEMENS.NS", "PIDILITIND.NS", "GRASIM.NS", "TECHM.NS",
    "HINDALCO.NS", "INDIGO.NS", "DIVISLAB.NS", "DRREDDY.NS", "CIPLA.NS"
]

TIMEFRAMES = {
    "5m":  {"interval": "5m",  "period": "5d",  "swing": 5,  "atr_mult": 1.2},
    "15m": {"interval": "15m", "period": "15d", "swing": 6,  "atr_mult": 1.5},
    "1h":  {"interval": "60m", "period": "60d", "swing": 8,  "atr_mult": 1.8},
    "1d":  {"interval": "1d",  "period": "1y",  "swing": 10, "atr_mult": 2.0},
    "1wk": {"interval": "1wk", "period": "3y",  "swing": 10, "atr_mult": 2.5},
}

# --- SESSION STATE ---
if "selected_stock" not in st.session_state:
    st.session_state.selected_stock = None
if "capital" not in st.session_state:
    st.session_state.capital = 100000.0
if "risk_pct" not in st.session_state:
    st.session_state.risk_pct = 1.0


# --- DATA FETCHING ---
@st.cache_data(ttl=300, show_spinner=False)
def fetch_ohlcv(ticker: str, tf_key: str) -> pd.DataFrame:
    cfg = TIMEFRAMES[tf_key]
    df = yf.download(ticker, period=cfg["period"], interval=cfg["interval"], progress=False, auto_adjust=True)
    if df is None or df.empty:
        return pd.DataFrame()
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df = df[["Open", "High", "Low", "Close", "Volume"]].dropna()
    return df


# --- TECHNICAL INDICATORS ---
def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    # SMAs
    df["SMA20"] = df["Close"].rolling(20).mean()
    df["SMA50"] = df["Close"].rolling(50).mean()

    # Bollinger Bands (20, 2)
    bb_std = df["Close"].rolling(20).std()
    df["BB_MID"] = df["SMA20"]
    df["BB_UPPER"] = df["BB_MID"] + 2 * bb_std
    df["BB_LOWER"] = df["BB_MID"] - 2 * bb_std

    # RSI (14) - Wilder's Smoothing
    delta = df["Close"].diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / 14, min_periods=14, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / 14, min_periods=14, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    df["RSI"] = 100 - (100 / (1 + rs))

    # ATR (14)
    prev_close = df["Close"].shift(1)
    tr = pd.concat([
        df["High"] - df["Low"],
        (df["High"] - prev_close).abs(),
        (df["Low"] - prev_close).abs()
    ], axis=1).max(axis=1)
    df["ATR"] = tr.ewm(alpha=1 / 14, min_periods=14, adjust=False).mean()

    # Volume SMA
    df["VOL_SMA20"] = df["Volume"].rolling(20).mean()

    # VWAP (session-grouped for intraday, rolling 20-bar anchor for daily/weekly)
    tp = (df["High"] + df["Low"] + df["Close"]) / 3.0
    if isinstance(df.index, pd.DatetimeIndex) and df.index.inferred_freq in (None, "T", "H"):
        session = df.index.date
        df["VWAP"] = (tp * df["Volume"]).groupby(session).cumsum() / df["Volume"].groupby(session).cumsum()
    else:
        df["VWAP"] = (tp * df["Volume"]).rolling(20).sum() / df["Volume"].rolling(20).sum()

    return df


# --- RSI ZONE & DIVERGENCE ENGINE ---
def detect_rsi_signals(df: pd.DataFrame, lookback: int = 15) -> list[dict]:
    signals = []
    if len(df) < lookback + 5 or df["RSI"].isna().all():
        return signals

    rsi = df["RSI"].values
    close = df["Close"].values
    opn = df["Open"].values

    r_now, r_prev = rsi[-1], rsi[-2]
    r_recent = rsi[-lookback:]
    r_min, r_max = np.nanmin(r_recent), np.nanmax(r_recent)
    is_green = close[-1] > opn[-1]
    is_red = close[-1] < opn[-1]

    # 1. Bullish Zone: Support at ~40 heading toward 60 (STRONG BUY)
    if r_min <= 42 and (38 <= r_prev <= 45) and r_now > r_prev and r_now < 60 and is_green:
        signals.append({
            "name": "RSI 40 Zone Support -> 60 Target",
            "bias": "BULLISH",
            "tag": "STRONG BUY",
            "detail": f"RSI bounced off 40 support ({r_min:.1f} -> {r_now:.1f}) with green candle"
        })

    # 2. Bullish Breakout: Crossed 60, retested ~60 as support, moving up
    if r_max > 62 and np.any((r_recent[-6:-1] >= 58) & (r_recent[-6:-1] <= 63)) and r_now > 61 and r_now > r_prev:
        signals.append({
            "name": "RSI 60 Breakout & Retest Support",
            "bias": "BULLISH",
            "tag": "BUY BREAKOUT",
            "detail": f"RSI broke 60, held ~60 support, resuming upside ({r_now:.1f})"
        })

    # 3. Bearish Zone: Dropped from 70, broke 60, retested ~60 resistance toward 40
    if r_max >= 68 and np.any((r_recent[-6:-1] >= 57) & (r_recent[-6:-1] <= 62)) and r_now < 59 and r_now < r_prev and is_red:
        signals.append({
            "name": "RSI 60 Breakdown & Resistance Rejection",
            "bias": "BEARISH",
            "tag": "SELL",
            "detail": f"RSI fell from 70+, rejected at 60 resistance toward 40 ({r_now:.1f})"
        })

    # 4. Bearish Breakdown: Dropped from 60, broke 40, retested ~40 resistance toward 30
    if r_max >= 55 and r_min < 40 and np.any((r_recent[-6:-1] >= 38) & (r_recent[-6:-1] <= 43)) and r_now < 39 and r_now < r_prev:
        signals.append({
            "name": "RSI 40 Breakdown & Resistance Rejection",
            "bias": "BEARISH",
            "tag": "STRONG SELL",
            "detail": f"RSI broke 40, rejected at 40 resistance toward 30 ({r_now:.1f})"
        })

    # 5. RSI Divergence (Price vs RSI pivot comparison)
    half = lookback // 2
    p_low1, p_low2 = np.min(close[-lookback:-half]), np.min(close[-half:])
    r_low1, r_low2 = np.nanmin(rsi[-lookback:-half]), np.nanmin(rsi[-half:])
    if p_low2 < p_low1 and r_low2 > r_low1 + 2:
        signals.append({
            "name": "Bullish RSI Divergence",
            "bias": "BULLISH",
            "tag": "REVERSAL",
            "detail": f"Lower price low ({p_low2:.2f} < {p_low1:.2f}) with higher RSI low ({r_low2:.1f} > {r_low1:.1f})"
        })

    p_high1, p_high2 = np.max(close[-lookback:-half]), np.max(close[-half:])
    r_high1, r_high2 = np.nanmax(rsi[-lookback:-half]), np.nanmax(rsi[-half:])
    if p_high2 > p_high1 and r_high2 < r_high1 - 2:
        signals.append({
            "name": "Bearish RSI Divergence",
            "bias": "BEARISH",
            "tag": "REVERSAL",
            "detail": f"Higher price high ({p_high2:.2f} > {p_high1:.2f}) with lower RSI high ({r_high2:.1f} < {r_high1:.1f})"
        })

    return signals


# --- CANDLESTICK PATTERN DETECTOR ---
def detect_candlesticks(df: pd.DataFrame) -> list[dict]:
    patterns = []
    if len(df) < 5:
        return patterns

    o, h, l, c = df["Open"].values, df["High"].values, df["Low"].values, df["Close"].values
    body = np.abs(c - o)
    rng = np.maximum(h - l, 1e-6)
    upper_wick = h - np.maximum(o, c)
    lower_wick = np.minimum(o, c) - l

    # Latest candle metrics
    b0, r0, uw0, lw0 = body[-1], rng[-1], upper_wick[-1], lower_wick[-1]
    bull0, bear0 = c[-1] > o[-1], c[-1] < o[-1]
    bull1, bear1 = c[-2] > o[-2], c[-2] < o[-2]

    # Doji
    if b0 / r0 <= 0.10:
        patterns.append({"name": "Doji", "bias": "NEUTRAL", "detail": "Indecision / potential inflection candle"})

    # Hammer (Bullish reversal after downtrend)
    if lw0 >= 2.0 * b0 and uw0 <= 0.25 * b0 and c[-1] < df["SMA20"].iloc[-1]:
        patterns.append({"name": "Hammer", "bias": "BULLISH", "detail": "Long lower wick rejection at support"})

    # Shooting Star (Bearish reversal after uptrend)
    if uw0 >= 2.0 * b0 and lw0 <= 0.25 * b0 and c[-1] > df["SMA20"].iloc[-1]:
        patterns.append({"name": "Shooting Star", "bias": "BEARISH", "detail": "Long upper wick rejection at resistance"})

    # Bullish / Bearish Engulfing
    if bear1 and bull0 and o[-1] <= c[-2] and c[-1] >= o[-2] and b0 > body[-2]:
        patterns.append({"name": "Bullish Engulfing", "bias": "BULLISH", "detail": "Strong green body engulfed prior red candle"})
    if bull1 and bear0 and o[-1] >= c[-2] and c[-1] <= o[-2] and b0 > body[-2]:
        patterns.append({"name": "Bearish Engulfing", "bias": "BEARISH", "detail": "Strong red body engulfed prior green candle"})

    # Bullish / Bearish Marubozu (Breakout momentum candle)
    if b0 / r0 >= 0.85 and r0 > df["ATR"].iloc[-1]:
        if bull0:
            patterns.append({"name": "Bullish Marubozu", "bias": "BULLISH", "detail": "Full-bodied momentum breakout candle"})
        elif bear0:
            patterns.append({"name": "Bearish Marubozu", "bias": "BEARISH", "detail": "Full-bodied momentum breakdown candle"})

    # Three White Soldiers
    if all(c[-i] > o[-i] and body[-i] / rng[-i] > 0.6 for i in (1, 2, 3)) and (c[-1] > c[-2] > c[-3]):
        patterns.append({"name": "Three White Soldiers", "bias": "BULLISH", "detail": "3 consecutive strong bullish breakout candles"})

    # Three Black Crows
    if all(c[-i] < o[-i] and body[-i] / rng[-i] > 0.6 for i in (1, 2, 3)) and (c[-1] < c[-2] < c[-3]):
        patterns.append({"name": "Three Black Crows", "bias": "BEARISH", "detail": "3 consecutive strong bearish breakdown candles"})

    return patterns


# --- CHART PATTERN DETECTOR ---
def detect_chart_patterns(df: pd.DataFrame, window: int = 30) -> list[dict]:
    patterns = []
    if len(df) < window + 5:
        return patterns

    sub = df.iloc[-window:]
    highs = sub["High"].values
    lows = sub["Low"].values
    close = sub["Close"].values
    x = np.arange(len(sub))

    # Linear regression slopes on rolling upper/lower halves to approximate trendlines
    half = window // 2
    h1, h2 = np.max(highs[:half]), np.max(highs[half:])
    l1, l2 = np.min(lows[:half]), np.min(lows[half:])
    tol = 0.012 * close[-1]

    flat_top = abs(h2 - h1) <= tol
    flat_bot = abs(l2 - l1) <= tol
    rising_bot = l2 > l1 + tol
    falling_top = h2 < h1 - tol

    # Triangles
    if flat_top and rising_bot:
        status = "BREAKOUT" if close[-1] > max(h1, h2) else "FORMING"
        patterns.append({"name": f"Ascending Triangle ({status})", "bias": "BULLISH", "detail": f"Flat resistance ~{max(h1,h2):.2f} with higher lows"})
    elif flat_bot and falling_top:
        status = "BREAKDOWN" if close[-1] < min(l1, l2) else "FORMING"
        patterns.append({"name": f"Descending Triangle ({status})", "bias": "BEARISH", "detail": f"Flat support ~{min(l1,l2):.2f} with lower highs"})
    elif falling_top and rising_bot:
        bias = "BULLISH" if close[-1] > h2 else ("BEARISH" if close[-1] < l2 else "NEUTRAL")
        patterns.append({"name": "Symmetrical Triangle", "bias": bias, "detail": "Converging trendlines coiling for breakout"})

    # Double Top / Double Bottom
    if flat_top and close[-1] < np.min(lows[half // 2: -2]):
        patterns.append({"name": "Double Top Breakdown", "bias": "BEARISH", "detail": f"Twin peaks near {max(h1,h2):.2f} with neckline break"})
    if flat_bot and close[-1] > np.max(highs[half // 2: -2]):
        patterns.append({"name": "Double Bottom Breakout", "bias": "BULLISH", "detail": f"Twin bottoms near {min(l1,l2):.2f} with neckline break"})

    # Cup & Handle approximation
    mid_low = np.min(lows[window // 4: 3 * window // 4])
    handle_low = np.min(lows[-5:])
    if flat_top and mid_low < min(h1, h2) - 2.5 * tol and handle_low > (mid_low + max(h1, h2)) / 2 and close[-1] >= max(h1, h2) * 0.995:
        patterns.append({"name": "Cup & Handle", "bias": "BULLISH", "detail": f"Rounded base with shallow handle near {max(h1,h2):.2f}"})

    # Head & Shoulders / Inverse H&S
    thirds = np.array_split(np.arange(window), 3)
    p_peaks = [np.max(highs[idx]) for idx in thirds]
    p_troughs = [np.min(lows[idx]) for idx in thirds]
    if p_peaks[1] > p_peaks[0] + tol and p_peaks[1] > p_peaks[2] + tol and abs(p_peaks[0] - p_peaks[2]) <= tol * 1.5:
        patterns.append({"name": "Head & Shoulders", "bias": "BEARISH", "detail": f"Head at {p_peaks[1]:.2f}, shoulders ~{p_peaks[0]:.2f}"})
    if p_troughs[1] < p_troughs[0] - tol and p_troughs[1] < p_troughs[2] - tol and abs(p_troughs[0] - p_troughs[2]) <= tol * 1.5:
        patterns.append({"name": "Inverse Head & Shoulders", "bias": "BULLISH", "detail": f"Head at {p_troughs[1]:.2f}, shoulders ~{p_troughs[0]:.2f}"})

    return patterns


# --- LEVELS, FIBONACCI, TRADE SETUP & POSITION SIZING ---
def compute_tf_analysis(df: pd.DataFrame, tf_key: str, capital: float, risk_pct: float) -> dict:
    cfg = TIMEFRAMES[tf_key]
    df = add_indicators(df)
    last = df.iloc[-1]
    price = float(last["Close"])
    atr = float(last["ATR"]) if not np.isnan(last["ATR"]) else price * 0.015
    swing = cfg["swing"]

    # Swing High/Low for S/R & Fibonacci
    lookback_df = df.iloc[-max(swing * 4, 30):]
    swing_high = float(lookback_df["High"].max())
    swing_low = float(lookback_df["Low"].min())
    fib_diff = max(swing_high - swing_low, 1e-6)
    fibs = {
        "0.0% (High)": round(swing_high, 2),
        "23.6%": round(swing_high - 0.236 * fib_diff, 2),
        "38.2%": round(swing_high - 0.382 * fib_diff, 2),
        "50.0%": round(swing_high - 0.500 * fib_diff, 2),
        "61.8%": round(swing_high - 0.618 * fib_diff, 2),
        "100.0% (Low)": round(swing_low, 2),
    }

    rsi_sigs = detect_rsi_signals(df, lookback=swing * 2)
    candles = detect_candlesticks(df)
    chart_pats = detect_chart_patterns(df, window=swing * 3)

    # Composite Bias Scoring
    score = 0
    if price > last["SMA20"]: score += 1
    else: score -= 1
    if last["SMA20"] > last["SMA50"]: score += 1
    else: score -= 1
    if price > last["VWAP"]: score += 1
    else: score -= 1
    if last["Volume"] > last["VOL_SMA20"]:
        score += 1 if last["Close"] > last["Open"] else -1

    for item in rsi_sigs + candles + chart_pats:
        if item["bias"] == "BULLISH": score += 2
        elif item["bias"] == "BEARISH": score -= 2

    if score >= 3:
        signal = "STRONG BUY" if score >= 5 else "BUY"
        direction = "LONG"
    elif score <= -3:
        signal = "STRONG SELL" if score <= -5 else "SELL"
        direction = "SHORT"
    else:
        signal = "NEUTRAL"
        direction = "LONG" if score >= 0 else "SHORT"

    # Accurate Timeframe-Specific Entry, SL, Targets & Position Sizing
    recent_low = float(df["Low"].iloc[-swing:].min())
    recent_high = float(df["High"].iloc[-swing:].max())
    buffer = cfg["atr_mult"] * atr

    if direction == "LONG":
        entry = round(price, 2)
        sl = round(min(recent_low, price - buffer), 2)
        if sl >= entry:
            sl = round(entry - buffer, 2)
        risk_per_share = max(entry - sl, 0.05)
        t1 = round(entry + 2.0 * risk_per_share, 2)
        t2 = round(entry + 3.0 * risk_per_share, 2)
    else:
        entry = round(price, 2)
        sl = round(max(recent_high, price + buffer), 2)
        if sl <= entry:
            sl = round(entry + buffer, 2)
        risk_per_share = max(sl - entry, 0.05)
        t1 = round(entry - 2.0 * risk_per_share, 2)
        t2 = round(entry - 3.0 * risk_per_share, 2)

    risk_amount = capital * (risk_pct / 100.0)
    qty = int(risk_amount // risk_per_share)
    position_value = round(qty * entry, 2)

    return {
        "df": df,
        "timeframe": tf_key,
        "price": round(price, 2),
        "rsi": round(float(last["RSI"]), 1) if not np.isnan(last["RSI"]) else 50.0,
        "sma20": round(float(last["SMA20"]), 2) if not np.isnan(last["SMA20"]) else price,
        "sma50": round(float(last["SMA50"]), 2) if not np.isnan(last["SMA50"]) else price,
        "vwap": round(float(last["VWAP"]), 2) if not np.isnan(last["VWAP"]) else price,
        "vol_ratio": round(float(last["Volume"] / last["VOL_SMA20"]), 2) if last["VOL_SMA20"] > 0 else 1.0,
        "support": round(recent_low, 2),
        "resistance": round(recent_high, 2),
        "fibs": fibs,
        "score": score,
        "signal": signal,
        "direction": direction,
        "entry": entry,
        "sl": sl,
        "t1": t1,
        "t2": t2,
        "rr": "1:2 / 1:3",
        "qty": qty,
        "risk_amount": round(risk_amount, 2),
        "position_value": position_value,
        "rsi_signals": rsi_sigs,
        "candles": candles,
        "chart_patterns": chart_pats,
    }


@st.cache_data(ttl=300, show_spinner=False)
def scan_top_50(capital: float, risk_pct: float) -> pd.DataFrame:
    rows = []
    for ticker in TOP_50_TICKERS:
        try:
            df_1d = fetch_ohlcv(ticker, "1d")
            df_1h = fetch_ohlcv(ticker, "1h")
            df_15m = fetch_ohlcv(ticker, "15m")
            if df_1d.empty or df_1h.empty or df_15m.empty:
                continue

            a_1d = compute_tf_analysis(df_1d, "1d", capital, risk_pct)
            a_1h = compute_tf_analysis(df_1h, "1h", capital, risk_pct)
            a_15m = compute_tf_analysis(df_15m, "15m", capital, risk_pct)

            active_patterns = [
                p["name"] for p in (a_1d["chart_patterns"] + a_1d["candles"] + a_1d["rsi_signals"])
            ]
            mtf_align = (
                "ALIGNED BULLISH" if all("BUY" in x["signal"] for x in (a_1d, a_1h, a_15m))
                else "ALIGNED BEARISH" if all("SELL" in x["signal"] for x in (a_1d, a_1h, a_15m))
                else "MIXED"
            )

            rows.append({
                "Stock": ticker.replace(".NS", ""),
                "Ticker": ticker,
                "Price": a_1d["price"],
                "MTF Confluence": mtf_align,
                "1D Signal": a_1d["signal"],
                "1H Signal": a_1h["signal"],
                "15M Signal": a_15m["signal"],
                "1D RSI": a_1d["rsi"],
                "Entry": a_1d["entry"],
                "SL": a_1d["sl"],
                "Target 1": a_1d["t1"],
                "Qty": a_1d["qty"],
                "Active Signals": ", ".join(active_patterns[:3]) if active_patterns else "Trend Following",
            })
        except Exception:
            continue
    return pd.DataFrame(rows)


# --- DYNAMIC PLOTLY CHART ---
def render_dynamic_chart(analysis: dict, ticker: str):
    df = analysis["df"].iloc[-100:]
    fig = make_subplots(
        rows=3, cols=1, shared_xaxes=True,
        vertical_spacing=0.03, row_heights=[0.62, 0.18, 0.20]
    )

    # Candlesticks
    fig.add_trace(go.Candlestick(
        x=df.index, open=df["Open"], high=df["High"], low=df["Low"], close=df["Close"], name="Price"
    ), row=1, col=1)

    # SMAs, VWAP & Bollinger Bands
    fig.add_trace(go.Scatter(x=df.index, y=df["SMA20"], line=dict(color="#2962FF", width=1.4), name="20 SMA"), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df["SMA50"], line=dict(color="#FF6D00", width=1.4), name="50 SMA"), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df["VWAP"], line=dict(color="#AA00FF", width=1.2, dash="dot"), name="VWAP"), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df["BB_UPPER"], line=dict(color="rgba(150,150,150,0.4)", width=1), name="BB Upper"), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df["BB_LOWER"], line=dict(color="rgba(150,150,150,0.4)", width=1), fill="tonexty", fillcolor="rgba(150,150,150,0.08)", name="BB Lower"), row=1, col=1)

    # Trade Levels (Entry, SL, T1, T2)
    fig.add_hline(y=analysis["entry"], line_dash="solid", line_color="#00E676", annotation_text=f"Entry {analysis['entry']}", row=1, col=1)
    fig.add_hline(y=analysis["sl"], line_dash="dash", line_color="#FF1744", annotation_text=f"SL {analysis['sl']}", row=1, col=1)
    fig.add_hline(y=analysis["t1"], line_dash="dot", line_color="#00B0FF", annotation_text=f"T1 {analysis['t1']}", row=1, col=1)
    fig.add_hline(y=analysis["t2"], line_dash="dot", line_color="#1DE9B6", annotation_text=f"T2 {analysis['t2']}", row=1, col=1)

    # Volume
    vol_colors = ["#26a69a" if c >= o else "#ef5350" for c, o in zip(df["Close"], df["Open"])]
    fig.add_trace(go.Bar(x=df.index, y=df["Volume"], marker_color=vol_colors, name="Volume"), row=2, col=1)

    # RSI + 40/60 Zone Lines
    fig.add_trace(go.Scatter(x=df.index, y=df["RSI"], line=dict(color="#FFD600", width=1.6), name="RSI (14)"), row=3, col=1)
    fig.add_hline(y=60, line_dash="dash", line_color="#00E676", annotation_text="60 Bull Zone", row=3, col=1)
    fig.add_hline(y=40, line_dash="dash", line_color="#FF1744", annotation_text="40 Bear Zone", row=3, col=1)

    fig.update_layout(
        height=720, template="plotly_dark", xaxis_rangeslider_visible=False,
        title=f"{ticker} ({analysis['timeframe']}) — {analysis['signal']} | Score: {analysis['score']}",
        margin=dict(l=10, r=10, t=45, b=10)
    )
    st.plotly_chart(fig, use_container_width=True)


# --- VIEW 2: DEDICATED STOCK DETAIL VIEW ---
def render_stock_detail_view(ticker: str):
    if st.button("← Back to Top 50 Matrix"):
        st.session_state.selected_stock = None
        st.rerun()

    st.title(f"MTF Deep-Dive: {ticker.replace('.NS', '')}")

    # Position Sizing Controls
    c_cap, c_risk, c_tf = st.columns([1, 1, 1])
    with c_cap:
        st.session_state.capital = st.number_input("Trading Capital (₹)", min_value=10000.0, value=st.session_state.capital, step=10000.0)
    with c_risk:
        st.session_state.risk_pct = st.number_input("Risk per Trade (%)", min_value=0.25, max_value=5.0, value=st.session_state.risk_pct, step=0.25)
    with c_tf:
        active_tf = st.selectbox("Active Chart & Execution Timeframe", list(TIMEFRAMES.keys()), index=3)

    # Compute MTF across all 5 timeframes
    mtf_results = {}
    for tf in TIMEFRAMES:
        df_tf = fetch_ohlcv(ticker, tf)
        if not df_tf.empty:
            mtf_results[tf] = compute_tf_analysis(df_tf, tf, st.session_state.capital, st.session_state.risk_pct)

    if active_tf not in mtf_results:
        st.error(f"Insufficient market data for {ticker} on {active_tf}.")
        return

    # 1. MTF Alignment Strip
    st.subheader("Multi-Timeframe Confluence Matrix")
    cols = st.columns(len(mtf_results))
    for idx, (tf, res) in enumerate(mtf_results.items()):
        with cols[idx]:
            st.metric(
                label=f"{tf.upper()} | RSI {res['rsi']}",
                value=res["signal"],
                delta=f"Entry {res['entry']} | SL {res['sl']}"
            )

    cur = mtf_results[active_tf]

    # 2. Execution & Position Sizing Card
    st.subheader(f"Execution Levels & Position Sizing ({active_tf.upper()})")
    m1, m2, m3, m4, m5, m6 = st.columns(6)
    m1.metric("Direction / Signal", f"{cur['direction']} ({cur['signal']})")
    m2.metric("Entry Price", f"₹{cur['entry']}")
    m3.metric("Stop Loss", f"₹{cur['sl']}")
    m4.metric("Targets (1:2 / 1:3)", f"₹{cur['t1']} / ₹{cur['t2']}")
    m5.metric("Position Size (Qty)", f"{cur['qty']} shares")
    m6.metric("Capital Allocated", f"₹{cur['position_value']:,.0f}")

    # 3. Active Patterns & Breakout Drivers
    st.subheader(f"Active Breakout Patterns, Candlesticks & RSI Zone Signals ({active_tf.upper()})")
    p_col1, p_col2, p_col3, p_col4 = st.columns(4)

    with p_col1:
        st.markdown("**Chart Patterns**")
        if cur["chart_patterns"]:
            for p in cur["chart_patterns"]:
                st.info(f"**{p['name']}** [{p['bias']}]\n\n{p['detail']}")
        else:
            st.caption("No classical chart pattern triggered on this timeframe.")

    with p_col2:
        st.markdown("**Breakout Candlesticks**")
        if cur["candles"]:
            for c in cur["candles"]:
                st.success(f"**{c['name']}** [{c['bias']}]\n\n{c['detail']}")
        else:
            st.caption("No high-momentum candlestick pattern on latest bar.")

    with p_col3:
        st.markdown("**RSI Zone & Divergence**")
        if cur["rsi_signals"]:
            for r in cur["rsi_signals"]:
                st.warning(f"**{r['name']}** ({r['tag']})\n\n{r['detail']}")
        else:
            st.caption(f"RSI at {cur['rsi']} — No 40/60 zone rejection or divergence.")

    with p_col4:
        st.markdown("**Key Levels & Fibonacci**")
        st.write(f"- **20 SMA / 50 SMA:** {cur['sma20']} / {cur['sma50']}")
        st.write(f"- **VWAP:** {cur['vwap']} | **Vol Ratio:** {cur['vol_ratio']}x")
        st.write(f"- **Support / Resistance:** {cur['support']} / {cur['resistance']}")
        for k, v in cur["fibs"].items():
            st.caption(f"Fib {k}: {v}")

    # 4. Interactive Chart
    render_dynamic_chart(cur, ticker)


# --- VIEW 1: MAIN TOP 50 MATRIX DASHBOARD ---
def render_main_dashboard():
    st.title("Top 50 MTF Breakout & Institutional Matrix")
    st.caption("Click any row in the matrix to open its dedicated Multi-Timeframe analysis, active breakout patterns, and dynamic chart.")

    with st.spinner("Scanning Top 50 stocks across 15m, 1h, and 1d timeframes..."):
        matrix_df = scan_top_50(st.session_state.capital, st.session_state.risk_pct)

    if matrix_df.empty:
        st.warning("Unable to load market data right now.")
        return

    display_df = matrix_df.drop(columns=["Ticker"])
    event = st.dataframe(
        display_df,
        use_container_width=True,
        hide_index=True,
        on_select="rerun",
        selection_mode="single-row",
        height=680
    )

    if event and event.selection and event.selection.rows:
        row_idx = event.selection.rows[0]
        st.session_state.selected_stock = matrix_df.iloc[row_idx]["Ticker"]
        st.rerun()


# --- ROUTER ---
if st.session_state.selected_stock:
    render_stock_detail_view(st.session_state.selected_stock)
else:
    render_main_dashboard()
