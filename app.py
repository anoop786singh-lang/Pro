मैंने आपके पुराने कोड के लॉजिक और ट्रेडिंगव्यू के डिज़ाइन को मिलाकर एक बेहद उन्नत और मज़बूत कोड तैयार किया है. इसमें इंडेंटेशन की समस्या नहीं आएगी और सभी एडवांस फीचर्स जैसे ड्राइंग टूल्स, बैकटेस्टिंग, और स्कैनर शामिल हैं. इस पूरे कोड को कॉपी करके सेव कर लें:
import datetime as dt
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st
import yfinance as yf

# --- PAGE CONFIGURATION ---
st.set_page_config(
    page_title="Market Master Pro | Advanced Terminal",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown(
    """
    <style>
        .block-container {
            padding-top: 1rem !important;
            padding-bottom: 1rem !important;
            padding-left: 1.2rem !important;
            padding-right: 1.2rem !important;
            max-width: 100% !important;
        }
        #MainMenu, footer, .stDeployButton {visibility: hidden;}
        div[data-testid="stMetricValue"] {font-size: 1.3rem !important;}
        div[data-testid="stMetricLabel"] {font-size: 0.78rem !important;}
    </style>
    """,
    unsafe_allow_html=True,
)

# --- WATCHLIST & SETTINGS ---
WATCHLIST: List[Dict[str, str]] = [
    {"label": "NIFTY 50", "symbol": "^NSEI"},
    {"label": "BANKNIFTY", "symbol": "^NSEBANK"},
    {"label": "RELIANCE", "symbol": "RELIANCE.NS"},
    {"label": "HDFCBANK", "symbol": "HDFCBANK.NS"},
    {"label": "INFY", "symbol": "INFY.NS"},
    {"label": "TCS", "symbol": "TCS.NS"},
    {"label": "ABCAPITAL", "symbol": "ABCAPITAL.NS"},
    {"label": "VEDL", "symbol": "VEDL.NS"},
    {"label": "SILVER", "symbol": "SI=F"},
    {"label": "GOLD", "symbol": "GC=F"},
]

TF_CONFIG: Dict[str, Dict[str, str]] = {
    "15M": {"period": "15d", "interval": "15m"},
    "1H": {"period": "60d", "interval": "60m"},
    "1D": {"period": "2y", "interval": "1d"},
    "1WK": {"period": "5y", "interval": "1wk"},
}


# --- INDICATOR & PATTERN ENGINE ---
def compute_indicators(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty or len(df) < 20:
        return df
    out = df.copy()
    close = out["Close"]
    high = out["High"]
    low = out["Low"]

    # SMA & Bollinger Bands (20, 2)
    out["SMA_20"] = close.rolling(20, min_periods=1).mean()
    std_20 = close.rolling(20, min_periods=1).std().fillna(0.0)
    out["BB_UPPER"] = out["SMA_20"] + (2.0 * std_20)
    out["BB_LOWER"] = out["SMA_20"] - (2.0 * std_20)

    # Wilder's RSI (14)
    delta = close.diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / 14, min_periods=14, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / 14, min_periods=14, adjust=False).mean()
    rs = gain / loss.replace(0, 1e-9)
    out["RSI"] = 100.0 - (100.0 / (1.0 + rs))

    # ATR (14)
    prev_close = close.shift(1)
    tr = pd.concat(
        [high - low, (high - prev_close).abs(), (low - prev_close).abs()], axis=1
    ).max(axis=1)
    out["ATR"] = tr.rolling(14, min_periods=1).mean()

    return out


def detect_candle_pattern(df: pd.DataFrame) -> str:
    if len(df) < 3:
        return "None"
    c0, c1 = df.iloc[-1], df.iloc[-2]
    body0 = abs(c0["Close"] - c0["Open"])
    rng0 = max(c0["High"] - c0["Low"], 1e-9)
    lower_wick = min(c0["Open"], c0["Close"]) - c0["Low"]
    upper_wick = c0["High"] - max(c0["Open"], c0["Close"])

    if body0 / rng0 < 0.12:
        return "Doji"
    if lower_wick > 2 * body0 and upper_wick < body0:
        return "Hammer / Pin Bar"
    if upper_wick > 2 * body0 and lower_wick < body0:
        return "Shooting Star"
    if (
        c1["Close"] < c1["Open"]
        and c0["Close"] > c0["Open"]
        and c0["Close"] > c1["Open"]
        and c0["Open"] < c1["Close"]
    ):
        return "Bullish Engulfing"
    if (
        c1["Close"] > c1["Open"]
        and c0["Close"] < c0["Open"]
        and c0["Close"] < c1["Open"]
        and c0["Open"] > c1["Close"]
    ):
        return "Bearish Engulfing"
    return "Standard Bar"


def evaluate_timeframe(df: pd.DataFrame) -> Dict:
    df_ind = compute_indicators(df)
    if df_ind.empty or len(df_ind) < 20:
        return {"signal": "NEUTRAL", "score": 0, "rsi": 50.0, "pattern": "None", "df": df_ind}

    last = df_ind.iloc[-1]
    close = float(last["Close"])
    rsi = float(last["RSI"])
    sma20 = float(last["SMA_20"])
    bb_up = float(last["BB_UPPER"])
    bb_low = float(last["BB_LOWER"])
    pattern = detect_candle_pattern(df_ind)

    score = 0
    if close > sma20:
        score += 1
    else:
        score -= 1

    if close > bb_up:
        score += 1
    elif close < bb_low:
        score -= 1

    if 55 <= rsi <= 72:
        score += 2
    elif rsi > 72:
        score += 1
    elif 28 <= rsi <= 45:
        score -= 2
    elif rsi < 28:
        score -= 1

    if pattern in ["Hammer / Pin Bar", "Bullish Engulfing"]:
        score += 1
    elif pattern in ["Shooting Star", "Bearish Engulfing"]:
        score -= 1

    if score >= 3:
        sig = "STRONG BUY"
    elif score >= 1:
        sig = "BUY"
    elif score <= -3:
        sig = "STRONG SELL"
    elif score <= -1:
        sig = "SELL"
    else:
        sig = "NEUTRAL"

    return {
        "signal": sig,
        "score": score,
        "rsi": round(rsi, 2),
        "pattern": pattern,
        "df": df_ind,
    }


# --- DATA FETCHING ---
@st.cache_data(ttl=180, show_spinner=False)
def fetch_mtf_data(symbol: str) -> Dict[str, pd.DataFrame]:
    data: Dict[str, pd.DataFrame] = {}
    for tf, params in TF_CONFIG.items():
        try:
            df = yf.download(
                symbol,
                period=params["period"],
                interval=params["interval"],
                progress=False,
                auto_adjust=True,
            )
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            df = df.dropna()
            data[tf] = df
        except Exception:
            data[tf] = pd.DataFrame()
    return data


@st.cache_data(ttl=600, show_spinner=False)
def fetch_fundamentals(symbol: str) -> Dict[str, str]:
    try:
        info = yf.Ticker(symbol).info
        return {
            "Name": str(info.get("shortName", symbol)),
            "Sector": str(info.get("sector", "Index / Commodity")),
            "Market Cap": f"{info.get('marketCap', 0):,}" if info.get("marketCap") else "N/A",
            "Trailing P/E": f"{info.get('trailingPE', 0):.2f}" if info.get("trailingPE") else "N/A",
            "52W High": f"{info.get('fiftyTwoWeekHigh', 0):,.2f}" if info.get("fiftyTwoWeekHigh") else "N/A",
            "52W Low": f"{info.get('fiftyTwoWeekLow', 0):,.2f}" if info.get("fiftyTwoWeekLow") else "N/A",
            "50D Avg": f"{info.get('fiftyDayAverage', 0):,.2f}" if info.get("fiftyDayAverage") else "N/A",
            "200D Avg": f"{info.get('twoHundredDayAverage', 0):,.2f}" if info.get("twoHundredDayAverage") else "N/A",
        }
    except Exception:
        return {"Name": symbol, "Status": "Fundamentals unavailable"}


def compute_master_signal(
    mtf_eval: Dict[str, Dict], active_tf: str, capital: float, risk_pct: float
) -> Dict:
    weights = {"1WK": 3, "1D": 3, "1H": 2, "15M": 1}
    weighted_sum = 0
    max_possible = 0
    for tf, w in weights.items():
        if tf in mtf_eval and not mtf_eval[tf]["df"].empty:
            weighted_sum += mtf_eval[tf]["score"] * w
            max_possible += 5 * w

    conf = int(min(98, max(15, (abs(weighted_sum) / max(max_possible, 1)) * 100 + 25)))
    if weighted_sum >= 12:
        master_sig = "STRONG BUY"
    elif weighted_sum >= 4:
        master_sig = "BUY"
    elif weighted_sum <= -12:
        master_sig = "STRONG SELL"
    elif weighted_sum <= -4:
        master_sig = "SELL"
    else:
        master_sig = "NEUTRAL"

    df_act = mtf_eval[active_tf]["df"]
    entry = float(df_act["Close"].iloc[-1])
    atr = float(df_act["ATR"].iloc[-1]) if "ATR" in df_act.columns else entry * 0.015

    if "SELL" in master_sig:
        sl = entry + (1.5 * atr)
        t1 = entry - (2.0 * atr)
        t2 = entry - (3.5 * atr)
    else:
        sl = entry - (1.5 * atr)
        t1 = entry + (2.0 * atr)
        t2 = entry + (3.5 * atr)

    risk_per_share = max(abs(entry - sl), 1e-6)
    qty = int((capital * (risk_pct / 100.0)) // risk_per_share)

    return {
        "signal": master_sig,
        "confidence": conf,
        "entry": round(entry, 2),
        "sl": round(sl, 2),
        "t1": round(t1, 2),
        "t2": round(t2, 2),
        "qty": max(qty, 1),
    }


# --- BACKTESTING SIMULATOR ---
def run_backtest(
    df: pd.DataFrame, initial_cap: float, rsi_buy: int, rsi_sell: int
) -> Tuple[pd.DataFrame, Dict]:
    if df.empty or len(df) < 30:
        return pd.DataFrame(), {}

    bt = df.copy().reset_index()
    capital = initial_cap
    position = 0
    entry_price = 0.0
    trades = []
    equity_curve = []

    for i in range(20, len(bt)):
        row = bt.iloc[i]
        price = float(row["Close"])
        rsi = float(row["RSI"])
        sma = float(row["SMA_20"])
        date_val = row.iloc[0]

        if position == 0 and price > sma and rsi >= rsi_buy and rsi < 75:
            position = int(capital // price)
            if position > 0:
                entry_price = price
                capital -= position * price
                trades.append({"Date": date_val, "Type": "BUY", "Price": round(price, 2), "PnL": 0.0})
        elif position > 0 and (rsi <= rsi_sell or price < sma):
            pnl = (price - entry_price) * position
            capital += position * price
            trades.append({"Date": date_val, "Type": "SELL", "Price": round(price, 2), "PnL": round(pnl, 2)})
            position = 0

        current_eq = capital + (position * price)
        equity_curve.append({"Date": date_val, "Equity": current_eq})

    final_eq = equity_curve[-1]["Equity"] if equity_curve else initial_cap
    closed_trades = [t for t in trades if t["Type"] == "SELL"]
    wins = [t for t in closed_trades if t["PnL"] > 0]
    win_rate = (len(wins) / len(closed_trades) * 100) if closed_trades else 0.0
    net_ret = ((final_eq - initial_cap) / initial_cap) * 100

    summary = {
        "Final Capital": f"{final_eq:,.2f}",
        "Net Return %": f"{net_ret:+.2f}%",
        "Total Trades": len(closed_trades),
        "Win Rate %": f"{win_rate:.1f}%",
    }
    return pd.DataFrame(equity_curve), summary


# --- STYLING HELPER ---
def style_signal(val: str) -> str:
    v = str(val).upper()
    if v == "STRONG BUY":
        return "background-color: #006400; color: white; font-weight: bold;"
    if v == "BUY":
        return "background-color: #198754; color: white; font-weight: bold;"
    if v == "STRONG SELL":
        return "background-color: #8b0000; color: white; font-weight: bold;"
    if v == "SELL":
        return "background-color: #dc3545; color: white; font-weight: bold;"
    return "background-color: #2b3035; color: #adb5bd;"


# --- SESSION STATE ---
if "symbol" not in st.session_state:
    st.session_state.symbol = WATCHLIST[0]["symbol"]
if "tf" not in st.session_state:
    st.session_state.tf = "1D"

# --- SIDEBAR ---
st.sidebar.header("Risk & Capital Settings")
capital = st.sidebar.number_input("Trading Capital", value=100000.0, step=10000.0)
risk_pct = st.sidebar.slider("Risk per Trade (%)", 0.5, 5.0, 1.5, 0.5)

# --- FETCH & EVALUATE ---
mtf_raw = fetch_mtf_data(st.session_state.symbol)
if not mtf_raw or mtf_raw[st.session_state.tf].empty:
    st.error("Market data unavailable for selected symbol.")
    st.stop()

mtf_eval = {tf: evaluate_timeframe(df) for tf, df in mtf_raw.items()}
master = compute_master_signal(mtf_eval, st.session_state.tf, capital, risk_pct)
active_df = mtf_eval[st.session_state.tf]["df"]

# --- TOP BAR (TRADINGVIEW STYLE) ---
c1, c2, c3, c4 = st.columns([2.2, 2.6, 1.8, 2.4])
with c1:
    sym_map = {f"{x['label']} ({x['symbol']})": x["symbol"] for x in WATCHLIST}
    keys = list(sym_map.keys())
    vals = list(sym_map.values())
    idx = vals.index(st.session_state.symbol) if st.session_state.symbol in vals else 0
    chosen = st.selectbox("Symbol", keys, index=idx, label_visibility="collapsed")
    if sym_map[chosen] != st.session_state.symbol:
        st.session_state.symbol = sym_map[chosen]
        st.rerun()

with c2:
    tf_cols = st.columns(len(TF_CONFIG))
    for i, tf_name in enumerate(TF_CONFIG.keys()):
        if tf_cols[i].button(
            tf_name,
            key=f"tf_{tf_name}",
            type="primary" if st.session_state.tf == tf_name else "secondary",
            use_container_width=True,
        ):
            st.session_state.tf = tf_name
            st.rerun()

with c3:
    last_c = float(active_df["Close"].iloc[-1])
    prev_c = float(active_df["Close"].iloc[-2]) if len(active_df) > 1 else last_c
    chg = ((last_c - prev_c) / prev_c) * 100
    st.metric(
        f"{st.session_state.symbol} · {st.session_state.tf}",
        f"{last_c:,.2f}",
        f"{chg:+.2f}%",
    )

with c4:
    st.metric(
        f"Master Signal (Qty: {master['qty']})",
        master["signal"],
        f"{master['confidence']}% Confidence",
    )

# --- INDICATOR & OVERLAY CONTROLS ---
t1, t2, t3, t4, t5, t6 = st.columns(6)
show_bb = t1.toggle("BB (20, 2)", value=True)
show_vol = t2.toggle("Volume", value=True)
show_rsi = t3.toggle("RSI (14)", value=True)
show_levels = t4.toggle("Trade Levels", value=True)
show_fib = t5.toggle("Auto Fib", value=False)
candle_count = t6.selectbox("Bars", [60, 120, 200], index=1, label_visibility="collapsed")

# --- INTERACTIVE CHART WITH DRAWING TOOLS ---
plot_df = active_df.tail(candle_count).copy()
fmt = "%d %b %H:%M" if st.session_state.tf in ["15M", "1H"] else "%d %b '%y"
x_idx = plot_df.index.strftime(fmt)

panels = ["price"]
if show_vol:
    panels.append("vol")
if show_rsi:
    panels.append("rsi")

heights = [0.68, 0.15, 0.17][: len(panels)]
if len(panels) == 2:
    heights = [0.78, 0.22]
elif len(panels) == 1:
    heights = [1.0]

fig = make_subplots(
    rows=len(panels),
    cols=1,
    shared_xaxes=True,
    vertical_spacing=0.02,
    row_heights=heights,
)

# Price Panel
fig.add_trace(
    go.Candlestick(
        x=x_idx,
        open=plot_df["Open"],
        high=plot_df["High"],
        low=plot_df["Low"],
        close=plot_df["Close"],
        increasing_line_color="#089981",
        decreasing_line_color="#f23645",
        name="Price",
        showlegend=False,
    ),
    row=1,
    col=1,
)

if show_bb:
    fig.add_trace(
        go.Scatter(
            x=x_idx, y=plot_df["BB_UPPER"], line=dict(color="rgba(41,98,255,0.7)", width=1.1), name="BB Upper"
        ),
        row=1,
        col=1,
    )
    fig.add_trace(
        go.Scatter(
            x=x_idx, y=plot_df["SMA_20"], line=dict(color="rgba(255,109,0,0.85)", width=1.1), name="20 SMA"
        ),
        row=1,
        col=1,
    )
    fig.add_trace(
        go.Scatter(
            x=x_idx,
            y=plot_df["BB_LOWER"],
            line=dict(color="rgba(41,98,255,0.7)", width=1.1),
            fill="tonexty",
            fillcolor="rgba(41,98,255,0.05)",
            name="BB Lower",
        ),
        row=1,
        col=1,
    )

if show_levels:
    for val, col_hex, dash_st, lbl in [
        (master["t2"], "#089981", "dot", f"T2 {master['t2']}"),
        (master["t1"], "#089981", "dash", f"T1 {master['t1']}"),
        (master["entry"], "#2962ff", "solid", f"ENTRY {master['entry']}"),
        (master["sl"], "#f23645", "dash", f"SL {master['sl']}"),
    ]:
        fig.add_hline(
            y=val,
            line_dash=dash_st,
            line_width=1.1,
            line_color=col_hex,
            annotation_text=lbl,
            annotation_position="top left",
            row=1,
            col=1,
        )

if show_fib:
    hi_max = float(plot_df["High"].max())
    lo_min = float(plot_df["Low"].min())
    diff = hi_max - lo_min
    for fib_lvl in [0.236, 0.382, 0.5, 0.618]:
        f_price = hi_max - (diff * fib_lvl)
        fig.add_hline(
            y=f_price,
            line_dash="dot",
            line_width=0.9,
            line_color="rgba(128,128,128,0.6)",
            annotation_text=f"Fib {fib_lvl:.3f} ({f_price:,.1f})",
            annotation_position="bottom right",
            row=1,
            col=1,
        )

curr_row = 2
if show_vol:
    v_cols = [
        "rgba(8,153,129,0.5)" if c >= o else "rgba(242,54,69,0.5)"
        for c, o in zip(plot_df["Close"], plot_df["Open"])
    ]
    fig.add_trace(
        go.Bar(x=x_idx, y=plot_df["Volume"], marker_color=v_cols, name="Volume", showlegend=False),
        row=curr_row,
        col=1,
    )
    fig.update_yaxes(title_text="Vol", side="right", row=curr_row, col=1)
    curr_row += 1

if show_rsi:
    fig.add_trace(
        go.Scatter(x=x_idx, y=plot_df["RSI"], line=dict(color="#7e57c2", width=1.5), name="RSI", showlegend=False),
        row=curr_row,
        col=1,
    )
    fig.add_hline(y=70, line_dash="dash", line_color="rgba(242,54,69,0.5)", row=curr_row, col=1)
    fig.add_hline(y=30, line_dash="dash", line_color="rgba(8,153,129,0.5)", row=curr_row, col=1)
    fig.update_yaxes(title_text="RSI", range=[0, 100], side="right", row=curr_row, col=1)

fig.update_yaxes(side="right", row=1, col=1)
fig.update_xaxes(type="category", nticks=10, rangeslider_visible=False)
fig.update_layout(
    height=680,
    template="plotly_white",
    dragmode="pan",
    hovermode="x unified",
    margin=dict(l=10, r=60, t=10, b=25),
    newshape=dict(line_color="#2962ff", line_width=2),
)

# Enable TradingView-like interactive drawing tools in modebar
plotly_config = {
    "scrollZoom": True,
    "displayModeBar": True,
    "displaylogo": False,
    "modeBarButtonsToAdd": [
        "drawline",
        "drawopenpath",
        "drawrect",
        "eraseshape",
    ],
}
st.plotly_chart(fig, use_container_width=True, config=plotly_config)

# --- BOTTOM WATCHLIST QUICK SCROLL BAR ---
wl_cols = st.columns(len(WATCHLIST))
for i, item in enumerate(WATCHLIST):
    if wl_cols[i].button(
        item["label"],
        key=f"wl_{item['symbol']}",
        type="primary" if item["symbol"] == st.session_state.symbol else "secondary",
        use_container_width=True,
    ):
        st.session_state.symbol = item["symbol"]
        st.rerun()

st.divider()

# --- ANALYSIS HUB: SCANNER, MTF MATRIX, BACKTESTING & FINANCIALS ---
tab1, tab2, tab3, tab4 = st.tabs(
    ["Confluence Scanner", "MTF Signal Matrix", "Backtest Simulator", "Financials & Details"]
)

with tab1:
    if st.button("Scan Full Watchlist Now", type="primary"):
        scan_rows = []
        for item in WATCHLIST:
            s_data = fetch_mtf_data(item["symbol"])
            if not s_data or s_data[st.session_state.tf].empty:
                continue
            s_eval = {t: evaluate_timeframe(d) for t, d in s_data.items()}
            s_master = compute_master_signal(s_eval, st.session_state.tf, capital, risk_pct)
            scan_rows.append(
                {
                    "Stock": item["label"],
                    "LTP": s_master["entry"],
                    "Master Signal": s_master["signal"],
                    "Conf %": s_master["confidence"],
                    "1WK": s_eval["1WK"]["signal"],
                    "1D": s_eval["1D"]["signal"],
                    "1H": s_eval["1H"]["signal"],
                    "15M": s_eval["15M"]["signal"],
                    "RSI": s_eval[st.session_state.tf]["rsi"],
                    "Pattern": s_eval[st.session_state.tf]["pattern"],
                    "Entry": s_master["entry"],
                    "SL": s_master["sl"],
                    "Target 1": s_master["t1"],
                }
            )
        if scan_rows:
            df_scan = pd.DataFrame(scan_rows).sort_values("Conf %", ascending=False)
            st.dataframe(
                df_scan.style.map(
                    style_signal, subset=["Master Signal", "1WK", "1D", "1H", "15M"]
                ),
                use_container_width=True,
                hide_index=True,
            )

with tab2:
    mtf_rows = [
        {
            "Timeframe": tf,
            "Signal": res["signal"],
            "Score": res["score"],
            "RSI (14)": res["rsi"],
            "Candle Pattern": res["pattern"],
        }
        for tf, res in mtf_eval.items()
    ]
    st.dataframe(
        pd.DataFrame(mtf_rows).style.map(style_signal, subset=["Signal"]),
        use_container_width=True,
        hide_index=True,
    )

with tab3:
    b1, b2, b3 = st.columns(3)
    bt_rsi_buy = b1.slider("Buy Trigger RSI >=", 45, 65, 55)
    bt_rsi_sell = b2.slider("Exit Trigger RSI <=", 30, 50, 45)
    bt_cap = b3.number_input("Simulation Capital", value=100000.0, step=10000.0)

    eq_df, bt_stats = run_backtest(active_df, bt_cap, bt_rsi_buy, bt_rsi_sell)
    if bt_stats:
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Final Capital", bt_stats["Final Capital"])
        m2.metric("Net Return", bt_stats["Net Return %"])
        m3.metric("Closed Trades", bt_stats["Total Trades"])
        m4.metric("Win Rate", bt_stats["Win Rate %"])
        st.line_chart(eq_df.set_index("Date")["Equity"], height=260)
    else:
        st.info("Insufficient historical bars to run backtest.")

with tab4:
    fund_data = fetch_fundamentals(st.session_state.symbol)
    f_df = pd.DataFrame(list(fund_data.items()), columns=["Metric", "Value"])
    st.dataframe(f_df, use_container_width=True, hide_index=True)


