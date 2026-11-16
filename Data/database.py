import sqlite3
from config.settings import settings
import logging

class DatabaseManager:
    def __init__(self):
        self.db_path = settings.DB_PATH
        self._ensure_directories()
        self.init_db()

    def _ensure_directories(self):
        import os
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)

    def get_connection(self):
        return sqlite3.connect(self.db_path)

    def init_db(self):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            # ऐतिहासिक डेटा के लिए टेबल
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS historical_bars (
                    symbol TEXT,
                    timestamp TEXT,
                    open REAL,
                    high REAL,
                    low REAL,
                    close REAL,
                    volume INTEGER,
                    PRIMARY KEY (symbol, timestamp)
                )
            """)
            # ट्रेड जर्नलिंग के लिए टेबल
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS trade_log (
                    trade_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT,
                    side TEXT,
                    entry_price REAL,
                    exit_price REAL,
                    quantity INTEGER,
                    pnl REAL,
                    timestamp TEXT
                )
            """)
            conn.commit()
            logging.info("Database initialized successfully.")

db_manager = DatabaseManager()
