import yfinance as yf
import pandas as pd
from data.database import db_manager
import logging

class DataPipeline:
    def fetch_and_store(self, symbol, period="60d", interval="1h"):
        clean_sym = symbol.strip().replace("^", "")
        if not ("." in clean_sym or "NSE" in clean_sym or "BSE" in clean_sym):
            clean_sym += ".NS"
            
        try:
            df = yf.download(clean_sym, period=period, interval=interval, progress=False)
            if df.empty:
                logging.warning(f"No data fetched for {symbol}")
                return False
                
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
                
            df = df.dropna()
            if len(df) < 10:
                logging.warning(f"Insufficient data points for {symbol}")
                return False

            records = [
                (symbol, ts.strftime('%Y-%m-%d %H:%M:%S'), float(row['Open']),
                 float(row['High']), float(row['Low']), float(row['Close']), int(row['Volume']))
                for ts, row in df.iterrows()
            ]

            with db_manager.get_connection() as conn:
                cursor = conn.cursor()
                cursor.executemany("""
                    INSERT OR REPLACE INTO historical_bars 
                    (symbol, timestamp, open, high, low, close, volume)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, records)
                conn.commit()
                
            logging.info(f"Successfully synchronized {len(records)} bars for {symbol}")
            return True
        except Exception as e:
            logging.error(f"Error in pipeline for {symbol}: {e}")
            return False

pipeline = DataPipeline()
