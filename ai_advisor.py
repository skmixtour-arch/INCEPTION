"""
🧠 AI ADVISOR - Market Intelligence Bot
========================================
Runs alongside INCEPTION Bot to provide:
- Real-time vector candle detection
- Unrecovered vector alerts
- Confidence scoring for signals
- Smart level identification (support/resistance)

Sends Telegram alerts to help with entry/exit decisions.
"""

import ccxt
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import time
import requests
import sys
import os

# Add parent directory for TradersRealityModel
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class AIAdvisor:
    """AI Market Advisor - Analyzes market and sends insights via Telegram."""
    
    VERSION = "1.0.0"
    
    # Credentials (same as INCEPTION bot)
    BINANCE_API_KEY = "HZHCu0fM6vxP4eDPkGGLpD6kHoksKPNTxceVDJusfjnsklwqne0dpzQ1vdbS3yrc"
    BINANCE_API_SECRET = "zZtxGRz9mWqvkIDquWPUdmltUbFPyibNzTNQmNoc6V2ep4VF9GdImZGj1W0dAAWi"
    TELEGRAM_BOT_TOKEN = "8371462261:AAELiZdXRedALn3KWblWq7Ce1ucYZP6LFrg"
    TELEGRAM_CHAT_ID = "345135704"
    
    def __init__(self):
        # Exchange connection
        self.exchange = ccxt.binanceusdm({
            'apiKey': self.BINANCE_API_KEY,
            'secret': self.BINANCE_API_SECRET,
            'enableRateLimit': True,
        })
        self.exchange.load_markets()
        self.symbol = 'BTC/USDC:USDC'
        
        # AI Model Parameters
        self.VECTOR_GREEN_RED_THRESHOLD = 2.0  # 200% volume = major vector
        self.VECTOR_BLUE_PINK_THRESHOLD = 1.5  # 150% volume = minor vector
        
        # State tracking
        self.unrecovered_vectors = []
        self.last_analysis_time = None
        self.last_alert_hour = None
        self.brinks_box = {'high': None, 'low': None, 'date': None}
        
        # Session times (UTC)
        self.BRINKS_START = 14
        self.BRINKS_END = 15
        self.TRADING_END = 20
    
    def send_telegram(self, message):
        """Send Telegram message."""
        try:
            url = f"https://api.telegram.org/bot{self.TELEGRAM_BOT_TOKEN}/sendMessage"
            data = {
                "chat_id": self.TELEGRAM_CHAT_ID,
                "text": message,
                "parse_mode": "Markdown"
            }
            requests.post(url, data=data, timeout=10)
        except Exception as e:
            print(f"Telegram error: {e}")
    
    def fetch_candles(self, timeframe='1h', limit=100):
        """Fetch candle data from Binance."""
        try:
            ohlcv = self.exchange.fetch_ohlcv(self.symbol, timeframe, limit=limit)
            df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms', utc=True)
            df.set_index('timestamp', inplace=True)
            return df
        except Exception as e:
            print(f"Error fetching candles: {e}")
            return None
    
    def analyze_vectors(self, df):
        """Identify vector candles and track unrecovered ones."""
        if df is None or len(df) < 20:
            return []
        
        # Calculate volume average
        df['vol_avg'] = df['volume'].rolling(window=10).mean()
        df['vol_ratio'] = df['volume'] / df['vol_avg']
        df['body'] = abs(df['close'] - df['open'])
        df['range'] = df['high'] - df['low']
        df['body_pct'] = df['body'] / df['range'].replace(0, 1)
        df['is_bullish'] = df['close'] > df['open']
        
        vectors = []
        
        for i in range(10, len(df)):
            row = df.iloc[i]
            
            if row['vol_ratio'] >= self.VECTOR_GREEN_RED_THRESHOLD and row['body_pct'] > 0.5:
                vector_type = "🟢 GREEN VECTOR (Bullish)" if row['is_bullish'] else "🔴 RED VECTOR (Bearish)"
                
                # Calculate key levels
                vector_50pct = (row['high'] + row['low']) / 2
                vector_open = row['open']
                
                vectors.append({
                    'time': df.index[i],
                    'type': vector_type,
                    'price': row['close'],
                    'high': row['high'],
                    'low': row['low'],
                    'level_50': vector_50pct,
                    'level_open': vector_open,
                    'is_bullish': row['is_bullish'],
                    'vol_ratio': row['vol_ratio'],
                    'recovered': False
                })
            
            elif row['vol_ratio'] >= self.VECTOR_BLUE_PINK_THRESHOLD and row['body_pct'] > 0.4:
                vector_type = "🔵 BLUE VECTOR (Minor Bull)" if row['is_bullish'] else "💗 PINK VECTOR (Minor Bear)"
                vectors.append({
                    'time': df.index[i],
                    'type': vector_type,
                    'price': row['close'],
                    'high': row['high'],
                    'low': row['low'],
                    'is_bullish': row['is_bullish'],
                    'vol_ratio': row['vol_ratio'],
                    'recovered': True  # Minor vectors don't track recovery
                })
        
        return vectors
    
    def check_vector_recovery(self, vectors, current_price):
        """Check if any unrecovered vectors have been recovered."""
        alerts = []
        
        for vec in vectors:
            if vec.get('recovered'):
                continue
            
            # Check if price has recovered to the vector's open level
            if vec['is_bullish']:
                # Green vector recovered if price drops below open
                if current_price < vec['level_open']:
                    vec['recovered'] = True
                    alerts.append(f"✅ Vector recovered at ${current_price:,.0f}")
            else:
                # Red vector recovered if price rises above open
                if current_price > vec['level_open']:
                    vec['recovered'] = True
                    alerts.append(f"✅ Vector recovered at ${current_price:,.0f}")
        
        return alerts
    
    def calculate_confidence(self, df, signal_direction):
        """
        Calculate AI confidence score (0-100) for a trade direction.
        
        Factors:
        - Trend alignment (EMA 50/200)
        - Volume momentum
        - Unrecovered vectors
        - Distance from key levels
        """
        if df is None or len(df) < 50:
            return 50  # Neutral
        
        score = 50  # Start neutral
        reasons = []
        
        current = df.iloc[-1]
        
        # 1. EMA Trend Alignment (+/- 15 points)
        df['ema_50'] = df['close'].ewm(span=50, adjust=False).mean()
        df['ema_200'] = df['close'].ewm(span=200, adjust=False).mean()
        
        ema_50 = df['ema_50'].iloc[-1]
        ema_200 = df['ema_200'].iloc[-1]
        price = current['close']
        
        if signal_direction == 'LONG':
            if price > ema_50 > ema_200:
                score += 15
                reasons.append("📈 Strong uptrend (price > 50 > 200 EMA)")
            elif price > ema_50:
                score += 8
                reasons.append("📈 Above 50 EMA")
            elif price < ema_200:
                score -= 10
                reasons.append("⚠️ Below 200 EMA (risky long)")
        else:  # SHORT
            if price < ema_50 < ema_200:
                score += 15
                reasons.append("📉 Strong downtrend (price < 50 < 200 EMA)")
            elif price < ema_50:
                score += 8
                reasons.append("📉 Below 50 EMA")
            elif price > ema_200:
                score -= 10
                reasons.append("⚠️ Above 200 EMA (risky short)")
        
        # 2. Volume Momentum (+/- 10 points)
        recent_vol = df['volume'].tail(3).mean()
        avg_vol = df['volume'].tail(20).mean()
        
        if recent_vol > avg_vol * 1.5:
            if (signal_direction == 'LONG' and current['close'] > current['open']) or \
               (signal_direction == 'SHORT' and current['close'] < current['open']):
                score += 10
                reasons.append("🔥 High volume in signal direction")
            else:
                score -= 5
                reasons.append("⚠️ Volume against signal")
        
        # 3. RSI Check (+/- 10 points)
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss.replace(0, 1)
        rsi = 100 - (100 / (1 + rs))
        current_rsi = rsi.iloc[-1]
        
        if signal_direction == 'LONG':
            if current_rsi < 35:
                score += 10
                reasons.append(f"🎯 RSI oversold ({current_rsi:.0f})")
            elif current_rsi > 70:
                score -= 10
                reasons.append(f"⚠️ RSI overbought ({current_rsi:.0f})")
        else:
            if current_rsi > 65:
                score += 10
                reasons.append(f"🎯 RSI overbought ({current_rsi:.0f})")
            elif current_rsi < 30:
                score -= 10
                reasons.append(f"⚠️ RSI oversold ({current_rsi:.0f})")
        
        # 4. Recent price action (+/- 5 points)
        last_5_candles = df.tail(5)
        bullish_candles = len(last_5_candles[last_5_candles['close'] > last_5_candles['open']])
        
        if signal_direction == 'LONG' and bullish_candles >= 3:
            score += 5
            reasons.append("✨ Bullish momentum")
        elif signal_direction == 'SHORT' and bullish_candles <= 2:
            score += 5
            reasons.append("✨ Bearish momentum")
        
        # Cap score between 0-100
        score = max(0, min(100, score))
        
        return score, reasons
    
    def get_key_levels(self, df):
        """Identify key support/resistance levels."""
        if df is None or len(df) < 20:
            return {}
        
        current_price = df['close'].iloc[-1]
        
        # Recent high/low
        recent_high = df['high'].tail(24).max()
        recent_low = df['low'].tail(24).min()
        
        # Round levels
        round_levels = []
        base = int(current_price / 1000) * 1000
        for offset in [-2000, -1000, 0, 1000, 2000]:
            round_levels.append(base + offset)
        
        # Find nearest levels
        levels = {
            '24h_high': recent_high,
            '24h_low': recent_low,
            'nearest_round_above': min([l for l in round_levels if l > current_price], default=None),
            'nearest_round_below': max([l for l in round_levels if l < current_price], default=None),
        }
        
        return levels
    
    def run_analysis(self):
        """Run full AI analysis and return insights."""
        now = datetime.utcnow()
        
        # Fetch data
        df_1h = self.fetch_candles('1h', 100)
        df_15m = self.fetch_candles('15m', 96)  # 24 hours
        
        if df_1h is None:
            return None
        
        current_price = df_1h['close'].iloc[-1]
        
        # Analyze vectors
        vectors_1h = self.analyze_vectors(df_1h)
        
        # Get recent major vectors (last 24h)
        cutoff = now - timedelta(hours=24)
        recent_vectors = [v for v in vectors_1h if v['time'] > pd.Timestamp(cutoff, tz='UTC')]
        unrecovered = [v for v in recent_vectors if not v.get('recovered', True) and 'GREEN' in v['type'] or 'RED' in v['type']]
        
        # Calculate confidence for both directions
        long_confidence, long_reasons = self.calculate_confidence(df_1h, 'LONG')
        short_confidence, short_reasons = self.calculate_confidence(df_1h, 'SHORT')
        
        # Get key levels
        levels = self.get_key_levels(df_1h)
        
        # Determine trading window status
        if now.hour >= self.BRINKS_START and now.hour < self.BRINKS_END:
            window_status = "🔍 BRINKS BOX FORMING"
        elif now.hour >= self.BRINKS_END and now.hour < self.TRADING_END:
            window_status = "⏳ TRADING WINDOW OPEN"
        else:
            window_status = "💤 OUTSIDE TRADING HOURS"
        
        return {
            'price': current_price,
            'time': now,
            'window_status': window_status,
            'vectors_24h': len(recent_vectors),
            'unrecovered_vectors': unrecovered,
            'long_confidence': long_confidence,
            'long_reasons': long_reasons,
            'short_confidence': short_confidence,
            'short_reasons': short_reasons,
            'levels': levels,
        }
    
    def format_analysis_message(self, analysis):
        """Format analysis into a Telegram message."""
        if not analysis:
            return None
        
        # Determine bias
        if analysis['long_confidence'] > analysis['short_confidence'] + 10:
            bias = "📈 BULLISH"
            conf = analysis['long_confidence']
            reasons = analysis['long_reasons'][:3]
        elif analysis['short_confidence'] > analysis['long_confidence'] + 10:
            bias = "📉 BEARISH"
            conf = analysis['short_confidence']
            reasons = analysis['short_reasons'][:3]
        else:
            bias = "➡️ NEUTRAL"
            conf = 50
            reasons = ["No clear directional bias"]
        
        msg = f"""
🧠 *AI ADVISOR REPORT*

💰 BTC: *${analysis['price']:,.2f}*
⏰ {analysis['time'].strftime('%H:%M UTC')}
{analysis['window_status']}

*MARKET BIAS:* {bias}
*AI Confidence:* {conf}%

"""
        
        if reasons:
            msg += "*Why:*\n"
            for r in reasons:
                msg += f"• {r}\n"
        
        # Add unrecovered vectors
        if analysis['unrecovered_vectors']:
            msg += f"\n⚠️ *Unrecovered Vectors:* {len(analysis['unrecovered_vectors'])}\n"
            for v in analysis['unrecovered_vectors'][:2]:
                msg += f"• {v['type'][:10]} @ ${v['price']:,.0f}\n"
        
        # Key levels
        levels = analysis['levels']
        if levels.get('24h_high') and levels.get('24h_low'):
            msg += f"""
*Key Levels:*
🔺 24h High: ${levels['24h_high']:,.0f}
🔻 24h Low: ${levels['24h_low']:,.0f}
"""
        
        return msg
    
    def run(self, interval_minutes=30):
        """Main run loop."""
        startup_msg = f"""
🧠 *AI ADVISOR v{self.VERSION} STARTED*

Analyzing BTC/USDC market every {interval_minutes} minutes.

Providing:
• Market bias (bullish/bearish/neutral)
• Confidence scoring
• Vector candle detection
• Key level alerts

Running alongside INCEPTION Bot...
"""
        self.send_telegram(startup_msg)
        print(f"[{datetime.utcnow()}] AI Advisor v{self.VERSION} Started")
        print(f"Sending analysis every {interval_minutes} minutes...")
        
        while True:
            try:
                now = datetime.utcnow()
                
                # Run analysis at the start of trading sessions
                should_alert = False
                
                # Alert at key times: start of Brinks, start of trading window, and every hour during trading
                if now.hour == self.BRINKS_START and now.minute < 5:
                    should_alert = True  # Brinks start
                elif now.hour == self.BRINKS_END and now.minute < 5:
                    should_alert = True  # Trading window start
                elif now.hour >= self.BRINKS_END and now.hour < self.TRADING_END:
                    # During trading window, alert every interval
                    if self.last_alert_hour != now.hour or now.minute % interval_minutes < 2:
                        should_alert = True
                
                # Run analysis
                if should_alert and self.last_alert_hour != now.hour:
                    print(f"[{now.strftime('%H:%M:%S')}] Running AI analysis...")
                    analysis = self.run_analysis()
                    
                    if analysis:
                        msg = self.format_analysis_message(analysis)
                        if msg:
                            self.send_telegram(msg)
                            print(f"[{now.strftime('%H:%M:%S')}] Sent AI report")
                    
                    self.last_alert_hour = now.hour
                
                # Status log
                ticker = self.exchange.fetch_ticker(self.symbol)
                price = ticker['last']
                print(f"[{now.strftime('%H:%M:%S')}] 🧠 AI Advisor | BTC: ${price:,.0f}")
                
                time.sleep(60)  # Check every minute
                
            except KeyboardInterrupt:
                print("\n🛑 AI Advisor stopped")
                self.send_telegram("🛑 *AI Advisor stopped*")
                break
            except Exception as e:
                print(f"Error: {e}")
                time.sleep(30)


if __name__ == "__main__":
    print("""
    🧠 AI ADVISOR - Market Intelligence
    ===================================
    Running alongside INCEPTION Bot
    """)
    
    advisor = AIAdvisor()
    advisor.run(interval_minutes=30)
