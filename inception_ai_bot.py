"""
🧠 INCEPTION AI BOT v3.0
========================
AI-Powered trading with learned patterns.

Features:
- Uses BrinksAIStrategyV7 with 360-day learned patterns
- Shows confidence scores in Telegram updates
- Only trades when AI confidence > 55%
- Explains WHY it's taking each trade
"""

import ccxt
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import time
import json
import os
import sys
import requests

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from strategies.brinks_ai_v7 import BrinksAIStrategyV7


class InceptionAIBot:
    """INCEPTION Bot v3.0 - AI-Powered Trading."""
    
    VERSION = "3.0.0"
    
    # Credentials
    BINANCE_API_KEY = "HZHCu0fM6vxP4eDPkGGLpD6kHoksKPNTxceVDJusfjnsklwqne0dpzQ1vdbS3yrc"
    BINANCE_API_SECRET = "zZtxGRz9mWqvkIDquWPUdmltUbFPyibNzTNQmNoc6V2ep4VF9GdImZGj1W0dAAWi"
    TELEGRAM_BOT_TOKEN = "8371462261:AAELiZdXRedALn3KWblWq7Ce1ucYZP6LFrg"
    TELEGRAM_CHAT_ID = "345135704"
    
    def __init__(self):
        # Exchange
        self.exchange = ccxt.binanceusdm({
            'apiKey': self.BINANCE_API_KEY,
            'secret': self.BINANCE_API_SECRET,
            'enableRateLimit': True,
        })
        self.exchange.load_markets()
        self.symbol = 'BTC/USDC:USDC'
        
        # AI Strategy
        self.strategy = BrinksAIStrategyV7()
        
        # Config
        self.LEVERAGE = 10
        self.POSITION_SIZE_PCT = 0.025
        self.SL_PCT = 0.01
        self.TP_PCT = 0.021
        
        # State
        self.is_running = True
        self.is_trading_enabled = True
        self.position = None
        self.trades = []
        self.last_signal_date = None
        self.last_update_id = 0
        
        # Paths
        self.base_dir = os.path.dirname(os.path.abspath(__file__))
        self.state_file = os.path.join(self.base_dir, 'inception_ai_state.json')
        self.log_file = os.path.join(self.base_dir, 'inception_ai_trades.log')
    
    def send_telegram(self, message, chat_id=None):
        """Send Telegram message."""
        try:
            url = f"https://api.telegram.org/bot{self.TELEGRAM_BOT_TOKEN}/sendMessage"
            data = {
                "chat_id": chat_id or self.TELEGRAM_CHAT_ID,
                "text": message,
                "parse_mode": "Markdown"
            }
            requests.post(url, data=data, timeout=10)
        except Exception as e:
            print(f"Telegram error: {e}")
    
    def check_telegram_commands(self):
        """Check for Telegram commands."""
        try:
            url = f"https://api.telegram.org/bot{self.TELEGRAM_BOT_TOKEN}/getUpdates"
            params = {"offset": self.last_update_id + 1, "timeout": 1}
            response = requests.get(url, params=params, timeout=5)
            data = response.json()
            
            if not data.get('ok'):
                return
            
            for update in data.get('result', []):
                self.last_update_id = update['update_id']
                
                message = update.get('message', {})
                text = message.get('text', '').lower().strip()
                chat_id = message.get('chat', {}).get('id')
                
                if str(chat_id) != self.TELEGRAM_CHAT_ID:
                    continue
                
                if text == '/status':
                    self.cmd_status(chat_id)
                elif text == '/stop':
                    self.is_trading_enabled = False
                    self.send_telegram("🛑 *Trading STOPPED*", chat_id)
                elif text == '/start':
                    self.is_trading_enabled = True
                    self.send_telegram("🟢 *Trading STARTED*", chat_id)
                elif text == '/ai':
                    self.cmd_ai_status(chat_id)
                elif text == '/trades':
                    self.cmd_trades(chat_id)
                    
        except Exception as e:
            pass
    
    def cmd_status(self, chat_id):
        """Status command."""
        price = self.get_price()
        balance = self.get_balance()
        now = datetime.utcnow()
        
        status = "🧠 AI TRADING" if self.is_trading_enabled else "🔴 STOPPED"
        
        msg = f"""
🧠 *INCEPTION AI v{self.VERSION}*

{status}

💰 Balance: ${balance:,.2f}
📈 BTC: ${price:,.2f} if price else 0
⏰ Time: {now.strftime('%H:%M UTC')}
📊 Strategy: {self.strategy.get_name()}
🎯 Min Confidence: {self.strategy.MIN_CONFIDENCE}%
"""
        
        if self.position:
            unrealized = self._calc_unrealized(price)
            msg += f"""
🔥 *ACTIVE POSITION*
• Type: {self.position['type']}
• Entry: ${self.position['entry']:,.2f}
• Confidence: {self.position.get('confidence', 'N/A')}%
• Unrealized: {unrealized:+.1f}%
"""
        self.send_telegram(msg, chat_id)
    
    def cmd_ai_status(self, chat_id):
        """Show current AI analysis."""
        df = self.fetch_candles(200)
        if df is None:
            self.send_telegram("❌ Cannot fetch data", chat_id)
            return
        
        now = datetime.utcnow()
        weekday = now.weekday()
        weekday_names = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
        
        # Get today's probabilities
        bull_prob = self.strategy.WEEKDAY_BULL_PROB.get(weekday, 0.35) * 100
        bear_prob = self.strategy.WEEKDAY_BEAR_PROB.get(weekday, 0.35) * 100
        
        # Check conditions
        price = df['close'].iloc[-1]
        df['ema_200'] = df['close'].ewm(span=200, adjust=False).mean()
        above_200 = price > df['ema_200'].iloc[-1]
        
        msg = f"""
🧠 *AI MARKET ANALYSIS*

📅 Today: {weekday_names[weekday]}
• Bull Probability: {bull_prob:.0f}%
• Bear Probability: {bear_prob:.0f}%

📊 Current Conditions:
• Price vs 200 EMA: {'Above ✅' if above_200 else 'Below 📉'}

⭐ Best Setups Today:
"""
        if weekday == 1:  # Tuesday
            msg += "• LONG trades have edge (43% win rate)\n"
        if weekday == 0:  # Monday
            msg += "• SHORT trades have edge (43% win rate)\n"
        if weekday == 3 and not above_200:  # Thursday below 200
            msg += "• ⭐ BEST BEAR SETUP (62.5%)\n"
        if weekday == 2:  # Wednesday
            msg += "• ⚠️ Low predictability day\n"
        
        self.send_telegram(msg, chat_id)
    
    def cmd_trades(self, chat_id):
        """Show recent trades with AI info."""
        if not self.trades:
            self.send_telegram("📋 No trades yet.", chat_id)
            return
        
        msg = "📋 *RECENT AI TRADES*\n\n"
        for t in self.trades[-5:]:
            emoji = "✅" if t['result'] == 'WIN' else "❌"
            msg += f"{emoji} {t['type']} | {t['pnl_pct']:+.1f}% | Conf: {t.get('confidence', 'N/A')}%\n"
        
        wins = len([t for t in self.trades if t['result'] == 'WIN'])
        total = len(self.trades)
        msg += f"\n📊 Win Rate: {wins}/{total} ({wins/total*100:.0f}%)" if total > 0 else ""
        
        self.send_telegram(msg, chat_id)
    
    def _calc_unrealized(self, price):
        if not self.position or not price:
            return 0
        if self.position['type'] == 'LONG':
            return (price - self.position['entry']) / self.position['entry'] * self.LEVERAGE * 100
        else:
            return (self.position['entry'] - price) / self.position['entry'] * self.LEVERAGE * 100
    
    def get_balance(self):
        try:
            balance = self.exchange.fetch_balance()
            usdc = float(balance.get('USDC', {}).get('free', 0) or 0)
            if usdc > 0:
                return usdc
            usdc_total = float(balance.get('USDC', {}).get('total', 0) or 0)
            if usdc_total > 0:
                return usdc_total
            return float(balance.get('USDT', {}).get('free', 0) or 0)
        except:
            return 0
    
    def get_price(self):
        try:
            ticker = self.exchange.fetch_ticker(self.symbol)
            return ticker['last']
        except:
            return None
    
    def fetch_candles(self, limit=200):
        try:
            ohlcv = self.exchange.fetch_ohlcv(self.symbol, '1h', limit=limit)
            df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms', utc=True)
            df.set_index('timestamp', inplace=True)
            return df
        except:
            return None
    
    def check_signal(self):
        """Check for AI signals with confidence."""
        df = self.fetch_candles(200)
        if df is None:
            return None
        
        signals = self.strategy.generate_signals(df)
        latest = signals.iloc[-1]
        
        if latest != 0:
            info = self.strategy.get_last_decision_info()
            return {
                'signal': latest,
                'price': df['close'].iloc[-1],
                'confidence': info['confidence'],
                'reasons': info['reasons']
            }
        return None
    
    def open_position(self, signal_data):
        """Open position with AI reasoning."""
        price = signal_data['price']
        trade_type = 'LONG' if signal_data['signal'] == 1.0 else 'SHORT'
        confidence = signal_data['confidence']
        reasons = signal_data['reasons']
        
        balance = self.get_balance()
        if balance < 10:
            self.send_telegram("❌ Insufficient balance!")
            return
        
        position_value = balance * self.POSITION_SIZE_PCT
        
        if trade_type == 'LONG':
            sl = price * (1 - self.SL_PCT)
            tp = price * (1 + self.TP_PCT)
        else:
            sl = price * (1 + self.SL_PCT)
            tp = price * (1 - self.TP_PCT)
        
        self.position = {
            'type': trade_type,
            'entry': price,
            'sl': sl,
            'tp': tp,
            'value': position_value,
            'confidence': confidence,
            'reasons': reasons,
            'entry_time': datetime.utcnow().isoformat(),
        }
        
        reasons_text = "\n".join([f"• {r}" for r in reasons[:4]])
        
        msg = f"""
🧠 *AI TRADE OPENED*

📊 Type: *{trade_type}*
🎯 Confidence: *{confidence:.0f}%*

💰 Entry: ${price:,.2f}
🛑 SL: ${sl:,.2f}
🎯 TP: ${tp:,.2f}

*AI Reasoning:*
{reasons_text}
"""
        self.send_telegram(msg)
        self.save_state()
    
    def check_position(self):
        if not self.position:
            return
        
        price = self.get_price()
        if not price:
            return
        
        sl = self.position['sl']
        tp = self.position['tp']
        trade_type = self.position['type']
        
        result = None
        exit_price = None
        
        if trade_type == 'LONG':
            if price <= sl:
                result, exit_price = 'LOSS', sl
            elif price >= tp:
                result, exit_price = 'WIN', tp
        else:
            if price >= sl:
                result, exit_price = 'LOSS', sl
            elif price <= tp:
                result, exit_price = 'WIN', tp
        
        if result:
            self.close_position(result, exit_price)
    
    def close_position(self, result, exit_price):
        entry = self.position['entry']
        trade_type = self.position['type']
        confidence = self.position.get('confidence', 50)
        
        if trade_type == 'LONG':
            pnl_pct = (exit_price - entry) / entry * self.LEVERAGE * 100
        else:
            pnl_pct = (entry - exit_price) / entry * self.LEVERAGE * 100
        
        pnl_value = self.position['value'] * (pnl_pct / 100)
        
        trade = {
            'type': trade_type,
            'entry': entry,
            'exit': exit_price,
            'result': result,
            'pnl_pct': pnl_pct,
            'pnl_value': pnl_value,
            'confidence': confidence,
        }
        self.trades.append(trade)
        
        emoji = "✅" if result == "WIN" else "🛑"
        accuracy = "✅ AI was right!" if result == "WIN" else "❌ AI needs learning"
        
        msg = f"""
{emoji} *{'TAKE PROFIT' if result == 'WIN' else 'STOP LOSS'}*

📊 {trade_type}
💰 Entry: ${entry:,.2f}
💵 Exit: ${exit_price:,.2f}
📈 PnL: *{pnl_pct:+.1f}%* (${pnl_value:+,.2f})

🧠 AI Confidence was: {confidence:.0f}%
{accuracy}
"""
        self.send_telegram(msg)
        
        self.position = None
        self.save_state()
    
    def save_state(self):
        state = {
            'position': self.position,
            'trades': self.trades[-100:],
            'last_signal_date': self.last_signal_date,
        }
        with open(self.state_file, 'w') as f:
            json.dump(state, f, default=str)
    
    def load_state(self):
        if os.path.exists(self.state_file):
            with open(self.state_file, 'r') as f:
                state = json.load(f)
                self.position = state.get('position')
                self.trades = state.get('trades', [])
                self.last_signal_date = state.get('last_signal_date')
    
    def run(self):
        """Main run loop."""
        msg = f"""
🧠 *INCEPTION AI v{self.VERSION} STARTED*

📱 *Commands:*
/status - Current status
/ai - AI market analysis
/start - Enable trading
/stop - Disable trading
/trades - Recent trades

🎯 Min Confidence: {self.strategy.MIN_CONFIDENCE}%
📊 Strategy: {self.strategy.get_name()}

⏳ AI analyzing patterns...
"""
        self.send_telegram(msg)
        
        print(f"[{datetime.utcnow()}] INCEPTION AI v{self.VERSION} STARTED")
        print(f"Strategy: {self.strategy.get_name()}")
        print(f"Min Confidence: {self.strategy.MIN_CONFIDENCE}%")
        
        self.load_state()
        
        while self.is_running:
            try:
                self.check_telegram_commands()
                
                now = datetime.utcnow()
                today = now.strftime('%Y-%m-%d')
                
                if self.position:
                    self.check_position()
                
                elif self.is_trading_enabled:
                    if now.hour >= 15 and now.hour < 20:
                        if self.last_signal_date != today:
                            signal = self.check_signal()
                            if signal:
                                self.open_position(signal)
                                self.last_signal_date = today
                
                price = self.get_price()
                status = "🧠" if self.is_trading_enabled else "🔴"
                pos = f"| {self.position['type']} @ ${self.position['entry']:,.0f}" if self.position else "| No position"
                print(f"[{now.strftime('%H:%M:%S')}] {status} BTC: ${price:,.0f} {pos}")
                
                time.sleep(30)
                
            except KeyboardInterrupt:
                print("\n🛑 Bot stopped")
                self.send_telegram("🛑 *AI Bot stopped*")
                self.save_state()
                break
            except Exception as e:
                print(f"Error: {e}")
                time.sleep(30)


if __name__ == "__main__":
    print("""
    🧠 INCEPTION AI BOT v3.0
    ========================
    AI-Powered Trading with Learned Patterns
    """)
    
    bot = InceptionAIBot()
    bot.run()
