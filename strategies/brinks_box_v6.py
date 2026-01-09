"""
Brinks Box Strategy v6.0 - COMPLETE PDF IMPLEMENTATION
=======================================================
Based on FULL PDF analysis including:

ENTRY METHODS:
1. BREAKOUT TRADE - Enter when price BREAKS Brinks high/low
2. VECTOR BLOCK TRADE - Trade off vector blocks INSIDE Brinks
3. STOP-HUNT SCALP - Trade reversal after 14:15-14:45 sweep

KEY RULES FROM PDFs:
- "Trades can be taken at the Brinks range BREAK of high or low 
   OR the vector block within brinks"
- "When Brinks low/high swept, watch how price forms each candle"
- Brinks at BOTTOM of NY session = Bullish bias
- Brinks at TOP of NY session = Bearish bias
- Stop-Hunt between 14:15-14:45 = Reversal signal
- Check unrecovered vectors before entry
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta


class BrinksBoxStrategyV6:
    """
    Complete Brinks Box Strategy from PDFs:
    - Breakout entries on Brinks break
    - Vector block trades inside Brinks
    - Stop-hunt reversal trades
    - Skip Monday (low WR)
    """
    
    def __init__(self):
        self.name = "BrinksBoxV6"
        
        # Session times (UTC)
        self.ASIAN_START = 0
        self.ASIAN_END = 8
        self.LONDON_START = 8
        self.LONDON_END = 14
        self.BRINKS_START = 14
        self.BRINKS_END = 15
        
        # Stop-hunt window
        self.STOPHUNT_START_MIN = 15  # 14:15
        self.STOPHUNT_END_MIN = 45    # 14:45
        
        # Trading window after Brinks
        self.SIGNAL_END = 20
        
        # Vector thresholds
        self.VECTOR_THRESHOLD = 1.5
        self.VOL_PERIOD = 20
        
        # Skip Monday - DISABLED per user request (trading all weekdays)
        self.SKIP_MONDAY = False
    
    def get_name(self) -> str:
        return self.name
    
    def _add_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add technical indicators."""
        df = df.copy()
        
        df['vol_avg'] = df['volume'].rolling(window=self.VOL_PERIOD, min_periods=5).mean()
        df['vol_ratio'] = df['volume'] / df['vol_avg']
        df['body'] = abs(df['close'] - df['open'])
        df['range'] = df['high'] - df['low']
        df['is_bullish'] = df['close'] > df['open']
        df['body_pct'] = df['body'] / df['range'].replace(0, 1)
        
        # Vector identification
        df['is_vector'] = (df['vol_ratio'] >= self.VECTOR_THRESHOLD) & (df['body_pct'] > 0.5)
        df['is_gvc'] = df['is_vector'] & df['is_bullish']
        df['is_rvc'] = df['is_vector'] & ~df['is_bullish']
        
        return df
    
    def _check_vector_recovered(self, vector_candle, subsequent_candles, is_bullish: bool) -> bool:
        """Check if vector has been recovered."""
        if subsequent_candles.empty:
            return False
        
        if is_bullish:  # GVC - recovered if price goes below the open
            for _, c in subsequent_candles.iterrows():
                if c['low'] < vector_candle['open']:
                    return True
        else:  # RVC - recovered if price goes above the open
            for _, c in subsequent_candles.iterrows():
                if c['high'] > vector_candle['open']:
                    return True
        return False
    
    def _analyze_brinks(self, brinks_data: pd.DataFrame, asian_high: float, asian_low: float) -> dict:
        """Analyze Brinks Box for vectors, sweeps, and patterns."""
        if brinks_data.empty:
            return None
        
        brinks_high = brinks_data['high'].max()
        brinks_low = brinks_data['low'].min()
        brinks_mid = (brinks_high + brinks_low) / 2
        brinks_open = brinks_data['open'].iloc[0]
        brinks_close = brinks_data['close'].iloc[-1]
        
        # Brinks direction
        brinks_direction = 'BULL' if brinks_close > brinks_open else 'BEAR'
        
        # Find vectors in Brinks
        gvc_list = brinks_data[brinks_data['is_gvc']]
        rvc_list = brinks_data[brinks_data['is_rvc']]
        
        # Check for unrecovered vectors
        unrecovered_gvc = []
        unrecovered_rvc = []
        
        for idx, gvc in gvc_list.iterrows():
            subsequent = brinks_data[brinks_data.index > idx]
            if not self._check_vector_recovered(gvc, subsequent, is_bullish=True):
                unrecovered_gvc.append(gvc)
        
        for idx, rvc in rvc_list.iterrows():
            subsequent = brinks_data[brinks_data.index > idx]
            if not self._check_vector_recovered(rvc, subsequent, is_bullish=False):
                unrecovered_rvc.append(rvc)
        
        # Check for sweeps
        swept_asian_high = brinks_high > asian_high
        swept_asian_low = brinks_low < asian_low
        
        # Check for stop-hunt pattern (sweep then reversal)
        # Look for sweep of brinks extreme followed by reversal
        first_half = brinks_data.iloc[:len(brinks_data)//2] if len(brinks_data) > 1 else brinks_data
        second_half = brinks_data.iloc[len(brinks_data)//2:] if len(brinks_data) > 1 else brinks_data
        
        bullish_stophunt = False
        bearish_stophunt = False
        
        if not first_half.empty and not second_half.empty:
            # Bullish stop-hunt: first sweeps low, then reverses up
            if first_half['low'].min() < second_half['low'].min():
                if second_half['close'].iloc[-1] > first_half['open'].iloc[0]:
                    bullish_stophunt = True
            
            # Bearish stop-hunt: first sweeps high, then reverses down  
            if first_half['high'].max() > second_half['high'].max():
                if second_half['close'].iloc[-1] < first_half['open'].iloc[0]:
                    bearish_stophunt = True
        
        return {
            'high': brinks_high,
            'low': brinks_low,
            'mid': brinks_mid,
            'direction': brinks_direction,
            'unrecovered_gvc': unrecovered_gvc,
            'unrecovered_rvc': unrecovered_rvc,
            'swept_asian_high': swept_asian_high,
            'swept_asian_low': swept_asian_low,
            'bullish_stophunt': bullish_stophunt,
            'bearish_stophunt': bearish_stophunt,
        }
    
    def generate_signals(self, df: pd.DataFrame) -> pd.Series:
        """
        Generate signals using complete PDF strategy.
        
        Entry Methods:
        1. BREAKOUT: Enter when price breaks Brinks high/low
        2. VECTOR BLOCK: Trade off vector blocks inside Brinks
        3. STOP-HUNT: Trade reversal after sweep
        """
        df = self._add_indicators(df)
        signals = pd.Series(0.0, index=df.index)
        
        for date in df.index.date:
            day_data = df[df.index.date == date]
            
            if day_data.empty:
                continue
            
            # Skip weekends
            weekday = day_data.index[0].weekday()
            if weekday >= 5:
                continue
            
            # Skip Monday (18% WR historically)
            if self.SKIP_MONDAY and weekday == 0:
                continue
            
            # === ASIAN SESSION ===
            asian = day_data[(day_data.index.hour >= self.ASIAN_START) & 
                            (day_data.index.hour < self.ASIAN_END)]
            if asian.empty:
                continue
            
            asian_high = asian['high'].max()
            asian_low = asian['low'].min()
            
            # === BRINKS BOX (14:00-15:00 UTC) ===
            brinks = day_data[(day_data.index.hour >= self.BRINKS_START) & 
                             (day_data.index.hour < self.BRINKS_END)]
            if brinks.empty:
                continue
            
            # Analyze Brinks
            ba = self._analyze_brinks(brinks, asian_high, asian_low)
            if ba is None:
                continue
            
            # === TRADING WINDOW (15:00-20:00 UTC) ===
            trading_window = day_data[(day_data.index.hour >= self.BRINKS_END) & 
                                      (day_data.index.hour < self.SIGNAL_END)]
            
            if trading_window.empty:
                continue
            
            signal_taken = False
            
            for idx, candle in trading_window.iterrows():
                if signal_taken:
                    break
                
                close = candle['close']
                signal = 0.0
                score = 0
                
                # ===== METHOD 1: BREAKOUT TRADE =====
                # Enter when price BREAKS Brinks high/low
                
                if close > ba['high']:
                    # Breakout above Brinks High = LONG
                    signal = 1.0
                    score += 2
                
                elif close < ba['low']:
                    # Breakout below Brinks Low = SHORT
                    signal = -1.0
                    score += 2
                
                # ===== METHOD 2: VECTOR BLOCK TRADE =====
                # Trade off unrecovered vectors inside Brinks
                
                elif len(ba['unrecovered_rvc']) > 0 and close > ba['mid']:
                    # Unrecovered RVC = Expect bullish recovery
                    signal = 1.0
                    score += 2
                
                elif len(ba['unrecovered_gvc']) > 0 and close < ba['mid']:
                    # Unrecovered GVC = Expect bearish recovery
                    signal = -1.0
                    score += 2
                
                # ===== METHOD 3: STOP-HUNT REVERSAL =====
                # Trade reversal after stop-hunt pattern
                
                if ba['bullish_stophunt'] and close > ba['mid']:
                    if signal == 0:
                        signal = 1.0
                    score += 1
                
                if ba['bearish_stophunt'] and close < ba['mid']:
                    if signal == 0:
                        signal = -1.0
                    score += 1
                
                # ===== ADDITIONAL CONFIRMATIONS =====
                
                # Asian sweep trap
                if ba['swept_asian_high'] and close < ba['mid']:
                    if signal == 0:
                        signal = -1.0
                    score += 1
                
                if ba['swept_asian_low'] and close > ba['mid']:
                    if signal == 0:
                        signal = 1.0
                    score += 1
                
                # Confirmation candle
                if candle['is_bullish'] and signal == 1.0:
                    score += 1
                elif not candle['is_bullish'] and signal == -1.0:
                    score += 1
                
                # Vector candle confirmation
                if candle['is_gvc'] and signal == 1.0:
                    score += 1
                elif candle['is_rvc'] and signal == -1.0:
                    score += 1
                
                # ===== FINAL DECISION =====
                # Require score >= 2 for entry
                
                if signal != 0 and score >= 2:
                    signals[idx] = signal
                    signal_taken = True
        
        return signals


if __name__ == "__main__":
    print("Brinks Box V6 - Complete PDF Implementation")
    print("Entry Methods: Breakout, Vector Block, Stop-Hunt")
