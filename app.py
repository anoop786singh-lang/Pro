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
        {"symbol": "RELIANCE.NS", "label": "RELIANCE", "category": "Stocks"},
    ]
    TIMEFRAMES = ["15m", "1h", "1d"]

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

# --- 3. DATA FETCHING MODULE ---
class DataFetcher:
    @staticmethod
    def get_ohlcv(symbol: str, tf: str) -> pd.DataFrame:
        db = DatabaseManager()
        cached_df = db.get_data(symbol, tf)
        if not cached_df.empty and (datetime.now() - cached_df.index[-1]).seconds < 3600:
            return cached_df

        try:
            df = yf.download(symbol, period="60d", interval=tf, progress=False)
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            df = df.dropna().copy()
            if not df.empty:
                db.save_data(symbol, tf, df)
            return df
        except Exception as e:
            st.warning(f"Network error for {symbol}, loading cached data.")
            return cached_df

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
        
        df["EMA9"] = df["Close"].ewm(span=9, adjust=False).mean()
        df["EMA20"] = df["Close"].ewm(span=20, adjust=False).mean()
        df["EMA50"] = df["Close"].ewm(span=50, adjust=False).mean()
        
        sma20 = df["Close"].rolling(20).mean()
        std20 = df["Close"].rolling(20).std()
        df["BB_Upper"] = sma20 + 2 * std20
        df["BB_Lower"] = sma20 - 2 * std20
        
        macdeMA12 = df["Close"].ewm(span=12, adjust=False).mean()
        macdEMA26 = df["Close"].ewm(span=26, adjust=False).mean()
        df["MACD"] = macdeMA12 - macdEMA26
        df["MACD_Signal"] = df["MACD"].ewm(span=9, adjust=False).mean()
        
        tr = np.maximum(df["High"] - df["Low"], 
                        np.maximum(abs(df["High"] - df["Close"].shift(1)), 
                                   abs(df["Low"] - df["Close"].shift(1))))
        df["ATR"] = tr.rolling(14).mean()
        return df.dropna()

# --- 5. SIGNAL & RISK MODULE ---
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
        if df.empty or len(df) < 4: return {"name": "None", "bias": 0}
        c0, c1, c2 = df.iloc[-1], df.iloc[-2], df.iloc[-3]

        def bar_stats(row):
            o, h, l, c = float(row["Open"]), float(row["High"]), float(row["Low"]), float(row["Close"])
            return o, h, l, c, abs(c - o), max(h - l, 1e-6), h - max(o, c), min(o, c) - l, c > o

        o0, h0, l0, cl0, b0, r0, uw0, lw0, bull0 = bar_stats(c0)
        o1, h1, l1, cl1, b1, r1, uw1, lw1, bull1 = bar_stats(c1)
        o2, h2, l2, cl2, b2, r2, uw2, lw2, bull2 = bar_stats(c2)

        if (not bull2) and b2 > r2*0.5 and b1 < r1*0.35 and bull0 and b0 > r0*0.5 and cl0 > (o2+cl2)/2: return {"name": "Morning Star", "bias": 2}
        if bull2 and b2 > r2*0.5 and b1 < r1*0.35 and (not bull0) and b0 > r0*0.5 and cl0 < (o2+cl2)/2: return {"name": "Evening Star", "bias": -2}
        if (not bull1) and bull0 and cl0 >= o1 and o0 <= cl1 and b0 > b1*1.05: return {"name": "Bullish Engulfing", "bias": 2}
        if bull1 and (not bull0) and cl0 <= o1 and o0 >= cl1 and b0 > b1*1.05: return {"name": "Bearish Engulfing", "bias": -2}
        if lw0 >= b0*2.0 and uw0 <= b0*0.4 and b0 > r0*0.12: return {"name": "Hammer", "bias": 1}
        if uw0 >= b0*2.0 and lw0 <= b0*0.4 and b0 > r0*0.12: return {"name": "Shooting Star", "bias": -1}
        if b0 <= r0*0.10: return {"name": "Doji Indecision", "bias": 0}

        return {"name": "None", "bias": 0}

    @staticmethod
    def evaluate_signal(df: pd.DataFrame) -> dict:
        if df.empty or len(df) < 26:
            c = float(df["Close"].iloc[-1]) if not df.empty else 100.0
            return {"signal": "NEUTRAL", "css": "sig-neutral", "score": 0.0, "levels": {"entry": c, "sl": c*0.98, "t1": c*1.015, "t2": c*1.03, "t3": c*1.05}, "pattern": "—"}

        last = df.iloc[-1]
        c, rsi, ema20, ema50 = float(last["Close"]), float(last["RSI"]), float(last["EMA20"]), float(last["EMA50"])
        macd, macd_sig = float(last["MACD"]), float(last["MACD_Signal"])
        candle = SignalGenerator.detect_candlestick_patterns(df)

        score = 0.0
        score += 1.0 if c > ema20 else -1.0
        score += 1.0 if ema20 > ema50 else -1.0
        score += 1.0 if macd > macd_sig else -1.0
        if rsi >= 60: score += 1.5
        elif rsi <= 40: score -= 1.5
        score += candle["bias"]

        levels = SignalGenerator.calculate_dynamic_levels(df, score)

        if score >= 4.0: sig = "STRONG BUY"
        elif score >= 1.5: sig = "BUY"
        elif score <= -4.0: sig = "STRONG SELL"
        elif score <= -1.8: sig = "SELL"
        else: sig = "NEUTRAL"

        return {"signal": sig, "css": f"sig-{sig.lower().replace(' ', '-')}", "score": score, "levels": levels, "pattern": candle["name"]}

class RiskManager:
    @staticmethod
    def calculate_position_size(account_balance: float, risk_per_trade_pct: float, entry_price: float, stop_loss: float) -> int:
        risk_amount = account_balance * (risk_per_trade_pct / 100.0)
        risk_per_share = abs(entry_price - stop_loss)
        return int(risk_amount // risk_per_share) if risk_per_share != 0 else 0

# --- 6. DASHBOARD MODULE ---
def run_dashboard():
    st.set_page_config(page_title="Institutional Trading Terminal", layout="wide")
    
    st.markdown("""
    <style>
        .stApp { background-color: #131722; color: #d1d4dc; }
        .sig-strong-buy { background-color: #089981; color: white; padding: 4px 8px; border-radius: 4px; font-weight: 700; }
        .sig-buy { background-color: rgba(8, 153, 129, 0.2); color: #089981; border: 1px solid #089981; padding: 4px 8px; border-radius: 4px; font-weight: 700; }
        .sig-neutral { background-color: rgba(120, 123, 134, 0.2); color: #d1d4dc; border: 1px solid #787b86; padding: 4px 8px; border-radius: 4px; font-weight: 700; }
        .sig-sell { background-color: rgba(242, 54, 69, 0.2); color: #f23645; border: 1px solid #f23645; padding: 4px 8px; border-radius: 4px; font-weight: 700; }
        .sig-strong-sell { background-color: #f23645; color: white; padding: 4px 8px; border-radius: 4px; font-weight: 700; }
    </style>
    """, unsafe_allow_html=True)

    st.title("Institutional Trading Terminal")
    symbol = st.selectbox("Select Asset", options=Config.WATCHLIST, format_func=lambda x: x["label"])
    tf = st.selectbox("Timeframe", options=Config.TIMEFRAMES)
    
    df = DataFetcher.get_ohlcv(symbol["symbol"], tf)
    if not df.empty:
        df = IndicatorCalculator.compute_all(df)
        analysis = SignalGenerator.evaluate_signal(df)
        lvl = analysis["levels"]
        
        c1, c2, c3 = st.columns(3)
        c1.metric("Signal", analysis["signal"])
        c2.metric("Pattern Detected", analysis["pattern"])
        c3.metric("Entry Level", lvl["entry"])
        
        st.write("Dynamic Targets:", lvl)

        # Risk Management Input
        bal = st.number_input("Account Balance (₹)", value=100000)
        risk_pct = st.slider("Risk Per Trade (%)", 0.5, 5.0, 1.0)
        pos_size = RiskManager.calculate_position_size(bal, risk_pct, lvl["entry"], lvl["sl"])
        st.info(f"Recommended Position Size: {pos_size} shares")

        fig = go.Figure(data=[go.Candlestick(
            x=df.index, open=df['Open'], high=df['High'],
            low=df['Low'], close=df['Close']
        )])
        fig.add_hline(y=lvl["entry"], line_color="blue", annotation_text="Entry")
        fig.add_hline(y=lvl["sl"], line_color="red", annotation_text="SL")
        fig.add_trace(go.Scatter(x=df.index, y=df['EMA20'], line=dict(color='orange'), name="EMA 20"))
        
        fig.update_layout(height=600, paper_bgcolor="#131722", plot_bgcolor="#131722", font=dict(color="#d1d4dc"))
        st.plotly_chart(fig, use_container_width=True)

if __name__ == "__main__":
    run_dashboard()
