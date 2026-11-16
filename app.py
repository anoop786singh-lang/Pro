import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

st.set_page_config(page_title="Pro Multi-Timeframe Scanner", layout="wide")

DEFAULT_TICKERS = [
    "RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "ICICIBANK.NS", "BHARTIARTL.NS",
    "SBIN.NS", "INFY.NS", "LICI.NS", "ITC.NS", "HINDUNILVR.NS",
    "LT.NS", "BAJFINANCE.NS", "HCLTECH.NS", "MARUTI.NS", "SUNPHARMA.NS",
    "ADANIENT.NS", "KOTAKBANK.NS", "TITAN.NS", "ONGC.NS", "TATAMOTORS.NS",
    "NTPC.NS", "AXISBANK.NS", "DMART.NS", "ADANIPORTS.NS", "ULTRACEMCO.NS",
    "ASIANPAINT.NS", "COALINDIA.NS", "BAJAJFINSV.NS", "BAJAJ-AUTO.NS", "POWERGRID.NS",
    "NESTLEIND.NS", "WIPRO.NS", "M&M.NS", "IOC.NS", "JIOFIN.NS",
    "HAL.NS", "DLF.NS", "IRFC.NS", "VBL.NS", "ZOMATO.NS",
    "BEL.NS", "LTIM.NS", "TRENT.NS", "INDIGO.NS", "TATASTEEL.NS",
    "SIEMENS.NS", "PIDILITIND.NS", "GRASIM.NS", "SBILIFE.NS", "TECHM.NS"
]

@st.cache_data(ttl=300, show_spinner=False)
def fetch_batch_data(tickers: list[str], interval: str) -> dict[str, pd.DataFrame]:
    period_map = {"15m": "15d", "1h": "60d", "1d": "1y", "1wk": "2y"}
    period = period_map.get(interval, "1y")
    raw = yf.download(
        tickers=tickers, period=period, interval=interval,
        group_by="ticker", auto_adjust=True, threads=True, progress=False
    )
    cleaned = {}
    for t in tickers:
        try:
            df = raw[t].dropna(how="all").copy() if len(tickers) > 1 else raw.dropna(how="all").copy()
            if len(df) >= 25:
                cleaned[t] = df
        except KeyError:
            continue
    return cleaned

def compute_indicators(df: pd.DataFrame, rsi_len: int = 14, bb_len: int = 20, bb_std: float = 2.0) -> pd.DataFrame:
    delta = df["Close"].diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / rsi_len, min_periods=rsi_len, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / rsi_len, min_periods=rsi_len, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    df["RSI"] = 100 - (100 / (1 + rs))

    df["SMA20"] = df["Close"].rolling(window=bb_len).mean()
    std = df["Close"].rolling(window=bb_len).std(ddof=1)
    df["BB_Upper"] = df["SMA20"] + (bb_std * std)
    df["BB_Lower"] = df["SMA20"] - (bb_std * std)
    df["BB_PctB"] = (df["Close"] - df["BB_Lower"]) / (df["BB_Upper"] - df["BB_Lower"])
    return df

def evaluate_signal(df: pd.DataFrame, rsi_os: int, rsi_ob: int) -> tuple[str, float, float]:
    curr, prev = df.iloc[-1], df.iloc[-2]
    bullish_candle = curr["Close"] > curr["Open"] and curr["Close"] > prev["High"]
    bearish_candle = curr["Close"] < curr["Open"] and curr["Close"] < prev["Low"]

    if curr["RSI"] <= rsi_os and curr["Low"] <= curr["BB_Lower"] and bullish_candle:
        return "STRONG BUY", round(curr["Low"] * 0.995, 2), round(curr["SMA20"], 2)
    elif curr["RSI"] >= rsi_ob and curr["High"] >= curr["BB_Upper"] and bearish_candle:
        return "STRONG SELL", round(curr["High"] * 1.005, 2), round(curr["SMA20"], 2)
    elif curr["Close"] > curr["SMA20"] and curr["RSI"] > 55:
        return "BULLISH TREND", round(curr["SMA20"], 2), round(curr["BB_Upper"], 2)
    elif curr["Close"] < curr["SMA20"] and curr["RSI"] < 45:
        return "BEARISH TREND", round(curr["SMA20"], 2), round(curr["BB_Lower"], 2)
    return "NEUTRAL", 0.0, 0.0

with st.sidebar:
    st.header("Scanner Parameters")
    timeframe = st.selectbox("Primary Timeframe", ["15m", "1h", "1d", "1wk"], index=2)
    rsi_os = st.slider("RSI Oversold", 15, 40, 30)
    rsi_ob = st.slider("RSI Overbought", 60, 85, 70)
    signal_filter = st.multiselect(
        "Filter Signals",
        ["STRONG BUY", "STRONG SELL", "BULLISH TREND", "BEARISH TREND", "NEUTRAL"],
        default=["STRONG BUY", "STRONG SELL", "BULLISH TREND", "BEARISH TREND", "NEUTRAL"]
    )
    if st.button("Force Refresh Data", use_container_width=True):
        st.cache_data.clear()

with st.spinner("Fetching batch market data..."):
    data_map = fetch_batch_data(DEFAULT_TICKERS, timeframe)

rows = []
processed_dfs = {}
for ticker, raw_df in data_map.items():
    df = compute_indicators(raw_df)
    processed_dfs[ticker] = df
    last = df.iloc[-1]
    prev_close = df.iloc[-2]["Close"]
    chg_pct = ((last["Close"] - prev_close) / prev_close) * 100
    sig, sl, tgt = evaluate_signal(df, rsi_os, rsi_ob)
    rows.append({
        "Ticker": ticker.replace(".NS", ""),
        "RawTicker": ticker,
        "Close": round(float(last["Close"]), 2),
        "Chg %": round(float(chg_pct), 2),
        "RSI (14)": round(float(last["RSI"]), 1),
        "20 SMA": round(float(last["SMA20"]), 2),
        "BB %B": round(float(last["BB_PctB"]), 2),
        "Signal": sig,
        "Stop Loss": sl if sl > 0 else None,
        "Target": tgt if tgt > 0 else None,
    })

scan_df = pd.DataFrame(rows)
filtered_df = scan_df[scan_df["Signal"].isin(signal_filter)].reset_index(drop=True)

m1, m2, m3, m4 = st.columns(4, border=True)
m1.metric("Scanned Equities", len(scan_df))
m2.metric("Strong Buy Setups", int((scan_df["Signal"] == "STRONG BUY").sum()))
m3.metric("Strong Sell Setups", int((scan_df["Signal"] == "STRONG SELL").sum()))
m4.metric("Avg Market RSI", f"{scan_df['RSI (14)'].mean():.1f}")

left_col, right_col = st.columns([1.35, 1.65], gap="medium")

with left_col:
    st.subheader(f"Scanner Results ({timeframe})")
    event = st.dataframe(
        filtered_df.drop(columns=["RawTicker"]),
        use_container_width=True, height=560, hide_index=True,
        on_select="rerun", selection_mode="single-row",
        column_config={
            "Close": st.column_config.NumberColumn(format="%.2f"),
            "Chg %": st.column_config.NumberColumn(format="%.2f%%"),
            "RSI (14)": st.column_config.ProgressColumn(min_value=0, max_value=100, format="%.1f"),
            "BB %B": st.column_config.NumberColumn(format="%.2f"),
        }
    )

with right_col:
    selected_rows = event.selection.rows if event and event.selection else []
    active_idx = selected_rows[0] if selected_rows else 0
    if not filtered_df.empty:
        sel_row = filtered_df.iloc[active_idx]
        sel_ticker = sel_row["RawTicker"]
        chart_df = processed_dfs[sel_ticker].tail(100)

        st.subheader(f"{sel_row['Ticker']} — {sel_row['Signal']} ({timeframe})")
        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.05, row_heights=[0.72, 0.28])
        fig.add_trace(go.Candlestick(
            x=chart_df.index, open=chart_df["Open"], high=chart_df["High"],
            low=chart_df["Low"], close=chart_df["Close"], name="Price"
        ), row=1, col=1)
        fig.add_trace(go.Scatter(x=chart_df.index, y=chart_df["SMA20"], line=dict(color="orange", width=1.5), name="20 SMA"), row=1, col=1)
        fig.add_trace(go.Scatter(x=chart_df.index, y=chart_df["BB_Upper"], line=dict(color="rgba(0,150,255,0.5)", dash="dot"), name="BB Upper"), row=1, col=1)
        fig.add_trace(go.Scatter(x=chart_df.index, y=chart_df["BB_Lower"], line=dict(color="rgba(0,150,255,0.5)", dash="dot"), fill="tonexty", fillcolor="rgba(0,150,255,0.06)", name="BB Lower"), row=1, col=1)

        fig.add_trace(go.Scatter(x=chart_df.index, y=chart_df["RSI"], line=dict(color="#A855F7", width=1.8), name="RSI (14)"), row=2, col=1)
        fig.add_hline(y=rsi_ob, line_dash="dash", line_color="red", row=2, col=1)
        fig.add_hline(y=rsi_os, line_dash="dash", line_color="green", row=2, col=1)

        fig.update_layout(height=560, margin=dict(l=10, r=10, t=10, b=10), xaxis_rangeslider_visible=False, template="plotly_dark", showlegend=False)
        st.plotly_chart(fig, use_container_width=True)
