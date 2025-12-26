"""
Brinks Box Live Paper Trading Bot
==================================
Uses V2 Strategy with real-time Binance order book analysis.

Features:
- V2 Strategy (Vector Candles + Session Analysis)
- Real-time Order Book Imbalance
- Funding Rate Analysis
- Paper Trading (no real money)
"""

import ccxt
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import time
import json
import os

# Strategy
import sys
sys.path.insert(0, '/Users/smith/Documents/ai predicitve model 1/trading_bot')
from strategies.brinks_box_v2 import BrinksBoxStrategyV2


class LivePaperBot:
    """Live paper trading bot with V2 strategy and order book analysis."""
    
    def __init__(self):
        # Exchange
        self.exchange = ccxt.binanceusdm()
        self.exchange.load_markets()
        self.symbol = 'BTC/USDT:USDT'
        
        # Strategy
        self.strategy = BrinksBoxStrategyV2()
        
        # Trading Config
        self.LEVERAGE = 10
        self.POSITION_SIZE_PCT = 0.025  # 2.5% of balance per trade
        self.SL_PCT = 0.008  # 0.8%
        self.TP_PCT = 0.021  # 2.1%
        
        # Paper Trading State
        self.balance = 10000.0
        self.initial_balance = 10000.0
        self.position = None  # {'type': 'LONG/SHORT', 'entry': price, 'sl': price, 'tp': price, 'size': btc}
        self.trades = []
        
        # Order Book Analysis
        self.order_book_levels = 50  # Analyze top 50 levels
        
        # Logging
        self.log_file = '/Users/smith/Documents/ai predicitve model 1/trading_bot/bot_log.json'
    
    def fetch_candles(self, limit=100):
        """Fetch recent 1H candles."""
        ohlcv = self.exchange.fetch_ohlcv(self.symbol, '1h', limit=limit)
        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms', utc=True)
        df.set_index('timestamp', inplace=True)
        return df
    
    def analyze_order_book(self):
        """Analyze real-time order book for liquidity imbalance."""
        ob = self.exchange.fetch_order_book(self.symbol, limit=self.order_book_levels)
        
        # Calculate volumes
        bid_volume = sum([b[1] for b in ob['bids']])
        ask_volume = sum([a[1] for a in ob['asks']])
        
        # Imbalance: +100% = all bids (bullish), -100% = all asks (bearish)
        imbalance = (bid_volume - ask_volume) / (bid_volume + ask_volume) * 100 if (bid_volume + ask_volume) > 0 else 0
        
        # Large walls detection
        bid_prices = [b[0] for b in ob['bids'][:10]]
        ask_prices = [a[0] for a in ob['asks'][:10]]
        
        current_price = (ob['bids'][0][0] + ob['asks'][0][0]) / 2
        
        return {
            'bid_volume': bid_volume,
            'ask_volume': ask_volume,
            'imbalance': imbalance,
            'direction': 'BULLISH' if imbalance > 10 else ('BEARISH' if imbalance < -10 else 'NEUTRAL'),
            'spread': ob['asks'][0][0] - ob['bids'][0][0],
            'current_price': current_price
        }
    
    def get_funding_rate(self):
        """Get current funding rate."""
        try:
            funding = self.exchange.fetch_funding_rate(self.symbol)
            return {
                'rate': funding['fundingRate'] * 100,
                'direction': 'BEARISH' if funding['fundingRate'] > 0.01 else ('BULLISH' if funding['fundingRate'] < -0.01 else 'NEUTRAL')
            }
        except:
            return {'rate': 0, 'direction': 'NEUTRAL'}
    
    def check_signal(self):
        """Check for trading signal combining strategy + order book."""
        # Get candle data
        df = self.fetch_candles(100)
        
        # Get strategy signal
        signals = self.strategy.generate_signals(df)
        latest_signal = signals.iloc[-1]
        
        # Get order book analysis
        ob_analysis = self.analyze_order_book()
        
        # Get funding rate
        funding = self.get_funding_rate()
        
        # Combine signals
        final_signal = 0.0
        confidence = 0
        reasons = []
        
        if latest_signal == 1.0:  # Strategy says LONG
            reasons.append('STRATEGY: LONG')
            confidence += 2
            
            # Order book confirms?
            if ob_analysis['direction'] == 'BULLISH':
                reasons.append(f"ORDER_BOOK: BULLISH ({ob_analysis['imbalance']:+.1f}%)")
                confidence += 1
            elif ob_analysis['direction'] == 'BEARISH':
                reasons.append(f"ORDER_BOOK: BEARISH ({ob_analysis['imbalance']:+.1f}%) - CONFLICT")
                confidence -= 1
            
            # Funding rate check
            if funding['direction'] == 'BULLISH':
                reasons.append(f"FUNDING: Bullish ({funding['rate']:.4f}%)")
                confidence += 1
            
            if confidence >= 2:
                final_signal = 1.0
        
        elif latest_signal == -1.0:  # Strategy says SHORT
            reasons.append('STRATEGY: SHORT')
            confidence += 2
            
            # Order book confirms?
            if ob_analysis['direction'] == 'BEARISH':
                reasons.append(f"ORDER_BOOK: BEARISH ({ob_analysis['imbalance']:+.1f}%)")
                confidence += 1
            elif ob_analysis['direction'] == 'BULLISH':
                reasons.append(f"ORDER_BOOK: BULLISH ({ob_analysis['imbalance']:+.1f}%) - CONFLICT")
                confidence -= 1
            
            # Funding rate check
            if funding['direction'] == 'BEARISH':
                reasons.append(f"FUNDING: Bearish ({funding['rate']:.4f}%)")
                confidence += 1
            
            if confidence >= 2:
                final_signal = -1.0
        
        return {
            'signal': final_signal,
            'confidence': confidence,
            'reasons': reasons,
            'price': ob_analysis['current_price'],
            'order_book': ob_analysis,
            'funding': funding
        }
    
    def open_position(self, signal_data):
        """Open a new position."""
        price = signal_data['price']
        trade_type = 'LONG' if signal_data['signal'] == 1.0 else 'SHORT'
        
        # Calculate position size
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
        
        self.log(f"OPENED {trade_type} @ ${price:,.2f} | SL: ${sl:,.2f} | TP: ${tp:,.2f}")
        self.log(f"  Reasons: {', '.join(signal_data['reasons'])}")
    
    def check_position(self):
        """Check if current position should be closed."""
        if not self.position:
            return
        
        ob = self.analyze_order_book()
        current_price = ob['current_price']
        
        result = None
        exit_price = None
        
        if self.position['type'] == 'LONG':
            if current_price <= self.position['sl']:
                result = 'LOSS'
                exit_price = self.position['sl']
            elif current_price >= self.position['tp']:
                result = 'WIN'
                exit_price = self.position['tp']
        else:  # SHORT
            if current_price >= self.position['sl']:
                result = 'LOSS'
                exit_price = self.position['sl']
            elif current_price <= self.position['tp']:
                result = 'WIN'
                exit_price = self.position['tp']
        
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
            'reasons': self.position['reasons']
        }
        self.trades.append(trade)
        
        self.log(f"CLOSED {trade_type} @ ${exit_price:,.2f} | {result} | PnL: {pnl_pct*100:+.1f}%")
        self.log(f"  Balance: ${self.balance:,.2f} (Total Return: {((self.balance - self.initial_balance) / self.initial_balance) * 100:+.2f}%)")
        
        self.position = None
        self.save_state()
    
    def log(self, message):
        """Print with timestamp."""
        ts = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')
        print(f"[{ts}] {message}")
    
    def save_state(self):
        """Save bot state to file."""
        state = {
            'balance': self.balance,
            'initial_balance': self.initial_balance,
            'position': self.position,
            'trades': self.trades,
            'last_update': datetime.utcnow().isoformat()
        }
        with open(self.log_file, 'w') as f:
            json.dump(state, f, indent=2)
    
    def load_state(self):
        """Load bot state from file."""
        if os.path.exists(self.log_file):
            with open(self.log_file, 'r') as f:
                state = json.load(f)
                self.balance = state.get('balance', 10000.0)
                self.initial_balance = state.get('initial_balance', 10000.0)
                self.position = state.get('position', None)
                self.trades = state.get('trades', [])
            self.log(f"Loaded state: Balance=${self.balance:,.2f}, Trades={len(self.trades)}")
    
    def print_status(self):
        """Print current status."""
        ob = self.analyze_order_book()
        funding = self.get_funding_rate()
        
        print()
        print("=" * 60)
        print(f"  BRINKS BOX BOT - STATUS")
        print("=" * 60)
        print(f"  BTC Price:    ${ob['current_price']:,.2f}")
        print(f"  Order Book:   {ob['direction']} ({ob['imbalance']:+.1f}%)")
        print(f"  Funding Rate: {funding['rate']:.4f}% ({funding['direction']})")
        print()
        print(f"  Balance:      ${self.balance:,.2f}")
        print(f"  Total Return: {((self.balance - self.initial_balance) / self.initial_balance) * 100:+.2f}%")
        print(f"  Trades:       {len(self.trades)}")
        
        if self.position:
            print()
            print(f"  ACTIVE: {self.position['type']} @ ${self.position['entry']:,.2f}")
            print(f"  SL: ${self.position['sl']:,.2f} | TP: ${self.position['tp']:,.2f}")
            
            if self.position['type'] == 'LONG':
                unrealized = (ob['current_price'] - self.position['entry']) / self.position['entry'] * self.LEVERAGE * 100
            else:
                unrealized = (self.position['entry'] - ob['current_price']) / self.position['entry'] * self.LEVERAGE * 100
            print(f"  Unrealized: {unrealized:+.1f}%")
        else:
            print()
            print("  No active position")
        
        print("=" * 60)
    
    def run_once(self):
        """Run one iteration of the bot."""
        try:
            # Check current position
            if self.position:
                self.check_position()
            
            # If no position, check for new signal
            if not self.position:
                signal_data = self.check_signal()
                
                if signal_data['signal'] != 0:
                    self.open_position(signal_data)
            
            # Print status
            self.print_status()
            
        except Exception as e:
            self.log(f"ERROR: {e}")
    
    def run(self, interval_seconds=60):
        """Run the bot in a loop."""
        self.log("Starting Brinks Box Paper Trading Bot...")
        self.load_state()
        
        while True:
            try:
                self.run_once()
                self.log(f"Sleeping {interval_seconds}s...")
                time.sleep(interval_seconds)
            except KeyboardInterrupt:
                self.log("Bot stopped by user.")
                self.save_state()
                break
            except Exception as e:
                self.log(f"ERROR: {e}")
                time.sleep(30)


if __name__ == "__main__":
    bot = LivePaperBot()
    
    # Run single check
    print("Running single check...")
    bot.run_once()
    
    # To run continuously, uncomment:
    # bot.run(interval_seconds=60)
