import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import datetime
import sqlite3

# --- 1. CONFIGURATION ---
class Config:
    WATCHLIST = [
        {"symbol": "^NSEI", "label": "NIFTY", "category": "Indices"},
        {"symbol": "^NSEBANK", "label": "BANKNIFTY", "category": "Indices"},
        {"symbol": "^BSESN", "label": "SENSEX", "category": "Indices"},
        {"symbol": "RELIANCE.NS", "label": "RELIANCE", "category": "Stocks"},
        {"symbol": "HDFCBANK.NS", "label": "HDFCBANK", "category": "Stocks"},
        {"symbol": "ICICIBANK.NS", "label": "ICICIBANK", "category": "Stocks"},
    ]
    TIMEFRAMES = ["15m", "30m", "45m", "1h", "2h", "4h", "1d", "1wk", "1mo"]

# --- 2. DATA PIPELINE ---
class DataPipeline:
    def __init__(self, db_name="institutional_terminal.db"):
        self.db_name = db_name
        self.init_db()

    def init_db(self):
        with sqlite3.connect(self.db_name) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS historical_bars (
                    symbol TEXT, timestamp TEXT, open REAL, high REAL,
                    low REAL, close REAL, volume INTEGER,
                    PRIMARY KEY (symbol, timestamp)
                )
            """)

    def fetch_and_store(self, symbol, period="1y", interval="1h"):
        clean_sym = symbol.strip().replace("^", "")
        if not ("." in clean_sym or "NSE" in clean_sym or "BSE" in clean_sym):
            clean_sym += ".NS"
        try:
            df = yf.download(clean_sym, period=period, interval=interval, progress=False)
            if df.empty: return False
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            df = df.dropna()
            records = [
                (symbol, ts.strftime('%Y-%m-%d %H:%M:%S'), float(row['Open']),
                 float(row['High']), float(row['Low']), float(row['Close']), int(row['Volume']))
                for ts, row in df.iterrows()
            ]
            with sqlite3.connect(self.db_name) as conn:
                conn.executemany("""
                    INSERT OR REPLACE INTO historical_bars 
                    (symbol, timestamp, open, high, low, close, volume)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, records)
            return True
        except Exception:
            return False

# --- 3. QUANTITATIVE & BACKTESTING ENGINE ---
class QuantEngine:
    @staticmethod
    def compute_indicators(df: pd.DataFrame) -> pd.DataFrame:
        d = df.copy()
        c = d["close"]
        d["SMA20"] = c.rolling(window=20).mean()
        std20 = c.rolling(window=20).std()
        d["BB_Upper"] = d["SMA20"] + (std20 * 2)
        d["BB_Lower"] = d["SMA20"] - (std20 * 2)
        
        delta = c.diff()
        gain = delta.clip(lower=0).ewm(alpha=1/14, adjust=False).mean()
        loss = (-delta.clip(upper=0)).ewm(alpha=1/14, adjust=False).mean()
        rs = gain / loss.replace(0, np.nan)
        d["RSI"] = (100 - (100 / (1 + rs))).fillna(50)
        return d.ffill().bfill()

    @staticmethod
    def run_backtest(df: pd.DataFrame, initial_capital=100000.0) -> tuple[pd.DataFrame, dict]:
        d = df.copy()
        d['Signal'] = 0
        d.loc[d['close'] >= d['BB_Upper'], 'Signal'] = 1
        d.loc[d['close'] <= d['BB_Lower'], 'Signal'] = -1
        
        d['Position'] = d['Signal'].shift(1)
        d['Return'] = d['close'].pct_change()
        d['Strategy_Return'] = d['Position'] * d['Return']
        d['Portfolio_Value'] = initial_capital * (1 + d['Strategy_Return']).cumsum().fillna(initial_capital)
        
        total_return = (d['Portfolio_Value'].iloc[-1] - initial_capital) / initial_capital * 100
        win_rate = (d['Strategy_Return'] > 0).mean() * 100 if 'Strategy_Return' in d.columns else 0
        
        metrics = {
            "Total Return (%)": round(total_return, 2),
            "Win Rate (%)": round(win_rate, 2),
            "Final Portfolio Value (₹)": round(d['Portfolio_Value'].iloc[-1], 2)
        }
        return d, metrics

# --- 4. STREAMLIT UI INTEGRATION ---
def run_master_terminal():
    st.set_page_config(layout="wide", page_title="Institutional Trading Terminal Pro")
    
    st.markdown("""
        <style>
        .main { background-color: #0c0e15; }
        .stTabs [data-baseweb="tab-list"] { gap: 16px; }
        .stTabs [data-baseweb="tab"] { background-color: #161b22; border-radius: 6px; color: #c9d1d9; font-weight: 600; }
        .stTabs [aria-selected="true"] { background-color: #1f6feb !important; color: white !important; }
        .metric-card { background-color: #161b22; padding: 15px; border-radius: 8px; border: 1px solid #30363d; text-align: center; }
        .sig-strong-buy { color: #238636; font-weight: 800; background: rgba(43,158,88,0.1); padding: 4px 8px; border-radius: 4px; }
        .sig-strong-sell { color: #da3633; font-weight: 800; background: rgba(218,54,51,0.1); padding: 4px 8px; border-radius: 4px; }
        .sig-neutral { color: #8b949e; font-weight: 800; background: rgba(139,148,158,0.1); padding: 4px 8px; border-radius: 4px; }
        </style>
    """, unsafe_allow_html=True)

    if "sym" not in st.session_state: st.session_state.sym = "^NSEI"
    if "lbl" not in st.session_state: st.session_state.lbl = "NIFTY"
    if "tf" not in st.session_state: st.session_state.tf = "1h"

    pipeline = DataPipeline()

    with st.sidebar:
        st.header("Terminal Navigation")
        for item in Config.WATCHLIST:
            if st.button(f"{item['label']} ({item['category']})", use_container_width=True):
                st.session_state.sym = item["symbol"]
                st.session_state.lbl = item["label"]
                st.rerun()
        
        st.markdown("<hr>", unsafe_allow_html=True)
        st.session_state.tf = st.selectbox("Timeframe Matrix", Config.TIMEFRAMES, index=2)
        if st.button("Force Sync Terminal Cache", type="primary", use_container_width=True):
            with st.spinner("Synchronizing with institutional feeds..."):
                for t in Config.TIMEFRAMES:
                    pipeline.fetch_and_store(st.session_state.sym, period="1y", interval=t)
            st.rerun()

    # Data Fetching & Sync
    pipeline.fetch_and_store(st.session_state.sym, period="1y", interval=st.session_state.tf)
    with sqlite3.connect(pipeline.db_name) as conn:
        query = f"SELECT timestamp, open, high, low, close, volume FROM historical_bars WHERE symbol='{st.session_state.sym}' ORDER BY timestamp ASC"
        raw_df = pd.read_sql_query(query, conn, parse_dates=['timestamp'], index_col='timestamp')

    if raw_df.empty:
        st.error("Terminal synchronization failed. Displaying fallback telemetry.")
        return

    df = QuantEngine.compute_indicators(raw_df)
    backtest_df, metrics = QuantEngine.run_backtest(df)

    last = df.iloc[-1]
    c, sma, upper, lower, rsi = float(last['close']), float(last['SMA20']), float(last['BB_Upper']), float(last['BB_Lower']), float(last['RSI'])

    if c >= upper and rsi > 60: signal_html = "<span class='sig-strong-buy'>STRONG BUY</span>"
    elif c <= lower and rsi < 40: signal_html = "<span class='sig-strong-sell'>STRONG SELL</span>"
    else: signal_html = "<span class='sig-neutral'>NEUTRAL</span>"

    # Main Dashboard Layout
    st.title(f"Institutional Terminal: {st.session_state.lbl}")
    
    top_c1, top_c2, top_c3, top_c4 = st.columns(4)
    top_c1.metric("Live Execution Price", f"₹{c:,.2f}")
    top_c2.markdown(f"<div class='metric-card'><div>Quantitative Signal</div><br>{signal_html}</div>", unsafe_allow_html=True)
    top_c3.metric("RSI (14)", f"{rsi:.2f}")
    top_c4.metric("20 Period SMA", f"₹{sma:,.2f}")

    tab1, tab2, tab3 = st.tabs(["Execution Chart", "Automated Backtest Engine", "Raw Telemetry"])

    with tab1:
        fig = go.Figure()
        fig.add_trace(go.Candlestick(
            x=df.index, open=df['open'], high=df['high'], low=df['low'], close=df['close'],
            name="Price Action", increasing_line_color='#238636', decreasing_line_color='#da3633'
        ))
        fig.add_trace(go.Scatter(x=df.index, y=df['SMA20'], line=dict(color='#1f6feb', width=2), name="20 SMA"))
        fig.add_trace(go.Scatter(x=df.index, y=df['BB_Upper'], line=dict(color='rgba(255,255,255,0.3)', width=1, dash='dot'), name="Bollinger Upper"))
        fig.add_trace(go.Scatter(x=df.index, y=df['BB_Lower'], line=dict(color='rgba(255,255,255,0.3)', width=1, dash='dot'), fill='tonexty', name="Bollinger Lower"))

        fig.update_layout(height=650, template="plotly_dark", yaxis=dict(side="right"), xaxis_rangeslider_visible=False, margin=dict(l=10, r=20, t=20, b=20))
        st.plotly_chart(fig, use_container_width=True)

        fig_rsi = go.Figure()
        fig_rsi.add_trace(go.Scatter(x=df.index, y=df['RSI'], line=dict(color='#a371f7', width=2), name="RSI"))
        fig_rsi.add_hline(y=70, line_dash="dash", line_color="#da3633")
        fig_rsi.add_hline(y=30, line_dash="dash", line_color="#238636")
        fig_rsi.update_layout(height=250, template="plotly_dark", yaxis=dict(side="right"), xaxis_rangeslider_visible=False, margin=dict(l=10, r=20, t=20, b=20))
        st.plotly_chart(fig_rsi, use_container_width=True)

    with tab2:
        st.subheader("Strategy Backtest Performance")
        b_cols = st.columns(len(metrics))
        for i, (k, v) in enumerate(metrics.items()):
            b_cols[i].metric(k, v)

        fig_bt = go.Figure()
        fig_bt.add_trace(go.Scatter(x=backtest_df.index, y=backtest_df['Portfolio_Value'], line=dict(color='#238636', width=2), name="Portfolio Equity"))
        fig_bt.update_layout(height=500, template="plotly_dark", yaxis=dict(side="right"), title="Equity Curve (Initial Capital: ₹1,000,00")
        st.plotly_chart(fig_bt, use_container_width=True)

    with tab3:
        st.subheader("Synchronized Historical Bars")
        st.dataframe(df.tail(100), use_container_width=True)

if __name__ == "__main__":
    run_master_terminal()
