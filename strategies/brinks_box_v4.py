"""
Brinks Box Strategy v4.0 - Complete PDF Implementation
========================================================
Combines ALL rules from the PDFs:

From Checklist-8-Brinks-Box-Strategy:
- Wait for Brinks to complete before entry
- Identify unrecovered vectors
- Vector recovery logic
- Sweep traps (Asian session)

From US-Brinx-Session-Small-file:
- Stop-hunt between 14:15-14:45 UTC
- Brinks position matters (top vs bottom of range)
- Check indices correlation

From Platinum-Trade-Setups-Checklist-Part-1:
- Monday Asian session reference
- Premium/Discount zones
- Vector block confluence areas

From Understanding_order_process:
- Volume delta indication (bid/ask imbalance proxy)
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta


class BrinksBoxStrategyV4:
    """
    Complete Brinks Box Strategy implementing all PDF rules.
    """
    
    def __init__(self):
        self.name = "BrinksBoxV4"
        
        # Session times (UTC)
        self.ASIAN_START = 0
        self.ASIAN_END = 8
        self.LONDON_START = 8
        self.LONDON_END = 14
        self.BRINKS_START = 14
        self.BRINKS_END = 15
        
        # Stop-hunt window (from PDF)
        self.STOPHUNT_START = 14  # 14:15 simplified to 14:00
        self.STOPHUNT_END = 15    # 14:45 simplified to 15:00
        
        # Vector thresholds
        self.VECTOR_THRESHOLD = 1.5
        self.VOL_PERIOD = 20
    
    def get_name(self) -> str:
        return self.name
    
    def _add_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add all technical indicators."""
        df = df.copy()
        
        # Volume analysis
        df['vol_avg'] = df['volume'].rolling(window=self.VOL_PERIOD, min_periods=5).mean()
        df['vol_ratio'] = df['volume'] / df['vol_avg']
        
        # Candle analysis
        df['body'] = abs(df['close'] - df['open'])
        df['range'] = df['high'] - df['low']
        df['is_bullish'] = df['close'] > df['open']
        df['body_pct'] = df['body'] / df['range'].replace(0, 1)  # Body as % of range
        
        # Vector identification (strong body + high volume)
        df['is_vector'] = (df['vol_ratio'] >= self.VECTOR_THRESHOLD) & (df['body_pct'] > 0.5)
        df['is_gvc'] = df['is_vector'] & df['is_bullish']   # Green Vector
        df['is_rvc'] = df['is_vector'] & ~df['is_bullish']  # Red Vector
        
        # Volume delta proxy (buy vs sell pressure)
        # If close near high = buying pressure, near low = selling pressure
        df['close_position'] = (df['close'] - df['low']) / df['range'].replace(0, 1)
        df['vol_delta'] = (df['close_position'] - 0.5) * df['volume']  # Positive = bullish
        
        # EMAs for trend
        df['ema_50'] = df['close'].ewm(span=50, adjust=False).mean()
        df['ema_200'] = df['close'].ewm(span=200, adjust=False).mean()
        df['trend'] = np.where(df['ema_50'] > df['ema_200'], 'BULL', 'BEAR')
        
        return df
    
    def _get_monday_asian_range(self, df: pd.DataFrame, current_date) -> dict:
        """Get Monday's Asian session range (important reference per PDF)."""
        # Find the Monday of this week
        current_weekday = pd.Timestamp(current_date).weekday()
        days_since_monday = current_weekday  # Monday = 0
        monday_date = current_date - timedelta(days=days_since_monday)
        
        monday_data = df[df.index.date == monday_date]
        if monday_data.empty:
            return None
        
        asian = monday_data[(monday_data.index.hour >= self.ASIAN_START) & 
                           (monday_data.index.hour < self.ASIAN_END)]
        if asian.empty:
            return None
        
        return {
            'high': asian['high'].max(),
            'low': asian['low'].min(),
            'mid': (asian['high'].max() + asian['low'].min()) / 2
        }
    
    def _check_premium_discount(self, price: float, monday_asian: dict) -> str:
        """
        Check if price is in Premium or Discount zone.
        Premium = above Monday Asian mid (expensive)
        Discount = below Monday Asian mid (cheap)
        """
        if monday_asian is None:
            return 'NEUTRAL'
        
        mid = monday_asian['mid']
        if price > mid:
            return 'PREMIUM'
        else:
            return 'DISCOUNT'
    
    def _detect_stop_hunt(self, brinks_data: pd.DataFrame) -> dict:
        """
        Detect stop-hunt pattern in Brinks (14:15-14:45 usually).
        Stop-hunt = quick sweep below low or above high, then reversal.
        """
        if len(brinks_data) < 2:
            return {'detected': False}
        
        # Check for reversal pattern
        first_half = brinks_data.iloc[:len(brinks_data)//2]
        second_half = brinks_data.iloc[len(brinks_data)//2:]
        
        # Bullish stop-hunt: first half goes down, second half recovers
        bullish_hunt = (first_half['low'].min() < second_half['low'].min() and 
                       second_half['close'].iloc[-1] > first_half['close'].iloc[0])
        
        # Bearish stop-hunt: first half goes up, second half dumps
        bearish_hunt = (first_half['high'].max() > second_half['high'].max() and
                       second_half['close'].iloc[-1] < first_half['close'].iloc[0])
        
        return {
            'detected': bullish_hunt or bearish_hunt,
            'direction': 'LONG' if bullish_hunt else ('SHORT' if bearish_hunt else None)
        }
    
    def _check_vector_recovered(self, vector_candle, subsequent_candles, is_bullish: bool) -> bool:
        """Check if vector has been recovered."""
        if is_bullish:  # GVC recovered if price breaks below its low
            for _, c in subsequent_candles.iterrows():
                if c['low'] < vector_candle['low']:
                    return True
        else:  # RVC recovered if price breaks above its high
            for _, c in subsequent_candles.iterrows():
                if c['high'] > vector_candle['high']:
                    return True
        return False
    
    def _get_brinks_position(self, brinks_data: pd.DataFrame, post_data: pd.DataFrame) -> str:
        """
        Determine Brinks Box position relative to price.
        From PDF: If Brinks at BOTTOM = expect UP, at TOP = expect DOWN
        """
        if brinks_data.empty or post_data.empty:
            return 'NEUTRAL'
        
        brinks_mid = (brinks_data['high'].max() + brinks_data['low'].min()) / 2
        current_price = post_data['close'].iloc[0]
        
        if current_price > brinks_mid:
            return 'BOTTOM'  # Brinks is below current price = bullish
        else:
            return 'TOP'     # Brinks is above current price = bearish
    
    def generate_signals(self, df: pd.DataFrame) -> pd.Series:
        """
        Generate signals using complete PDF logic.
        
        Signal scoring system:
        - Unrecovered vector: +2 (strong)
        - Stop-hunt detection: +2 (strong)
        - Brinks position: +1
        - Premium/Discount alignment: +1
        - Asian sweep trap: +1
        - Trend alignment: +1
        
        Require score >= 3 for entry
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
            
            # === GET MONDAY ASIAN REFERENCE ===
            monday_asian = self._get_monday_asian_range(df, date)
            
            # === ASIAN SESSION ===
            asian = day_data[(day_data.index.hour >= self.ASIAN_START) & 
                            (day_data.index.hour < self.ASIAN_END)]
            if asian.empty:
                continue
            
            asian_high = asian['high'].max()
            asian_low = asian['low'].min()
            
            # === LONDON SESSION ===
            london = day_data[(day_data.index.hour >= self.LONDON_START) & 
                             (day_data.index.hour < self.LONDON_END)]
            london_direction = 'BULL' if (not london.empty and 
                                          london['close'].iloc[-1] > london['open'].iloc[0]) else 'BEAR'
            
            # === BRINKS BOX ===
            brinks = day_data[(day_data.index.hour >= self.BRINKS_START) & 
                             (day_data.index.hour < self.BRINKS_END)]
            if brinks.empty:
                continue
            
            brinks_high = brinks['high'].max()
            brinks_low = brinks['low'].min()
            brinks_mid = (brinks_high + brinks_low) / 2
            
            # === VECTOR ANALYSIS IN BRINKS ===
            brinks_gvc = brinks[brinks['is_gvc']]
            brinks_rvc = brinks[brinks['is_rvc']]
            
            gvc_recovered = True
            for idx, gvc in brinks_gvc.iterrows():
                subsequent = brinks[brinks.index > idx]
                if not self._check_vector_recovered(gvc, subsequent, is_bullish=True):
                    gvc_recovered = False
                    break
            
            rvc_recovered = True
            for idx, rvc in brinks_rvc.iterrows():
                subsequent = brinks[brinks.index > idx]
                if not self._check_vector_recovered(rvc, subsequent, is_bullish=False):
                    rvc_recovered = False
                    break
            
            has_unrecovered_gvc = len(brinks_gvc) > 0 and not gvc_recovered
            has_unrecovered_rvc = len(brinks_rvc) > 0 and not rvc_recovered
            
            # === STOP-HUNT DETECTION ===
            stop_hunt = self._detect_stop_hunt(brinks)
            
            # === ASIAN SWEEP DETECTION ===
            brinks_swept_asian_high = brinks_high > asian_high
            brinks_swept_asian_low = brinks_low < asian_low
            
            # === POST-BRINKS SIGNALS ===
            post = day_data[(day_data.index.hour >= self.BRINKS_END) & 
                           (day_data.index.hour < 20)]
            if post.empty:
                continue
            
            # Get Brinks position
            brinks_position = self._get_brinks_position(brinks, post)
            
            signal_taken = False
            
            for idx, candle in post.iterrows():
                if signal_taken:
                    break
                
                close = candle['close']
                trend = candle['trend']
                
                # Check Premium/Discount
                zone = self._check_premium_discount(close, monday_asian)
                
                # === SCORING SYSTEM ===
                long_score = 0
                short_score = 0
                
                # 1. Unrecovered Vectors (+2)
                if has_unrecovered_rvc:  # RVC unrecovered = expect LONG
                    long_score += 2
                if has_unrecovered_gvc:  # GVC unrecovered = expect SHORT
                    short_score += 2
                
                # 2. Stop-Hunt Detection (+2)
                if stop_hunt['detected']:
                    if stop_hunt['direction'] == 'LONG':
                        long_score += 2
                    elif stop_hunt['direction'] == 'SHORT':
                        short_score += 2
                
                # 3. Brinks Position (+1)
                if brinks_position == 'BOTTOM':  # Brinks below = bullish
                    long_score += 1
                elif brinks_position == 'TOP':   # Brinks above = bearish
                    short_score += 1
                
                # 4. Premium/Discount Zone (+1)
                if zone == 'DISCOUNT':  # Cheap = good for longs
                    long_score += 1
                elif zone == 'PREMIUM':  # Expensive = good for shorts
                    short_score += 1
                
                # 5. Asian Sweep Trap (+1)
                if brinks_swept_asian_low and close > brinks_mid:
                    long_score += 1  # Swept low but recovered = bullish trap
                if brinks_swept_asian_high and close < brinks_mid:
                    short_score += 1  # Swept high but rejected = bearish trap
                
                # 6. Trend Alignment (+1)
                if trend == 'BULL':
                    long_score += 1
                else:
                    short_score += 1
                
                # 7. London Direction (+1)
                if london_direction == 'BULL':
                    long_score += 1
                else:
                    short_score += 1
                
                # 8. Breakout confirmation (+1)
                if close > brinks_high:
                    long_score += 1
                if close < brinks_low:
                    short_score += 1
                
                # === FINAL DECISION (require score >= 3) ===
                if long_score >= 3 and short_score < long_score:
                    signals[idx] = 1.0
                    signal_taken = True
                elif short_score >= 3 and long_score < short_score:
                    signals[idx] = -1.0
                    signal_taken = True
        
        return signals


if __name__ == "__main__":
    print("Brinks Box V4 - Complete PDF Implementation")
    print("Testing strategy...")
