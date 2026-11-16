import concurrent.futures
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st
import yfinance as yf

# -----------------------------------------------------------------------------
# PAGE CONFIGURATION & SESSION STATE
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="Market Master Pro | MTF Terminal",
    layout="wide",
    initial_sidebar_state="collapsed",
)

if "selected_ticker" not in st.session_state:
    st.session_state.selected_ticker = "RELIANCE"
if "selected_tf" not in st.session_state:
    st.session_state.selected_tf = "1D"
if "focus_mode" not in st.session_state:
    st.session_state.focus_mode = False

# -----------------------------------------------------------------------------
# CSS: STICKY TOP HEADER, FLOATING IN-CHART CONTROLS & PINCH-ZOOM SUPPORT
# -----------------------------------------------------------------------------
focus_css = (
    """
    section[data-testid="stSidebar"] { display: none !important; }
    header[data-testid="stHeader"] { display: none !important; }
    .block-container { padding-top: 0.4rem !important; padding-bottom: 0.4rem !important; max-width: 100% !important; }
    """
    if st.session_state.focus_mode
    else """
    .block-container { padding-top: 1.0rem; padding-bottom: 1rem; }
    """
)

st.markdown(
    f"""
    <style>
        {focus_css}
        div[data-testid="stMetricValue"] {{ font-size: 1.35rem; font-weight: 700; }}
        .signal-badge {{
            padding: 5px 12px;
            border-radius: 6px;
            font-weight: 700;
            text-align: center;
            display: inline-block;
        }}
        div[data-testid="stVerticalBlock"] > div:has(div.sticky-anchor) {{
            position: sticky;
            top: { '0px' if st.session_state.focus_mode else '2.8rem' };
            z-index: 999;
            background-color: var(--background-color, #ffffff);
            padding-top: 6px;
            padding-bottom: 8px;
            border-bottom: 1px solid rgba(128, 128, 128, 0.25);
        }}
        /* Floating overlay bar positioned directly over the top-left of the Plotly chart */
        div[data-testid="stVerticalBlock"] > div:has(div.chart-overlay-anchor) {{
            position: relative;
            z-index: 50;
            margin-bottom: -58px;
            padding-left: 14px;
            padding-top: 10px;
            pointer-events: none;
        }}
        div[data-testid="stVerticalBlock"] > div:has(div.chart-overlay-anchor) div[data-testid="stSelectbox"],
        div[data-testid="stVerticalBlock"] > div:has(div.chart-overlay-anchor) .floating-chart-badge {{
            pointer-events: auto;
        }}
        div[data-testid="stVerticalBlock"] > div:has(div.chart-overlay-anchor) div[data-baseweb="select"] > div {{
            background-color: rgba(255, 255, 255, 0.92) !important;
            backdrop-filter: blur(4px);
            border: 1px solid rgba(49, 51, 63, 0.25) !important;
            min-height: 32px !important;
            height: 32px !important;
            font-size: 0.82rem !important;
            font-weight: 600 !important;
        }}
        .floating-chart-badge {{
            display: inline-flex;
            align-items: center;
            height: 32px;
            padding: 0 10px;
            border-radius: 6px;
            color: #ffffff;
            font-size: 0.78rem;
            font-weight: 700;
            white-space: nowrap;
            box-shadow: 0 1px 4px rgba(0, 0, 0, 0.15);
        }}
        /* Route touch pinch-zoom & pan gestures directly to Plotly canvas */
        .js-plotly-plot .plotly .nsewdrag,
        .js-plotly-plot .plotly .drag {{
            touch-action: none !important;
        }}
    </style>
    """,
    unsafe_allow_html=True,
)

# -----------------------------------------------------------------------------
# TOP 200 NSE EQUITY UNIVERSE & MULTI-TIMEFRAME CONFIGURATION
# -----------------------------------------------------------------------------
TOP_200_SYMBOLS = [
    "RELIANCE", "TCS", "HDFCBANK", "BHARTIARTL", "ICICIBANK", "INFY", "SBIN", "HINDUNILVR",
    "ITC", "LT", "HCLTECH", "BAJFINANCE", "SUNPHARMA", "MARUTI", "M&M", "KOTAKBANK",
    "AXISBANK", "TITAN", "ONGC", "ADANIENT", "NTPC", "TATAMOTORS", "ULTRACEMCO", "POWERGRID",
    "BAJAJFINSV", "ADANIPORTS", "COALINDIA", "ASIANPAINT", "WIPRO", "DMART", "HAL", "SIEMENS",
    "TRENT", "BEL", "JSWSTEEL", "NESTLEIND", "IOC", "VBL", "DLF", "IRFC", "TATASTEEL",
    "JIOFIN", "ZOMATO", "GRASIM", "LTIM", "TECHM", "PIDILITIND", "HINDZINC", "SBILIFE",
    "PFC", "ADANIPOWER", "RECLTD", "ADANIGREEN", "HDFCLIFE", "INDIGO", "BANKBARODA", "GAIL",
    "AMBUJACEM", "BPCL", "CIPLA", "EICHERMOT", "DIVISLAB", "ABB", "BRITANNIA", "PNB",
    "CHOLAFIN", "TVSMOTOR", "VEDL", "SHREECEM", "TATAPOWER", "BAJAJ-AUTO", "GODREJCP", "HAVELLS",
    "LODHA", "MANKIND", "DRREDDY", "UNIONBANK", "CANBK", "APOLLOHOSP", "CGPOWER", "DABUR",
    "HEROMOTOCO", "ICICIPRULI", "INDHOTEL", "JINDALSTEL", "MARICO", "MAXHEALTH", "MOTHERSON",
    "NAUKRI", "NHPC", "OBEROIRLTY", "OFSS", "PERSISTENT", "POLYCAB", "SHRIRAMFIN", "SOLARINDS",
    "SRF", "SUNDARMFIN", "SUPREMEIND", "TATACONSUM", "TATAELXSI", "TORNTPHARM", "TORNTPR",
    "TRIDENT", "UBL", "UNITDSPR", "UPL", "VOLTAS", "YESBANK", "ZYDUSLIFE", "ACC", "ALKEM",
    "ASHOKLEY", "ASTRAL", "ATUL", "AUBANK", "AUROPHARMA", "BALKRISIND", "BANDHANBNK", "BATAINDIA",
    "BERGEPAINT", "BHARATFORG", "BHEL", "BIOCON", "BOSCHLTD", "BSE", "CDSL", "CENTRALBK",
    "CESC", "CHAMBLFERT", "COFORGE", "COLPAL", "CONCOR", "COROMANDEL", "CROMPTON", "CUMMINSIND",
    "DALBHARAT", "DEEPAKNTR", "DELHIVERY", "DEVYANI", "DIXON", "ESCORTS", "EXIDEIND", "FEDERALBNK",
    "FORTIS", "GLAND", "GLAXO", "GMRINFRA", "GODREJPROP", "GRANULES", "GUJGASLTD", "HDFCAMC",
    "HINDPETRO", "HONAUT", "IDFCFIRSTB", "IGL", "INDIANB", "INDUSTOWER", "IPCALAB", "IRCTC",
    "ISEC", "JKCEMENT", "JSL", "JSWENERGY", "JUBLFOOD", "KALYANKJIL", "KEI", "KPITTECH",
    "L&TFH", "LALPATHLAB", "LAURUSLABS", "LICHSGFIN", "LICI", "LTTS", "LUPIN", "M&MFIN",
    "MAHABANK", "MAZDOCK", "MCX", "METROBRAND", "MFSL", "MGL", "MPHASIS", "MRF", "MUTHOOTFIN",
    "NATIONALUM", "NAVINFLUOR", "NMDC", "NUVOCO", "OIL", "PAGEIND", "PATANJALI", "PAYTM",
    "PETRONET", "PIIND", "POLICYBZR", "POONAWALLA", "PRESTIGE", "PVRINOX", "RAMCOCEM", "RBLBANK",
]
TOP_200_UNIVERSE = {sym: f"{sym}.NS" for sym in TOP_200_SYMBOLS[:200]}

# (fetch_interval, fetch_period, resample_rule_or_None)
TIMEFRAME_MAP = {
    "15M": ("15m", "15d", None),
    "30M": ("30m", "30d", None),
    "45M": ("15m", "30d", "45min"),
    "1H": ("1h", "60d", None),
    "2H": ("1h", "90d", "2h"),
    "4H": ("1h", "180d", "4h"),
    "1D": ("1d", "max", None),
    "1WK": ("1wk", "max", None),
    "1MO": ("1mo", "max", None),
}

TF_WEIGHTS = {"15M": 1, "30M": 1, "45M": 1, "1H": 2, "2H": 2, "4H": 2, "1D": 3, "1WK": 3, "1MO": 4}
MAX_POSSIBLE_WEIGHTED_SCORE = sum(3 * w for w in TF_WEIGHTS.values())  # 63


# -----------------------------------------------------------------------------
# TECHNICAL INDICATORS, CONFLUENCE & ACCURACY ENGINE
# -----------------------------------------------------------------------------
def resample_ohlcv(df: pd.DataFrame, rule: str) -> pd.DataFrame:
    agg = {"Open": "first", "High": "max", "Low": "min", "Close": "last", "Volume": "sum"}
    return df.resample(rule).agg(agg).dropna(subset=["Open", "Close"])


def compute_indicators(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    df["SMA20"] = df["Close"].rolling(20).mean()
    df["SMA50"] = df["Close"].rolling(50).mean()
    std20 = df["Close"].rolling(20).std()
    df["BB_Upper"] = df["SMA20"] + 2 * std20
    df["BB_Lower"] = df["SMA20"] - 2 * std20

    delta = df["Close"].diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = (-delta.clip(upper=0)).rolling(14).mean()
    rs = gain / loss.replace(0, np.nan)
    df["RSI"] = 100 - (100 / (1 + rs))

    high_low = df["High"] - df["Low"]
    high_close = (df["High"] - df["Close"].shift()).abs()
    low_close = (df["Low"] - df["Close"].shift()).abs()
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    df["ATR"] = tr.rolling(14).mean()

    df["Vol_SMA20"] = df["Volume"].rolling(20).mean()
    df["Res20"] = df["High"].rolling(20).max().shift(1)
    df["Sup20"] = df["Low"].rolling(20).min().shift(1)
    return df


def compute_historical_hit_rate(df: pd.DataFrame) -> float:
    if df is None or len(df) < 40:
        return 55.0
    sub = df.dropna(subset=["SMA20", "RSI", "Close"]).copy()
    if len(sub) < 20:
        return 55.0
    bull_cond = (sub["Close"] > sub["SMA20"]) & (sub["RSI"] >= 55)
    bear_cond = (sub["Close"] < sub["SMA20"]) & (sub["RSI"] <= 45)
    fwd_ret = sub["Close"].shift(-3) - sub["Close"]

    bull_hits = ((bull_cond) & (fwd_ret > 0)).sum()
    bear_hits = ((bear_cond) & (fwd_ret < 0)).sum()
    total_trigs = bull_cond.sum() + bear_cond.sum()
    if total_trigs == 0:
        return 55.0
    return round(float((bull_hits + bear_hits) / total_trigs) * 100.0, 1)


def evaluate_signal(df: pd.DataFrame) -> tuple[str, int, float, float]:
    if df is None or len(df) < 25:
        return "NEUTRAL", 0, np.nan, 50.0

    last = df.iloc[-1]
    prev = df.iloc[-2]
    score = 0
    factors_aligned = 0
    total_factors = 6

    if last["Close"] > last["SMA20"]:
        score += 1
        factors_aligned += 1
    elif last["Close"] < last["SMA20"]:
        score -= 1
        factors_aligned += 1

    if pd.notna(last.get("SMA50")):
        if last["Close"] > last["SMA50"] and score > 0:
            factors_aligned += 1
        elif last["Close"] < last["SMA50"] and score < 0:
            factors_aligned += 1

    rsi_val = float(last["RSI"]) if pd.notna(last["RSI"]) else 50.0
    if rsi_val >= 58:
        score += 1
        if score > 0:
            factors_aligned += 1
    elif rsi_val <= 42:
        score -= 1
        if score < 0:
            factors_aligned += 1

    if last["Close"] > last["BB_Upper"] or (prev["Close"] < prev["BB_Lower"] and last["Close"] > last["BB_Lower"]):
        score += 1
        factors_aligned += 1
    elif last["Close"] < last["BB_Lower"] or (prev["Close"] > prev["BB_Upper"] and last["Close"] < last["BB_Lower"]):
        score -= 1
        factors_aligned += 1

    if pd.notna(last.get("Vol_SMA20")) and last["Vol_SMA20"] > 0 and last["Volume"] >= last["Vol_SMA20"]:
        factors_aligned += 1

    if last["Close"] > last["Open"] and (last["Close"] > prev["High"] or (pd.notna(last.get("Res20")) and last["Close"] > last["Res20"])):
        score += 1
        factors_aligned += 1
    elif last["Close"] < last["Open"] and (last["Close"] < prev["Low"] or (pd.notna(last.get("Sup20")) and last["Close"] < last["Sup20"])):
        score -= 1
        factors_aligned += 1

    tech_conf = (factors_aligned / total_factors) * 100.0
    hist_acc = compute_historical_hit_rate(df)
    accuracy = round(min(97.5, max(42.0, 0.65 * tech_conf + 0.35 * hist_acc)), 1)

    if score >= 3:
        sig = "STRONG BUY"
    elif score >= 1:
        sig = "BUY"
    elif score <= -3:
        sig = "STRONG SELL"
    elif score <= -1:
        sig = "SELL"
    else:
        sig = "NEUTRAL"
        accuracy = round(min(65.0, accuracy), 1)

    return sig, score, round(rsi_val, 2), accuracy


def calculate_trade_levels(df: pd.DataFrame, signal: str) -> dict:
    last = df.iloc[-1]
    entry = float(last["Close"])
    atr = float(last["ATR"]) if pd.notna(last["ATR"]) and last["ATR"] > 0 else entry * 0.015

    if "SELL" in signal:
        sl = round(entry + 1.5 * atr, 2)
        t1 = round(entry - 2.0 * atr, 2)
        t2 = round(entry - 3.5 * atr, 2)
    else:
        sl = round(entry - 1.5 * atr, 2)
        t1 = round(entry + 2.0 * atr, 2)
        t2 = round(entry + 3.5 * atr, 2)

    return {"entry": round(entry, 2), "sl": sl, "t1": t1, "t2": t2}


# -----------------------------------------------------------------------------
# BATCHED BULK DOWNLOAD & TOP 200 -> TOP 50 SCANNER ENGINE
# -----------------------------------------------------------------------------
@st.cache_data(ttl=600, show_spinner=False)
def bulk_download_universe_tf(tf_label: str) -> dict[str, pd.DataFrame]:
    interval, period, resample_rule = TIMEFRAME_MAP[tf_label]
    scan_period = {"15M": "15d", "30M": "30d", "45M": "30d", "1H": "60d", "2H": "60d", "4H": "90d", "1D": "2y", "1WK": "5y", "1MO": "10y"}[tf_label]
    symbols_list = list(TOP_200_UNIVERSE.values())

    raw = yf.download(
        tickers=symbols_list,
        interval=interval,
        period=scan_period,
        group_by="ticker",
        threads=True,
        progress=False,
        auto_adjust=True,
    )

    result = {}
    if raw is None or raw.empty:
        return result

    for name, sym in TOP_200_UNIVERSE.items():
        try:
            if isinstance(raw.columns, pd.MultiIndex):
                if sym not in raw.columns.get_level_values(0):
                    continue
                sub = raw[sym].dropna(how="all")
            else:
                sub = raw.dropna(how="all")

            if sub.empty or len(sub) < 25:
                continue
            if resample_rule:
                sub = resample_ohlcv(sub, resample_rule)
            result[name] = compute_indicators(sub)
        except Exception:
            continue
    return result


@st.cache_data(ttl=600, show_spinner="Scanning Top 200 NSE stocks across 9 timeframes...")
def scan_top_50_opportunities() -> pd.DataFrame:
    tf_data_map = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = {executor.submit(bulk_download_universe_tf, tf): tf for tf in TIMEFRAME_MAP.keys()}
        for fut in concurrent.futures.as_completed(futures):
            tf_name = futures[fut]
            try:
                tf_data_map[tf_name] = fut.result()
            except Exception:
                tf_data_map[tf_name] = {}

    rows = []
    for name, symbol in TOP_200_UNIVERSE.items():
        tf_signals = {}
        weighted_score = 0
        acc_list = []
        daily_df = tf_data_map.get("1D", {}).get(name)
        daily_rsi = np.nan

        for tf_label in TIMEFRAME_MAP.keys():
            df = tf_data_map.get(tf_label, {}).get(name)
            sig, sc, rsi_val, acc = evaluate_signal(df)
            tf_signals[tf_label] = sig
            weighted_score += sc * TF_WEIGHTS[tf_label]
            acc_list.append(acc)
            if tf_label == "1D":
                daily_rsi = rsi_val

        if daily_df is None or daily_df.empty:
            continue

        confluence_score = round((weighted_score / MAX_POSSIBLE_WEIGHTED_SCORE) * 100.0, 1)
        abs_strength = abs(confluence_score)

        if weighted_score >= 22:
            overall = "STRONG BUY"
        elif weighted_score >= 7:
            overall = "BUY"
        elif weighted_score <= -22:
            overall = "STRONG SELL"
        elif weighted_score <= -7:
            overall = "SELL"
        else:
            overall = "NEUTRAL"

        overall_acc = round(float(np.mean(acc_list)), 1) if acc_list else 50.0
        levels = calculate_trade_levels(daily_df, overall)
        ltp = levels["entry"]

        rows.append(
            {
                "Stock": name,
                "Symbol": symbol,
                "LTP": ltp,
                "Confluence": confluence_score,
                "AbsStrength": abs_strength,
                "15M": tf_signals["15M"],
                "30M": tf_signals["30M"],
                "45M": tf_signals["45M"],
                "1H": tf_signals["1H"],
                "2H": tf_signals["2H"],
                "4H": tf_signals["4H"],
                "1D": tf_signals["1D"],
                "1WK": tf_signals["1WK"],
                "1MO": tf_signals["1MO"],
                "Master Signal": overall,
                "Accuracy %": overall_acc,
                "RSI (14)": daily_rsi,
                "Entry": levels["entry"],
                "SL": levels["sl"],
                "T1": levels["t1"],
                "T2": levels["t2"],
            }
        )

    full_df = pd.DataFrame(rows)
    if full_df.empty:
        return full_df

    actionable = full_df[full_df["Master Signal"] != "NEUTRAL"].copy()
    if len(actionable) >= 50:
        top50 = actionable.sort_values(by=["AbsStrength", "Accuracy %"], ascending=[False, False]).head(50)
    else:
        top50 = full_df.sort_values(by=["AbsStrength", "Accuracy %"], ascending=[False, False]).head(50)

    top50 = top50.drop(columns=["AbsStrength"]).reset_index(drop=True)
    top50.insert(0, "Rank", range(1, len(top50) + 1))
    return top50


@st.cache_data(ttl=300, show_spinner=False)
def fetch_ohlcv(symbol: str, tf_label: str) -> pd.DataFrame:
    interval, period, resample_rule = TIMEFRAME_MAP[tf_label]
    df = yf.download(symbol, interval=interval, period=period, progress=False, auto_adjust=True)
    if df.empty:
        return df
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    if resample_rule:
        df = resample_ohlcv(df, resample_rule)
    return compute_indicators(df)


def style_matrix(df: pd.DataFrame):
    def color_signal(val):
        if val == "STRONG BUY":
            return "background-color: #0f5132; color: #ffffff; font-weight: 700;"
        if val == "BUY":
            return "background-color: #198754; color: #ffffff; font-weight: 600;"
        if val == "STRONG SELL":
            return "background-color: #842029; color: #ffffff; font-weight: 700;"
        if val == "SELL":
            return "background-color: #dc3545; color: #ffffff; font-weight: 600;"
        if val == "NEUTRAL":
            return "background-color: #e9ecef; color: #495057;"
        return ""

    signal_cols = list(TIMEFRAME_MAP.keys()) + ["Master Signal"]
    return (
        df.style.map(color_signal, subset=signal_cols)
        .format(
            {
                "LTP": "{:,.2f}",
                "Confluence": "{:+.1f}%",
                "Accuracy %": "{:.1f}%",
                "RSI (14)": "{:.2f}",
                "Entry": "{:,.2f}",
                "SL": "{:,.2f}",
                "T1": "{:,.2f}",
                "T2": "{:,.2f}",
            },
            na_rep="-",
        )
    )


# -----------------------------------------------------------------------------
# FULL-PAGE MODAL DIALOG FOR EXCEL-LIKE TOP 50 MATRIX
# -----------------------------------------------------------------------------
@st.dialog("Top 50 MTF Opportunities (Scanned from Top 200 Stocks)", width="large")
def open_full_page_matrix(matrix_df: pd.DataFrame):
    f1, f2, f3 = st.columns([2, 2, 3])
    with f1:
        sig_filter = st.multiselect(
            "Filter Master Signal",
            ["STRONG BUY", "BUY", "SELL", "STRONG SELL", "NEUTRAL"],
            default=[],
        )
    with f2:
        search_txt = st.text_input("Search Stock", placeholder="e.g., RELIANCE, HAL")
    with f3:
        st.caption("Ranked by Multi-Timeframe Confluence Strength. Click any row to load its chart.")

    filtered = matrix_df.copy()
    if sig_filter:
        filtered = filtered[filtered["Master Signal"].isin(sig_filter)]
    if search_txt:
        filtered = filtered[filtered["Stock"].str.contains(search_txt.strip().upper(), na=False)]

    display_df = filtered.drop(columns=["Symbol"]).reset_index(drop=True)
    selection = st.dataframe(
        style_matrix(display_df),
        use_container_width=True,
        height=620,
        hide_index=True,
        on_select="rerun",
        selection_mode="single-row",
    )

    if selection and selection.selection.rows:
        chosen_idx = selection.selection.rows[0]
        chosen_stock = display_df.iloc[chosen_idx]["Stock"]
        if chosen_stock != st.session_state.selected_ticker:
            st.session_state.selected_ticker = chosen_stock
            st.rerun()


# -----------------------------------------------------------------------------
# RUN SCANNER & SIDEBAR TOP 50 WATCHLIST
# -----------------------------------------------------------------------------
matrix_df = scan_top_50_opportunities()
active_universe_names = matrix_df["Stock"].tolist() if not matrix_df.empty else list(TOP_200_UNIVERSE.keys())
if st.session_state.selected_ticker not in TOP_200_UNIVERSE:
    st.session_state.selected_ticker = active_universe_names[0]

capital = 100000.0
risk_pct = 1.0

with st.sidebar:
    st.subheader("Risk & Capital Settings")
    capital = st.number_input("Trading Capital", min_value=1000.0, value=100000.0, step=5000.0)
    risk_pct = st.slider("Risk per Trade (%)", min_value=0.25, max_value=5.0, value=1.0, step=0.25)

    st.divider()
    st.subheader("Top 50 MTF Watchlist")
    if st.button("Rescan Top 200 Stocks", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

    if not matrix_df.empty:
        for _, row in matrix_df.iterrows():
            stock_name = row["Stock"]
            msig = row["Master Signal"]
            conf_val = row["Confluence"]
            badge = "🟢" if "BUY" in msig else ("🔴" if "SELL" in msig else "⚪")
            btn_type = "primary" if stock_name == st.session_state.selected_ticker else "secondary"
            if st.button(
                f"#{int(row['Rank'])} {badge} {stock_name} ({conf_val:+.0f}%)",
                key=f"wl_{stock_name}",
                use_container_width=True,
                type=btn_type,
            ):
                st.session_state.selected_ticker = stock_name
                st.rerun()


# -----------------------------------------------------------------------------
# PERSISTENT STICKY TOP NAVIGATION & INTEGRATED CHART CONTROLS
# -----------------------------------------------------------------------------
dropdown_tickers = (
    active_universe_names
    if st.session_state.selected_ticker in active_universe_names
    else [st.session_state.selected_ticker] + active_universe_names
)
curr_idx = dropdown_tickers.index(st.session_state.selected_ticker)
tf_keys = list(TIMEFRAME_MAP.keys())

sticky_header = st.container()
with sticky_header:
    st.markdown('<div class="sticky-anchor"></div>', unsafe_allow_html=True)
    nav_prev, nav_sym, nav_next, nav_tf, nav_price, nav_sig, nav_mat, nav_focus = st.columns(
        [0.45, 1.8, 0.45, 1.05, 1.35, 1.65, 1.55, 1.35]
    )

    with nav_prev:
        if st.button("◀", help="Previous Top-50 Stock", use_container_width=True):
            st.session_state.selected_ticker = dropdown_tickers[(curr_idx - 1) % len(dropdown_tickers)]
            st.rerun()

    with nav_sym:
        selected_stock = st.selectbox(
            "Active Symbol",
            dropdown_tickers,
            index=curr_idx,
            key="top_nav_symbol",
            label_visibility="collapsed",
        )
        if selected_stock != st.session_state.selected_ticker:
            st.session_state.selected_ticker = selected_stock
            st.rerun()

    with nav_next:
        if st.button("▶", help="Next Top-50 Stock", use_container_width=True):
            st.session_state.selected_ticker = dropdown_tickers[(curr_idx + 1) % len(dropdown_tickers)]
            st.rerun()

    with nav_tf:
        selected_tf = st.selectbox(
            "Timeframe",
            tf_keys,
            index=tf_keys.index(st.session_state.selected_tf),
            key="top_nav_tf",
            label_visibility="collapsed",
        )
        if selected_tf != st.session_state.selected_tf:
            st.session_state.selected_tf = selected_tf
            st.rerun()

    symbol = TOP_200_UNIVERSE[st.session_state.selected_ticker]
    chart_df = fetch_ohlcv(symbol, st.session_state.selected_tf)
    tf_signal, tf_score, tf_rsi, tf_acc = evaluate_signal(chart_df)

    with nav_price:
        if not chart_df.empty:
            curr_price = float(chart_df["Close"].iloc[-1])
            prev_price = float(chart_df["Close"].iloc[-2]) if len(chart_df) > 1 else curr_price
            pct_chg = ((curr_price - prev_price) / prev_price) * 100 if prev_price else 0.0
            st.metric(
                label=f"{st.session_state.selected_ticker} ({st.session_state.selected_tf})",
                value=f"{curr_price:,.2f}",
                delta=f"{pct_chg:+.2f}%",
            )

    with nav_sig:
        sig_color = "#198754" if "BUY" in tf_signal else ("#dc3545" if "SELL" in tf_signal else "#6c757d")
        st.markdown(
            f"""
            <div style="margin-top: 2px;">
                <span style="font-size: 0.75rem; color: #6c757d;">{st.session_state.selected_tf} | Acc: <b>{tf_acc}%</b></span><br>
                <span class="signal-badge" style="background-color: {sig_color}; color: white;">{tf_signal}</span>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with nav_mat:
        if st.button("⤢ Top 50 Matrix", use_container_width=True, type="primary"):
            open_full_page_matrix(matrix_df)

    with nav_focus:
        focus_label = "Exit Focus ✕" if st.session_state.focus_mode else "⛶ Focus Mode"
        if st.button(focus_label, use_container_width=True):
            st.session_state.focus_mode = not st.session_state.focus_mode
            st.rerun()

    qtf_cols = st.columns(len(TIMEFRAME_MAP))
    for idx_tf, tf_btn in enumerate(TIMEFRAME_MAP.keys()):
        is_active_tf = tf_btn == st.session_state.selected_tf
        if qtf_cols[idx_tf].button(
            tf_btn,
            key=f"qtf_{tf_btn}",
            use_container_width=True,
            type="primary" if is_active_tf else "secondary",
        ):
            st.session_state.selected_tf = tf_btn
            st.rerun()

# -----------------------------------------------------------------------------
# INDICATOR & TRADE LEVEL TOGGLES
# -----------------------------------------------------------------------------
t1_col, t2_col, t3_col, t4_col, t5_col, t6_col = st.columns([1.1, 1, 1, 1.2, 1.1, 1.1])
show_bb = t1_col.toggle("BB (20, 2)", value=True)
show_vol = t2_col.toggle("Volume", value=True)
show_rsi = t3_col.toggle("RSI (14)", value=True)
show_levels = t4_col.toggle("Trade Levels", value=True)
show_fib = t5_col.toggle("Auto Fib", value=False)
bars_option = t6_col.selectbox("Bars", ["120", "250", "500", "ALL (Max History)"], index=1, label_visibility="collapsed")

# -----------------------------------------------------------------------------
# INTERACTIVE CANDLESTICK CHART WITH FLOATING CONTROLS & LIVE BADGE
# -----------------------------------------------------------------------------
if not chart_df.empty:
    plot_df = chart_df.copy() if bars_option.startswith("ALL") else chart_df.tail(int(bars_option)).copy()
    levels = calculate_trade_levels(chart_df, tf_signal)

    risk_amount = capital * (risk_pct / 100.0)
    per_share_risk = abs(levels["entry"] - levels["sl"])
    qty = int(risk_amount // per_share_risk) if per_share_risk > 0 else 0

    if show_levels:
        lv1, lv2, lv3, lv4, lv5 = st.columns(5)
        lv1.metric("ENTRY", f"{levels['entry']:,.2f}")
        lv2.metric("STOP LOSS (SL)", f"{levels['sl']:,.2f}")
        lv3.metric("TARGET 1 (T1)", f"{levels['t1']:,.2f}")
        lv4.metric("TARGET 2 (T2)", f"{levels['t2']:,.2f}")
        lv5.metric("Position Size (Qty)", f"{qty:,} units")

    # Persistent Floating Control Bar embedded directly over the top-left of the chart canvas
    badge_bg = "#198754" if "BUY" in tf_signal else ("#dc3545" if "SELL" in tf_signal else "#495057")
    floating_ctrl = st.container()
    with floating_ctrl:
        st.markdown('<div class="chart-overlay-anchor"></div>', unsafe_allow_html=True)
        ov_sym_col, ov_tf_col, ov_badge_col, _ = st.columns([1.45, 0.85, 1.85, 5.85])

        with ov_sym_col:
            ov_selected_stock = st.selectbox(
                "Chart Stock",
                dropdown_tickers,
                index=curr_idx,
                key="chart_overlay_symbol",
                label_visibility="collapsed",
            )
            if ov_selected_stock != st.session_state.selected_ticker:
                st.session_state.selected_ticker = ov_selected_stock
                st.rerun()

        with ov_tf_col:
            ov_selected_tf = st.selectbox(
                "Chart Timeframe",
                tf_keys,
                index=tf_keys.index(st.session_state.selected_tf),
                key="chart_overlay_tf",
                label_visibility="collapsed",
            )
            if ov_selected_tf != st.session_state.selected_tf:
                st.session_state.selected_tf = ov_selected_tf
                st.rerun()

        with ov_badge_col:
            st.markdown(
                f'<div class="floating-chart-badge" style="background-color: {badge_bg};">'
                f"{tf_signal} ({tf_acc}%)"
                f"</div>",
                unsafe_allow_html=True,
            )

    rows_count = 1 + int(show_vol) + int(show_rsi)
    row_heights = [0.64]
    if show_vol and show_rsi:
        row_heights = [0.60, 0.20, 0.20]
    elif show_vol or show_rsi:
        row_heights = [0.75, 0.25]

    fig = make_subplots(
        rows=rows_count,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.03,
        row_heights=row_heights,
    )

    is_intraday = st.session_state.selected_tf in ["15M", "30M", "45M", "1H", "2H", "4H"]
    x_labels = plot_df.index.strftime("%d %b %H:%M") if is_intraday else plot_df.index.strftime("%d %b '%y")

    fig.add_trace(
        go.Candlestick(
            x=x_labels,
            open=plot_df["Open"],
            high=plot_df["High"],
            low=plot_df["Low"],
            close=plot_df["Close"],
            name="Price",
            increasing_line_color="#089981",
            decreasing_line_color="#f23645",
        ),
        row=1,
        col=1,
    )

    if show_bb:
        fig.add_trace(
            go.Scatter(x=x_labels, y=plot_df["BB_Upper"], name="BB Upper", line=dict(color="rgba(41, 98, 255, 0.45)", width=1)),
            row=1,
            col=1,
        )
        fig.add_trace(
            go.Scatter(x=x_labels, y=plot_df["SMA20"], name="20 SMA", line=dict(color="#ff9800", width=1.4)),
            row=1,
            col=1,
        )
        fig.add_trace(
            go.Scatter(
                x=x_labels,
                y=plot_df["BB_Lower"],
                name="BB Lower",
                line=dict(color="rgba(41, 98, 255, 0.45)", width=1),
                fill="tonexty",
                fillcolor="rgba(41, 98, 255, 0.05)",
            ),
            row=1,
            col=1,
        )

    if show_fib:
        hi = float(plot_df["High"].max())
        lo = float(plot_df["Low"].min())
        diff = hi - lo
        for fib_lvl, col in [(0.236, "#9c27b0"), (0.382, "#673ab7"), (0.5, "#2196f3"), (0.618, "#009688")]:
            price_lvl = hi - diff * fib_lvl
            fig.add_hline(
                y=price_lvl,
                line_dash="dot",
                line_color=col,
                annotation_text=f"Fib {fib_lvl:.3f} ({price_lvl:,.1f})",
                annotation_position="bottom right",
                row=1,
                col=1,
            )

    if show_levels:
        level_specs = [
            (levels["t2"], f"T2 {levels['t2']:,.2f}", "#2e7d32", "dot"),
            (levels["t1"], f"T1 {levels['t1']:,.2f}", "#089981", "dash"),
            (levels["entry"], f"ENTRY {levels['entry']:,.2f}", "#2962ff", "solid"),
            (levels["sl"], f"SL {levels['sl']:,.2f}", "#f23645", "dash"),
        ]
        for y_val, label_txt, line_col, dash_style in level_specs:
            fig.add_hline(
                y=y_val,
                line_dash=dash_style,
                line_color=line_col,
                line_width=1.5,
                annotation_text=label_txt,
                annotation_position="top left",
                annotation_font=dict(color=line_col, size=11),
                row=1,
                col=1,
            )

    current_row = 2
    if show_vol:
        vol_colors = ["#089981" if c >= o else "#f23645" for c, o in zip(plot_df["Close"], plot_df["Open"])]
        fig.add_trace(
            go.Bar(x=x_labels, y=plot_df["Volume"], name="Volume", marker_color=vol_colors, opacity=0.65),
            row=current_row,
            col=1,
        )
        fig.update_yaxes(title_text="Vol", fixedrange=False, row=current_row, col=1)
        current_row += 1

    if show_rsi:
        fig.add_trace(
            go.Scatter(x=x_labels, y=plot_df["RSI"], name="RSI (14)", line=dict(color="#7e57c2", width=1.6)),
            row=current_row,
            col=1,
        )
        fig.add_hline(y=70, line_dash="dash", line_color="#f23645", line_width=1, row=current_row, col=1)
        fig.add_hline(y=30, line_dash="dash", line_color="#089981", line_width=1, row=current_row, col=1)
        fig.update_yaxes(title_text="RSI", range=[0, 100], fixedrange=False, row=current_row, col=1)

    chart_height = 680 if st.session_state.focus_mode else 560
    fig.update_layout(
        height=chart_height,
        margin=dict(l=10, r=10, t=20, b=10),
        xaxis_rangeslider_visible=False,
        dragmode="pan",
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.01, xanchor="right", x=1),
    )
    fig.update_xaxes(type="category", nticks=10, fixedrange=False, showgrid=True, gridcolor="rgba(0,0,0,0.05)")
    fig.update_yaxes(side="right", fixedrange=False, showgrid=True, gridcolor="rgba(0,0,0,0.05)", row=1, col=1)

    st.plotly_chart(
        fig,
        use_container_width=True,
        config={
            "scrollZoom": True,
            "doubleClick": "reset+autosize",
            "responsive": True,
            "displayModeBar": True,
            "modeBarButtonsToAdd": ["drawline", "drawrect", "eraseshape"],
            "modeBarButtonsToRemove": ["lasso2d", "select2d"],
        },
    )

# -----------------------------------------------------------------------------
# COLLAPSIBLE EXCEL-LIKE TOP 50 MTF SIGNAL MATRIX & BACKTEST TABS
# -----------------------------------------------------------------------------
if not st.session_state.focus_mode and not matrix_df.empty:
    with st.expander("⤢ Top 50 Strongest Buy/Sell Matrix (Scanned from Top 200 NSE Stocks)", expanded=True):
        m_col1, m_col2, m_col3 = st.columns([4, 1.5, 1.5])
        m_col1.caption("Dynamically ranked by Multi-Timeframe Confluence Score across 9 timeframes. Click any row to load its chart.")
        side_filter = m_col2.selectbox("Filter Side", ["All Top 50", "Buy Opportunities", "Sell Opportunities"], label_visibility="collapsed")
        if m_col3.button("Open Full-Screen View ⤢", key="expander_modal_btn", use_container_width=True):
            open_full_page_matrix(matrix_df)

        filtered_inline = matrix_df.copy()
        if side_filter == "Buy Opportunities":
            filtered_inline = filtered_inline[filtered_inline["Master Signal"].isin(["STRONG BUY", "BUY"])]
        elif side_filter == "Sell Opportunities":
            filtered_inline = filtered_inline[filtered_inline["Master Signal"].isin(["STRONG SELL", "SELL"])]

        inline_df = filtered_inline.drop(columns=["Symbol"]).reset_index(drop=True)
        inline_sel = st.dataframe(
            style_matrix(inline_df),
            use_container_width=True,
            height=450,
            hide_index=True,
            on_select="rerun",
            selection_mode="single-row",
        )

        if inline_sel and inline_sel.selection.rows:
            picked_row = inline_sel.selection.rows[0]
            picked_stock = inline_df.iloc[picked_row]["Stock"]
            if picked_stock != st.session_state.selected_ticker:
                st.session_state.selected_ticker = picked_stock
                st.rerun()

    tab_bt, tab_fin = st.tabs(["Backtest Simulator", "Financials & Details"])

    with tab_bt:
        b1, b2, b3 = st.columns(3)
        buy_rsi = b1.slider("Buy Trigger RSI ≥", 40, 80, 55)
        exit_rsi = b2.slider("Exit Trigger RSI ≤", 20, 60, 45)
        sim_cap = b3.number_input("Simulation Capital", min_value=1000.0, value=float(capital), step=5000.0)

        if not chart_df.empty:
            bt_df = chart_df.dropna(subset=["RSI", "Close"]).copy()
            in_pos = False
            entry_p = 0.0
            cap = sim_cap
            trades = []
            equity = []

            for _, r in bt_df.iterrows():
                price = float(r["Close"])
                rsi_v = float(r["RSI"])
                if not in_pos and rsi_v >= buy_rsi:
                    in_pos = True
                    entry_p = price
                elif in_pos and rsi_v <= exit_rsi:
                    pnl_pct = (price - entry_p) / entry_p
                    cap *= (1 + pnl_pct)
                    trades.append(pnl_pct)
                    in_pos = False
                equity.append(cap)

            wins = sum(1 for t in trades if t > 0)
            win_rate = (wins / len(trades) * 100) if trades else 0.0
            net_ret = ((cap - sim_cap) / sim_cap) * 100

            s1, s2, s3, s4 = st.columns(4)
            s1.metric("Final Capital", f"{cap:,.2f}")
            s2.metric("Net Return", f"{net_ret:+.2f}%")
            s3.metric("Closed Trades", len(trades))
            s4.metric("Win Rate", f"{win_rate:.1f}%")
            st.line_chart(pd.Series(equity, index=bt_df.index, name="Equity Curve"))

    with tab_fin:
        info = yf.Ticker(symbol).info
        fin_rows = [
            ("Name", info.get("longName", st.session_state.selected_ticker)),
            ("Sector", info.get("sector", "Index / Equity")),
            ("Market Cap", f"{info['marketCap']:,}" if info.get("marketCap") else "N/A"),
            ("Trailing P/E", f"{info['trailingPE']:.2f}" if info.get("trailingPE") else "N/A"),
            ("52W High", f"{info['fiftyTwoWeekHigh']:,.2f}" if info.get("fiftyTwoWeekHigh") else "N/A"),
            ("52W Low", f"{info['fiftyTwoWeekLow']:,.2f}" if info.get("fiftyTwoWeekLow") else "N/A"),
            ("50D Avg", f"{info['fiftyDayAverage']:,.2f}" if info.get("fiftyDayAverage") else "N/A"),
            ("200D Avg", f"{info['twoHundredDayAverage']:,.2f}" if info.get("twoHundredDayAverage") else "N/A"),
        ]
        st.dataframe(pd.DataFrame(fin_rows, columns=["Metric", "Value"]), use_container_width=True, hide_index=True)
