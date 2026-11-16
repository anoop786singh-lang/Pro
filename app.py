# --- config.py ---
class Config:
    WATCHLIST = [
        {"symbol": "^NSEI", "label": "NIFTY", "category": "Indices"},
        {"symbol": "^NSEBANK", "label": "BANKNIFTY", "category": "Indices"},
        {"symbol": "RELIANCE.NS", "label": "RELIANCE", "category": "Stocks"},
    ]
    TIMEFRAMES = ["15m", "1h", "1d"]

# --- data_module.py ---
import yfinance as yf
import pandas as pd
from datetime import datetime

class DataFetcher:
    @staticmethod
    def get_ohlcv(symbol: str, tf: str) -> pd.DataFrame:
        try:
            df = yf.download(symbol, period="60d", interval=tf, progress=False)
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            return df.dropna().copy()
        except Exception as e:
            print(f"Error fetching {symbol}: {e}")
            return pd.DataFrame()
# --- indicators_module.py ---
import pandas as pd
import numpy as np

class IndicatorCalculator:
    @staticmethod
    def compute_all(df: pd.DataFrame) -> pd.DataFrame:
        if df.empty:
            return df
        df = df.copy()
        
        # RSI
        delta = df["Close"].diff()
        gain = delta.clip(lower=0).ewm(alpha=1/14, min_periods=14, adjust=False).mean()
        loss = (-delta.clip(upper=0)).ewm(alpha=1/14, min_periods=14, adjust=False).mean()
        rs = gain / loss.replace(0, np.nan)
        df["RSI"] = 100 - (100 / (1 + rs))
        
        # Moving Averages
        df["EMA20"] = df["Close"].ewm(span=20, adjust=False).mean()
        df["EMA50"] = df["Close"].ewm(span=50, adjust=False).mean()
        
        # Bollinger Bands
        sma20 = df["Close"].rolling(20).mean()
        std20 = df["Close"].rolling(20).std()
        df["BB_Upper"] = sma20 + 2 * std20
        df["BB_Lower"] = sma20 - 2 * std20
        
        # ATR
        tr = np.maximum(df["High"] - df["Low"], 
                        np.maximum(abs(df["High"] - df["Close"].shift(1)), 
                                   abs(df["Low"] - df["Close"].shift(1))))
        df["ATR"] = tr.rolling(14).mean()
        
        return df.dropna()
# --- signals_module.py ---
import pandas as pd
import numpy as np

class SignalGenerator:
    @staticmethod
    def generate_signals(df: pd.DataFrame) -> dict:
        if df.empty:
            return {"signal": "NEUTRAL", "levels": {}}
        
        last = df.iloc[-1]
        close = float(last["Close"])
        rsi = float(last["RSI"])
        atr = float(last["ATR"])
        
        # Simple Logic for Demonstration
        if rsi < 30:
            signal = "STRONG BUY"
        elif rsi > 70:
            signal = "STRONG SELL"
        else:
            signal = "NEUTRAL"
            
        levels = {
            "entry": close,
            "sl": round(close - (1.5 * atr), 2),
            "target": round(close + (2.0 * atr), 2)
        }
        
        return {"signal": signal, "levels": levels}
# --- dashboard_module.py ---
import streamlit as st
import plotly.graph_objects as go
from config import Config
from data_module import DataFetcher
from indicators_module import IndicatorCalculator
from signals_module import SignalGenerator

def run_dashboard():
    st.title("Institutional Trading Terminal")
    symbol = st.selectbox("Select Asset", options=Config.WATCHLIST, format_func=lambda x: x["label"])
    tf = st.selectbox("Timeframe", options=Config.TIMEFRAMES)
    
    df = DataFetcher.get_ohlcv(symbol["symbol"], tf)
    if not df.empty:
        df = IndicatorCalculator.compute_all(df)
        analysis = SignalGenerator.generate_signals(df)
        
        st.metric("Signal", analysis["signal"])
        st.write("Trade Levels:", analysis["levels"])
        
        fig = go.Figure(data=[go.Candlestick(
            x=df.index, open=df['Open'], high=df['High'],
            low=df['Low'], close=df['Close']
        )])
        st.plotly_chart(fig)
# --- main.py ---
import streamlit as st
from dashboard_module import run_dashboard

if __name__ == "__main__":
    try:
        run_dashboard()
    except Exception as e:
        st.error(f"Application Error: {e}")
# --- signals_module.py ---
import pandas as pd
import numpy as np

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
    def evaluate_signal(df: pd.DataFrame, sr_level: float, is_support: bool) -> dict:
        if df.empty or len(df) < 26:
            c = float(df["Close"].iloc[-1]) if not df.empty else 100.0
            return {"signal": "NEUTRAL", "css": "sig-neutral", "score": 0.0, "levels": {"entry": c, "sl": c*0.98, "t1": c*1.015, "t2": c*1.03, "t3": c*1.05}}

        last = df.iloc[-1]
        c, rsi, ema9, ema20, ema50 = float(last["Close"]), float(last["RSI"]), float(last["EMA9"]), float(last["EMA20"]), float(last["EMA50"])
        macd, macd_sig = float(last["MACD"]), float(last["MACD_Signal"])
        candle = SignalGenerator.detect_candlestick_patterns(df)

        score = 0.0
        score += 1.0 if c > ema20 else -1.0
        score += 1.0 if ema20 > ema50 else -1.0
        score += 1.0 if macd > macd_sig else -1.0
        if rsi >= 60: score += 1.5
        elif rsi <= 40: score -= 1.5
        score += candle["bias"]

        dist = abs(c - sr_level)
        if dist < c * 0.005:
            score += 2.0 if is_support else -2.0

        levels = SignalGenerator.calculate_dynamic_levels(df, score)

        if score >= 4.0: sig = "STRONG BUY"
        elif score >= 1.5: sig = "BUY"
        elif score <= -4.0: sig = "STRONG SELL"
        elif score <= -1.8: sig = "SELL"
        else: sig = "NEUTRAL"

        return {"signal": sig, "css": f"sig-{sig.lower().replace(' ', '-')}", "score": score, "levels": levels, "pattern": candle["name"]}
