import pandas as pd
import numpy as np

class SignalManager:
    @staticmethod
    def add_trading_levels(df: pd.DataFrame) -> pd.DataFrame:
        d = df.copy()
        if 'BB_Upper' not in d.columns or 'BB_Lower' not in d.columns:
            return d
        
        d['Signal'] = 'HOLD'
        d['Entry'] = np.nan
        d['Target'] = np.nan
        d['StopLoss'] = np.nan
        
        for i in range(1, len(d)):
            prev_c = d['close'].iloc[i-1]
            curr_c = d['close'].iloc[i]
            prev_u = d['BB_Upper'].iloc[i-1]
            curr_u = d['BB_Upper'].iloc[i]
            prev_l = d['BB_Lower'].iloc[i-1]
            curr_l = d['BB_Lower'].iloc[i]
            
            # Buy Signal Logic
            if prev_c < prev_u and curr_c >= curr_u:
                d.iloc[i, d.columns.get_loc('Signal')] = 'BUY'
                d.iloc[i, d.columns.get_loc('Entry')] = curr_c
                d.iloc[i, d.columns.get_loc('Target')] = curr_c * 1.02 # 2% Target
                d.iloc[i, d.columns.get_loc('StopLoss')] = curr_c * 0.99 # 1% SL
                
            # Sell Signal Logic
            elif prev_c > prev_l and curr_c <= curr_l:
                d.iloc[i, d.columns.get_loc('Signal')] = 'SELL'
                d.iloc[i, d.columns.get_loc('Entry')] = curr_c
                d.iloc[i, d.columns.get_loc('Target')] = curr_c * 0.98 # 2% Target
                d.iloc[i, d.columns.get_loc('StopLoss')] = curr_c * 1.01 # 1% SL
                
            # Carry forward levels if no new signal
            else:
                d.iloc[i, d.columns.get_loc('Entry')] = d.iloc[i-1, d.columns.get_loc('Entry')]
                d.iloc[i, d.columns.get_loc('Target')] = d.iloc[i-1, d.columns.get_loc('Target')]
                d.iloc[i, d.columns.get_loc('StopLoss')] = d.iloc[i-1, d.columns.get_loc('StopLoss')]
                
        return d
