import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from concurrent.futures import ThreadPoolExecutor, as_completed

# ---------------------------------------------------------
# PAGE CONFIGURATION & TRADINGVIEW STYLE CSS
# ---------------------------------------------------------
st.set_page_config(
    page_title="Ultra Accuracy Technical Scanner",
    layout="wide",
    initial_sidebar_state="expanded"
)

if "fullscreen_section" not in st.session_state:
    st.session_state.fullscreen_section = None

# Initialize Chart Toggles
default_toggles = {
    "ind_bb": True, "ind_ema": False, "ind_vol": True,
    "ind_rsi": False, "ind_macd": False, "ind_trades": True,
    "ind_pivots": False
}
for k, v in default_toggles.items():
    if k not in st.session_state:
        st.session_state[k] = v

def toggle_fullscreen(section_key: str):
    st.session_state.fullscreen_section = None if st.session_state.fullscreen_section == section_key else section_key

def toggle_chart_indicator(ind_key: str):
    st.session_state[ind_key] = not st.session_state[ind_key]

st.markdown("""
<style>
    .block-container { padding-top: 1rem; padding-bottom: 2rem; }
    .tf-card { border-radius: 10px; padding: 15px 12px; text-align: center; font-weight: 800; border: 2px solid #e2e8f0; margin-bottom: 10px; font-size: 1.1rem; }
    .tf-title { font-size: 0.85rem; color: #334155; text-transform: uppercase; margin-bottom: 6px; font-weight: 700; }
    .sig-strong-buy { background-color: #16a34a; color: #ffffff; border: 2px solid #16a34a; }
    .sig-buy { background-color: #22c55e; color: #ffffff; border: 2px solid #15803d; }
    .sig-neutral { background-color: #64748b; color: #ffffff; border: 2px solid #475569; }
    .sig-sell { background-color: #ef4444; color: #ffffff; border: 2px solid #b91c1c; }
    .sig-strong-sell { background-color: #dc2626; color: #ffffff; border: 2px solid #991b1b; }
    .summary-banner { border-radius: 10px; padding: 16px; text-align: center; font-size: 1.3rem; font-weight: 900; margin: 10px 0 20px 0; text-transform: uppercase; }
    .fs-active-banner { background: linear-gradient(90deg, #0f172a 0%, #1e293b 100%); color: #f8fafc; padding: 10px 18px; border-radius: 8px; font-weight: 700; margin-bottom: 12px; display: flex; justify-content: space-between; border-left: 5px solid #22c55e; }
    .section-header-box { font-size: 1.15rem; font-weight: 800; color: #0f172a; }
    .mkt-card { background-color: #ffffff; border: 1px solid #e2e8f0; border-radius: 10px; padding: 12px 14px 4px 14px; margin-bottom: 6px; }
    .mkt-header { display: flex; justify-content: space-between; align-items: center; font-size: 0.82rem; font-weight: 700; color: #475569; }
    .mkt-price { font-size: 1.25rem; font-weight: 800; color: #0f172a; margin-top: 2px; }
    .mkt-pos { color: #16a34a; font-weight: 700; }
    .mkt-neg { color: #dc2626; font-weight: 700; }
    .top-bar-container { display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #e2e8f0; margin-bottom: 14px; }
    .app-main-title { font-size: 1.45rem; font-weight: 900; color: #0f172a; }
    .live-badge { display: inline-flex; align-items: center; background-color: #16a34a; color: white; padding: 6px 14px; border-radius: 20px; font-weight: 800; animation: pulse 1.5s infinite; }
    @keyframes pulse { 0% { opacity: 1; } 50% { opacity: 0.6; } 100% { opacity: 1; } }
    .tv-toolbar-header { font-size: 0.78rem; font-weight: 800; color: #334155; text-transform: uppercase; background-color: #f8fafc; padding: 6px 10px; border-radius: 6px; border: 1px solid #e2e8f0; margin-bottom: 8px; }
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

BANNER_LABELS = {
    "market_overview": "MARKET OVERVIEW",
    "screener_table": "SCANNER RESULTS TABLE",
    "confluence_matrix": "MULTI-TIMEFRAME CONFLUENCE MATRIX & CHART"
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
        prev_close = float(df[dates == unique_dates[-2]]["Close"].iloc[-1]) if len(unique_dates) >= 2 else float(df["Close"].iloc[0])
        chg = curr - prev_close
        chg_pct = (chg / prev_close) * 100 if prev_close != 0 else 0.0

        return {
            "name": item["name"], "ticker": item["ticker"], "category": item.get("category", "Indian Indices"),
            "prefix": item.get("prefix", ""), "price": curr, "chg": chg, "chg_pct": chg_pct, "history": df["Close"].tail(60)
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
        x=list(range(len(series))), y=series.values, mode="lines",
        line=dict(color=line_color, width=2), fill="tozeroy", fillcolor=fill_color,
        hovertemplate="%{y:,.2f}<extra></extra>"
    ))
    y_min, y_max = float(series.min()), float(series.max())
    pad = (y_max - y_min) * 0.08 if y_max != y_min else 1.0
    fig.update_layout(
        height=chart_height, margin=dict(l=0, r=0, t=4, b=0),
        xaxis=dict(visible=False, fixedrange=True), yaxis=dict(visible=False, range=[y_min - pad, y_max + pad], fixedrange=True),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", showlegend=False, hovermode="x"
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
            <div class="mkt-header"><span>{data['name']}</span><span class="{cls}">{fmt_chg}</span></div>
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
    close, high, low = df["Close"], df["High"], df["Low"]
    volume = df["Volume"] if "Volume" in df.columns else pd.Series(1000, index=df.index)
    curr_price = float(close.iloc[-1])

    ma_periods = [5, 10, 20, 50, 100, 200]
    ma_buy, ma_sell, ma_details = 0, 0, []
    for p in ma_periods:
        sma_val = float(close.rolling(p).mean().iloc[-1]) if len(close) >= p else float(close.mean())
        ema_val = float(close.ewm(span=p, adjust=False).mean().iloc[-1]) if len(close) >= p else float(close.mean())
        sma_sig, ema_sig = ("Buy" if curr_price > sma_val else "Sell"), ("Buy" if curr_price > ema_val else "Sell")
        ma_buy += (1 if sma_sig == "Buy" else 0) + (1 if ema_sig == "Buy" else 0)
        ma_sell += (1 if sma_sig == "Sell" else 0) + (1 if ema_sig == "Sell" else 0)
        ma_details.append({"Period": f"MA{p}", "SMA": round(sma_val, 2), "SMA_Action": sma_sig, "EMA": round(ema_val, 2), "EMA_Action": ema_sig})

    ind_buy, ind_sell, ind_neut, ind_details = 0, 0, 0, []
    rsi_series = compute_rsi(close, 14)
    rsi_val = float(rsi_series.iloc[-1])
    if 55 < rsi_val < 75:
        rsi_act = "Buy"; ind_buy += 1
    elif 25 < rsi_val < 45:
        rsi_act = "Sell"; ind_sell += 1
    elif rsi_val <= 25:
        rsi_act = "Buy"; ind_buy += 1
    elif rsi_val >= 75:
        rsi_act = "Sell"; ind_sell += 1
    else:
        rsi_act = "Neutral"; ind_neut += 1
    ind_details.append({"Indicator": "RSI (14)", "Value": round(rsi_val, 2), "Action": rsi_act})

    ema12, ema26 = close.ewm(span=12, adjust=False).mean(), close.ewm(span=26, adjust=False).mean()
    macd_line = ema12 - ema26
    signal_line = macd_line.ewm(span=9, adjust=False).mean()
    macd_hist = macd_line - signal_line
    macd_val, sig_val = float(macd_line.iloc[-1]), float(signal_line.iloc[-1])
    macd_act = "Buy" if macd_val > sig_val else "Sell"
    if macd_act == "Buy":
        ind_buy += 1
    else:
        ind_sell += 1
    ind_details.append({"Indicator": "MACD (12,26)", "Value": round(macd_val, 2), "Action": macd_act})

    low14, high14 = low.rolling(14).min(), high.rolling(14).max()
    stoch_k = 100 * (close - low14) / (high14 - low14).replace(0, np.nan)
    stoch_val = float(stoch_k.rolling(3).mean().iloc[-1])
    if 50 < stoch_val < 80:
        st_act = "Buy"; ind_buy += 1
    elif 20 < stoch_val < 50:
        st_act = "Sell"; ind_sell += 1
    else:
        st_act = "Neutral"; ind_neut += 1
    ind_details.append({"Indicator": "STOCH (9,6)", "Value": round(stoch_val, 2), "Action": st_act})

    tp = (high + low + close) / 3
    cci = (tp - tp.rolling(14).mean()) / (0.015 * tp.rolling(14).apply(lambda x: np.mean(np.abs(x - np.mean(x))), raw=True))
    cci_val = float(cci.iloc[-1])
    if cci_val > 50:
        cci_act = "Buy"; ind_buy += 1
    elif cci_val < -50:
        cci_act = "Sell"; ind_sell += 1
    else:
        cci_act = "Neutral"; ind_neut += 1
    ind_details.append({"Indicator": "CCI (14)", "Value": round(cci_val, 2), "Action": cci_act})

    willr = -100 * (high14 - close) / (high14 - low14).replace(0, np.nan)
    willr_val = float(willr.iloc[-1])
    if willr_val > -50:
        wr_act = "Buy"; ind_buy += 1
    elif willr_val < -50:
        wr_act = "Sell"; ind_sell += 1
    else:
        wr_act = "Neutral"; ind_neut += 1
    ind_details.append({"Indicator": "Williams %R", "Value": round(willr_val, 2), "Action": wr_act})

    roc_val = float(((close.iloc[-1] - close.iloc[-13]) / close.iloc[-13]) * 100)
    roc_act = "Buy" if roc_val > 0 else "Sell"
    if roc_act == "Buy":
        ind_buy += 1
    else:
        ind_sell += 1
    ind_details.append({"Indicator": "ROC (12)", "Value": round(roc_val, 2), "Action": roc_act})

    ema13 = float(close.ewm(span=13, adjust=False).mean().iloc[-1])
    bbp_val = float((high.iloc[-1] - ema13) + (low.iloc[-1] - ema13))
    bbp_act = "Buy" if bbp_val > 0 else "Sell"
    if bbp_act == "Buy":
        ind_buy += 1
    else:
        ind_sell += 1
    ind_details.append({"Indicator": "Bull/Bear Power (13)", "Value": round(bbp_val, 2), "Action": bbp_act})

    bb_mid, bb_std = close.rolling(20).mean(), close.rolling(20).std()
    bb_upper, bb_lower = bb_mid + 2 * bb_std, bb_mid - 2 * bb_std
    bb_act = "Buy" if curr_price > float(bb_mid.iloc[-1]) else "Sell"
    if bb_act == "Buy":
        ind_buy += 1
    else:
        ind_sell += 1
    ind_details.append({"Indicator": "Bollinger (20,2)", "Value": round(float(bb_mid.iloc[-1]), 2), "Action": bb_act})

    ema20, ema50, ema200 = close.ewm(span=20, adjust=False).mean(), close.ewm(span=50, adjust=False).mean(), close.ewm(span=200, adjust=False).mean()
    total_signals = ma_buy + ma_sell + ind_buy + ind_sell + ind_neut
    net_score = ((ma_buy + ind_buy) - (ma_sell + ind_sell)) / max(total_signals, 1) * 100

    signal = "STRONG BUY" if net_score >= 45 else ("BUY" if net_score >= 15 else ("STRONG SELL" if net_score <= -45 else ("SELL" if net_score <= -15 else "NEUTRAL")))
    prev_h, prev_l, prev_c = float(high.iloc[-2]), float(low.iloc[-2]), float(close.iloc[-2])
    pp, rng = (prev_h + prev_l + prev_c) / 3.0, prev_h - prev_l

    pivots = pd.DataFrame([
        {"Level": "R3", "Classic": round(prev_h + 2 * (pp - prev_l), 2), "Fibonacci": round(pp + 1.000 * rng, 2)},
        {"Level": "R2", "Classic": round(pp + rng, 2), "Fibonacci": round(pp + 0.618 * rng, 2)},
        {"Level": "R1", "Classic": round(2 * pp - prev_l, 2), "Fibonacci": round(pp + 0.382 * rng, 2)},
        {"Level": "Pivot Point", "Classic": round(pp, 2), "Fibonacci": round(pp, 2)},
        {"Level": "S1", "Classic": round(2 * pp - prev_h, 2), "Fibonacci": round(pp - 0.382 * rng, 2)},
        {"Level": "S2", "Classic": round(pp - rng, 2), "Fibonacci": round(pp - 0.618 * rng, 2)},
        {"Level": "S3", "Classic": round(prev_l - 2 * (prev_h - pp), 2), "Fibonacci": round(pp - 1.000 * rng, 2)},
    ])

    enriched_df = df.assign(
        BB_Mid=bb_mid, BB_Upper=bb_upper, BB_Lower=bb_lower,
        EMA_20=ema20, EMA_50=ema50, EMA_200=ema200,
        RSI=rsi_series, MACD=macd_line, MACD_Sig=signal_line,
        MACD_Hist=macd_hist, Volume=volume
    )
    return {
        "price": curr_price, "rsi": round(rsi_val, 2), "signal": signal, "score": round(net_score, 1),
        "ma_buy": ma_buy, "ma_sell": ma_sell, "ind_buy": ind_buy, "ind_sell": ind_sell,
        "ma_details": pd.DataFrame(ma_details), "ind_details": pd.DataFrame(ind_details),
        "pivots": pivots, "df": enriched_df
    }

@st.cache_data(ttl=180, show_spinner=False)
def analyze_single_stock(ticker: str) -> dict:
    tf_results = {}
    for tf_key, cfg in TIMEFRAMES.items():
        try:
            df = yf.download(ticker, period=cfg["period"], interval=cfg["interval"], progress=False, auto_adjust=True)
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            df.dropna(inplace=True)
            res = evaluate_timeframe(df)
            if res:
                tf_results[tf_key] = res
        except Exception:
            continue
    if "1d" not in tf_results:
        return None

    d1, df_1d = tf_results["1d"], tf_results["1d"]["df"]
    prev_close = float(df_1d["Close"].iloc[-2]) if len(df_1d) > 1 else d1["price"]
    chg_pct = ((d1["price"] - prev_close) / prev_close) * 100
    weighted_score, total_w, buy_tf, sell_tf = 0.0, 0.0, 0, 0
    for k, w in {"15m": 0.15, "1h": 0.25, "1d": 0.35, "1wk": 0.25}.items():
        if k in tf_results:
            weighted_score += tf_results[k]["score"] * w
            total_w += w
            if "BUY" in tf_results[k]["signal"]:
                buy_tf += 1
            elif "SELL" in tf_results[k]["signal"]:
                sell_tf += 1
    final_score = round(weighted_score / max(total_w, 0.01), 1)
    master_signal = "STRONG BUY" if final_score >= 40 and buy_tf >= 3 else ("BUY" if final_score >= 12 else ("STRONG SELL" if final_score <= -40 and sell_tf >= 3 else ("SELL" if final_score <= -12 else "NEUTRAL")))

    atr = float((df_1d["High"] - df_1d["Low"]).rolling(14).mean().iloc[-1])
    entry_price = round(d1["price"], 2)
    is_sell = "SELL" in master_signal
    trade_side = "SELL" if is_sell else ("BUY" if "BUY" in master_signal else "NEUTRAL (BUY BIAS)")
    stop_loss = round(entry_price + 1.5 * atr if is_sell else entry_price - 1.5 * atr, 2)
    t1 = round(entry_price - 1.5 * atr if is_sell else entry_price + 1.5 * atr, 2)
    t2 = round(entry_price - 3.0 * atr if is_sell else entry_price + 3.0 * atr, 2)
    t3 = round(entry_price - 4.5 * atr if is_sell else entry_price + 4.5 * atr, 2)

    return {
        "Ticker": ticker.replace(".NS", ""), "FullTicker": ticker, "Close": entry_price, "Chg %": round(chg_pct, 2),
        "RSI (14)": d1["rsi"], "15m": tf_results.get("15m", {}).get("signal", "N/A"),
        "1h": tf_results.get("1h", {}).get("signal", "N/A"), "1d": tf_results.get("1d", {}).get("signal", "N/A"),
        "1wk": tf_results.get("1wk", {}).get("signal", "N/A"), "Master Signal": master_signal,
        "Score": final_score, "Trade Side": trade_side, "Entry": entry_price,
        "Stop Loss": stop_loss, "Target 1": t1, "Target 2": t2, "Target 3": t3, "tf_data": tf_results
    }

@st.cache_data(ttl=180, show_spinner=False)
def scan_all_equities(tickers: list) -> list:
    results = []
    with ThreadPoolExecutor(max_workers=12) as executor:
        futures = {executor.submit(analyze_single_stock, t): t for t in tickers}
        for future in as_completed(futures):
            res = future.result()
            if res:
                results.append(res)
    return results

def get_signal_css(s: str) -> str:
    s = s.upper()
    return "sig-strong-buy" if s == "STRONG BUY" else ("sig-buy" if s == "BUY" else ("sig-strong-sell" if s == "STRONG SELL" else ("sig-sell" if s == "SELL" else "sig-neutral")))

def style_dataframe(df: pd.DataFrame):
    def color_cell(val):
        v = str(val).upper()
        return "background-color: #15803d; color: white; font-weight: bold;" if v == "STRONG BUY" else ("background-color: #22c55e; color: white; font-weight: bold;" if v == "BUY" else ("background-color: #b91c1c; color: white; font-weight: bold;" if v == "STRONG SELL" else ("background-color: #ef4444; color: white; font-weight: bold;" if v == "SELL" else ("background-color: #64748b; color: white;" if v == "NEUTRAL" else ""))))
    cols = [c for c in ["15m", "1h", "1d", "1wk", "Master Signal"] if c in df.columns]
    fmt = {"Close": "₹{:.2f}", "Chg %": "{:+.2f}%", "RSI (14)": "{:.1f}", "Score": "{:+.1f}"}
    if "Stop Loss" in df.columns:
        fmt["Stop Loss"] = "₹{:.2f}"
    if "Target 1" in df.columns:
        fmt["Target 1"] = "₹{:.2f}"
    return df.style.map(color_cell, subset=cols).format(fmt)

def render_section_header(title: str, sec_key: str):
    is_fs = (st.session_state.fullscreen_section == sec_key)
    h_col, btn_col = st.columns([6, 1.4])
    with h_col:
        st.markdown(f'<div class="section-header-box">{title}</div>', unsafe_allow_html=True)
    with btn_col:
        st.button("🗗 Minimize" if is_fs else "⛶ Full Screen", key=f"btn_fs_{sec_key}", on_click=toggle_fullscreen, args=(sec_key,), use_container_width=True)

def render_market_overview_section(is_fs: bool = False):
    render_section_header("Market Overview — Indian Indices & Global Markets", "market_overview")
    data = fetch_market_overview()
    st.markdown("**Indian Benchmark Indices**")
    cols = st.columns(4)
    for idx, item in enumerate(INDIAN_INDICES):
        render_market_card(cols[idx], data.get(item["ticker"]), f"in_{idx}", is_fs=is_fs)
    st.markdown("---")
    c1, c2 = st.columns([1.2, 2.8])
    with c1:
        st.markdown("**Global Markets, Commodities & Crypto**")
    with c2:
        asset_filter = st.radio("Select Global Asset Class", ["All Global Assets", "US Indices", "Commodities", "Crypto & Forex"], horizontal=True, label_visibility="collapsed", key=f"asset_filter_{is_fs}")
    filtered = [g for g in GLOBAL_ASSETS if asset_filter == "All Global Assets" or g["category"] == asset_filter]
    for start in range(0, len(filtered), 4):
        row = filtered[start:start+4]
        g_cols = st.columns(len(row))
        for idx, item in enumerate(row):
            render_market_card(g_cols[idx], data.get(item["ticker"]), f"gl_{start}_{idx}", is_fs=is_fs)

def render_screener_section(df_f: pd.DataFrame, is_fs: bool = False):
    render_section_header(f"Scanner Results ({len(df_f)} Equities)", "screener_table")
    cols = ["Ticker", "Close", "Chg %", "RSI (14)", "15m", "1h", "1d", "1wk", "Master Signal", "Score"] + (["Stop Loss", "Target 1"] if is_fs else [])
    st.dataframe(style_dataframe(df_f[cols]), use_container_width=True, height=780 if is_fs else 650, hide_index=True)

def render_matrix_and_chart_section(df_f: pd.DataFrame, df_all: pd.DataFrame, data_map: dict, primary_tf: str, is_fs: bool = False):
    render_section_header("Multi-Timeframe Confluence Matrix & Technical Chart", "confluence_matrix")
    options = df_f["Ticker"].tolist() if not df_f.empty else df_all["Ticker"].tolist()
    sel = st.selectbox("Select Equity for Deep Technical Analysis", options, index=0, key=f"ticker_select_{is_fs}")
    obj = data_map[sel]
    tf_d = obj["tf_data"]
    act_d = tf_d.get(primary_tf, tf_d["1d"])
    st.markdown(f"### {sel} — ₹{obj['Close']:.2f} ({obj['Chg %']:+.2f}%)")

    tf_cols = st.columns(4)
    for idx, (tk, tm) in enumerate(TIMEFRAMES.items()):
        s_txt = tf_d[tk]["signal"] if tk in tf_d else "N/A"
        with tf_cols[idx]:
            st.markdown(f'<div class="tf-card {get_signal_css(s_txt)}"><div class="tf-title">{tm["label"]} ({tk})</div><div>{s_txt}</div></div>', unsafe_allow_html=True)

    msig = obj["Master Signal"]
    st.markdown(f'<div class="summary-banner {get_signal_css(msig)}">MASTER SIGNAL: {msig} (Confidence Score: {obj["Score"]:+.1f})</div>', unsafe_allow_html=True)

    t1, t2, t3, t4, t5 = st.columns(5)
    t1.metric(f"{obj['Trade Side']} Entry", f"₹{obj['Entry']:.2f}")
    t2.metric("Stop Loss", f"₹{obj['Stop Loss']:.2f}")
    t3.metric("Target 1", f"₹{obj['Target 1']:.2f}")
    t4.metric("Target 2", f"₹{obj['Target 2']:.2f}")
    t5.metric("Target 3", f"₹{obj['Target 3']:.2f}")

    tab_chart, tab_sum, tab_det = st.tabs(["Interactive Chart", "Technical Summary & Pivots", "Indicator Breakdown"])
    with tab_chart:
        # ---------------------------------------------------------
        # TRADINGVIEW STYLE TOP OVERLAY & INDICATOR TOOLBAR
        # ---------------------------------------------------------
        st.markdown('<div class="tv-toolbar-header">Chart Overlays & Indicators (Click to Toggle ON / OFF)</div>', unsafe_allow_html=True)
        tb_cols = st.columns(7)
        t_items = [
            ("ind_bb", "BB"),
            ("ind_ema", "EMA"),
            ("ind_vol", "Volume"),
            ("ind_rsi", "RSI"),
            ("ind_macd", "MACD"),
            ("ind_trades", "Levels"),
            ("ind_pivots", "Pivots")
        ]
        for idx, (sk, lbl) in enumerate(t_items):
            act = st.session_state[sk]
            with tb_cols[idx]:
                st.button(
                    f"{'✓ ' if act else '+ '}{lbl}",
                    key=f"tb_{sk}_{is_fs}",
                    on_click=toggle_chart_indicator,
                    args=(sk,),
                    type="primary" if act else "secondary",
                    use_container_width=True
                )

        pdf = act_d["df"].tail(120 if is_fs else 80)
        s_bb = st.session_state.ind_bb
        s_ema = st.session_state.ind_ema
        s_vol = st.session_state.ind_vol
        s_rsi = st.session_state.ind_rsi
        s_macd = st.session_state.ind_macd
        s_trd = st.session_state.ind_trades
        s_piv = st.session_state.ind_pivots

        active_panels = [p for p, flag in [("vol", s_vol), ("rsi", s_rsi), ("macd", s_macd)] if flag]
        tot_rows = 1 + len(active_panels)
        if tot_rows == 1:
            rh = [1.0]
        elif tot_rows == 2:
            rh = [0.75, 0.25]
        elif tot_rows == 3:
            rh = [0.62, 0.19, 0.19]
        else:
            rh = [0.55, 0.15, 0.15, 0.15]

        fig = make_subplots(rows=tot_rows, cols=1, shared_xaxes=True, vertical_spacing=0.03, row_heights=rh)
        fig.add_trace(
            go.Candlestick(
                x=pdf.index, open=pdf["Open"], high=pdf["High"], low=pdf["Low"], close=pdf["Close"],
                name="Price", increasing_line_color="#16a34a", decreasing_line_color="#dc2626"
            ),
            row=1, col=1
        )

        if s_bb:
            fig.add_trace(go.Scatter(x=pdf.index, y=pdf["BB_Upper"], line=dict(color="rgba(59,130,246,0.55)", width=1), name="BB Upper"), row=1, col=1)
            fig.add_trace(go.Scatter(x=pdf.index, y=pdf["BB_Mid"], line=dict(color="#f59e0b", width=1.2), name="BB Mid"), row=1, col=1)
            fig.add_trace(go.Scatter(x=pdf.index, y=pdf["BB_Lower"], line=dict(color="rgba(59,130,246,0.55)", width=1), fill="tonexty", fillcolor="rgba(59,130,246,0.06)", name="BB Lower"), row=1, col=1)

        if s_ema:
            fig.add_trace(go.Scatter(x=pdf.index, y=pdf["EMA_20"], line=dict(color="#06b6d4", width=1.5), name="EMA 20"), row=1, col=1)
            fig.add_trace(go.Scatter(x=pdf.index, y=pdf["EMA_50"], line=dict(color="#8b5cf6", width=1.6), name="EMA 50"), row=1, col=1)
            fig.add_trace(go.Scatter(x=pdf.index, y=pdf["EMA_200"], line=dict(color="#ec4899", width=1.9), name="EMA 200"), row=1, col=1)

        if s_trd:
            is_sl = (obj["Trade Side"] == "SELL")
            tlines = [
                (obj["Entry"], "#dc2626" if is_sl else "#2563eb", "solid", f"{'SELL' if is_sl else 'BUY'} ENTRY: ₹{obj['Entry']:.2f}"),
                (obj["Stop Loss"], "#ef4444", "dash", f"SL: ₹{obj['Stop Loss']:.2f}"),
                (obj["Target 1"], "#22c55e", "dot", f"T1: ₹{obj['Target 1']:.2f}"),
                (obj["Target 2"], "#16a34a", "dash", f"T2: ₹{obj['Target 2']:.2f}"),
                (obj["Target 3"], "#15803d", "dashdot", f"T3: ₹{obj['Target 3']:.2f}")
            ]
            for p, c, d, txt in tlines:
                fig.add_hline(
                    y=p, line_width=1.5, line_dash=d, line_color=c,
                    annotation_text=txt, annotation_position="top left",
                    annotation_font=dict(size=10, color=c, family="Arial Black"),
                    annotation_bgcolor="rgba(255,255,255,0.8)",
                    row=1, col=1
                )

        if s_piv:
            for _, r in act_d["pivots"].iterrows():
                if r["Level"] in ["R2", "R1", "S1", "S2"]:
                    fig.add_hline(
                        y=r["Classic"], line_width=1.1, line_dash="dot", line_color="#f97316",
                        annotation_text=f"{r['Level']}: ₹{r['Classic']}", annotation_position="bottom left",
                        annotation_font=dict(size=9, color="#f97316"),
                        annotation_bgcolor="rgba(255,255,255,0.75)",
                        row=1, col=1
                    )

        fig.update_yaxes(title_text="Price (₹)", side="right", title_font=dict(size=11), row=1, col=1)

        cur = 2
        for p in active_panels:
            if p == "vol":
                fig.add_trace(
                    go.Bar(
                        x=pdf.index, y=pdf["Volume"],
                        marker_color=["#16a34a" if r["Close"] >= r["Open"] else "#dc2626" for _, r in pdf.iterrows()],
                        opacity=0.65, name="Volume"
                    ),
                    row=cur, col=1
                )
                fig.update_yaxes(title_text="Vol", side="right", title_font=dict(size=10), row=cur, col=1)
            elif p == "rsi":
                fig.add_trace(go.Scatter(x=pdf.index, y=pdf["RSI"], line=dict(color="#7c3aed", width=1.6), name="RSI"), row=cur, col=1)
                fig.add_hline(y=70, line_dash="dash", line_width=1, line_color="#dc2626", row=cur, col=1)
                fig.add_hline(y=30, line_dash="dash", line_width=1, line_color="#16a34a", row=cur, col=1)
                fig.update_yaxes(title_text="RSI", range=[0, 100], side="right", title_font=dict(size=10), row=cur, col=1)
            elif p == "macd":
                fig.add_trace(
                    go.Bar(
                        x=pdf.index, y=pdf["MACD_Hist"],
                        marker_color=["#16a34a" if v >= 0 else "#dc2626" for v in pdf["MACD_Hist"]],
                        opacity=0.6, name="Hist"
                    ),
                    row=cur, col=1
                )
                fig.add_trace(go.Scatter(x=pdf.index, y=pdf["MACD"], line=dict(color="#2563eb", width=1.4), name="MACD"), row=cur, col=1)
                fig.add_trace(go.Scatter(x=pdf.index, y=pdf["MACD_Sig"], line=dict(color="#f97316", width=1.4), name="Sig"), row=cur, col=1)
                fig.update_yaxes(title_text="MACD", side="right", title_font=dict(size=10), row=cur, col=1)
            cur += 1

        fig.update_layout(
            height=(680 if is_fs else 540) + max(0, (tot_rows - 2) * 90),
            margin=dict(l=10, r=55, t=15, b=10),
            xaxis_rangeslider_visible=False,
            template="plotly_white",
            showlegend=False,
            hovermode="x unified"
        )
        fig.update_xaxes(showgrid=True, gridcolor="#e2e8f0")
        fig.update_yaxes(showgrid=True, gridcolor="#e2e8f0", side="right")
        st.plotly_chart(
            fig,
            use_container_width=True,
            config={"displayModeBar": True, "responsive": True},
            key=f"mc_{sel}_{primary_tf}_{is_fs}_{s_bb}_{s_ema}_{s_vol}_{s_rsi}_{s_macd}_{s_trd}_{s_piv}"
        )

    with tab_sum:
        st.markdown(f"**Technical Summary ({TIMEFRAMES[primary_tf]['label']})**")
        st.dataframe(
            pd.DataFrame([
                {
                    "Category": "Moving Averages (12)",
                    "Summary": "Strong Buy" if act_d["ma_buy"] >= 9 else ("Buy" if act_d["ma_buy"] > act_d["ma_sell"] else ("Strong Sell" if act_d["ma_sell"] >= 9 else "Sell")),
                    "Buy": act_d["ma_buy"], "Sell": act_d["ma_sell"]
                },
                {
                    "Category": "Technical Indicators (8)",
                    "Summary": "Strong Buy" if act_d["ind_buy"] >= 6 else ("Buy" if act_d["ind_buy"] > act_d["ind_sell"] else ("Strong Sell" if act_d["ind_sell"] >= 6 else "Sell")),
                    "Buy": act_d["ind_buy"], "Sell": act_d["ind_sell"]
                }
            ]),
            use_container_width=True, hide_index=True
        )
        st.markdown(f"**Pivot Points ({TIMEFRAMES[primary_tf]['label']})**")
        st.dataframe(act_d["pivots"], use_container_width=True, hide_index=True)

    with tab_det:
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("**Moving Averages Detail**")
            st.dataframe(act_d["ma_details"], use_container_width=True, hide_index=True)
        with c2:
            st.markdown("**Oscillators & Trend Detail**")
            st.dataframe(act_d["ind_details"], use_container_width=True, hide_index=True)

# ---------------------------------------------------------
# SIDEBAR & MAIN APPLICATION LAYOUT
# ---------------------------------------------------------
with st.sidebar:
    st.header("Scanner Parameters")
    prim_tf = st.selectbox("Chart & Detail Timeframe", ["1d", "1h", "15m", "1wk"], index=0)
    v_mode = st.radio("Screener Ranking Mode", ["All Scanned Equities", "Top 25 Buy Signals", "Top 25 Sell Signals"], index=0)
    s_filt = st.multiselect("Filter Master Signals", ["STRONG BUY", "BUY", "NEUTRAL", "SELL", "STRONG SELL"], default=["STRONG BUY", "BUY", "NEUTRAL", "SELL", "STRONG SELL"])
    st.markdown("---")
    st.markdown("**Quick View Layout**")
    if st.session_state.fullscreen_section is not None:
        st.button("🗗 Exit Full Screen Mode", on_click=toggle_fullscreen, args=(st.session_state.fullscreen_section,), use_container_width=True)
    if st.button("Refresh Live Market Data", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

st.markdown('<div class="top-bar-container"><div class="app-main-title">ULTRA ACCURACY MARKET TERMINAL</div><div class="live-badge"><span style="height:10px;width:10px;background:#fff;border-radius:50%;display:inline-block;margin-right:8px;box-shadow:0 0 8px #fff;"></span>LIVE MARKET</div></div>', unsafe_allow_html=True)

with st.spinner("Scanning Nifty 50 with Ultra Accuracy Engine..."):
    r_data = scan_all_equities(NIFTY_50)

if not r_data:
    st.error("Unable to fetch live market data.")
    st.stop()

df_all = pd.DataFrame([{k: v for k, v in i.items() if k != "tf_data"} for i in r_data])
d_map = {i["Ticker"]: i for i in r_data}

if v_mode == "Top 25 Buy Signals":
    df_f = df_all[df_all["Score"] > 0].sort_values(by="Score", ascending=False).head(25)
elif v_mode == "Top 25 Sell Signals":
    df_f = df_all[df_all["Score"] < 0].sort_values(by="Score", ascending=True).head(25)
else:
    df_f = df_all[df_all["Master Signal"].isin(s_filt)].sort_values(by="Score", ascending=False)

af_sec = st.session_state.fullscreen_section
if af_sec is not None:
    banner_label = BANNER_LABELS.get(af_sec, "")
    st.markdown(f'<div class="fs-active-banner"><span>FULL SCREEN MODE ACTIVE: {banner_label}</span><span>Click \'Minimize\' to restore full dashboard layout</span></div>', unsafe_allow_html=True)
    if af_sec == "market_overview":
        render_market_overview_section(is_fs=True)
    elif af_sec == "screener_table":
        render_screener_section(df_f, is_fs=True)
    elif af_sec == "confluence_matrix":
        render_matrix_and_chart_section(df_f, df_all, d_map, prim_tf, is_fs=True)
else:
    with st.container(border=True):
        render_market_overview_section(is_fs=False)
    st.markdown("---")
    sb_cnt = len(df_all[df_all["Master Signal"] == "STRONG BUY"])
    b_cnt = len(df_all[df_all["Master Signal"].isin(["STRONG BUY", "BUY"])])
    ss_cnt = len(df_all[df_all["Master Signal"] == "STRONG SELL"])
    s_cnt = len(df_all[df_all["Master Signal"].isin(["STRONG SELL", "SELL"])])
    arsi = round(df_all["RSI (14)"].mean(), 1)

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Scanned Equities", f"{len(df_all)} / 50")
    k2.metric("Buy Setups (Strong)", f"{b_cnt} ({sb_cnt})")
    k3.metric("Sell Setups (Strong)", f"{s_cnt} ({ss_cnt})")
    k4.metric("Avg Market RSI (14)", f"{arsi}")
    st.markdown("---")

    lc, rc = st.columns([1.2, 1.4], gap="large")
    with lc:
        with st.container(border=True):
            render_screener_section(df_f, is_fs=False)
    with rc:
        with st.container(border=True):
            render_matrix_and_chart_section(df_f, df_all, d_map, prim_tf, is_fs=False)
