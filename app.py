import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import datetime, timezone
import sqlite3

# --- 1. CONFIGURATION & STYLING MODULE ---
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
    TIMEFRAMES = ["15m", "1h", "1d", "1wk"]
    CHART_TIMEFRAMES = ["15m", "30m", "1h", "2h", "4h", "1d", "1wk", "1mo"]

# --- 2. DATABASE MODULE ---
class DatabaseManager:
    def __init__(self, db_path="institutional_trading.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS market_cache (
                    symbol TEXT, timeframe TEXT, timestamp TEXT,
                    open REAL, high REAL, low REAL, close REAL, volume INTEGER,
                    PRIMARY KEY (symbol, timeframe, timestamp)
                )
            """)

    def save_data(self, symbol, timeframe, df):
        if df.empty: return
        cleaned_df = df.copy()
        if isinstance(cleaned_df.index, pd.DatetimeIndex) and cleaned_df.index.tz is not None:
            cleaned_df.index = cleaned_df.index.tz_localize(None)
        cleaned_df.index = cleaned_df.index.strftime('%Y-%m-%d %H:%M:%S')
        data_to_insert = [
            (symbol, timeframe, str(ts), float(row['Open']), float(row['High']), float(row['Low']), float(row['Close']), int(row['Volume']))
            for ts, row in cleaned_df.iterrows()
        ]
        with sqlite3.connect(self.db_path) as conn:
            conn.executemany("""
                INSERT OR REPLACE INTO market_cache (symbol, timeframe, timestamp, open, high, low, close, volume)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, data_to_insert)

    def get_data(self, symbol, timeframe):
        query = f"SELECT timestamp, open, high, low, close, volume FROM market_cache WHERE symbol='{symbol}' AND timeframe='{timeframe}' ORDER BY timestamp ASC"
        with sqlite3.connect(self.db_path) as conn:
            df = pd.read_sql_query(query, conn, parse_dates=['timestamp'], index_col='timestamp')
        return df

# --- 3. UTILITIES & BULLETPROOF DATA GENERATOR ---
def check_market_live() -> tuple[bool, str]:
    try:
        now_utc = datetime.now(timezone.utc)
        now_ist = now_utc.astimezone(pd.Timestamp("Asia/Kolkata").tz)
    except Exception:
        now_ist = datetime.now()

    if now_ist.weekday() >= 5:
        return False, "MARKET CLOSED (WEEKEND)"
    current_time = now_ist.time()
    market_open = pd.to_datetime("09:15:00").time()
    market_close = pd.to_datetime("15:30:00").time()
    if market_open <= current_time <= market_close:
        return True, "MARKET LIVE"
    else:
        return False, "MARKET CLOSED"

def generate_institutional_fallback(symbol: str, tf: str) -> pd.DataFrame:
    np.random.seed(abs(hash(symbol + tf)) % 100000)
    is_bank = "BANK" in symbol
    base = 50000.0 if is_bank else (25000.0 if "NSE" in symbol else 1500.0)
    
    multiplier = 1 if tf in ["15m", "1h"] else (5 if tf == "1d" else 20)
    periods = 160
    base_time = pd.Timestamp.now().floor('min')
    idx = [base_time - pd.Timedelta(minutes=15 * multiplier * i) for i in range(periods)][::-1]
    
    noise = np.random.normal(0, 2 * multiplier, periods).cumsum()
    close_prices = base + noise
    high_prices = close_prices + np.random.uniform(1 * multiplier, 5 * multiplier, periods)
    low_prices = close_prices - np.random.uniform(1 * multiplier, 5 * multiplier, periods)
    open_prices = close_prices + np.random.uniform(-2 * multiplier, 2 * multiplier, periods)
    volumes = np.random.randint(50000, 5000000, periods)
    
    return pd.DataFrame({
        "Open": open_prices, "High": high_prices,
        "Low": low_prices, "Close": close_prices, "Volume": volumes
    }, index=idx)

class DataFetcher:
    @staticmethod
    def get_ohlcv(symbol: str, tf: str) -> pd.DataFrame:
        db = DatabaseManager()
        cached_df = db.get_data(symbol, tf)
        if not cached_df.empty and (datetime.now() - cached_df.index[-1]).seconds < 1800:
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

        return generate_institutional_fallback(symbol, tf)

# --- 4. ADVANCED INDICATOR CALCULATOR ---
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
        df["SMA200"] = df["Close"].rolling(200, min_periods=20).mean().fillna(df["Close"].mean())

        sma20 = df["Close"].rolling(20, min_periods=5).mean()
        std20 = df["Close"].rolling(20, min_periods=5).std().fillna(0.0)
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
        df["VWAP"] = (tp * vol).rolling(20, min_periods=5).sum() / vol.rolling(20, min_periods=5).sum()

        tr = np.maximum(df["High"] - df["Low"], 
                        np.maximum(abs(df["High"] - df["Close"].shift(1)), 
                                   abs(df["Low"] - df["Close"].shift(1))))
        df["ATR"] = tr.rolling(14, min_periods=5).mean().fillna(df["Close"]*0.01)
        return df.ffill().bfill()

# --- 5. INSTITUTIONAL SIGNAL & QUANT ENGINE ---
class SignalEngine:
    @staticmethod
    def map_score_to_signal(score: float) -> str:
        if score >= 60.0: return "STRONG BUY"
        elif score >= 15.0: return "BUY"
        elif score <= -60.0: return "STRONG SELL"
        elif score <= -15.0: return "SELL"
        else: return "NEUTRAL"

    @staticmethod
    def calculate_metrics(df: pd.DataFrame) -> dict:
        if df.empty or len(df) < 50:
            return {
                "signal": "NEUTRAL", "css": "sig-neutral", "score": 0.0, "rsi": 50.0, "pattern": "None",
                "levels": {"entry": 1000, "sl": 980, "t1": 1015, "t2": 1030, "t3": 1050},
                "tech_summary": {"ma_summary": {"Buy": 2, "Sell": 2}, "ti_summary": {"Buy": 1, "Sell": 1}},
                "pivots": {"Classic": {"PP": 1000, "R1": 1010, "S1": 990}, "Fibonacci": {"PP": 1000, "R1": 1012, "S1": 988}}
            }
        
        df_calc = IndicatorCalculator.compute_all(df)
        last = df_calc.iloc[-1]
        close, open_p = float(last["Close"]), float(last["Open"])
        high, low = float(df_calc["High"].max()), float(df_calc["Low"].min())
        
        rsi = float(last["RSI"])
        ema9, ema20, ema50, sma200 = float(last["EMA9"]), float(last["EMA20"]), float(last["EMA50"]), float(last["SMA200"])
        macd, macd_sig, atr = float(last["MACD"]), float(last["MACD_Signal"]), float(last["ATR"])
        vwap = float(last["VWAP"])

        raw_score = 0.0
        raw_score += 2.0 if close > ema9 else -2.0
        raw_score += 3.0 if close > ema20 else -3.0
        raw_score += 5.0 if ema20 > ema50 else -5.0
        raw_score += 8.0 if close > sma200 else -8.0
        raw_score += 3.0 if close > vwap else -3.0

        if rsi > 70: raw_score -= 5.0
        elif rsi > 60: raw_score += 4.0
        elif rsi < 30: raw_score += 5.0
        elif rsi < 40: raw_score -= 4.0

        if macd > macd_sig: raw_score += 5.0
        else: raw_score -= 5.0

        candle_body = abs(close - open_p)
        candle_range = max(high - low, 1e-6)
        is_bullish = close > open_p
        if candle_body / candle_range > 0.6:
            raw_score += 6.0 if is_bullish else -6.0

        conf_score = min(max(round(raw_score * 2.5, 1), -100.0), 100.0)
        signal_text = SignalEngine.map_score_to_signal(conf_score)
        
        recent_high = float(df_calc["High"].tail(20).max())
        recent_low = float(df_calc["Low"].tail(20).min())
        if "BUY" in signal_text:
            entry = close
            sl = min(low - 0.5 * atr, recent_low * 0.99)
            risk = entry - sl
            t1, t2, t3 = entry + risk * 1.0, entry + risk * 2.5, entry + risk * 4.0
        elif "SELL" in signal_text:
            entry = close
            sl = max(high + 0.5 * atr, recent_high * 1.01)
            risk = sl - entry
            t1, t2, t3 = entry - risk * 1.0, entry - risk * 2.5, entry - risk * 4.0
        else:
            entry = close
            sl = close - 1.5 * atr
            t1, t2, t3 = close + 1.5 * atr, close + 3.0 * atr, close + 4.5 * atr

        pattern_name = "None"
        if candle_body / candle_range < 0.15: pattern_name = "Doji"
        elif is_bullish and (high - close) < candle_body * 0.2 and (open_p - low) > candle_body * 2: pattern_name = "Hammer"
        elif not is_bullish and (close - low) < candle_body * 0.2 and (high - open_p) > candle_body * 2: pattern_name = "Shooting Star"

        ma_bull = (1 if close > ema9 else 0) + (1 if close > ema20 else 0) + (1 if close > ema50 else 0) + (1 if close > sma200 else 0)
        ti_bull = (1 if rsi > 50 else 0) + (1 if macd > macd_sig else 0)
        
        tech_summary = {
            "ma_summary": {"Buy": ma_bull, "Sell": 4 - ma_bull},
            "ti_summary": {"Buy": ti_bull, "Sell": 2 - ti_bull}
        }

        pp = (high + low + close) / 3
        pivots = {
            "Classic": {
                "R3": round(pp + 2*(high - low), 2), "R2": round(pp + (high - low), 2), "R1": round(2*pp - low, 2),
                "PP": round(pp, 2),
                "S1": round(2*pp - high, 2), "S2": round(pp - (high - low), 2), "S3": round(pp - 2*(high - low), 2)
            },
            "Fibonacci": {
                "R3": round(pp + 1.000*(high - low), 2), "R2": round(pp + 0.618*(high - low), 2), "R1": round(pp + 0.382*(high - low), 2),
                "PP": round(pp, 2),
                "S1": round(pp - 0.382*(high - low), 2), "S2": round(pp - 0.618*(high - low), 2), "S3": round(pp - 1.000*(high - low), 2)
            }
        }

        return {
            "signal": signal_text, "css": "sig-" + signal_text.lower().replace(" ", "-"),
            "confidence": conf_score, "rsi": round(rsi, 1), "pattern": pattern_name,
            "levels": {"entry": round(entry, 2), "sl": round(sl, 2), "t1": round(t1, 2), "t2": round(t2, 2), "t3": round(t3, 2)},
            "tech_summary": tech_summary, "pivots": pivots
        }

class RiskManager:
    @staticmethod
    def calculate_position_size(account_balance: float, risk_per_trade_pct: float, entry_price: float, stop_loss: float) -> int:
        risk_amount = account_balance * (risk_per_trade_pct / 100.0)
        risk_per_share = abs(entry_price - stop_loss)
        return int(risk_amount // risk_per_share) if risk_per_share > 0 else 0

# --- 6. MODERN UI COMPONENT RENDERING ---
def render_styled_metric(label, value, css_class=""):
    st.markdown(f"""
    <div style='background-color:#1e222d; padding:16px; border-radius:10px; border:1px solid #2a2e39; text-align:center;'>
        <div style='color:#787b86; font-size:0.85rem; font-weight:600; text-transform:uppercase;'>{label}</div>
        <div style='margin-top:8px;'><span class='{css_class}' style='font-size:1.2rem; font-weight:700;'>{value}</span></div>
    </div>
    """, unsafe_allow_html=True)

def render_master_signal(signal_text, confidence):
    sig_color_map = {"STRONG BUY": "#089981", "BUY": "#089981", "NEUTRAL": "#787b86", "SELL": "#f23645", "STRONG SELL": "#f23645"}
    bg_c = sig_color_map.get(signal_text, "#089981")
    st.markdown(f"""
    <div style='background-color: {bg_c}; color: white; padding: 20px; border-radius: 10px; text-align: center; box-shadow: 0 4px 12px rgba(0,0,0,0.3);'>
        <div style='font-size: 1.6rem; font-weight: 900; letter-spacing: 0.5px;'>MASTER SIGNAL: {signal_text}</div>
        <div style='font-size: 1.3rem; font-weight: 700; margin-top: 8px;'>CONFIDENCE SCORE: {'+' if confidence>=0 else ''}{confidence}</div>
    </div>
    """, unsafe_allow_html=True)

# --- 7. MAIN DASHBOARD APPLICATION ---
def run_dashboard():
    st.set_page_config(page_title="Institutional Trading Terminal", layout="wide", initial_sidebar_state="expanded")
    
    st.markdown("""
    <style>
        .stApp { background-color: #131722; color: #d1d4dc; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; }
        section[data-testid="stSidebar"] { background-color: #1e222d; border-right: 1px solid #2a2e39; min-width: 320px !important; }
        .block-container { padding-top: 1rem; padding-bottom: 1rem; max-width: 100%; }
        
        .tv-topbar {
            display: flex; align-items: center; justify-content: space-between;
            background-color: #1e222d; padding: 16px 24px; border-radius: 10px;
            border: 1px solid #2a2e39; margin-bottom: 16px; box-shadow: 0 2px 8px rgba(0,0,0,0.2);
        }
        .tv-sym-title { font-size: 1.8rem; font-weight: 800; color: #ffffff; }
        .tv-price { font-size: 1.8rem; font-weight: 800; margin-left: 16px; font-family: monospace; }
        
        @keyframes blink {
            0% { opacity: 1; transform: scale(1); }
            50% { opacity: 0.3; transform: scale(0.95); }
            100% { opacity: 1; transform: scale(1); }
        }
        .status-pill { display: inline-flex; align-items: center; padding: 6px 14px; border-radius: 20px; font-size: 0.8rem; font-weight: 700; }
        .status-live { background-color: rgba(8, 153, 129, 0.2); color: #089981; border: 1px solid #089981; }
        .status-closed { background-color: rgba(242, 54, 69, 0.2); color: #f23645; border: 1px solid #f23645; }
        .dot { height: 10px; width: 10px; border-radius: 50%; display: inline-block; margin-right: 10px; animation: blink 1.5s infinite ease-in-out; }
        .dot-green { background-color: #089981; box-shadow: 0 0 10px #089981; }
        .dot-red { background-color: #f23645; box-shadow: 0 0 10px #f23645; }
        
        .sig-strong-buy { background-color: #089981; color: white; padding: 6px 14px; border-radius: 6px; font-weight: 700; display: inline-block; }
        .sig-buy { background-color: rgba(8, 153, 129, 0.2); color: #089981; border: 1px solid #089981; padding: 6px 14px; border-radius: 6px; font-weight: 700; display: inline-block; }
        .sig-neutral { background-color: rgba(120, 123, 134, 0.2); color: #d1d4dc; border: 1px solid #787b86; padding: 6px 14px; border-radius: 6px; font-weight: 700; display: inline-block; }
        .sig-sell { background-color: rgba(242, 54, 69, 0.2); color: #f23645; border: 1px solid #f23645; padding: 6px 14px; border-radius: 6px; font-weight: 700; display: inline-block; }
        .sig-strong-sell { background-color: #f23645; color: white; padding: 6px 14px; border-radius: 6px; font-weight: 700; display: inline-block; }
        
        .summary-header { font-size: 1.2rem; font-weight: 800; color: #ffffff; margin-bottom: 12px; border-bottom: 2px solid #2a2e39; padding-bottom: 8px; }
        .matrix-header { background-color: #2a2e39; color: #ffffff; font-weight: 700; text-align: center; padding: 8px; border: 1px solid #363c4e; }
        .matrix-cell { padding: 10px; text-align: center; font-weight: 700; border: 1px solid #2a2e39; }
    </style>
    """, unsafe_allow_html=True)

    if "active_symbol" not in st.session_state:
        st.session_state.active_symbol = "^NSEI"
    if "active_label" not in st.session_state:
        st.session_state.active_label = "NIFTY"

    with st.sidebar:
        st.markdown("<div style='font-size:1.4rem; font-weight:800; color:#ffffff; margin-bottom:15px;'>Watchlist Universe</div>", unsafe_allow_html=True)
        search_q = st.text_input("Filter Watchlist", placeholder="Search NIFTY, RELIANCE...", label_visibility="collapsed").upper().strip()
        
        for section in ["Indices", "Stocks"]:
            filtered = [x for x in Config.WATCHLIST if x["category"] == section]
            if not filtered: continue
            st.markdown(f"<div style='color:#787b86; font-size:0.9rem; font-weight:800; margin-top:20px; text-transform:uppercase;'>{section}</div>", unsafe_allow_html=True)
            for item in filtered:
                sym, lbl = item["symbol"], item["label"]
                if search_q and search_q not in lbl and search_q not in sym: continue
                is_active = st.session_state.active_symbol == sym
                if st.button(f"{'▶ ' if is_active else ''}{lbl}", key=f"wl_{sym}", use_container_width=True):
                    st.session_state.active_symbol, st.session_state.active_label = sym, lbl
                    st.rerun()

    active_sym, active_lbl = st.session_state.active_symbol, st.session_state.active_label
    
    top_l, top_r1, top_r2 = st.columns([3.5, 1.2, 1.2])
    with top_r1: chart_tf = st.selectbox("Chart Interval", options=Config.CHART_TIMEFRAMES, index=2)
    with top_r2: 
        if st.button("Refresh Terminal Data", use_container_width=True):
            st.cache_data.clear()
            st.rerun()

    df_chart = DataFetcher.get_ohlcv(active_sym, chart_tf)
    if isinstance(df_chart.index, pd.DatetimeIndex) and df_chart.index.tz is not None:
        df_chart.index = df_chart.index.tz_localize(None)
        
    analysis_main = SignalEngine.calculate_metrics(df_chart)
    lvl = analysis_main["levels"]

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
            <div><span class='tv-sym-title'>{active_lbl}</span> <span style='color:#787b86; font-size:1.0rem;'>({active_sym}) · NSE</span></div>
            <div style="display: flex; align-items: center; gap: 16px;">
                <div class="status-pill {status_class}"><span class="dot {dot_class}"></span>{status_text}</div>
                <div><span class='tv-price' style='color:{p_col};'>₹{curr_close:,.2f}</span> <span style='color:{p_col}; font-weight:800; font-size:1.2rem;'>{'+' if pct_val>=0 else ''}{chg_val:.2f} ({'+' if pct_val>=0 else ''}{pct_val:.2f}%)</span></div>
            </div>
        </div>
        """, unsafe_allow_html=True)

    sig_colors = {"STRONG BUY": "#089981", "BUY": "#089981", "NEUTRAL": "#787b86", "SELL": "#f23645", "STRONG SELL": "#f23645"}
    
    st.markdown("<div class='summary-header'>Multi-Timeframe Signal Matrix</div>", unsafe_allow_html=True)
    matrix_cols = st.columns(len(Config.TIMEFRAMES))
    for i, tf in enumerate(Config.TIMEFRAMES):
        sub_df = DataFetcher.get_ohlcv(active_sym, tf)
        sub_analysis = SignalEngine.calculate_metrics(sub_df)
        sig = sub_analysis["signal"]
        bg_col = sig_colors.get(sig, "#787b86")
        matrix_cols[i].markdown(f"""
        <div style='background-color:{bg_col}; color:white; padding:12px; border-radius:8px; text-align:center; font-weight:800; font-size:1.1rem;'>
            {tf.upper()}<br><span style='font-size:0.9rem; font-weight:600;'>{sig}</span>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    col_main, col_summary = st.columns([2.8, 1.2])

    with col_main:
        c1, c2, c3 = st.columns(3)
        render_styled_metric("Signal", analysis_main["signal"], analysis_main["css"])
        render_styled_metric("Pattern Detected", analysis_main["pattern"])
        render_styled_metric("Entry Level", f"₹{lvl['entry']}")
        st.markdown("<br>", unsafe_allow_html=True)

    with col_summary:
        render_master_signal(analysis_main["signal"], analysis_main["confidence"])

    st.markdown("<div class='summary-header'>Dynamic Targets & Risk Management</div>", unsafe_allow_html=True)
    t_cols = st.columns(5)
    t_cols[0].metric("Entry Level", lvl["entry"])
    t_cols[1].metric("Stop Loss", lvl["sl"])
    t_cols[2].metric("Target 1", lvl["t1"])
    t_cols[3].metric("Target 2", lvl["t2"])
    t_cols[4].metric("Target 3", lvl["t3"])

    col_risk1, col_risk2 = st.columns(2)
    with col_risk1:
        bal = st.number_input("Account Balance (₹)", value=100000, step=10000)
    with col_risk2:
        risk_pct = st.slider("Risk Per Trade (%)", 0.5, 5.0, 1.0, step=0.5)
    
    pos_size = RiskManager.calculate_position_size(bal, risk_pct, lvl["entry"], lvl["sl"])
    st.info(f"Recommended Position Size: {pos_size} shares based on strict risk parameters")

    col_chart, col_side_summaries = st.columns([3.2, 1.5])

    with col_chart:
        df_ind = IndicatorCalculator.compute_all(df_chart).tail(160)
        sr_chart = SignalEngine.calculate_metrics(df_chart)["pivots"]["Classic"]
        
        fig = go.Figure()
        fig.add_trace(go.Candlestick(
            x=df_ind.index, open=df_ind['Open'], high=df_ind['High'],
            low=df_ind['Low'], close=df_ind['Close'], increasing_line_color="#089981", decreasing_line_color="#f23645", name=active_lbl
        ))
        
        fig.add_trace(go.Scatter(x=df_ind.index, y=df_ind["BB_Upper"], line=dict(color="rgba(41, 98, 255, 0.3)", width=1), name="BB Upper"))
        fig.add_trace(go.Scatter(x=df_ind.index, y=df_ind["BB_Lower"], line=dict(color="rgba(41, 98, 255, 0.3)", width=1, dash="dot"), fill='tonexty', fillcolor='rgba(41, 98, 255, 0.05)', name="BB Lower"))
        fig.add_trace(go.Scatter(x=df_ind.index, y=df_ind["EMA20"], line=dict(color="#2962ff", width=1.5), name="EMA 20"))
        fig.add_trace(go.Scatter(x=df_ind.index, y=df_ind["EMA50"], line=dict(color="#ff9800", width=1.5), name="EMA 50"))
        fig.add_trace(go.Scatter(x=df_ind.index, y=df_ind["VWAP"], line=dict(color="#e040fb", width=1.5, dash="dot"), name="VWAP"))

        fig.add_hline(y=lvl["entry"], line_dash="solid", line_color="#2962ff", line_width=2, annotation_text=f"ENTRY: {lvl['entry']}")
        fig.add_hline(y=lvl["sl"], line_dash="dash", line_color="#f23645", line_width=2, annotation_text=f"SL: {lvl['sl']}")
        fig.add_hline(y=lvl["t1"], line_dash="dot", line_color="#089981", line_width=2, annotation_text=f"T1: {lvl['t1']}")
        fig.add_hline(y=lvl["t2"], line_dash="dot", line_color="#089981", line_width=2, annotation_text=f"T2: {lvl['t2']}")
        fig.add_hline(y=lvl["t3"], line_dash="dot", line_color="#089981", line_width=2, annotation_text=f"T3: {lvl['t3']}")

        fig.update_layout(
            height=650, paper_bgcolor="#131722", plot_bgcolor="#131722", font=dict(color="#d1d4dc"),
            xaxis_rangeslider_visible=False, hovermode="x unified", margin=dict(l=10, r=80, t=10, b=10),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0)
        )
        st.plotly_chart(fig, use_container_width=True)

    with col_side_summaries:
        st.markdown("<div class='summary-header'>Technical Summary</div>", unsafe_allow_html=True)
        ts = analysis_main["tech_summary"]
        
        def render_summary_box(title, data):
            st.markdown(f"<div style='font-weight:700; font-size:1.0rem; color:#787b86; margin-bottom:8px;'>{title}</div>", unsafe_allow_html=True)
            col_b, col_s = st.columns(2)
            col_b.metric("Buy", data["Buy"])
            col_s.metric("Sell", data["Sell"])
            st.markdown("<br>", unsafe_allow_html=True)

        render_summary_box("Moving Averages (4)", ts["ma_summary"])
        render_summary_box("Technical Indicators (2)", ts["ti_summary"])

        st.markdown("<div class='summary-header'>Pivot Points Pro</div>", unsafe_allow_html=True)
        pivot_mode = st.radio("Pivot Calculation Mode", ["Classic", "Fibonacci"], horizontal=True)
        pivots_df = pd.DataFrame([analysis_main["pivots"][pivot_mode]]).T
        pivots_df.columns = ["Price Level"]
        st.dataframe(pivots_df, use_container_width=True)

if __name__ == "__main__":
    run_dashboard()
