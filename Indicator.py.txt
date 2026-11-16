import pandas as pd
import numpy as np

class QuantEngine:
    @staticmethod
    def compute_indicators(df: pd.DataFrame) -> pd.DataFrame:
        if df.empty:
            return df
        d = df.copy()
        c = d['close']
        
        # 1. 20 Period Moving Average
        d['SMA20'] = c.rolling(window=20).mean()
        
        # 2. Bollinger Bands (20 SMA, 2 Std Dev)
        std20 = c.rolling(window=20).std()
        d['BB_Upper'] = d['SMA20'] + (std20 * 2)
        d['BB_Lower'] = d['SMA20'] - (std20 * 2)
        
        # 3. RSI (14 Period)
        delta = c.diff()
        gain = delta.clip(lower=0).ewm(alpha=1/14, adjust=False).mean()
        loss = (-delta.clip(upper=0)).ewm(alpha=1/14, adjust=False).mean()
        rs = gain / loss.replace(0, np.nan)
        d['RSI'] = (100 - (100 / (1 + rs))).fillna(50)
        
        return d.ffill().bfill()

    @staticmethod
    def generate_signals(df: pd.DataFrame) -> str:
        if df.empty or 'RSI' not in df.columns:
            return "NEUTRAL"
        
        last = df.iloc[-1]
        c = last['close']
        bb_u = last['BB_Upper']
        bb_l = last['BB_Lower']
        rsi = last['RSI']
        
        if c >= bb_u and rsi > 60:
            return "STRONG_BUY"
        elif c <= bb_l and rsi < 40:
            return "STRONG_SELL"
        else:
            return "NEUTRAL"

quant_engine = QuantEngine()
