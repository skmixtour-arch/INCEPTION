"""
██╗███╗   ██╗ ██████╗███████╗██████╗ ████████╗██╗ ██████╗ ███╗   ██╗
██║████╗  ██║██╔════╝██╔════╝██╔══██╗╚══██╔══╝██║██╔═══██╗████╗  ██║
██║██╔██╗ ██║██║     █████╗  ██████╔╝   ██║   ██║██║   ██║██╔██╗ ██║
██║██║╚██╗██║██║     ██╔══╝  ██╔═══╝    ██║   ██║██║   ██║██║╚██╗██║
██║██║ ╚████║╚██████╗███████╗██║        ██║   ██║╚██████╔╝██║ ╚████║
╚═╝╚═╝  ╚═══╝ ╚═════╝╚══════╝╚═╝        ╚═╝   ╚═╝ ╚═════╝ ╚═╝  ╚═══╝

INCEPTION Trading Bot v3.0 - LIVE TRADING
Strategy: Brinks Box V6 (Breakout Detection)
Telegram Commands: /status /stop /start /balance /trades
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
from strategies.brinks_box_v6 import BrinksBoxStrategyV6


class InceptionBotLive:
    """INCEPTION Bot v3.0 - LIVE TRADING with Real Orders on Binance Futures"""
    
    VERSION = "3.0.0"
    
    # === CREDENTIALS (Edit these) ===
    BINANCE_API_KEY = "xoLxpdAmRcnS7RT9Ny9tNJFhMD9GZTotzAlLkjfZi1D0VDhHXXW9Zvi5YgAk5yvm"
    BINANCE_API_SECRET = "85ecGU87TGJadp7k0aAK4XZXbl1PdA35QWzfePzIYyBTv4roeiDYUfb4UYVMbc3P"
    TELEGRAM_BOT_TOKEN = "8371462261:AAELiZdXRedALn3KWblWq7Ce1ucYZP6LFrg"
    TELEGRAM_CHAT_ID = "345135704"
    
    # === TRADING CONFIG ===
    SYMBOL = "BTC/USDC:USDC"
    LEVERAGE = 10
    POSITION_SIZE_PCT = 0.50  # 50% of balance per trade
    SL_PCT = 0.01             # 1% stop loss
    TP_PCT = 0.021            # 2.1% take profit
    
    def __init__(self):
        # Trading config (instance variables)
        self.symbol = self.SYMBOL
        self.LEVERAGE = self.LEVERAGE
        self.POSITION_SIZE_PCT = self.POSITION_SIZE_PCT
        self.SL_PCT = self.SL_PCT
        self.TP_PCT = self.TP_PCT
        
        # Exchange connection
        self.exchange = ccxt.binanceusdm({
            'apiKey': self.BINANCE_API_KEY,
            'secret': self.BINANCE_API_SECRET,
            'enableRateLimit': True,
        })
        self.exchange.load_markets()
        
        # Set leverage
        self._set_leverage()
        
        # Strategy
        self.strategy = BrinksBoxStrategyV6()
        
        # State
        self.is_running = True
        self.is_trading_enabled = True
        self.position = None
        self.trades = []
        self.last_signal_date = None
        self.last_update_id = 0
        self.brinks_high = None
        self.brinks_low = None
        self.pending_orders = None  # Track pending breakout orders
        self.orders_placed_date = None  # Track when orders were placed
        
        # Paths
        self.base_dir = os.path.dirname(os.path.abspath(__file__))
        self.state_file = os.path.join(self.base_dir, 'inception_state.json')
        self.log_file = os.path.join(self.base_dir, 'inception_trades.log')
    
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
                text = message.get('text', '')
                chat_id = message.get('chat', {}).get('id')
                
                # Only respond to authorized user
                if str(chat_id) != self.TELEGRAM_CHAT_ID:
                    continue
                
                self.handle_command(text, chat_id)
                
        except Exception as e:
            pass  # Silent fail for polling
    
    def handle_command(self, text, chat_id):
        """Handle Telegram commands."""
        text = text.lower().strip()
        
        if text == '/status':
            self.cmd_status(chat_id)
        elif text == '/balance':
            self.cmd_balance(chat_id)
        elif text == '/stop':
            self.cmd_stop(chat_id)
        elif text == '/start':
            self.cmd_start(chat_id)
        elif text == '/trades':
            self.cmd_trades(chat_id)
        elif text == '/help':
            self.cmd_help(chat_id)
        elif text.startswith('/'):
            self.send_telegram("❓ Unknown command. Type /help for list.", chat_id)
    
    def cmd_status(self, chat_id):
        """Status command."""
        price = self.get_price()
        balance = self.get_balance()
        now = datetime.utcnow()
        
        status = "🟢 TRADING" if self.is_trading_enabled else "🔴 STOPPED"
        
        msg = f"""
📊 *INCEPTION BOT STATUS*

{status}

💰 Balance: ${balance:,.2f}
📈 BTC: ${price:,.2f if price else 0}
⏰ Time: {now.strftime('%H:%M UTC')}
"""
        
        if self.position:
            unrealized = self._calc_unrealized(price)
            msg += f"""
🔥 *ACTIVE POSITION*
• Type: {self.position['type']}
• Entry: ${self.position['entry']:,.2f}
• SL: ${self.position['sl']:,.2f}
• TP: ${self.position['tp']:,.2f}
• Unrealized: {unrealized:+.1f}%
"""
        else:
            if now.hour >= 14 and now.hour < 15:
                msg += "\n🔍 Brinks Box ACTIVE - Analyzing..."
            elif now.hour >= 15 and now.hour < 20:
                msg += "\n⏳ Trading window OPEN"
            else:
                msg += "\n💤 Outside trading window"
        
        self.send_telegram(msg, chat_id)
    
    def cmd_balance(self, chat_id):
        """Balance command."""
        balance = self.get_balance()
        msg = f"""
💰 *BALANCE*

USDT: ${balance:,.2f}
"""
        self.send_telegram(msg, chat_id)
    
    def cmd_stop(self, chat_id):
        """Stop trading command."""
        self.is_trading_enabled = False
        self.send_telegram("🛑 *Trading STOPPED*\nBot will not open new positions.\nUse /start to resume.", chat_id)
    
    def cmd_start(self, chat_id):
        """Start trading command."""
        self.is_trading_enabled = True
        self.send_telegram("🟢 *Trading STARTED*\nBot will look for signals.", chat_id)
    
    def cmd_trades(self, chat_id):
        """Show recent trades."""
        if not self.trades:
            self.send_telegram("📋 No trades yet.", chat_id)
            return
        
        msg = "📋 *RECENT TRADES*\n\n"
        for t in self.trades[-5:]:
            emoji = "✅" if t['result'] == 'WIN' else "❌"
            msg += f"{emoji} {t['type']} | {t['pnl_pct']:+.1f}%\n"
        
        wins = len([t for t in self.trades if t['result'] == 'WIN'])
        total = len(self.trades)
        msg += f"\n📊 Win Rate: {wins}/{total} ({wins/total*100:.0f}%)" if total > 0 else ""
        
        self.send_telegram(msg, chat_id)
    
    def cmd_help(self, chat_id):
        """Help command."""
        msg = """
🤖 *INCEPTION BOT COMMANDS*

/status - Current status
/balance - Check balance
/start - Enable trading
/stop - Disable trading
/trades - Recent trades
/help - This message
"""
        self.send_telegram(msg, chat_id)
    
    def _calc_unrealized(self, price):
        """Calculate unrealized PnL."""
        if not self.position or not price:
            return 0
        if self.position['type'] == 'LONG':
            return (price - self.position['entry']) / self.position['entry'] * self.LEVERAGE * 100
        else:
            return (self.position['entry'] - price) / self.position['entry'] * self.LEVERAGE * 100
    
    def get_balance(self):
        try:
            balance = self.exchange.fetch_balance()
            # Check USDC first (for BTC/USDC pair), fallback to USDT
            usdc = float(balance.get('USDC', {}).get('free', 0) or 0)
            if usdc > 0:
                return usdc
            # If USDC is 0, check total (might be in margin)
            usdc_total = float(balance.get('USDC', {}).get('total', 0) or 0)
            if usdc_total > 0:
                return usdc_total
            # Fallback to USDT
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
        """Check for Brinks box breakout in real-time."""
        df = self.fetch_candles(200)
        if df is None:
            return None
        
        now = datetime.utcnow()
        today = now.date()
        
        # Get today's data
        today_data = df[df.index.date == today]
        if today_data.empty:
            return None
        
        # Get Brinks Box (14:00-15:00 UTC)
        brinks = today_data[(today_data.index.hour >= 14) & (today_data.index.hour < 15)]
        if brinks.empty:
            return None
        
        brinks_high = brinks['high'].max()
        brinks_low = brinks['low'].min()
        
        # Get current price
        current_price = self.get_price()
        if not current_price:
            return None
        
        # Store brinks levels for display
        self.brinks_high = brinks_high
        self.brinks_low = brinks_low
        
        # Check for breakout
        signal = 0.0
        
        if current_price > brinks_high:
            signal = 1.0  # LONG - price broke above Brinks box
            print(f"🔺 BREAKOUT UP: ${current_price:,.2f} > Brinks High ${brinks_high:,.2f}")
        elif current_price < brinks_low:
            signal = -1.0  # SHORT - price broke below Brinks box
            print(f"🔻 BREAKOUT DOWN: ${current_price:,.2f} < Brinks Low ${brinks_low:,.2f}")
        else:
            print(f"📊 Price ${current_price:,.2f} inside Brinks Box [${brinks_low:,.2f} - ${brinks_high:,.2f}]")
        
        return {'signal': signal, 'price': current_price, 'brinks_high': brinks_high, 'brinks_low': brinks_low}
    
    def place_breakout_orders(self):
        """Place pending stop orders at Brinks box levels for exact breakout entry."""
        df = self.fetch_candles(50)
        if df is None:
            return False
        
        now = datetime.utcnow()
        today = now.date()
        
        # Get today's Brinks Box (14:00-15:00 UTC)
        today_data = df[df.index.date == today]
        brinks = today_data[(today_data.index.hour >= 14) & (today_data.index.hour < 15)]
        
        if brinks.empty:
            print("⚠️ No Brinks box data yet")
            return False
        
        brinks_high = brinks['high'].max()
        brinks_low = brinks['low'].min()
        self.brinks_high = brinks_high
        self.brinks_low = brinks_low
        
        # Get balance and calculate position size
        balance = self.get_balance()
        if balance < 10:
            self.send_telegram("❌ Insufficient balance for breakout orders")
            return False
        
        position_value = balance * self.POSITION_SIZE_PCT
        notional_value = position_value * self.LEVERAGE
        
        # Calculate amount for LONG (at brinks high)
        amount_long = round(notional_value / brinks_high, 3)
        # Calculate amount for SHORT (at brinks low)  
        amount_short = round(notional_value / brinks_low, 3)
        
        # Ensure minimum notional ($100)
        if amount_long * brinks_high < 100:
            amount_long = round(105 / brinks_high, 3)
        if amount_short * brinks_low < 100:
            amount_short = round(105 / brinks_low, 3)
        
        # Add small buffer to breakout levels (0.05%)
        long_entry = round(brinks_high * 1.0005, 2)
        short_entry = round(brinks_low * 0.9995, 2)
        
        try:
            # Cancel any existing pending orders first
            self.exchange.cancel_all_orders(self.symbol)
            
            # Place LONG breakout order (BUY STOP at Brinks High)
            long_order = self.exchange.create_order(
                symbol=self.symbol,
                type='STOP_MARKET',
                side='buy',
                amount=amount_long,
                params={
                    'stopPrice': long_entry,
                    'positionSide': 'LONG'
                }
            )
            
            # Place SHORT breakout order (SELL STOP at Brinks Low)
            short_order = self.exchange.create_order(
                symbol=self.symbol,
                type='STOP_MARKET',
                side='sell',
                amount=amount_short,
                params={
                    'stopPrice': short_entry,
                    'positionSide': 'SHORT'
                }
            )
            
            self.pending_orders = {
                'long_order_id': long_order.get('id'),
                'short_order_id': short_order.get('id'),
                'long_entry': long_entry,
                'short_entry': short_entry,
                'amount_long': amount_long,
                'amount_short': amount_short,
                'brinks_high': brinks_high,
                'brinks_low': brinks_low
            }
            self.orders_placed_date = now.strftime('%Y-%m-%d')
            
            msg = f"""
🎯 *BREAKOUT ORDERS PLACED*

📈 LONG trigger: ${long_entry:,.2f}
📉 SHORT trigger: ${short_entry:,.2f}

📦 Brinks Box:
  High: ${brinks_high:,.2f}
  Low: ${brinks_low:,.2f}

⏳ Waiting for breakout...
"""
            self.send_telegram(msg)
            print(f"✅ Breakout orders placed: LONG@${long_entry:,.2f} | SHORT@${short_entry:,.2f}")
            return True
            
        except Exception as e:
            self.send_telegram(f"❌ Failed to place breakout orders: {str(e)}")
            print(f"Order error: {e}")
            return False

    def _set_leverage(self):
        """Set leverage for the trading pair."""
        try:
            # Binance requires setting leverage per symbol
            market = self.exchange.market(self.symbol)
            self.exchange.set_leverage(self.LEVERAGE, market['id'])
            print(f"Leverage set to {self.LEVERAGE}x")
        except Exception as e:
            print(f"Leverage setting error (may already be set): {e}")
    
    def _set_sl_tp_for_position(self, trade_type, entry_price, amount):
        """Set SL/TP orders for an existing position."""
        try:
            if trade_type == 'LONG':
                sl_price = round(entry_price * (1 - self.SL_PCT), 2)
                tp_price = round(entry_price * (1 + self.TP_PCT), 2)
                sl_side = 'sell'
                position_side = 'LONG'
            else:
                sl_price = round(entry_price * (1 + self.SL_PCT), 2)
                tp_price = round(entry_price * (1 - self.TP_PCT), 2)
                sl_side = 'buy'
                position_side = 'SHORT'
            
            # Place stop-loss
            self.exchange.create_order(
                symbol=self.symbol,
                type='STOP_MARKET',
                side=sl_side,
                amount=amount,
                params={
                    'stopPrice': sl_price,
                    'positionSide': position_side,
                    'closePosition': True
                }
            )
            
            # Place take-profit
            self.exchange.create_order(
                symbol=self.symbol,
                type='TAKE_PROFIT_MARKET',
                side=sl_side,
                amount=amount,
                params={
                    'stopPrice': tp_price,
                    'positionSide': position_side,
                    'closePosition': True
                }
            )
            
            self.send_telegram(f"✅ SL/TP set:\n🛑 SL: ${sl_price:,.2f}\n🎯 TP: ${tp_price:,.2f}")
            return True
        except Exception as e:
            self.send_telegram(f"⚠️ Failed to set SL/TP: {e}")
            return False
    
    def open_position(self, signal_data):
        """Open a REAL position on Binance with stop-loss."""
        price = signal_data['price']
        trade_type = 'LONG' if signal_data['signal'] == 1.0 else 'SHORT'
        side = 'buy' if trade_type == 'LONG' else 'sell'
        
        balance = self.get_balance()
        if balance < 10:
            self.send_telegram("❌ Insufficient balance!")
            return
        
        # Calculate position size
        position_value = balance * self.POSITION_SIZE_PCT
        # With leverage, we can trade larger notional value
        notional_value = position_value * self.LEVERAGE
        amount = notional_value / price
        
        # Round to Binance precision (3 decimals for BTC)
        amount = round(amount, 3)
        
        # Ensure minimum notional value of $100
        if amount * price < 100:
            amount = round(105 / price, 3)  # Set to just above $100
        
        if amount < 0.001:
            self.send_telegram("❌ Position too small (min 0.001 BTC)")
            return
        
        # Calculate SL/TP prices
        if trade_type == 'LONG':
            sl_price = round(price * (1 - self.SL_PCT), 2)
            tp_price = round(price * (1 + self.TP_PCT), 2)
        else:
            sl_price = round(price * (1 + self.SL_PCT), 2)
            tp_price = round(price * (1 - self.TP_PCT), 2)
        
        try:
            # 1. Open market order (with Hedge Mode support)
            self.send_telegram(f"⏳ Opening {trade_type} position...")
            
            position_side = 'LONG' if trade_type == 'LONG' else 'SHORT'
            order = self.exchange.create_market_order(
                symbol=self.symbol,
                side=side,
                amount=amount,
                params={'positionSide': position_side}
            )
            
            entry_price = float(order.get('average', order.get('price', price)))
            
            # 2. Place stop-loss order
            sl_side = 'sell' if trade_type == 'LONG' else 'buy'
            sl_order = self.exchange.create_order(
                symbol=self.symbol,
                type='STOP_MARKET',
                side=sl_side,
                amount=amount,
                params={
                    'stopPrice': sl_price,
                    'positionSide': position_side,
                    'closePosition': True
                }
            )
            
            # 3. Place take-profit order
            tp_order = self.exchange.create_order(
                symbol=self.symbol,
                type='TAKE_PROFIT_MARKET',
                side=sl_side,
                amount=amount,
                params={
                    'stopPrice': tp_price,
                    'positionSide': position_side,
                    'closePosition': True
                }
            )
            
            # 4. VERIFY orders were placed
            if not sl_order.get('id') or not tp_order.get('id'):
                # Orders failed - close position immediately!
                self.send_telegram("⚠️ SL/TP orders failed! Closing position...")
                self.exchange.create_market_order(
                    symbol=self.symbol,
                    side=sl_side,
                    amount=amount,
                    params={'positionSide': position_side}
                )
                self.send_telegram("🛑 Position closed - SL/TP could not be placed")
                return
            
            # Save position state
            self.position = {
                'type': trade_type,
                'entry': entry_price,
                'sl': sl_price,
                'tp': tp_price,
                'amount': amount,
                'value': position_value,
                'entry_time': datetime.utcnow().isoformat(),
                'order_id': order.get('id'),
                'sl_order_id': sl_order.get('id'),
                'tp_order_id': tp_order.get('id'),
            }
            
            msg = f"""
🚀 *LIVE POSITION OPENED*

📊 Type: *{trade_type}*
📦 Size: {amount} BTC
💰 Entry: ${entry_price:,.2f}
🛑 SL: ${sl_price:,.2f} (-{self.SL_PCT*100}%)
🎯 TP: ${tp_price:,.2f} (+{self.TP_PCT*100}%)
💵 Value: ${position_value:,.2f}
⚡ Leverage: {self.LEVERAGE}x
✅ SL/TP Orders Verified
"""
            self.send_telegram(msg)
            self.save_state()
            
        except Exception as e:
            error_msg = f"❌ *ORDER FAILED*\n\n{str(e)}"
            self.send_telegram(error_msg)
            print(f"Order error: {e}")
    
    def check_position(self):
        """Check if position is still open on Binance and sync state."""
        if not self.position:
            return
        
        try:
            # Check actual positions on Binance
            positions = self.exchange.fetch_positions([self.symbol])
            
            # Find our position
            real_position = None
            for pos in positions:
                if pos['symbol'] == self.symbol and float(pos.get('contracts', 0)) != 0:
                    real_position = pos
                    break
            
            # If no real position exists but we have local state, position was closed (SL/TP hit)
            if real_position is None:
                # Position was closed by SL or TP
                price = self.get_price()
                sl = self.position['sl']
                tp = self.position['tp']
                entry = self.position['entry']
                trade_type = self.position['type']
                
                # Determine if it was SL or TP based on price distance
                if trade_type == 'LONG':
                    sl_dist = abs(price - sl)
                    tp_dist = abs(price - tp)
                    if sl_dist < tp_dist:
                        result, exit_price = 'LOSS', sl
                    else:
                        result, exit_price = 'WIN', tp
                else:
                    sl_dist = abs(price - sl)
                    tp_dist = abs(price - tp)
                    if sl_dist < tp_dist:
                        result, exit_price = 'LOSS', sl
                    else:
                        result, exit_price = 'WIN', tp
                
                self.close_position(result, exit_price)
                return
            
            # Position still exists - update unrealized PnL info
            unrealized_pnl = float(real_position.get('unrealizedPnl', 0))
            current_price = self.get_price()
            
            # Log current status
            pnl_pct = self._calc_unrealized(current_price) if current_price else 0
            print(f"Position: {self.position['type']} | Unrealized: {pnl_pct:+.1f}% | ${unrealized_pnl:+.2f}")
            
        except Exception as e:
            print(f"Position check error: {e}")
    
    def close_position(self, result, exit_price):
        """Record position close (position already closed by SL/TP on exchange)."""
        entry = self.position['entry']
        trade_type = self.position['type']
        
        if trade_type == 'LONG':
            pnl_pct = (exit_price - entry) / entry * self.LEVERAGE * 100
        else:
            pnl_pct = (entry - exit_price) / entry * self.LEVERAGE * 100
        
        pnl_value = self.position['value'] * (pnl_pct / 100)
        
        # Cancel any remaining SL/TP orders
        try:
            self.exchange.cancel_all_orders(self.symbol)
        except:
            pass
        
        trade = {
            'type': trade_type,
            'entry': entry,
            'exit': exit_price,
            'result': result,
            'pnl_pct': pnl_pct,
            'pnl_value': pnl_value,
            'closed_at': datetime.utcnow().isoformat(),
        }
        self.trades.append(trade)
        
        emoji = "✅" if result == "WIN" else "🛑"
        msg = f"""
{emoji} *{'TAKE PROFIT' if result == 'WIN' else 'STOP LOSS'} HIT*

📊 {trade_type}
💰 Entry: ${entry:,.2f}
💵 Exit: ${exit_price:,.2f}
📈 PnL: *{pnl_pct:+.1f}%* (${pnl_value:+,.2f})
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
            json.dump(state, f)
    
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
🤖 *INCEPTION BOT v{self.VERSION} STARTED*

📱 *Telegram Commands:*
/status - Current status
/balance - Check balance
/start - Enable trading
/stop - Disable trading
/trades - Recent trades

⏳ Waiting for Brinks Box...
"""
        self.send_telegram(msg)
        
        print(f"[{datetime.utcnow()}] INCEPTION BOT v{self.VERSION} STARTED")
        print("Telegram commands active: /status /stop /start /balance /trades")
        
        self.load_state()
        
        while self.is_running:
            try:
                # Check Telegram commands
                self.check_telegram_commands()
                
                now = datetime.utcnow()
                today = now.strftime('%Y-%m-%d')
                
                # Check existing position
                if self.position:
                    self.check_position()
                
                # Trading logic (if enabled)
                elif self.is_trading_enabled:
                    # At 15:00 UTC - place pending breakout orders
                    if now.hour == 15 and now.minute < 5:
                        if self.orders_placed_date != today:
                            self.place_breakout_orders()
                    
                    # During trading window - check if orders filled
                    elif now.hour >= 15 and now.hour < 20:
                        if self.pending_orders:
                            # Check if a position was opened by our pending orders
                            positions = self.exchange.fetch_positions([self.symbol])
                            for p in positions:
                                contracts = float(p.get('contracts', 0))
                                if contracts != 0:
                                    # Position opened! Cancel opposite order and set SL/TP
                                    side = p.get('side', '')
                                    entry_price = float(p.get('entryPrice', 0))
                                    
                                    self.exchange.cancel_all_orders(self.symbol)
                                    
                                    trade_type = 'LONG' if side == 'long' else 'SHORT'
                                    self.send_telegram(f"🚀 *{trade_type} BREAKOUT!*\nEntry: ${entry_price:,.2f}")
                                    
                                    # Set SL/TP for the new position
                                    self._set_sl_tp_for_position(trade_type, entry_price, abs(contracts))
                                    
                                    self.position = {
                                        'type': trade_type,
                                        'entry': entry_price,
                                        'amount': abs(contracts),
                                        'entry_time': datetime.utcnow().isoformat()
                                    }
                                    self.pending_orders = None
                                    self.last_signal_date = today
                                    self.save_state()
                                    break
                
                # Status print
                price = self.get_price()
                status = "🟢" if self.is_trading_enabled else "🔴"
                pos = f"| {self.position['type']} @ ${self.position['entry']:,.0f}" if self.position else "| No position"
                pending = " | Pending orders" if self.pending_orders else ""
                print(f"[{now.strftime('%H:%M:%S')}] {status} BTC: ${price:,.0f} {pos}{pending}")
                
                # Faster polling during trading window (10 sec), otherwise 30 sec
                sleep_time = 10 if (now.hour >= 15 and now.hour < 20) else 30
                time.sleep(sleep_time)
                
            except KeyboardInterrupt:
                print("\n🛑 Bot stopped")
                self.send_telegram("🛑 *Bot stopped*")
                self.save_state()
                break
            except Exception as e:
                print(f"Error: {e}")
                time.sleep(30)


if __name__ == "__main__":
    print("""
    ██╗███╗   ██╗ ██████╗███████╗██████╗ ████████╗██╗ ██████╗ ███╗   ██╗
    ██║████╗  ██║██╔════╝██╔════╝██╔══██╗╚══██╔══╝██║██╔═══██╗████╗  ██║
    ██║██╔██╗ ██║██║     █████╗  ██████╔╝   ██║   ██║██║   ██║██╔██╗ ██║
    ██║██║╚██╗██║██║     ██╔══╝  ██╔═══╝    ██║   ██║██║   ██║██║╚██╗██║
    ██║██║ ╚████║╚██████╗███████╗██║        ██║   ██║╚██████╔╝██║ ╚████║
    ╚═╝╚═╝  ╚═══╝ ╚═════╝╚══════╝╚═╝        ╚═╝   ╚═╝ ╚═════╝ ╚═╝  ╚═══╝
    
    V3.0 - LIVE TRADING ON BINANCE FUTURES
    """)
    
    bot = InceptionBotLive()
    bot.run()

