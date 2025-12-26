"""
Brinks Box Strategy v2.0 - Enhanced
=====================================
Based on "Checklist-8-Brinks-Box-Strategy-.pdf" + Hybrid System

Enhancements:
1. Vector Candle confirmation (volume-based)
2. Asian session sweep detection
3. London session trend analysis
4. Session behavior filters

Logic:
1. Skip weekends (Sat/Sun)
2. Analyze Asian Session (00:00-08:00 UTC) - Get range + sweep info
3. Analyze London Session (08:00-14:00 UTC) - Get trend direction
4. Analyze Brinks Box (14:00-15:00 UTC) - Get breakout levels
5. Only trade if:
   - Vector candle confirms direction
   - Asian sweep aligns with trade direction
   - London trend supports the trade
"""

import pandas as pd
import numpy as np


class BrinksBoxStrategyV2:
    """
    Enhanced Brinks Box Strategy with multi-session analysis.
    """
    
    def __init__(self):
        self.name = "BrinksBoxV2"
        
        # Session times (UTC)
        self.ASIAN_START = 0    # 00:00 UTC
        self.ASIAN_END = 8      # 08:00 UTC
        self.LONDON_START = 8   # 08:00 UTC
        self.LONDON_END = 14    # 14:00 UTC
        self.BRINKS_START = 14  # 14:00 UTC
        self.BRINKS_END = 15    # 15:00 UTC
        
        # Vector candle threshold
        self.VECTOR_THRESHOLD = 1.5  # 150% of average volume
        self.VOL_PERIOD = 20         # Volume lookback period
    
    def get_name(self) -> str:
        return self.name
    
    def _identify_vectors(self, df: pd.DataFrame) -> pd.DataFrame:
        """Identify vector candles based on volume."""
        df = df.copy()
        df['vol_avg'] = df['volume'].rolling(window=self.VOL_PERIOD, min_periods=5).mean()
        df['vol_ratio'] = df['volume'] / df['vol_avg']
        df['is_bullish'] = df['close'] > df['open']
        
        # Vector types
        df['is_vector'] = df['vol_ratio'] >= self.VECTOR_THRESHOLD
        df['vector_bullish'] = df['is_vector'] & df['is_bullish']
        df['vector_bearish'] = df['is_vector'] & ~df['is_bullish']
        
        return df
    
    def generate_signals(self, df: pd.DataFrame) -> pd.Series:
        """
        Generate trading signals with enhanced filtering.
        
        Returns:
            pd.Series: 1.0 = LONG, -1.0 = SHORT, 0.0 = No signal
        """
        # Add vector identification
        df = self._identify_vectors(df)
        signals = pd.Series(0.0, index=df.index)
        
        # Group by date
        for date in df.index.date:
            day_data = df[df.index.date == date]
            
            if day_data.empty:
                continue
            
            # === SKIP WEEKENDS ===
            weekday = day_data.index[0].weekday()
            if weekday >= 5:  # Saturday (5) or Sunday (6)
                continue
            
            # === 1. ASIAN SESSION ANALYSIS ===
            asian_mask = (day_data.index.hour >= self.ASIAN_START) & \
                         (day_data.index.hour < self.ASIAN_END)
            asian_data = day_data[asian_mask]
            
            if asian_data.empty:
                continue
            
            asian_high = asian_data['high'].max()
            asian_low = asian_data['low'].min()
            asian_range = asian_high - asian_low
            asian_close = asian_data['close'].iloc[-1]
            
            # Asian session direction
            asian_direction = 'BULLISH' if asian_close > asian_data['open'].iloc[0] else 'BEARISH'
            
            # Vector candles in Asian session
            asian_bull_vectors = asian_data['vector_bullish'].sum()
            asian_bear_vectors = asian_data['vector_bearish'].sum()
            
            # === 2. LONDON SESSION ANALYSIS ===
            london_mask = (day_data.index.hour >= self.LONDON_START) & \
                          (day_data.index.hour < self.LONDON_END)
            london_data = day_data[london_mask]
            
            if london_data.empty:
                continue
            
            london_high = london_data['high'].max()
            london_low = london_data['low'].min()
            london_close = london_data['close'].iloc[-1]
            
            # London trend
            london_direction = 'BULLISH' if london_close > london_data['open'].iloc[0] else 'BEARISH'
            
            # Did London sweep Asian levels?
            london_swept_asian_high = london_high > asian_high
            london_swept_asian_low = london_low < asian_low
            
            # Vector candles in London
            london_bull_vectors = london_data['vector_bullish'].sum()
            london_bear_vectors = london_data['vector_bearish'].sum()
            
            # === 3. BRINKS BOX ANALYSIS ===
            brinks_mask = (day_data.index.hour >= self.BRINKS_START) & \
                          (day_data.index.hour < self.BRINKS_END)
            brinks_data = day_data[brinks_mask]
            
            if brinks_data.empty:
                continue
            
            brinks_high = brinks_data['high'].max()
            brinks_low = brinks_data['low'].min()
            brinks_mid = (brinks_high + brinks_low) / 2
            brinks_range = brinks_high - brinks_low
            
            # Brinks swept Asian levels?
            brinks_swept_asian_high = brinks_high > asian_high
            brinks_swept_asian_low = brinks_low < asian_low
            
            # Vector candles in Brinks
            brinks_bull_vectors = brinks_data['vector_bullish'].sum()
            brinks_bear_vectors = brinks_data['vector_bearish'].sum()
            
            # === 4. POST-BRINKS SIGNALS ===
            post_mask = (day_data.index.hour >= self.BRINKS_END) & \
                        (day_data.index.hour < 20)  # Trade until 20:00 UTC only
            post_data = day_data[post_mask]
            
            if post_data.empty:
                continue
            
            # Only take FIRST signal of the day
            signal_taken = False
            
            for idx, candle in post_data.iterrows():
                if signal_taken:
                    break
                    
                signal = 0.0
                confidence = 0
                
                # === LONG CONDITIONS ===
                long_conditions = []
                
                # Condition 1: Price above Brinks High (Breakout)
                if candle['close'] > brinks_high:
                    long_conditions.append('BREAKOUT')
                    confidence += 1
                
                # Condition 2: Asian Low Sweep Trap
                # Brinks went below Asian Low, but price recovered above Brinks Mid
                if brinks_swept_asian_low and candle['close'] > brinks_mid:
                    long_conditions.append('ASIAN_SWEEP_TRAP')
                    confidence += 2  # Strong signal
                
                # Condition 3: Vector confirmation in Brinks
                if brinks_bull_vectors > 0:
                    long_conditions.append('VECTOR_CONFIRM')
                    confidence += 1
                
                # Condition 4: London trend alignment
                if london_direction == 'BULLISH':
                    long_conditions.append('LONDON_TREND')
                    confidence += 1
                
                # === SHORT CONDITIONS ===
                short_conditions = []
                
                # Condition 1: Price below Brinks Low (Breakdown)
                if candle['close'] < brinks_low:
                    short_conditions.append('BREAKDOWN')
                    confidence += 1
                
                # Condition 2: Asian High Sweep Trap
                # Brinks went above Asian High, but price rejected below Brinks Mid
                if brinks_swept_asian_high and candle['close'] < brinks_mid:
                    short_conditions.append('ASIAN_SWEEP_TRAP')
                    confidence += 2  # Strong signal
                
                # Condition 3: Vector confirmation in Brinks
                if brinks_bear_vectors > 0:
                    short_conditions.append('VECTOR_CONFIRM')
                    confidence += 1
                
                # Condition 4: London trend alignment
                if london_direction == 'BEARISH':
                    short_conditions.append('LONDON_TREND')
                    confidence += 1
                
                # === FINAL SIGNAL DECISION ===
                # Require at least 2 conditions for entry
                if len(long_conditions) >= 2 and len(short_conditions) < 2:
                    signal = 1.0
                    signal_taken = True
                elif len(short_conditions) >= 2 and len(long_conditions) < 2:
                    signal = -1.0
                    signal_taken = True
                
                signals[idx] = signal
        
        return signals


# === QUICK TEST ===
if __name__ == "__main__":
    import ccxt
    from datetime import datetime, timedelta
    
    print("Testing Brinks Box Strategy V2...")
    print("-" * 50)
    
    # Fetch data
    exchange = ccxt.binanceusdm()
    exchange.load_markets()
    symbol = 'BTC/USDT:USDT'
    
    now = datetime.utcnow()
    since = int((now - timedelta(days=30)).timestamp() * 1000)
    
    all_data = []
    current_since = since
    while True:
        ohlcv = exchange.fetch_ohlcv(symbol, '1h', since=current_since, limit=500)
        if not ohlcv:
            break
        all_data.extend(ohlcv)
        current_since = ohlcv[-1][0] + 1
        if len(ohlcv) < 500:
            break
    
    df = pd.DataFrame(all_data, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms', utc=True)
    df.set_index('timestamp', inplace=True)
    
    # Run strategy
    strategy = BrinksBoxStrategyV2()
    signals = strategy.generate_signals(df)
    
    # Report
    longs = (signals == 1.0).sum()
    shorts = (signals == -1.0).sum()
    
    print(f"Candles: {len(df)}")
    print(f"LONG signals:  {longs}")
    print(f"SHORT signals: {shorts}")
    print(f"Total signals: {longs + shorts}")
