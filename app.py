import sys
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

from core.data_fetcher import fetch_all_timeframes
from core.signal_engine import compute_master_and_risk, evaluate_timeframe
from settings import settings

# --- APPLICATION CONFIGURATION ---
st.set_page_config(
    page_title=settings.PROJECT_NAME,
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown(
    """
    <style>
        .block-container {
            padding-top: 1.2rem !important;
            padding-bottom: 1.5rem !important;
            padding-left: 1.5rem !important;
            padding-right: 1.5rem !important;
            max-width: 100% !important;
        }
        footer {visibility: hidden;}
        #MainMenu {visibility: hidden;}
        div[data-testid="stToolbar"] {visibility: hidden;}
        .stDeployButton {display:none;}
        div[data-testid="stMetricValue"] {
            font-size: 1.35rem !important;
        }
        div[data-testid="stMetricLabel"] {
            font-size: 0.8rem !important;
        }
    </style>
    """,
    unsafe_allow_html=True,
)


# --- CORE UTILITIES & STYLING ---
def style_signal_cell(val: str) -> str:
    """Applies enterprise-grade conditional formatting to signal strings."""
    v: str = str(val).upper().strip()
    if v == "STRONG BUY":
        return "background-color: #006400; color: #ffffff; font-weight: bold;"
    elif v == "BUY":
        return "background-color: #198754; color: #ffffff; font-weight: bold;"
    elif v == "STRONG SELL":
        return "background-color: #8b0000; color: #ffffff; font-weight: bold;"
    elif v == "SELL":
        return "background-color: #dc3545; color: #ffffff; font-weight: bold;"
    return "background-color: #2b3035; color: #adb5bd;"


# --- TECHNICAL ANALYSIS ENGINE ---
def ensure_bollinger_bands(
    df: pd.DataFrame, period: int = 20, std_dev: float = 2.0
) -> pd.DataFrame:
    """Ensures Bollinger Bands are present in the dataframe using vectorized operations."""
    out: pd.DataFrame = df.copy()
    if out.empty or "Close" not in out.columns:
        return out
    if not {"BB_UPPER", "BB_MID", "BB_LOWER"}.issubset(out.columns):
        mid: pd.Series = (
            out["Close"].rolling(window=period, min_periods=1).mean()
        )
        std: pd.Series = (
            out["Close"].rolling(window=period, min_periods=1).std().fillna(0.0)
        )
        out["BB_MID"] = mid
        out["BB_UPPER"] = mid + (std_dev * std)
        out["BB_LOWER"] = mid - (std_dev * std)
    return out


def ensure_rsi(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    """Ensures RSI indicator is calculated accurately."""
    out: pd.DataFrame = df.copy()
    if out.empty or "Close" not in out.columns:
        return out
    if "RSI" not in out.columns or out["RSI"].isna().all():
        delta: pd.Series = out["Close"].diff()
        gain: pd.Series = (
            delta.clip(lower=0).rolling(window=period, min_periods=1).mean()
        )
        loss: pd.Series = (-delta.clip(upper=0)).rolling(
            window=period, min_periods=1
        ).mean()
        rs: pd.Series = gain / loss.replace(0, 1e-9)
        out["RSI"] = 100.0 - (100.0 / (1.0 + rs))
    return out


def evaluate_bb_and_breakout_confluence(
    df: pd.DataFrame, master_signal: str
) -> Tuple[bool, str, str]:
    """Evaluates high-confluence setups combining Bollinger Bands and Price Action."""
    df_processed = ensure_bollinger_bands(ensure_rsi(df))
    if df_processed.empty or len(df_processed) < 25:
        return False, "N/A", "None"

    row: pd.Series = df_processed.iloc[-1]
    prev: pd.Series = df_processed.iloc[-2]
    close: float = float(row["Close"])
    rsi: float = float(row["RSI"])
    bb_upper: float = float(row["BB_UPPER"])
    bb_lower: float = float(row["BB_LOWER"])
    bb_mid: float = float(row["BB_MID"])

    recent_high: float = float(df_processed["High"].iloc[-21:-1].max())
    recent_low: float = float(df_processed["Low"].iloc[-21:-1].min())

    is_bull: bool = "BUY" in master_signal
    is_bear: bool = "SELL" in master_signal

    bb_status: str = "Inside Bands"
    breakout_status: str = "Range"
    qualified: bool = False

    if is_bull:
        if (
            close > bb_upper
            or (prev["Close"] <= prev["BB_MID"] and close > bb_mid)
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
        if (
            close < bb_lower
            or (prev["Close"] >= prev["BB_MID"] and close < bb_mid)
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


# --- DATA SCANNING ---
@st.cache_data(ttl=180, show_spinner=False)
def run_scanner_universe(exec_tf: str) -> pd.DataFrame:
    """Scans the core watchlist for optimal setups."""
    rows: List[Dict] = []
    for item in settings.CORE_WATCHLIST:
        sym: str = item["symbol"]
        raw = fetch_all_timeframes(sym)
        if not raw or exec_tf not in raw or raw[exec_tf].empty:
            continue

        mtf_res = {tf: evaluate_timeframe(df) for tf, df in raw.items()}
        if mtf_res[exec_tf]["price"] == 0:
            continue

        master = compute_master_and_risk(mtf_res, exec_tf)
        m_sig: str = master["master_signal"]
        if m_sig == "NEUTRAL":
            continue

        exec_df = mtf_res[exec_tf]["df"]
        qualified, bb_stat, bo_stat = evaluate_bb_and_breakout_confluence(
            exec_df, m_sig
        )
        if not qualified:
            continue

        top_pat: str = (
            mtf_res[exec_tf]["patterns"][0]["pattern"]
            if mtf_res[exec_tf]["patterns"]
            else "None"
        )

        display_sym: str = sym.replace(".NS", "")
        rows.append(
            {
                "Stock": display_sym,
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


# --- STATE INITIALIZATION ---
if "active_symbol" not in st.session_state:
    st.session_state.active_symbol = settings.CORE_WATCHLIST[0]["symbol"]
if "active_tf" not in st.session_state:
    st.session_state.active_tf = "1D"
if "panel_price" not in st.session_state:
    st.session_state.panel_price = True
if "panel_volume" not in st.session_state:
    st.session_state.panel_volume = True
if "panel_rsi" not in st.session_state:
    st.session_state.panel_rsi = True
if "show_bb" not in st.session_state:
    st.session_state.show_bb = True
if "show_levels" not in st.session_state:
    st.session_state.show_levels = True

# --- SIDEBAR CONTROLS ---
st.sidebar.title(f"{settings.PROJECT_NAME} v{settings.VERSION}")
capital: float = st.sidebar.number_input(
    "Trading Capital (INR)", value=settings.INITIAL_CAPITAL
)
risk_pct: float = st.sidebar.slider(
    "Max Risk Per Trade (%)", 0.5, 5.0, settings.MAX_RISK_PER_TRADE_PCT
)

# --- DATA FETCHING & PROCESSING ---
raw_data = fetch_all_timeframes(st.session_state.active_symbol)
if not raw_data or all(df.empty for df in raw_data.values()):
    st.error(
        f"Unable to fetch market data for ticker: {st.session_state.active_symbol}"
    )
    st.stop()

mtf_results = {tf: evaluate_timeframe(df) for tf, df in raw_data.items()}
master = compute_master_and_risk(
    mtf_results, st.session_state.active_tf, capital, risk_pct
)

chart_source_df = ensure_bollinger_bands(
    ensure_rsi(mtf_results[st.session_state.active_tf]["df"])
)

# --- HEADER METRICS ---
hdr_c1, hdr_c2, hdr_c3, hdr_c4 = st.columns([2.2, 2.8, 1.8, 2.2])

with hdr_c1:
    display_watch = {
        f"{item['label']} ({item['symbol'].replace('.NS', '')})": item["symbol"]
        for item in settings.CORE_WATCHLIST
    }
    sym_values = list(display_watch.values())
    curr_idx: int = (
        sym_values.index(st.session_state.active_symbol)
        if st.session_state.active_symbol in sym_values
        else 0
    )
    selected_label = st.selectbox(
        "Instrument",
        options=list(display_watch.keys()),
        index=curr_idx,
        label_visibility="collapsed",
    )
    if display_watch[selected_label] != st.session_state.active_symbol:
        st.session_state.active_symbol = display_watch[selected_label]
        st.rerun()

with hdr_c2:
    tf_keys: List[str] = ["15M", "1H", "1D", "1WK"]
    available_tfs: List[str] = [
        tf for tf in tf_keys if tf in settings.TIMEFRAMES
    ] or list(settings.TIMEFRAMES.keys())
    tf_cols = st.columns(len(available_tfs))
    for i, tf in enumerate(available_tfs):
        btn_type = (
            "primary" if st.session_state.active_tf == tf else "secondary"
        )
        if tf_cols[i].button(
            tf, key=f"top_tf_{tf}", type=btn_type, use_container_width=True
        ):
            st.session_state.active_tf = tf
            st.rerun()

with hdr_c3:
    latest_close: float = (
        float(chart_source_df["Close"].iloc[-1])
        if not chart_source_df.empty
        else master["entry"]
    )
    prev_close: float = (
        float(chart_source_df["Close"].iloc[-2])
        if len(chart_source_df) > 1
        else latest_close
    )
    pct_chg: float = (
        ((latest_close - prev_close) / prev_close * 100.0)
        if prev_close
        else 0.0
    )
    st.metric(
        label=f"{st.session_state.active_symbol.replace('.NS', '')} · {st.session_state.active_tf}",
        value=f"{latest_close:,.2f}",
        delta=f"{pct_chg:+.2f}%",
    )

with hdr_c4:
    st.metric(
        label="Signal",
        value=master["master_signal"],
        delta=f"{master['confidence_score']}% Conf",
    )

# --- PANEL TOGGLES ---
tog_c1, tog_c2, tog_c3, tog_c4, tog_c5, _ = st.columns(
    [1.1, 1.2, 1.2, 1.5, 1.2, 3.8]
)
with tog_c1:
    st.session_state.panel_price = st.toggle(
        "Price", value=st.session_state.panel_price, key="tog_price"
    )
with tog_c2:
    st.session_state.panel_volume = st.toggle(
        "Volume", value=st.session_state.panel_volume, key="tog_vol"
    )
with tog_c3:
    st.session_state.panel_rsi = st.toggle(
        "RSI (14)", value=st.session_state.panel_rsi, key="tog_rsi"
    )
with tog_c4:
    st.session_state.show_bb = st.toggle(
        "BB (20, 2)", value=st.session_state.show_bb, key="tog_bb"
    )
with tog_c5:
    st.session_state.show_levels = st.toggle(
        "Levels", value=st.session_state.show_levels, key="tog_lvl"
    )

active_panels: List[str] = []
if st.session_state.panel_price:
    active_panels.append("price")
if st.session_state.panel_volume:
    active_panels.append("volume")
if st.session_state.panel_rsi:
    active_panels.append("rsi")

# --- CHART RENDERING ENGINE ---
if not active_panels:
    st.warning("All chart panels are disabled. Enable Price, Volume, or RSI above.")
else:
    chart_df = chart_source_df.tail(180).copy()
    fmt_str: str = (
        "%d %b %H:%M"
        if st.session_state.active_tf in ["15M", "1H"]
        else "%d %b '%y"
    )
    x_labels = chart_df.index.strftime(fmt_str)

    weight_map = {"price": 0.68, "volume": 0.15, "rsi": 0.17}
    raw_weights = [weight_map[p] for p in active_panels]
    total_weight: float = sum(raw_weights)
    row_heights = [w / total_weight for w in raw_weights]
    rows_count: int = len(active_panels)

    fig = make_subplots(
        rows=rows_count,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.025 if rows_count > 1 else 0.0,
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
                        line=dict(color="#089981", width=1.2), fillcolor="#089981"
                    ),
                    decreasing=dict(
                        line=dict(color="#f23645", width=1.2), fillcolor="#f23645"
                    ),
                    whiskerwidth=0.4,
                    name="Price",
                    showlegend=False,
                ),
                row=idx,
                col=1,
            )

            if st.session_state.show_bb and {
                "BB_UPPER",
                "BB_MID",
                "BB_LOWER",
            }.issubset(chart_df.columns):
                fig.add_trace(
                    go.Scatter(
                        x=x_labels,
                        y=chart_df["BB_UPPER"],
                        line=dict(color="rgba(41, 98, 255, 0.75)", width=1.2),
                        name="BB Upper",
                        hoverinfo="y",
                    ),
                    row=idx,
                    col=1,
                )
                fig.add_trace(
                    go.Scatter(
                        x=x_labels,
                        y=chart_df["BB_MID"],
                        line=dict(color="rgba(255, 109, 0, 0.85)", width=1.2),
                        name="BB Basis",
                        hoverinfo="y",
                    ),
                    row=idx,
                    col=1,
                )
                fig.add_trace(
                    go.Scatter(
                        x=x_labels,
                        y=chart_df["BB_LOWER"],
                        line=dict(color="rgba(41, 98, 255, 0.75)", width=1.2),
                        fill="tonexty",
                        fillcolor="rgba(41, 98, 255, 0.06)",
                        name="BB Lower",
                        hoverinfo="y",
                    ),
                    row=idx,
                    col=1,
                )

            if st.session_state.show_levels:
                level_specs = [
                    (
                        master["target_3"],
                        "#089981",
                        "dot",
                        f"T3 {master['target_3']:,.2f}",
                    ),
                    (
                        master["target_2"],
                        "#089981",
                        "dot",
                        f"T2 {master['target_2']:,.2f}",
                    ),
                    (
                        master["target_1"],
                        "#089981",
                        "dash",
                        f"T1 {master['target_1']:,.2f}",
                    ),
                    (
                        master["entry"],
                        "#2962ff",
                        "solid",
                        f"ENTRY {master['entry']:,.2f}",
                    ),
                    (
                        master["stop_loss"],
                        "#f23645",
                        "dash",
                        f"SL {master['stop_loss']:,.2f}",
                    ),
                ]
                for y_val, l_color, l_dash, l_text in level_specs:
                    fig.add_hline(
                        y=y_val,
                        line_dash=l_dash,
                        line_width=1.2,
                        line_color=l_color,
                        annotation_text=l_text,
                        annotation_position="top left",
                        annotation_font=dict(size=10, color=l_color),
                        row=idx,
                        col=1,
                    )

            fig.update_yaxes(
                side="right",
                autorange=True,
                fixedrange=False,
                showgrid=True,
                gridcolor="rgba(42, 46, 57, 0.08)",
                zeroline=False,
                row=idx,
                col=1,
            )

        elif panel == "volume":
            vol_colors = [
                "rgba(8, 153, 129, 0.55)" if c >= o else "rgba(242, 54, 69, 0.55)"
                for c, o in zip(chart_df["Close"], chart_df["Open"])
            ]
            fig.add_trace(
                go.Bar(
                    x=x_labels,
                    y=chart_df["Volume"],
                    marker_color=vol_colors,
                    name="Volume",
                    showlegend=False,
                ),
                row=idx,
                col=1,
            )
            fig.update_yaxes(
                side="right",
                title_text="Vol",
                fixedrange=False,
                showgrid=True,
                gridcolor="rgba(42, 46, 57, 0.08)",
                row=idx,
                col=1,
            )

        elif panel == "rsi":
            fig.add_trace(
                go.Scatter(
                    x=x_labels,
                    y=chart_df["RSI"],
                    line=dict(color="#7e57c2", width=1.6),
                    name="RSI (14)",
                    showlegend=False,
                ),
                row=idx,
                col=1,
            )
            fig.add_hline(
                y=70,
                line_dash="dash",
                line_width=1.0,
                line_color="rgba(242, 54, 69, 0.55)",
                row=idx,
                col=1,
            )
            fig.add_hline(
                y=30,
                line_dash="dash",
                line_width=1.0,
                line_color="rgba(8, 153, 129, 0.55)",
                row=idx,
                col=1,
            )
            fig.update_yaxes(
                side="right",
                title_text="RSI",
                range=[0, 100],
                fixedrange=False,
                showgrid=True,
                gridcolor="rgba(42, 46, 57, 0.08)",
                row=idx,
                col=1,
            )

    total_bars: int = len(x_labels)
    initial_visible_bars: int = min(75, total_bars)
    init_range = [
        max(0, total_bars - initial_visible_bars) - 0.5,
        total_bars - 0.5,
    ]

    fig.update_xaxes(
        type="category",
        range=init_range,
        nticks=10,
        fixedrange=False,
        showgrid=True,
        gridcolor="rgba(42, 46, 57, 0.08)",
        rangeslider=dict(visible=False),
    )

    chart_height: int = (
        680 if rows_count == 1 else (740 if rows_count == 2 else 800)
    )

    fig.update_layout(
        height=chart_height,
        template="plotly_white",
        paper_bgcolor="#ffffff",
        plot_bgcolor="#ffffff",
        dragmode="pan",
        hovermode="x unified",
        bargap=0.22,
        margin=dict(l=12, r=64, t=12, b=28),
        legend=dict(
            orientation="h",
            yanchor="top",
            y=0.99,
            xanchor="left",
            x=0.01,
            bgcolor="rgba(255,255,255,0.75)",
        ),
        xaxis=dict(fixedrange=False),
        yaxis=dict(fixedrange=False),
    )

    st.plotly_chart(
        fig,
        use_container_width=True,
        config={
            "scrollZoom": True,
            "displayModeBar": True,
            "displaylogo": False,
            "doubleClick": "reset",
            "modeBarButtonsToRemove": ["lasso2d", "select2d"],
            "modeBarButtonsToRemove": ["lasso2d", "select2d", "autoScale2d"],
        },
    )

# --- WATCHLIST NAVIGATION ---
watchlist_items = settings.CORE_WATCHLIST
wl_cols = st.columns(len(watchlist_items))
for i, item in enumerate(watchlist_items):
    sym: str = item["symbol"]
    disp_name: str = item.get("label", sym.replace(".NS", ""))
    is_active: bool = sym == st.session_state.active_symbol
    if wl_cols[i].button(
        disp_name,
        key=f"wl_btn_{sym}",
        type="primary" if is_active else "secondary",
        use_container_width=True,
    ):
        st.session_state.active_symbol = sym
        st.rerun()

st.divider()

# --- INTELLIGENCE & MATRIX EXPANDERS ---
with st.expander("Market Intelligence, MTF Matrix & Risk Levels", expanded=False):
    tab_scan, tab_mtf, tab_risk = st.tabs(
        ["Confluence Scanner", "MTF Signal Matrix", "Risk & Levels"]
    )

    with tab_scan:
        scanner_df = run_scanner_universe(st.session_state.active_tf)
        sig_cols: List[str] = ["Master Signal", "1WK", "1D", "1H", "15M"]
        if scanner_df.empty:
            st.info(
                "No high-accuracy confluence candidates found for current"
                " timeframe."
            )
        else:
            st.dataframe(
                scanner_df.style.map(style_signal_cell, subset=sig_cols),
                use_container_width=True,
                hide_index=True,
            )

    with tab_mtf:
        matrix_rows: List[Dict] = []
        for tf, res in mtf_results.items():
            pat_name: str = (
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
        st.dataframe(
            pd.DataFrame(matrix_rows).style.map(
                style_signal_cell, subset=["Signal"]
            ),
            use_container_width=True,
            hide_index=True,
        )

    with tab_risk:
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
