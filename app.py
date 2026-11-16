import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# -----------------------------------------------------------------------------
# PAGE CONFIGURATION & COMPACT INSTITUTIONAL STYLING
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="MTF Institutional Trading Terminal",
    layout="wide",
    initial_sidebar_state="collapsed"
)

st.markdown("""
<style>
    /* Compact layout & clean institutional styling */
    .block-container {
        padding-top: 1.2rem;
        padding-bottom: 1rem;
        padding-left: 1.5rem;
        padding-right: 1.5rem;
    }
    h1 {
        font-size: 1.65rem !important;
        font-weight: 700 !important;
        margin-bottom: 0.2rem !important;
    }
    h2 {
        font-size: 1.25rem !important;
        font-weight: 600 !important;
        margin-top: 0.6rem !important;
        margin-bottom: 0.3rem !important;
    }
    h3 {
        font-size: 1.05rem !important;
        font-weight: 600 !important;
    }
    div[data-testid="stMetricValue"] {
        font-size: 1.35rem !important;
        font-weight: 700 !important;
    }
    div[data-testid="stMetricLabel"] {
        font-size: 0.78rem !important;
        color: #555555;
    }
    /* Styled compact table */
    div[data-testid="stDataFrame"] {
        border: 1px solid #e0e0e0;
        border-radius: 6px;
        overflow: hidden;
    }
    .stButton > button {
        padding: 0.25rem 0.75rem;
        font-size: 0.85rem;
        border-radius: 4px;
    }
</style>
""", unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# SESSION STATE MANAGEMENT
# -----------------------------------------------------------------------------
if "selected_stock" not in st.session_state:
    st.session_state.selected_stock = None

NIFTY_50_TICKERS = [
    "RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "ICICIBANK.NS", "BHARTIARTL.NS",
    "SBIN.NS", "INFY.NS", "LICI.NS", "ITC.NS", "HINDUNILVR.NS",
    "LT.NS", "BAJFINANCE.NS", "HCLTECH.NS", "MARUTI.NS", "SUNPHARMA.NS",
    "ADANIENT.NS", "KOTAKBANK.NS", "TITAN.NS", "ONGC.NS", "TATAMOTORS.NS",
    "NTPC.NS", "AXISBANK.NS", "ULTRACEMCO.NS", "WIPRO.NS", "M&M.NS",
    "COALINDIA.NS", "BAJAJFINSV.NS", "POWERGRID.NS", "NESTLEIND.NS", "TATASTEEL.NS"
]

# -----------------------------------------------------------------------------
# TECHNICAL INDICATORS & PATTERN ENGINE
# -----------------------------------------------------------------------------
def compute_indicators(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    close = df["Close"]
    high = df["High"]
    low = df["Low"]
    volume = df["Volume"]

    # SMAs
    df["SMA20"] = close.rolling(20).mean()
    df["SMA50"] = close.rolling(50).mean()

    # Bollinger Bands (20, 2)
    std20 = close.rolling(20).std()
    df["BB_Upper"] = df["SMA20"] + 2 * std20
    df["BB_Lower"] = df["SMA20"] - 2 * std20

    # Rolling VWAP (20-period institutional anchor)
    tp = (high + low + close) / 3.0
    df["VWAP"] = (tp * volume).rolling(20).sum() / volume.rolling(20).sum()

    # RSI (14) - Wilder's Smoothing
    delta = close.diff()
    gain = delta.clip(lower=0).ewm(alpha=1/14, min_periods=14, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1/14, min_periods=14, adjust=False).mean()
    rs = gain / loss.replace(0, np.nan)
    df["RSI"] = 100 - (100 / (1 + rs))
    df["RSI"] = df["RSI"].fillna(50.0)

    # ATR (14)
    tr = pd.concat([
        high - low,
        (high - close.shift()).abs(),
        (low - close.shift()).abs()
    ], axis=1).max(axis=1)
    df["ATR"] = tr.rolling(14).mean()

    return df

def analyze_timeframe(df: pd.DataFrame):
    if df is None or len(df) < 55:
        return {
            "signal": "NEUTRAL", "score": 0, "rsi": 50.0,
            "entry": 0.0, "sl": 0.0, "t1": 0.0, "t2": 0.0,
            "patterns": [], "candles": [], "rsi_note": "Insufficient data",
            "sma20": 0.0, "sma50": 0.0, "vwap": 0.0, "vol_ratio": 1.0,
            "support": 0.0, "resistance": 0.0, "fib": {}
        }

    df = compute_indicators(df)
    last = df.iloc[-1]
    prev = df.iloc[-2]

    price = float(last["Close"])
    rsi = float(last["RSI"])
    prev_rsi = float(prev["RSI"])
    sma20 = float(last["SMA20"])
    sma50 = float(last["SMA50"])
    vwap = float(last["VWAP"]) if not np.isnan(last["VWAP"]) else price
    atr = float(last["ATR"]) if not np.isnan(last["ATR"]) else price * 0.015

    # Scoring & Signals
    score = 0
    if price > sma20: score += 1
    else: score -= 1
    if price > sma50: score += 1
    else: score -= 1
    if price > vwap: score += 1
    else: score -= 1
    if rsi >= 60: score += 1
    elif rsi <= 40: score -= 1

    if score >= 3: signal = "STRONG BUY"
    elif score >= 1: signal = "BUY"
    elif score <= -3: signal = "STRONG SELL"
    elif score <= -1: signal = "SELL"
    else: signal = "NEUTRAL"

    # Swing High/Low & Fibonacci (60 bars)
    lookback = df.tail(60)
    swing_high = float(lookback["High"].max())
    swing_low = float(lookback["Low"].min())
    diff = swing_high - swing_low
    fib = {
        "0.0% (High)": round(swing_high, 2),
        "23.6%": round(swing_high - 0.236 * diff, 2),
        "38.2%": round(swing_high - 0.382 * diff, 2),
        "50.0%": round(swing_high - 0.500 * diff, 2),
        "61.8%": round(swing_high - 0.618 * diff, 2),
        "100.0% (Low)": round(swing_low, 2),
    }

    # Execution Levels (1:2 and 1:3 R:R)
    if "SELL" in signal:
        entry = round(price, 1)
        sl = round(max(swing_high, price + 1.5 * atr), 1)
        risk = max(sl - entry, price * 0.005)
        t1 = round(entry - 2 * risk, 1)
        t2 = round(entry - 3 * risk, 1)
    else:
        entry = round(price, 1)
        sl = round(min(swing_low, price - 1.5 * atr), 1)
        risk = max(entry - sl, price * 0.005)
        t1 = round(entry + 2 * risk, 1)
        t2 = round(entry + 3 * risk, 1)

    # Active Signals & Patterns
    patterns = []
    if price > sma20 > sma50:
        patterns.append("Trend Following")
    if abs(swing_low - float(lookback["Low"].tail(15).min())) / swing_low < 0.015 and price > sma20:
        patterns.append("Double Bottom Breakout")
    if swing_low < float(lookback["Low"].head(20).min()) and price > sma50:
        patterns.append("Inverse Head & Shoulders")

    # Candlestick detection
    candles = []
    body = abs(last["Close"] - last["Open"])
    rng = max(last["High"] - last["Low"], 1e-6)
    if body / rng < 0.12:
        candles.append("Doji")
    elif last["Close"] > last["Open"] and prev["Close"] < prev["Open"] and last["Close"] > prev["Open"] and last["Open"] < prev["Close"]:
        candles.append("Bullish Engulfing")
    elif last["Close"] < last["Open"] and prev["Close"] > prev["Open"] and last["Close"] < prev["Open"] and last["Open"] > prev["Close"]:
        candles.append("Bearish Engulfing")

    # RSI 40/60 Zone Rules
    rsi_signals = []
    if prev_rsi < 60 <= rsi:
        rsi_signals.append("RSI 60 Breakout & Retest Support")
    elif prev_rsi >= 60 > rsi:
        rsi_signals.append("RSI 60 Breakdown & Resistance Rejection")
    elif prev_rsi > 40 >= rsi:
        rsi_signals.append("RSI 40 Bear Zone Breakdown")

    vol_ratio = round(float(last["Volume"]) / max(float(df["Volume"].tail(20).mean()), 1.0), 2)

    return {
        "signal": signal,
        "score": score,
        "rsi": round(rsi, 1),
        "entry": entry,
        "sl": sl,
        "t1": t1,
        "t2": t2,
        "patterns": patterns,
        "candles": candles,
        "rsi_signals": rsi_signals,
        "sma20": round(sma20, 2),
        "sma50": round(sma50, 2),
        "vwap": round(vwap, 2),
        "vol_ratio": vol_ratio,
        "support": round(swing_low, 1),
        "resistance": round(swing_high, 1),
        "fib": fib,
        "df": df
    }

@st.cache_data(ttl=300, show_spinner=False)
def fetch_stock_data(ticker: str, interval: str):
    period_map = {
        "5m": "5d",
        "15m": "15d",
        "1h": "60d",
        "1d": "1y",
        "1wk": "3y"
    }
    try:
        df = yf.download(ticker, period=period_map.get(interval, "1y"), interval=interval, progress=False)
        if df.empty:
            return None
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        return df.dropna()
    except Exception:
        return None

@st.cache_data(ttl=300, show_spinner=False)
def scan_all_stocks(capital: float, risk_pct: float):
    rows = []
    risk_amount = capital * (risk_pct / 100.0)
    for ticker in NIFTY_50_TICKERS:
        df_1d = fetch_stock_data(ticker, "1d")
        df_1h = fetch_stock_data(ticker, "1h")
        df_15m = fetch_stock_data(ticker, "15m")

        res_1d = analyze_timeframe(df_1d)
        res_1h = analyze_timeframe(df_1h)
        res_15m = analyze_timeframe(df_15m)

        if res_1d["entry"] == 0:
            continue

        sigs = [res_1d["signal"], res_1h["signal"], res_15m["signal"]]
        if all("BUY" in s for s in sigs):
            confluence = "ALIGNED BULLISH"
        elif all("SELL" in s for s in sigs):
            confluence = "ALIGNED BEARISH"
        else:
            confluence = "MIXED"

        risk_per_share = max(abs(res_1d["entry"] - res_1d["sl"]), res_1d["entry"] * 0.005)
        qty = max(1, int(risk_amount // risk_per_share))

        all_active = res_1d["patterns"] + res_1d["candles"] + res_1d["rsi_signals"]
        active_str = ", ".join(all_active) if all_active else "Trend Following"

        rows.append({
            "Ticker": ticker,
            "Stock": ticker.replace(".NS", ""),
            "Price": res_1d["entry"],
            "MTF Confluence": confluence,
            "1D Signal": res_1d["signal"],
            "1H Signal": res_1h["signal"],
            "15M Signal": res_15m["signal"],
            "1D RSI": res_1d["rsi"],
            "Entry": res_1d["entry"],
            "SL": res_1d["sl"],
            "Target 1": res_1d["t1"],
            "Qty": qty,
            "Active Signals": active_str
        })
    return pd.DataFrame(rows)

# -----------------------------------------------------------------------------
# COMPACT STYLED MATRIX VIEW (MAIN DASHBOARD)
# -----------------------------------------------------------------------------
def style_matrix(df: pd.DataFrame):
    def color_signal(val):
        if val in ["STRONG BUY", "ALIGNED BULLISH"]:
            return "background-color: #d4edda; color: #155724; font-weight: 700;"
        elif val == "BUY":
            return "background-color: #e8f5e9; color: #2e7d32; font-weight: 600;"
        elif val in ["STRONG SELL", "ALIGNED BEARISH"]:
            return "background-color: #f8d7da; color: #721c24; font-weight: 700;"
        elif val == "SELL":
            return "background-color: #ffebee; color: #c62828; font-weight: 600;"
        elif val == "MIXED":
            return "background-color: #fff3cd; color: #856404; font-weight: 600;"
        return "color: #555555;"

    return (
        df.style
        .map(color_signal, subset=["MTF Confluence", "1D Signal", "1H Signal", "15M Signal"])
        .format({
            "Price": "₹{:.1f}",
            "1D RSI": "{:.1f}",
            "Entry": "₹{:.1f}",
            "SL": "₹{:.1f}",
            "Target 1": "₹{:.1f}"
        })
    )

def render_main_dashboard():
    st.title("Top 50 MTF Breakout & Institutional Matrix")
    st.caption("Click any row in the matrix to open its dedicated Multi-Timeframe analysis, active breakout patterns, and dynamic chart.")

    c1, c2, c3 = st.columns([1.2, 1.2, 2.6])
    with c1:
        capital = st.number_input("Trading Capital (₹)", min_value=10000.0, value=100000.0, step=10000.0)
    with c2:
        risk_pct = st.number_input("Risk per Trade (%)", min_value=0.1, max_value=10.0, value=1.0, step=0.25)
    with c3:
        confluence_filter = st.multiselect(
            "Filter MTF Confluence",
            ["ALIGNED BULLISH", "ALIGNED BEARISH", "MIXED"],
            default=["ALIGNED BULLISH", "ALIGNED BEARISH", "MIXED"]
        )

    with st.spinner("Scanning Top 50 stocks across 15m, 1h, and 1d timeframes..."):
        matrix_df = scan_all_stocks(capital, risk_pct)

    if matrix_df.empty:
        st.warning("No market data available at the moment.")
        return

    filtered_df = matrix_df[matrix_df["MTF Confluence"].isin(confluence_filter)].reset_index(drop=True)
    display_cols = [
        "Stock", "Price", "MTF Confluence", "1D Signal", "1H Signal",
        "15M Signal", "1D RSI", "Entry", "SL", "Target 1", "Qty", "Active Signals"
    ]

    event = st.dataframe(
        style_matrix(filtered_df[display_cols]),
        use_container_width=True,
        height=640,
        hide_index=True,
        on_select="rerun",
        selection_mode="single-row"
    )

    if event and event.selection and len(event.selection.rows) > 0:
        selected_idx = event.selection.rows[0]
        st.session_state.selected_stock = filtered_df.iloc[selected_idx]["Ticker"]
        st.rerun()

# -----------------------------------------------------------------------------
# DEDICATED DEEP-DIVE VIEW WITH RIGHT PRICE AXIS & LEFT INDICATOR CONTROLS
# -----------------------------------------------------------------------------
def render_deep_dive(ticker: str):
    if st.button("← Back to Top 50 Matrix"):
        st.session_state.selected_stock = None
        st.rerun()

    stock_name = ticker.replace(".NS", "")
    st.title(f"MTF Deep-Dive: {stock_name}")

    ctrl1, ctrl2, ctrl3 = st.columns([1.2, 1.2, 1.4])
    with ctrl1:
        capital = st.number_input("Trading Capital (₹)", min_value=10000.0, value=100000.0, step=10000.0, key="dd_cap")
    with ctrl2:
        risk_pct = st.number_input("Risk per Trade (%)", min_value=0.1, max_value=10.0, value=1.0, step=0.25, key="dd_risk")
    with ctrl3:
        active_tf = st.selectbox("Active Chart & Execution Timeframe", ["5m", "15m", "1h", "1d", "1wk"], index=3)

    # Multi-Timeframe Confluence Strip
    timeframes = ["5m", "15m", "1h", "1d", "1wk"]
    tf_results = {}
    for tf in timeframes:
        tf_results[tf] = analyze_timeframe(fetch_stock_data(ticker, tf))

    st.subheader("Multi-Timeframe Confluence Matrix")
    tf_cols = st.columns(5)
    for idx, tf in enumerate(timeframes):
        res = tf_results[tf]
        with tf_cols[idx]:
            st.metric(
                label=f"{tf.upper()} | RSI {res['rsi']}",
                value=res["signal"],
                delta=f"Entry {res['entry']} | SL {res['sl']}"
            )

    # Execution Levels & Position Sizing
    active_res = tf_results[active_tf]
    risk_amount = capital * (risk_pct / 100.0)
    risk_per_share = max(abs(active_res["entry"] - active_res["sl"]), active_res["entry"] * 0.005)
    qty = max(1, int(risk_amount // risk_per_share))
    allocated = int(qty * active_res["entry"])

    st.subheader(f"Execution Levels & Position Sizing ({active_tf.upper()})")
    ex1, ex2, ex3, ex4, ex5 = st.columns(5)
    direction = "LONG" if "BUY" in active_res["signal"] else ("SHORT" if "SELL" in active_res["signal"] else "WAIT")
    ex1.metric("Direction / Signal", f"{direction} ({active_res['signal']})")
    ex2.metric("Entry Price", f"₹{active_res['entry']}")
    ex3.metric("Stop Loss", f"₹{active_res['sl']}")
    ex4.metric("Targets (1:2 / 1:3)", f"₹{active_res['t1']} / ₹{active_res['t2']}")
    ex5.metric("Position Size (Qty)", f"{qty} shares", delta=f"₹{allocated:,} Cap")

    # Active Patterns & Key Levels
    st.subheader(f"Active Breakout Patterns, Candlesticks & RSI Zone Signals ({active_tf.upper()})")
    p1, p2, p3, p4 = st.columns(4)
    with p1:
        st.markdown("**Chart Patterns**")
        st.write(", ".join(active_res["patterns"]) if active_res["patterns"] else "No classical chart pattern triggered on this timeframe.")
    with p2:
        st.markdown("**Breakout Candlesticks**")
        st.write(", ".join(active_res["candles"]) if active_res["candles"] else "No high-momentum candlestick pattern on latest bar.")
    with p3:
        st.markdown("**RSI Zone & Divergence**")
        st.write(", ".join(active_res["rsi_signals"]) if active_res["rsi_signals"] else f"RSI at {active_res['rsi']} — No 40/60 zone rejection or divergence.")
    with p4:
        st.markdown("**Key Levels & Fibonacci**")
        st.markdown(f"- **20 SMA / 50 SMA:** {active_res['sma20']} / {active_res['sma50']}")
        st.markdown(f"- **VWAP:** {active_res['vwap']} | **Vol Ratio:** {active_res['vol_ratio']}x")
        st.markdown(f"- **Support / Resistance:** {active_res['support']} / {active_res['resistance']}")
        for k, v in active_res["fib"].items():
            st.caption(f"Fib {k}: {v}")

    # -------------------------------------------------------------------------
    # DYNAMIC CHART WITH LEFT-SIDE INDICATOR TOGGLE POPOVER & RIGHT PRICE AXIS
    # -------------------------------------------------------------------------
    df_chart = active_res.get("df")
    if df_chart is None or df_chart.empty:
        st.error("Unable to render chart for selected timeframe.")
        return

    df_plot = df_chart.tail(120).copy()

    # Left-side Popover Button to Pin/Unpin Indicators & Sub-panels
    left_ctrl_col, title_col = st.columns([1.3, 4.7])
    with left_ctrl_col:
        with st.popover("⚙️ Indicators & Panels", use_container_width=True):
            st.markdown("**Overlay Indicators**")
            show_sma20 = st.checkbox("20 SMA", value=True, key="tog_sma20")
            show_sma50 = st.checkbox("50 SMA", value=True, key="tog_sma50")
            show_vwap = st.checkbox("VWAP", value=True, key="tog_vwap")
            show_bb = st.checkbox("Bollinger Bands (Upper/Lower)", value=True, key="tog_bb")
            st.divider()
            st.markdown("**Lower Indicator Panels**")
            show_vol = st.checkbox("Volume Panel", value=True, key="tog_vol")
            show_rsi = st.checkbox("RSI (14) Panel", value=True, key="tog_rsi")
    with title_col:
        st.markdown(f"### {ticker} ({active_tf}) — {active_res['signal']} | Score: {active_res['score']}")

    # Build dynamic subplot rows based on pinned lower panels
    active_panels = ["price"]
    if show_vol:
        active_panels.append("vol")
    if show_rsi:
        active_panels.append("rsi")

    num_rows = len(active_panels)
    if num_rows == 3:
        row_heights = [0.62, 0.18, 0.20]
    elif num_rows == 2:
        row_heights = [0.75, 0.25]
    else:
        row_heights = [1.0]

    fig = make_subplots(
        rows=num_rows,
        cols=1,
        shared_xaxes=False,  # Independent X-axes so zooming price doesn't distort Volume/RSI
        vertical_spacing=0.04,
        row_heights=row_heights
    )

    # Row 1: Price Candlestick & Overlays (Price Axis on RIGHT)
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
        fig.add_trace(go.Scatter(x=df_plot.index, y=df_plot["SMA50"], name="50 SMA", line=dict(color="#ff7f0e", width=1.4)), row=1, col=1)
    if show_vwap:
        fig.add_trace(go.Scatter(x=df_plot.index, y=df_plot["VWAP"], name="VWAP", line=dict(color="#9467bd", width=1.3, dash="dot")), row=1, col=1)
    if show_bb:
        fig.add_trace(go.Scatter(x=df_plot.index, y=df_plot["BB_Upper"], name="BB Upper", line=dict(color="rgba(160,160,160,0.6)", width=1)), row=1, col=1)
        fig.add_trace(go.Scatter(x=df_plot.index, y=df_plot["BB_Lower"], name="BB Lower", line=dict(color="rgba(160,160,160,0.6)", width=1), fill="tonexty", fillcolor="rgba(200,200,200,0.12)"), row=1, col=1)

    # Entry, SL, T1, T2 horizontal levels on Price pane
    levels = [
        (active_res["entry"], f"Entry {active_res['entry']}", "#26a69a", "solid"),
        (active_res["sl"], f"SL {active_res['sl']}", "#ef5350", "dash"),
        (active_res["t1"], f"T1 {active_res['t1']}", "#00acc1", "dot"),
        (active_res["t2"], f"T2 {active_res['t2']}", "#00838f", "dot"),
    ]
    for lvl_val, lvl_lbl, lvl_col, lvl_dash in levels:
        fig.add_hline(
            y=lvl_val,
            line_color=lvl_col,
            line_dash=lvl_dash,
            line_width=1.3,
            annotation_text=lvl_lbl,
            annotation_position="top left",
            row=1, col=1
        )

    # Configure Right-side Price Y-Axis
    fig.update_yaxes(side="right", fixedrange=False, row=1, col=1)

    current_row = 2

    # Volume Panel (Left Y-Axis, Fixedrange to prevent accidental zoom distortion)
    if show_vol:
        vol_colors = ["#26a69a" if c >= o else "#ef5350" for c, o in zip(df_plot["Close"], df_plot["Open"])]
        fig.add_trace(
            go.Bar(x=df_plot.index, y=df_plot["Volume"], name="Volume", marker_color=vol_colors, showlegend=False),
            row=current_row, col=1
        )
        fig.update_yaxes(side="left", fixedrange=True, title_text="Vol", row=current_row, col=1)
        fig.update_xaxes(fixedrange=True, showticklabels=(current_row == num_rows), row=current_row, col=1)
        current_row += 1

    # RSI Panel (Left Y-Axis, Fixed 0-100 range with 40/60 Zones)
    if show_rsi:
        fig.add_trace(
            go.Scatter(x=df_plot.index, y=df_plot["RSI"], name="RSI (14)", line=dict(color="#eab308", width=1.6), showlegend=False),
            row=current_row, col=1
        )
        fig.add_hline(y=60, line_color="#26a69a", line_dash="dash", line_width=1.1, annotation_text="60 Bull Zone", annotation_position="top left", row=current_row, col=1)
        fig.add_hline(y=40, line_color="#ef5350", line_dash="dash", line_width=1.1, annotation_text="40 Bear Zone", annotation_position="bottom left", row=current_row, col=1)
        fig.update_yaxes(side="left", range=[20, 85], fixedrange=True, title_text="RSI", row=current_row, col=1)
        fig.update_xaxes(fixedrange=True, showticklabels=True, row=current_row, col=1)

    fig.update_layout(
        height=640,
        margin=dict(l=45, r=55, t=20, b=30),
        xaxis_rangeslider_visible=False,
        dragmode="pan",
        legend=dict(orientation="h", yanchor="bottom", y=1.01, xanchor="left", x=0.0),
        hovermode="x unified"
    )

    st.plotly_chart(
        fig,
        use_container_width=True,
        config={"scrollZoom": True, "displayModeBar": True}
    )

# -----------------------------------------------------------------------------
# ROUTER
# -----------------------------------------------------------------------------
if st.session_state.selected_stock:
    render_deep_dive(st.session_state.selected_stock)
else:
    render_main_dashboard()
