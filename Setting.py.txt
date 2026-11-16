
import os
from dotenv import load_dotenv

load_dotenv()

class SystemSettings:
    PROJECT_NAME: str = "Institutional Trading Terminal Pro"
    VERSION: str = "2.0.0"
    
    # पाथ सेटिंग्स
    BASE_DIR: str = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    DB_PATH: str = os.path.join(BASE_DIR, "data", "market_master.db")
    LOG_PATH: str = os.path.join(BASE_DIR, "logs", "terminal.log")
    
    # ब्रोकर और एपीआई सेटिंग्स
    BROKER_API_KEY: str = os.getenv("BROKER_API_KEY", "SECURE_API_KEY_PLACEHOLDER")
    BROKER_API_SECRET: str = os.getenv("BROKER_API_SECRET", "SECURE_API_SECRET_PLACEHOLDER")
    USE_LIVE_BROKER: bool = os.getenv("USE_LIVE_BROKER", "False").lower() == "true"
    
    # डिफ़ॉल्ट पैरामीटर्स
    DEFAULT_TIMEFRAME: str = "1h"
    INITIAL_CAPITAL: float = 1000000.0 # 10 Lakhs
    MAX_RISK_PER_TRADE_PCT: float = 2.0
    
    # वॉचलिस्ट यूनिवर्स
    CORE_WATCHLIST = [
        {"symbol": "^NSEI", "label": "NIFTY", "category": "Indices"},
        {"symbol": "^NSEBANK", "label": "BANKNIFTY", "category": "Indices"},
        {"symbol": "^BSESN", "label": "SENSEX", "category": "Indices"},
        {"symbol": "RELIANCE.NS", "label": "RELIANCE", "category": "Stocks"},
        {"symbol": "HDFCBANK.NS", "label": "HDFCBANK", "category": "Stocks"},
        {"symbol": "ICICIBANK.NS", "label": "ICICIBANK", "category": "Stocks"},
        {"symbol": "TCS.NS", "label": "TCS", "category": "Stocks"},
        {"symbol": "INFY.NS", "label": "INFY", "category": "Stocks"},
    ]

settings = SystemSettings()
