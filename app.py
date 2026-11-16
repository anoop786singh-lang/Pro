import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode, DataReturnMode

st.set_page_config(page_title="Market Master Pro — Institutional Terminal", layout="wide")

# --- CUSTOM STYLING ---
st.markdown("""
<style>
    .block-container { padding-top: 1rem; padding-bottom: 1rem; }
    div[data-testid="stMetricValue"] { font-size: 1.15rem; }
</style>
""", unsafe_allow_html=True)

DEFAULT_WATCHLIST = [
    {"Ticker": "RELIANCE.NS", "Name": "Reliance Industries"},
    {"Ticker": "TCS.NS", "Name": "Tata Consultancy Services"},
    {"Ticker": "HDFCBANK.NS", "Name": "HDFC Bank"},
    {"Ticker": "INFY.NS", "Name": "Infosys"},
    {"Ticker": "ICICIBANK.NS", "Name": "ICICI Bank"},
    {"Ticker": "BHARTIARTL.NS", "Name": "Bharti Airtel"},
    {"Ticker": "SBIN.NS", "Name": "State Bank of India"},
    {"Ticker": "LT.NS", "Name": "Larsen & Toubro"},
    {"Ticker": "^NSEI", "Name": "Nifty 50 Index"},
]

TIMEFRAME_MAP = {
    "15m": {"interval": "15m", "period": "60d",  "swing_window": 10},
    "1h":  {"interval": "1h",  "period": "730d", "swing_window": 10},
    "1d":  {"interval": "1d",  "period": "2y",   "swing_window": 14},
    "1wk": {"interval": "1wk", "period": "5y",   "swing_window": 10},
}

if "selected_ticker" not in st.session_state:
    st.session_state.selected_ticker = DEFAULT_WATCHLIST[0]["Ticker"]

# --- DATA & QUANTITATIVE ENGINE ---
@st.cache_data(ttl=300)
def fetch_data(symbol: str, tf_key: str) -> pd.DataFrame:
    cfg = TIMEFRAME_MAP[tf_key]
    df = yf.download(symbol, period=cfg["period"], interval=cfg["interval"], progress=False)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df = df.dropna().copy()
    return df

def compute_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))

def compute_vwap_bands(df: pd.DataFrame, window: int = 20) -> pd.DataFrame:
    tp = (df["High"] + df["Low"] + df["Close"]) / 3.0
    vol = df["Volume"].replace(0, np.nan).fillna(1.0)
    pv = tp * vol
    vwap = pv.rolling(window).sum() / vol.rolling(window).sum()
    std = (tp - vwap).rolling(window).std()
    df["VWAP"] = vwap
    df["VWAP_U1"] = vwap + std
    df["VWAP_L1"] = vwap - std
    df["VWAP_U2"] = vwap + 2 * std
    df["VWAP_L2"] = vwap - 2 * std
    return df

def compute_order_flow_imbalance(df: pd.DataFrame) -> pd.DataFrame:
    spread = (df["High"] - df["Low"]).replace(0, np.nan)
    body_ratio = (df["Close"] - df["Open"]) / spread
    vol = df["Volume"].fillna(0)
    raw_ofi = body_ratio.fillna(0) * vol
    ofi_mean = raw_ofi.rolling(20).mean()
    ofi_std = raw_ofi.rolling(20).std().replace(0, np.nan)
    df["OFI"] = raw_ofi
    df["OFI_Z"] = ((raw_ofi - ofi_mean) / ofi_std).fillna(0)
    return df

def compute_volume_profile(df: pd.DataFrame, bins: int = 32):
    recent = df.tail(120)
    prices = recent["Close"].values
    volumes = recent["Volume"].fillna(0).values
    if len(prices) == 0 or volumes.sum() == 0:
        return None
    hist, bin_edges = np.histogram(prices, bins=bins, weights=volumes)
    bin_centers = 0.5 * (bin_edges[:-1] + bin_edges[1:])
    poc_idx = int(np.argmax(hist))
    poc_price = float(bin_centers[poc_idx])
    
    # 70% Value Area
    total_vol = hist.sum()
    sorted_idx = np.argsort(hist)[::-1]
    cum_vol = 0.0
    va_prices = []
    for idx in sorted_idx:
        cum_vol += hist[idx]
        va_prices.append(bin_centers[idx])
        if cum_vol >= 0.70 * total_vol:
            break
    vah = float(max(va_prices))
    val = float(min(va_prices))
    return {"centers": bin_centers, "hist": hist, "poc": poc_price, "vah": vah, "val": val}

def detect_patterns(df: pd.DataFrame) -> pd.DataFrame:
    o, h, l, c = df["Open"], df["High"], df["Low"], df["Close"]
    body = (c - o).abs()
    prev_body = body.shift(1)
    upper_wick = h - np.maximum(o, c)
    lower_wick = np.minimum(o, c) - l

    bull_engulf = (c > o) & (c.shift(1) < o.shift(1)) & (c >= o.shift(1)) & (o <= c.shift(1)) & (body > prev_body)
    bear_engulf = (c < o) & (c.shift(1) > o.shift(1)) & (c <= o.shift(1)) & (o >= c.shift(1)) & (body > prev_body)
    bull_pin = (lower_wick > 2.2 * body) & (upper_wick < 0.4 * body) & (body > 0)
    bear_pin = (upper_wick > 2.2 * body) & (lower_wick < 0.4 * body) & (body > 0)

    pattern = pd.Series("", index=df.index)
    pattern[bull_engulf] = "Bull Engulf"
    pattern[bear_engulf] = "Bear Engulf"
    pattern[bull_pin] = "Bull Pin"
    pattern[bear_pin] = "Bear Pin"
    df["Pattern"] = pattern
    return df

def get_signal_label(rsi_val: float, price: float, sma20: float, ofi_z: float) -> str:
    score = 0
    if rsi_val >= 60: score += 1
    if rsi_val >= 70: score += 1
    if rsi_val <= 40: score -= 1
    if rsi_val <= 30: score -= 1
    if price > sma20: score += 1
    else: score -= 1
    if ofi_z > 1.2: score += 1
    elif ofi_z < -1.2: score -= 1

    if score >= 3: return "STRONG BUY"
    if score >= 1: return "BUY"
    if score <= -3: return "STRONG SELL"
    if score <= -1: return "SELL"
    return "NEUTRAL"

@st.cache_data(ttl=300)
def build_scanner_matrix(watchlist: list) -> pd.DataFrame:
    rows = []
    for item in watchlist:
        sym = item["Ticker"]
        try:
            df_1d = fetch_data(sym, "1d")
            df_1h = fetch_data(sym, "1h")
            df_15m = fetch_data(sym, "15m")
            if df_1d.empty:
                continue
            df_1d = compute_order_flow_imbalance(df_1d)
            rsi_1d = float(compute_rsi(df_1d["Close"], 14).iloc[-1])
            rsi_1h = float(compute_rsi(df_1h["Close"], 14).iloc[-1]) if not df_1h.empty else rsi_1d
            rsi_15m = float(compute_rsi(df_15m["Close"], 14).iloc[-1]) if not df_15m.empty else rsi_1h
            close_p = float(df_1d["Close"].iloc[-1])
            prev_p = float(df_1d["Close"].iloc[-2]) if len(df_1d) > 1 else close_p
            chg_pct = ((close_p - prev_p) / prev_p) * 100
            sma20 = float(df_1d["Close"].rolling(20).mean().iloc[-1])
            ofi_z = float(df_1d["OFI_Z"].iloc[-1])
            sig = get_signal_label(rsi_1d, close_p, sma20, ofi_z)
            flow_tag = "ACCUMULATION" if ofi_z > 1.0 else ("DISTRIBUTION" if ofi_z < -1.0 else "BALANCED")

            rows.append({
                "Ticker": sym,
                "Name": item["Name"],
                "LTP": round(close_p, 2),
                "Chg %": round(chg_pct, 2),
                "15m RSI": round(rsi_15m, 1),
                "1H RSI": round(rsi_1h, 1),
                "1D RSI": round(rsi_1d, 1),
                "OFI Z-Score": round(ofi_z, 2),
                "Inst. Flow": flow_tag,
                "Matrix Signal": sig,
            })
        except Exception:
            continue
    return pd.DataFrame(rows)

# --- TOP HEADER & CONTROLS ---
hdr_c1, hdr_c2, hdr_c3 = st.columns([3, 1.5, 1.5])
with hdr_c1:
    st.subheader("Market Master Pro — Institutional Quantitative Terminal")
with hdr_c2:
    custom_sym = st.text_input("Quick Symbol Override", value="", placeholder="e.g. TATAMOTORS.NS").upper().strip()
    if custom_sym and custom_sym != st.session_state.selected_ticker:
        st.session_state.selected_ticker = custom_sym
with hdr_c3:
    chart_tf = st.selectbox("Primary Chart Timeframe", options=list(TIMEFRAME_MAP.keys()), index=2)

# --- CLICKABLE AGGRID MATRIX SCANNER ---
matrix_df = build_scanner_matrix(DEFAULT_WATCHLIST)
if not matrix_df.empty:
    gb = GridOptionsBuilder.from_dataframe(matrix_df)
    gb.configure_selection(selection_mode="single", use_checkbox=False)
    gb.configure_default_column(resizable=True, sortable=True, filter=True)
    gb.configure_column("Ticker", width=120, pinned="left")
    gb.configure_column("Name", width=180)
    gb.configure_column("Matrix Signal", width=140, cellStyle={
        "styleConditions": [
            {"condition": "params.value == 'STRONG BUY'", "style": {"backgroundColor": "#0b5345", "color": "#58d68d", "fontWeight": "bold"}},
            {"condition": "params.value == 'BUY'", "style": {"backgroundColor": "#145a32", "color": "#82e0aa"}},
            {"condition": "params.value == 'STRONG SELL'", "style": {"backgroundColor": "#641e16", "color": "#f1948a", "fontWeight": "bold"}},
            {"condition": "params.value == 'SELL'", "style": {"backgroundColor": "#78281f", "color": "#f5b7b1"}},
        ]
    })
    grid_options = gb.build()
    grid_resp = AgGrid(
        matrix_df,
        gridOptions=grid_options,
        height=230,
        update_mode=GridUpdateMode.SELECTION_CHANGED,
        data_return_mode=DataReturnMode.FILTERED_AND_SORTED,
        fit_columns_on_grid_load=True,
        theme="streamlit",
        key="scanner_aggrid"
    )
    selected_rows = grid_resp.get("selected_rows", [])
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

# --- READ BOTTOM CONTROLS STATE ---
ticker = st.session_state.selected_ticker
rsi_tf = st.session_state.get("rsi_tf_ctrl", chart_tf)
rsi_period = st.session_state.get("rsi_period_ctrl", 14)
rsi_lower = st.session_state.get("rsi_lower_ctrl", 40)
rsi_upper = st.session_state.get("rsi_upper_ctrl", 60)
show_rsi = st.session_state.get("show_rsi_ctrl", True)
show_vol = st.session_state.get("show_vol_ctrl", True)
show_vpvr = st.session_state.get("show_vpvr_ctrl", True)
show_vwap = st.session_state.get("show_vwap_ctrl", True)
show_patterns = st.session_state.get("show_patterns_ctrl", True)
show_heatmap = st.session_state.get("show_heatmap_ctrl", False)

# --- FETCH & CALCULATE ACTIVE SYMBOL ---
df_chart = fetch_data(ticker, chart_tf)
df_rsi = fetch_data(ticker, rsi_tf)

if df_chart.empty:
    st.error(f"No market data available for {ticker}.")
    st.stop()

df_chart = df_chart.tail(180).copy()
df_chart["SMA20"] = df_chart["Close"].rolling(20).mean()
df_chart["BB_Std"] = df_chart["Close"].rolling(20).std()
df_chart["BB_Upper"] = df_chart["SMA20"] + 2 * df_chart["BB_Std"]
df_chart["BB_Lower"] = df_chart["SMA20"] - 2 * df_chart["BB_Std"]
df_chart = compute_vwap_bands(df_chart, 20)
df_chart = compute_order_flow_imbalance(df_chart)
df_chart = detect_patterns(df_chart)

df_rsi["RSI"] = compute_rsi(df_rsi["Close"], int(rsi_period))
latest_rsi = float(df_rsi["RSI"].iloc[-1])
df_chart["RSI_Aligned"] = df_rsi[["RSI"]].reindex(df_chart.index, method="ffill")["RSI"].bfill()

vpvr = compute_volume_profile(df_chart)
window = TIMEFRAME_MAP[chart_tf]["swing_window"]
recent_slice = df_chart.tail(window * 3)
swing_high = float(recent_slice["High"].max())
swing_low = float(recent_slice["Low"].min())
current_price = float(df_chart["Close"].iloc[-1])
current_vwap = float(df_chart["VWAP"].iloc[-1]) if not np.isnan(df_chart["VWAP"].iloc[-1]) else current_price
latest_ofi_z = float(df_chart["OFI_Z"].iloc[-1])

if latest_rsi >= rsi_upper:
    bias = "BULLISH"
    entry = current_price
    stop_loss = swing_low
    risk = max(entry - stop_loss, entry * 0.005)
    target_1 = entry + 1.5 * risk
    target_2 = entry + 2.5 * risk
elif latest_rsi <= rsi_lower:
    bias = "BEARISH"
    entry = current_price
    stop_loss = swing_high
    risk = max(stop_loss - entry, entry * 0.005)
    target_1 = entry - 1.5 * risk
    target_2 = entry - 2.5 * risk
else:
    bias = "NEUTRAL"
    entry = current_price
    stop_loss = swing_low
    target_1 = swing_high
    target_2 = swing_high + (swing_high - swing_low) * 0.5

# --- TOP KPI METRICS BAR ---
m1, m2, m3, m4, m5, m6, m7 = st.columns(7)
m1.metric(f"{ticker} ({chart_tf})", f"{current_price:.2f}", bias)
m2.metric("Swing High / Low", f"{swing_high:.1f} / {swing_low:.1f}")
m3.metric("Stop Loss", f"{stop_loss:.2f}")
m4.metric("Targets (T1 / T2)", f"{target_1:.1f} / {target_2:.1f}")
m5.metric("VWAP / POC", f"{current_vwap:.1f} / {vpvr['poc']:.1f}" if vpvr else f"{current_vwap:.1f}")
m6.metric("OFI Z-Score", f"{latest_ofi_z:+.2f}", "Inst. Flow")
m7.metric(f"RSI ({rsi_tf}|{rsi_period})", f"{latest_rsi:.2f}", f"{rsi_lower}/{rsi_upper}")

# --- DYNAMIC SUBPLOT CHART WITH TRADINGVIEW RIGHT-AXIS TAGS ---
active_subplots = ["price"]
if show_vol and "Volume" in df_chart.columns:
    active_subplots.append("volume")
if show_rsi:
    active_subplots.append("rsi")

num_rows = len(active_subplots)
row_heights = [1.0] if num_rows == 1 else ([0.74, 0.26] if num_rows == 2 else [0.62, 0.16, 0.22])

fig = make_subplots(
    rows=num_rows,
    cols=1,
    shared_xaxes=True,
    vertical_spacing=0.03,
    row_heights=row_heights
)

# 1. Candlesticks
fig.add_trace(go.Candlestick(
    x=df_chart.index,
    open=df_chart["Open"], high=df_chart["High"],
    low=df_chart["Low"], close=df_chart["Close"],
    increasing_line_color="#26a69a", decreasing_line_color="#ef5350",
    name="Price"
), row=1, col=1)

# 2. Bollinger & SMA20
fig.add_trace(go.Scatter(x=df_chart.index, y=df_chart["SMA20"], line=dict(color="#2962ff", width=1.2), name="20 SMA"), row=1, col=1)
fig.add_trace(go.Scatter(x=df_chart.index, y=df_chart["BB_Upper"], line=dict(color="rgba(239,83,80,0.45)", width=1), name="BB Upper"), row=1, col=1)
fig.add_trace(go.Scatter(x=df_chart.index, y=df_chart["BB_Lower"], line=dict(color="rgba(38,166,154,0.45)", width=1), name="BB Lower"), row=1, col=1)

# 3. VWAP & Deviation Bands
if show_vwap:
    fig.add_trace(go.Scatter(x=df_chart.index, y=df_chart["VWAP"], line=dict(color="#ff9800", width=1.6), name="VWAP"), row=1, col=1)
    fig.add_trace(go.Scatter(x=df_chart.index, y=df_chart["VWAP_U1"], line=dict(color="rgba(255,152,0,0.35)", width=1, dash="dot"), name="VWAP +1σ"), row=1, col=1)
    fig.add_trace(go.Scatter(x=df_chart.index, y=df_chart["VWAP_L1"], line=dict(color="rgba(255,152,0,0.35)", width=1, dash="dot"), name="VWAP -1σ"), row=1, col=1)

# 4. Volume Profile (VPVR) Right-Side Overlay
if show_vpvr and vpvr is not None:
    fig.add_trace(go.Bar(
        x=vpvr["hist"],
        y=vpvr["centers"],
        orientation="h",
        xaxis="x2",
        yaxis="y",
        marker=dict(color="rgba(100, 181, 246, 0.22)", line=dict(color="rgba(100, 181, 246, 0.45)", width=0.5)),
        name="Volume Profile",
        showlegend=False,
        hoverinfo="y+x"
    ))
    fig.update_layout(
        xaxis2=dict(
            overlaying="x",
            side="top",
            range=[max(vpvr["hist"]) * 4.5, 0],
            showgrid=False,
            showticklabels=False,
            zeroline=False
        )
    )

# 5. Automated Pattern Recognition Annotations
if show_patterns:
    pat_df = df_chart[df_chart["Pattern"] != ""]
    if not pat_df.empty:
        bull_pats = pat_df[pat_df["Pattern"].str.startswith("Bull")]
        bear_pats = pat_df[pat_df["Pattern"].str.startswith("Bear")]
        if not bull_pats.empty:
            fig.add_trace(go.Scatter(
                x=bull_pats.index, y=bull_pats["Low"] * 0.996,
                mode="markers+text", text=bull_pats["Pattern"], textposition="bottom center",
                marker=dict(symbol="triangle-up", size=9, color="#00e676"),
                textfont=dict(size=9, color="#00e676"), name="Bull Patterns"
            ), row=1, col=1)
        if not bear_pats.empty:
            fig.add_trace(go.Scatter(
                x=bear_pats.index, y=bear_pats["High"] * 1.004,
                mode="markers+text", text=bear_pats["Pattern"], textposition="top center",
                marker=dict(symbol="triangle-down", size=9, color="#ff5252"),
                textfont=dict(size=9, color="#ff5252"), name="Bear Patterns"
            ), row=1, col=1)

# 6. TradingView-Style Right-Axis Price Tags & Horizontal Lines
tv_levels = [
    (current_price, f"{current_price:.2f}", "#26a69a" if df_chart["Close"].iloc[-1] >= df_chart["Open"].iloc[-1] else "#ef5350", "solid"),
    (swing_high,    f"SH {swing_high:.2f}", "#00acc1", "dot"),
    (swing_low,     f"SLw {swing_low:.2f}", "#00acc1", "dot"),
    (stop_loss,     f"SL {stop_loss:.2f}",  "#e53935", "dash"),
    (target_1,      f"T1 {target_1:.2f}",   "#43a047", "dash"),
    (target_2,      f"T2 {target_2:.2f}",   "#2e7d32", "dash"),
]
if vpvr is not None:
    tv_levels.append((vpvr["poc"], f"POC {vpvr['poc']:.2f}", "#ab47bc", "dashdot"))

for y_val, tag_text, bg_col, dash_style in tv_levels:
    fig.add_hline(y=y_val, line_dash=dash_style, line_color=bg_col, line_width=1.1, row=1, col=1)
    fig.add_annotation(
        xref="paper", x=1.002, yref="y", y=y_val,
        text=f"<b>{tag_text}</b>",
        showarrow=False,
        xanchor="left", yanchor="middle",
        font=dict(color="white", size=10),
        bgcolor=bg_col,
        borderpad=3
    )

# 7. Volume + OFI Subplot
current_row = 2
if "volume" in active_subplots:
    vol_colors = np.where(
        df_chart["OFI_Z"] > 1.5, "#00e5ff",
        np.where(df_chart["OFI_Z"] < -1.5, "#ff1744",
                 np.where(df_chart["Close"] >= df_chart["Open"], "rgba(38,166,154,0.65)", "rgba(239,83,80,0.65)"))
    )
    fig.add_trace(go.Bar(
        x=df_chart.index, y=df_chart["Volume"],
        marker_color=vol_colors, name="Vol / OFI Spike"
    ), row=current_row, col=1)
    fig.update_yaxes(title_text="Vol/OFI", side="right", row=current_row, col=1)
    current_row += 1

# 8. RSI Subplot with Right-Axis Tag
if "rsi" in active_subplots:
    fig.add_trace(go.Scatter(
        x=df_chart.index, y=df_chart["RSI_Aligned"],
        line=dict(color="#66bb6a", width=1.8), name=f"RSI ({rsi_period})"
    ), row=current_row, col=1)
    fig.add_hline(y=rsi_upper, line_dash="dash", line_color="#ef5350", line_width=1, row=current_row, col=1)
    fig.add_hline(y=50, line_dash="dot", line_color="gray", line_width=0.9, row=current_row, col=1)
    fig.add_hline(y=rsi_lower, line_dash="dash", line_color="#26a69a", line_width=1, row=current_row, col=1)
    fig.update_yaxes(range=[0, 100], title_text=f"RSI {rsi_period}", side="right", row=current_row, col=1)
    fig.add_annotation(
        xref="paper", x=1.002, yref=f"y{current_row}", y=latest_rsi,
        text=f"<b>{latest_rsi:.2f}</b>",
        showarrow=False, xanchor="left", yanchor="middle",
        font=dict(color="white", size=10), bgcolor="#2e7d32", borderpad=3
    )

fig.update_layout(
    height=680,
    xaxis_rangeslider_visible=False,
    template="plotly_dark",
    margin=dict(l=10, r=78, t=20, b=15),
    legend=dict(orientation="h", yanchor="bottom", y=1.01, xanchor="left", x=0)
)
fig.update_yaxes(side="right", row=1, col=1)

st.plotly_chart(fig, use_container_width=True)

# --- BOTTOM-LEFT TRADINGVIEW-STYLE INDICATOR CONTROLS ---
b_col1, b_col2, _ = st.columns([1.2, 1.6, 5.2])
with b_col1:
    st.toggle("Show RSI", value=True, key="show_rsi_ctrl")
with b_col2:
    with st.popover("⚙ Indicators & Quant Layers"):
        st.toggle("Show Volume & OFI", value=True, key="show_vol_ctrl")
        st.toggle("Show Volume Profile (VPVR)", value=True, key="show_vpvr_ctrl")
        st.toggle("Show VWAP & σ Bands", value=True, key="show_vwap_ctrl")
        st.toggle("Show Pattern Annotations", value=True, key="show_patterns_ctrl")
        st.toggle("Show MTF Correlation Heatmap", value=False, key="show_heatmap_ctrl")
        st.divider()
        st.selectbox("RSI Timeframe", options=list(TIMEFRAME_MAP.keys()), index=list(TIMEFRAME_MAP.keys()).index(chart_tf), key="rsi_tf_ctrl")
        st.number_input("RSI Period", min_value=2, max_value=50, value=14, step=1, key="rsi_period_ctrl")
        st.number_input("RSI Lower", min_value=1, max_value=99, value=40, step=1, key="rsi_lower_ctrl")
        st.number_input("RSI Upper", min_value=1, max_value=99, value=60, step=1, key="rsi_upper_ctrl")

# --- OPTIONAL MULTI-TIMEFRAME CORRELATION HEATMAP ---
if show_heatmap:
    st.markdown("#### Multi-Timeframe & Cross-Asset Return Correlation Matrix (1D)")
    close_dict = {}
    for item in DEFAULT_WATCHLIST[:8]:
        s = item["Ticker"]
        d = fetch_data(s, "1d")
        if not d.empty:
            close_dict[s.replace(".NS", "")] = d["Close"].tail(60).pct_change()
    if len(close_dict) > 1:
        corr_df = pd.DataFrame(close_dict).corr().round(2)
        hm_fig = go.Figure(data=go.Heatmap(
            z=corr_df.values,
            x=corr_df.columns,
            y=corr_df.index,
            colorscale="RdBu",
            zmin=-1, zmax=1,
            text=corr_df.values,
            texttemplate="%{text}"
        ))
        hm_fig.update_layout(height=340, template="plotly_dark", margin=dict(l=20, r=20, t=20, b=20))
        st.plotly_chart(hm_fig, use_container_width=True)
