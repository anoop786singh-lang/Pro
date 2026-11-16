import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode, DataReturnMode

st.set_page_config(page_title="Market Master Pro", layout="wide")
st.title("Market Master Pro — Multi-Timeframe Terminal")

# --- WATCHLIST & SESSION STATE ---
DEFAULT_WATCHLIST = [
    {"Ticker": "RELIANCE.NS", "Name": "Reliance Industries", "Sector": "Energy"},
    {"Ticker": "TCS.NS", "Name": "Tata Consultancy Services", "Sector": "IT"},
    {"Ticker": "HDFCBANK.NS", "Name": "HDFC Bank", "Sector": "Banking"},
    {"Ticker": "INFY.NS", "Name": "Infosys", "Sector": "IT"},
    {"Ticker": "ICICIBANK.NS", "Name": "ICICI Bank", "Sector": "Banking"},
    {"Ticker": "BHARTIARTL.NS", "Name": "Bharti Airtel", "Sector": "Telecom"},
    {"Ticker": "SBIN.NS", "Name": "State Bank of India", "Sector": "Banking"},
    {"Ticker": "LT.NS", "Name": "Larsen & Toubro", "Sector": "Infrastructure"},
]

if "selected_ticker" not in st.session_state:
    st.session_state.selected_ticker = DEFAULT_WATCHLIST[0]["Ticker"]

# --- SIDEBAR CONTROLS ---
st.sidebar.header("Market & Chart Settings")

manual_ticker = st.sidebar.text_input(
    "Manual Ticker Override",
    value=st.session_state.selected_ticker
).upper().strip()

if manual_ticker and manual_ticker != st.session_state.selected_ticker:
    st.session_state.selected_ticker = manual_ticker

# Note: yfinance enforces hard lookback caps on intraday intervals (60d for 15m, 730d for 1h); 1d/1wk/1mo fetch full listing-to-present history ("max")
TIMEFRAME_MAP = {
    "15m": {"interval": "15m", "period": "60d",  "swing_window": 10},
    "1h":  {"interval": "1h",  "period": "730d", "swing_window": 10},
    "1d":  {"interval": "1d",  "period": "max",  "swing_window": 14},
    "1wk": {"interval": "1wk", "period": "max",  "swing_window": 10},
    "1mo": {"interval": "1mo", "period": "max",  "swing_window": 8},
}

chart_tf = st.sidebar.selectbox(
    "Chart Timeframe (Price & Swing Levels)",
    options=list(TIMEFRAME_MAP.keys()),
    index=2
)

st.sidebar.header("Independent RSI Settings")
rsi_tf = st.sidebar.selectbox(
    "RSI Calculation Timeframe",
    options=list(TIMEFRAME_MAP.keys()),
    index=3
)
rsi_period = st.sidebar.number_input("RSI Period", min_value=2, max_value=50, value=14, step=1)
rsi_lower = st.sidebar.number_input("RSI Lower Level (Oversold / Support)", min_value=1, max_value=99, value=40, step=1)
rsi_upper = st.sidebar.number_input("RSI Upper Level (Overbought / Resistance)", min_value=1, max_value=99, value=60, step=1)

# --- DATA & INDICATOR HELPERS ---
@st.cache_data(ttl=300)
def fetch_data(symbol: str, tf_key: str) -> pd.DataFrame:
    cfg = TIMEFRAME_MAP[tf_key]
    df = yf.download(symbol, period=cfg["period"], interval=cfg["interval"], progress=False)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df.dropna(inplace=True)
    return df

@st.cache_data(ttl=300)
def build_watchlist_snapshot(watchlist: list[dict]) -> pd.DataFrame:
    rows = []
    for item in watchlist:
        sym = item["Ticker"]
        try:
            df_snap = yf.download(sym, period="5d", interval="1d", progress=False)
            if isinstance(df_snap.columns, pd.MultiIndex):
                df_snap.columns = df_snap.columns.get_level_values(0)
            df_snap.dropna(inplace=True)
            if len(df_snap) >= 2:
                ltp = float(df_snap["Close"].iloc[-1])
                prev = float(df_snap["Close"].iloc[-2])
                chg_pct = ((ltp - prev) / prev) * 100
            elif len(df_snap) == 1:
                ltp = float(df_snap["Close"].iloc[-1])
                chg_pct = 0.0
            else:
                ltp, chg_pct = np.nan, np.nan
        except Exception:
            ltp, chg_pct = np.nan, np.nan
        rows.append({
            "Ticker": sym,
            "Stock Name": item["Name"],
            "Sector": item["Sector"],
            "LTP": round(ltp, 2) if not np.isnan(ltp) else 0.0,
            "Change %": round(chg_pct, 2) if not np.isnan(chg_pct) else 0.0,
        })
    return pd.DataFrame(rows)

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
    swing_high = float(recent["High"].max())
    swing_low = float(recent["Low"].min())
    return swing_high, swing_low

# --- LAYOUT: LEFT CLICKABLE WATCHLIST | RIGHT LIVE CHART ---
col_list, col_chart = st.columns([1.15, 2.85], gap="medium")

with col_list:
    st.subheader("Watchlist (Click Row to Open)")
    watchlist_df = build_watchlist_snapshot(DEFAULT_WATCHLIST)

    gb = GridOptionsBuilder.from_dataframe(watchlist_df)
    gb.configure_selection(selection_mode="single", use_checkbox=False)
    gb.configure_column("Ticker", pinned="left", width=115, cellStyle={"fontWeight": "bold", "color": "#00B4D8", "cursor": "pointer"})
    gb.configure_column("Stock Name", width=150, cellStyle={"cursor": "pointer"})
    gb.configure_column("Sector", width=95)
    gb.configure_column("LTP", width=85, type=["numericColumn"])
    gb.configure_column("Change %", width=90, type=["numericColumn"])
    gb.configure_grid_options(domLayout="normal", rowHeight=34)

    grid_response = AgGrid(
        watchlist_df,
        gridOptions=gb.build(),
        update_mode=GridUpdateMode.SELECTION_CHANGED,
        data_return_mode=DataReturnMode.FILTERED_AND_SORTED,
        fit_columns_on_grid_load=False,
        theme="streamlit",
        height=680,
        key="watchlist_aggrid"
    )

    selected_rows = grid_response.get("selected_rows", None)
    if selected_rows is not None:
        if isinstance(selected_rows, pd.DataFrame) and not selected_rows.empty:
            clicked_ticker = selected_rows.iloc[0]["Ticker"]
            if clicked_ticker != st.session_state.selected_ticker:
                st.session_state.selected_ticker = clicked_ticker
                st.rerun()
        elif isinstance(selected_rows, list) and len(selected_rows) > 0:
            clicked_ticker = selected_rows[0]["Ticker"]
            if clicked_ticker != st.session_state.selected_ticker:
                st.session_state.selected_ticker = clicked_ticker
                st.rerun()

with col_chart:
    ticker = st.session_state.selected_ticker
    df_chart = fetch_data(ticker, chart_tf)
    df_rsi = fetch_data(ticker, rsi_tf)

    if df_chart.empty or df_rsi.empty:
        st.error(f"No data returned for {ticker}. Check ticker symbol.")
        st.stop()

    # Chart Indicators (20 SMA & Bollinger Bands)
    df_chart["SMA20"] = df_chart["Close"].rolling(20).mean()
    df_chart["BB_Std"] = df_chart["Close"].rolling(20).std()
    df_chart["BB_Upper"] = df_chart["SMA20"] + 2 * df_chart["BB_Std"]
    df_chart["BB_Lower"] = df_chart["SMA20"] - 2 * df_chart["BB_Std"]

    # Independent RSI Calculation & Alignment to Chart Index
    df_rsi["RSI"] = compute_rsi(df_rsi["Close"], int(rsi_period))
    latest_rsi = float(df_rsi["RSI"].iloc[-1])

    rsi_aligned = df_rsi[["RSI"]].reindex(df_chart.index, method="ffill")
    df_chart["RSI_Aligned"] = rsi_aligned["RSI"].bfill()

    # Automatic Swing High / Low & Trade Levels per Active Chart Timeframe
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
        bias = "NEUTRAL (RANGE)"
        entry = current_price
        stop_loss = swing_low
        target_1 = swing_high
        target_2 = swing_high + (swing_high - swing_low) * 0.5

    # Metrics Bar
    m1, m2, m3, m4, m5, m6 = st.columns(6)
    m1.metric(f"{ticker} ({chart_tf})", f"{current_price:.2f}", bias)
    m2.metric(f"Swing High ({chart_tf})", f"{swing_high:.2f}")
    m3.metric(f"Swing Low ({chart_tf})", f"{swing_low:.2f}")
    m4.metric("Auto Stop Loss", f"{stop_loss:.2f}")
    m5.metric("Target 1 / 2", f"{target_1:.2f} / {target_2:.2f}")
    m6.metric(f"RSI ({rsi_tf}|{rsi_period})", f"{latest_rsi:.2f}", f"{rsi_lower}/{rsi_upper}")

    # Interactive Plotly Chart
    fig = make_subplots(
        rows=2, cols=1, shared_xaxes=True,
        vertical_spacing=0.06, row_heights=[0.72, 0.28],
        subplot_titles=(
            f"{ticker} [{chart_tf} Chart] — Auto Swing High/Low, SL & Targets",
            f"RSI ({rsi_period}) on [{rsi_tf} Timeframe] — Custom Levels ({rsi_lower} / {rsi_upper})"
        )
    )

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
        (swing_high, f"Swing High ({chart_tf}): {swing_high:.2f}", "purple", "dot"),
        (swing_low,  f"Swing Low ({chart_tf}): {swing_low:.2f}",   "purple", "dot"),
        (entry,      f"Entry: {entry:.2f}",                        "blue",   "solid"),
        (stop_loss,  f"Stop Loss: {stop_loss:.2f}",                "red",    "dash"),
        (target_1,   f"Target 1: {target_1:.2f}",                  "green",  "dash"),
        (target_2,   f"Target 2: {target_2:.2f}",                  "darkgreen", "dash"),
    ]
    for y_val, label, color, dash in levels:
        fig.add_hline(
            y=y_val, line_dash=dash, line_color=color, line_width=1.3,
            annotation_text=label, annotation_position="top left",
            row=1, col=1
        )

    fig.add_trace(go.Scatter(
        x=df_chart.index, y=df_chart["RSI_Aligned"],
        line=dict(color="#00B4D8", width=1.8),
        name=f"RSI ({rsi_tf})"
    ), row=2, col=1)

    fig.add_hline(y=rsi_upper, line_dash="dash", line_color="red", annotation_text=f"Upper ({rsi_upper})", row=2, col=1)
    fig.add_hline(y=50, line_dash="dot", line_color="gray", row=2, col=1)
    fig.add_hline(y=rsi_lower, line_dash="dash", line_color="green", annotation_text=f"Lower ({rsi_lower})", row=2, col=1)

    fig.update_yaxes(range=[0, 100], row=2, col=1)
    fig.update_layout(height=720, xaxis_rangeslider_visible=True, template="plotly_dark", margin=dict(l=20, r=20, t=40, b=20))

    st.plotly_chart(fig, use_container_width=True)
