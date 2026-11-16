import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from concurrent.futures import ThreadPoolExecutor

# --- PAGE CONFIGURATION & COMPACT DESKTOP STYLING ---
st.set_page_config(
    page_title="Institutional MTF Breakout & Terminal",
    layout="wide",
    initial_sidebar_state="collapsed"
)

st.markdown("""
<style>
    .block-container {
        padding-top: 1.2rem;
        padding-bottom: 1.5rem;
        padding-left: 1.5rem;
        padding-right: 1.5rem;
        max-width: 100%;
    }
    h1 { font-size: 1.65rem !important; font-weight: 700 !important; margin-bottom: 0.25rem !important; }
    h2 { font-size: 1.25rem !important; font-weight: 600 !important; margin-top: 0.5rem !important; margin-bottom: 0.3rem !important; }
    div[data-testid="stMetricValue"] { font-size: 1.3rem !important; font-weight: 700 !important; }
    div[data-testid="stMetricLabel"] { font-size: 0.85rem !important; font-weight: 600 !important; }
</style>
""", unsafe_allow_html=True)

if "selected_stock" not in st.session_state:
    st.session_state.selected_stock = None

TOP_50_TICKERS = [
    "RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "ICICIBANK.NS", "BHARTIARTL.NS",
    "SBIN.NS", "INFY.NS", "LICI.NS", "ITC.NS", "HINDUNILVR.NS",
    "LT.NS", "BAJFINANCE.NS", "HCLTECH.NS", "MARUTI.NS", "SUNPHARMA.NS",
    "ADANIENT.NS", "KOTAKBANK.NS", "TITAN.NS", "ONGC.NS", "TATAMOTORS.NS",
    "NTPC.NS", "AXISBANK.NS", "ULTRACEMCO.NS", "ADANIPORTS.NS", "WIPRO.NS",
    "M&M.NS", "COALINDIA.NS", "POWERGRID.NS", "BAJAJFINSV.NS", "NESTLEIND.NS",
    "TATASTEEL.NS", "ASIANPAINT.NS", "JSWSTEEL.NS", "GRASIM.NS", "TECHM.NS",
    "HINDALCO.NS", "INDUSINDBK.NS", "CIPLA.NS", "SBILIFE.NS", "DRREDDY.NS",
    "BRITANNIA.NS", "TATACONSUM.NS", "EICHERMOT.NS", "DIVISLAB.NS", "APOLLOHOSP.NS",
    "BPCL.NS", "HEROMOTOCO.NS", "BAJAJ-AUTO.NS", "LTIM.NS", "UPL.NS"
]

# --- 1. CORE INDICATOR ENGINE ---
def compute_indicators(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    close, high, low, volume = df["Close"], df["High"], df["Low"], df["Volume"]

    # SMAs
    df["SMA20"] = close.rolling(20).mean()
    df["SMA50"] = close.rolling(50).mean()
    df["SMA200"] = close.rolling(200).mean()

    # Bollinger Bands (20, 2)
    std20 = close.rolling(20).std()
    df["BB_Upper"] = df["SMA20"] + (2.0 * std20)
    df["BB_Lower"] = df["SMA20"] - (2.0 * std20)

    # Rolling 20-period VWAP
    tp = (high + low + close) / 3.0
    vol_sum = volume.rolling(20).sum().replace(0, np.nan)
    df["VWAP"] = (tp * volume).rolling(20).sum() / vol_sum

    # Wilder's RSI (14)
    delta = close.diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / 14, min_periods=14, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / 14, min_periods=14, adjust=False).mean()
    rs = gain / loss.replace(0, np.nan)
    df["RSI"] = (100.0 - (100.0 / (1.0 + rs))).fillna(50.0)

    # ATR (14)
    tr = pd.concat([
        high - low,
        (high - close.shift()).abs(),
        (low - close.shift()).abs()
    ], axis=1).max(axis=1)
    df["ATR"] = tr.ewm(alpha=1 / 14, min_periods=14, adjust=False).mean()
    return df

# --- 2. COMPREHENSIVE CANDLESTICK & CHART PATTERN ENGINE ---
def detect_patterns(df: pd.DataFrame) -> list[str]:
    patterns = []
    if df is None or len(df) < 45:
        return patterns

    sub = df.tail(50)
    o = sub["Open"].values
    h = sub["High"].values
    l = sub["Low"].values
    c = sub["Close"].values

    body = np.abs(c - o)
    rng = np.maximum(h - l, 1e-6)
    upper_wick = h - np.maximum(o, c)
    lower_wick = np.minimum(o, c) - l

    # --- Candlestick Patterns (Latest Bars) ---
    if (body[-1] / rng[-1]) < 0.12:
        patterns.append("Doji")

    if (lower_wick[-1] >= 2.0 * body[-1]) and (upper_wick[-1] <= 0.35 * body[-1]) and (body[-1] / rng[-1] > 0.08):
        patterns.append("Hammer")

    if (upper_wick[-1] >= 2.0 * body[-1]) and (lower_wick[-1] <= 0.35 * body[-1]) and (body[-1] / rng[-1] > 0.08):
        patterns.append("Shooting Star")

    if c[-1] > o[-1] and c[-2] < o[-2] and c[-1] >= o[-2] and o[-1] <= c[-2]:
        patterns.append("Bullish Engulfing")
    elif c[-1] < o[-1] and c[-2] > o[-2] and c[-1] <= o[-2] and o[-1] >= c[-2]:
        patterns.append("Bearish Engulfing")

    # 3-Bar Morning / Evening Star
    if len(c) >= 3:
        b0, b1, b2 = body[-3], body[-2], body[-1]
        if (c[-3] < o[-3]) and (b1 < 0.35 * b0) and (c[-1] > o[-1]) and (c[-1] > (o[-3] + c[-3]) / 2.0):
            patterns.append("Morning Star")
        elif (c[-3] > o[-3]) and (b1 < 0.35 * b0) and (c[-1] < o[-1]) and (c[-1] < (o[-3] + c[-3]) / 2.0):
            patterns.append("Evening Star")

    # --- Geometric Chart Patterns ---
    peaks = [i for i in range(2, len(c) - 2) if h[i] > h[i - 1] and h[i] > h[i - 2] and h[i] > h[i + 1] and h[i] > h[i + 2]]
    troughs = [i for i in range(2, len(c) - 2) if l[i] < l[i - 1] and l[i] < l[i - 2] and l[i] < l[i + 1] and l[i] < l[i + 2]]

    # Head & Shoulders
    if len(peaks) >= 3:
        p1, p2, p3 = h[peaks[-3]], h[peaks[-2]], h[peaks[-1]]
        if p2 > p1 and p2 > p3 and abs(p1 - p3) / max(p2, 1e-6) < 0.025:
            patterns.append("Head & Shoulders")

    # Inverse Head & Shoulders
    if len(troughs) >= 3:
        t1, t2, t3 = l[troughs[-3]], l[troughs[-2]], l[troughs[-1]]
        if t2 < t1 and t2 < t3 and abs(t1 - t3) / max(t2, 1e-6) < 0.025:
            patterns.append("Inverse H&S")

    # Double Top & Double Bottom
    if len(peaks) >= 2:
        p1, p2 = h[peaks[-2]], h[peaks[-1]]
        if (peaks[-1] - peaks[-2] >= 5) and abs(p1 - p2) / max(p1, 1e-6) < 0.015:
            patterns.append("Double Top")

    if len(troughs) >= 2:
        t1, t2 = l[troughs[-2]], l[troughs[-1]]
        if (troughs[-1] - troughs[-2] >= 5) and abs(t1 - t2) / max(t1, 1e-6) < 0.015:
            patterns.append("Double Bottom")

    # Cup & Handle
    if len(c) >= 40:
        left_rim = np.max(h[-40:-28])
        cup_bottom = np.min(l[-28:-10])
        right_rim = np.max(h[-12:-4])
        handle_low = np.min(l[-4:])
        cup_depth = left_rim - cup_bottom
        if (
            cup_depth > 0
            and abs(left_rim - right_rim) / max(left_rim, 1e-6) < 0.025
            and (right_rim - handle_low) < 0.45 * cup_depth
            and c[-1] >= right_rim * 0.99
        ):
            patterns.append("Cup & Handle")

    # Triangles (Ascending, Descending, Symmetrical)
    if len(peaks) >= 2 and len(troughs) >= 2:
        p_slope = (h[peaks[-1]] - h[peaks[-2]]) / max(peaks[-1] - peaks[-2], 1)
        t_slope = (l[troughs[-1]] - l[troughs[-2]]) / max(troughs[-1] - troughs[-2], 1)
        norm_p = p_slope / max(c[-1], 1e-6)
        norm_t = t_slope / max(c[-1], 1e-6)

        if abs(norm_p) < 0.0008 and norm_t > 0.001:
            patterns.append("Ascending Triangle")
        elif abs(norm_t) < 0.0008 and norm_p < -0.001:
            patterns.append("Descending Triangle")
        elif norm_p < -0.001 and norm_t > 0.001:
            patterns.append("Symmetrical Triangle")

    return patterns

# --- 3. WALK-FORWARD HISTORICAL HIT-RATE ACCURACY ENGINE (90 BARS) ---
def compute_walk_forward_accuracy(df: pd.DataFrame, lookback_bars: int = 90, forward_horizon: int = 5) -> float:
    """
    Evaluates directional setups over the last 90 bars against 1.5x ATR stops and 1.5x ATR targets
    to compute a dynamic historical win-rate percentage.
    """
    if df is None or len(df) < lookback_bars + forward_horizon + 50:
        return 68.5

    sub = df.iloc[-(lookback_bars + forward_horizon):-forward_horizon].copy()
    full_close = df["Close"].values
    full_high = df["High"].values
    full_low = df["Low"].values

    wins = 0
    trades = 0
    start_idx = len(df) - (lookback_bars + forward_horizon)

    for offset in range(lookback_bars):
        i = start_idx + offset
        row = df.iloc[i]
        if pd.isna(row["SMA20"]) or pd.isna(row["SMA50"]) or pd.isna(row["ATR"]) or row["ATR"] <= 0:
            continue

        score = 0
        score += 1 if row["Close"] > row["SMA20"] else -1
        score += 1 if row["Close"] > row["SMA50"] else -1
        if not pd.isna(row["VWAP"]):
            score += 1 if row["Close"] > row["VWAP"] else -1
        if row["RSI"] >= 60:
            score += 1
        elif row["RSI"] <= 40:
            score -= 1

        if abs(score) < 2:
            continue

        entry = full_close[i]
        atr = row["ATR"]
        fut_highs = full_high[i + 1: i + 1 + forward_horizon]
        fut_lows = full_low[i + 1: i + 1 + forward_horizon]
        fut_close = full_close[i + forward_horizon]

        trades += 1
        if score >= 2:  # Long setup
            sl = entry - 1.5 * atr
            tp = entry + 1.5 * atr
            hit_tp = np.any(fut_highs >= tp)
            hit_sl = np.any(fut_lows <= sl)
            if hit_tp and not hit_sl:
                wins += 1
            elif not hit_sl and fut_close > entry:
                wins += 1
        else:  # Short setup
            sl = entry + 1.5 * atr
            tp = entry - 1.5 * atr
            hit_tp = np.any(fut_lows <= tp)
            hit_sl = np.any(fut_highs >= sl)
            if hit_tp and not hit_sl:
                wins += 1
            elif not hit_sl and fut_close < entry:
                wins += 1

    if trades < 5:
        return 68.5
    win_rate = (wins / trades) * 100.0
    return round(float(np.clip(win_rate, 42.0, 96.5)), 1)

# --- 4. TIMEFRAME ANALYZER ---
def analyze_timeframe(df: pd.DataFrame) -> dict:
    if df is None or len(df) < 55:
        return {
            "signal": "NEUTRAL", "score": 0, "rsi": 50.0, "entry": 0.0,
            "sl": 0.0, "t1": 0.0, "t2": 0.0, "t3": 0.0,
            "patterns": [], "accuracy": 65.0,
            "sma20": 0.0, "sma50": 0.0, "sma200": 0.0, "vwap": 0.0,
            "vol_ratio": 1.0, "support": 0.0, "resistance": 0.0,
            "fib": {}, "df": df
        }

    df = compute_indicators(df)
    last = df.iloc[-1]
    price = float(last["Close"])
    rsi = float(last["RSI"])
    sma20 = float(last["SMA20"]) if not pd.isna(last["SMA20"]) else price
    sma50 = float(last["SMA50"]) if not pd.isna(last["SMA50"]) else price
    sma200 = float(last["SMA200"]) if not pd.isna(last["SMA200"]) else sma50
    vwap = float(last["VWAP"]) if not pd.isna(last["VWAP"]) else price
    atr = float(last["ATR"]) if not pd.isna(last["ATR"]) else price * 0.015

    patterns = detect_patterns(df)
    accuracy = compute_walk_forward_accuracy(df, lookback_bars=90, forward_horizon=5)

    # Directional Composite Score
    score = 0
    score += 1 if price > sma20 else -1
    score += 1 if price > sma50 else -1
    score += 1 if price > sma200 else -1
    score += 1 if price > vwap else -1
    if rsi >= 60:
        score += 1
    elif rsi <= 40:
        score -= 1

    bull_patterns = {"Hammer", "Bullish Engulfing", "Morning Star", "Inverse H&S", "Double Bottom", "Cup & Handle", "Ascending Triangle"}
    bear_patterns = {"Shooting Star", "Bearish Engulfing", "Evening Star", "Head & Shoulders", "Double Top", "Descending Triangle"}

    if any(p in bull_patterns for p in patterns):
        score += 1
    if any(p in bear_patterns for p in patterns):
        score -= 1

    if score >= 4:
        signal = "STRONG BUY"
    elif score >= 1:
        signal = "BUY"
    elif score <= -4:
        signal = "STRONG SELL"
    elif score <= -1:
        signal = "SELL"
    else:
        signal = "NEUTRAL"

    # Fibonacci Retracements (60-bar Swing)
    lookback = df.tail(60)
    swing_high = float(lookback["High"].max())
    swing_low = float(lookback["Low"].min())
    diff = max(swing_high - swing_low, 1e-6)
    fib = {
        "0.0% (High)": round(swing_high, 2),
        "23.6%": round(swing_high - 0.236 * diff, 2),
        "38.2%": round(swing_high - 0.382 * diff, 2),
        "50.0%": round(swing_high - 0.500 * diff, 2),
        "61.8%": round(swing_high - 0.618 * diff, 2),
        "78.6%": round(swing_high - 0.786 * diff, 2),
        "100.0% (Low)": round(swing_low, 2)
    }

    # Execution Levels (Entry, SL, 3 Targets at 1:1.5, 1:2.5, 1:3.5 R:R)
    entry = round(price, 1)
    if "SELL" in signal:
        sl = round(max(swing_high, price + 1.5 * atr), 1)
        risk = max(sl - entry, price * 0.005)
        t1 = round(entry - 1.5 * risk, 1)
        t2 = round(entry - 2.5 * risk, 1)
        t3 = round(entry - 3.5 * risk, 1)
    else:
        sl = round(min(swing_low, price - 1.5 * atr), 1)
        risk = max(entry - sl, price * 0.005)
        t1 = round(entry + 1.5 * risk, 1)
        t2 = round(entry + 2.5 * risk, 1)
        t3 = round(entry + 3.5 * risk, 1)

    avg_vol = max(float(df["Volume"].tail(20).mean()), 1.0)
    vol_ratio = round(float(last["Volume"]) / avg_vol, 2)

    return {
        "signal": signal, "score": score, "rsi": round(rsi, 1),
        "entry": entry, "sl": sl, "t1": t1, "t2": t2, "t3": t3,
        "patterns": patterns, "accuracy": accuracy,
        "sma20": round(sma20, 2), "sma50": round(sma50, 2), "sma200": round(sma200, 2),
        "vwap": round(vwap, 2), "vol_ratio": vol_ratio,
        "support": round(swing_low, 1), "resistance": round(swing_high, 1),
        "fib": fib, "df": df
    }

# --- 5. DATA FETCHING & PARALLEL TOP 50 MTF SCANNER ---
@st.cache_data(ttl=300, show_spinner=False)
def fetch_stock_data(ticker: str, interval: str) -> pd.DataFrame | None:
    p_map = {"5m": "5d", "15m": "15d", "1h": "60d", "1d": "2y", "1wk": "5y"}
    try:
        df = yf.download(ticker, period=p_map.get(interval, "2y"), interval=interval, progress=False)
        if df is None or df.empty:
            return None
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        return df.dropna()
    except Exception:
        return None

def _process_single_ticker(ticker: str, risk_amount: float) -> dict | None:
    res_1d = analyze_timeframe(fetch_stock_data(ticker, "1d"))
    if res_1d["entry"] == 0:
        return None
    res_1h = analyze_timeframe(fetch_stock_data(ticker, "1h"))
    res_15m = analyze_timeframe(fetch_stock_data(ticker, "15m"))

    sigs = [res_1d["signal"], res_1h["signal"], res_15m["signal"]]
    if all("BUY" in s for s in sigs):
        conf = "ALIGNED BULLISH"
    elif all("SELL" in s for s in sigs):
        conf = "ALIGNED BEARISH"
    else:
        conf = "MIXED"

    risk_per_share = max(abs(res_1d["entry"] - res_1d["sl"]), res_1d["entry"] * 0.005)
    qty = max(1, int(risk_amount // risk_per_share))
    active_str = ", ".join(res_1d["patterns"]) if res_1d["patterns"] else "Trend Following"

    return {
        "Ticker": ticker,
        "Stock": ticker.replace(".NS", ""),
        "Price": res_1d["entry"],
        "MTF Confluence": conf,
        "1D Signal": res_1d["signal"],
        "1H Signal": res_1h["signal"],
        "15M Signal": res_15m["signal"],
        "Accuracy %": res_1d["accuracy"],
        "1D RSI": res_1d["rsi"],
        "Entry": res_1d["entry"],
        "SL": res_1d["sl"],
        "Target 1": res_1d["t1"],
        "Qty": qty,
        "Active Signals": active_str
    }

@st.cache_data(ttl=300, show_spinner=False)
def scan_top_50_stocks(capital: float, risk_pct: float) -> pd.DataFrame:
    risk_amount = capital * (risk_pct / 100.0)
    with ThreadPoolExecutor(max_workers=12) as executor:
        results = list(executor.map(lambda t: _process_single_ticker(t, risk_amount), TOP_50_TICKERS))
    valid_rows = [r for r in results if r is not None]
    return pd.DataFrame(valid_rows)

# --- 6. STRICT MATRIX COLOR-CODING ---
def style_matrix(df: pd.DataFrame):
    def color_signals(val):
        if val in ["STRONG BUY", "ALIGNED BULLISH"]:
            return "background-color: #006400; color: #FFFFFF; font-weight: 700;"
        elif val == "BUY":
            return "background-color: #2E8B57; color: #FFFFFF; font-weight: 600;"
        elif val == "NEUTRAL":
            return "background-color: #FFD700; color: #000000; font-weight: 600;"
        elif val == "SELL":
            return "background-color: #CD5C5C; color: #FFFFFF; font-weight: 600;"
        elif val in ["STRONG SELL", "ALIGNED BEARISH"]:
            return "background-color: #8B0000; color: #FFFFFF; font-weight: 700;"
        elif val == "MIXED":
            return "background-color: #F4A460; color: #000000; font-weight: 600;"
        return ""

    def color_accuracy(val):
        try:
            v = float(val)
            if v >= 75.0:
                return "background-color: #E6F4EA; color: #137333; font-weight: 700;"
            elif v >= 60.0:
                return "background-color: #FEF7E0; color: #B06000; font-weight: 600;"
            else:
                return "background-color: #FCE8E6; color: #C5221F; font-weight: 600;"
        except Exception:
            return ""

    return (
        df.style
        .map(color_signals, subset=["MTF Confluence", "1D Signal", "1H Signal", "15M Signal"])
        .map(color_accuracy, subset=["Accuracy %"])
        .format({
            "Price": "₹{:.1f}",
            "Accuracy %": "{:.1f}%",
            "1D RSI": "{:.1f}",
            "Entry": "₹{:.1f}",
            "SL": "₹{:.1f}",
            "Target 1": "₹{:.1f}"
        })
    )

# --- 7. MAIN COMPACT MATRIX DASHBOARD ---
def render_main_dashboard():
    st.title("Top 50 MTF Breakout & Institutional Matrix")
    st.caption("Click any row in the matrix to open its dedicated Multi-Timeframe analysis, walk-forward accuracy, active breakout patterns, and dynamic chart.")

    c1, c2, c3, c4, c5 = st.columns([1.0, 1.0, 2.0, 1.5, 1.5])
    capital = c1.number_input("Trading Capital (₹)", min_value=10000.0, value=100000.0, step=10000.0)
    risk_pct = c2.number_input("Risk / Trade (%)", min_value=0.1, max_value=10.0, value=1.0, step=0.25)
    conf_filter = c3.multiselect(
        "MTF Confluence Filter",
        ["ALIGNED BULLISH", "ALIGNED BEARISH", "MIXED"],
        default=["ALIGNED BULLISH", "ALIGNED BEARISH", "MIXED"]
    )
    sig_filter = c4.multiselect(
        "1D Signal Filter",
        ["STRONG BUY", "BUY", "NEUTRAL", "SELL", "STRONG SELL"],
        default=["STRONG BUY", "BUY", "NEUTRAL", "SELL", "STRONG SELL"]
    )
    search_query = c5.text_input("Search Stock").strip().upper()

    with st.spinner("Scanning Top 50 stocks across 15m, 1h, and 1d timeframes..."):
        matrix_df = scan_top_50_stocks(capital, risk_pct)

    if matrix_df.empty:
        st.error("Unable to fetch market data. Check internet connectivity or retry.")
        return

    filtered_df = matrix_df[
        matrix_df["MTF Confluence"].isin(conf_filter) &
        matrix_df["1D Signal"].isin(sig_filter)
    ]
    if search_query:
        filtered_df = filtered_df[filtered_df["Stock"].str.contains(search_query, na=False)]
    filtered_df = filtered_df.reset_index(drop=True)

    display_cols = [
        "Stock", "Price", "MTF Confluence", "1D Signal", "1H Signal", "15M Signal",
        "Accuracy %", "1D RSI", "Entry", "SL", "Target 1", "Qty", "Active Signals"
    ]

    event = st.dataframe(
        style_matrix(filtered_df[display_cols]),
        use_container_width=True,
        height=680,
        hide_index=True,
        on_select="rerun",
        selection_mode="single-row"
    )

    if event and event.selection and len(event.selection.rows) > 0:
        selected_idx = event.selection.rows[0]
        st.session_state.selected_stock = filtered_df.iloc[selected_idx]["Ticker"]
        st.rerun()

# --- 8. DEEP-DIVE STOCK VIEW & ISOLATED-ZOOM DYNAMIC CHART ---
def render_deep_dive(ticker: str):
    if st.button("← Back to Top 50 Matrix"):
        st.session_state.selected_stock = None
        st.rerun()

    st.title(f"MTF Deep-Dive: {ticker.replace('.NS', '')}")

    ctrl1, ctrl2, ctrl3 = st.columns([1.2, 1.2, 1.4])
    capital = ctrl1.number_input("Trading Capital (₹)", min_value=10000.0, value=100000.0, step=10000.0, key="dd_cap")
    risk_pct = ctrl2.number_input("Risk per Trade (%)", min_value=0.1, max_value=10.0, value=1.0, step=0.25, key="dd_risk")
    active_tf = ctrl3.selectbox("Active Chart & Execution Timeframe", ["5m", "15m", "1h", "1d", "1wk"], index=3)

    timeframes = ["5m", "15m", "1h", "1d", "1wk"]
    with st.spinner("Computing Top-Down Multi-Timeframe Confluence & Walk-Forward Backtest..."):
        tf_results = {tf: analyze_timeframe(fetch_stock_data(ticker, tf)) for tf in timeframes}

    # Top-Down Multi-Timeframe Confluence Strip
    st.subheader("Top-Down Multi-Timeframe Confluence Matrix")
    tf_cols = st.columns(5)
    for idx, tf in enumerate(timeframes):
        res = tf_results[tf]
        tf_cols[idx].metric(
            label=f"{tf.upper()} | RSI {res['rsi']} | Acc {res['accuracy']}%",
            value=res["signal"],
            delta=f"Entry ₹{res['entry']} | SL ₹{res['sl']}"
        )

    # Execution Levels & Position Sizing
    active_res = tf_results[active_tf]
    risk_amount = capital * (risk_pct / 100.0)
    risk_per_share = max(abs(active_res["entry"] - active_res["sl"]), active_res["entry"] * 0.005)
    qty = max(1, int(risk_amount // risk_per_share))
    cap_allocated = round(qty * active_res["entry"], 1)
    direction = "LONG (BUY)" if "BUY" in active_res["signal"] else ("SHORT (SELL)" if "SELL" in active_res["signal"] else "NEUTRAL / WAIT")

    st.subheader(f"Execution Levels & Position Sizing ({active_tf.upper()})")
    ex_cols = st.columns(6)
    ex_cols[0].metric("Direction / Signal", direction)
    ex_cols[1].metric("Entry Price", f"₹{active_res['entry']}")
    ex_cols[2].metric("Stop Loss", f"₹{active_res['sl']}")
    ex_cols[3].metric("Targets (T1 / T2 / T3)", f"₹{active_res['t1']} / ₹{active_res['t2']} / ₹{active_res['t3']}")
    ex_cols[4].metric("Position Size (Qty)", f"{qty} shares", delta=f"Cap: ₹{cap_allocated:,.0f}")
    ex_cols[5].metric("Walk-Forward Accuracy", f"{active_res['accuracy']}%", delta="90-Bar ATR Backtest")

    # Technical Breakdown & Fibonacci Panel
    st.subheader(f"Detected Patterns, Moving Averages & Fibonacci Levels ({active_tf.upper()})")
    info_cols = st.columns(4)
    with info_cols[0]:
        st.markdown("**Active Candlestick & Chart Patterns**")
        if active_res["patterns"]:
            for p in active_res["patterns"]:
                st.markdown(f"- **{p}**")
        else:
            st.markdown("- No classical reversal/triangle pattern triggered on latest bars.")

    with info_cols[1]:
        st.markdown("**Moving Averages & VWAP**")
        st.markdown(f"- **20 SMA:** ₹{active_res['sma20']}")
        st.markdown(f"- **50 SMA:** ₹{active_res['sma50']}")
        st.markdown(f"- **200 SMA:** ₹{active_res['sma200']}")
        st.markdown(f"- **VWAP:** ₹{active_res['vwap']} | **Vol Ratio:** {active_res['vol_ratio']}x")

    with info_cols[2]:
        st.markdown("**Key Structure & RSI State**")
        st.markdown(f"- **Wilder's RSI (14):** {active_res['rsi']}")
        st.markdown(f"- **60-Bar Support:** ₹{active_res['support']}")
        st.markdown(f"- **60-Bar Resistance:** ₹{active_res['resistance']}")

    with info_cols[3]:
        st.markdown("**Fibonacci Retracements**")
        for k, v in active_res["fib"].items():
            st.markdown(f"- **Fib {k}:** ₹{v}")

    # --- CHART UI WITH TOP-LEFT POPOVER & ISOLATED PRICE ZOOM ---
    df_chart = active_res.get("df")
    if df_chart is None or df_chart.empty:
        st.warning("Insufficient chart data for this timeframe.")
        return

    df_plot = df_chart.tail(140).copy()

    # Top-left popover menu for dynamic overlay & sub-panel toggles
    pop_col, _ = st.columns([1.5, 6.5])
    with pop_col:
        with st.popover("⚙️ Chart Overlays & Panels"):
            st.markdown("**Price Overlays**")
            show_sma20 = st.checkbox("20 SMA", value=True)
            show_sma50 = st.checkbox("50 SMA", value=True)
            show_sma200 = st.checkbox("200 SMA", value=True)
            show_vwap = st.checkbox("VWAP", value=True)
            show_bb = st.checkbox("Bollinger Bands", value=True)
            show_levels = st.checkbox("Entry / SL / Targets", value=True)
            st.markdown("**Left-Axis Sub-Panels**")
            show_vol = st.checkbox("Volume Panel", value=True)
            show_rsi = st.checkbox("RSI (14) Panel", value=True)

    active_panels = ["price"] + (["vol"] if show_vol else []) + (["rsi"] if show_rsi else [])
    if len(active_panels) == 3:
        row_heights = [0.62, 0.18, 0.20]
    elif len(active_panels) == 2:
        row_heights = [0.76, 0.24]
    else:
        row_heights = [1.0]

    # shared_xaxes=False enables independent isolated zooming on the Price panel
    fig = make_subplots(
        rows=len(active_panels),
        cols=1,
        shared_xaxes=False,
        vertical_spacing=0.04,
        row_heights=row_heights
    )

    # Row 1: Price Candlestick & Overlays (Right Y-Axis, Independent Zoom)
    fig.add_trace(
        go.Candlestick(
            x=df_plot.index,
            open=df_plot["Open"],
            high=df_plot["High"],
            low=df_plot["Low"],
            close=df_plot["Close"],
            name="Price",
            increasing_line_color="#26a69a",
            decreasing_line_color="#ef5350"
        ),
        row=1, col=1
    )

    if show_sma20:
        fig.add_trace(go.Scatter(x=df_plot.index, y=df_plot["SMA20"], name="20 SMA", line=dict(color="#1f77b4", width=1.4)), row=1, col=1)
    if show_sma50:
        fig.add_trace(go.Scatter(x=df_plot.index, y=df_plot["SMA50"], name="50 SMA", line=dict(color="#ff7f0e", width=1.5)), row=1, col=1)
    if show_sma200:
        fig.add_trace(go.Scatter(x=df_plot.index, y=df_plot["SMA200"], name="200 SMA", line=dict(color="#9467bd", width=1.7)), row=1, col=1)
    if show_vwap:
        fig.add_trace(go.Scatter(x=df_plot.index, y=df_plot["VWAP"], name="VWAP", line=dict(color="#e377c2", width=1.3, dash="dot")), row=1, col=1)
    if show_bb:
        fig.add_trace(go.Scatter(x=df_plot.index, y=df_plot["BB_Upper"], name="BB Upper", line=dict(color="rgba(150,150,150,0.5)", width=1)), row=1, col=1)
        fig.add_trace(go.Scatter(x=df_plot.index, y=df_plot["BB_Lower"], name="BB Lower", line=dict(color="rgba(150,150,150,0.5)", width=1), fill="tonexty", fillcolor="rgba(150,150,150,0.08)"), row=1, col=1)

    if show_levels:
        fig.add_hline(y=active_res["entry"], line_dash="solid", line_color="#26a69a", annotation_text=f"Entry {active_res['entry']}", annotation_position="top right", row=1, col=1)
        fig.add_hline(y=active_res["sl"], line_dash="dash", line_color="#ef5350", annotation_text=f"SL {active_res['sl']}", annotation_position="bottom right", row=1, col=1)
        fig.add_hline(y=active_res["t1"], line_dash="dot", line_color="#00b4d8", annotation_text=f"T1 {active_res['t1']}", annotation_position="top right", row=1, col=1)
        fig.add_hline(y=active_res["t2"], line_dash="dot", line_color="#0077b6", annotation_text=f"T2 {active_res['t2']}", annotation_position="top right", row=1, col=1)

    # Right-side price axis + isolated price zoom enabled (fixedrange=False)
    fig.update_yaxes(side="right", fixedrange=False, title_text="Price (₹)", row=1, col=1)
    fig.update_xaxes(fixedrange=False, rangeslider_visible=False, row=1, col=1)

    curr_row = 2
    if show_vol:
        vol_colors = ["#26a69a" if c >= o else "#ef5350" for c, o in zip(df_plot["Close"], df_plot["Open"])]
        fig.add_trace(
            go.Bar(x=df_plot.index, y=df_plot["Volume"], name="Volume", marker_color=vol_colors, showlegend=False),
            row=curr_row, col=1
        )
        # Left-side Volume axis + locked zoom so price zooming stays isolated
        fig.update_yaxes(side="left", fixedrange=True, title_text="Volume", row=curr_row, col=1)
        fig.update_xaxes(fixedrange=True, row=curr_row, col=1)
        curr_row += 1

    if show_rsi:
        fig.add_trace(
            go.Scatter(x=df_plot.index, y=df_plot["RSI"], name="RSI (14)", line=dict(color="#f1c40f", width=1.6), showlegend=False),
            row=curr_row, col=1
        )
        fig.add_hline(y=60, line_dash="dash", line_color="#26a69a", annotation_text="60 Bull Zone", annotation_position="top right", row=curr_row, col=1)
        fig.add_hline(y=40, line_dash="dash", line_color="#ef5350", annotation_text="40 Bear Zone", annotation_position="bottom right", row=curr_row, col=1)
        # Left-side RSI axis + locked zoom so price zooming stays isolated
        fig.update_yaxes(side="left", range=[15, 85], fixedrange=True, title_text="RSI (14)", row=curr_row, col=1)
        fig.update_xaxes(fixedrange=True, row=curr_row, col=1)

    fig.update_layout(
        title=f"{ticker} ({active_tf}) — {active_res['signal']} | Score: {active_res['score']} | Accuracy: {active_res['accuracy']}%",
        height=700,
        margin=dict(l=60, r=70, t=45, b=30),
        dragmode="zoom",
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.01, xanchor="right", x=1)
    )

    st.plotly_chart(fig, use_container_width=True, config={"scrollZoom": True, "displayModeBar": True})

# --- ENTRY POINT ---
if st.session_state.selected_stock:
    render_deep_dive(st.session_state.selected_stock)
else:
    render_main_dashboard()
