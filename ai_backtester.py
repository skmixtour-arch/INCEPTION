"""
🧠 AI STRATEGY BACKTESTER
=========================
Backtests the BrinksAI V7 strategy over historical data.
"""

import ccxt
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from strategies.brinks_ai_v7 import BrinksAIStrategyV7


class AIBacktester:
    """Backtester for AI Strategy."""
    
    def __init__(self):
        self.exchange = ccxt.binanceusdm({'enableRateLimit': True})
        self.exchange.load_markets()
        self.symbol = 'BTC/USDC:USDC'
        
        # Trading params
        self.LEVERAGE = 10
        self.SL_PCT = 0.01
        self.TP_PCT = 0.021
        self.INITIAL_BALANCE = 200  # Start with $200
    
    def fetch_data(self, days=60):
        """Fetch historical data."""
        print(f"📊 Fetching {days} days of data...")
        
        all_data = []
        end_time = datetime.utcnow()
        candles_needed = days * 24
        
        while len(all_data) < candles_needed:
            since = int((end_time - timedelta(hours=1000)).timestamp() * 1000)
            ohlcv = self.exchange.fetch_ohlcv(self.symbol, '1h', since=since, limit=1000)
            
            if not ohlcv:
                break
            
            all_data = ohlcv + all_data
            end_time = datetime.utcfromtimestamp(ohlcv[0][0] / 1000)
            print(f"  Fetched up to {end_time.strftime('%Y-%m-%d')}")
        
        df = pd.DataFrame(all_data, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms', utc=True)
        df.set_index('timestamp', inplace=True)
        df = df.drop_duplicates().sort_index()
        
        # Keep only last N days
        cutoff = datetime.utcnow() - timedelta(days=days)
        df = df[df.index >= pd.Timestamp(cutoff, tz='UTC')]
        
        print(f"✅ Data: {df.index[0].date()} to {df.index[-1].date()} ({len(df)} candles)")
        return df
    
    def run_backtest(self, df, strategy):
        """Run backtest simulation."""
        print(f"\n🔬 Running Backtest: {strategy.get_name()}")
        print(f"  Leverage: {self.LEVERAGE}x | SL: {self.SL_PCT*100}% | TP: {self.TP_PCT*100}%")
        print("-" * 50)
        
        # Generate signals
        signals = strategy.generate_signals(df)
        
        # Track trades
        trades = []
        balance = self.INITIAL_BALANCE
        position = None
        
        for i, (idx, candle) in enumerate(df.iterrows()):
            # Check existing position
            if position:
                high = candle['high']
                low = candle['low']
                
                result = None
                exit_price = None
                
                if position['type'] == 'LONG':
                    if low <= position['sl']:
                        result, exit_price = 'LOSS', position['sl']
                    elif high >= position['tp']:
                        result, exit_price = 'WIN', position['tp']
                else:  # SHORT
                    if high >= position['sl']:
                        result, exit_price = 'LOSS', position['sl']
                    elif low <= position['tp']:
                        result, exit_price = 'WIN', position['tp']
                
                if result:
                    # Calculate PnL
                    if position['type'] == 'LONG':
                        pnl_pct = (exit_price - position['entry']) / position['entry'] * self.LEVERAGE
                    else:
                        pnl_pct = (position['entry'] - exit_price) / position['entry'] * self.LEVERAGE
                    
                    pnl_value = position['size'] * pnl_pct
                    balance += pnl_value
                    
                    trades.append({
                        'date': position['entry_time'],
                        'type': position['type'],
                        'entry': position['entry'],
                        'exit': exit_price,
                        'result': result,
                        'pnl_pct': pnl_pct * 100,
                        'pnl_value': pnl_value,
                        'confidence': position.get('confidence', 50),
                        'balance': balance,
                    })
                    
                    position = None
            
            # Check for new signal
            if position is None and idx in signals.index:
                signal = signals[idx]
                
                if signal != 0:
                    price = candle['close']
                    trade_type = 'LONG' if signal == 1.0 else 'SHORT'
                    
                    # Position sizing (2.5% of balance)
                    size = balance * 0.025
                    
                    if trade_type == 'LONG':
                        sl = price * (1 - self.SL_PCT)
                        tp = price * (1 + self.TP_PCT)
                    else:
                        sl = price * (1 + self.SL_PCT)
                        tp = price * (1 - self.TP_PCT)
                    
                    # Get AI confidence
                    info = strategy.get_last_decision_info()
                    
                    position = {
                        'type': trade_type,
                        'entry': price,
                        'sl': sl,
                        'tp': tp,
                        'size': size,
                        'entry_time': idx,
                        'confidence': info['confidence'],
                    }
        
        return trades, balance
    
    def print_results(self, trades, final_balance):
        """Print detailed results."""
        if not trades:
            print("\n❌ No trades generated")
            return
        
        df_trades = pd.DataFrame(trades)
        
        wins = len(df_trades[df_trades['result'] == 'WIN'])
        losses = len(df_trades[df_trades['result'] == 'LOSS'])
        total = len(df_trades)
        win_rate = wins / total * 100 if total > 0 else 0
        
        total_pnl = df_trades['pnl_value'].sum()
        return_pct = (final_balance - self.INITIAL_BALANCE) / self.INITIAL_BALANCE * 100
        
        avg_win = df_trades[df_trades['result'] == 'WIN']['pnl_pct'].mean() if wins > 0 else 0
        avg_loss = df_trades[df_trades['result'] == 'LOSS']['pnl_pct'].mean() if losses > 0 else 0
        
        # Calculate drawdown
        peak = self.INITIAL_BALANCE
        max_drawdown = 0
        for bal in df_trades['balance']:
            if bal > peak:
                peak = bal
            drawdown = (peak - bal) / peak * 100
            if drawdown > max_drawdown:
                max_drawdown = drawdown
        
        # Average confidence
        avg_confidence = df_trades['confidence'].mean()
        
        # Confidence vs win rate
        high_conf_trades = df_trades[df_trades['confidence'] >= 60]
        high_conf_wins = len(high_conf_trades[high_conf_trades['result'] == 'WIN'])
        high_conf_wr = high_conf_wins / len(high_conf_trades) * 100 if len(high_conf_trades) > 0 else 0
        
        print("\n" + "=" * 60)
        print("🧠 AI STRATEGY BACKTEST RESULTS")
        print("=" * 60)
        
        print(f"""
📊 *PERFORMANCE SUMMARY*
------------------------
Initial Balance:     ${self.INITIAL_BALANCE:,.2f}
Final Balance:       ${final_balance:,.2f}
Total Return:        {return_pct:+.1f}%
Max Drawdown:        -{max_drawdown:.1f}%

📈 *TRADE STATISTICS*
------------------------
Total Trades:        {total}
Wins:                {wins} ({win_rate:.1f}%)
Losses:              {losses}
Avg Win:             +{avg_win:.1f}%
Avg Loss:            {avg_loss:.1f}%

🧠 *AI CONFIDENCE ANALYSIS*
------------------------
Avg Confidence:      {avg_confidence:.0f}%
High Conf Trades:    {len(high_conf_trades)} (≥60%)
High Conf Win Rate:  {high_conf_wr:.1f}%
""")
        
        # Print recent trades
        print("📋 *RECENT TRADES*")
        print("-" * 60)
        for _, t in df_trades.tail(10).iterrows():
            emoji = "✅" if t['result'] == 'WIN' else "❌"
            date_str = t['date'].strftime('%m/%d %H:%M') if hasattr(t['date'], 'strftime') else str(t['date'])[:10]
            print(f"  {emoji} {date_str} | {t['type']:5} | {t['pnl_pct']:+6.1f}% | Conf: {t['confidence']:.0f}%")
        
        print("\n" + "=" * 60)
        
        # Weekday breakdown
        df_trades['weekday'] = pd.to_datetime(df_trades['date']).dt.dayofweek
        print("\n📅 *WIN RATE BY WEEKDAY*")
        print("-" * 40)
        for day in range(5):
            day_trades = df_trades[df_trades['weekday'] == day]
            if len(day_trades) > 0:
                day_wins = len(day_trades[day_trades['result'] == 'WIN'])
                day_wr = day_wins / len(day_trades) * 100
                day_names = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri']
                print(f"  {day_names[day]}: {day_wins}/{len(day_trades)} ({day_wr:.0f}%)")
        
        # By trade type
        print("\n📊 *WIN RATE BY TYPE*")
        print("-" * 40)
        for ttype in ['LONG', 'SHORT']:
            type_trades = df_trades[df_trades['type'] == ttype]
            if len(type_trades) > 0:
                type_wins = len(type_trades[type_trades['result'] == 'WIN'])
                type_wr = type_wins / len(type_trades) * 100
                print(f"  {ttype}: {type_wins}/{len(type_trades)} ({type_wr:.0f}%)")
        
        print("\n" + "=" * 60)
        
        return {
            'total_trades': total,
            'wins': wins,
            'win_rate': win_rate,
            'return_pct': return_pct,
            'max_drawdown': max_drawdown,
            'final_balance': final_balance,
        }


def main():
    print("""
    ╔══════════════════════════════════════════════════════════╗
    ║         🧠 AI STRATEGY BACKTESTER                        ║
    ║         Testing BrinksAI V7 (60 Days)                    ║
    ╚══════════════════════════════════════════════════════════╝
    """)
    
    backtester = AIBacktester()
    strategy = BrinksAIStrategyV7()
    
    # Fetch data
    df = backtester.fetch_data(days=60)
    
    # Run backtest
    trades, final_balance = backtester.run_backtest(df, strategy)
    
    # Print results
    results = backtester.print_results(trades, final_balance)
    
    return results


if __name__ == "__main__":
    main()
