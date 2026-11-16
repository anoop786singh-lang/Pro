मैंने आपके बताए सभी फीचर्स के साथ पूरा आर्किटेक्चर अपडेट कर दिया है। अब आपके टर्मिनल में कलर-कोडेड मैट्रिक्स, टॉगल होने वाले सब-प्लॉट्स, और टॉप-डाउन स्कैनर शामिल हैं।.
1. इंडिकेटर अपडेट (core/indicators.py)```python
import numpy as np
import pandas as pd
def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
if df.empty or len(df) < 30:
return df
out = df.copy()
close = out["Close"]
high = out["High"]
low = out["Low"]
out["EMA_20"] = close.ewm(span=20, adjust=False).mean()
out["EMA_50"] = close.ewm(span=50, adjust=False).mean()
out["EMA_200"] = close.ewm(span=200, adjust=False).mean()
bb_mid = close.rolling(window=20).mean()
bb_std = close.rolling(window=20).std()
out["BB_MID"] = bb_mid
out["BB_UPPER"] = bb_mid + (2 * bb_std)
out["BB_LOWER"] = bb_mid - (2 * bb_std)
delta = close.diff()
gain = delta.clip(lower=0).ewm(alpha=1 / 14, adjust=False).mean()
loss = (-delta.clip(upper=0)).ewm(alpha=1 / 14, adjust=False).mean()
rs = gain / loss.replace(0, np.nan)
out["RSI"] = 100 - (100 / (1 + rs))
ema12 = close.ewm(span=12, adjust=False).mean()
ema26 = close.ewm(span=26, adjust=False).mean()
out["MACD"] = ema12 - ema26
out["MACD_SIGNAL"] = out["MACD"].ewm(span=9, adjust=False).mean()
out["MACD_HIST"] = out["MACD"] - out["MACD_SIGNAL"]
prev_close = close.shift(1)
tr = pd.concat(
[high - low, (high - prev_close).abs(), (low - prev_close).abs()],
axis=1,
).max(axis=1)
out["ATR"] = tr.ewm(alpha=1 / 14, adjust=False).mean()
up_move = high.diff()
down_move = -low.diff()
plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
minus_dm = np.where(
(down_move > up_move) & (down_move > 0), down_move, 0.0
)
atr_smooth = tr.ewm(alpha=1 / 14, adjust=False).mean().replace(0, np.nan)
plus_di = (
100
* pd.Series(plus_dm, index=out.index).ewm(
alpha=1 / 14, adjust=False
).mean()
/ atr_smooth
)
minus_di = (
100
* pd.Series(minus_dm, index=out.index).ewm(
alpha=1 / 14, adjust=False
).mean()
/ atr_smooth
)
dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
out["ADX"] = dx.ewm(alpha=1 / 14, adjust=False).mean()
return out

### 2. मुख्य टर्मिनल और स्कैनर (`app.py`)
```python
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st
from core.data_fetcher import fetch_all_timeframes
from core.signal_engine import compute_master_and_risk, evaluate_timeframe
from settings import settings

st.set_page_config(page_title=settings.PROJECT_NAME, layout="wide")

NSE_SCANNER_UNIVERSE = [
    "RELIANCE.NS",
    "TCS.NS",
    "HDFCBANK.NS",
    "ICICIBANK.NS",
    "INFY.NS",
    "SBIN.NS",
    "BHARTIARTL.NS",
    "ITC.NS",
    "LT.NS",
    "KOTAKBANK.NS",
    "AXISBANK.NS",
    "HINDUNILVR.NS",
    "BAJFINANCE.NS",
    "MARUTI.NS",
    "SUNPHARMA.NS",
    "TATAMOTORS.NS",
    "TITAN.NS",
    "NTPC.NS",
    "POWERGRID.NS",
    "ULTRACEMCO.NS",
    "ASIANPAINT.NS",
    "WIPRO.NS",
    "HCLTECH.NS",
    "ADANIENT.NS",
    "ADANIPORTS.NS",
    "ONGC.NS",
    "COALINDIA.NS",
    "JSWSTEEL.NS",
    "TATASTEEL.NS",
    "M&M.NS",
]


def style_signal_cell(val: str) -> str:
    v = str(val).upper().strip()
    if v == "STRONG BUY":
        return "background-color: #006400; color: #ffffff; font-weight: bold;"
    elif v == "BUY":
        return "background-color: #198754; color: #ffffff; font-weight: bold;"
    elif v == "STRONG SELL":
        return "background-color: #8b0000; color: #ffffff; font-weight: bold;"
    elif v == "SELL":
        return "background-color: #dc3545; color: #ffffff; font-weight: bold;"
    return "background-color: #2b3035; color: #adb5bd;"


def evaluate_bb_and_breakout_confluence(
    df: pd.DataFrame, master_signal: str
) -> tuple[bool, str, str]:
    if df.empty or len(df) < 25 or "BB_UPPER" not in df.columns:
        return False, "N/A", "None"

    row = df.iloc[-1]
    prev = df.iloc[-2]
    close = float(row["Close"])
    rsi = float(row["RSI"])
    bb_upper = float(row["BB_UPPER"])
    bb_lower = float(row["BB_LOWER"])
    bb_mid = float(row["BB_MID"])

    recent_high = float(df["High"].iloc[-21:-1].max())
    recent_low = float(df["Low"].iloc[-21:-1].min())

    is_bull = "BUY" in master_signal
    is_bear = "SELL" in master_signal

    bb_status = "Inside Bands"
    breakout_status = "Range"
    qualified = False

    if is_bull:
        if close > bb_upper or (
            prev["Close"] <= prev["BB_MID"] and close > bb_mid
        ):
            bb_status = (
                "Upper Band Breakout" if close > bb_upper else "Mid-BB Reclaim"
            )
        if close > recent_high:
            breakout_status = "20-Bar Resistance Breakout"
        elif close > prev["High"] and row["Close"] > row["Open"]:
            breakout_status = "Bullish Candle Breakout"

        if (52 <= rsi <= 75) and (
            bb_status != "Inside Bands" or "Breakout" in breakout_status
        ):
            qualified = True

    elif is_bear:
        if close < bb_lower or (
            prev["Close"] >= prev["BB_MID"] and close < bb_mid
        ):
            bb_status = (
                "Lower Band Breakdown" if close < bb_lower else "Mid-BB Rejection"
            )
        if close < recent_low:
            breakout_status = "20-Bar Support Breakdown"
        elif close < prev["Low"] and row["Close"] < row["Open"]:
            breakout_status = "Bearish Candle Breakdown"

        if (25 <= rsi <= 48) and (
            bb_status != "Inside Bands" or "Breakdown" in breakout_status
        ):
            qualified = True

    return qualified, bb_status, breakout_status


@st.cache_data(ttl=180, show_spinner=False)
def run_nse_topdown_scanner(exec_tf: str) -> pd.DataFrame:
    rows = []
    for sym in NSE_SCANNER_UNIVERSE:
        raw = fetch_all_timeframes(sym)
        if not raw or exec_tf not in raw or raw[exec_tf].empty:
            continue

        mtf_res = {tf: evaluate_timeframe(df) for tf, df in raw.items()}
        if mtf_res[exec_tf]["price"] == 0:
            continue

        master = compute_master_and_risk(mtf_res, exec_tf)
        m_sig = master["master_signal"]
        if m_sig == "NEUTRAL":
            continue

        exec_df = mtf_res[exec_tf]["df"]
        qualified, bb_stat, bo_stat = evaluate_bb_and_breakout_confluence(
            exec_df, m_sig
        )
        if not qualified:
            continue

        top_pat = (
            mtf_res[exec_tf]["patterns"][0]["pattern"]
            if mtf_res[exec_tf]["patterns"]
            else "None"
        )

        rows.append(
            {
                "Stock": sym.replace(".NS", ""),
                "LTP": master["entry"],
                "Master Signal": m_sig,
                "Conf %": master["confidence_score"],
                "1WK": mtf_res.get("1WK", {}).get("signal", "NEUTRAL"),
                "1D": mtf_res.get("1D", {}).get("signal", "NEUTRAL"),
                "1H": mtf_res.get("1H", {}).get("signal", "NEUTRAL"),
                "15M": mtf_res.get("15M", {}).get("signal", "NEUTRAL"),
                "RSI": mtf_res[exec_tf]["rsi"],
                "BB Status": bb_stat,
                "Trigger / Pattern": f"{bo_stat} ({top_pat})",
                "Entry": master["entry"],
                "SL": master["stop_loss"],
                "Target 1": master["target_1"],
            }
        )

    if not rows:
        return pd.DataFrame()

    df_scan = pd.DataFrame(rows)
    return df_scan.sort_values(by="Conf %", ascending=False).reset_index(
        drop=True
    )


st.sidebar.title(f"{settings.PROJECT_NAME} v{settings.VERSION}")
watchlist_map = {
    f"{item['label']} ({item['category']})": item["symbol"]
    for item in settings.CORE_WATCHLIST
}
selected_label = st.sidebar.selectbox("Instrument", list(watchlist_map.keys()))
custom_symbol = st.sidebar.text_input("Or Custom Ticker", "")
symbol = (
    custom_symbol.strip().upper()
    if custom_symbol.strip()
    else watchlist_map[selected_label]
)

exec_tf = st.sidebar.selectbox(
    "Execution Timeframe", list(settings.TIMEFRAMES.keys()), index=1
)
capital = st.sidebar.number_input(
    "Trading Capital (INR)", value=settings.INITIAL_CAPITAL
)
risk_pct = st.sidebar.slider(
    "Max Risk Per Trade (%)", 0.5, 5.0, settings.MAX_RISK_PER_TRADE_PCT
)

st.sidebar.divider()
st.sidebar.subheader("Chart Overlays & Panels")
show_bb = st.sidebar.checkbox("Show Bollinger Bands", value=True)
show_levels = st.sidebar.checkbox("Show Entry / SL / Targets", value=True)
show_volume = st.sidebar.checkbox("Show Volume Panel", value=True)
show_rsi = st.sidebar.checkbox("Show RSI Panel", value=True)

raw_data = fetch_all_timeframes(symbol)
mtf_results = {tf: evaluate_timeframe(df) for tf, df in raw_data.items()}

if mtf_results[exec_tf]["price"] == 0:
    st.error("Unable to fetch data. Verify ticker.")
    st.stop()

master = compute_master_and_risk(mtf_results, exec_tf, capital, risk_pct)

st.title(f"Institutional Terminal — {symbol}")
k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("LTP", f"{master['entry']:,.2f}")
k2.metric("Master Signal", master["master_signal"])
k3.metric("Confidence", f"{master['confidence_score']}%")
k4.metric("Recommended Qty", f"{master['position_qty']:,}")
k5.metric("Risk Amount", f"{master['risk_amount']:,.0f}")

st.divider()

st.subheader(f"NSE Top-Down High-Accuracy Scanner ({exec_tf} Execution)")
with st.spinner("Scanning NSE universe for RSI + BB + Breakout confluence..."):
    scanner_df = run_nse_topdown_scanner(exec_tf)

sig_cols = ["Master Signal", "1WK", "1D", "1H", "15M"]

if scanner_df.empty:
    st.info(
        "No high-accuracy Buy/Sell confluence candidates found in current"
        " cycle."
    )
else:
    compact_cols = [
        "Stock",
        "LTP",
        "Master Signal",
        "Conf %",
        "1D",
        "1H",
        "15M",
        "RSI",
        "BB Status",
        "Trigger / Pattern",
    ]
    compact_df = scanner_df[compact_cols].head(5)
    st.dataframe(
        compact_df.style.map(
            style_signal_cell, subset=["Master Signal", "1D", "1H", "15M"]
        ),
        use_container_width=True,
        hide_index=True,
    )

    with st.expander(
        f"Expand Full NSE Scanner Matrix ({len(scanner_df)} Qualified Stocks)",
        expanded=False,
    ):
        st.dataframe(
            scanner_df.style.map(style_signal_cell, subset=sig_cols),
            use_container_width=True,
            hide_index=True,
        )

st.divider()

col_matrix, col_risk = st.columns([1.3, 1])
with col_matrix:
    st.subheader("Multi-Timeframe Signal Matrix")
    matrix_rows = []
    for tf, res in mtf_results.items():
        pat_name = (
            res["patterns"][0]["pattern"] if res["patterns"] else "-"
        )
        matrix_rows.append(
            {
                "Timeframe": tf,
                "Signal": res["signal"],
                "Confidence": f"{res['confidence']}%",
                "Score": res["score"],
                "RSI": res["rsi"],
                "Pattern": pat_name,
            }
        )
    matrix_df = pd.DataFrame(matrix_rows)
    st.dataframe(
        matrix_df.style.map(style_signal_cell, subset=["Signal"]),
        use_container_width=True,
        hide_index=True,
    )

with col_risk:
    st.subheader("Dynamic Targets & Risk Management")
    levels_df = pd.DataFrame(
        [
            {"Level": "Entry Price", "Price": master["entry"]},
            {"Level": "Stop Loss", "Price": master["stop_loss"]},
            {"Level": "Target 1", "Price": master["target_1"]},
            {"Level": "Target 2", "Price": master["target_2"]},
            {"Level": "Target 3", "Price": master["target_3"]},
        ]
    )
    st.dataframe(levels_df, use_container_width=True, hide_index=True)

chart_df = mtf_results[exec_tf]["df"].tail(120)

rows_count = 1 + int(show_volume) + int(show_rsi)
if rows_count == 1:
    row_heights = [1.0]
elif rows_count == 2:
    row_heights = [0.76, 0.24]
else:
    row_heights = [0.64, 0.16, 0.20]

fig = make_subplots(
    rows=rows_count,
    cols=1,
    shared_xaxes=True,
    vertical_spacing=0.03,
    row_heights=row_heights,
)

fig.add_trace(
    go.Candlestick(
        x=chart_df.index,
        open=chart_df["Open"],
        high=chart_df["High"],
        low=chart_df["Low"],
        close=chart_df["Close"],
        increasing_line_color="#26a69a",
        decreasing_line_color="#ef5350",
        name="Price",
    ),
    row=1,
    col=1,
)

if show_bb and "BB_UPPER" in chart_df.columns:
    fig.add_trace(
        go.Scatter(
            x=chart_df.index,
            y=chart_df["BB_UPPER"],
            line=dict(color="rgba(100, 181, 246, 0.6)", width=1),
            name="BB Upper",
        ),
        row=1,
        col=1,
    )
    fig.add_trace(
        go.Scatter(
            x=chart_df.index,
            y=chart_df["BB_MID"],
            line=dict(color="rgba(255, 193, 7, 0.7)", width=1, dash="dot"),
            name="BB Mid (20)",
        ),
        row=1,
        col=1,
    )
    fig.add_trace(
        go.Scatter(
            x=chart_df.index,
            y=chart_df["BB_LOWER"],
            line=dict(color="rgba(100, 181, 246, 0.6)", width=1),
            fill="tonexty",
            fillcolor="rgba(100, 181, 246, 0.06)",
            name="BB Lower",
        ),
        row=1,
        col=1,
    )

if show_levels:
    fig.add_hline(
        y=master["entry"],
        line_dash="solid",
        line_color="#2196f3",
        annotation_text="ENTRY",
        row=1,
        col=1,
    )
    fig.add_hline(
        y=master["stop_loss"],
        line_dash="dash",
        line_color="#ef5350",
        annotation_text="SL",
        row=1,
        col=1,
    )
    fig.add_hline(
        y=master["target_1"],
        line_dash="dot",
        line_color="#26a69a",
        annotation_text="T1",
        row=1,
        col=1,
    )
    fig.add_hline(
        y=master["target_2"],
        line_dash="dot",
        line_color="#00e676",
        annotation_text="T2",
        row=1,
        col=1,
    )
    fig.add_hline(
        y=master["target_3"],
        line_dash="dot",
        line_color="#00c853",
        annotation_text="T3",
        row=1,
        col=1,
    )

current_row = 2

if show_volume:
    vol_colors = [
        "#26a69a" if c >= o else "#ef5350"
        for c, o in zip(chart_df["Close"], chart_df["Open"])
    ]
    fig.add_trace(
        go.Bar(
            x=chart_df.index,
            y=chart_df["Volume"],
            marker_color=vol_colors,
            name="Volume",
            opacity=0.75,
        ),
        row=current_row,
        col=1,
    )
    fig.update_yaxes(title_text="Vol", row=current_row, col=1)
    current_row += 1

if show_rsi:
    fig.add_trace(
        go.Scatter(
            x=chart_df.index,
            y=chart_df["RSI"],
            line=dict(color="#ab47bc", width=1.8),
            name="RSI (14)",
        ),
        row=current_row,
        col=1,
    )
    fig.add_hline(
        y=70,
        line_dash="dash",
        line_color="rgba(239, 83, 80, 0.6)",
        row=current_row,
        col=1,
    )
    fig.add_hline(
        y=30,
        line_dash="dash",
        line_color="rgba(38, 166, 154, 0.6)",
        row=current_row,
        col=1,
    )
    fig.update_yaxes(title_text="RSI", range=[0, 100], row=current_row, col=1)

chart_height = 680 if rows_count > 1 else 560
fig.update_layout(
    height=chart_height,
    xaxis_rangeslider_visible=False,
    template="plotly_dark",
    margin=dict(l=10, r=10, t=25, b=10),
    legend=dict(
        orientation="h", yanchor="bottom", y=1.01, xanchor="right", x=1
    ),
)
st.plotly_chart(fig, use_container_width=True)

