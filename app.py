import streamlit as st
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

if "fullscreen_section" not in st.session_state:
    st.session_state.fullscreen_section = None

def toggle_fullscreen(section_key: str):
    if st.session_state.fullscreen_section == section_key:
        st.session_state.fullscreen_section = None
    else:
        st.session_state.fullscreen_section = section_key

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
    /* Fullscreen Mode Banner & Container Styling */
    .fs-active-banner {
        background: linear-gradient(90deg, #0f172a 0%, #1e293b 100%);
        color: #f8fafc;
        padding: 10px 18px;
        border-radius: 8px;
        font-weight: 700;
        font-size: 0.95rem;
        margin-bottom: 12px;
        display: flex;
        align-items: center;
        justify-content: space-between;
        border-left: 5px solid #22c55e;
    }
    .section-header-box {
        font-size: 1.15rem;
        font-weight: 800;
        color: #0f172a;
        padding-top: 4px;
    }
    /* Market Overview Card Styling */
    .mkt-card {
        background-color: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 10px;
        padding: 12px 14px 4px 14px;
        box-shadow: 0 1px 4px rgba(15, 23, 42, 0.05);
        margin-bottom: 6px;
    }
    .mkt-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        font-size: 0.82rem;
        font-weight: 700;
        color: #475569;
        text-transform: uppercase;
    }
    .mkt-price {
        font-size: 1.25rem;
        font-weight: 800;
        color: #0f172a;
        margin-top: 2px;
    }
    .mkt-pos { color: #16a34a; font-weight: 700; font-size: 0.85rem; }
    .mkt-neg { color: #dc2626; font-weight: 700; font-size: 0.85rem; }
    /* Blinking Live Market Badge */
    .top-bar-container {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 4px 0 12px 0;
        border-bottom: 1px solid #e2e8f0;
        margin-bottom: 14px;
    }
    .app-main-title {
        font-size: 1.45rem;
        font-weight: 900;
        color: #0f172a;
        letter-spacing: -0.3px;
    }
    .live-badge {
        display: inline-flex;
        align-items: center;
        background-color: #16a34a;
        color: white;
        padding: 6px 14px;
        border-radius: 20px;
        font-weight: 800;
        font-size: 0.88rem;
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
# MARKET OVERVIEW CONFIGURATION
# ---------------------------------------------------------
INDIAN_INDICES = [
    {"name": "Nifty 50", "ticker": "^NSEI", "prefix": ""},
    {"name": "Sensex", "ticker": "^BSESN", "prefix": ""},
    {"name": "Bank Nifty", "ticker": "^NSEBANK", "prefix": ""},
    {"name": "India VIX", "ticker": "^INDIAVIX", "prefix": ""}
]

GLOBAL_ASSETS = [
    {"name": "Dow Jones", "ticker": "^DJI", "category": "US Indices", "prefix": ""},
    {"name": "S&P 500", "ticker": "^GSPC", "category": "US Indices", "prefix": ""},
    {"name": "Nasdaq", "ticker": "^IXIC", "category": "US Indices", "prefix": ""},
    {"name": "Crude Oil (WTI)", "ticker": "CL=F", "category": "Commodities", "prefix": "$"},
    {"name": "Gold", "ticker": "GC=F", "category": "Commodities", "prefix": "$"},
    {"name": "Bitcoin", "ticker": "BTC-USD", "category": "Crypto & Forex", "prefix": "$"},
    {"name": "USD / INR", "ticker": "INR=X", "category": "Crypto & Forex", "prefix": "₹"}
]

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
# MARKET OVERVIEW FETCHER & MINI CHART BUILDER
# ---------------------------------------------------------
def _fetch_single_index(item: dict) -> dict:
    try:
        df = yf.download(item["ticker"], period="5d", interval="15m", progress=False, auto_adjust=True)
        if df is None or df.empty:
            df = yf.download(item["ticker"], period="1mo", interval="1d", progress=False, auto_adjust=True)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df.dropna(inplace=True)
        if len(df) < 2:
            return None

        curr = float(df["Close"].iloc[-1])
        dates = df.index.date
        unique_dates = pd.unique(dates)
        if len(unique_dates) >= 2:
            prev_day_df = df[dates == unique_dates[-2]]
            prev_close = float(prev_day_df["Close"].iloc[-1])
        else:
            prev_close = float(df["Close"].iloc[0])

        chg = curr - prev_close
        chg_pct = (chg / prev_close) * 100 if prev_close != 0 else 0.0

        return {
            "name": item["name"],
            "ticker": item["ticker"],
            "category": item.get("category", "Indian Indices"),
            "prefix": item.get("prefix", ""),
            "price": curr,
            "chg": chg,
            "chg_pct": chg_pct,
            "history": df["Close"].tail(60)
        }
    except Exception:
        return None

@st.cache_data(ttl=120, show_spinner=False)
def fetch_market_overview() -> dict:
    all_items = INDIAN_INDICES + GLOBAL_ASSETS
    results = {}
    with ThreadPoolExecutor(max_workers=11) as executor:
        futures = {executor.submit(_fetch_single_index, item): item["ticker"] for item in all_items}
        for future in as_completed(futures):
            res = future.result()
            if res:
                results[res["ticker"]] = res
    return results

def build_mini_sparkline(series: pd.Series, is_positive: bool, chart_height: int = 75) -> go.Figure:
    line_color = "#16a34a" if is_positive else "#dc2626"
    fill_color = "rgba(22, 163, 74, 0.12)" if is_positive else "rgba(220, 38, 38, 0.12)"
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=list(range(len(series))),
        y=series.values,
        mode="lines",
        line=dict(color=line_color, width=2),
        fill="tozeroy",
        fillcolor=fill_color,
        hovertemplate="%{y:,.2f}<extra></extra>"
    ))
    y_min, y_max = float(series.min()), float(series.max())
    pad = (y_max - y_min) * 0.08 if y_max != y_min else 1.0
    fig.update_layout(
        height=chart_height,
        margin=dict(l=0, r=0, t=4, b=0),
        xaxis=dict(visible=False, fixedrange=True),
        yaxis=dict(visible=False, range=[y_min - pad, y_max + pad], fixedrange=True),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        showlegend=False,
        hovermode="x"
    )
    return fig

def render_market_card(col, data: dict, key_suffix: str, is_fs: bool = False):
    with col:
        if not data:
            st.info("Data unavailable")
            return
        is_pos = data["chg"] >= 0
        cls = "mkt-pos" if is_pos else "mkt-neg"
        arrow = "▲" if is_pos else "▼"
        fmt_price = f"{data['prefix']}{data['price']:,.2f}"
        fmt_chg = f"{arrow} {data['chg']:+,.2f} ({data['chg_pct']:+.2f}%)"

        st.markdown(f"""
        <div class="mkt-card">
            <div class="mkt-header">
                <span>{data['name']}</span>
                <span class="{cls}">{fmt_chg}</span>
            </div>
            <div class="mkt-price">{fmt_price}</div>
        </div>
        """, unsafe_allow_html=True)
        fig = build_mini_sparkline(data["history"], is_pos, chart_height=130 if is_fs else 75)
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False, "responsive": True}, key=f"spark_{data['ticker']}_{key_suffix}_{is_fs}")
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
    if 55 < rsi_val < 75: rsi_act = "Buy"; ind_buy += 1
    elif 25 < rsi_val < 45: rsi_act = "Sell"; ind_sell += 1
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
    if 50 < stoch_val < 80: st_act = "Buy"; ind_buy += 1
    elif 20 < stoch_val < 50: st_act = "Sell"; ind_sell += 1
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
# MODULAR SECTION RENDERERS (WITH MAXIMIZE / MINIMIZE TOGGLE)
# ---------------------------------------------------------
def render_section_header(title: str, section_key: str):
    is_fs = (st.session_state.fullscreen_section == section_key)
    h_col, btn_col = st.columns([6, 1.4])
    with h_col:
        st.markdown(f'<div class="section-header-box">{title}</div>', unsafe_allow_html=True)
    with btn_col:
        btn_label = "🗗 Minimize" if is_fs else "⛶ Full Screen"
        st.button(
            btn_label,
            key=f"btn_fs_{section_key}",
            on_click=toggle_fullscreen,
            args=(section_key,),
            use_container_width=True
        )

def render_market_overview_section(is_fs: bool = False):
    render_section_header("Market Overview — Indian Indices & Global Markets", "market_overview")
    market_overview_data = fetch_market_overview()

    st.markdown("**Indian Benchmark Indices**")
    ind_cols = st.columns(4)
    for idx, item in enumerate(INDIAN_INDICES):
        render_market_card(ind_cols[idx], market_overview_data.get(item["ticker"]), f"in_{idx}", is_fs=is_fs)

    st.markdown("---")
    hdr_col1, hdr_col2 = st.columns([1.2, 2.8])
    with hdr_col1:
        st.markdown("**Global Markets, Commodities & Crypto**")
    with hdr_col2:
        asset_filter = st.radio(
            "Select Global Asset Class",
            ["All Global Assets", "US Indices", "Commodities", "Crypto & Forex"],
            horizontal=True,
            label_visibility="collapsed",
            key=f"asset_filter_{is_fs}"
        )

    filtered_global = [
        g for g in GLOBAL_ASSETS
        if asset_filter == "All Global Assets" or g["category"] == asset_filter
    ]

    for row_start in range(0, len(filtered_global), 4):
        row_items = filtered_global[row_start:row_start + 4]
        g_cols = st.columns(len(row_items))
        for idx, item in enumerate(row_items):
            render_market_card(g_cols[idx], market_overview_data.get(item["ticker"]), f"gl_{row_start}_{idx}", is_fs=is_fs)

def render_screener_section(df_filtered: pd.DataFrame, is_fs: bool = False):
    render_section_header(f"Scanner Results ({len(df_filtered)} Equities)", "screener_table")
    display_cols = ["Ticker", "Close", "Chg %", "RSI (14)", "15m", "1h", "1d", "1wk", "Master Signal", "Score"]
    if is_fs:
        display_cols = ["Ticker", "Close", "Chg %", "RSI (14)", "15m", "1h", "1d", "1wk", "Master Signal", "Score", "Stop Loss", "Target"]
    st.dataframe(
        style_dataframe(df_filtered[display_cols]),
        use_container_width=True,
        height=780 if is_fs else 650,
        hide_index=True
    )

def render_matrix_and_chart_section(df_filtered: pd.DataFrame, df_all: pd.DataFrame, data_map: dict, primary_tf: str, is_fs: bool = False):
    render_section_header("Multi-Timeframe Confluence Matrix & Technical Chart", "confluence_matrix")

    ticker_options = df_filtered["Ticker"].tolist() if not df_filtered.empty else df_all["Ticker"].tolist()
    selected_ticker = st.selectbox(
        "Select Equity for Deep Technical Analysis",
        ticker_options,
        index=0,
        key=f"ticker_select_{is_fs}"
    )
    stock_obj = data_map[selected_ticker]
    tf_dict = stock_obj["tf_data"]
    active_tf_data = tf_dict.get(primary_tf, tf_dict["1d"])

    st.markdown(f"### {selected_ticker} — ₹{stock_obj['Close']:.2f} ({stock_obj['Chg %']:+.2f}%)")

    # 1. MULTI-TIMEFRAME ALIGNMENT CARDS (MATRIX)
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
        plot_df = active_tf_data["df"].tail(120 if is_fs else 80)

        fig = make_subplots(
            rows=2, cols=1,
            shared_xaxes=True,
            vertical_spacing=0.03,
            row_heights=[0.70, 0.30]
        )

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

        fig.add_trace(go.Scatter(x=plot_df.index, y=plot_df["BB_Upper"], line=dict(color="rgba(59,130,246,0.3)", width=1), name="BB Upper"), row=1, col=1)
        fig.add_trace(go.Scatter(x=plot_df.index, y=plot_df["BB_Mid"], line=dict(color="#f59e0b", width=1.2), name="20 SMA"), row=1, col=1)
        fig.add_trace(go.Scatter(x=plot_df.index, y=plot_df["BB_Lower"], line=dict(color="rgba(59,130,246,0.3)", width=1), fill="tonexty", fillcolor="rgba(59,130,246,0.04)", name="BB Lower"), row=1, col=1)

        vol_colors = ["#16a34a" if row["Close"] >= row["Open"] else "#dc2626" for _, row in plot_df.iterrows()]
        fig.add_trace(go.Bar(
            x=plot_df.index,
            y=plot_df["Volume"],
            marker_color=vol_colors,
            name="Volume",
            opacity=0.6
        ), row=2, col=1)

        fig.update_layout(
            height=680 if is_fs else 520,
            margin=dict(l=10, r=10, t=10, b=10),
            xaxis_rangeslider_visible=False,
            template="plotly_white",
            showlegend=False,
            hovermode="x unified"
        )

        fig.update_xaxes(showgrid=True, gridcolor="#e2e8f0")
        fig.update_yaxes(showgrid=True, gridcolor="#e2e8f0")

        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": True, "responsive": True}, key=f"main_chart_{selected_ticker}_{primary_tf}_{is_fs}")

    with tab_details:
        c_ma, c_ind = st.columns(2)
        with c_ma:
            st.markdown("**Moving Averages Detail**")
            st.dataframe(active_tf_data["ma_details"], use_container_width=True, hide_index=True)
        with c_ind:
            st.markdown("**Oscillators & Trend Detail**")
            st.dataframe(active_tf_data["ind_details"], use_container_width=True, hide_index=True)

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
    st.markdown("---")
    st.markdown("**Quick View Layout**")
    if st.session_state.fullscreen_section is not None:
        st.button("🗗 Exit Full Screen Mode", on_click=toggle_fullscreen, args=(st.session_state.fullscreen_section,), use_container_width=True)
    if st.button("Refresh Live Market Data", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

# ---------------------------------------------------------
# TOP HEADER & BLINKING LIVE MARKET BADGE
# ---------------------------------------------------------
st.markdown("""
<div class="top-bar-container">
    <div class="app-main-title">ULTRA ACCURACY MARKET TERMINAL</div>
    <div class="live-badge"><span class="live-dot"></span>LIVE MARKET</div>
</div>
""", unsafe_allow_html=True)

# ---------------------------------------------------------
# EXECUTE NIFTY 50 SCAN & COMPUTE MARKET METRICS
# ---------------------------------------------------------
with st.spinner("Scanning Nifty 50 with Ultra Accuracy Engine..."):
    raw_data = scan_all_equities(NIFTY_50)

if not raw_data:
    st.error("Unable to fetch live market data.")
    st.stop()

df_all = pd.DataFrame([{k: v for k, v in item.items() if k != "tf_data"} for item in raw_data])
data_map = {item["Ticker"]: item for item in raw_data}

if view_mode == "Top 25 Buy Signals":
    df_filtered = df_all[df_all["Score"] > 0].sort_values(by="Score", ascending=False).head(25)
elif view_mode == "Top 25 Sell Signals":
    df_filtered = df_all[df_all["Score"] < 0].sort_values(by="Score", ascending=True).head(25)
else:
    df_filtered = df_all[df_all["Master Signal"].isin(signal_filter)].sort_values(by="Score", ascending=False)

# ---------------------------------------------------------
# ROUTING: FULL-SCREEN EXPANDED VIEW VS STANDARD DASHBOARD
# ---------------------------------------------------------
active_fs = st.session_state.fullscreen_section

if active_fs is not None:
    fs_labels = {
        "market_overview": "MARKET OVERVIEW",
        "screener_table": "SCANNER RESULTS TABLE",
        "confluence_matrix": "MULTI-TIMEFRAME CONFLUENCE MATRIX & CHART"
    }
    st.markdown(f"""
    <div class="fs-active-banner">
        <span>FULL SCREEN MODE ACTIVE: {fs_labels.get(active_fs, '')}</span>
        <span>Click 'Minimize' to restore full dashboard layout</span>
    </div>
    """, unsafe_allow_html=True)

    if active_fs == "market_overview":
        render_market_overview_section(is_fs=True)
    elif active_fs == "screener_table":
        render_screener_section(df_filtered, is_fs=True)
    elif active_fs == "confluence_matrix":
        render_matrix_and_chart_section(df_filtered, df_all, data_map, primary_tf, is_fs=True)

else:
    # 1. MARKET OVERVIEW SECTION
    with st.container(border=True):
        render_market_overview_section(is_fs=False)

    st.markdown("---")

    # 2. KPI SUMMARY METRICS
    strong_buy_cnt = len(df_all[df_all["Master Signal"] == "STRONG BUY"])
    buy_cnt = len(df_all[df_all["Master Signal"].isin(["STRONG BUY", "BUY"])])
    strong_sell_cnt = len(df_all[df_all["Master Signal"].isin(["STRONG SELL"])])
    sell_cnt = len(df_all[df_all["Master Signal"].isin(["STRONG SELL", "SELL"])])
    avg_rsi = round(df_all["RSI (14)"].mean(), 1)

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Scanned Equities", f"{len(df_all)} / 50")
    k2.metric("Buy Setups (Strong)", f"{buy_cnt} ({strong_buy_cnt})")
    k3.metric("Sell Setups (Strong)", f"{sell_cnt} ({strong_sell_cnt})")
    k4.metric("Avg Market RSI (14)", f"{avg_rsi}")

    st.markdown("---")

    # 3. MAIN WORKSPACE: LEFT SCREENER TABLE | RIGHT MATRIX & CHART PANEL
    left_col, right_col = st.columns([1.2, 1.4], gap="large")

    with left_col:
        with st.container(border=True):
            render_screener_section(df_filtered, is_fs=False)

    with right_col:
        with st.container(border=True):
            render_matrix_and_chart_section(df_filtered, df_all, data_map, primary_tf, is_fs=False)
