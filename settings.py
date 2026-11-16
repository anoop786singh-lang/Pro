{\rtf1\ansi\ansicpg1252\cocoartf2907
\cocoatextscaling1\cocoaplatform1{\fonttbl\f0\fnil\fcharset0 .SFUI-Regular;\f1\fnil\fcharset0 .SFUI-Semibold;}
{\colortbl;\red255\green255\blue255;\red0\green0\blue0;}
{\*\expandedcolortbl;;\cssrgb\c0\c0\c0;}
\pard\tx560\tx1120\tx1680\tx2240\tx2800\tx3360\tx3920\tx4480\tx5040\tx5600\tx6160\tx6720\sl270\slmult1\sb141\partightenfactor0

\f0\fs34 \cf2 import os\
\pard\tx560\tx1120\tx1680\tx2240\tx2800\tx3360\tx3920\tx4480\tx5040\tx5600\tx6160\tx6720\sl270\slmult1\partightenfactor0
\cf2 from dotenv import load_dotenv\
\pard\tx560\tx1120\tx1680\tx2240\tx2800\tx3360\tx3920\tx4480\tx5040\tx5600\tx6160\tx6720\sl270\slmult1\sb265\partightenfactor0
\cf2 load_dotenv()\
class SystemSettings:\
\pard\tx560\tx1120\tx1680\tx2240\tx2800\tx3360\tx3920\tx4480\tx5040\tx5600\tx6160\tx6720\sl270\slmult1\partightenfactor0
\cf2 PROJECT_NAME: str = "Institutional Trading Terminal Pro"\
VERSION: str = "2.1.0"\
\pard\tx560\tx1120\tx1680\tx2240\tx2800\tx3360\tx3920\tx4480\tx5040\tx5600\tx6160\tx6720\sl270\slmult1\sb265\partightenfactor0
\cf2 BASE_DIR: str = os.path.dirname(os.path.abspath(
\f1\b file
\f0\b0 ))\
\pard\tx560\tx1120\tx1680\tx2240\tx2800\tx3360\tx3920\tx4480\tx5040\tx5600\tx6160\tx6720\sl270\slmult1\partightenfactor0
\cf2 DB_PATH: str = os.path.join(BASE_DIR, "data", "market_master.db")\
LOG_PATH: str = os.path.join(BASE_DIR, "logs", "terminal.log")\
\pard\tx560\tx1120\tx1680\tx2240\tx2800\tx3360\tx3920\tx4480\tx5040\tx5600\tx6160\tx6720\sl270\slmult1\sb265\partightenfactor0
\cf2 DEFAULT_TIMEFRAME: str = "1h"\
\pard\tx560\tx1120\tx1680\tx2240\tx2800\tx3360\tx3920\tx4480\tx5040\tx5600\tx6160\tx6720\sl270\slmult1\partightenfactor0
\cf2 INITIAL_CAPITAL: float = 1000000.0\
MAX_RISK_PER_TRADE_PCT: float = 2.0\
\pard\tx560\tx1120\tx1680\tx2240\tx2800\tx3360\tx3920\tx4480\tx5040\tx5600\tx6160\tx6720\sl270\slmult1\sb265\partightenfactor0
\cf2 TIMEFRAMES = \{\
\pard\tx560\tx1120\tx1680\tx2240\tx2800\tx3360\tx3920\tx4480\tx5040\tx5600\tx6160\tx6720\sl270\slmult1\partightenfactor0
\cf2 "15M": \{"interval": "15m", "period": "15d", "weight": 0.15\},\
"1H":  \{"interval": "1h",  "period": "60d", "weight": 0.25\},\
"1D":  \{"interval": "1d",  "period": "1y",  "weight": 0.35\},\
"1WK": \{"interval": "1wk", "period": "3y",  "weight": 0.25\},\
\}\
\pard\tx560\tx1120\tx1680\tx2240\tx2800\tx3360\tx3920\tx4480\tx5040\tx5600\tx6160\tx6720\sl270\slmult1\sb265\partightenfactor0
\cf2 CORE_WATCHLIST = [\
\pard\tx560\tx1120\tx1680\tx2240\tx2800\tx3360\tx3920\tx4480\tx5040\tx5600\tx6160\tx6720\sl270\slmult1\partightenfactor0
\cf2 \{"symbol": "^NSEI", "label": "NIFTY", "category": "Indices"\},\
\{"symbol": "^NSEBANK", "label": "BANKNIFTY", "category": "Indices"\},\
\{"symbol": "^BSESN", "label": "SENSEX", "category": "Indices"\},\
\{"symbol": "RELIANCE.NS", "label": "RELIANCE", "category": "Stocks"\},\
\{"symbol": "HDFCBANK.NS", "label": "HDFCBANK", "category": "Stocks"\},\
\{"symbol": "ICICIBANK.NS", "label": "ICICIBANK", "category": "Stocks"\},\
\{"symbol": "TCS.NS", "label": "TCS", "category": "Stocks"\},\
\{"symbol": "INFY.NS", "label": "INFY", "category": "Stocks"\},\
]\
\pard\tx560\tx1120\tx1680\tx2240\tx2800\tx3360\tx3920\tx4480\tx5040\tx5600\tx6160\tx6720\sl270\slmult1\sb265\partightenfactor0
\cf2 @classmethod\
\pard\tx560\tx1120\tx1680\tx2240\tx2800\tx3360\tx3920\tx4480\tx5040\tx5600\tx6160\tx6720\sl270\slmult1\partightenfactor0
\cf2 def ensure_dirs(cls):\
os.makedirs(os.path.dirname(cls.DB_PATH), exist_ok=True)\
os.makedirs(os.path.dirname(cls.LOG_PATH), exist_ok=True)\
\pard\tx560\tx1120\tx1680\tx2240\tx2800\tx3360\tx3920\tx4480\tx5040\tx5600\tx6160\tx6720\sl270\slmult1\sb265\partightenfactor0
\cf2 settings = SystemSettings()\
\pard\tx560\tx1120\tx1680\tx2240\tx2800\tx3360\tx3920\tx4480\tx5040\tx5600\tx6160\tx6720\sl270\slmult1\partightenfactor0
\cf2 settings.ensure_dirs()}
