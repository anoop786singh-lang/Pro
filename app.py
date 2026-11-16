import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from settings import settings
from core.data_fetcher import fetch_all_timeframes
from core.signal_engine import evaluate_timeframe, compute_master_and_risk
st.set_page_config(page_title=settings.PROJECT_NAME, layout="wide")
st.sidebar.title(f"{settings.PROJECT_NAME} v{settings.VERSION}")
watchlist_map = {f"{item['label']} ({item['category']})": item["symbol"] for item in settings.CORE_WATCHLIST}
selected_label = st.sidebar.selectbox("Instrument", list(watchlist_map.keys()))
custom_symbol = st.sidebar.text_input("Or Custom Ticker", "")
symbol = custom_symbol.strip().upper() if custom_symbol.strip() else watchlist_map[selected_label]
exec_tf = st.sidebar.selectbox("Execution Timeframe", list(settings.TIMEFRAMES.keys()), index=1)
capital = st.sidebar.number_input("Trading Capital (INR)", value=settings.INITIAL_CAPITAL)
risk_pct = st.sidebar.slider("Max Risk Per Trade (%)", 0.5, 5.0, settings.MAX_RISK_PER_TRADE_PCT)
raw_data = fetch_all_timeframes(symbol)
mtf_results = {tf: evaluate_timeframe(df) for tf, df in raw_data.items()}
if mtf_results[exec_tf]["price"] == 0:
    st.error("Unable to fetch data. Verify ticker.")
    st.stop()
master = compute_master_and_risk(mtf_results, exec_tf, capital, risk_pct)
st.title(f"Institutional Terminal — {symbol}")
k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("LTP", f"{master['entry']:,.2f}")
k2.metric("Master Signal", master["master_signal"])
k3.metric("Confidence", f"{master['confidence_score']}%")
k4.metric("Recommended Qty", f"{master['position_qty']:,}")
k5.metric("Risk Amount", f"{master['risk_amount']:,.0f}")
st.divider()
col_matrix, col_risk = st.columns([1.3, 1])
with col_matrix:
    st.subheader("Multi-Timeframe Signal Matrix")
    matrix_rows = []
    for tf, res in mtf_results.items():
        matrix_rows.append({
            "Timeframe": tf, "Signal": res["signal"],
            "Confidence": f"{res['confidence']}%", "Score": res["score"],
            "RSI": res["rsi"], "ATR": res["atr"]
        })
    st.dataframe(pd.DataFrame(matrix_rows), use_container_width=True, hide_index=True)
with col_risk:
    st.subheader("Dynamic Targets & Risk Management")
    levels_df = pd.DataFrame([
        {"Level": "Entry Price", "Price": master["entry"]},
        {"Level": "Stop Loss", "Price": master["stop_loss"]},
        {"Level": "Target 1", "Price": master["target_1"]},
        {"Level": "Target 2", "Price": master["target_2"]},
        {"Level": "Target 3", "Price": master["target_3"]},
    ])
    st.dataframe(levels_df, use_container_width=True, hide_index=True)
chart_df = mtf_results[exec_tf]["df"].tail(120)
fig = go.Figure()
fig.add_trace(go.Candlestick(x=chart_df.index, open=chart_df["Open"], high=chart_df["High"], low=chart_df["Low"], close=chart_df["Close"], name="Price"))
fig.add_trace(go.Scatter(x=chart_df.index, y=chart_df["EMA_20"], name="EMA 20"))
fig.add_hline(y=master["entry"], line_dash="solid", annotation_text="ENTRY")
fig.add_hline(y=master["stop_loss"], line_dash="dash", line_color="red", annotation_text="SL")
fig.add_hline(y=master["target_1"], line_dash="dot", line_color="green", annotation_text="T1")
fig.add_hline(y=master["target_2"], line_dash="dot", line_color="green", annotation_text="T2")
fig.update_layout(height=500, xaxis_rangeslider_visible=False)
st.plotly_chart(fig, use_container_width=True)
