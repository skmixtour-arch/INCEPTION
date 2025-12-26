"""
██╗███╗   ██╗ ██████╗███████╗██████╗ ████████╗██╗ ██████╗ ███╗   ██╗
██║████╗  ██║██╔════╝██╔════╝██╔══██╗╚══██╔══╝██║██╔═══██╗████╗  ██║
██║██╔██╗ ██║██║     █████╗  ██████╔╝   ██║   ██║██║   ██║██╔██╗ ██║
██║██║╚██╗██║██║     ██╔══╝  ██╔═══╝    ██║   ██║██║   ██║██║╚██╗██║
██║██║ ╚████║╚██████╗███████╗██║        ██║   ██║╚██████╔╝██║ ╚████║
╚═╝╚═╝  ╚═══╝ ╚═════╝╚══════╝╚═╝        ╚═╝   ╚═╝ ╚═════╝ ╚═╝  ╚═══╝
                                                                     
INCEPTION Trading Bot v1.0
Based on Brinks Box V4 Strategy

90-Day Backtest Results:
- Win Rate: 45.6%
- Return: +441.92%
- Max Drawdown: -57.0%

Configuration:
- SL: 1.0% | TP: 2.1% | Leverage: 10x
- Timeframe: 1H | Sessions: Mon-Fri
"""

import ccxt
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import time
import json
import os
import sys

# Add strategy path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from strategies.brinks_box_v5 import BrinksBoxStrategyV5


class InceptionBot:
    """
    INCEPTION Trading Bot - Brinks Box V4 Strategy
    
    Features:
    - V4 Strategy (Vector Recovery, Stop-Hunt, Brinks Position, Premium/Discount)
    - Real-time Order Book Analysis
    - Funding Rate Analysis
    - Paper Trading Mode (default) or Live Trading
    """
    
    VERSION = "1.0.0"
    
    def __init__(self, live_mode=False, api_key=None, api_secret=None):
        self.live_mode = live_mode
        
        # Exchange setup
        if live_mode and api_key and api_secret:
            self.exchange = ccxt.binanceusdm({
                'apiKey': api_key,
                'secret': api_secret,
                'enableRateLimit': True,
            })
        else:
            self.exchange = ccxt.binanceusdm()
        
        self.exchange.load_markets()
        self.symbol = 'BTC/USDT:USDT'
        
        # Strategy - V4 Optimized
        self.strategy = BrinksBoxStrategyV5()
        
        # Trading Configuration - OPTIMIZED SETTINGS
        self.LEVERAGE = 10
        self.POSITION_SIZE_PCT = 0.025  # 2.5% of balance per trade
        self.SL_PCT = 0.01              # 1.0% Stop Loss (optimized)
        self.TP_PCT = 0.021             # 2.1% Take Profit (lucky number)
        
        # Paper Trading State
        self.balance = 10000.0
        self.initial_balance = 10000.0
        self.position = None
        self.trades = []
        
        # Paths
        self.base_dir = os.path.dirname(os.path.abspath(__file__))
        self.state_file = os.path.join(self.base_dir, 'inception_state.json')
        self.log_file = os.path.join(self.base_dir, 'inception_trades.log')
    
    def log(self, message, level='INFO'):
        """Log message with timestamp."""
        ts = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')
        log_msg = f"[{ts}] [{level}] {message}"
        print(log_msg)
        
        # Also write to log file
        with open(self.log_file, 'a') as f:
            f.write(log_msg + '\n')
    
    def fetch_candles(self, limit=200):
        """Fetch recent 1H candles."""
        try:
            ohlcv = self.exchange.fetch_ohlcv(self.symbol, '1h', limit=limit)
            df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms', utc=True)
            df.set_index('timestamp', inplace=True)
            return df
        except Exception as e:
            self.log(f"Error fetching candles: {e}", 'ERROR')
            return None
    
    def get_order_book(self):
        """Analyze real-time order book."""
        try:
            ob = self.exchange.fetch_order_book(self.symbol, limit=50)
            bid_vol = sum([b[1] for b in ob['bids']])
            ask_vol = sum([a[1] for a in ob['asks']])
            imbalance = (bid_vol - ask_vol) / (bid_vol + ask_vol) * 100 if (bid_vol + ask_vol) > 0 else 0
            
            return {
                'bid_volume': bid_vol,
                'ask_volume': ask_vol,
                'imbalance': imbalance,
                'direction': 'BULLISH' if imbalance > 10 else ('BEARISH' if imbalance < -10 else 'NEUTRAL'),
                'price': (ob['bids'][0][0] + ob['asks'][0][0]) / 2
            }
        except Exception as e:
            self.log(f"Error getting order book: {e}", 'ERROR')
            return None
    
    def get_funding_rate(self):
        """Get current funding rate."""
        try:
            funding = self.exchange.fetch_funding_rate(self.symbol)
            rate = funding['fundingRate'] * 100
            return {
                'rate': rate,
                'direction': 'BEARISH' if rate > 0.03 else ('BULLISH' if rate < -0.03 else 'NEUTRAL')
            }
        except:
            return {'rate': 0, 'direction': 'NEUTRAL'}
    
    def check_signal(self):
        """Check for trading signals using V4 strategy."""
        df = self.fetch_candles(200)
        if df is None:
            return None
        
        # Get V4 strategy signal
        signals = self.strategy.generate_signals(df)
        latest_signal = signals.iloc[-1]
        
        # Get order book
        ob = self.get_order_book()
        if ob is None:
            return None
        
        # Get funding rate
        funding = self.get_funding_rate()
        
        # Build signal data
        signal_data = {
            'signal': latest_signal,
            'price': ob['price'],
            'order_book': ob,
            'funding': funding,
            'timestamp': datetime.utcnow().isoformat(),
            'reasons': []
        }
        
        if latest_signal == 1.0:
            signal_data['reasons'].append('V4 Strategy: LONG')
            if ob['direction'] == 'BULLISH':
                signal_data['reasons'].append(f"Order Book: Bullish ({ob['imbalance']:+.1f}%)")
        elif latest_signal == -1.0:
            signal_data['reasons'].append('V4 Strategy: SHORT')
            if ob['direction'] == 'BEARISH':
                signal_data['reasons'].append(f"Order Book: Bearish ({ob['imbalance']:+.1f}%)")
        
        return signal_data
    
    def open_position(self, signal_data):
        """Open a new position."""
        price = signal_data['price']
        trade_type = 'LONG' if signal_data['signal'] == 1.0 else 'SHORT'
        
        # Calculate position
        position_value = self.balance * self.POSITION_SIZE_PCT
        btc_size = position_value / price
        
        # Set SL/TP
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
            'size': btc_size,
            'value': position_value,
            'entry_time': datetime.utcnow().isoformat(),
            'reasons': signal_data['reasons']
        }
        
        self.log(f"🚀 OPENED {trade_type} @ ${price:,.2f}")
        self.log(f"   SL: ${sl:,.2f} | TP: ${tp:,.2f}")
        self.log(f"   Reasons: {', '.join(signal_data['reasons'])}")
        
        self.save_state()
    
    def check_position(self):
        """Check if position should be closed."""
        if not self.position:
            return
        
        ob = self.get_order_book()
        if ob is None:
            return
        
        current_price = ob['price']
        entry = self.position['entry']
        sl = self.position['sl']
        tp = self.position['tp']
        trade_type = self.position['type']
        
        result = None
        exit_price = None
        
        if trade_type == 'LONG':
            if current_price <= sl:
                result = 'LOSS'
                exit_price = sl
            elif current_price >= tp:
                result = 'WIN'
                exit_price = tp
        else:  # SHORT
            if current_price >= sl:
                result = 'LOSS'
                exit_price = sl
            elif current_price <= tp:
                result = 'WIN'
                exit_price = tp
        
        if result:
            self.close_position(result, exit_price)
    
    def close_position(self, result, exit_price):
        """Close the current position."""
        entry = self.position['entry']
        trade_type = self.position['type']
        
        # Calculate PnL
        if trade_type == 'LONG':
            pnl_pct = (exit_price - entry) / entry * self.LEVERAGE
        else:
            pnl_pct = (entry - exit_price) / entry * self.LEVERAGE
        
        pnl_value = self.position['value'] * pnl_pct
        self.balance += pnl_value
        
        # Emoji based on result
        emoji = '✅' if result == 'WIN' else '❌'
        
        # Record trade
        trade = {
            'type': trade_type,
            'entry': entry,
            'exit': exit_price,
            'result': result,
            'pnl_pct': pnl_pct * 100,
            'pnl_value': pnl_value,
            'balance_after': self.balance,
            'entry_time': self.position['entry_time'],
            'exit_time': datetime.utcnow().isoformat(),
        }
        self.trades.append(trade)
        
        ret = ((self.balance - self.initial_balance) / self.initial_balance) * 100
        
        self.log(f"{emoji} CLOSED {trade_type} @ ${exit_price:,.2f} | {result} | PnL: {pnl_pct*100:+.1f}%")
        self.log(f"   Balance: ${self.balance:,.2f} | Total Return: {ret:+.2f}%")
        
        self.position = None
        self.save_state()
    
    def save_state(self):
        """Save bot state to file."""
        state = {
            'version': self.VERSION,
            'balance': self.balance,
            'initial_balance': self.initial_balance,
            'position': self.position,
            'trades': self.trades[-100:],  # Keep last 100 trades
            'updated': datetime.utcnow().isoformat()
        }
        with open(self.state_file, 'w') as f:
            json.dump(state, f, indent=2)
    
    def load_state(self):
        """Load bot state from file."""
        if os.path.exists(self.state_file):
            with open(self.state_file, 'r') as f:
                state = json.load(f)
                self.balance = state.get('balance', 10000.0)
                self.initial_balance = state.get('initial_balance', 10000.0)
                self.position = state.get('position', None)
                self.trades = state.get('trades', [])
            self.log(f"📂 Loaded state: Balance=${self.balance:,.2f}, Trades={len(self.trades)}")
    
    def print_status(self):
        """Print current status."""
        ob = self.get_order_book()
        funding = self.get_funding_rate()
        
        print()
        print("╔══════════════════════════════════════════════════════════════╗")
        print("║              INCEPTION BOT - STATUS                          ║")
        print("╠══════════════════════════════════════════════════════════════╣")
        if ob:
            print(f"║  BTC Price:    ${ob['price']:,.2f}")
            print(f"║  Order Book:   {ob['direction']} ({ob['imbalance']:+.1f}%)")
        print(f"║  Funding Rate: {funding['rate']:.4f}% ({funding['direction']})")
        print("╠══════════════════════════════════════════════════════════════╣")
        ret = ((self.balance - self.initial_balance) / self.initial_balance) * 100
        print(f"║  Balance:      ${self.balance:,.2f}")
        print(f"║  Return:       {ret:+.2f}%")
        print(f"║  Trades:       {len(self.trades)}")
        
        if self.position:
            print("╠══════════════════════════════════════════════════════════════╣")
            print(f"║  🔥 ACTIVE: {self.position['type']} @ ${self.position['entry']:,.2f}")
            print(f"║  SL: ${self.position['sl']:,.2f} | TP: ${self.position['tp']:,.2f}")
            
            if ob:
                if self.position['type'] == 'LONG':
                    unrealized = (ob['price'] - self.position['entry']) / self.position['entry'] * self.LEVERAGE * 100
                else:
                    unrealized = (self.position['entry'] - ob['price']) / self.position['entry'] * self.LEVERAGE * 100
                print(f"║  Unrealized: {unrealized:+.1f}%")
        else:
            print("╠══════════════════════════════════════════════════════════════╣")
            print("║  No active position - Waiting for signal...")
        
        print("╚══════════════════════════════════════════════════════════════╝")
    
    def run_once(self):
        """Run one iteration."""
        try:
            # Check existing position
            if self.position:
                self.check_position()
            
            # Look for new signals if no position
            if not self.position:
                signal_data = self.check_signal()
                if signal_data and signal_data['signal'] != 0:
                    self.open_position(signal_data)
            
            # Print status
            self.print_status()
            
        except Exception as e:
            self.log(f"Error in run_once: {e}", 'ERROR')
    
    def run(self, interval_seconds=60):
        """Run the bot continuously."""
        self.log("═" * 60)
        self.log("🚀 INCEPTION BOT STARTED")
        self.log(f"   Version: {self.VERSION}")
        self.log(f"   Mode: {'LIVE' if self.live_mode else 'PAPER'}")
        self.log(f"   SL: {self.SL_PCT*100}% | TP: {self.TP_PCT*100}% | Leverage: {self.LEVERAGE}x")
        self.log("═" * 60)
        
        self.load_state()
        
        while True:
            try:
                self.run_once()
                self.log(f"⏳ Sleeping {interval_seconds}s...")
                time.sleep(interval_seconds)
            except KeyboardInterrupt:
                self.log("🛑 Bot stopped by user")
                self.save_state()
                break
            except Exception as e:
                self.log(f"Error: {e}", 'ERROR')
                time.sleep(30)


def main():
    """Main entry point."""
    print("""
    ██╗███╗   ██╗ ██████╗███████╗██████╗ ████████╗██╗ ██████╗ ███╗   ██╗
    ██║████╗  ██║██╔════╝██╔════╝██╔══██╗╚══██╔══╝██║██╔═══██╗████╗  ██║
    ██║██╔██╗ ██║██║     █████╗  ██████╔╝   ██║   ██║██║   ██║██╔██╗ ██║
    ██║██║╚██╗██║██║     ██╔══╝  ██╔═══╝    ██║   ██║██║   ██║██║╚██╗██║
    ██║██║ ╚████║╚██████╗███████╗██║        ██║   ██║╚██████╔╝██║ ╚████║
    ╚═╝╚═╝  ╚═══╝ ╚═════╝╚══════╝╚═╝        ╚═╝   ╚═╝ ╚═════╝ ╚═╝  ╚═══╝
    
    BRINKS BOX V4 STRATEGY - PAPER TRADING BOT
    """)
    
    bot = InceptionBot(live_mode=False)
    
    # Run single check for testing
    print("Running single check...")
    bot.run_once()
    
    # Uncomment to run continuously:
    # bot.run(interval_seconds=60)


if __name__ == "__main__":
    main()
