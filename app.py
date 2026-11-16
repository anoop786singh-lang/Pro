import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

st.set_page_config(
    page_title="Market Master Pro — Institutional Terminal",
    layout="wide",
    initial_sidebar_state="expanded",
)

# --- TRADINGVIEW DARK UI & RESPONSIVE STYLING ---
st.markdown("""
<style>
    .stApp { background-color: #131722; color: #d1d4dc; }
    section[data-testid="stSidebar"] {
        background-color: #1e222d;
        border-right: 1px solid #2a2e39;
        min-width: 315px !important;
        max-width: 345px !important;
    }
    .block-container { padding-top: 0.75rem; padding-bottom: 1rem; max-width: 100%; }
    .tv-topbar {
        display: flex; align-items: center; justify-content: space-between;
        background-color: #1e222d; padding: 10px 16px; border-radius: 6px;
        border: 1px solid #2a2e39; margin-bottom: 10px;
    }
    .tv-sym-title { font-size: 1.35rem; font-weight: 700; color: #ffffff; }
    .tv-price { font-size: 1.35rem; font-weight: 700; margin-left: 12px; }
    .regime-bar {
        display: flex; align-items: center; justify-content: space-between;
        background-color: #1a1e29; padding: 8px 14px; border-radius: 6px;
        border: 1px solid #2a2e39; margin-bottom: 10px; font-size: 0.82rem;
    }
    .mtf-card {
        background-color: #1e222d; border: 1px solid #2a2e39; border-radius: 6px;
        padding: 8px 4px; text-align: center; margin-bottom: 6px;
    }
    .mtf-tf { font-size: 0.72rem; color: #787b86; font-weight: 700; text-transform: uppercase; }
    .mtf-sig {
        font-size: 0.76rem; font-weight: 700; margin-top: 4px; padding: 3px 4px;
        border-radius: 4px; display: inline-block; width: 92%;
    }
    .mtf-meta { font-size: 0.66rem; color: #b2b5be; margin-top: 4px; line-height: 1.25; }
    .sig-strong-buy { background-color: #089981; color: #ffffff; }
    .sig-buy { background-color: rgba(8, 153, 129, 0.25); color: #089981; border: 1px solid #089981; }
    .sig-neutral { background-color: rgba(120, 123, 134, 0.25); color: #d1d4dc; border: 1px solid #787b86; }
    .sig-sell { background-color: rgba(242, 54, 69, 0.25); color: #f23645; border: 1px solid #f23645; }
    .sig-strong-sell { background-color: #f23645; color: #ffffff; }
    div[data-testid="stSidebar"] button {
        text-align: left !important;
        justify-content: flex-start !important;
        padding: 4px 8px !important;
        font-size: 0.80rem !important;
        background-color: transparent !important;
        border: 1px solid transparent !important;
        color: #d1d4dc !important;
    }
    div[data-testid="stSidebar"] button:hover {
        background-color: #2a2e39 !important;
        border-color: #363a45 !important;
    }
</style>
""", unsafe_allow_html=True)

# --- WATCHLIST UNIVERSE ---
WATCHLIST_ITEMS = [
    {"symbol": "^NSEI", "label": "NIFTY", "category": "Indices"},
    {"symbol": "^NSEBANK", "label": "BANKNIFTY", "category": "Indices"},
    {"symbol": "^BSESN", "label": "SENSEX", "category": "Indices"},
    {"symbol": "^CNXIT", "label": "NIFTYIT", "category": "Indices"},
    {"symbol": "^INDIAVIX", "label": "INDIAVIX", "category": "Indices"},
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
    {"symbol": "ADANIENT.NS", "label": "ADANIENT", "category": "Stocks"},
    {"symbol": "DRREDDY.NS", "label": "DRREDDY", "category": "Stocks"},
    {"symbol": "TRENT.NS", "label": "TRENT", "category": "Stocks"},
    {"symbol": "BEL.NS", "label": "BEL", "category": "Stocks"},
]

ALL_TIMEFRAMES = ["15m", "30m", "45m", "1h", "2h", "4h", "1d", "1wk", "1mo"]
CHART_TIMEFRAMES = ["15m", "30m", "1h", "2h", "4h", "1d", "1wk", "1mo"]

if "active_symbol" not in st.session_state:
    st.session_state.active_symbol = "^NSEI"
if "active_label" not in st.session_state:
    st.session_state.active_label = "NIFTY"

# --- DATA FETCHING & RESAMPLING ---
@st.cache_data(ttl=180)
def get_ohlcv(symbol: str, tf: str) -> pd.DataFrame:
    try:
        if tf in ["15m", "30m"]:
            df = yf.download(symbol, period="60d", interval=tf, progress=False, auto_adjust=False)
        elif tf == "45m":
            raw = yf.download(symbol, period="60d", interval="15m", progress=False, auto_adjust=False)
            if not raw.empty:
                df = raw.resample("45min").agg({"Open": "first", "High": "max", "Low": "min", "Close": "last", "Volume": "sum"}).dropna()
            else: return pd.DataFrame()
        elif tf in ["1h", "2h", "4h"]:
            df = yf.download(symbol, period="730d", interval=tf, progress=False, auto_adjust=False)
        elif tf == "1d":
            df = yf.download(symbol, period="2y", interval="1d", progress=False, auto_adjust=False)
        elif tf == "1wk":
            df = yf.download(symbol, period="5y", interval="1wk", progress=False, auto_adjust=False)
        else:
            df = yf.download(symbol, period="10y", interval="1mo", progress=False, auto_adjust=False)

        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        
        required_cols = ["Open", "High", "Low", "Close", "Volume"]
        if not all(col in df.columns for col in required_cols):
            return pd.DataFrame()

        return df.dropna().copy()
    except Exception as e:
        return pd.DataFrame()

# --- INDICATORS & DYNAMIC LEVELS ---
def compute_indicators(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    delta = df["Close"].diff()
    gain = delta.clip(lower=0).ewm(alpha=1/14, min_periods=14, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1/14, min_periods=14, adjust=False).mean()
    rs = gain / loss.replace(0, np.nan)
    df["RSI"] = 100 - (100 / (1 + rs))
    df["RSI_MA"] = df["RSI"].ewm(span=9, adjust=False).mean()

    df["EMA9"] = df["Close"].ewm(span=9, adjust=False).mean()
    df["EMA20"] = df["Close"].ewm(span=20, adjust=False).mean()
    df["EMA50"] = df["Close"].ewm(span=50, adjust=False).mean()
    df["SMA200"] = df["Close"].rolling(200, min_periods=50).mean()

    ema12 = df["Close"].ewm(span=12, adjust=False).mean()
    ema26 = df["Close"].ewm(span=26, adjust=False).mean()
    df["MACD"] = ema12 - ema26
    df["MACD_Signal"] = df["MACD"].ewm(span=9, adjust=False).mean()
    df["MACD_Hist"] = df["MACD"] - df["MACD_Signal"]

    sma20 = df["Close"].rolling(20).mean()
    std20 = df["Close"].rolling(20).std()
    df["BB_Upper"] = sma20 + 2 * std20
    df["BB_Lower"] = sma20 - 2 * std20
    df["BB_Mid"] = sma20

    tp = (df["High"] + df["Low"] + df["Close"]) / 3
    vol = df["Volume"].replace(0, np.nan).fillna(1.0)
    df["VWAP"] = (tp * vol).rolling(20).sum() / vol.rolling(20).sum()

    tr = np.maximum(df["High"] - df["Low"], np.maximum(abs(df["High"] - df["Close"].shift(1)), abs(df["Low"] - df["Close"].shift(1))))
    df["ATR"] = tr.rolling(14).mean()
    return df

def calculate_dynamic_trade_levels(df: pd.DataFrame, bias_score: float) -> dict:
    if df.empty or "ATR" not in df.columns or np.isnan(df["ATR"].iloc[-1]):
        c = float(df["Close"].iloc[-1]) if not df.empty else 100.0
        return {"entry": c, "sl": c*0.98, "t1": c*1.015, "t2": c*1.03, "t3": c*1.05}

    last = df.iloc[-1]
    c = float(last["Close"])
    h = float(last["High"])
    l = float(last["Low"])
    atr = float(last["ATR"])
    
    recent_high = float(df["High"].tail(20).max())
    recent_low = float(df["Low"].tail(20).min())

    if bias_score >= 0:
        entry = c
        sl = min(l - 0.5 * atr, recent_low)
        risk = c - sl
        t1 = c + risk * 1.0
        t2 = c + risk * 2.0
        t3 = c + risk * 3.0
    else:
        entry = c
        sl = max(h + 0.5 * atr, recent_high)
        risk = sl - c
        t1 = c - risk * 1.0
        t2 = c - risk * 2.0
        t3 = c - risk * 3.0

    return {
        "entry": round(entry, 2), "sl": round(sl, 2),
        "t1": round(t1, 2), "t2": round(t2, 2), "t3": round(t3, 2)
    }

def detect_support_resistance(df: pd.DataFrame, lookback: int = 80, order: int = 4) -> dict:
    close = float(df["Close"].iloc[-1]) if not df.empty else 100.0
    def_supp = round(close * 0.98, 2)
    def_res = round(close * 1.02, 2)

    if df.empty or len(df) < order * 2 + 5:
        return {"support": def_supp, "resistance": def_res, "s_strength": 1, "r_strength": 1}

    sub = df.tail(lookback).copy()
    atr = float(sub["ATR"].iloc[-1]) if ("ATR" in sub.columns and not np.isnan(sub["ATR"].iloc[-1])) else close * 0.015
    tol = max(atr * 0.6, close * 0.004)

    highs, lows = sub["High"].values, sub["Low"].values
    pivot_highs, pivot_lows = [], []

    for i in range(order, len(sub) - order):
        if highs[i] == np.max(highs[i - order : i + order + 1]): pivot_highs.append(float(highs[i]))
        if lows[i] == np.min(lows[i - order : i + order + 1]): pivot_lows.append(float(lows[i]))

    def cluster_levels(levels):
        if not levels: return []
        levels = sorted(levels)
        clusters = [[levels[0]]]
        for lv in levels[1:]:
            if abs(lv - np.mean(clusters[-1])) <= tol: clusters[-1].append(lv)
            else: clusters.append([lv])
        return [(float(np.mean(c)), len(c)) for c in clusters]

    res_clusters = [c for c in cluster_levels(pivot_highs) if c[0] > close * 0.998]
    sup_clusters = [c for c in cluster_levels(pivot_lows) if c[0] < close * 1.002]

    nearest_r = def_res
    r_str = 1
    if res_clusters:
        best_r = min(res_clusters, key=lambda x: abs(x[0] - close))
        nearest_r = round(float(best_r[0]), 2)
        r_str = int(best_r[1])

    nearest_s = def_supp
    s_str = 1
    if sup_clusters:
        best_s = min(sup_clusters, key=lambda x: abs(close - x[0]))
        nearest_s = round(float(best_s[0]), 2)
        s_str = int(best_s[1])

    return {"support": nearest_s, "resistance": nearest_r, "s_strength": s_str, "r_strength": r_str}

def detect_candlestick_patterns(df: pd.DataFrame) -> dict:
    if df.empty or len(df) < 4: return {"name": "None", "bias": 0, "short": "—"}
    c0, c1, c2 = df.iloc[-1], df.iloc[-2], df.iloc[-3]

    def bar_stats(row):
        o, h, l, c = float(row["Open"]), float(row["High"]), float(row["Low"]), float(row["Close"])
        body = abs(c - o)
        rng = max(h - l, 1e-6)
        return o, h, l, c, body, rng, h - max(o, c), min(o, c) - l, c > o

    o0, h0, l0, cl0, b0, r0, uw0, lw0, bull0 = bar_stats(c0)
    o1, h1, l1, cl1, b1, r1, uw1, lw1, bull1 = bar_stats(c1)
    o2, h2, l2, cl2, b2, r2, uw2, lw2, bull2 = bar_stats(c2)

    if (not bull2) and b2 > r2*0.5 and b1 < r1*0.35 and bull0 and b0 > r0*0.5 and cl0 > (o2+cl2)/2: return {"name": "Morning Star", "bias": 2, "short": "MornStar"}
    if bull2 and b2 > r2*0.5 and b1 < r1*0.35 and (not bull0) and b0 > r0*0.5 and cl0 < (o2+cl2)/2: return {"name": "Evening Star", "bias": -2, "short": "EveStar"}
    if (not bull1) and bull0 and cl0 >= o1 and o0 <= cl1 and b0 > b1*1.05: return {"name": "Bullish Engulfing", "bias": 2, "short": "BullEng"}
    if bull1 and (not bull0) and cl0 <= o1 and o0 >= cl1 and b0 > b1*1.05: return {"name": "Bearish Engulfing", "bias": -2, "short": "BearEng"}
    if lw0 >= b0*2.0 and uw0 <= b0*0.4 and b0 > r0*0.12: return {"name": "Hammer", "bias": 1, "short": "Hammer"}
    if uw0 >= b0*2.0 and lw0 <= b0*0.4 and b0 > r0*0.12: return {"name": "Shooting Star", "bias": -1, "short": "ShootStar"}
    if b0 <= r0*0.10: return {"name": "Doji Indecision", "bias": 0, "short": "Doji"}

    return {"name": "None", "bias": 0, "short": "—"}

def evaluate_timeframe_signal(df: pd.DataFrame, macro_bias: int = 0) -> dict:
    if df.empty or len(df) < 26:
        close = float(df["Close"].iloc[-1]) if not df.empty else 100.0
        return {
            "signal": "NEUTRAL", "css": "sig-neutral", "badge_col": "#787b86", "score": 0.0, "rsi": 50.0, "pattern": "—", "sr_tag": "Mid",
            "sr": {"support": round(close * 0.98, 2), "resistance": round(close * 1.02, 2)},
            "levels": {"entry": close, "sl": close*0.98, "t1": close*1.015, "t2": close*1.03, "t3": close*1.05}
        }

    df = compute_indicators(df)
    sr = detect_support_resistance(df)
    candle = detect_candlestick_patterns(df)

    last = df.iloc[-1]
    close, rsi = float(last["Close"]), float(last["RSI"]) if not np.isnan(last["RSI"]) else 50.0
    rsi_ma = float(last["RSI_MA"]) if not np.isnan(last["RSI_MA"]) else rsi
    ema9, ema20, ema50 = float(last["EMA9"]), float(last["EMA20"]), float(last["EMA50"])
    sma200 = float(last["SMA200"]) if not np.isnan(last["SMA200"]) else ema50
    macd, macd_sig = float(last["MACD"]), float(last["MACD_Signal"])
    atr = float(last["ATR"]) if not np.isnan(last["ATR"]) else close * 0.015

    raw_score = 0.0
    raw_score += 1.0 if close > ema20 else -1.0
    raw_score += 1.0 if ema20 > ema50 else -1.0
    raw_score += 0.75 if ema9 > ema20 else -0.75
    raw_score += 0.75 if close > sma200 else -0.75

    if rsi >= 62 and rsi > rsi_ma: raw_score += 2.0
    elif rsi >= 53: raw_score += 1.0
    elif rsi <= 38 and rsi < rsi_ma: raw_score -= 2.0
    elif rsi <= 47: raw_score -= 1.0
    raw_score += 1.0 if macd > macd_sig else -1.0

    dist_to_sup, dist_to_res = close - sr["support"], sr["resistance"] - close
    sr_tag = "Mid"
    if 0 <= dist_to_sup <= 0.8 * atr:
        raw_score += 1.5 if candle["bias"] >= 0 else -0.5
        sr_tag = "Near S1"
    elif dist_to_sup < 0:
        raw_score -= 1.5
        sr_tag = "Broke S1"
    elif 0 <= dist_to_res <= 0.8 * atr:
        raw_score += 1.5 if (candle["bias"] > 0 and rsi > 60) else -1.0
        sr_tag = "At R1"
    elif dist_to_res < 0:
        raw_score += 2.0
        sr_tag = "Broke R1"

    raw_score += float(candle["bias"])
    if macro_bias != 0:
        if (raw_score > 0 and macro_bias > 0) or (raw_score < 0 and macro_bias < 0): raw_score *= 1.25
        elif (raw_score > 0 and macro_bias < 0) or (raw_score < 0 and macro_bias > 0): raw_score *= 0.75

    score = round(raw_score, 1)
    
    trade_levels = calculate_dynamic_trade_levels(df, score)

    if score >= 5.5: sig_text = "STRONG BUY"
    elif score >= 1.8: sig_text = "BUY"
    elif score <= -5.5: sig_text = "STRONG SELL"
    elif score <= -1.8: sig_text = "SELL"
    else: sig_text = "NEUTRAL"

    return {
        "signal": sig_text, "css": f"sig-{sig_text.lower().replace(' ', '-')}",
        "score": score, "rsi": round(rsi, 1), "pattern": candle["short"],
        "sr_tag": sr_tag, "sr": sr, "levels": trade_levels
    }

def run_top_down_analysis(symbol: str) -> dict:
    df_1mo, df_1wk, df_1d = get_ohlcv(symbol, "1mo"), get_ohlcv(symbol, "1wk"), get_ohlcv(symbol, "1d")
    res_1mo = evaluate_timeframe_signal(df_1mo, macro_bias=0)
    res_1wk = evaluate_timeframe_signal(df_1wk, macro_bias=1 if res_1mo["score"] > 1 else (-1 if res_1mo["score"] < -1 else 0))
    htf_raw = res_1mo["score"] * 0.45 + res_1wk["score"] * 0.55
    macro_bias = 1 if htf_raw >= 1.5 else (-1 if htf_raw <= -1.5 else 0)
    res_1d = evaluate_timeframe_signal(df_1d, macro_bias=macro_bias)
    
    td_score = res_1mo["score"] * 0.30 + res_1wk["score"] * 0.40 + res_1d["score"] * 0.30
    intraday_bias = 1 if td_score >= 1.8 else (-1 if td_score <= -1.8 else 0)

    results = {"1mo": res_1mo, "1wk": res_1wk, "1d": res_1d}
    for tf in ["4h", "2h", "1h", "45m", "30m", "15m"]:
        results[tf] = evaluate_timeframe_signal(get_ohlcv(symbol, tf), macro_bias=intraday_bias)

    weights = {"1mo": 0.16, "1wk": 0.18, "1d": 0.20, "4h": 0.14, "2h": 0.10, "1h": 0.09, "45m": 0.05, "30m": 0.04, "15m": 0.04}
    weighted_score = round(sum(results[tf]["score"] * w for tf, w in weights.items()), 2)

    if weighted_score >= 4.2: master_sig, master_css, master_col = "STRONG BUY", "sig-strong-buy", "#089981"
    elif weighted_score >= 1.5: master_sig, master_css, master_col = "BUY", "sig-buy", "#2ecc71"
    elif weighted_score <= -4.2: master_sig, master_css, master_col = "STRONG SELL", "sig-strong-sell", "#f23645"
    elif weighted_score <= -1.5: master_sig, master_css, master_col = "SELL", "sig-sell", "#e74c3c"
    else: master_sig, master_css, master_col = "NEUTRAL", "sig-neutral", "#787b86"

    return {
        "mtf": results, "weighted_score": weighted_score, "master_sig": master_sig,
        "master_css": master_css, "master_col": master_col,
        "regime_label": "BULLISH UPTREND" if intraday_bias == 1 else ("BEARISH DOWNTREND" if intraday_bias == -1 else "SIDEWAYS / CONSOLIDATION"),
        "regime_color": "#089981" if intraday_bias == 1 else ("#f23645" if intraday_bias == -1 else "#b2b5be")
    }

@st.cache_data(ttl=180)
def get_watchlist_snapshot() -> dict:
    snap = {}
    for item in WATCHLIST_ITEMS:
        sym = item["symbol"]
        df_1d = get_ohlcv(sym, "1d")
        if len(df_1d) >= 2:
            c, p = float(df_1d["Close"].iloc[-1]), float(df_1d["Close"].iloc[-2])
            td = run_top_down_analysis(sym)
            snap[sym] = {"price": c, "chg": c - p, "pct": ((c - p) / p) * 100, "signal": td["master_sig"], "col": td["master_col"]}
        else:
            snap[sym] = {"price": 0.0, "chg": 0.0, "pct": 0.0, "signal": "NEUTRAL", "col": "#787b86"}
    return snap

# --- SIDEBAR & TOP CONTROLS ---
with st.sidebar:
    st.markdown("<div style='font-size:1.05rem; font-weight:700; color:#ffffff; margin-bottom:6px;'>Watchlist</div>", unsafe_allow_html=True)
    search_q = st.text_input("Filter Watchlist", placeholder="Search NIFTY, RELIANCE...", label_visibility="collapsed").upper().strip()
    st.markdown("<div style='font-size:0.78rem; font-weight:600; color:#b2b5be; margin-top:6px;'>Top-Down Signal Filter</div>", unsafe_allow_html=True)
    sig_filter = st.radio("Signal Filter Mode", options=["ALL", "STRONG BUY", "STRONG SELL"], index=0, horizontal=True, label_visibility="collapsed")
    custom_sym = st.text_input("Custom Symbol", placeholder="Add symbol (e.g. ZOMATO.NS)", label_visibility="collapsed").upper().strip()
    if custom_sym and st.button(f"+ Open {custom_sym}", use_container_width=True):
        st.session_state.active_symbol, st.session_state.active_label = custom_sym, custom_sym.replace(".NS", "")
        st.rerun()

    snapshot = get_watchlist_snapshot()
    for section in ["Indices", "Stocks"]:
        filtered = [x for x in WATCHLIST_ITEMS if x["category"] == section]
        if not filtered: continue
        st.markdown(f"<div style='color:#787b86; font-size:0.75rem; font-weight:700; margin-top:10px;'>{section.upper()}</div>", unsafe_allow_html=True)
        for item in filtered:
            sym, lbl = item["symbol"], item["label"]
            info = snapshot.get(sym, {"price": 0.0, "chg": 0.0, "pct": 0.0, "signal": "NEUTRAL", "col": "#787b86"})
            if (search_q and search_q not in lbl and search_q not in sym) or (sig_filter != "ALL" and info["signal"] != sig_filter):
                continue
            is_active = st.session_state.active_symbol == sym
            pct_col = "#089981" if info["pct"] >= 0 else "#f23645"
            col_sym, col_val = st.columns([1.05, 1.45])
            with col_sym:
                if st.button(f"{'▶ ' if is_active else ''}{lbl}", key=f"wl_btn_{sym}", use_container_width=True):
                    st.session_state.active_symbol, st.session_state.active_label = sym, lbl
                    st.rerun()
            with col_val:
                st.markdown(f"<div style='text-align:right;'><span style='font-size:0.82rem; font-weight:600;'>{info['price']:,.2f}</span><br><span style='font-size:0.65rem; color:{pct_col};'>{'+' if info['pct']>=0 else ''}{info['pct']:.2f}%</span> <span style='background-color:{info['col']}; color:white; padding:2px 6px; border-radius:4px; font-weight:700; font-size:0.68rem;'>{info['signal']}</span></div>", unsafe_allow_html=True)

active_sym, active_lbl = st.session_state.active_symbol, st.session_state.active_label
td_analysis = run_top_down_analysis(active_sym)
mtf_results = td_analysis["mtf"]

top_l, top_r1, top_r2, top_r3 = st.columns([3.5, 1.1, 1.1, 0.9])
with top_r1: chart_tf = st.selectbox("Interval", options=CHART_TIMEFRAMES, index=3)
with top_r2: chart_style = st.selectbox("Style", options=["Candles", "Line"], index=0)
with top_r3:
    if st.button("Refresh", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

df_chart = get_ohlcv(active_sym, chart_tf)
if df_chart.empty:
    st.error(f"No market data available for {active_sym}.")
    st.stop()

df_chart = compute_indicators(df_chart).tail(160)
sr_chart = detect_support_resistance(df_chart)
candle_chart = detect_candlestick_patterns(df_chart)

curr_close = float(df_chart["Close"].iloc[-1])
prev_close = float(df_chart["Close"].iloc[-2]) if len(df_chart) > 1 else curr_close
chg_val = curr_close - prev_close
pct_val = (chg_val / prev_close) * 100 if prev_close != 0 else 0.0
p_col = "#089981" if pct_val >= 0 else "#f23645"

with top_l:
    st.markdown(f"<div class='tv-topbar'><div><span class='tv-sym-title'>{active_lbl}</span> <span style='color:#787b86; font-size:0.85rem;'>({active_sym}) · NSE</span></div><div><span class='tv-price' style='color:{p_col};'>₹{curr_close:,.2f}</span> <span style='color:{p_col}; font-weight:600;'>{'+' if pct_val>=0 else ''}{chg_val:.2f} ({'+' if pct_val>=0 else ''}{pct_val:.2f}%)</span></div></div>", unsafe_allow_html=True)

st.markdown(f"<div class='regime-bar'><div><span style='color:#787b86; font-weight:700;'>MACRO REGIME:</span> <span style='color:{td_analysis['regime_color']}; font-weight:700;'>{td_analysis['regime_label']}</span></div><div><span style='color:#787b86;'>SUPPORT:</span> <b style='color:#089981;'>₹{sr_chart['support']:,.2f}</b> | <span style='color:#787b86;'>RESISTANCE:</span> <b style='color:#f23645;'>₹{sr_chart['resistance']:,.2f}</b></div><div><span style='color:#787b86;'>CANDLE:</span> <b style='color:#ffffff;'>{candle_chart['name']}</b></div></div>", unsafe_allow_html=True)

# MTF Cards with Dynamic Signal Levels
tf_cols = st.columns(len(ALL_TIMEFRAMES) + 1)
for idx, tf in enumerate(ALL_TIMEFRAMES):
    r = mtf_results[tf]
    lvl = r["levels"]
    with tf_cols[idx]:
        st.markdown(f"<div class='mtf-card'><div class='mtf-tf'>{tf}</div><div class='mtf-sig {r['css']}'>{r['signal']}</div><div class='mtf-meta'>Entry: {lvl['entry']}<br>SL: {lvl['sl']}<br>T1: {lvl['t1']}</div></div>", unsafe_allow_html=True)

with tf_cols[-1]:
    st.markdown(f"<div class='mtf-card' style='border-color:#434651;'><div class='mtf-tf'>TOP-DOWN</div><div class='mtf-sig {td_analysis['master_css']}'>{td_analysis['master_sig']}</div><div class='mtf-meta'>Score {td_analysis['weighted_score']:+.2f}</div></div>", unsafe_allow_html=True)

# Extract levels for the active selected timeframe chart
active_levels = mtf_results[chart_tf]["levels"]

# Toggles
t1, t2, t3, t4, t5, t6 = st.columns(6)
show_bb = t1.checkbox("Bollinger Bands", value=True)
show_ema = t2.checkbox("EMA 20/50", value=True)
show_sr = t3.checkbox("Support & Resistance", value=True)
show_vwap = t4.checkbox("VWAP", value=False)
show_rsi = t5.checkbox("RSI (14)", value=True)
show_macd = t6.checkbox("MACD", value=False)

# Chart plotting
panels = ["price"]
if show_rsi: panels.append("rsi")
if show_macd: panels.append("macd")

fig = make_subplots(rows=len(panels), cols=1, shared_xaxes=True, vertical_spacing=0.03, row_heights=[0.6, 0.2, 0.2][:len(panels)])

if chart_style == "Candles":
    fig.add_trace(go.Candlestick(x=df_chart.index, open=df_chart["Open"], high=df_chart["High"], low=df_chart["Low"], close=df_chart["Close"], increasing_line_color="#089981", decreasing_line_color="#f23645", name=active_lbl), row=1, col=1)
else:
    fig.add_trace(go.Scatter(x=df_chart.index, y=df_chart["Close"], line=dict(color="#2962ff", width=2), name=active_lbl), row=1, col=1)

if show_bb:
    fig.add_trace(go.Scatter(x=df_chart.index, y=df_chart["BB_Upper"], line=dict(color="rgba(41, 98, 255, 0.4)", width=1), name="BB Upper"), row=1, col=1)
    fig.add_trace(go.Scatter(x=df_chart.index, y=df_chart["BB_Lower"], line=dict(color="rgba(41, 98, 255, 0.4)", width=1, dash="dot"), fill='tonexty', fillcolor='rgba(41, 98, 255, 0.05)', name="BB Lower"), row=1, col=1)
    fig.add_trace(go.Scatter(x=df_chart.index, y=df_chart["BB_Mid"], line=dict(color="rgba(41, 98, 255, 0.5)", width=1.5), name="BB Mid"), row=1, col=1)

if show_ema:
    fig.add_trace(go.Scatter(x=df_chart.index, y=df_chart["EMA20"], line=dict(color="#2962ff", width=1.5), name="EMA 20"), row=1, col=1)
    fig.add_trace(go.Scatter(x=df_chart.index, y=df_chart["EMA50"], line=dict(color="#ff9800", width=1.5), name="EMA 50"), row=1, col=1)

if show_vwap:
    fig.add_trace(go.Scatter(x=df_chart.index, y=df_chart["VWAP"], line=dict(color="#e040fb", width=1.5, dash="dot"), name="VWAP"), row=1, col=1)

# Dynamic Trade Levels Overlay with safe fallbacks
try:
    fig.add_hline(y=active_levels.get("entry", curr_close), line_dash="solid", line_color="#2962ff", line_width=1.5, row=1, col=1, annotation_text=f"ENTRY: {active_levels.get('entry', curr_close)}")
    fig.add_hline(y=active_levels.get("sl", curr_close*0.98), line_dash="dash", line_color="#f23645", line_width=1.5, row=1, col=1, annotation_text=f"SL: {active_levels.get('sl', curr_close*0.98)}")
    fig.add_hline(y=active_levels.get("t1", curr_close*1.015), line_dash="dot", line_color="#089981", line_width=1.5, row=1, col=1, annotation_text=f"T1: {active_levels.get('t1', curr_close*1.015)}")
    fig.add_hline(y=active_levels.get("t2", curr_close*1.03), line_dash="dot", line_color="#089981", line_width=1.5, row=1, col=1, annotation_text=f"T2: {active_levels.get('t2', curr_close*1.03)}")
    fig.add_hline(y=active_levels.get("t3", curr_close*1.05), line_dash="dot", line_color="#089981", line_width=1.5, row=1, col=1, annotation_text=f"T3: {active_levels.get('t3', curr_close*1.05)}")
except Exception as e:
    pass

if show_sr:
    fig.add_hline(y=sr_chart.get("resistance", curr_close*1.02), line_dash="dash", line_color="#f23645", line_width=1.5, opacity=0.5, row=1, col=1)
    fig.add_hline(y=sr_chart.get("support", curr_close*0.98), line_dash="dash", line_color="#089981", line_width=1.5, opacity=0.5, row=1, col=1)

curr_row = 2
if show_rsi:
    fig.add_trace(go.Scatter(x=df_chart.index, y=df_chart["RSI"], line=dict(color="#7e57c2", width=1.6), name="RSI (14)"), row=curr_row, col=1)
    fig.add_hrect(y0=30, y1=70, fillcolor="rgba(126, 87, 194, 0.1)", line_width=0, row=curr_row, col=1)
    fig.update_yaxes(range=[0, 100], title_text="RSI", side="right", gridcolor="#2a2e39", row=curr_row, col=1)
    curr_row += 1

if show_macd:
    fig.add_trace(go.Bar(x=df_chart.index, y=df_chart["MACD_Hist"], marker_color=np.where(df_chart["MACD_Hist"]>=0, "#089981", "#f23645"), name="MACD Hist"), row=curr_row, col=1)
    fig.add_trace(go.Scatter(x=df_chart.index, y=df_chart["MACD"], line=dict(color="#2962ff", width=1.5), name="MACD"), row=curr_row, col=1)
    fig.add_trace(go.Scatter(x=df_chart.index, y=df_chart["MACD_Signal"], line=dict(color="#ff6d00", width=1.5), name="Signal"), row=curr_row, col=1)
    fig.update_yaxes(title_text="MACD", side="right", gridcolor="#2a2e39", row=curr_row, col=1)

fig.update_yaxes(side="right", gridcolor="#2a2e39", zerolinecolor="#2a2e39", row=1, col=1)
fig.update_xaxes(gridcolor="#2a2e39", row=1, col=1)
if len(panels) > 1:
    fig.update_xaxes(gridcolor="#2a2e39", row=2, col=1)

fig.update_layout(
    height=650, paper_bgcolor="#131722", plot_bgcolor="#131722", font=dict(color="#d1d4dc"),
    xaxis_rangeslider_visible=False, hovermode="x unified",
    margin=dict(l=10, r=80, t=10, b=10),
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0)
)

st.plotly_chart(fig, use_container_width=True)
