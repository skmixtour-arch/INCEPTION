"""
Brinks Box Strategy v7.0 - ENHANCED WITH VECTOR FILTERS
========================================================
Builds on V6 with enhanced vector candle filtering:

IMPROVEMENTS OVER V6:
1. VECTOR BLOCK FILTER - Skip trades if blocking vectors present
2. VECTOR CONFLUENCE - Boost score if supportive vectors present
3. BRINKS POSITION BIAS - Trade with London range direction
4. STOP-HUNT REVERSAL - Enhanced stop-hunt detection

ENTRY LOGIC:
1. Check Brinks Box at 15:00 UTC
2. Find unrecovered vectors above/below Brinks
3. Place pending orders ONLY if no blocking vectors
4. Set SL/TP when filled
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta


class BrinksBoxStrategyV7:
    """
    Brinks Box V7 - Enhanced with Vector Candle Filters.
    
    Key improvements:
    - Filter breakouts by checking for blocking vectors
    - Add confluence from supportive vectors
    - Consider Brinks position in London range
    """
    
    def __init__(self):
        self.name = "BrinksBoxV7"
        
        # Session times (UTC)
        self.ASIAN_START = 0
        self.ASIAN_END = 8
        self.LONDON_START = 8
        self.LONDON_END = 14
        self.BRINKS_START = 14
        self.BRINKS_END = 15
        self.SIGNAL_END = 20
        
        # Vector detection thresholds
        self.VECTOR_THRESHOLD = 1.5  # Volume ratio for vector candle
        self.VECTOR_BODY_PCT = 0.5   # Minimum body % of range
        self.VOL_PERIOD = 20
        
        # Filtering settings
        self.USE_VECTOR_FILTER = True      # Check for blocking vectors
        self.USE_CONFLUENCE = True         # Boost for supportive vectors
        self.USE_BRINKS_POSITION = True    # Consider Brinks in London range
        self.USE_STOPHUNT = True           # Trade stop-hunt reversals
    
    def get_name(self) -> str:
        return self.name
    
    def _add_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add technical indicators and vector detection."""
        df = df.copy()
        
        # Volume analysis
        df['vol_avg'] = df['volume'].rolling(window=self.VOL_PERIOD, min_periods=5).mean()
        df['vol_ratio'] = df['volume'] / df['vol_avg'].replace(0, 1)
        
        # Candle analysis
        df['body'] = abs(df['close'] - df['open'])
        df['range'] = df['high'] - df['low']
        df['is_bullish'] = df['close'] > df['open']
        df['body_pct'] = df['body'] / df['range'].replace(0, 1)
        
        # Vector identification (high volume + high body %)
        df['is_vector'] = (df['vol_ratio'] >= self.VECTOR_THRESHOLD) & (df['body_pct'] > self.VECTOR_BODY_PCT)
        df['is_gvc'] = df['is_vector'] & df['is_bullish']   # Green Vector Candle
        df['is_rvc'] = df['is_vector'] & ~df['is_bullish']  # Red Vector Candle
        
        return df
    
    def _check_vector_recovered(self, vector_candle, subsequent_candles, is_bullish: bool) -> bool:
        """Check if vector has been recovered (filled)."""
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
    
    def find_unrecovered_vectors(self, df: pd.DataFrame, end_time=None) -> dict:
        """
        Find all unrecovered (unfilled) vector candles.
        
        Returns:
            dict with 'gvc_above', 'gvc_below', 'rvc_above', 'rvc_below' lists
        """
        df = self._add_indicators(df)
        
        if end_time:
            df = df[df.index <= end_time]
        
        current_price = df['close'].iloc[-1] if not df.empty else None
        if current_price is None:
            return {'gvc_above': [], 'gvc_below': [], 'rvc_above': [], 'rvc_below': []}
        
        gvc_above = []
        gvc_below = []
        rvc_above = []
        rvc_below = []
        
        # Find GVCs (Green Vector Candles)
        gvc_candles = df[df['is_gvc']]
        for idx, gvc in gvc_candles.iterrows():
            subsequent = df[df.index > idx]
            if not self._check_vector_recovered(gvc, subsequent, is_bullish=True):
                # Unrecovered GVC - check position relative to current price
                if gvc['high'] < current_price:
                    gvc_below.append({'time': idx, 'high': gvc['high'], 'low': gvc['low']})
                elif gvc['low'] > current_price:
                    gvc_above.append({'time': idx, 'high': gvc['high'], 'low': gvc['low']})
        
        # Find RVCs (Red Vector Candles)
        rvc_candles = df[df['is_rvc']]
        for idx, rvc in rvc_candles.iterrows():
            subsequent = df[df.index > idx]
            if not self._check_vector_recovered(rvc, subsequent, is_bullish=False):
                if rvc['high'] < current_price:
                    rvc_below.append({'time': idx, 'high': rvc['high'], 'low': rvc['low']})
                elif rvc['low'] > current_price:
                    rvc_above.append({'time': idx, 'high': rvc['high'], 'low': rvc['low']})
        
        return {
            'gvc_above': gvc_above,
            'gvc_below': gvc_below,
            'rvc_above': rvc_above,
            'rvc_below': rvc_below
        }
    
    def check_blocking_vectors(self, vectors: dict, trade_type: str) -> bool:
        """
        Check if there are blocking vectors that could prevent the trade.
        
        For LONG: Check for RVCs (resistance) above current price
        For SHORT: Check for GVCs (support) below current price
        
        Returns True if trade should be BLOCKED.
        """
        if trade_type == 'LONG':
            # RVCs above act as resistance - could block upward move
            return len(vectors['rvc_above']) > 0
        else:  # SHORT
            # GVCs below act as support - could block downward move
            return len(vectors['gvc_below']) > 0
    
    def check_supportive_vectors(self, vectors: dict, trade_type: str) -> int:
        """
        Check for supportive vectors that add confluence.
        
        For LONG: GVCs below add support
        For SHORT: RVCs above add resistance pressure
        
        Returns confluence score (0, 1, or 2).
        """
        score = 0
        
        if trade_type == 'LONG':
            # GVCs below = support
            if len(vectors['gvc_below']) > 0:
                score += 1
            if len(vectors['gvc_below']) >= 2:
                score += 1
        else:  # SHORT
            # RVCs above = resistance
            if len(vectors['rvc_above']) > 0:
                score += 1
            if len(vectors['rvc_above']) >= 2:
                score += 1
        
        return score
    
    def get_brinks_position_bias(self, brinks_high: float, brinks_low: float, 
                                  london_high: float, london_low: float) -> str:
        """
        Determine bias based on where Brinks sits in London range.
        
        - Brinks at bottom of London = Bullish (expect bounce)
        - Brinks at top of London = Bearish (expect rejection)
        """
        london_range = london_high - london_low
        if london_range == 0:
            return 'NEUTRAL'
        
        brinks_mid = (brinks_high + brinks_low) / 2
        london_mid = (london_high + london_low) / 2
        
        # Calculate position (0 = bottom, 1 = top)
        position = (brinks_mid - london_low) / london_range
        
        if position < 0.35:
            return 'BULL'  # Brinks at bottom - expect bounce
        elif position > 0.65:
            return 'BEAR'  # Brinks at top - expect rejection
        else:
            return 'NEUTRAL'
    
    def check_stophunt_pattern(self, brinks_data: pd.DataFrame) -> dict:
        """
        Check for stop-hunt pattern in Brinks data.
        
        Stop-hunt = sweep of extreme followed by reversal.
        """
        if brinks_data.empty or len(brinks_data) < 2:
            return {'bullish': False, 'bearish': False}
        
        first_half = brinks_data.iloc[:len(brinks_data)//2]
        second_half = brinks_data.iloc[len(brinks_data)//2:]
        
        bullish_stophunt = False
        bearish_stophunt = False
        
        if not first_half.empty and not second_half.empty:
            # Bullish stop-hunt: sweeps low first, then reverses up
            if first_half['low'].min() < second_half['low'].min():
                if second_half['close'].iloc[-1] > first_half['open'].iloc[0]:
                    bullish_stophunt = True
            
            # Bearish stop-hunt: sweeps high first, then reverses down
            if first_half['high'].max() > second_half['high'].max():
                if second_half['close'].iloc[-1] < first_half['open'].iloc[0]:
                    bearish_stophunt = True
        
        return {'bullish': bullish_stophunt, 'bearish': bearish_stophunt}
    
    def analyze_breakout_opportunity(self, df: pd.DataFrame, brinks_high: float, 
                                      brinks_low: float, current_price: float,
                                      london_high: float = None, london_low: float = None) -> dict:
        """
        Full analysis for breakout opportunity with all V7 filters.
        
        Returns:
            dict with 'signal' (-1, 0, 1), 'score', 'blocked', 'reason'
        """
        result = {
            'signal': 0,
            'score': 0,
            'blocked': False,
            'reason': '',
            'vectors': None
        }
        
        # Find unrecovered vectors
        vectors = self.find_unrecovered_vectors(df)
        result['vectors'] = vectors
        
        # Determine trade direction
        trade_type = None
        if current_price > brinks_high:
            trade_type = 'LONG'
            result['signal'] = 1
            result['score'] = 2  # Base score for breakout
        elif current_price < brinks_low:
            trade_type = 'SHORT'
            result['signal'] = -1
            result['score'] = 2
        else:
            result['reason'] = 'Price inside Brinks box'
            return result
        
        # === FILTER 1: Check for blocking vectors ===
        if self.USE_VECTOR_FILTER:
            if self.check_blocking_vectors(vectors, trade_type):
                result['blocked'] = True
                result['signal'] = 0
                blocking = 'RVC above' if trade_type == 'LONG' else 'GVC below'
                result['reason'] = f'Blocked by unrecovered {blocking}'
                return result
        
        # === FILTER 2: Add confluence from supportive vectors ===
        if self.USE_CONFLUENCE:
            confluence_score = self.check_supportive_vectors(vectors, trade_type)
            result['score'] += confluence_score
        
        # === FILTER 3: Brinks position bias ===
        if self.USE_BRINKS_POSITION and london_high and london_low:
            bias = self.get_brinks_position_bias(brinks_high, brinks_low, london_high, london_low)
            
            if bias == 'BULL' and trade_type == 'LONG':
                result['score'] += 1
            elif bias == 'BEAR' and trade_type == 'SHORT':
                result['score'] += 1
            elif bias == 'BULL' and trade_type == 'SHORT':
                result['score'] -= 1  # Against bias
            elif bias == 'BEAR' and trade_type == 'LONG':
                result['score'] -= 1
        
        result['reason'] = f'{trade_type} breakout - Score {result["score"]}'
        return result
    
    def generate_signals(self, df: pd.DataFrame) -> pd.Series:
        """
        Generate trading signals with full V7 filters.
        """
        df = self._add_indicators(df)
        signals = pd.Series(0.0, index=df.index)
        
        unique_dates = sorted(set(df.index.date))
        
        for date in unique_dates:
            day_data = df[df.index.date == date]
            if day_data.empty:
                continue
            
            # Skip weekends
            weekday = day_data.index[0].weekday()
            if weekday >= 5:
                continue
            
            # Get London session
            london = day_data[(day_data.index.hour >= self.LONDON_START) & 
                             (day_data.index.hour < self.LONDON_END)]
            if london.empty:
                continue
            
            london_high = london['high'].max()
            london_low = london['low'].min()
            
            # Get Brinks Box
            brinks = day_data[(day_data.index.hour >= self.BRINKS_START) & 
                             (day_data.index.hour < self.BRINKS_END)]
            if brinks.empty:
                continue
            
            brinks_high = brinks['high'].max()
            brinks_low = brinks['low'].min()
            
            # Check for stop-hunt pattern
            stophunt = self.check_stophunt_pattern(brinks)
            
            # Trading window
            trading = day_data[(day_data.index.hour >= self.BRINKS_END) & 
                              (day_data.index.hour < self.SIGNAL_END)]
            if trading.empty:
                continue
            
            signal_taken = False
            
            for idx, candle in trading.iterrows():
                if signal_taken:
                    break
                
                current_price = candle['close']
                
                # Analyze opportunity
                analysis = self.analyze_breakout_opportunity(
                    df[df.index <= idx], brinks_high, brinks_low, current_price,
                    london_high, london_low
                )
                
                if analysis['blocked']:
                    continue
                
                if analysis['signal'] != 0 and analysis['score'] >= 2:
                    signals[idx] = float(analysis['signal'])
                    signal_taken = True
                
                # Check stop-hunt entry
                elif self.USE_STOPHUNT:
                    if stophunt['bullish'] and current_price > (brinks_high + brinks_low) / 2:
                        signals[idx] = 1.0
                        signal_taken = True
                    elif stophunt['bearish'] and current_price < (brinks_high + brinks_low) / 2:
                        signals[idx] = -1.0
                        signal_taken = True
        
        return signals


if __name__ == "__main__":
    print("Brinks Box V7 - Enhanced Vector Candle Filters")
    print("Improvements: Vector Filter, Confluence, Position Bias, Stop-Hunt")
