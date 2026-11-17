import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from streamlit_autorefresh import st_autorefresh
from datetime import datetime

# --- PAGE CONFIG ---
st.set_page_config(
    page_title="Nifty 200 Live Matrix Scanner",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- AUTO REFRESH EVERY 10 SECONDS ---
st_autorefresh(interval=10000, key="nifty200_live_refresh")

# --- SYMBOLS LIST ---
NIFTY_200_SYMBOLS = [
    "RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "ICICIBANK.NS", "BHARTIARTL.NS",
    "SBIN.NS", "INFY.NS", "LICI.NS", "ITC.NS", "HINDUNILVR.NS",
    "LT.NS", "BAJFINANCE.NS", "HCLTECH.NS", "MARUTI.NS", "SUNPHARMA.NS",
    "ADANIENT.NS", "KOTAKBANK.NS", "TITAN.NS", "ONGC.NS", "TATAMOTORS.NS"
]

def compute_indicators(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    close = df["Close"]
    high = df["High"]
    low = df["Low"]
    open_p = df["Open"]
    vol = df["Volume"]

    delta = close.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)
    avg_gain = gain.ewm(alpha=1/14, min_periods=14, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/14, min_periods=14, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    df["RSI"] = 100 - (100 / (1 + rs))

    df["SMA20"] = close.rolling(window=20).mean()
    std20 = close.rolling(window=20).std()
    df["BB_Upper"] = df["SMA20"] + (2 * std20)
    df["BB_Lower"] = df["SMA20"] - (2 * std20)

    df["Vol_SMA20"] = vol.rolling(window=20).mean()
    df["Vol_Ratio"] = vol / df["Vol_SMA20"].replace(0, np.nan)

    tr1 = high - low
    tr2 = (high - close.shift()).abs()
    tr3 = (low - close.shift()).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    df["ATR"] = tr.rolling(window=14).mean()

    df["Swing_High"] = high.rolling(window=20).max()
    df["Swing_Low"] = low.rolling(window=20).min()

    return df

def detect_candlestick_pattern(df: pd.DataFrame) -> tuple[str, int]:
    if len(df) < 3:
        return "None", 0
    c = df.iloc[-1]
    p = df.iloc[-2]

    body = abs(c["Close"] - c["Open"])
    rng = max(c["High"] - c["Low"], 1e-6)
    upper_wick = c["High"] - max(c["Open"], c["Close"])
    lower_wick = min(c["Open"], c["Close"]) - c["Low"]
    p_body = abs(p["Close"] - p["Open"])

    if (p["Close"] < p["Open"]) and (c["Close"] > c["Open"]) and (c["Open"] <= p["Close"]) and (c["Close"] >= p["Open"]) and (body > p_body):
        return "Bullish Engulfing", 1
    if (p["Close"] > p["Open"]) and (c["Close"] < c["Open"]) and (c["Open"] >= p["Close"]) and (c["Close"] <= p["Open"]) and (body > p_body):
        return "Bearish Engulfing", -1
    if (lower_wick >= 2 * body) and (upper_wick <= 0.3 * body) and (body / rng > 0.1):
        return "Hammer", 1
    if (upper_wick >= 2 * body) and (lower_wick <= 0.3 * body) and (body / rng > 0.1):
        return "Shooting Star", -1
    if body <= 0.1 * rng:
        return "Doji", 0

    return "Standard", 0

def analyze_stock(symbol: str, df: pd.DataFrame) -> dict | None:
    if df is None or len(df) < 25:
        return None
    df = compute_indicators(df)
    last = df.iloc[-1]

    if pd.isna(last["RSI"]) or pd.isna(last["BB_Upper"]) or pd.isna(last["ATR"]):
        return None

    price = float(last["Close"])
    rsi = float(last["RSI"])
    bb_up = float(last["BB_Upper"])
    bb_low = float(last["BB_Lower"])
    sma20 = float(last["SMA20"])
    vol_ratio = float(last["Vol_Ratio"]) if not pd.isna(last["Vol_Ratio"]) else 1.0
    atr = float(last["ATR"])
    swing_high = float(last["Swing_High"])
    swing_low = float(last["Swing_Low"])

    pattern_name, pattern_bias = detect_candlestick_pattern(df)

    if price <= swing_low * 1.005:
        structure = "Near Bottom"
    elif price >= swing_high * 0.995:
        structure = "Near Top"
    else:
        structure = "Mid-Range"

    bull_points = 0
    bear_points = 0

    if rsi < 30: bull_points += 30
    elif rsi < 40: bull_points += 20
    elif rsi > 70: bear_points += 30
    elif rsi > 60: bear_points += 20

    if price <= bb_low: bull_points += 25
    elif price < sma20: bull_points += 10
    elif price >= bb_up: bear_points += 25
    elif price > sma20: bear_points += 10

    if vol_ratio >= 1.5:
        bull_points += 20; bear_points += 20
    elif vol_ratio >= 1.1:
        bull_points += 10; bear_points += 10

    if pattern_bias == 1: bull_points += 15
    elif pattern_bias == -1: bear_points += 15

    if structure == "Near Bottom": bull_points += 10
    elif structure == "Near Top": bear_points += 10

    if bull_points >= bear_points:
        accuracy = min(98, max(35, bull_points))
        signal = "STRONG BUY" if accuracy >= 70 else ("BUY" if accuracy >= 55 else "NEUTRAL")
        entry = round(price, 2)
        sl = round(max(swing_low - 0.5 * atr, entry - 1.5 * atr), 2)
        risk = max(entry - sl, atr * 0.5)
        t1 = round(entry + 1.0 * risk, 2)
        t2 = round(entry + 2.0 * risk, 2)
        t3 = round(entry + 3.0 * risk, 2)
    else:
        accuracy = min(98, max(35, bear_points))
        signal = "STRONG SELL" if accuracy >= 70 else ("SELL" if accuracy >= 55 else "NEUTRAL")
        entry = round(price, 2)
        sl = round(min(swing_high + 0.5 * atr, entry + 1.5 * atr), 2)
        risk = max(sl - entry, atr * 0.5)
        t1 = round(entry - 1.0 * risk, 2)
        t2 = round(entry - 2.0 * risk, 2)
        t3 = round(entry - 3.0 * risk, 2)

    return {
        "Symbol": symbol.replace(".NS", ""),
        "Full_Symbol": symbol,
        "LTP": round(price, 2),
        "Signal": signal,
        "Accuracy %": int(accuracy),
        "Entry": entry,
        "Stop Loss": sl,
        "Target 1": t1,
        "Target 2": t2,
        "Target 3": t3,
        "RSI (14)": round(rsi, 1),
        "Vol Spike": f"{vol_ratio:.2f}x",
        "Structure": structure,
        "Pattern": pattern_name,
        "BB Lower": round(bb_low, 2),
        "BB Upper": round(bb_up, 2),
    }

@st.cache_data(ttl=9, show_spinner=False)
def fetch_market_matrix(symbols: tuple, interval: str) -> pd.DataFrame:
    period_map = {"5m": "5d", "15m": "10d", "30m": "1mo", "1h": "1mo", "1d": "6mo", "1wk": "2y"}
    raw = yf.download(tickers=list(symbols), period=period_map.get(interval, "10d"), interval=interval, group_by="ticker", threads=True, progress=False)

    results = []
    for sym in symbols:
        try:
            df_sym = raw[sym].dropna() if len(symbols) > 1 else raw.dropna()
            row = analyze_stock(sym, df_sym)
            if row: results.append(row)
        except Exception:
            continue
    return pd.DataFrame(results)

def render_trade_chart(symbol: str, interval: str, trade_row: dict):
    period_map = {"5m": "5d", "15m": "10d", "30m": "1mo", "1h": "1mo", "1d": "6mo", "1wk": "2y"}
    df = yf.download(symbol, period=period_map.get(interval, "10d"), interval=interval, progress=False)
    if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
    df = compute_indicators(df.dropna()).tail(80)

    fig = make_subplots(rows=3, cols=1, shared_xaxes=True, vertical_spacing=0.04, row_heights=[0.62, 0.18, 0.20], subplot_titles=(f"{trade_row['Symbol']} ({interval}) — {trade_row['Signal']} | Accuracy: {trade_row['Accuracy %']}%", "Volume", "RSI (14)"))
    fig.add_trace(go.Candlestick(x=df.index, open=df["Open"], high=df["High"], low=df["Low"], close=df["Close"], name="Price", increasing_line_color="#00C805", decreasing_line_color="#FF3B30"), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df["BB_Upper"], line=dict(color="rgba(100,149,237,0.5)", width=1), name="BB Upper"), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df["SMA20"], line=dict(color="orange", width=1, dash="dot"), name="SMA 20"), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df["BB_Lower"], line=dict(color="rgba(100,149,237,0.5)", width=1), fill="tonexty", fillcolor="rgba(100,149,237,0.07"), name="BB Lower"), row=1, col=1)

    levels = [
        (trade_row["Entry"], f"ENTRY: {trade_row['Entry']}", "#2979FF", "solid"),
        (trade_row["Stop Loss"], f"SL: {trade_row['Stop Loss']}", "#FF1744", "dash"),
        (trade_row["Target 1"], f"T1: {trade_row['Target 1']}", "#00E676", "dot"),
        (trade_row["Target 2"], f"T2: {trade_row['Target 2']}", "#00C853", "dashdot"),
        (trade_row["Target 3"], f"T3: {trade_row['Target 3']}", "#1B5E20", "dash"),
    ]
    for price_lvl, label_txt, color_hex, dash_style in levels:
        fig.add_hline(y=price_lvl, line_dash=dash_style, line_color=color_hex, line_width=1.6, annotation_text=label_txt, annotation_position="right", annotation_font_color=color_hex, row=1, col=1)

    vol_colors = ["#00C805" if c >= o else "#FF3B30" for c, o in zip(df["Close"], df["Open"])]
    fig.add_trace(go.Bar(x=df.index, y=df["Volume"], marker_color=vol_colors, name="Volume"), row=2, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df["RSI"], line=dict(color="#AB47BC", width=1.5), name="RSI"), row=3, col=1)
    fig.add_hline(y=70, line_dash="dash", line_color="red", row=3, col=1)
    fig.add_hline(y=30, line_dash="dash", line_color="green", row=3, col=1)

    fig.update_layout(height=720, template="plotly_dark", xaxis_rangeslider_visible=False, showlegend=False, margin=dict(l=10, r=95, t=40, b=10))
    st.plotly_chart(fig, use_container_width=True)

st.title("Nifty 200 Live Technical Matrix")
timeframe = st.sidebar.selectbox("Timeframe", ["5m", "15m", "30m", "1h", "1d", "1wk"], index=1)
active_symbols = tuple(NIFTY_200_SYMBOLS)

with st.spinner("Scanning live market data..."):
    matrix_df = fetch_market_matrix(active_symbols, timeframe)

if not matrix_df.empty:
    selected_stock = st.selectbox("Select Stock:", options=matrix_df["Symbol"].tolist())
    stock_row = matrix_df[matrix_df["Symbol"] == selected_stock].iloc[0].to_dict()
    render_trade_chart(stock_row["Full_Symbol"], timeframe, stock_row)
