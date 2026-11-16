import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# -----------------------------------------------------------------------------
# PAGE CONFIGURATION
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="Market Master Pro | MTF Terminal",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
        .block-container { padding-top: 1.2rem; padding-bottom: 1rem; }
        div[data-testid="stMetricValue"] { font-size: 1.4rem; font-weight: 700; }
        .signal-badge {
            padding: 6px 12px;
            border-radius: 6px;
            font-weight: 700;
            text-align: center;
            display: inline-block;
        }
    </style>
    """,
    unsafe_allow_html=True,
)

# -----------------------------------------------------------------------------
# WATCHLIST CONFIGURATION
# -----------------------------------------------------------------------------
WATCHLIST = {
    "NIFTY 50": "^NSEI",
    "BANK NIFTY": "^NSEBANK",
    "RELIANCE": "RELIANCE.NS",
    "HDFCBANK": "HDFCBANK.NS",
    "INFY": "INFY.NS",
    "TCS": "TCS.NS",
    "ICICIBANK": "ICICIBANK.NS",
    "SBIN": "SBIN.NS",
    "BHARTIARTL": "BHARTIARTL.NS",
    "ITC": "ITC.NS",
    "LT": "LT.NS",
    "AXISBANK": "AXISBANK.NS",
    "KOTAKBANK": "KOTAKBANK.NS",
    "TATAMOTORS": "TATAMOTORS.NS",
    "SUNPHARMA": "SUNPHARMA.NS",
    "MARUTI": "MARUTI.NS",
    "TITAN": "TITAN.NS",
    "BAJFINANCE": "BAJFINANCE.NS",
    "HINDUNILVR": "HINDUNILVR.NS",
    "NTPC": "NTPC.NS",
    "TATASTEEL": "TATASTEEL.NS",
    "VEDL": "VEDL.NS",
    "ADANIENT": "ADANIENT.NS",
    "WIPRO": "WIPRO.NS",
    "HCLTECH": "HCLTECH.NS",
}

TIMEFRAME_MAP = {
    "15M": ("15m", "15d"),
    "1H": ("1h", "60d"),
    "1D": ("1d", "1y"),
    "1WK": ("1wk", "3y"),
}

if "selected_ticker" not in st.session_state:
    st.session_state.selected_ticker = "RELIANCE"
if "selected_tf" not in st.session_state:
    st.session_state.selected_tf = "1D"

# -----------------------------------------------------------------------------
# TECHNICAL INDICATORS & SIGNAL ENGINE
# -----------------------------------------------------------------------------
def compute_indicators(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    df["SMA20"] = df["Close"].rolling(20).mean()
    std20 = df["Close"].rolling(20).std()
    df["BB_Upper"] = df["SMA20"] + 2 * std20
    df["BB_Lower"] = df["SMA20"] - 2 * std20

    delta = df["Close"].diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = (-delta.clip(upper=0)).rolling(14).mean()
    rs = gain / loss.replace(0, np.nan)
    df["RSI"] = 100 - (100 / (1 + rs))

    high_low = df["High"] - df["Low"]
    high_close = (df["High"] - df["Close"].shift()).abs()
    low_close = (df["Low"] - df["Close"].shift()).abs()
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    df["ATR"] = tr.rolling(14).mean()
    return df


def evaluate_signal(df: pd.DataFrame) -> tuple[str, int, float]:
    if df is None or len(df) < 25:
        return "NEUTRAL", 0, np.nan

    last = df.iloc[-1]
    prev = df.iloc[-2]
    score = 0

    # Trend vs 20 SMA
    if last["Close"] > last["SMA20"]:
        score += 1
    elif last["Close"] < last["SMA20"]:
        score -= 1

    # RSI Momentum
    rsi_val = float(last["RSI"]) if pd.notna(last["RSI"]) else 50.0
    if rsi_val >= 60:
        score += 1
    elif rsi_val <= 40:
        score -= 1

    # Bollinger Breakout / Reversal
    if last["Close"] > last["BB_Upper"] or (prev["Close"] < prev["BB_Lower"] and last["Close"] > last["BB_Lower"]):
        score += 1
    elif last["Close"] < last["BB_Lower"] or (prev["Close"] > prev["BB_Upper"] and last["Close"] < last["BB_Lower"]):
        score -= 1

    # Candle Confirmation
    if last["Close"] > last["Open"] and last["Close"] > prev["High"]:
        score += 1
    elif last["Close"] < last["Open"] and last["Close"] < prev["Low"]:
        score -= 1

    if score >= 3:
        return "STRONG BUY", score, round(rsi_val, 2)
    elif score >= 1:
        return "BUY", score, round(rsi_val, 2)
    elif score <= -3:
        return "STRONG SELL", score, round(rsi_val, 2)
    elif score <= -1:
        return "SELL", score, round(rsi_val, 2)
    return "NEUTRAL", 0, round(rsi_val, 2)


def calculate_trade_levels(df: pd.DataFrame, signal: str) -> dict:
    last = df.iloc[-1]
    entry = float(last["Close"])
    atr = float(last["ATR"]) if pd.notna(last["ATR"]) and last["ATR"] > 0 else entry * 0.015

    if "SELL" in signal:
        sl = round(entry + 1.5 * atr, 2)
        t1 = round(entry - 2.0 * atr, 2)
        t2 = round(entry - 3.5 * atr, 2)
    else:
        sl = round(entry - 1.5 * atr, 2)
        t1 = round(entry + 2.0 * atr, 2)
        t2 = round(entry + 3.5 * atr, 2)

    return {"entry": round(entry, 2), "sl": sl, "t1": t1, "t2": t2}


@st.cache_data(ttl=300, show_spinner=False)
def fetch_ohlcv(symbol: str, interval: str, period: str) -> pd.DataFrame:
    df = yf.download(symbol, interval=interval, period=period, progress=False, auto_adjust=True)
    if df.empty:
        return df
    return compute_indicators(df)


@st.cache_data(ttl=300, show_spinner=False)
def build_full_matrix() -> pd.DataFrame:
    rows = []
    for name, symbol in WATCHLIST.items():
        tf_signals = {}
        tf_scores = []
        daily_df = None
        daily_rsi = np.nan

        for tf_label, (interval, period) in TIMEFRAME_MAP.items():
            df = fetch_ohlcv(symbol, interval, period)
            sig, sc, rsi_val = evaluate_signal(df)
            tf_signals[tf_label] = sig
            tf_scores.append(sc)
            if tf_label == "1D":
                daily_df = df
                daily_rsi = rsi_val

        total_score = sum(tf_scores)
        if total_score >= 6:
            overall = "STRONG BUY"
        elif total_score >= 2:
            overall = "BUY"
        elif total_score <= -6:
            overall = "STRONG SELL"
        elif total_score <= -2:
            overall = "SELL"
        else:
            overall = "NEUTRAL"

        if daily_df is not None and not daily_df.empty:
            levels = calculate_trade_levels(daily_df, overall)
            ltp = levels["entry"]
        else:
            levels = {"entry": np.nan, "sl": np.nan, "t1": np.nan, "t2": np.nan}
            ltp = np.nan

        rows.append(
            {
                "Stock": name,
                "Symbol": symbol,
                "LTP": ltp,
                "15M": tf_signals["15M"],
                "1H": tf_signals["1H"],
                "1D": tf_signals["1D"],
                "1WK": tf_signals["1WK"],
                "Score": total_score,
                "Master Signal": overall,
                "RSI (14)": daily_rsi,
                "Entry": levels["entry"],
                "SL": levels["sl"],
                "T1": levels["t1"],
                "T2": levels["t2"],
            }
        )
    return pd.DataFrame(rows)


def style_matrix(df: pd.DataFrame):
    def color_signal(val):
        if val == "STRONG BUY":
            return "background-color: #0f5132; color: #ffffff; font-weight: 700;"
        if val == "BUY":
            return "background-color: #198754; color: #ffffff; font-weight: 600;"
        if val == "STRONG SELL":
            return "background-color: #842029; color: #ffffff; font-weight: 700;"
        if val == "SELL":
            return "background-color: #dc3545; color: #ffffff; font-weight: 600;"
        if val == "NEUTRAL":
            return "background-color: #e9ecef; color: #495057;"
        return ""

    signal_cols = ["15M", "1H", "1D", "1WK", "Master Signal"]
    return (
        df.style.map(color_signal, subset=signal_cols)
        .format(
            {
                "LTP": "{:,.2f}",
                "RSI (14)": "{:.2f}",
                "Entry": "{:,.2f}",
                "SL": "{:,.2f}",
                "T1": "{:,.2f}",
                "T2": "{:,.2f}",
            },
            na_rep="-",
        )
    )


# -----------------------------------------------------------------------------
# FULL-PAGE MODAL DIALOG FOR EXCEL-LIKE MATRIX
# -----------------------------------------------------------------------------
@st.dialog("Full-Page Multi-Timeframe Signal Matrix", width="large")
def open_full_page_matrix(matrix_df: pd.DataFrame):
    f1, f2, f3 = st.columns([2, 2, 3])
    with f1:
        sig_filter = st.multiselect(
            "Filter Master Signal",
            ["STRONG BUY", "BUY", "NEUTRAL", "SELL", "STRONG SELL"],
            default=[],
        )
    with f2:
        search_txt = st.text_input("Search Stock", placeholder="e.g., RELIANCE, TCS")
    with f3:
        st.caption("Select any row to load its interactive chart and trade levels immediately.")

    filtered = matrix_df.copy()
    if sig_filter:
        filtered = filtered[filtered["Master Signal"].isin(sig_filter)]
    if search_txt:
        filtered = filtered[filtered["Stock"].str.contains(search_txt.strip().upper(), na=False)]

    display_df = filtered.drop(columns=["Symbol"]).reset_index(drop=True)
    selection = st.dataframe(
        style_matrix(display_df),
        use_container_width=True,
        height=620,
        hide_index=True,
        on_select="rerun",
        selection_mode="single-row",
    )

    if selection and selection.selection.rows:
        chosen_idx = selection.selection.rows[0]
        chosen_stock = display_df.iloc[chosen_idx]["Stock"]
        if chosen_stock != st.session_state.selected_ticker:
            st.session_state.selected_ticker = chosen_stock
            st.rerun()


# -----------------------------------------------------------------------------
# SIDEBAR: RISK SETTINGS & SCROLLABLE WATCHLIST
# -----------------------------------------------------------------------------
with st.sidebar:
    st.subheader("Risk & Capital Settings")
    capital = st.number_input("Trading Capital", min_value=1000.0, value=100000.0, step=5000.0)
    risk_pct = st.slider("Risk per Trade (%)", min_value=0.25, max_value=5.0, value=1.0, step=0.25)

    st.divider()
    st.subheader("Watchlist")
    if st.button("Refresh All Signals", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

    matrix_df = build_full_matrix()

    for _, row in matrix_df.iterrows():
        stock_name = row["Stock"]
        msig = row["Master Signal"]
        badge = "🟢" if "BUY" in msig else ("🔴" if "SELL" in msig else "⚪")
        btn_type = "primary" if stock_name == st.session_state.selected_ticker else "secondary"
        if st.button(
            f"{badge} {stock_name}  |  {msig}",
            key=f"wl_{stock_name}",
            use_container_width=True,
            type=btn_type,
        ):
            st.session_state.selected_ticker = stock_name
            st.rerun()


# -----------------------------------------------------------------------------
# TOP HEADER BAR: TICKER, TIMEFRAME, SIGNAL & MATRIX EXPAND BUTTON
# -----------------------------------------------------------------------------
ticker_names = list(WATCHLIST.keys())
h1, h2, h3, h4, h5 = st.columns([2.2, 1.3, 1.5, 1.8, 1.7])

with h1:
    selected_stock = st.selectbox(
        "Active Symbol",
        ticker_names,
        index=ticker_names.index(st.session_state.selected_ticker),
        label_visibility="collapsed",
    )
    if selected_stock != st.session_state.selected_ticker:
        st.session_state.selected_ticker = selected_stock
        st.rerun()

with h2:
    tf_keys = list(TIMEFRAME_MAP.keys())
    selected_tf = st.selectbox(
        "Timeframe",
        tf_keys,
        index=tf_keys.index(st.session_state.selected_tf),
        label_visibility="collapsed",
    )
    if selected_tf != st.session_state.selected_tf:
        st.session_state.selected_tf = selected_tf
        st.rerun()

symbol = WATCHLIST[st.session_state.selected_ticker]
interval, period = TIMEFRAME_MAP[st.session_state.selected_tf]
chart_df = fetch_ohlcv(symbol, interval, period)
tf_signal, tf_score, tf_rsi = evaluate_signal(chart_df)

with h3:
    if not chart_df.empty:
        curr_price = float(chart_df["Close"].iloc[-1])
        prev_price = float(chart_df["Close"].iloc[-2]) if len(chart_df) > 1 else curr_price
        pct_chg = ((curr_price - prev_price) / prev_price) * 100 if prev_price else 0.0
        st.metric(
            label=f"{st.session_state.selected_ticker} ({st.session_state.selected_tf})",
            value=f"{curr_price:,.2f}",
            delta=f"{pct_chg:+.2f}%",
        )

with h4:
    sig_color = "#198754" if "BUY" in tf_signal else ("#dc3545" if "SELL" in tf_signal else "#6c757d")
    st.markdown(
        f"""
        <div style="margin-top: 4px;">
            <span style="font-size: 0.8rem; color: #6c757d;">{st.session_state.selected_tf} Signal (Score: {tf_score})</span><br>
            <span class="signal-badge" style="background-color: {sig_color}; color: white;">{tf_signal}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

with h5:
    if st.button("⤢ Full-Page MTF Matrix", use_container_width=True, type="primary"):
        open_full_page_matrix(matrix_df)

# -----------------------------------------------------------------------------
# INDICATOR & TRADE LEVEL TOGGLES
# -----------------------------------------------------------------------------
t1_col, t2_col, t3_col, t4_col, t5_col, t6_col = st.columns([1.1, 1, 1, 1.2, 1.1, 1.1])
show_bb = t1_col.toggle("BB (20, 2)", value=True)
show_vol = t2_col.toggle("Volume", value=True)
show_rsi = t3_col.toggle("RSI (14)", value=True)
show_levels = t4_col.toggle("Trade Levels", value=True)
show_fib = t5_col.toggle("Auto Fib", value=False)
bars_to_show = t6_col.selectbox("Bars", [60, 120, 200, 300], index=1, label_visibility="collapsed")

# -----------------------------------------------------------------------------
# INTERACTIVE CANDLESTICK CHART WITH PERSISTENT TRADE LEVELS
# -----------------------------------------------------------------------------
if not chart_df.empty:
    plot_df = chart_df.tail(bars_to_show).copy()
    levels = calculate_trade_levels(chart_df, tf_signal)

    # Position sizing readout
    risk_amount = capital * (risk_pct / 100.0)
    per_share_risk = abs(levels["entry"] - levels["sl"])
    qty = int(risk_amount // per_share_risk) if per_share_risk > 0 else 0

    if show_levels:
        lv1, lv2, lv3, lv4, lv5 = st.columns(5)
        lv1.metric("ENTRY", f"{levels['entry']:,.2f}")
        lv2.metric("STOP LOSS (SL)", f"{levels['sl']:,.2f}")
        lv3.metric("TARGET 1 (T1)", f"{levels['t1']:,.2f}")
        lv4.metric("TARGET 2 (T2)", f"{levels['t2']:,.2f}")
        lv5.metric("Position Size (Qty)", f"{qty:,} units")

    rows_count = 1 + int(show_vol) + int(show_rsi)
    row_heights = [0.64]
    if show_vol and show_rsi:
        row_heights = [0.60, 0.20, 0.20]
    elif show_vol or show_rsi:
        row_heights = [0.75, 0.25]

    fig = make_subplots(
        rows=rows_count,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.03,
        row_heights=row_heights,
    )

    x_labels = plot_df.index.strftime("%d %b %H:%M") if st.session_state.selected_tf in ["15M", "1H"] else plot_df.index.strftime("%d %b '%y")

    fig.add_trace(
        go.Candlestick(
            x=x_labels,
            open=plot_df["Open"],
            high=plot_df["High"],
            low=plot_df["Low"],
            close=plot_df["Close"],
            name="Price",
            increasing_line_color="#089981",
            decreasing_line_color="#f23645",
        ),
        row=1,
        col=1,
    )

    if show_bb:
        fig.add_trace(
            go.Scatter(x=x_labels, y=plot_df["BB_Upper"], name="BB Upper", line=dict(color="rgba(41, 98, 255, 0.45)", width=1)),
            row=1,
            col=1,
        )
        fig.add_trace(
            go.Scatter(x=x_labels, y=plot_df["SMA20"], name="20 SMA", line=dict(color="#ff9800", width=1.4)),
            row=1,
            col=1,
        )
        fig.add_trace(
            go.Scatter(
                x=x_labels,
                y=plot_df["BB_Lower"],
                name="BB Lower",
                line=dict(color="rgba(41, 98, 255, 0.45)", width=1),
                fill="tonexty",
                fillcolor="rgba(41, 98, 255, 0.05)",
            ),
            row=1,
            col=1,
        )

    if show_fib:
        hi = float(plot_df["High"].max())
        lo = float(plot_df["Low"].min())
        diff = hi - lo
        for fib_lvl, col in [(0.236, "#9c27b0"), (0.382, "#673ab7"), (0.5, "#2196f3"), (0.618, "#009688")]:
            price_lvl = hi - diff * fib_lvl
            fig.add_hline(
                y=price_lvl,
                line_dash="dot",
                line_color=col,
                annotation_text=f"Fib {fib_lvl:.3f} ({price_lvl:,.1f})",
                annotation_position="bottom right",
                row=1,
                col=1,
            )

    if show_levels:
        level_specs = [
            (levels["t2"], f"T2 {levels['t2']:,.2f}", "#2e7d32", "dot"),
            (levels["t1"], f"T1 {levels['t1']:,.2f}", "#089981", "dash"),
            (levels["entry"], f"ENTRY {levels['entry']:,.2f}", "#2962ff", "solid"),
            (levels["sl"], f"SL {levels['sl']:,.2f}", "#f23645", "dash"),
        ]
        for y_val, label_txt, line_col, dash_style in level_specs:
            fig.add_hline(
                y=y_val,
                line_dash=dash_style,
                line_color=line_col,
                line_width=1.5,
                annotation_text=label_txt,
                annotation_position="top left",
                annotation_font=dict(color=line_col, size=11),
                row=1,
                col=1,
            )

    current_row = 2
    if show_vol:
        vol_colors = ["#089981" if c >= o else "#f23645" for c, o in zip(plot_df["Close"], plot_df["Open"])]
        fig.add_trace(
            go.Bar(x=x_labels, y=plot_df["Volume"], name="Volume", marker_color=vol_colors, opacity=0.65),
            row=current_row,
            col=1,
        )
        fig.update_yaxes(title_text="Vol", row=current_row, col=1)
        current_row += 1

    if show_rsi:
        fig.add_trace(
            go.Scatter(x=x_labels, y=plot_df["RSI"], name="RSI (14)", line=dict(color="#7e57c2", width=1.6)),
            row=current_row,
            col=1,
        )
        fig.add_hline(y=70, line_dash="dash", line_color="#f23645", line_width=1, row=current_row, col=1)
        fig.add_hline(y=30, line_dash="dash", line_color="#089981", line_width=1, row=current_row, col=1)
        fig.update_yaxes(title_text="RSI", range=[0, 100], row=current_row, col=1)

    fig.update_layout(
        height=560,
        margin=dict(l=10, r=10, t=20, b=10),
        xaxis_rangeslider_visible=False,
        dragmode="pan",
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.01, xanchor="right", x=1),
    )
    fig.update_xaxes(type="category", nticks=10, showgrid=True, gridcolor="rgba(0,0,0,0.05)")
    fig.update_yaxes(side="right", showgrid=True, gridcolor="rgba(0,0,0,0.05)", row=1, col=1)

    st.plotly_chart(
        fig,
        use_container_width=True,
        config={
            "scrollZoom": True,
            "displayModeBar": True,
            "modeBarButtonsToRemove": ["lasso2d", "select2d"],
        },
    )

# -----------------------------------------------------------------------------
# COLLAPSIBLE EXCEL-LIKE MTF SIGNAL MATRIX & BACKTEST TABS
# -----------------------------------------------------------------------------
with st.expander("⤢ Excel-Style Multi-Timeframe Signal Matrix (All Watchlist Stocks)", expanded=True):
    m_col1, m_col2 = st.columns([5, 1.5])
    m_col1.caption("Click any row to switch the active chart above without losing your workspace.")
    if m_col2.button("Open Full-Screen View ⤢", key="expander_modal_btn", use_container_width=True):
        open_full_page_matrix(matrix_df)

    inline_df = matrix_df.drop(columns=["Symbol"]).reset_index(drop=True)
    inline_sel = st.dataframe(
        style_matrix(inline_df),
        use_container_width=True,
        height=420,
        hide_index=True,
        on_select="rerun",
        selection_mode="single-row",
    )

    if inline_sel and inline_sel.selection.rows:
        picked_row = inline_sel.selection.rows[0]
        picked_stock = inline_df.iloc[picked_row]["Stock"]
        if picked_stock != st.session_state.selected_ticker:
            st.session_state.selected_ticker = picked_stock
            st.rerun()

tab_bt, tab_fin = st.tabs(["Backtest Simulator", "Financials & Details"])

with tab_bt:
    b1, b2, b3 = st.columns(3)
    buy_rsi = b1.slider("Buy Trigger RSI ≥", 40, 80, 55)
    exit_rsi = b2.slider("Exit Trigger RSI ≤", 20, 60, 45)
    sim_cap = b3.number_input("Simulation Capital", min_value=1000.0, value=float(capital), step=5000.0)

    if not chart_df.empty:
        bt_df = chart_df.dropna(subset=["RSI", "Close"]).copy()
        in_pos = False
        entry_p = 0.0
        cap = sim_cap
        trades = []
        equity = []

        for _, r in bt_df.iterrows():
            price = float(r["Close"])
            rsi_v = float(r["RSI"])
            if not in_pos and rsi_v >= buy_rsi:
                in_pos = True
                entry_p = price
            elif in_pos and rsi_v <= exit_rsi:
                pnl_pct = (price - entry_p) / entry_p
                cap *= (1 + pnl_pct)
                trades.append(pnl_pct)
                in_pos = False
            equity.append(cap)

        wins = sum(1 for t in trades if t > 0)
        win_rate = (wins / len(trades) * 100) if trades else 0.0
        net_ret = ((cap - sim_cap) / sim_cap) * 100

        s1, s2, s3, s4 = st.columns(4)
        s1.metric("Final Capital", f"{cap:,.2f}")
        s2.metric("Net Return", f"{net_ret:+.2f}%")
        s3.metric("Closed Trades", len(trades))
        s4.metric("Win Rate", f"{win_rate:.1f}%")
        st.line_chart(pd.Series(equity, index=bt_df.index, name="Equity Curve"))

with tab_fin:
    info = yf.Ticker(symbol).info
    fin_rows = [
        ("Name", info.get("longName", st.session_state.selected_ticker)),
        ("Sector", info.get("sector", "Index / Commodity")),
        ("Market Cap", f"{info['marketCap']:,}" if info.get("marketCap") else "N/A"),
        ("Trailing P/E", f"{info['trailingPE']:.2f}" if info.get("trailingPE") else "N/A"),
        ("52W High", f"{info['fiftyTwoWeekHigh']:,.2f}" if info.get("fiftyTwoWeekHigh") else "N/A"),
        ("52W Low", f"{info['fiftyTwoWeekLow']:,.2f}" if info.get("fiftyTwoWeekLow") else "N/A"),
        ("50D Avg", f"{info['fiftyDayAverage']:,.2f}" if info.get("fiftyDayAverage") else "N/A"),
        ("200D Avg", f"{info['twoHundredDayAverage']:,.2f}" if info.get("twoHundredDayAverage") else "N/A"),
    ]
    st.dataframe(pd.DataFrame(fin_rows, columns=["Metric", "Value"]), use_container_width=True, hide_index=True)
