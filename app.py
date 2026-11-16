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
show_price = st.sidebar.checkbox("Show Price Chart", value=True)
show_volume = st.sidebar.checkbox("Show Volume Panel", value=True)
show_rsi = st.sidebar.checkbox("Show RSI Panel", value=True)
show_bb = st.sidebar.checkbox("Show Bollinger Bands", value=True)
show_levels = st.sidebar.checkbox("Show Entry / SL / Targets", value=True)

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

active_panels = []
if show_price:
    active_panels.append("price")
if show_volume:
    active_panels.append("volume")
if show_rsi:
    active_panels.append("rsi")

if not active_panels:
    st.warning(
        "All chart panels are hidden. Enable at least one panel (Price,"
        " Volume, or RSI) in the sidebar."
    )
else:
    chart_df = mtf_results[exec_tf]["df"].tail(180).copy()
    fmt_str = "%d %b %H:%M" if exec_tf in ["15M", "1H"] else "%d %b %Y"
    x_labels = chart_df.index.strftime(fmt_str)

    weight_map = {"price": 0.62, "volume": 0.17, "rsi": 0.21}
    raw_weights = [weight_map[p] for p in active_panels]
    total_w = sum(raw_weights)
    row_heights = [w / total_w for w in raw_weights]
    rows_count = len(active_panels)

    fig = make_subplots(
        rows=rows_count,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.04 if rows_count > 1 else 0.0,
        row_heights=row_heights,
    )

    for idx, panel in enumerate(active_panels, start=1):
        if panel == "price":
            fig.add_trace(
                go.Candlestick(
                    x=x_labels,
                    open=chart_df["Open"],
                    high=chart_df["High"],
                    low=chart_df["Low"],
                    close=chart_df["Close"],
                    increasing=dict(
                        line=dict(color="#26a69a", width=1.2),
                        fillcolor="#26a69a",
                    ),
                    decreasing=dict(
                        line=dict(color="#ef5350", width=1.2),
                        fillcolor="#ef5350",
                    ),
                    whiskerwidth=0.4,
                    name="Price",
                ),
                row=idx,
                col=1,
            )

            if show_bb and "BB_UPPER" in chart_df.columns:
                fig.add_trace(
                    go.Scatter(
                        x=x_labels,
                        y=chart_df["BB_UPPER"],
                        line=dict(color="rgba(100, 181, 246, 0.7)", width=1.2),
                        name="BB Upper",
                    ),
                    row=idx,
                    col=1,
                )
                fig.add_trace(
                    go.Scatter(
                        x=x_labels,
                        y=chart_df["BB_MID"],
                        line=dict(
                            color="rgba(255, 193, 7, 0.8)",
                            width=1.2,
                            dash="dot",
                        ),
                        name="BB Mid (20)",
                    ),
                    row=idx,
                    col=1,
                )
                fig.add_trace(
                    go.Scatter(
                        x=x_labels,
                        y=chart_df["BB_LOWER"],
                        line=dict(color="rgba(100, 181, 246, 0.7)", width=1.2),
                        fill="tonexty",
                        fillcolor="rgba(100, 181, 246, 0.06)",
                        name="BB Lower",
                    ),
                    row=idx,
                    col=1,
                )

            if show_levels:
                fig.add_hline(
                    y=master["entry"],
                    line_dash="solid",
                    line_color="#2196f3",
                    annotation_text="ENTRY",
                    annotation_position="top left",
                    row=idx,
                    col=1,
                )
                fig.add_hline(
                    y=master["stop_loss"],
                    line_dash="dash",
                    line_color="#ef5350",
                    annotation_text="SL",
                    annotation_position="bottom left",
                    row=idx,
                    col=1,
                )
                fig.add_hline(
                    y=master["target_1"],
                    line_dash="dot",
                    line_color="#26a69a",
                    annotation_text="T1",
                    annotation_position="top left",
                    row=idx,
                    col=1,
                )
                fig.add_hline(
                    y=master["target_2"],
                    line_dash="dot",
                    line_color="#00e676",
                    annotation_text="T2",
                    annotation_position="top left",
                    row=idx,
                    col=1,
                )
                fig.add_hline(
                    y=master["target_3"],
                    line_dash="dot",
                    line_color="#00c853",
                    annotation_text="T3",
                    annotation_position="top left",
                    row=idx,
                    col=1,
                )

            fig.update_yaxes(
                side="right",
                autorange=True,
                fixedrange=False,
                showgrid=True,
                gridcolor="rgba(255, 255, 255, 0.06)",
                row=idx,
                col=1,
            )

        elif panel == "volume":
            vol_colors = [
                "#26a69a" if c >= o else "#ef5350"
                for c, o in zip(chart_df["Close"], chart_df["Open"])
            ]
            fig.add_trace(
                go.Bar(
                    x=x_labels,
                    y=chart_df["Volume"],
                    marker_color=vol_colors,
                    name="Volume",
                    opacity=0.75,
                ),
                row=idx,
                col=1,
            )
            fig.update_yaxes(
                side="right",
                title_text="Vol",
                fixedrange=False,
                showgrid=True,
                gridcolor="rgba(255, 255, 255, 0.06)",
                row=idx,
                col=1,
            )

        elif panel == "rsi":
            fig.add_trace(
                go.Scatter(
                    x=x_labels,
                    y=chart_df["RSI"],
                    line=dict(color="#ab47bc", width=1.8),
                    name="RSI (14)",
                ),
                row=idx,
                col=1,
            )
            fig.add_hline(
                y=70,
                line_dash="dash",
                line_color="rgba(239, 83, 80, 0.6)",
                row=idx,
                col=1,
            )
            fig.add_hline(
                y=30,
                line_dash="dash",
                line_color="rgba(38, 166, 154, 0.6)",
                row=idx,
                col=1,
            )
            fig.update_yaxes(
                side="right",
                title_text="RSI",
                range=[0, 100],
                fixedrange=True,
                showgrid=True,
                gridcolor="rgba(255, 255, 255, 0.06)",
                row=idx,
                col=1,
            )

    total_bars = len(x_labels)
    initial_visible_bars = min(65, total_bars)
    init_range = [
        max(0, total_bars - initial_visible_bars) - 0.5,
        total_bars - 0.5,
    ]

    fig.update_xaxes(
        type="category",
        range=init_range,
        nticks=12,
        showgrid=True,
        gridcolor="rgba(255, 255, 255, 0.06)",
        rangeslider=dict(visible=False),
    )
    fig.update_xaxes(
        rangeslider=dict(
            visible=True,
            thickness=0.05,
            bgcolor="rgba(255, 255, 255, 0.04)",
        ),
        row=rows_count,
        col=1,
    )

    chart_height = 760 if rows_count > 1 else 620
    fig.update_layout(
        height=chart_height,
        template="plotly_dark",
        dragmode="pan",
        hovermode="x unified",
        bargap=0.22,
        margin=dict(l=24, r=72, t=48, b=36),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="left",
            x=0,
        ),
    )

    st.plotly_chart(
        fig,
        use_container_width=True,
        config={"scrollZoom": True, "displayModeBar": True},
    )
