import streamlit as st
import yfinance as yf
import plotly.graph_objects as go
import pandas as pd
import numpy as np

# पेज कॉन्फ़िगरेशन
st.set_page_config(layout="wide", page_title="Professional Trading Terminal")

SECTOR_TICKERS = {
    "Banking & Finance": ["HDFCBANK.NS", "ICICIBANK.NS", "SBIN.NS"],
    "IT & Tech": ["TCS.NS", "INFY.NS", "HCLTECH.NS"],
    "Oil, Gas & Energy": ["RELIANCE.NS", "ONGC.NS", "NTPC.NS"],
    "Automobile": ["MARUTI.NS", "TATAMOTORS.NS"]
}

def add_institutional_indicators(df):
    # VWAP Calculation
    q = df['Volume'] * ((df['High'] + df['Low'] + df['Close']) / 3)
    df['VWAP'] = q.cumsum() / df['Volume'].cumsum()
    
    # 200 EMA
    df['EMA_200'] = df['Close'].ewm(span=200, adjust=False).mean()
    
    # Supply & Demand Zones
    df['Demand'] = df['Low'].rolling(window=30).min()
    df['Supply'] = df['High'].rolling(window=30).max()
    return df

def get_confluence_signal(df_small, df_large):
    if len(df_small) < 200 or len(df_large) < 50:
        return "WAITING FOR DATA", "#6c757d"
    
    df_s = add_institutional_indicators(df_small)
    df_l = add_institutional_indicators(df_large)
    
    curr_price = df_s['Close'].iloc[-1]
    vwap = df_s['VWAP'].iloc[-1]
    ema_large = df_l['EMA_200'].iloc[-1]
    major_trend = "BULLISH" if df_l['Close'].iloc[-1] > ema_large else "BEARISH"
    
    is_buy = (curr_price > vwap) and (curr_price > ema_large) and (major_trend == "BULLISH")
    is_sell = (curr_price < vwap) and (curr_price < ema_large) and (major_trend == "BEARISH")
    
    if is_buy:
        return f"INSTITUTIONAL BUY SIGNAL (Trend: {major_trend})", "green"
    elif is_sell:
        return f"INSTITUTIONAL SELL SIGNAL (Trend: {major_trend})", "red"
    else:
        return "NO CONFLUENCE (Price inside Demand/Supply)", "orange"

def create_institutional_chart(df, ticker):
    fig = go.Figure()
    fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name='Price'))
    fig.add_trace(go.Scatter(x=df.index, y=df['VWAP'], line=dict(color='blue', width=2), name='VWAP'))
    fig.add_trace(go.Scatter(x=df.index, y=df['EMA_200'], line=dict(color='orange', width=1.5), name='200 EMA'))
    
    fig.add_hline(y=df['Demand'].iloc[-1], line_dash="dash", line_color="green", annotation_text="Demand Zone")
    fig.add_hline(y=df['Supply'].iloc[-1], line_dash="dash", line_color= "red", annotation_text="Supply Zone")
    
    fig.update_layout(title=f"{ticker} Institutional Order Flow Analysis", template="plotly_dark", height=650)
    return fig

# UI Sidebar
st.sidebar.title("Scanner Control")
selected_sector = st.sidebar.selectbox("Select Sector:", list(SECTOR_TICKERS.keys()))
selected_stock = st.sidebar.selectbox("Select Stock:", SECTOR_TICKERS[selected_sector])

st.title("ProTerminal X - Institutional Grade Scanner")

# Data Fetching & Processing
if selected_stock:
    ticker_obj = yf.Ticker(selected_stock)
    df_small = ticker_obj.history(period="60d", interval="15m")
    df_large = ticker_obj.history(period="2y", interval="1d")
    
    df_s = add_institutional_indicators(df_small)
    
    # Signal Display
    text, color = get_confluence_signal(df_small, df_large)
    st.markdown(f"<h3 style='text-align: center; color: white; background-color: {color}; padding: 10px; border-radius: 5px;'>{text}</h3>", unsafe_allow_html=True)
    
    # Chart Display
    chart = create_institutional_chart(df_s, selected_stock)
    st.plotly_chart(chart, use_container_width=True)
