import pandas as pd
import yfinance as yf
import streamlit as st
from settings import settings

@st.cache_data(ttl=120, show_spinner=False)
def fetch_ohlcv(symbol: str, interval: str, period: str) -> pd.DataFrame:
    df = yf.download(symbol, interval=interval, period=period, progress=False, auto_adjust=True)
    if df is None or df.empty:
        return pd.DataFrame()
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df = df[["Open", "High", "Low", "Close", "Volume"]].dropna()
    return df

def fetch_all_timeframes(symbol: str) -> dict[str, pd.DataFrame]:
    data = {}
    for tf_label, cfg in settings.TIMEFRAMES.items():
        data[tf_label] = fetch_ohlcv(symbol, cfg["interval"], cfg["period"])
    return data
