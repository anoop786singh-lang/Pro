import os
from dotenv import load_dotenv

load_dotenv()


class SystemSettings:

    PROJECT_NAME: str = "Institutional Trading Terminal Pro"
    VERSION: str = "3.0.0"

    BASE_DIR: str = os.path.dirname(os.path.abspath(__file__))
    DB_PATH: str = os.path.join(BASE_DIR, "data", "market_master.db")
    LOG_PATH: str = os.path.join(BASE_DIR, "logs", "terminal.log")

    BROKER_API_KEY: str = os.getenv(
        "BROKER_API_KEY", "SECURE_API_KEY_PLACEHOLDER"
    )
    BROKER_API_SECRET: str = os.getenv(
        "BROKER_API_SECRET", "SECURE_API_SECRET_PLACEHOLDER"
    )
    USE_LIVE_BROKER: bool = (
        os.getenv("USE_LIVE_BROKER", "False").lower() == "true"
    )

    INITIAL_CAPITAL: float = 1000000.0
    MAX_RISK_PER_TRADE_PCT: float = 2.0

    TIMEFRAMES = {
        "15M": {"interval": "15m", "period": "15d", "weight": 0.15},
        "1H": {"interval": "1h", "period": "60d", "weight": 0.25},
        "1D": {"interval": "1d", "period": "1y", "weight": 0.35},
        "1WK": {"interval": "1wk", "period": "3y", "weight": 0.25},
    }

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

    @classmethod
    def ensure_dirs(cls):
        os.makedirs(os.path.dirname(cls.DB_PATH), exist_ok=True)
        os.makedirs(os.path.dirname(cls.LOG_PATH), exist_ok=True)


settings = SystemSettings()
settings.ensure_dirs()
