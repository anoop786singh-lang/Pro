import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

st.set_page_config(page_title="Market Master Pro", layout="wide")

# --- WATCHLIST & SESSION STATE ---
DEFAULT_WATCHLIST = [
    {"Ticker": "RELIANCE.NS", "Name": "Reliance Industries"},
    {"Ticker": "TCS.NS", "Name": "Tata Consultancy Services"},
    {"Ticker": "HDFCBANK.NS", "Name": "HDFC Bank"},
    {"Ticker": "INFY.NS", "Name": "Infosys"},
    {"Ticker": "ICICIBANK.NS", "Name": "ICICI Bank"},
    {"Ticker": "BHARTIARTL.NS", "Name": "Bharti Airtel"},
    {"Ticker": "SBIN.NS", "Name": "State Bank of India"},
    {"Ticker": "LT.NS", "Name": "Larsen & Toubro"},
]

if "selected_ticker" not in st.session_state:
    st.session_state.selected_ticker = DEFAULT_WATCHLIST[0]["Ticker"]

# --- SIDEBAR: CLICKABLE WATCHLIST & TIMEFRAME ---
st.sidebar.title("Market Master Pro")
st.sidebar.subheader("Watchlist")

for item in DEFAULT_WATCHLIST:
    sym = item["Ticker"]
    is_active = sym == st.session_state.selected_ticker
    btn_label = f"▶ {sym.replace('.NS', '')} — {item['Name']}" if is_active else f"{sym.replace('.NS', '')} — {item['Name']}"
    if st.sidebar.button(btn_label, key=f"wl_{sym}", use_container_width=True, type="primary" if is_active else "secondary"):
        st.session_state.selected_ticker = sym
        st.rerun()

st.sidebar.divider()
manual_ticker = st.sidebar.text_input(
    "Custom Symbol (NSE/Global)",
    value=st.session_state.selected_ticker
).upper().strip()

if manual_ticker and manual_ticker != st.session_state.selected_ticker:
    st.session_state.selected_ticker = manual_ticker
    st.rerun()

TIMEFRAME_MAP = {
    "15m": {"interval": "15m", "period": "60d",  "swing_window": 10},
    "1h":  {"interval": "1h",  "period": "730d", "swing_window": 10},
    "1d":  {"interval": "1d",  "period": "max",  "swing_window": 14},
    "1wk": {"interval": "1wk", "period": "max",  "swing_window": 10},
    "1mo": {"interval": "1mo", "period": "max",  "swing_window": 8},
}

chart_tf = st.sidebar.selectbox(
    "Chart Timeframe",
    options=list(TIMEFRAME_MAP.keys()),
    index=2
)

# --- DATA & INDICATOR HELPERS ---
@st.cache_data(ttl=300)
def fetch_data(symbol: str, tf_key: str) -> pd.DataFrame:
    cfg = TIMEFRAME_MAP[tf_key]
    df = yf.download(symbol, period=cfg["period"], interval=cfg["interval"], progress=False)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df.dropna(inplace=True)
    return df

def compute_rsi(series: pd.Series, period: int) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))

def detect_swing_levels(df: pd.DataFrame, lookback: int):
    recent = df.tail(lookback * 3)
    return float(recent["High"].max()), float(recent["Low"].min())

# --- FETCH & COMPUTE ---
ticker = st.session_state.selected_ticker
rsi_tf = st.session_state.get("rsi_tf_ctrl", chart_tf)
rsi_period = st.session_state.get("rsi_period_ctrl", 14)
rsi_lower = st.session_state.get("rsi_lower_ctrl", 40)
rsi_upper = st.session_state.get("rsi_upper_ctrl", 60)
show_rsi = st.session_state.get("show_rsi_ctrl", True)
show_vol = st.session_state.get("show_vol_ctrl", False)

df_chart = fetch_data(ticker, chart_tf)
df_rsi = fetch_data(ticker, rsi_tf)

if df_chart.empty or df_rsi.empty:
    st.error(f"No data returned for {ticker}. Check ticker symbol.")
    st.stop()

df_chart["SMA20"] = df_chart["Close"].rolling(20).mean()
df_chart["BB_Std"] = df_chart["Close"].rolling(20).std()
df_chart["BB_Upper"] = df_chart["SMA20"] + 2 * df_chart["BB_Std"]
df_chart["BB_Lower"] = df_chart["SMA20"] - 2 * df_chart["BB_Std"]

df_rsi["RSI"] = compute_rsi(df_rsi["Close"], int(rsi_period))
latest_rsi = float(df_rsi["RSI"].iloc[-1])
df_chart["RSI_Aligned"] = df_rsi[["RSI"]].reindex(df_chart.index, method="ffill")["RSI"].bfill()

window = TIMEFRAME_MAP[chart_tf]["swing_window"]
swing_high, swing_low = detect_swing_levels(df_chart, window)
current_price = float(df_chart["Close"].iloc[-1])

if latest_rsi >= rsi_upper:
    bias = "BULLISH"
    entry = current_price
    stop_loss = swing_low
    risk = max(entry - stop_loss, entry * 0.005)
    target_1 = entry + (1.5 * risk)
    target_2 = entry + (2.5 * risk)
elif latest_rsi <= rsi_lower:
    bias = "BEARISH"
    entry = current_price
    stop_loss = swing_high
    risk = max(stop_loss - entry, entry * 0.005)
    target_1 = entry - (1.5 * risk)
    target_2 = entry - (2.5 * risk)
else:
    bias = "NEUTRAL"
    entry = current_price
    stop_loss = swing_low
    target_1 = swing_high
    target_2 = swing_high + (swing_high - swing_low) * 0.5

# --- TOP METRICS BAR ---
m1, m2, m3, m4, m5, m6 = st.columns(6)
m1.metric(f"{ticker} ({chart_tf})", f"{current_price:.2f}", bias)
m2.metric("Swing High", f"{swing_high:.2f}")
m3.metric("Swing Low", f"{swing_low:.2f}")
m4.metric("Stop Loss", f"{stop_loss:.2f}")
m5.metric("Target 1 / 2", f"{target_1:.2f} / {target_2:.2f}")
m6.metric(f"RSI ({rsi_tf}|{rsi_period})", f"{latest_rsi:.2f}", f"{rsi_lower}/{rsi_upper}")

# --- DYNAMIC SUBPLOT STRUCTURE ---
active_subplots = ["price"]
if show_vol and "Volume" in df_chart.columns:
    active_subplots.append("volume")
if show_rsi:
    active_subplots.append("rsi")

num_rows = len(active_subplots)
if num_rows == 1:
    row_heights = [1.0]
elif num_rows == 2:
    row_heights = [0.74, 0.26]
else:
    row_heights = [0.62, 0.16, 0.22]

fig = make_subplots(
    rows=num_rows,
    cols=1,
    shared_xaxes=True,
    vertical_spacing=0.04,
    row_heights=row_heights
)

# Row 1: Price + Indicators + Levels
fig.add_trace(go.Candlestick(
    x=df_chart.index,
    open=df_chart["Open"], high=df_chart["High"],
    low=df_chart["Low"], close=df_chart["Close"],
    name="Price"
), row=1, col=1)

fig.add_trace(go.Scatter(x=df_chart.index, y=df_chart["SMA20"], line=dict(color="orange", width=1.2), name="20 SMA"), row=1, col=1)
fig.add_trace(go.Scatter(x=df_chart.index, y=df_chart["BB_Upper"], line=dict(color="rgba(150,150,150,0.4)", width=1), name="BB Upper"), row=1, col=1)
fig.add_trace(go.Scatter(x=df_chart.index, y=df_chart["BB_Lower"], line=dict(color="rgba(150,150,150,0.4)", width=1), name="BB Lower"), row=1, col=1)

levels = [
    (swing_high, f"Swing High: {swing_high:.2f}", "purple", "dot"),
    (swing_low,  f"Swing Low: {swing_low:.2f}",   "purple", "dot"),
    (entry,      f"Entry: {entry:.2f}",           "blue",   "solid"),
    (stop_loss,  f"SL: {stop_loss:.2f}",          "red",    "dash"),
    (target_1,   f"T1: {target_1:.2f}",           "green",  "dash"),
    (target_2,   f"T2: {target_2:.2f}",           "darkgreen", "dash"),
]
for y_val, label, color, dash in levels:
    fig.add_hline(
        y=y_val, line_dash=dash, line_color=color, line_width=1.2,
        annotation_text=label, annotation_position="top left",
        row=1, col=1
    )

current_row = 2

# Optional Volume Subplot
if "volume" in active_subplots:
    vol_colors = np.where(df_chart["Close"] >= df_chart["Open"], "rgba(38,166,154,0.6)", "rgba(239,83,80,0.6)")
    fig.add_trace(go.Bar(
        x=df_chart.index, y=df_chart["Volume"],
        marker_color=vol_colors, name="Volume"
    ), row=current_row, col=1)
    fig.update_yaxes(title_text="Vol", row=current_row, col=1)
    current_row += 1

# Optional RSI Subplot
if "rsi" in active_subplots:
    fig.add_trace(go.Scatter(
        x=df_chart.index, y=df_chart["RSI_Aligned"],
        line=dict(color="#00B4D8", width=1.8),
        name=f"RSI ({rsi_period})"
    ), row=current_row, col=1)
    fig.add_hline(y=rsi_upper, line_dash="dash", line_color="red", row=current_row, col=1)
    fig.add_hline(y=50, line_dash="dot", line_color="gray", row=current_row, col=1)
    fig.add_hline(y=rsi_lower, line_dash="dash", line_color="green", row=current_row, col=1)
    fig.update_yaxes(range=[0, 100], title_text=f"RSI ({rsi_period})", row=current_row, col=1)

fig.update_layout(
    height=650,
    xaxis_rangeslider_visible=False,
    template="plotly_dark",
    margin=dict(l=15, r=15, t=25, b=15)
)
st.plotly_chart(fig, use_container_width=True)

# --- BOTTOM-LEFT TRADINGVIEW-STYLE INDICATOR CONTROLS ---
ctrl_col1, ctrl_col2, _ = st.columns([1.2, 1.4, 5.4])

with ctrl_col1:
    st.toggle("Show RSI", value=True, key="show_rsi_ctrl")

with ctrl_col2:
    with st.popover("⚙ Indicators & RSI"):
        st.toggle("Show Volume", value=False, key="show_vol_ctrl")
        st.selectbox("RSI Timeframe", options=list(TIMEFRAME_MAP.keys()), index=list(TIMEFRAME_MAP.keys()).index(chart_tf), key="rsi_tf_ctrl")
        st.number_input("RSI Period", min_value=2, max_value=50, value=14, step=1, key="rsi_period_ctrl")
        st.number_input("RSI Lower Level", min_value=1, max_value=99, value=40, step=1, key="rsi_lower_ctrl")
        st.number_input("RSI Upper Level", min_value=1, max_value=99, value=60, step=1, key="rsi_upper_ctrl")
