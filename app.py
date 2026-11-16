import streamlit st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from concurrent.futures import ThreadPoolExecutor, as_completed

# ---------------------------------------------------------
# PAGE CONFIGURATION & INVESTING.COM STYLE CSS
# ---------------------------------------------------------
st.set_page_config(
    page_title="Ultra Accuracy Technical Scanner",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    .block-container { padding-top: 1rem; padding-bottom: 2rem; }
    .tf-card {
        border-radius: 10px;
        padding: 15px 12px;
        text-align: center;
        font-weight: 800;
        border: 2px solid #e2e8f0;
        margin-bottom: 10px;
        font-size: 1.1rem;
    }
    .tf-title { font-size: 0.85rem; color: #334155; text-transform: uppercase; margin-bottom: 6px; font-weight: 700; }
    .sig-strong-buy { background-color: #16a34a; color: #ffffff; border: 2px solid #16a34a; box-shadow: 0 4px 14px rgba(22, 163, 74, 0.4); }
    .sig-buy { background-color: #22c55e; color: #ffffff; border: 2px solid #15803d; }
    .sig-neutral { background-color: #64748b; color: #ffffff; border: 2px solid #475569; }
    .sig-sell { background-color: #ef4444; color: #ffffff; border: 2px solid #b91c1c; }
    .sig-strong-sell { background-color: #dc2626; color: #ffffff; border: 2px solid #991b1b; box-shadow: 0 4px 14px rgba(220, 38, 38, 0.4); }
    .summary-banner {
        border-radius: 10px;
        padding: 16px;
        text-align: center;
        font-size: 1.3rem;
        font-weight: 900;
        letter-spacing: 1px;
        margin: 10px 0 20px 0;
        text-transform: uppercase;
    }
    /* Blinking Live Market Badge */
    .live-badge-wrapper {
        display: flex;
        align-items: center;
        justify-content: flex-end;
        padding: 10px 20px;
    }
    .live-badge {
        display: inline-flex;
        align-items: center;
        background-color: #16a34a;
        color: white;
        padding: 6px 14px;
        border-radius: 20px;
        font-weight: 800;
        font-size: 0.9rem;
        letter-spacing: 0.5px;
        box-shadow: 0 0 15px rgba(22, 163, 74, 0.6);
        animation: pulse 1.5s infinite;
    }
    .live-dot {
        height: 10px;
        width: 10px;
        background-color: #ffffff;
        border-radius: 50%;
        display: inline-block;
        margin-right: 8px;
        box-shadow: 0 0 8px #ffffff;
    }
    @keyframes pulse {
        0% { transform: scale(1); box-shadow: 0 0 15px rgba(22, 163, 74, 0.6); }
        50% { transform: scale(1.05); box-shadow: 0 0 25px rgba(22, 163, 74, 0.9); }
        100% { transform: scale(1); box-shadow: 0 0 15px rgba(22, 163, 74, 0.6); }
    }
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------
# UNIVERSE: FULL NIFTY 50 CONSTITUENTS (NSE)
# ---------------------------------------------------------
NIFTY_50 = [
    "RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "ICICIBANK.NS", "BHARTIARTL.NS",
    "SBIN.NS", "INFY.NS", "LICI.NS", "ITC.NS", "HINDUNILVR.NS",
    "LT.NS", "BAJFINANCE.NS", "HCLTECH.NS", "MARUTI.NS", "SUNPHARMA.NS",
    "ADANIENT.NS", "KOTAKBANK.NS", "TITAN.NS", "ONGC.NS", "TATAMOTORS.NS",
    "NTPC.NS", "AXISBANK.NS", "ADANIPORTS.NS", "ULTRACEMCO.NS", "ASIANPAINT.NS",
    "COALINDIA.NS", "BAJAJFINSV.NS", "NESTLEIND.NS", "WIPRO.NS", "M&M.NS",
    "POWERGRID.NS", "JSWSTEEL.NS", "TATASTEEL.NS", "GRASIM.NS", "TECHM.NS",
    "HINDALCO.NS", "INDUSINDBK.NS", "SBILIFE.NS", "DRREDDY.NS", "CIPLA.NS",
    "BAJAJ-AUTO.NS", "TATACONSUM.NS", "BRITANNIA.NS", "APOLLOHOSP.NS", "EICHERMOT.NS",
    "DIVISLAB.NS", "HEROMOTOCO.NS", "BPCL.NS", "SHRIRAMFIN.NS", "TRENT.NS"
]

TIMEFRAMES = {
    "15m": {"interval": "15m", "period": "5d", "label": "15 Min"},
    "1h":  {"interval": "1h",  "period": "1mo", "label": "Hourly"},
    "1d":  {"interval": "1d",  "period": "1y",  "label": "Daily"},
    "1wk": {"interval": "1wk", "period": "2y",  "label": "Weekly"}
}

# ---------------------------------------------------------
# TECHNICAL ENGINE (MOVING AVERAGES, INDICATORS, PIVOTS)
# ---------------------------------------------------------
def compute_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))

def evaluate_timeframe(df: pd.DataFrame) -> dict:
    if df is None or len(df) < 30:
        return None

    close = df["Close"]
    high = df["High"]
    low = df["Low"]
    volume = df["Volume"] if "Volume" in df.columns else pd.Series(1000, index=df.index)
    curr_price = float(close.iloc[-1])

    ma_periods = [5, 10, 20, 50, 100, 200]
    ma_buy, ma_sell = 0, 0
    ma_details = []

    for p in ma_periods:
        sma_val = float(close.rolling(p).mean().iloc[-1]) if len(close) >= p else float(close.mean())
        ema_val = float(close.ewm(span=p, adjust=False).mean().iloc[-1]) if len(close) >= p else float(close.mean())
        sma_sig = "Buy" if curr_price > sma_val else "Sell"
        ema_sig = "Buy" if curr_price > ema_val else "Sell"
        ma_buy += (1 if sma_sig == "Buy" else 0) + (1 if ema_sig == "Buy" else 0)
        ma_sell += (1 if sma_sig == "Sell" else 0) + (1 if ema_sig == "Sell" else 0)
        ma_details.append({"Period": f"MA{p}", "SMA": round(sma_val, 2), "SMA_Action": sma_sig, "EMA": round(ema_val, 2), "EMA_Action": ema_sig})

    ind_buy, ind_sell, ind_neut = 0, 0, 0
    ind_details = []

    rsi_series = compute_rsi(close, 14)
    rsi_val = float(rsi_series.iloc[-1])
    if rsi_val > 55 and rsi_val < 75: rsi_act = "Buy"; ind_buy += 1
    elif rsi_val < 45 and rsi_val > 25: rsi_act = "Sell"; ind_sell += 1
    elif rsi_val <= 25: rsi_act = "Buy"; ind_buy += 1
    elif rsi_val >= 75: rsi_act = "Sell"; ind_sell += 1
    else: rsi_act = "Neutral"; ind_neut += 1
    ind_details.append({"Indicator": "RSI (14)", "Value": round(rsi_val, 2), "Action": rsi_act})

    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    macd_line = ema12 - ema26
    signal_line = macd_line.ewm(span=9, adjust=False).mean()
    macd_val = float(macd_line.iloc[-1])
    sig_val = float(signal_line.iloc[-1])
    macd_act = "Buy" if macd_val > sig_val else "Sell"
    if macd_act == "Buy": ind_buy += 1
    else: ind_sell += 1
    ind_details.append({"Indicator": "MACD (12,26)", "Value": round(macd_val, 2), "Action": macd_act})

    low14 = low.rolling(14).min()
    high14 = high.rolling(14).max()
    stoch_k = 100 * (close - low14) / (high14 - low14).replace(0, np.nan)
    stoch_val = float(stoch_k.rolling(3).mean().iloc[-1])
    if stoch_val > 50 and stoch_val < 80: st_act = "Buy"; ind_buy += 1
    elif stoch_val < 50 and stoch_val > 20: st_act = "Sell"; ind_sell += 1
    else: st_act = "Neutral"; ind_neut += 1
    ind_details.append({"Indicator": "STOCH (9,6)", "Value": round(stoch_val, 2), "Action": st_act})

    tp = (high + low + close) / 3
    cci = (tp - tp.rolling(14).mean()) / (0.015 * tp.rolling(14).apply(lambda x: np.mean(np.abs(x - np.mean(x))), raw=True))
    cci_val = float(cci.iloc[-1])
    if cci_val > 50: cci_act = "Buy"; ind_buy += 1
    elif cci_val < -50: cci_act = "Sell"; ind_sell += 1
    else: cci_act = "Neutral"; ind_neut += 1
    ind_details.append({"Indicator": "CCI (14)", "Value": round(cci_val, 2), "Action": cci_act})

    willr = -100 * (high14 - close) / (high14 - low14).replace(0, np.nan)
    willr_val = float(willr.iloc[-1])
    if willr_val > -50: wr_act = "Buy"; ind_buy += 1
    elif willr_val < -50: wr_act = "Sell"; ind_sell += 1
    else: wr_act = "Neutral"; ind_neut += 1
    ind_details.append({"Indicator": "Williams %R", "Value": round(willr_val, 2), "Action": wr_act})

    roc_val = float(((close.iloc[-1] - close.iloc[-13]) / close.iloc[-13]) * 100)
    roc_act = "Buy" if roc_val > 0 else "Sell"
    if roc_act == "Buy": ind_buy += 1
    else: ind_sell += 1
    ind_details.append({"Indicator": "ROC (12)", "Value": round(roc_val, 2), "Action": roc_act})

    ema13 = float(close.ewm(span=13, adjust=False).mean().iloc[-1])
    bbp_val = float((high.iloc[-1] - ema13) + (low.iloc[-1] - ema13))
    bbp_act = "Buy" if bbp_val > 0 else "Sell"
    if bbp_act == "Buy": ind_buy += 1
    else: ind_sell += 1
    ind_details.append({"Indicator": "Bull/Bear Power (13)", "Value": round(bbp_val, 2), "Action": bbp_act})

    bb_mid = close.rolling(20).mean()
    bb_std = close.rolling(20).std()
    bb_upper = bb_mid + 2 * bb_std
    bb_lower = bb_mid - 2 * bb_std
    bb_act = "Buy" if curr_price > float(bb_mid.iloc[-1]) else "Sell"
    if bb_act == "Buy": ind_buy += 1
    else: ind_sell += 1
    ind_details.append({"Indicator": "Bollinger (20,2)", "Value": round(float(bb_mid.iloc[-1]), 2), "Action": bb_act})

    total_buy = ma_buy + ind_buy
    total_sell = ma_sell + ind_sell
    total_signals = total_buy + total_sell + ind_neut
    net_score = ((total_buy - total_sell) / max(total_signals, 1)) * 100

    if net_score >= 45: signal = "STRONG BUY"
    elif net_score >= 15: signal = "BUY"
    elif net_score <= -45: signal = "STRONG SELL"
    elif net_score <= -15: signal = "SELL"
    else: signal = "NEUTRAL"

    prev_h = float(high.iloc[-2])
    prev_l = float(low.iloc[-2])
    prev_c = float(close.iloc[-2])
    pp = (prev_h + prev_l + prev_c) / 3.0
    rng = prev_h - prev_l

    pivots = pd.DataFrame([
        {"Level": "R3", "Classic": round(prev_h + 2 * (pp - prev_l), 2), "Fibonacci": round(pp + 1.000 * rng, 2)},
        {"Level": "R2", "Classic": round(pp + rng, 2),                  "Fibonacci": round(pp + 0.618 * rng, 2)},
        {"Level": "R1", "Classic": round(2 * pp - prev_l, 2),           "Fibonacci": round(pp + 0.382 * rng, 2)},
        {"Level": "Pivot Point", "Classic": round(pp, 2),               "Fibonacci": round(pp, 2)},
        {"Level": "S1", "Classic": round(2 * pp - prev_h, 2),           "Fibonacci": round(pp - 0.382 * rng, 2)},
        {"Level": "S2", "Classic": round(pp - rng, 2),                  "Fibonacci": round(pp - 0.618 * rng, 2)},
        {"Level": "S3", "Classic": round(prev_l - 2 * (prev_h - pp), 2),"Fibonacci": round(pp - 1.000 * rng, 2)},
    ])

    return {
        "price": curr_price, "rsi": round(rsi_val, 2), "signal": signal, "score": round(net_score, 1),
        "ma_buy": ma_buy, "ma_sell": ma_sell, "ind_buy": ind_buy, "ind_sell": ind_sell,
        "ma_details": pd.DataFrame(ma_details), "ind_details": pd.DataFrame(ind_details), "pivots": pivots,
        "df": df.assign(BB_Mid=bb_mid, BB_Upper=bb_upper, BB_Lower=bb_lower, RSI=rsi_series, Volume=volume)
    }

# ---------------------------------------------------------
# MULTI-TIMEFRAME DATA FETCHER & ALIGNMENT ENGINE
# ---------------------------------------------------------
@st.cache_data(ttl=180, show_spinner=False)
def analyze_single_stock(ticker: str) -> dict:
    tf_results = {}
    for tf_key, cfg in TIMEFRAMES.items():
        try:
            df = yf.download(ticker, period=cfg["period"], interval=cfg["interval"], progress=False, auto_adjust=True)
            if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
            df.dropna(inplace=True)
            res = evaluate_timeframe(df)
            if res: tf_results[tf_key] = res
        except Exception: continue

    if "1d" not in tf_results: return None

    d1 = tf_results["1d"]
    df_1d = d1["df"]
    prev_close = float(df_1d["Close"].iloc[-2]) if len(df_1d) > 1 else d1["price"]
    chg_pct = ((d1["price"] - prev_close) / prev_close) * 100

    weights = {"15m": 0.15, "1h": 0.25, "1d": 0.35, "1wk": 0.25}
    weighted_score = 0.0
    total_w = 0.0
    buy_tf_count = 0
    sell_tf_count = 0

    for k, w in weights.items():
        if k in tf_results:
            sc = tf_results[k]["score"]
            sig = tf_results[k]["signal"]
            weighted_score += sc * w
            total_w += w
            if "BUY" in sig: buy_tf_count += 1
            elif "SELL" in sig: sell_tf_count += 1

    final_score = round(weighted_score / max(total_w, 0.01), 1)

    if final_score >= 40 and buy_tf_count >= 3: master_signal = "STRONG BUY"
    elif final_score >= 12: master_signal = "BUY"
    elif final_score <= -40 and sell_tf_count >= 3: master_signal = "STRONG SELL"
    elif final_score <= -12: master_signal = "SELL"
    else: master_signal = "NEUTRAL"

    atr = float((df_1d["High"] - df_1d["Low"]).rolling(14).mean().iloc[-1])
    if "BUY" in master_signal:
        stop_loss = round(d1["price"] - 1.5 * atr, 2); target = round(d1["price"] + 3.0 * atr, 2)
    elif "SELL" in master_signal:
        stop_loss = round(d1["price"] + 1.5 * atr, 2); target = round(d1["price"] - 3.0 * atr, 2)
    else:
        stop_loss = round(d1["price"] - 1.5 * atr, 2); target = round(d1["price"] + 1.5 * atr, 2)

    return {
        "Ticker": ticker.replace(".NS", ""), "FullTicker": ticker, "Close": round(d1["price"], 2),
        "Chg %": round(chg_pct, 2), "RSI (14)": d1["rsi"],
        "15m": tf_results.get("15m", {}).get("signal", "N/A"), "1h": tf_results.get("1h", {}).get("signal", "N/A"),
        "1d": tf_results.get("1d", {}).get("signal", "N/A"), "1wk": tf_results.get("1wk", {}).get("signal", "N/A"),
        "Master Signal": master_signal, "Score": final_score, "Stop Loss": stop_loss, "Target": target, "tf_data": tf_results
    }

@st.cache_data(ttl=180, show_spinner=False)
def scan_all_equities(tickers: list) -> list:
    results = []
    with ThreadPoolExecutor(max_workers=12) as executor:
        futures = {executor.submit(analyze_single_stock, t): t for t in tickers}
        for future in as_completed(futures):
            res = future.result()
            if res: results.append(res)
    return results

def get_signal_css(signal: str) -> str:
    s = signal.upper()
    if s == "STRONG BUY": return "sig-strong-buy"
    if s == "BUY": return "sig-buy"
    if s == "STRONG SELL": return "sig-strong-sell"
    if s == "SELL": return "sig-sell"
    return "sig-neutral"

def style_dataframe(df: pd.DataFrame):
    def color_cell(val):
        v = str(val).upper()
        if v == "STRONG BUY": return "background-color: #15803d; color: white; font-weight: bold;"
        elif v == "BUY": return "background-color: #22c55e; color: white; font-weight: bold;"
        elif v == "STRONG SELL": return "background-color: #b91c1c; color: white; font-weight: bold;"
        elif v == "SELL": return "background-color: #ef4444; color: white; font-weight: bold;"
        elif v == "NEUTRAL": return "background-color: #64748b; color: white;"
        return ""
    signal_cols = [c for c in ["15m", "1h", "1d", "1wk", "Master Signal"] if c in df.columns]
    return df.style.map(color_cell, subset=signal_cols).format({
        "Close": "₹{:.2f}", "Chg %": "{:+.2f}%", "RSI (14)": "{:.1f}", "Score": "{:+.1f}",
        "Stop Loss": "₹{:.2f}", "Target": "₹{:.2f}"
    })

# ---------------------------------------------------------
# SIDEBAR CONTROLS
# ---------------------------------------------------------
with st.sidebar:
    st.header("Scanner Parameters")
    primary_tf = st.selectbox("Chart & Detail Timeframe", ["1d", "1h", "15m", "1wk"], index=0)
    view_mode = st.radio(
        "Screener Ranking Mode",
        ["All Scanned Equities", "Top 25 Buy Signals", "Top 25 Sell Signals"],
        index=0
    )
    signal_filter = st.multiselect(
        "Filter Master Signals",
        ["STRONG BUY", "BUY", "NEUTRAL", "SELL", "STRONG SELL"],
        default=["STRONG BUY", "BUY", "NEUTRAL", "SELL", "STRONG SELL"]
    )
    if st.button("Refresh Live Market Data", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

# ---------------------------------------------------------
# EXECUTE SCAN & COMPUTE MARKET METRICS
# ---------------------------------------------------------
with st.spinner("Scanning Nifty 50 with Ultra Accuracy Engine..."):
    raw_data = scan_all_equities(NIFTY_50)

if not raw_data:
    st.error("Unable to fetch live market data.")
    st.stop()

df_all = pd.DataFrame([{k: v for k, v in item.items() if k != "tf_data"} for item in raw_data])
data_map = {item["Ticker"]: item for item in raw_data}

strong_buy_cnt = len(df_all[df_all["Master Signal"] == "STRONG BUY"])
buy_cnt = len(df_all[df_all["Master Signal"].isin(["STRONG BUY", "BUY"])])
strong_sell_cnt = len(df_all[df_all["Master Signal"].isin(["STRONG SELL"])])
sell_cnt = len(df_all[df_all["Master Signal"].isin(["STRONG SELL", "SELL"])])
avg_rsi = round(df_all["RSI (14)"].mean(), 1)

# Top Banner: Live Market Status Indicator
st.markdown("""
<div class="live-badge-wrapper">
    <div class="live-badge"><span class="live-dot"></span>LIVE MARKET</div>
</div>
""", unsafe_allow_html=True)

k1, k2, k3, k4 = st.columns(4)
k1.metric("Scanned Equities", f"{len(df_all)} / 50")
k2.metric("Buy Setups (Strong)", f"{buy_cnt} ({strong_buy_cnt})")
k3.metric("Sell Setups (Strong)", f"{sell_cnt} ({strong_sell_cnt})")
k4.metric("Avg Market RSI (14)", f"{avg_rsi}")

st.markdown("---")

if view_mode == "Top 25 Buy Signals":
    df_filtered = df_all[df_all["Score"] > 0].sort_values(by="Score", ascending=False).head(25)
elif view_mode == "Top 25 Sell Signals":
    df_filtered = df_all[df_all["Score"] < 0].sort_values(by="Score", ascending=True).head(25)
else:
    df_filtered = df_all[df_all["Master Signal"].isin(signal_filter)].sort_values(by="Score", ascending=False)

# ---------------------------------------------------------
# MAIN WORKSPACE: LEFT SCREENER TABLE | RIGHT INVESTING.COM PANEL
# ---------------------------------------------------------
left_col, right_col = st.columns([1.2, 1.4], gap="large")

with left_col:
    st.subheader(f"Scanner Results ({len(df_filtered)})")
    display_cols = ["Ticker", "Close", "Chg %", "RSI (14)", "15m", "1h", "1d", "1wk", "Master Signal", "Score"]
    st.dataframe(
        style_dataframe(df_filtered[display_cols]),
        use_container_width=True,
        height=650,
        hide_index=True
    )

with right_col:
    ticker_options = df_filtered["Ticker"].tolist() if not df_filtered.empty else df_all["Ticker"].tolist()
    selected_ticker = st.selectbox("Select Equity for Deep Technical Analysis", ticker_options, index=0)
    stock_obj = data_map[selected_ticker]
    tf_dict = stock_obj["tf_data"]
    active_tf_data = tf_dict.get(primary_tf, tf_dict["1d"])

    st.markdown(f"### {selected_ticker} — ₹{stock_obj['Close']:.2f} ({stock_obj['Chg %']:+.2f}%)")

    # 1. MULTI-TIMEFRAME ALIGNMENT CARDS
    tf_cols = st.columns(4)
    for idx, (tf_k, tf_meta) in enumerate(TIMEFRAMES.items()):
        sig_txt = tf_dict[tf_k]["signal"] if tf_k in tf_dict else "N/A"
        css_cls = get_signal_css(sig_txt)
        with tf_cols[idx]:
            st.markdown(f"""
            <div class="tf-card {css_cls}">
                <div class="tf-title">{tf_meta['label']} ({tf_k})</div>
                <div>{sig_txt}</div>
            </div>
            """, unsafe_allow_html=True)

    master_sig = stock_obj["Master Signal"]
    master_css = get_signal_css(master_sig)
    st.markdown(f"""
    <div class="summary-banner {master_css}">
        MASTER SIGNAL: {master_sig} (Confidence Score: {stock_obj['Score']:+.1f})
    </div>
    """, unsafe_allow_html=True)

    t1, t2, t3 = st.columns(3)
    t1.metric("Current Price", f"₹{stock_obj['Close']:.2f}")
    t2.metric("ATR Stop Loss", f"₹{stock_obj['Stop Loss']:.2f}")
    t3.metric("ATR Target (1:2)", f"₹{stock_obj['Target']:.2f}")

    tab_summary, tab_chart, tab_details = st.tabs(["Technical Summary & Pivots", "Interactive Chart", "Indicator Breakdown"])

    with tab_summary:
        st.markdown(f"**Technical Summary ({TIMEFRAMES[primary_tf]['label']})**")
        sum_df = pd.DataFrame([
            {
                "Category": "Moving Averages (12)",
                "Summary": "Strong Buy" if active_tf_data["ma_buy"] >= 9 else ("Buy" if active_tf_data["ma_buy"] > active_tf_data["ma_sell"] else ("Strong Sell" if active_tf_data["ma_sell"] >= 9 else "Sell")),
                "Buy": active_tf_data["ma_buy"],
                "Sell": active_tf_data["ma_sell"]
            },
            {
                "Category": "Technical Indicators (8)",
                "Summary": "Strong Buy" if active_tf_data["ind_buy"] >= 6 else ("Buy" if active_tf_data["ind_buy"] > active_tf_data["ind_sell"] else ("Strong Sell" if active_tf_data["ind_sell"] >= 6 else "Sell")),
                "Buy": active_tf_data["ind_buy"],
                "Sell": active_tf_data["ind_sell"]
            }
        ])
        st.dataframe(sum_df, use_container_width=True, hide_index=True)

        st.markdown(f"**Pivot Points ({TIMEFRAMES[primary_tf]['label']})**")
        st.dataframe(active_tf_data["pivots"], use_container_width=True, hide_index=True)

    with tab_chart:
        plot_df = active_tf_data["df"].tail(80)
        
        # Investing.com Style Subplots: Price Chart (70%) + Volume Bars (30%)
        fig = make_subplots(
            rows=2, cols=1, 
            shared_xaxes=True, 
            vertical_spacing=0.03, 
            row_heights=[0.70, 0.30]
        )

        # Price Candlesticks
        fig.add_trace(go.Candlestick(
            x=plot_df.index, 
            open=plot_df["Open"], 
            high=plot_df["High"], 
            low=plot_df["Low"], 
            close=plot_df["Close"],
            name="Price", 
            increasing_line_color="#16a34a", 
            decreasing_line_color="#dc2626"
        ), row=1, col=1)

        # Bollinger Bands
        fig.add_trace(go.Scatter(x=plot_df.index, y=plot_df["BB_Upper"], line=dict(color="rgba(59,130,246,0.3)", width=1), name="BB Upper"), row=1, col=1)
        fig.add_trace(go.Scatter(x=plot_df.index, y=plot_df["BB_Mid"], line=dict(color="#f59e0b", width=1.2), name="20 SMA"), row=1, col=1)
        fig.add_trace(go.Scatter(x=plot_df.index, y=plot_df["BB_Lower"], line=dict(color="rgba(59,130,246,0.3)", width=1), fill="tonexty", fillcolor="rgba(59,130,246,0.04)", name="BB Lower"), row=1, col=1)

        # Volume Bars Colored by Price Action
        vol_colors = ["#16a34a" if row["Close"] >= row["Open"] else "#dc2626" for _, row in plot_df.iterrows()]
        fig.add_trace(go.Bar(
            x=plot_df.index, 
            y=plot_df["Volume"], 
            marker_color=vol_colors,
            name="Volume",
            opacity=0.6
        ), row=2, col=1)

        # Persistent Layout Configuration Prevent Disappearances
        fig.update_layout(
            height=520, 
            margin=dict(l=10, r=10, t=10, b=10), 
            xaxis_rangeslider_visible=False,
            template="plotly_white",
            showlegend=False,
            hovermode="x unified"
        )
        
        # Ensure Axes remain locked and responsive
        fig.update_xaxes(showgrid=True, gridcolor="#e2e8f0")
        fig.update_yaxes(showgrid=True, gridcolor="#e2e8f0")

        st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': True, 'responsive': True})

    with tab_details:
        c_ma, c_ind = st.columns(2)
        with c_ma:
            st.markdown("**Moving Averages Detail**")
            st.dataframe(active_tf_data["ma_details"], use_container_width=True, hide_index=True)
        with c_ind:
            st.markdown("**Oscillators & Trend Detail**")
            st.dataframe(active_tf_data["ind_details"], use_container_width=True, hide_index=True)
