"""
Brinks Box Strategy v3.0 - Vector Recovery Optimized
=====================================================
Based on "Checklist-8-Brinks-Box-Strategy-.pdf"

KEY INSIGHT FROM PDF:
- "If you see aggressive move and vectors NOT recovered = expect recovery (reversal)"
- "If vectors ARE recovered = look for continuation break of high/low"
- This is the core of avoiding false signals!

Logic:
1. Wait for Brinks Box to complete (14:00-15:00 UTC)
2. Identify vectors (GVC/RVC) created INSIDE the Brinks Box
3. Check if vectors have been RECOVERED within the Brinks
4. If NOT recovered → Expect recovery (opposite direction of vector)
5. If RECOVERED → Look for breakout continuation
"""

import pandas as pd
import numpy as np


class BrinksBoxStrategyV3:
    """
    Enhanced Brinks Box Strategy with proper Vector Recovery logic.
    """
    
    def __init__(self):
        self.name = "BrinksBoxV3"
        
        # Session times (UTC)
        self.ASIAN_START = 0    # 00:00 UTC
        self.ASIAN_END = 8      # 08:00 UTC
        self.LONDON_START = 8   # 08:00 UTC
        self.LONDON_END = 14    # 14:00 UTC
        self.BRINKS_START = 14  # 14:00 UTC
        self.BRINKS_END = 15    # 15:00 UTC
        
        # Vector thresholds
        self.VECTOR_THRESHOLD = 1.5  # 150% of average volume
        self.VOL_PERIOD = 20
    
    def get_name(self) -> str:
        return self.name
    
    def _add_vectors(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add vector candle identification."""
        df = df.copy()
        df['vol_avg'] = df['volume'].rolling(window=self.VOL_PERIOD, min_periods=5).mean()
        df['vol_ratio'] = df['volume'] / df['vol_avg']
        df['body'] = abs(df['close'] - df['open'])
        df['range'] = df['high'] - df['low']
        df['is_bullish'] = df['close'] > df['open']
        
        # Vector = high volume + strong body (>60% of range)
        df['is_vector'] = (df['vol_ratio'] >= self.VECTOR_THRESHOLD) & (df['body'] > df['range'] * 0.5)
        df['is_gvc'] = df['is_vector'] & df['is_bullish']   # Green Vector Candle
        df['is_rvc'] = df['is_vector'] & ~df['is_bullish']  # Red Vector Candle
        
        return df
    
    def _check_vector_recovered(self, vector_candle, subsequent_candles, is_bullish):
        """
        Check if a vector candle has been RECOVERED.
        
        For GVC (bullish): Recovered if price goes BELOW the GVC low
        For RVC (bearish): Recovered if price goes ABOVE the RVC high
        """
        if is_bullish:  # GVC
            vector_low = vector_candle['low']
            # Check if any subsequent candle went below the GVC low
            for _, c in subsequent_candles.iterrows():
                if c['low'] < vector_low:
                    return True
        else:  # RVC
            vector_high = vector_candle['high']
            # Check if any subsequent candle went above the RVC high
            for _, c in subsequent_candles.iterrows():
                if c['high'] > vector_high:
                    return True
        return False
    
    def generate_signals(self, df: pd.DataFrame) -> pd.Series:
        """
        Generate trading signals with proper vector recovery logic.
        
        KEY RULE FROM PDF:
        - Unrecovered GVC in Brinks → Expect SHORT (they will recover it = push down)
        - Unrecovered RVC in Brinks → Expect LONG (they will recover it = push up)
        - If vector IS recovered → Look for breakout
        """
        df = self._add_vectors(df)
        signals = pd.Series(0.0, index=df.index)
        
        for date in df.index.date:
            day_data = df[df.index.date == date]
            
            if day_data.empty:
                continue
            
            # Skip weekends
            weekday = day_data.index[0].weekday()
            if weekday >= 5:
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
            
            brinks_high = brinks['high'].max()
            brinks_low = brinks['low'].min()
            brinks_mid = (brinks_high + brinks_low) / 2
            
            # === ANALYZE VECTORS IN BRINKS ===
            brinks_gvc = brinks[brinks['is_gvc']]  # Green vectors in Brinks
            brinks_rvc = brinks[brinks['is_rvc']]  # Red vectors in Brinks
            
            # Check if vectors are recovered WITHIN the Brinks
            gvc_recovered = True
            rvc_recovered = True
            
            for idx, gvc in brinks_gvc.iterrows():
                # Get candles after this GVC but still in Brinks
                subsequent = brinks[brinks.index > idx]
                if not self._check_vector_recovered(gvc, subsequent, is_bullish=True):
                    gvc_recovered = False
                    break
            
            for idx, rvc in brinks_rvc.iterrows():
                subsequent = brinks[brinks.index > idx]
                if not self._check_vector_recovered(rvc, subsequent, is_bullish=False):
                    rvc_recovered = False
                    break
            
            # === DETERMINE SIGNAL LOGIC ===
            # From PDF: "If aggressive move up and vectors NOT recovered = SHORT (they will recover)"
            
            has_unrecovered_gvc = len(brinks_gvc) > 0 and not gvc_recovered
            has_unrecovered_rvc = len(brinks_rvc) > 0 and not rvc_recovered
            
            # Check for sweep traps (Asian session)
            brinks_swept_asian_high = brinks_high > asian_high
            brinks_swept_asian_low = brinks_low < asian_low
            
            # === POST-BRINKS SIGNALS ===
            post = day_data[(day_data.index.hour >= self.BRINKS_END) & 
                           (day_data.index.hour < 20)]
            if post.empty:
                continue
            
            signal_taken = False
            
            for idx, candle in post.iterrows():
                if signal_taken:
                    break
                
                close = candle['close']
                signal = 0.0
                reasons = []
                
                # === SCENARIO 1: UNRECOVERED GVC = EXPECT SHORT ===
                # PDF: "aggressive move up + vectors NOT recovered = expect recovery"
                if has_unrecovered_gvc:
                    if close < brinks_mid:
                        signal = -1.0
                        reasons.append('UNRECOVERED GVC: Expect recovery (SHORT)')
                
                # === SCENARIO 2: UNRECOVERED RVC = EXPECT LONG ===
                if has_unrecovered_rvc:
                    if close > brinks_mid:
                        signal = 1.0
                        reasons.append('UNRECOVERED RVC: Expect recovery (LONG)')
                
                # === SCENARIO 3: VECTORS RECOVERED = BREAKOUT ===
                if not has_unrecovered_gvc and not has_unrecovered_rvc:
                    # "If no vectors to recover = look for continuation break"
                    if close > brinks_high:
                        signal = 1.0
                        reasons.append('VECTORS RECOVERED: Breakout HIGH (LONG)')
                    elif close < brinks_low:
                        signal = -1.0
                        reasons.append('VECTORS RECOVERED: Breakout LOW (SHORT)')
                
                # === SCENARIO 4: SWEEP TRAPS ===
                if brinks_swept_asian_high and close < brinks_mid:
                    if signal != -1.0:  # Don't override if already SHORT
                        signal = -1.0
                        reasons.append('SWEEP TRAP: Asian High swept, price rejected (SHORT)')
                
                if brinks_swept_asian_low and close > brinks_mid:
                    if signal != 1.0:  # Don't override if already LONG
                        signal = 1.0
                        reasons.append('SWEEP TRAP: Asian Low swept, price rejected (LONG)')
                
                if signal != 0:
                    signals[idx] = signal
                    signal_taken = True
        
        return signals


# === TEST ===
if __name__ == "__main__":
    import ccxt
    from datetime import datetime, timedelta
    
    print("Testing Brinks Box Strategy V3...")
    print("-" * 50)
    
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
    
    strategy = BrinksBoxStrategyV3()
    signals = strategy.generate_signals(df)
    
    longs = (signals == 1.0).sum()
    shorts = (signals == -1.0).sum()
    
    print(f"Candles: {len(df)}")
    print(f"LONG signals:  {longs}")
    print(f"SHORT signals: {shorts}")
