import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

st.set_page_config(page_title="TradingView Pro — Indian Markets Terminal", layout="wide", initial_sidebar_state="expanded")

# --- TRADINGVIEW DARK UI STYLING ---
st.markdown("""
<style>
    .stApp { background-color: #131722; color: #d1d4dc; }
    section[data-testid="stSidebar"] { background-color: #1e222d; border-right: 1px solid #2a2e39; }
    .block-container { padding-top: 1rem; padding-bottom: 1rem; max-width: 100%; }
    .tv-header {
        display: flex; align-items: center; justify-content: space-between;
        background-color: #1e222d; padding: 10px 16px; border-radius: 6px;
        border: 1px solid #2a2e39; margin-bottom: 12px;
    }
    .tv-sym-title { font-size: 1.35rem; font-weight: 700; color: #ffffff; }
    .tv-price { font-size: 1.35rem; font-weight: 700; margin-left: 14px; }
    .mtf-card {
        background-color: #1e222d; border: 1px solid #2a2e39; border-radius: 6px;
        padding: 10px 8px; text-align: center;
    }
    .mtf-tf { font-size: 0.75rem; color: #787b86; font-weight: 600; text-transform: uppercase; }
    .mtf-sig {
        font-size: 0.92rem; font-weight: 700; margin-top: 5px; padding: 3px 6px;
        border-radius: 4px; display: inline-block; width: 90%;
    }
    .mtf-meta { font-size: 0.72rem; color: #b2b5be; margin-top: 5px; }
    .sig-strong-buy { background-color: rgba(8, 153, 129, 0.22); color: #089981; border: 1px solid #089981; }
    .sig-buy { background-color: rgba(41, 98, 255, 0.22); color: #2962ff; border: 1px solid #2962ff; }
    .sig-neutral { background-color: rgba(120, 123, 134, 0.22); color: #b2b5be; border: 1px solid #787b86; }
    .sig-sell { background-color: rgba(242, 54, 69, 0.22); color: #f23645; border: 1px solid #f23645; }
    .sig-strong-sell { background-color: rgba(183, 28, 28, 0.30); color: #ff5252; border: 1px solid #ff5252; }
    .watchlist-row {
        padding: 6px 8px; border-bottom: 1px solid #2a2e39; font-size: 0.82rem;
    }
</style>
""", unsafe_allow_html=True)

# --- WATCHLIST UNIVERSE (INDIAN INDICES & STOCKS) ---
WATCHLIST_ITEMS = [
    {"symbol": "^NSEI", "label": "NIFTY 50", "category": "Indices"},
    {"symbol": "^NSEBANK", "label": "BANK NIFTY", "category": "Indices"},
    {"symbol": "^BSESN", "label": "SENSEX", "category": "Indices"},
    {"symbol": "^CNXIT", "label": "NIFTY IT", "category": "Indices"},
    {"symbol": "RELIANCE.NS", "label": "RELIANCE", "category": "Stocks"},
    {"symbol": "TCS.NS", "label": "TCS", "category": "Stocks"},
    {"symbol": "HDFCBANK.NS", "label": "HDFCBANK", "category": "Stocks"},
    {"symbol": "ICICIBANK.NS", "label": "ICICIBANK", "category": "Stocks"},
    {"symbol": "INFY.NS", "label": "INFY", "category": "Stocks"},
    {"symbol": "BHARTIARTL.NS", "label": "BHARTIARTL", "category": "Stocks"},
    {"symbol": "SBIN.NS", "label": "SBIN", "category": "Stocks"},
    {"symbol": "LT.NS", "label": "LT", "category": "Stocks"},
    {"symbol": "ITC.NS", "label": "ITC", "category": "Stocks"},
    {"symbol": "BAJFINANCE.NS", "label": "BAJFINANCE", "category": "Stocks"},
    {"symbol": "TATAMOTORS.NS", "label": "TATAMOTORS", "category": "Stocks"},
    {"symbol": "SUNPHARMA.NS", "label": "SUNPHARMA", "category": "Stocks"},
    {"symbol": "AXISBANK.NS", "label": "AXISBANK", "category": "Stocks"},
    {"symbol": "KOTAKBANK.NS", "label": "KOTAKBANK", "category": "Stocks"},
    {"symbol": "MARUTI.NS", "label": "MARUTI", "category": "Stocks"},
    {"symbol": "TITAN.NS", "label": "TITAN", "category": "Stocks"},
]

TIMEFRAMES = ["15m", "1h", "4h", "1d", "1wk"]

if "active_symbol" not in st.session_state:
    st.session_state.active_symbol = "^NSEI"
if "active_label" not in st.session_state:
    st.session_state.active_label = "NIFTY 50"

# --- DATA FETCHING & 4H RESAMPLING ---
@st.cache_data(ttl=180)
def get_ohlcv(symbol: str, tf: str) -> pd.DataFrame:
    if tf == "15m":
        df = yf.download(symbol, period="30d", interval="15m", progress=False)
    elif tf == "1h":
        df = yf.download(symbol, period="180d", interval="1h", progress=False)
    elif tf == "4h":
        raw = yf.download(symbol, period="365d", interval="1h", progress=False)
        if isinstance(raw.columns, pd.MultiIndex):
            raw.columns = raw.columns.get_level_values(0)
        raw = raw.dropna()
        if raw.empty:
            return pd.DataFrame()
        df = raw.resample("4h").agg({
            "Open": "first",
            "High": "max",
            "Low": "min",
            "Close": "last",
            "Volume": "sum"
        }).dropna()
        return df
    elif tf == "1d":
        df = yf.download(symbol, period="2y", interval="1d", progress=False)
    else:  # 1wk
        df = yf.download(symbol, period="5y", interval="1wk", progress=False)

    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df.dropna().copy()

@st.cache_data(ttl=180)
def get_watchlist_quotes() -> dict:
    quotes = {}
    for item in WATCHLIST_ITEMS:
        sym = item["symbol"]
        df = get_ohlcv(sym, "1d")
        if len(df) >= 2:
            c = float(df["Close"].iloc[-1])
            p = float(df["Close"].iloc[-2])
            chg = c - p
            pct = (chg / p) * 100
            quotes[sym] = (c, chg, pct)
        elif len(df) == 1:
            c = float(df["Close"].iloc[-1])
            quotes[sym] = (c, 0.0, 0.0)
        else:
            quotes[sym] = (0.0, 0.0, 0.0)
    return quotes

# --- TECHNICAL INDICATORS & SIGNAL SCORING ---
def compute_indicators(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    # RSI (14)
    delta = df["Close"].diff()
    gain = delta.clip(lower=0).ewm(alpha=1/14, min_periods=14, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1/14, min_periods=14, adjust=False).mean()
    rs = gain / loss.replace(0, np.nan)
    df["RSI"] = 100 - (100 / (1 + rs))

    # Moving Averages
    df["EMA20"] = df["Close"].ewm(span=20, adjust=False).mean()
    df["EMA50"] = df["Close"].ewm(span=50, adjust=False).mean()
    df["SMA200"] = df["Close"].rolling(200).mean()

    # MACD (12, 26, 9)
    ema12 = df["Close"].ewm(span=12, adjust=False).mean()
    ema26 = df["Close"].ewm(span=26, adjust=False).mean()
    df["MACD"] = ema12 - ema26
    df["MACD_Signal"] = df["MACD"].ewm(span=9, adjust=False).mean()
    df["MACD_Hist"] = df["MACD"] - df["MACD_Signal"]

    # Bollinger Bands (20, 2)
    sma20 = df["Close"].rolling(20).mean()
    std20 = df["Close"].rolling(20).std()
    df["BB_Upper"] = sma20 + 2 * std20
    df["BB_Lower"] = sma20 - 2 * std20

    # VWAP (Rolling 20-bar session proxy)
    tp = (df["High"] + df["Low"] + df["Close"]) / 3
    vol = df["Volume"].replace(0, np.nan).fillna(1.0)
    df["VWAP"] = (tp * vol).rolling(20).sum() / vol.rolling(20).sum()

    # ATR (14)
    tr = np.maximum(df["High"] - df["Low"],
                    np.maximum(abs(df["High"] - df["Close"].shift(1)), abs(df["Low"] - df["Close"].shift(1))))
    df["ATR"] = tr.rolling(14).mean()
    return df

def evaluate_timeframe_signal(df: pd.DataFrame) -> dict:
    if df.empty or len(df) < 26:
        return {"signal": "NEUTRAL", "css": "sig-neutral", "score": 0, "rsi": 50.0, "trend": "Flat"}
    df = compute_indicators(df)
    last = df.iloc[-1]
    close = float(last["Close"])
    rsi = float(last["RSI"]) if not np.isnan(last["RSI"]) else 50.0
    ema20 = float(last["EMA20"])
    ema50 = float(last["EMA50"])
    macd = float(last["MACD"])
    macd_sig = float(last["MACD_Signal"])

    score = 0
    # Oscillator points
    if rsi >= 65: score += 2
    elif rsi >= 55: score += 1
    elif rsi <= 35: score -= 2
    elif rsi <= 45: score -= 1

    score += 1 if macd > macd_sig else -1
    # Trend MA points
    score += 1 if close > ema20 else -1
    score += 1 if close > ema50 else -1
    score += 1 if ema20 > ema50 else -1

    if score >= 4:
        return {"signal": "STRONG BUY", "css": "sig-strong-buy", "score": score, "rsi": round(rsi, 1), "trend": "Bullish"}
    elif score >= 1:
        return {"signal": "BUY", "css": "sig-buy", "score": score, "rsi": round(rsi, 1), "trend": "Up"}
    elif score <= -4:
        return {"signal": "STRONG SELL", "css": "sig-strong-sell", "score": score, "rsi": round(rsi, 1), "trend": "Bearish"}
    elif score <= -1:
        return {"signal": "SELL", "css": "sig-sell", "score": score, "rsi": round(rsi, 1), "trend": "Down"}
    return {"signal": "NEUTRAL", "css": "sig-neutral", "score": score, "rsi": round(rsi, 1), "trend": "Range"}

# --- LEFT-HAND TRADINGVIEW WATCHLIST PANEL ---
with st.sidebar:
    st.markdown("### Watchlist")
    search_q = st.text_input("Search Symbol", placeholder="Filter NIFTY, RELIANCE...", label_visibility="collapsed").upper().strip()
    custom_ticker = st.text_input("Custom Yahoo Ticker", placeholder="Add e.g. ZOMATO.NS", label_visibility="collapsed").upper().strip()
    if custom_ticker:
        if st.button(f"Load {custom_ticker}", use_container_width=True):
            st.session_state.active_symbol = custom_ticker
            st.session_state.active_label = custom_ticker.replace(".NS", "")
            st.rerun()

    quotes = get_watchlist_quotes()

    for section in ["Indices", "Stocks"]:
        st.markdown(f"<div style='color:#787b86; font-size:0.75rem; font-weight:700; margin-top:10px; margin-bottom:4px; letter-spacing:0.05em;'>{section.upper()}</div>", unsafe_allow_html=True)
        for item in [x for x in WATCHLIST_ITEMS if x["category"] == section]:
            if search_q and search_q not in item["label"] and search_q not in item["symbol"]:
                continue
            sym = item["symbol"]
            lbl = item["label"]
            price, chg, pct = quotes.get(sym, (0.0, 0.0, 0.0))
            is_active = (st.session_state.active_symbol == sym)
            color_hex = "#089981" if pct >= 0 else "#f23645"
            sign = "+" if pct >= 0 else ""

            c1, c2 = st.columns([1.35, 1.0])
            with c1:
                btn_label = f"▶ {lbl}" if is_active else lbl
                if st.button(btn_label, key=f"wl_{sym}", use_container_width=True):
                    st.session_state.active_symbol = sym
                    st.session_state.active_label = lbl
                    st.rerun()
            with c2:
                st.markdown(
                    f"<div style='text-align:right; line-height:1.15; padding-top:4px;'>"
                    f"<span style='font-size:0.82rem; font-weight:600; color:#d1d4dc;'>{price:,.2f}</span><br>"
                    f"<span style='font-size:0.72rem; color:{color_hex};'>{sign}{pct:.2f}%</span>"
                    f"</div>",
                    unsafe_allow_html=True
                )

# --- MAIN WORKSPACE: HEADER, MTF MATRIX & INTERACTIVE CHART ---
active_sym = st.session_state.active_symbol
active_lbl = st.session_state.active_label

# Top Toolbar
top_l, top_r1, top_r2, top_r3 = st.columns([3.2, 1.2, 1.2, 1.0])
with top_l:
    price, chg, pct = quotes.get(active_sym, (0.0, 0.0, 0.0))
    if price == 0.0:
        d_tmp = get_ohlcv(active_sym, "1d")
        if len(d_tmp) >= 2:
            price = float(d_tmp["Close"].iloc[-1])
            chg = price - float(d_tmp["Close"].iloc[-2])
            pct = (chg / float(d_tmp["Close"].iloc[-2])) * 100
    p_color = "#089981" if pct >= 0 else "#f23645"
    p_sign = "+" if pct >= 0 else ""
    st.markdown(
        f"<div class='tv-header'>"
        f"<div><span class='tv-sym-title'>{active_lbl}</span> <span style='color:#787b86; font-size:0.85rem;'>({active_sym}) · NSE</span></div>"
        f"<div><span class='tv-price' style='color:{p_color};'>₹{price:,.2f}</span> "
        f"<span style='color:{p_color}; font-size:0.95rem; font-weight:600;'>{p_sign}{chg:.2f} ({p_sign}{pct:.2f}%)</span></div>"
        f"</div>",
        unsafe_allow_html=True
    )
with top_r1:
    chart_tf = st.selectbox("Chart Interval", options=TIMEFRAMES, index=3)
with top_r2:
    chart_style = st.selectbox("Chart Type", options=["Candles", "Hollow Candles", "Line"], index=0)
with top_r3:
    if st.button("Refresh", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

# --- MULTI-TIMEFRAME TECHNICAL ANALYSIS MATRIX (15m, 1h, 4h, 1d, 1wk) ---
mtf_results = {}
total_score = 0
for tf in TIMEFRAMES:
    df_tf = get_ohlcv(active_sym, tf)
    mtf_results[tf] = evaluate_timeframe_signal(df_tf)
    total_score += mtf_results[tf]["score"]

if total_score >= 12:
    overall_sig, overall_css = "STRONG BUY", "sig-strong-buy"
elif total_score >= 4:
    overall_sig, overall_css = "BUY", "sig-buy"
elif total_score <= -12:
    overall_sig, overall_css = "STRONG SELL", "sig-strong-sell"
elif total_score <= -4:
    overall_sig, overall_css = "SELL", "sig-sell"
else:
    overall_sig, overall_css = "NEUTRAL", "sig-neutral"

matrix_cols = st.columns([1, 1, 1, 1, 1, 1.35])
for idx, tf in enumerate(TIMEFRAMES):
    res = mtf_results[tf]
    with matrix_cols[idx]:
        st.markdown(
            f"<div class='mtf-card'>"
            f"<div class='mtf-tf'>{tf} Timeframe</div>"
            f"<div class='mtf-sig {res['css']}'>{res['signal']}</div>"
            f"<div class='mtf-meta'>RSI: {res['rsi']} · {res['trend']}</div>"
            f"</div>",
            unsafe_allow_html=True
        )

with matrix_cols[5]:
    st.markdown(
        f"<div class='mtf-card' style='border-color:#434651;'>"
        f"<div class='mtf-tf'>Consensus Summary</div>"
        f"<div class='mtf-sig {overall_css}'>{overall_sig}</div>"
        f"<div class='mtf-meta'>Net Score: {total_score:+d} / +30</div>"
        f"</div>",
        unsafe_allow_html=True
    )

st.markdown("<div style='height:10px;'></div>", unsafe_allow_html=True)

# --- INDICATOR OVERLAY TOGGLES ---
ind_c1, ind_c2, ind_c3, ind_c4, ind_c5 = st.columns(5)
with ind_c1:
    show_ema = st.checkbox("EMA 20 / 50", value=True)
with ind_c2:
    show_bb = st.checkbox("Bollinger Bands", value=False)
with ind_c3:
    show_vwap = st.checkbox("VWAP (20)", value=True)
with ind_c4:
    show_rsi = st.checkbox("RSI (14)", value=True)
with ind_c5:
    show_macd = st.checkbox("MACD (12,26,9)", value=True)

# --- BUILD INTERACTIVE PLOTLY TRADINGVIEW CHART ---
df_chart = get_ohlcv(active_sym, chart_tf)
if df_chart.empty:
    st.error(f"No historical data returned for {active_sym} ({chart_tf}).")
    st.stop()

df_chart = compute_indicators(df_chart).tail(160)

panels = ["price"]
if show_rsi:
    panels.append("rsi")
if show_macd:
    panels.append("macd")

n_rows = len(panels)
heights = [1.0] if n_rows == 1 else ([0.72, 0.28] if n_rows == 2 else [0.58, 0.20, 0.22])

fig = make_subplots(
    rows=n_rows, cols=1, shared_xaxes=True,
    vertical_spacing=0.02, row_heights=heights
)

# Main Price Trace
if chart_style == "Candles":
    fig.add_trace(go.Candlestick(
        x=df_chart.index, open=df_chart["Open"], high=df_chart["High"],
        low=df_chart["Low"], close=df_chart["Close"],
        increasing_line_color="#089981", increasing_fillcolor="#089981",
        decreasing_line_color="#f23645", decreasing_fillcolor="#f23645",
        name=active_lbl
    ), row=1, col=1)
elif chart_style == "Hollow Candles":
    fig.add_trace(go.Candlestick(
        x=df_chart.index, open=df_chart["Open"], high=df_chart["High"],
        low=df_chart["Low"], close=df_chart["Close"],
        increasing_line_color="#089981", increasing_fillcolor="rgba(0,0,0,0)",
        decreasing_line_color="#f23645", decreasing_fillcolor="#f23645",
        name=active_lbl
    ), row=1, col=1)
else:
    fig.add_trace(go.Scatter(
        x=df_chart.index, y=df_chart["Close"],
        line=dict(color="#2962ff", width=2), fill="tozeroy",
        fillcolor="rgba(41, 98, 255, 0.12)", name=active_lbl
    ), row=1, col=1)

# Overlays
if show_ema:
    fig.add_trace(go.Scatter(x=df_chart.index, y=df_chart["EMA20"], line=dict(color="#2962ff", width=1.3), name="EMA 20"), row=1, col=1)
    fig.add_trace(go.Scatter(x=df_chart.index, y=df_chart["EMA50"], line=dict(color="#ff9800", width=1.3), name="EMA 50"), row=1, col=1)

if show_vwap:
    fig.add_trace(go.Scatter(x=df_chart.index, y=df_chart["VWAP"], line=dict(color="#e040fb", width=1.3, dash="dot"), name="VWAP"), row=1, col=1)

if show_bb:
    fig.add_trace(go.Scatter(x=df_chart.index, y=df_chart["BB_Upper"], line=dict(color="rgba(41,98,255,0.45)", width=1), name="BB Upper"), row=1, col=1)
    fig.add_trace(go.Scatter(x=df_chart.index, y=df_chart["BB_Lower"], line=dict(color="rgba(41,98,255,0.45)", width=1), fill="tonexty", fillcolor="rgba(41,98,255,0.06)", name="BB Lower"), row=1, col=1)

# Current Price Line & Right-Axis Badge
curr_close = float(df_chart["Close"].iloc[-1])
curr_open = float(df_chart["Open"].iloc[-1])
badge_col = "#089981" if curr_close >= curr_open else "#f23645"

fig.add_hline(y=curr_close, line_dash="dash", line_color=badge_col, line_width=1, row=1, col=1)
fig.add_annotation(
    xref="paper", x=1.002, yref="y", y=curr_close,
    text=f"<b>{curr_close:,.2f}</b>", showarrow=False,
    xanchor="left", yanchor="middle",
    font=dict(color="#ffffff", size=11), bgcolor=badge_col, borderpad=3
)

curr_row = 2
if show_rsi:
    latest_rsi = float(df_chart["RSI"].iloc[-1])
    fig.add_trace(go.Scatter(
        x=df_chart.index, y=df_chart["RSI"],
        line=dict(color="#7e57c2", width=1.6), name="RSI (14)"
    ), row=curr_row, col=1)
    fig.add_hrect(y0=30, y1=70, fillcolor="rgba(126, 87, 194, 0.08)", line_width=0, row=curr_row, col=1)
    fig.add_hline(y=70, line_dash="dot", line_color="#787b86", line_width=0.9, row=curr_row, col=1)
    fig.add_hline(y=30, line_dash="dot", line_color="#787b86", line_width=0.9, row=curr_row, col=1)
    fig.update_yaxes(range=[0, 100], title_text="RSI", side="right", gridcolor="#2a2e39", row=curr_row, col=1)
    fig.add_annotation(
        xref="paper", x=1.002, yref=f"y{curr_row}", y=latest_rsi,
        text=f"<b>{latest_rsi:.1f}</b>", showarrow=False,
        xanchor="left", yanchor="middle",
        font=dict(color="#ffffff", size=10), bgcolor="#7e57c2", borderpad=3
    )
    curr_row += 1

if show_macd:
    hist_colors = np.where(df_chart["MACD_Hist"] >= 0, "rgba(8, 153, 129, 0.65)", "rgba(242, 54, 69, 0.65)")
    fig.add_trace(go.Bar(x=df_chart.index, y=df_chart["MACD_Hist"], marker_color=hist_colors, name="MACD Hist"), row=curr_row, col=1)
    fig.add_trace(go.Scatter(x=df_chart.index, y=df_chart["MACD"], line=dict(color="#2962ff", width=1.4), name="MACD"), row=curr_row, col=1)
    fig.add_trace(go.Scatter(x=df_chart.index, y=df_chart["MACD_Signal"], line=dict(color="#ff6d00", width=1.4), name="Signal"), row=curr_row, col=1)
    fig.update_yaxes(title_text="MACD", side="right", gridcolor="#2a2e39", row=curr_row, col=1)

fig.update_yaxes(side="right", gridcolor="#2a2e39", zerolinecolor="#2a2e39", row=1, col=1)
fig.update_xaxes(gridcolor="#2a2e39", showspikes=True, spikemode="across", spikesnap="cursor", spikecolor="#787b86", spikethickness=1)
fig.update_yaxes(showspikes=True, spikemode="across", spikecolor="#787b86", spikethickness=1)

fig.update_layout(
    height=640,
    paper_bgcolor="#131722",
    plot_bgcolor="#131722",
    font=dict(color="#d1d4dc"),
    xaxis_rangeslider_visible=False,
    hovermode="x unified",
    margin=dict(l=10, r=75, t=15, b=15),
    legend=dict(orientation="h", yanchor="bottom", y=1.01, xanchor="left", x=0, bgcolor="rgba(0,0,0,0)")
)

st.plotly_chart(fig, use_container_width=True)
