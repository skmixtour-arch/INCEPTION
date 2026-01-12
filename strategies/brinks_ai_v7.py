"""
🧠 BRINKS BOX AI STRATEGY v7.0
==============================
Uses LEARNED PATTERNS from 360-day analysis to make smarter decisions.

KEY DISCOVERIES INTEGRATED:
1. Vector Candles = 64% bull / 59% bear accuracy
2. Best LONG day = Tuesday (43%)
3. Best SHORT day = Monday (43%)
4. Bearish Brinks → Bear continuation = 53%
5. Thursday + Below 200 EMA = 62.5% bear win rate
6. Avoid Wednesday (lowest predictability)
"""

import pandas as pd
import numpy as np
from datetime import datetime
import json
import os


class BrinksAIStrategyV7:
    """
    AI-Enhanced Brinks Strategy using learned patterns.
    Makes decisions based on 360 days of historical analysis.
    """
    
    def __init__(self):
        self.name = "BrinksAI_V7"
        
        # Session times (UTC)
        self.BRINKS_START = 14
        self.BRINKS_END = 15
        self.TRADING_END = 20
        
        # Vector threshold
        self.VECTOR_THRESHOLD = 1.5
        
        # === LEARNED PATTERNS ===
        # From 360-day analysis
        
        # Weekday probabilities (0=Mon, 4=Fri)
        self.WEEKDAY_BULL_PROB = {
            0: 0.283,  # Monday - worst for longs
            1: 0.434,  # Tuesday - BEST for longs
            2: 0.340,  # Wednesday - unpredictable
            3: 0.370,  # Thursday
            4: 0.370,  # Friday
        }
        
        self.WEEKDAY_BEAR_PROB = {
            0: 0.434,  # Monday - BEST for shorts
            1: 0.340,  # Tuesday
            2: 0.245,  # Wednesday - unpredictable
            3: 0.407,  # Thursday
            4: 0.426,  # Friday
        }
        
        # Vector candle probabilities
        self.GVC_BULL_PROB = 0.643  # GVC → Bull = 64.3%
        self.RVC_BEAR_PROB = 0.591  # RVC → Bear = 59.1%
        
        # Brinks direction continuation
        self.BULL_BRINKS_BULL_PROB = 0.489
        self.BEAR_BRINKS_BEAR_PROB = 0.531  # Higher!
        
        # EMA patterns
        self.ABOVE_200_BULL_PROB = 0.401
        self.BELOW_200_BEAR_PROB = 0.432
        
        # Best conditions discovered
        self.BEST_BEAR_SETUP = {
            'weekday': 3,  # Thursday
            'below_200': True,
            'win_rate': 0.625,  # 62.5%!
        }
        
        # Minimum confidence to take trade
        self.MIN_CONFIDENCE = 55  # Only trade if > 55% probability
    
    def get_name(self):
        return self.name
    
    def _add_indicators(self, df):
        """Add technical indicators."""
        df = df.copy()
        
        # Volume
        df['vol_avg'] = df['volume'].rolling(window=20).mean()
        df['vol_ratio'] = df['volume'] / df['vol_avg']
        
        # Price action
        df['body'] = abs(df['close'] - df['open'])
        df['range'] = df['high'] - df['low']
        df['body_pct'] = df['body'] / df['range'].replace(0, 1)
        df['is_bullish'] = df['close'] > df['open']
        
        # Vectors
        df['is_vector'] = (df['vol_ratio'] >= self.VECTOR_THRESHOLD) & (df['body_pct'] > 0.5)
        df['is_gvc'] = df['is_vector'] & df['is_bullish']
        df['is_rvc'] = df['is_vector'] & ~df['is_bullish']
        
        # EMAs
        df['ema_50'] = df['close'].ewm(span=50, adjust=False).mean()
        df['ema_200'] = df['close'].ewm(span=200, adjust=False).mean()
        
        # RSI
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss.replace(0, 1)
        df['rsi'] = 100 - (100 / (1 + rs))
        
        return df
    
    def calculate_ai_confidence(self, df, brinks_data, signal_direction):
        """
        Calculate AI confidence score based on learned patterns.
        Returns probability (0-100) and reasons.
        """
        if df is None or brinks_data.empty:
            return 50, []
        
        current = df.iloc[-1]
        weekday = current.name.weekday()
        
        # Start with base probability from weekday
        if signal_direction == 'LONG':
            base_prob = self.WEEKDAY_BULL_PROB.get(weekday, 0.35)
        else:
            base_prob = self.WEEKDAY_BEAR_PROB.get(weekday, 0.35)
        
        confidence = base_prob * 100
        reasons = []
        
        # === VECTOR CANDLE BOOST ===
        # Most powerful pattern from learnings
        has_gvc = brinks_data['is_gvc'].any()
        has_rvc = brinks_data['is_rvc'].any()
        
        if signal_direction == 'LONG' and has_gvc:
            confidence = max(confidence, self.GVC_BULL_PROB * 100)
            reasons.append(f"🟢 GVC detected (64% bull rate)")
        
        if signal_direction == 'SHORT' and has_rvc:
            confidence = max(confidence, self.RVC_BEAR_PROB * 100)
            reasons.append(f"🔴 RVC detected (59% bear rate)")
        
        # === BRINKS DIRECTION BOOST ===
        brinks_open = brinks_data['open'].iloc[0]
        brinks_close = brinks_data['close'].iloc[-1]
        brinks_bullish = brinks_close > brinks_open
        
        if signal_direction == 'LONG' and brinks_bullish:
            confidence += 5
            reasons.append("📈 Bullish Brinks aligns")
        elif signal_direction == 'SHORT' and not brinks_bullish:
            confidence += 8  # Bear continuation is stronger (53% vs 49%)
            reasons.append("📉 Bearish Brinks aligns (+8%)")
        
        # === EMA TREND BOOST ===
        above_200 = current['close'] > current['ema_200']
        
        if signal_direction == 'LONG' and above_200:
            confidence += 5
            reasons.append("📈 Above 200 EMA")
        elif signal_direction == 'SHORT' and not above_200:
            confidence += 7  # Stronger pattern
            reasons.append("📉 Below 200 EMA (+7%)")
        
        # === BEST SETUP CHECK ===
        # Thursday + Below 200 EMA = 62.5% bear
        if signal_direction == 'SHORT':
            if weekday == 3 and not above_200:
                confidence = max(confidence, 62)
                reasons.append("⭐ BEST SETUP: Thu + Below 200 (62.5%)")
        
        # === WEEKDAY WARNINGS ===
        if weekday == 2:  # Wednesday
            confidence -= 10
            reasons.append("⚠️ Wednesday (low predictability)")
        
        if weekday == 0 and signal_direction == 'LONG':
            confidence -= 10
            reasons.append("⚠️ Monday worst for longs")
        
        # === RSI EXTREMES ===
        rsi = current['rsi']
        if not pd.isna(rsi):
            if signal_direction == 'LONG' and rsi < 35:
                confidence += 5
                reasons.append(f"🎯 RSI oversold ({rsi:.0f})")
            elif signal_direction == 'SHORT' and rsi > 65:
                confidence += 5
                reasons.append(f"🎯 RSI overbought ({rsi:.0f})")
        
        # Cap at 0-100
        confidence = max(0, min(100, confidence))
        
        return confidence, reasons
    
    def generate_signals(self, df):
        """
        Generate signals using AI-learned patterns.
        Only takes trades when confidence > MIN_CONFIDENCE.
        """
        df = self._add_indicators(df)
        signals = pd.Series(0.0, index=df.index)
        
        for date in df.index.date:
            day_data = df[df.index.date == date]
            
            if day_data.empty:
                continue
            
            weekday = day_data.index[0].weekday()
            
            # Skip weekends
            if weekday >= 5:
                continue
            
            # === GET BRINKS BOX ===
            brinks = day_data[(day_data.index.hour >= self.BRINKS_START) & 
                             (day_data.index.hour < self.BRINKS_END)]
            if brinks.empty:
                continue
            
            brinks_high = brinks['high'].max()
            brinks_low = brinks['low'].min()
            brinks_mid = (brinks_high + brinks_low) / 2
            
            # === TRADING WINDOW ===
            trading = day_data[(day_data.index.hour >= self.BRINKS_END) & 
                              (day_data.index.hour < self.TRADING_END)]
            
            if trading.empty:
                continue
            
            signal_taken = False
            
            for idx, candle in trading.iterrows():
                if signal_taken:
                    break
                
                close = candle['close']
                potential_signal = 0.0
                
                # === BREAKOUT DETECTION ===
                if close > brinks_high:
                    potential_signal = 1.0  # Long
                elif close < brinks_low:
                    potential_signal = -1.0  # Short
                
                # === VECTOR BLOCK TRADE ===
                elif brinks['is_rvc'].any() and close > brinks_mid:
                    potential_signal = 1.0
                elif brinks['is_gvc'].any() and close < brinks_mid:
                    potential_signal = -1.0
                
                if potential_signal != 0:
                    # Calculate AI confidence
                    direction = 'LONG' if potential_signal == 1.0 else 'SHORT'
                    confidence, reasons = self.calculate_ai_confidence(day_data, brinks, direction)
                    
                    # Only take trade if confidence > threshold
                    if confidence >= self.MIN_CONFIDENCE:
                        signals[idx] = potential_signal
                        signal_taken = True
                        
                        # Store confidence for logging
                        self._last_confidence = confidence
                        self._last_reasons = reasons
        
        return signals
    
    def get_last_decision_info(self):
        """Get info about the last trading decision."""
        return {
            'confidence': getattr(self, '_last_confidence', 50),
            'reasons': getattr(self, '_last_reasons', [])
        }


if __name__ == "__main__":
    print("🧠 Brinks AI Strategy V7")
    print("Uses learned patterns from 360-day analysis")
    print("Min confidence required:", BrinksAIStrategyV7().MIN_CONFIDENCE, "%")
