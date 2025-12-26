"""
Backtester for Brinks Box Strategy
===================================
Uses Binance BTCUSDT Perpetual Futures data for accuracy.
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import ccxt
import sys

sys.path.insert(0, '/Users/smith/Documents/ai predicitve model 1/trading_bot')
from strategies.brinks_box import BrinksBoxStrategy


# === CONFIGURATION ===
STOP_LOSS_PCT = 0.012   # 1.2%
TAKE_PROFIT_PCT = 0.021 # 2.1%
LEVERAGE = 10           # 10x


def fetch_binance_futures(days: int = 60):
    """Fetch BTCUSDT Perpetual Futures data from Binance."""
    print(f"Fetching Binance BTCUSDT Perpetual Futures ({days} days, 1H)...")
    
    exchange = ccxt.binanceusdm()
    exchange.load_markets()
    symbol = 'BTC/USDT:USDT'
    
    # Calculate since timestamp
    now = datetime.utcnow()
    since = int((now - timedelta(days=days)).timestamp() * 1000)
    
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
    
    # Convert to DataFrame
    df = pd.DataFrame(all_data, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms', utc=True)
    df.set_index('timestamp', inplace=True)
    
    print(f"Loaded: {len(df)} candles")
    print(f"Range: {df.index[0]} to {df.index[-1]}")
    
    return df


def run_backtest(days: int = 60):
    print("=" * 60)
    print(f"   BRINKS BOX STRATEGY BACKTEST")
    print(f"   DATA SOURCE: Binance BTCUSDT Perpetual Futures")
    print("=" * 60)
    print(f"Stop Loss:   {STOP_LOSS_PCT*100}%")
    print(f"Take Profit: {TAKE_PROFIT_PCT*100}%")
    print(f"Leverage:    {LEVERAGE}x")
    print("-" * 60)
    
    # Fetch data from Binance
    df = fetch_binance_futures(days)
    
    # Generate signals
    strategy = BrinksBoxStrategy()
    signals = strategy.generate_signals(df)
    
    print(f"Signals: {(signals == 1.0).sum()} LONG, {(signals == -1.0).sum()} SHORT")
    print("-" * 60)
    
    # === SIMULATION ===
    initial_balance = 10000.0
    balance = initial_balance
    trades = []
    active_trade = None
    
    for i in range(len(df)):
        candle = df.iloc[i]
        timestamp = candle.name
        sig = signals.iloc[i]
        
        # --- Manage Active Trade ---
        if active_trade:
            entry = active_trade['entry']
            sl = active_trade['sl']
            tp = active_trade['tp']
            trade_type = active_trade['type']
            entry_time = active_trade['entry_time']
            
            if trade_type == 'LONG':
                if candle['low'] <= sl:
                    pnl = (sl - entry) / entry * LEVERAGE
                    balance *= (1 + pnl)
                    trades.append({
                        'entry_time': entry_time,
                        'exit_time': timestamp,
                        'type': 'LONG',
                        'entry': entry,
                        'exit': sl,
                        'result': 'LOSS',
                        'pnl': pnl
                    })
                    active_trade = None
                elif candle['high'] >= tp:
                    pnl = (tp - entry) / entry * LEVERAGE
                    balance *= (1 + pnl)
                    trades.append({
                        'entry_time': entry_time,
                        'exit_time': timestamp,
                        'type': 'LONG',
                        'entry': entry,
                        'exit': tp,
                        'result': 'WIN',
                        'pnl': pnl
                    })
                    active_trade = None
            
            elif trade_type == 'SHORT':
                if candle['high'] >= sl:
                    pnl = (entry - sl) / entry * LEVERAGE
                    balance *= (1 + pnl)
                    trades.append({
                        'entry_time': entry_time,
                        'exit_time': timestamp,
                        'type': 'SHORT',
                        'entry': entry,
                        'exit': sl,
                        'result': 'LOSS',
                        'pnl': pnl
                    })
                    active_trade = None
                elif candle['low'] <= tp:
                    pnl = (entry - tp) / entry * LEVERAGE
                    balance *= (1 + pnl)
                    trades.append({
                        'entry_time': entry_time,
                        'exit_time': timestamp,
                        'type': 'SHORT',
                        'entry': entry,
                        'exit': tp,
                        'result': 'WIN',
                        'pnl': pnl
                    })
                    active_trade = None
        
        # --- Open New Trade ---
        if active_trade is None and sig != 0:
            price = candle['close']
            
            if sig == 1.0:  # LONG
                active_trade = {
                    'type': 'LONG',
                    'entry': price,
                    'sl': price * (1 - STOP_LOSS_PCT),
                    'tp': price * (1 + TAKE_PROFIT_PCT),
                    'entry_time': timestamp
                }
            
            elif sig == -1.0:  # SHORT
                active_trade = {
                    'type': 'SHORT',
                    'entry': price,
                    'sl': price * (1 + STOP_LOSS_PCT),
                    'tp': price * (1 - TAKE_PROFIT_PCT),
                    'entry_time': timestamp
                }
    
    # === RESULTS ===
    print("\n" + "=" * 60)
    print("   RESULTS")
    print("=" * 60)
    print(f"Initial Balance: ${initial_balance:,.2f}")
    print(f"Final Balance:   ${balance:,.2f}")
    
    net_return = ((balance - initial_balance) / initial_balance) * 100
    print(f"Net Return:      {net_return:+.2f}%")
    
    print(f"\nTotal Trades:    {len(trades)}")
    
    if trades:
        wins = [t for t in trades if t['result'] == 'WIN']
        losses = [t for t in trades if t['result'] == 'LOSS']
        win_rate = len(wins) / len(trades) * 100
        
        print(f"Wins:            {len(wins)}")
        print(f"Losses:          {len(losses)}")
        print(f"Win Rate:        {win_rate:.1f}%")
        
        # Print first 10 trades for verification
        print("\n" + "=" * 60)
        print("   FIRST 10 TRADES (for verification)")
        print("=" * 60)
        
        for i, t in enumerate(trades[:10], 1):
            print(f"\nTrade #{i}: {t['type']} - {t['result']}")
            print(f"  Entry: {t['entry_time']} @ ${t['entry']:,.2f}")
            print(f"  Exit:  {t['exit_time']} @ ${t['exit']:,.2f}")
            print(f"  PnL:   {t['pnl']*100:+.2f}%")
    
    print("=" * 60)
    
    return balance, trades


if __name__ == "__main__":
    run_backtest(90)
