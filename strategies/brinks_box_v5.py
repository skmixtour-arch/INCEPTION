"""
Brinks Box Strategy v5.0 - FULLY OPTIMIZED
===========================================
Based on COMPLETE PDF rules analysis:

MISSING RULES ADDED:
1. Wait for CONFIRMATION CANDLE after Brinks completes
2. Speed candles = manipulation signal (look for reversal)
3. No vectors recovered in Brinks = expect recovery (reversal trade)
4. Vectors recovered = breakout trade
5. SKIP MONDAY (18% win rate historically)
6. Wait until 15:00+ for true signal (don't enter at 15:00 candle)

From PDF:
- "You must wait until the box is formed"
- "Wait to see what the candlestick does that appears once the brinks is complete"
- "Speed of candle = manipulation signal, expect recovery"
- "If no vectors to recover = breakout continuation"
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta


class BrinksBoxStrategyV5:
    """
    Brinks Box V5 - Complete PDF Implementation with Confirmation
    """
    
    def __init__(self):
        self.name = "BrinksBoxV5"
        
        # Session times (UTC)
        self.ASIAN_START = 0
        self.ASIAN_END = 8
        self.LONDON_START = 8
        self.LONDON_END = 14
        self.BRINKS_START = 14
        self.BRINKS_END = 15
        
        # Signal window - AFTER Brinks, not during
        self.SIGNAL_START = 15  # Only enter AFTER 15:00
        self.SIGNAL_END = 20
        
        # Vector thresholds
        self.VECTOR_THRESHOLD = 1.5
        self.VOL_PERIOD = 20
        
        # SKIP MONDAY (18% WR in backtests)
        self.SKIP_MONDAY = True
    
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
        
        # Speed candle = very high volume (>2x average) + strong body
        df['is_speed_candle'] = (df['vol_ratio'] >= 2.0) & (df['body_pct'] > 0.7)
        
        return df
    
    def _check_vector_recovered(self, vector_candle, subsequent_candles, is_bullish: bool) -> bool:
        """Check if vector has been FULLY recovered."""
        if is_bullish:  # GVC - recovered if price goes BELOW the open
            vector_open = vector_candle['open']
            for _, c in subsequent_candles.iterrows():
                if c['low'] < vector_open:
                    return True
        else:  # RVC - recovered if price goes ABOVE the open
            vector_open = vector_candle['open']
            for _, c in subsequent_candles.iterrows():
                if c['high'] > vector_open:
                    return True
        return False
    
    def _analyze_brinks(self, brinks_data: pd.DataFrame) -> dict:
        """
        Analyze Brinks Box for vectors and patterns.
        Returns analysis dict with all relevant info.
        """
        if brinks_data.empty:
            return None
        
        brinks_high = brinks_data['high'].max()
        brinks_low = brinks_data['low'].min()
        brinks_mid = (brinks_high + brinks_low) / 2
        brinks_range = brinks_high - brinks_low
        
        # Find vectors in Brinks
        gvc_list = brinks_data[brinks_data['is_gvc']]
        rvc_list = brinks_data[brinks_data['is_rvc']]
        
        # Check recovery status for each vector
        unrecovered_gvc = False
        unrecovered_rvc = False
        
        for idx, gvc in gvc_list.iterrows():
            subsequent = brinks_data[brinks_data.index > idx]
            if not self._check_vector_recovered(gvc, subsequent, is_bullish=True):
                unrecovered_gvc = True
                break
        
        for idx, rvc in rvc_list.iterrows():
            subsequent = brinks_data[brinks_data.index > idx]
            if not self._check_vector_recovered(rvc, subsequent, is_bullish=False):
                unrecovered_rvc = True
                break
        
        # Check for speed candle in Brinks (manipulation signal)
        has_speed_candle = brinks_data['is_speed_candle'].any()
        if has_speed_candle:
            last_speed = brinks_data[brinks_data['is_speed_candle']].iloc[-1]
            speed_direction = 'UP' if last_speed['is_bullish'] else 'DOWN'
        else:
            speed_direction = None
        
        # Determine Brinks direction (where did it close relative to open)
        brinks_open = brinks_data['open'].iloc[0]
        brinks_close = brinks_data['close'].iloc[-1]
        brinks_direction = 'BULL' if brinks_close > brinks_open else 'BEAR'
        
        return {
            'high': brinks_high,
            'low': brinks_low,
            'mid': brinks_mid,
            'range': brinks_range,
            'unrecovered_gvc': unrecovered_gvc,
            'unrecovered_rvc': unrecovered_rvc,
            'has_speed_candle': has_speed_candle,
            'speed_direction': speed_direction,
            'direction': brinks_direction
        }
    
    def _get_confirmation_signal(self, candle, brinks_analysis: dict, asian_high: float, asian_low: float) -> tuple:
        """
        Get signal based on CONFIRMATION CANDLE after Brinks.
        
        Rules from PDF:
        1. If unrecovered RVC in Brinks → Expect LONG (they will recover = push up)
        2. If unrecovered GVC in Brinks → Expect SHORT (they will recover = push down)
        3. If speed candle UP but didn't hold → Expect SHORT (front-run/trap)
        4. If speed candle DOWN but didn't hold → Expect LONG (front-run/trap)
        5. If vectors recovered → Look for breakout continuation
        """
        close = candle['close']
        ba = brinks_analysis
        
        signal = 0.0
        confidence = 0
        reasons = []
        
        # Rule 1: Unrecovered RVC = Expect LONG (recovery trade)
        if ba['unrecovered_rvc'] and not ba['unrecovered_gvc']:
            if close > ba['mid']:  # Confirmation: price moved up
                signal = 1.0
                confidence += 2
                reasons.append('Unrecovered RVC: Expect bullish recovery')
        
        # Rule 2: Unrecovered GVC = Expect SHORT (recovery trade)
        elif ba['unrecovered_gvc'] and not ba['unrecovered_rvc']:
            if close < ba['mid']:  # Confirmation: price moved down
                signal = -1.0
                confidence += 2
                reasons.append('Unrecovered GVC: Expect bearish recovery')
        
        # Rule 3: Speed candle trap detection
        if ba['has_speed_candle']:
            if ba['speed_direction'] == 'UP' and close < ba['mid']:
                # Speed up but couldn't hold = bull trap
                signal = -1.0
                confidence += 2
                reasons.append('Speed candle UP trapped: Short expected')
            elif ba['speed_direction'] == 'DOWN' and close > ba['mid']:
                # Speed down but couldn't hold = bear trap
                signal = 1.0
                confidence += 2
                reasons.append('Speed candle DOWN trapped: Long expected')
        
        # Rule 4: If no unrecovered vectors = breakout continuation
        if not ba['unrecovered_gvc'] and not ba['unrecovered_rvc']:
            if close > ba['high']:
                signal = 1.0
                confidence += 1
                reasons.append('Vectors recovered: Breakout HIGH')
            elif close < ba['low']:
                signal = -1.0
                confidence += 1
                reasons.append('Vectors recovered: Breakout LOW')
        
        # Rule 5: Asian sweep trap
        brinks_swept_asian_high = ba['high'] > asian_high
        brinks_swept_asian_low = ba['low'] < asian_low
        
        if brinks_swept_asian_high and close < ba['mid']:
            if signal == 0:
                signal = -1.0
            confidence += 1
            reasons.append('Asian high swept & rejected')
        
        if brinks_swept_asian_low and close > ba['mid']:
            if signal == 0:
                signal = 1.0
            confidence += 1
            reasons.append('Asian low swept & rejected')
        
        # Rule 6: Confirmation candle direction
        if candle['is_bullish'] and signal == 1.0:
            confidence += 1
            reasons.append('Bullish confirmation candle')
        elif not candle['is_bullish'] and signal == -1.0:
            confidence += 1
            reasons.append('Bearish confirmation candle')
        
        return signal, confidence, reasons
    
    def generate_signals(self, df: pd.DataFrame) -> pd.Series:
        """
        Generate signals with full PDF logic.
        
        Key improvements in V5:
        - Wait for confirmation candle AFTER Brinks (not during)
        - Detect speed candle traps
        - Skip Monday trades
        - Require confidence >= 2
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
            
            # SKIP MONDAY (18% win rate)
            if self.SKIP_MONDAY and weekday == 0:
                continue
            
            # === ASIAN SESSION ===
            asian = day_data[(day_data.index.hour >= self.ASIAN_START) & 
                            (day_data.index.hour < self.ASIAN_END)]
            if asian.empty:
                continue
            
            asian_high = asian['high'].max()
            asian_low = asian['low'].min()
            
            # === BRINKS BOX ===
            brinks = day_data[(day_data.index.hour >= self.BRINKS_START) & 
                             (day_data.index.hour < self.BRINKS_END)]
            if brinks.empty:
                continue
            
            # Analyze Brinks
            brinks_analysis = self._analyze_brinks(brinks)
            if brinks_analysis is None:
                continue
            
            # === WAIT FOR CONFIRMATION - AFTER BRINKS ===
            # This is the key difference: we wait for a candle AFTER 15:00
            post = day_data[(day_data.index.hour >= self.SIGNAL_START) & 
                           (day_data.index.hour < self.SIGNAL_END)]
            
            if post.empty:
                continue
            
            signal_taken = False
            
            # Look at first 2 candles after Brinks for confirmation
            for idx, candle in post.head(3).iterrows():
                if signal_taken:
                    break
                
                signal, confidence, reasons = self._get_confirmation_signal(
                    candle, brinks_analysis, asian_high, asian_low
                )
                
                # Require confidence >= 2 for entry
                if signal != 0 and confidence >= 2:
                    signals[idx] = signal
                    signal_taken = True
        
        return signals


if __name__ == "__main__":
    print("Brinks Box V5 - Fully Optimized")
