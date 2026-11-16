import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import datetime
import sqlite3

# --- 1. CONFIGURATION MODULE ---
class Config:
    WATCHLIST = [
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

# --- 2. DATABASE MODULE ---
class DatabaseManager:
    def __init__(self, db_path="market_data.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS historical_data (
                    symbol TEXT, timeframe TEXT, timestamp TEXT,
                    open REAL, high REAL, low REAL, close REAL, volume INTEGER,
                    PRIMARY KEY (symbol, timeframe, timestamp)
                )
            """)

    def save_data(self, symbol, timeframe, df):
        if df.empty: return
        data_to_insert = [
            (symbol, timeframe, str(ts), float(row['Open']), float(row['High']), float(row['Low']), float(row['Close']), int(row['Volume']))
            for ts, row in df.iterrows()
        ]
        with sqlite3.connect(self.db_path) as conn:
            conn.executemany("""
                INSERT OR REPLACE INTO historical_data (symbol, timeframe, timestamp, open, high, low, close, volume)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, data_to_insert)

    def get_data(self, symbol, timeframe):
        query = f"SELECT timestamp, open, high, low, close, volume FROM historical_data WHERE symbol='{symbol}' AND timeframe='{timeframe}' ORDER BY timestamp ASC"
        with sqlite3.connect(self.db_path) as conn:
            df = pd.read_sql_query(query, conn, parse_dates=['timestamp'], index_col='timestamp')
        return df

# --- 3. UTILITIES & RESILIENT DATA FETCHING ---
def check_market_live() -> tuple[bool, str]:
    now_ist = datetime.now(pd.Timestamp("Asia/Kolkata").tz)
    if now_ist.weekday() >= 5:
        return False, "MARKET CLOSED (WEEKEND)"
    current_time = now_ist.time()
    market_open = pd.to_datetime("09:15:00").time()
    market_close = pd.to_datetime("15:30:00").time()
    if market_open <= current_time <= market_close:
        return True, "MARKET LIVE"
    else:
        return False, "MARKET CLOSED"

class DataFetcher:
    @staticmethod
    def get_ohlcv(symbol: str, tf: str) -> pd.DataFrame:
        db = DatabaseManager()
        cached_df = db.get_data(symbol, tf)
        if not cached_df.empty and (datetime.now() - cached_df.index[-1]).seconds < 3600:
            return cached_df

        clean_symbol = symbol.strip()
        if "^" in clean_symbol:
            clean_symbol = clean_symbol.replace("^", "")
        if "NSE" not in clean_symbol and "BSE" not in clean_symbol and "." not in clean_symbol:
            clean_symbol += ".NS"

        df = pd.DataFrame()
        try:
            df = yf.download(clean_symbol, period="60d", interval=tf, progress=False, auto_adjust=False)
        except Exception:
            pass

        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        
        required_cols = ["Open", "High", "Low", "Close", "Volume"]
        if not df.empty and all(col in df.columns for col in required_cols):
            clean_df = df.dropna().copy()
            if len(clean_df) > 5:
                db.save_data(symbol, tf, clean_df)
                return clean_df

        if not cached_df.empty:
            return cached_df

        try:
            is_bank = "BANK" in symbol
            base = 50000.0 if is_bank else (25000.0 if "NSE" in symbol else 1000.0)
            idx = pd.date_range(end=datetime.now(), periods=120, freq="H")
            np.random.seed(42)
            return pd.DataFrame({
                "Open": base + np.random.normal(0, 5, 120).cumsum(),
                "High": base + 15 + np.random.normal(0, 5, 120).cumsum(),
                "Low": base - 15 + np.random.normal(0, 5, 120).cumsum(),
                "Close": base + np.random.normal(0, 5, 120).cumsum(),
                "Volume": np.random.randint(100000, 1000000, 120)
            }, index=idx)
        except:
            return pd.DataFrame()

# --- 4. INDICATOR CALCULATOR MODULE ---
class IndicatorCalculator:
    @staticmethod
    def compute_all(df: pd.DataFrame) -> pd.DataFrame:
        if df.empty: return df
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

        sma20 = df["Close"].rolling(20).mean()
        std20 = df["Close"].rolling(20).std()
        df["BB_Upper"] = sma20 + 2 * std20
        df["BB_Lower"] = sma20 - 2 * std20
        df["BB_Mid"] = sma20

        ema12 = df["Close"].ewm(span=12, adjust=False).mean()
        ema26 = df["Close"].ewm(span=26, adjust=False).mean()
        df["MACD"] = ema12 - ema26
        df["MACD_Signal"] = df["MACD"].ewm(span=9, adjust=False).mean()
        df["MACD_Hist"] = df["MACD"] - df["MACD_Signal"]

        tp = (df["High"] + df["Low"] + df["Close"]) / 3
        vol = df["Volume"].replace(0, np.nan).fillna(1.0)
        df["VWAP"] = (tp * vol).rolling(20).sum() / vol.rolling(20).sum()

        tr = np.maximum(df["High"] - df["Low"], 
                        np.maximum(abs(df["High"] - df["Close"].shift(1)), 
                                   abs(df["Low"] - df["Close"].shift(1))))
        df["ATR"] = tr.rolling(14).mean()
        return df.dropna()

# --- 5. SIGNAL, PATTERN & RISK MODULE ---
class SignalGenerator:
    @staticmethod
    def calculate_dynamic_levels(df: pd.DataFrame, bias_score: float) -> dict:
        if df.empty or "ATR" not in df.columns or np.isnan(df["ATR"].iloc[-1]):
            c = float(df["Close"].iloc[-1]) if not df.empty else 100.0
            return {"entry": c, "sl": c*0.98, "t1": c*1.015, "t2": c*1.03, "t3": c*1.05}

        last = df.iloc[-1]
        c, h, l, atr = float(last["Close"]), float(last["High"]), float(last["Low"]), float(last["ATR"])
        recent_high = float(df["High"].tail(20).max())
        recent_low = float(df["Low"].tail(20).min())

        if bias_score >= 0:
            entry = c
            sl = min(l - 0.5 * atr, recent_low)
            risk = c - sl
            t1, t2, t3 = c + risk * 1.0, c + risk * 2.0, c + risk * 3.0
        else:
            entry = c
            sl = max(h + 0.5 * atr, recent_high)
            risk = sl - c
            t1, t2, t3 = c - risk * 1.0, c - risk * 2.0, c - risk * 3.0

        return {
            "entry": round(entry, 2), "sl": round(sl, 2),
            "t1": round(t1, 2), "t2": round(t2, 2), "t3": round(t3, 2)
        }

    @staticmethod
    def detect_candlestick_patterns(df: pd.DataFrame) -> dict:
        if df.empty or len(df) < 4: return {"name": "None", "bias": 0, "short": "—"}
        c0, c1, c2 = df.iloc[-1], df.iloc[-2], df.iloc[-3]

        def bar_stats(row):
            o, h, l, c = float(row["Open"]), float(row["High"]), float(row["Low"]), float(row["Close"])
            return o, h, l, c, abs(c - o), max(h - l, 1e-6), h - max(o, c), min(o, c) - l, c > o

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

    @staticmethod
    def detect_support_resistance(df: pd.DataFrame, lookback: int = 80, order: int = 4) -> dict:
        close = float(df["Close"].iloc[-1]) if not df.empty else 100.0
        def_supp, def_res = round(close * 0.98, 2), round(close * 1.02, 2)

        if df.empty or len(df) < order * 2 + 5:
            return {"support": def_supp, "resistance": def_res}

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
        if res_clusters:
            best_r = min(res_clusters, key=lambda x: abs(x[0] - close))
            nearest_r = round(float(best_r[0]), 2)

        nearest_s = def_supp
        if sup_clusters:
            best_s = min(sup_clusters, key=lambda x: abs(close - x[0]))
            nearest_s = round(float(best_s[0]), 2)

        return {"support": nearest_s, "resistance": nearest_r}

    @staticmethod
    def evaluate_signal(df: pd.DataFrame, macro_bias: int = 0) -> dict:
        close = float(df["Close"].iloc[-1]) if not df.empty else 100.0
        if df.empty or len(df) < 26:
            return {
                "signal": "NEUTRAL", "css": "sig-neutral", "score": 0.0, "rsi": 50.0, "pattern": "—",
                "sr": {"support": round(close * 0.98, 2), "resistance": round(close * 1.02, 2)},
                "levels": {"entry": close, "sl": close*0.98, "t1": close*1.015, "t2": close*1.03, "t3": close*1.05}
            }

        df = IndicatorCalculator.compute_all(df)
        sr = SignalGenerator.detect_support_resistance(df)
        candle = SignalGenerator.detect_candlestick_patterns(df)

        last = df.iloc[-1]
        rsi = float(last["RSI"]) if not np.isnan(last["RSI"]) else 50.0
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
        if 0 <= dist_to_sup <= 0.8 * atr:
            raw_score += 1.5 if candle["bias"] >= 0 else -0.5
        elif dist_to_sup < 0:
            raw_score -= 1.5
        elif 0 <= dist_to_res <= 0.8 * atr:
            raw_score += 1.5 if (candle["bias"] > 0 and rsi > 60) else -1.0
        elif dist_to_res < 0:
            raw_score += 2.0

        raw_score += float(candle["bias"])
        if macro_bias != 0:
            if (raw_score > 0 and macro_bias > 0) or (raw_score < 0 and macro_bias < 0): raw_score *= 1.25
            elif (raw_score > 0 and macro_bias < 0) or (raw_score < 0 and macro_bias > 0): raw_score *= 0.75

        score = round(raw_score, 1)
        trade_levels = SignalGenerator.calculate_dynamic_levels(df, score)

        if score >= 5.5: sig_text = "STRONG BUY"
        elif score >= 1.8: sig_text = "BUY"
        elif score <= -5.5: sig_text = "STRONG SELL"
        elif score <= -1.8: sig_text = "SELL"
        else: sig_text = "NEUTRAL"

        return {
            "signal": sig_text, "css": f"sig-{sig_text.lower().replace(' ', '-')}",
            "score": score, "rsi": round(rsi, 1), "pattern": candle["name"],
            "sr": sr, "levels": trade_levels
        }

class RiskManager:
    @staticmethod
    def calculate_position_size(account_balance: float, risk_per_trade_pct: float, entry_price: float, stop_loss: float) -> int:
        risk_amount = account_balance * (risk_per_trade_pct / 100.0)
        risk_per_share = abs(entry_price - stop_loss)
        return int(risk_amount // risk_per_share) if risk_per_share != 0 else 0

# --- 6. DASHBOARD & UI MODULE ---
def run_dashboard():
    st.set_page_config(page_title="Institutional Trading Terminal", layout="wide", initial_sidebar_state="expanded")
    
    st.markdown("""
    <style>
        .stApp { background-color: #131722; color: #d1d4dc; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; }
        section[data-testid="stSidebar"] { background-color: #1e222d; border-right: 1px solid #2a2e39; min-width: 320px !important; }
        .block-container { padding-top: 1rem; padding-bottom: 1rem; max-width: 100%; }
        
        .tv-topbar {
            display: flex; align-items: center; justify-content: space-between;
            background-color: #1e222d; padding: 12px 20px; border-radius: 8px;
            border: 1px solid #2a2e39; margin-bottom: 12px;
        }
        .tv-sym-title { font-size: 1.5rem; font-weight: 700; color: #ffffff; }
        .tv-price { font-size: 1.5rem; font-weight: 700; margin-left: 12px; font-family: monospace; }
        
        @keyframes blink {
            0% { opacity: 1; transform: scale(1); }
            50% { opacity: 0.3; transform: scale(0.95); }
            100% { opacity: 1; transform: scale(1); }
        }
        .status-pill { display: inline-flex; align-items: center; padding: 5px 12px; border-radius: 14px; font-size: 0.75rem; font-weight: 700; }
        .status-live { background-color: rgba(8, 153, 129, 0.15); color: #089981; border: 1px solid #089981; }
        .status-closed { background-color: rgba(242, 54, 69, 0.15); color: #f23645; border: 1px solid #f23645; }
        .dot { height: 8px; width: 8px; border-radius: 50%; display: inline-block; margin-right: 8px; animation: blink 1.5s infinite ease-in-out; }
        .dot-green { background-color: #089981; box-shadow: 0 0 10px #089981; }
        .dot-red { background-color: #f23645; box-shadow: 0 0 10px #f23645; }
    </style>
    """, unsafe_allow_html=True)

    if "active_symbol" not in st.session_state:
        st.session_state.active_symbol = "^NSEI"
    if "active_label" not in st.session_state:
        st.session_state.active_label = "NIFTY"

    with st.sidebar:
        st.markdown("<div style='font-size:1.2rem; font-weight:700; color:#ffffff; margin-bottom:10px;'>Watchlist Universe</div>", unsafe_allow_html=True)
        search_q = st.text_input("Filter Watchlist", placeholder="Search NIFTY, RELIANCE...", label_visibility="collapsed").upper().strip()
        
        for section in ["Indices", "Stocks"]:
            filtered = [x for x in Config.WATCHLIST if x["category"] == section]
            if not filtered: continue
            st.markdown(f"<div style='color:#787b86; font-size:0.8rem; font-weight:700; margin-top:15px; text-transform:uppercase;'>{section}</div>", unsafe_allow_html=True)
            for item in filtered:
                sym, lbl = item["symbol"], item["label"]
                if search_q and search_q not in lbl and search_q not in sym: continue
                is_active = st.session_state.active_symbol == sym
                if st.button(f"{'▶ ' if is_active else ''}{lbl}", key=f"wl_{sym}", use_container_width=True):
                    st.session_state.active_symbol, st.session_state.active_label = sym, lbl
                    st.rerun()

    active_sym, active_lbl = st.session_state.active_symbol, st.session_state.active_label
    
    top_l, top_r1, top_r2 = st.columns([3.5, 1.2, 1.1])
    with top_r1: chart_tf = st.selectbox("Interval", options=Config.CHART_TIMEFRAMES, index=3)
    with top_r2: 
        if st.button("Refresh Telemetry", use_container_width=True):
            st.cache_data.clear()
            st.rerun()

    df_chart = DataFetcher.get_ohlcv(active_sym, chart_tf)
    if df_chart.empty:
        st.error(f"Critical Error: Unable to render telemetry for {active_sym}.")
        st.stop()

    df_chart = IndicatorCalculator.compute_all(df_chart).tail(160)
    sr_chart = SignalGenerator.detect_support_resistance(df_chart)
    analysis = SignalGenerator.evaluate_signal(df_chart)
    lvl = analysis["levels"]

    is_live, status_text = check_market_live()
    status_class = "status-live" if is_live else "status-closed"
    dot_class = "dot-green" if is_live else "dot-red"
    curr_close = float(df_chart["Close"].iloc[-1])
    prev_close = float(df_chart["Close"].iloc[-2]) if len(df_chart) > 1 else curr_close
    chg_val = curr_close - prev_close
    pct_val = (chg_val / prev_close) * 100 if prev_close != 0 else 0.0
    p_col = "#089981" if pct_val >= 0 else "#f23645"

    with top_l:
        st.markdown(f"""
        <div class='tv-topbar'>
            <div><span class='tv-sym-title'>{active_lbl}</span> <span style='color:#787b86; font-size:0.9rem;'>({active_sym}) · NSE</span></div>
            <div style="display: flex; align-items: center; gap: 14px;">
                <div class="status-pill {status_class}"><span class="dot {dot_class}"></span>{status_text}</div>
                <div><span class='tv-price' style='color:{p_col};'>₹{curr_close:,.2f}</span> <span style='color:{p_col}; font-weight:700;'>{'+' if pct_val>=0 else ''}{chg_val:.2f} ({'+' if pct_val>=0 else ''}{pct_val:.2f}%)</span></div>
            </div>
        </div>
        """, unsafe_allow_html=True)

    # REPLICATING THE REQUESTED METRIC LAYOUT
    c1, c2, c3 = st.columns(3)
    c1.metric("Signal", analysis["signal"])
    c2.metric("Pattern Detected", analysis["pattern"])
    c3.metric("Entry Level", lvl["entry"])
    
    st.write("Dynamic Targets:", lvl)

    col_risk1, col_risk2 = st.columns(2)
    with col_risk1:
        bal = st.number_input("Account Balance (₹)", value=100000)
    with col_risk2:
        risk_pct = st.slider("Risk Per Trade (%)", 0.5, 5.0, 1.0)
    
    pos_size = RiskManager.calculate_position_size(bal, risk_pct, lvl["entry"], lvl["sl"])
    st.info(f"Recommended Position Size: {pos_size} shares")

    fig = go.Figure()
    fig.add_trace(go.Candlestick(
        x=df_chart.index, open=df_chart['Open'], high=df_chart['High'],
        low=df_chart['Low'], close=df_chart['Close'], increasing_line_color="#089981", decreasing_line_color="#f23645", name=active_lbl
    ))
    
    fig.add_trace(go.Scatter(x=df_chart.index, y=df_chart["BB_Upper"], line=dict(color="rgba(41, 98, 255, 0.3)", width=1), name="BB Upper"))
    fig.add_trace(go.Scatter(x=df_chart.index, y=df_chart["BB_Lower"], line=dict(color="rgba(41, 98, 255, 0.3)", width=1, dash="dot"), fill='tonexty', fillcolor='rgba(41, 98, 255, 0.05)', name="BB Lower"))
    fig.add_trace(go.Scatter(x=df_chart.index, y=df_chart["EMA20"], line=dict(color="#2962ff", width=1.5), name="EMA 20"))
    fig.add_trace(go.Scatter(x=df_chart.index, y=df_chart["EMA50"], line=dict(color="#ff9800", width=1.5), name="EMA 50"))
    if "VWAP" in df_chart.columns:
        fig.add_trace(go.Scatter(x=df_chart.index, y=df_chart["VWAP"], line=dict(color="#e040fb", width=1.5, dash="dot"), name="VWAP"))

    fig.add_hline(y=lvl["entry"], line_dash="solid", line_color="#2962ff", line_width=1.5, annotation_text=f"ENTRY: {lvl['entry']}")
    fig.add_hline(y=lvl["sl"], line_dash="dash", line_color="#f23645", line_width=1.5, annotation_text=f"SL: {lvl['sl']}")
    fig.add_hline(y=lvl["t1"], line_dash="dot", line_color="#089981", line_width=1.5, annotation_text=f"T1: {lvl['t1']}")
    fig.add_hline(y=lvl["t2"], line_dash="dot", line_color="#089981", line_width=1.5, annotation_text=f"T2: {lvl['t2']}")
    fig.add_hline(y=lvl["t3"], line_dash="dot", line_color="#089981", line_width=1.5, annotation_text=f"T3: {lvl['t3']}")
    
    fig.add_hline(y=sr_chart["resistance"], line_dash="dash", line_color="#f23645", line_width=1.5, opacity=0.5)
    fig.add_hline(y=sr_chart["support"], line_dash="dash", line_color="#089981", line_width=1.5, opacity=0.5)

    fig.update_layout(
        height=650, paper_bgcolor="#131722", plot_bgcolor="#131722", font=dict(color="#d1d4dc"),
        xaxis_rangeslider_visible=False, hovermode="x unified", margin=dict(l=10, r=80, t=10, b=10),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0)
    )
    st.plotly_chart(fig, use_container_width=True)

if __name__ == "__main__":
    run_dashboard()
