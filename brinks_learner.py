"""
🧠 BRINKS PATTERN LEARNER
=========================
Analyzes 360 days of BTC data to discover patterns:
- Inside Brinks Box (14:00-15:00 UTC)
- Outside Brinks Box
- Breakout behaviors
- Vector correlations
- Win rate by conditions

Outputs a pattern recognition model and insights report.
"""

import ccxt
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from collections import defaultdict
import json
import os
import warnings
warnings.filterwarnings('ignore')


class BrinksPatternLearner:
    """AI system that learns patterns from historical Brinks data."""
    
    def __init__(self):
        # Exchange connection
        self.exchange = ccxt.binanceusdm({
            'enableRateLimit': True,
        })
        self.exchange.load_markets()
        self.symbol = 'BTC/USDC:USDC'
        
        # Session times (UTC)
        self.BRINKS_START = 14
        self.BRINKS_END = 15
        self.TRADING_END = 20
        
        # Vector thresholds
        self.VECTOR_THRESHOLD = 1.5
        
        # Storage
        self.patterns = defaultdict(list)
        self.insights = {}
        
        # Output directory
        self.output_dir = os.path.dirname(os.path.abspath(__file__))
    
    def fetch_historical_data(self, days=360):
        """Fetch historical 1h candles."""
        print(f"📊 Fetching {days} days of historical data...")
        
        all_data = []
        # Binance limits to 1000 candles per request
        # 24 candles per day * 360 days = 8640 candles
        
        end_time = datetime.utcnow()
        candles_needed = days * 24
        candles_per_request = 1000
        
        while len(all_data) < candles_needed:
            try:
                since = int((end_time - timedelta(hours=candles_per_request)).timestamp() * 1000)
                ohlcv = self.exchange.fetch_ohlcv(self.symbol, '1h', since=since, limit=candles_per_request)
                
                if not ohlcv:
                    break
                
                all_data = ohlcv + all_data  # Prepend older data
                end_time = datetime.utcfromtimestamp(ohlcv[0][0] / 1000)
                
                print(f"  Fetched up to {end_time.strftime('%Y-%m-%d')} | Total: {len(all_data)} candles")
                
            except Exception as e:
                print(f"  Error: {e}")
                break
        
        df = pd.DataFrame(all_data, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms', utc=True)
        df.set_index('timestamp', inplace=True)
        df = df.drop_duplicates()
        df = df.sort_index()
        
        print(f"✅ Loaded {len(df)} candles from {df.index[0].date()} to {df.index[-1].date()}")
        return df
    
    def add_features(self, df):
        """Add technical features for pattern analysis."""
        print("🔧 Adding technical features...")
        
        df = df.copy()
        
        # Basic price features
        df['body'] = abs(df['close'] - df['open'])
        df['range'] = df['high'] - df['low']
        df['body_pct'] = df['body'] / df['range'].replace(0, 1)
        df['is_bullish'] = df['close'] > df['open']
        
        # Volume features
        df['vol_avg'] = df['volume'].rolling(window=20).mean()
        df['vol_ratio'] = df['volume'] / df['vol_avg']
        df['is_vector'] = (df['vol_ratio'] >= self.VECTOR_THRESHOLD) & (df['body_pct'] > 0.5)
        
        # EMAs
        df['ema_5'] = df['close'].ewm(span=5, adjust=False).mean()
        df['ema_13'] = df['close'].ewm(span=13, adjust=False).mean()
        df['ema_50'] = df['close'].ewm(span=50, adjust=False).mean()
        df['ema_200'] = df['close'].ewm(span=200, adjust=False).mean()
        
        # Trend indicators
        df['above_ema50'] = df['close'] > df['ema_50']
        df['above_ema200'] = df['close'] > df['ema_200']
        df['ema50_above_200'] = df['ema_50'] > df['ema_200']
        
        # Price change
        df['pct_change'] = df['close'].pct_change() * 100
        df['pct_change_2h'] = df['close'].pct_change(2) * 100
        df['pct_change_4h'] = df['close'].pct_change(4) * 100
        
        # Time features
        df['hour'] = df.index.hour
        df['weekday'] = df.index.weekday
        df['is_brinks'] = (df['hour'] >= self.BRINKS_START) & (df['hour'] < self.BRINKS_END)
        df['is_trading'] = (df['hour'] >= self.BRINKS_END) & (df['hour'] < self.TRADING_END)
        
        # RSI
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss.replace(0, 1)
        df['rsi'] = 100 - (100 / (1 + rs))
        
        return df
    
    def analyze_brinks_patterns(self, df):
        """Analyze patterns specifically during Brinks Box hours."""
        print("\n📈 Analyzing Brinks Box Patterns...")
        
        brinks_data = df[df['is_brinks']].copy()
        trading_data = df[df['is_trading']].copy()
        
        patterns = {
            'brinks_stats': {},
            'trading_stats': {},
            'daily_patterns': [],
            'vector_patterns': [],
            'breakout_patterns': [],
            'weekday_analysis': {},
            'best_conditions': [],
            'correlations': {}
        }
        
        # === BRINKS BOX STATISTICS ===
        patterns['brinks_stats'] = {
            'avg_range_pct': (brinks_data['range'] / brinks_data['close'] * 100).mean(),
            'avg_volume': brinks_data['volume'].mean(),
            'bullish_pct': brinks_data['is_bullish'].mean() * 100,
            'vector_pct': brinks_data['is_vector'].mean() * 100,
            'avg_body_pct': brinks_data['body_pct'].mean() * 100,
        }
        
        # === TRADING WINDOW STATISTICS ===
        patterns['trading_stats'] = {
            'avg_range_pct': (trading_data['range'] / trading_data['close'] * 100).mean(),
            'avg_volume': trading_data['volume'].mean(),
            'bullish_pct': trading_data['is_bullish'].mean() * 100,
            'avg_move_pct': trading_data['pct_change'].abs().mean(),
        }
        
        # === DAILY BRINKS BOX ANALYSIS ===
        print("  Analyzing daily Brinks boxes...")
        
        dates = df.index.date
        unique_dates = sorted(set(dates))
        
        daily_results = []
        
        for date in unique_dates:
            day_data = df[df.index.date == date]
            weekday = day_data.index[0].weekday()
            
            if weekday >= 5:  # Skip weekends
                continue
            
            # Get Brinks candles
            brinks = day_data[(day_data['hour'] >= self.BRINKS_START) & (day_data['hour'] < self.BRINKS_END)]
            if brinks.empty:
                continue
            
            brinks_high = brinks['high'].max()
            brinks_low = brinks['low'].min()
            brinks_range = brinks_high - brinks_low
            brinks_mid = (brinks_high + brinks_low) / 2
            brinks_close = brinks['close'].iloc[-1]
            brinks_direction = 'BULL' if brinks_close > brinks['open'].iloc[0] else 'BEAR'
            
            # Get trading window data
            trading = day_data[(day_data['hour'] >= self.BRINKS_END) & (day_data['hour'] < self.TRADING_END)]
            if trading.empty:
                continue
            
            # Check for breakouts
            trading_high = trading['high'].max()
            trading_low = trading['low'].min()
            
            broke_high = trading_high > brinks_high
            broke_low = trading_low < brinks_low
            
            # Determine outcome
            if broke_high and not broke_low:
                breakout_dir = 'BULL'
            elif broke_low and not broke_high:
                breakout_dir = 'BEAR'
            elif broke_high and broke_low:
                breakout_dir = 'BOTH'
            else:
                breakout_dir = 'NONE'
            
            # Calculate move after breakout
            if broke_high:
                bull_move = (trading_high - brinks_high) / brinks_high * 100
            else:
                bull_move = 0
            
            if broke_low:
                bear_move = (brinks_low - trading_low) / brinks_low * 100
            else:
                bear_move = 0
            
            # Check vectors in Brinks
            brinks_vectors = brinks[brinks['is_vector']]
            has_gvc = (brinks_vectors['is_bullish'] == True).any() if not brinks_vectors.empty else False
            has_rvc = (brinks_vectors['is_bullish'] == False).any() if not brinks_vectors.empty else False
            
            # Get pre-Brinks context
            asian = day_data[day_data['hour'] < 8]
            london = day_data[(day_data['hour'] >= 8) & (day_data['hour'] < 14)]
            
            asian_high = asian['high'].max() if not asian.empty else brinks_high
            asian_low = asian['low'].min() if not asian.empty else brinks_low
            
            swept_asian_high = brinks_high > asian_high
            swept_asian_low = brinks_low < asian_low
            
            daily_results.append({
                'date': str(date),
                'weekday': weekday,
                'weekday_name': ['Mon', 'Tue', 'Wed', 'Thu', 'Fri'][weekday],
                'brinks_high': brinks_high,
                'brinks_low': brinks_low,
                'brinks_range_pct': brinks_range / brinks_mid * 100,
                'brinks_direction': brinks_direction,
                'breakout_direction': breakout_dir,
                'bull_move_pct': bull_move,
                'bear_move_pct': bear_move,
                'has_gvc': has_gvc,
                'has_rvc': has_rvc,
                'swept_asian_high': swept_asian_high,
                'swept_asian_low': swept_asian_low,
                'above_ema50': brinks['above_ema50'].iloc[-1],
                'above_ema200': brinks['above_ema200'].iloc[-1],
                'rsi': brinks['rsi'].iloc[-1] if not pd.isna(brinks['rsi'].iloc[-1]) else 50,
            })
        
        patterns['daily_patterns'] = daily_results
        
        # === PATTERN ANALYSIS ===
        print("  Extracting key patterns...")
        
        df_results = pd.DataFrame(daily_results)
        
        if len(df_results) > 0:
            # Weekday analysis
            for day in range(5):
                day_data = df_results[df_results['weekday'] == day]
                if len(day_data) > 0:
                    bull_breakouts = len(day_data[day_data['breakout_direction'] == 'BULL'])
                    bear_breakouts = len(day_data[day_data['breakout_direction'] == 'BEAR'])
                    total = len(day_data)
                    
                    patterns['weekday_analysis'][['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday'][day]] = {
                        'total_days': total,
                        'bull_breakout_pct': bull_breakouts / total * 100 if total > 0 else 0,
                        'bear_breakout_pct': bear_breakouts / total * 100 if total > 0 else 0,
                        'avg_bull_move': day_data['bull_move_pct'].mean(),
                        'avg_bear_move': day_data['bear_move_pct'].mean(),
                    }
            
            # Vector patterns
            gvc_days = df_results[df_results['has_gvc'] == True]
            rvc_days = df_results[df_results['has_rvc'] == True]
            
            patterns['vector_patterns'] = {
                'gvc_bull_breakout_pct': len(gvc_days[gvc_days['breakout_direction'] == 'BULL']) / len(gvc_days) * 100 if len(gvc_days) > 0 else 0,
                'gvc_bear_breakout_pct': len(gvc_days[gvc_days['breakout_direction'] == 'BEAR']) / len(gvc_days) * 100 if len(gvc_days) > 0 else 0,
                'rvc_bull_breakout_pct': len(rvc_days[rvc_days['breakout_direction'] == 'BULL']) / len(rvc_days) * 100 if len(rvc_days) > 0 else 0,
                'rvc_bear_breakout_pct': len(rvc_days[rvc_days['breakout_direction'] == 'BEAR']) / len(rvc_days) * 100 if len(rvc_days) > 0 else 0,
                'gvc_days': len(gvc_days),
                'rvc_days': len(rvc_days),
            }
            
            # Brinks direction correlation
            bull_brinks = df_results[df_results['brinks_direction'] == 'BULL']
            bear_brinks = df_results[df_results['brinks_direction'] == 'BEAR']
            
            patterns['breakout_patterns'] = {
                'bull_brinks_to_bull_breakout': len(bull_brinks[bull_brinks['breakout_direction'] == 'BULL']) / len(bull_brinks) * 100 if len(bull_brinks) > 0 else 0,
                'bull_brinks_to_bear_breakout': len(bull_brinks[bull_brinks['breakout_direction'] == 'BEAR']) / len(bull_brinks) * 100 if len(bull_brinks) > 0 else 0,
                'bear_brinks_to_bull_breakout': len(bear_brinks[bear_brinks['breakout_direction'] == 'BULL']) / len(bear_brinks) * 100 if len(bear_brinks) > 0 else 0,
                'bear_brinks_to_bear_breakout': len(bear_brinks[bear_brinks['breakout_direction'] == 'BEAR']) / len(bear_brinks) * 100 if len(bear_brinks) > 0 else 0,
            }
            
            # Asian sweep patterns
            swept_high = df_results[df_results['swept_asian_high'] == True]
            swept_low = df_results[df_results['swept_asian_low'] == True]
            
            patterns['asian_sweep_patterns'] = {
                'swept_high_then_bear_pct': len(swept_high[swept_high['breakout_direction'] == 'BEAR']) / len(swept_high) * 100 if len(swept_high) > 0 else 0,
                'swept_low_then_bull_pct': len(swept_low[swept_low['breakout_direction'] == 'BULL']) / len(swept_low) * 100 if len(swept_low) > 0 else 0,
                'swept_high_days': len(swept_high),
                'swept_low_days': len(swept_low),
            }
            
            # EMA trend patterns
            above_200 = df_results[df_results['above_ema200'] == True]
            below_200 = df_results[df_results['above_ema200'] == False]
            
            patterns['ema_patterns'] = {
                'above_200_bull_pct': len(above_200[above_200['breakout_direction'] == 'BULL']) / len(above_200) * 100 if len(above_200) > 0 else 0,
                'above_200_bear_pct': len(above_200[above_200['breakout_direction'] == 'BEAR']) / len(above_200) * 100 if len(above_200) > 0 else 0,
                'below_200_bull_pct': len(below_200[below_200['breakout_direction'] == 'BULL']) / len(below_200) * 100 if len(below_200) > 0 else 0,
                'below_200_bear_pct': len(below_200[below_200['breakout_direction'] == 'BEAR']) / len(below_200) * 100 if len(below_200) > 0 else 0,
            }
            
            # RSI patterns
            oversold = df_results[df_results['rsi'] < 35]
            overbought = df_results[df_results['rsi'] > 65]
            
            patterns['rsi_patterns'] = {
                'oversold_bull_pct': len(oversold[oversold['breakout_direction'] == 'BULL']) / len(oversold) * 100 if len(oversold) > 0 else 0,
                'overbought_bear_pct': len(overbought[overbought['breakout_direction'] == 'BEAR']) / len(overbought) * 100 if len(overbought) > 0 else 0,
                'oversold_days': len(oversold),
                'overbought_days': len(overbought),
            }
            
            # Find best conditions for each direction
            best_bull_conditions = []
            best_bear_conditions = []
            
            # Test combinations
            for day in range(5):
                for above_200 in [True, False]:
                    for rsi_zone in ['oversold', 'normal', 'overbought']:
                        mask = (df_results['weekday'] == day) & (df_results['above_ema200'] == above_200)
                        
                        if rsi_zone == 'oversold':
                            mask = mask & (df_results['rsi'] < 35)
                        elif rsi_zone == 'overbought':
                            mask = mask & (df_results['rsi'] > 65)
                        
                        subset = df_results[mask]
                        
                        if len(subset) >= 5:  # Minimum sample size
                            bull_rate = len(subset[subset['breakout_direction'] == 'BULL']) / len(subset)
                            bear_rate = len(subset[subset['breakout_direction'] == 'BEAR']) / len(subset)
                            
                            condition = {
                                'weekday': ['Mon', 'Tue', 'Wed', 'Thu', 'Fri'][day],
                                'above_200': above_200,
                                'rsi_zone': rsi_zone,
                                'sample_size': len(subset),
                            }
                            
                            if bull_rate > 0.55:
                                best_bull_conditions.append({**condition, 'win_rate': bull_rate * 100, 'avg_move': subset['bull_move_pct'].mean()})
                            
                            if bear_rate > 0.55:
                                best_bear_conditions.append({**condition, 'win_rate': bear_rate * 100, 'avg_move': subset['bear_move_pct'].mean()})
            
            patterns['best_bull_conditions'] = sorted(best_bull_conditions, key=lambda x: x['win_rate'], reverse=True)[:5]
            patterns['best_bear_conditions'] = sorted(best_bear_conditions, key=lambda x: x['win_rate'], reverse=True)[:5]
        
        return patterns
    
    def generate_report(self, patterns):
        """Generate a human-readable report of findings."""
        print("\n📝 Generating Insights Report...")
        
        report = []
        report.append("=" * 60)
        report.append("🧠 BRINKS PATTERN LEARNER - INSIGHTS REPORT")
        report.append(f"Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}")
        report.append("=" * 60)
        
        # Overall stats
        report.append("\n📊 BRINKS BOX STATISTICS (14:00-15:00 UTC)")
        report.append("-" * 40)
        bs = patterns.get('brinks_stats', {})
        report.append(f"  Average Range: {bs.get('avg_range_pct', 0):.3f}%")
        report.append(f"  Bullish Candles: {bs.get('bullish_pct', 0):.1f}%")
        report.append(f"  Vector Candles: {bs.get('vector_pct', 0):.1f}%")
        
        # Weekday analysis
        report.append("\n📅 WEEKDAY ANALYSIS")
        report.append("-" * 40)
        for day, stats in patterns.get('weekday_analysis', {}).items():
            report.append(f"\n  {day} ({stats['total_days']} days):")
            report.append(f"    Bull Breakout: {stats['bull_breakout_pct']:.1f}% (avg +{stats['avg_bull_move']:.2f}%)")
            report.append(f"    Bear Breakout: {stats['bear_breakout_pct']:.1f}% (avg -{stats['avg_bear_move']:.2f}%)")
        
        # Vector patterns
        report.append("\n🔥 VECTOR CANDLE PATTERNS")
        report.append("-" * 40)
        vp = patterns.get('vector_patterns', {})
        report.append(f"  When GVC in Brinks ({vp.get('gvc_days', 0)} days):")
        report.append(f"    → Bull Breakout: {vp.get('gvc_bull_breakout_pct', 0):.1f}%")
        report.append(f"    → Bear Breakout: {vp.get('gvc_bear_breakout_pct', 0):.1f}%")
        report.append(f"  When RVC in Brinks ({vp.get('rvc_days', 0)} days):")
        report.append(f"    → Bull Breakout: {vp.get('rvc_bull_breakout_pct', 0):.1f}%")
        report.append(f"    → Bear Breakout: {vp.get('rvc_bear_breakout_pct', 0):.1f}%")
        
        # Brinks direction correlation
        report.append("\n🎯 BRINKS DIRECTION → BREAKOUT CORRELATION")
        report.append("-" * 40)
        bp = patterns.get('breakout_patterns', {})
        report.append(f"  Bullish Brinks → Bull Breakout: {bp.get('bull_brinks_to_bull_breakout', 0):.1f}%")
        report.append(f"  Bullish Brinks → Bear Breakout: {bp.get('bull_brinks_to_bear_breakout', 0):.1f}%")
        report.append(f"  Bearish Brinks → Bull Breakout: {bp.get('bear_brinks_to_bull_breakout', 0):.1f}%")
        report.append(f"  Bearish Brinks → Bear Breakout: {bp.get('bear_brinks_to_bear_breakout', 0):.1f}%")
        
        # Asian sweep patterns
        report.append("\n🌊 ASIAN SWEEP PATTERNS (Trap Detection)")
        report.append("-" * 40)
        asp = patterns.get('asian_sweep_patterns', {})
        report.append(f"  Swept Asian High → Bear Breakout: {asp.get('swept_high_then_bear_pct', 0):.1f}% ({asp.get('swept_high_days', 0)} days)")
        report.append(f"  Swept Asian Low → Bull Breakout: {asp.get('swept_low_then_bull_pct', 0):.1f}% ({asp.get('swept_low_days', 0)} days)")
        
        # EMA patterns
        report.append("\n📈 EMA TREND PATTERNS")
        report.append("-" * 40)
        ep = patterns.get('ema_patterns', {})
        report.append(f"  Above 200 EMA → Bull: {ep.get('above_200_bull_pct', 0):.1f}% | Bear: {ep.get('above_200_bear_pct', 0):.1f}%")
        report.append(f"  Below 200 EMA → Bull: {ep.get('below_200_bull_pct', 0):.1f}% | Bear: {ep.get('below_200_bear_pct', 0):.1f}%")
        
        # RSI patterns
        report.append("\n📉 RSI EXTREMES")
        report.append("-" * 40)
        rp = patterns.get('rsi_patterns', {})
        report.append(f"  Oversold (RSI<35) → Bull Breakout: {rp.get('oversold_bull_pct', 0):.1f}% ({rp.get('oversold_days', 0)} days)")
        report.append(f"  Overbought (RSI>65) → Bear Breakout: {rp.get('overbought_bear_pct', 0):.1f}% ({rp.get('overbought_days', 0)} days)")
        
        # Best conditions
        report.append("\n⭐ BEST BULL CONDITIONS (Win Rate > 55%)")
        report.append("-" * 40)
        for cond in patterns.get('best_bull_conditions', [])[:5]:
            report.append(f"  {cond['weekday']} | {'Above' if cond['above_200'] else 'Below'} 200 EMA | RSI: {cond['rsi_zone']}")
            report.append(f"    → Win Rate: {cond['win_rate']:.1f}% | Avg Move: +{cond['avg_move']:.2f}% | Samples: {cond['sample_size']}")
        
        report.append("\n⭐ BEST BEAR CONDITIONS (Win Rate > 55%)")
        report.append("-" * 40)
        for cond in patterns.get('best_bear_conditions', [])[:5]:
            report.append(f"  {cond['weekday']} | {'Above' if cond['above_200'] else 'Below'} 200 EMA | RSI: {cond['rsi_zone']}")
            report.append(f"    → Win Rate: {cond['win_rate']:.1f}% | Avg Move: -{cond['avg_move']:.2f}% | Samples: {cond['sample_size']}")
        
        report.append("\n" + "=" * 60)
        report.append("🧠 KEY INSIGHTS FOR TRADING")
        report.append("=" * 60)
        
        # Generate key insights
        insights = []
        
        # Best weekday
        weekday_stats = patterns.get('weekday_analysis', {})
        if weekday_stats:
            best_bull_day = max(weekday_stats.items(), key=lambda x: x[1]['bull_breakout_pct'])
            best_bear_day = max(weekday_stats.items(), key=lambda x: x[1]['bear_breakout_pct'])
            worst_day = min(weekday_stats.items(), key=lambda x: (x[1]['bull_breakout_pct'] + x[1]['bear_breakout_pct']))
            
            insights.append(f"📆 Best day for LONGS: {best_bull_day[0]} ({best_bull_day[1]['bull_breakout_pct']:.0f}% bull breakouts)")
            insights.append(f"📆 Best day for SHORTS: {best_bear_day[0]} ({best_bear_day[1]['bear_breakout_pct']:.0f}% bear breakouts)")
            insights.append(f"⚠️  Least predictable: {worst_day[0]} (lowest combined breakout rate)")
        
        # Brinks direction insight
        bp = patterns.get('breakout_patterns', {})
        if bp.get('bull_brinks_to_bull_breakout', 0) > 55:
            insights.append(f"✅ Bullish Brinks → Bull continuation has edge ({bp['bull_brinks_to_bull_breakout']:.0f}%)")
        elif bp.get('bull_brinks_to_bear_breakout', 0) > 55:
            insights.append(f"🔄 Bullish Brinks often reverses to Bear ({bp['bull_brinks_to_bear_breakout']:.0f}%)")
        
        if bp.get('bear_brinks_to_bear_breakout', 0) > 55:
            insights.append(f"✅ Bearish Brinks → Bear continuation has edge ({bp['bear_brinks_to_bear_breakout']:.0f}%)")
        elif bp.get('bear_brinks_to_bull_breakout', 0) > 55:
            insights.append(f"🔄 Bearish Brinks often reverses to Bull ({bp['bear_brinks_to_bull_breakout']:.0f}%)")
        
        # Asian sweep insight
        asp = patterns.get('asian_sweep_patterns', {})
        if asp.get('swept_high_then_bear_pct', 0) > 55:
            insights.append(f"🎯 Asian High Sweep = Bear signal ({asp['swept_high_then_bear_pct']:.0f}% bear breakouts)")
        if asp.get('swept_low_then_bull_pct', 0) > 55:
            insights.append(f"🎯 Asian Low Sweep = Bull signal ({asp['swept_low_then_bull_pct']:.0f}% bull breakouts)")
        
        for insight in insights:
            report.append(f"\n{insight}")
        
        report.append("\n" + "=" * 60)
        
        return "\n".join(report)
    
    def save_results(self, patterns, report):
        """Save patterns and report to files."""
        # Save patterns JSON
        patterns_file = os.path.join(self.output_dir, 'learned_patterns.json')
        
        # Convert daily_patterns to serializable format
        serializable_patterns = {}
        for k, v in patterns.items():
            if k == 'daily_patterns':
                serializable_patterns[k] = v  # Already serializable
            else:
                serializable_patterns[k] = v
        
        with open(patterns_file, 'w') as f:
            json.dump(serializable_patterns, f, indent=2, default=str)
        print(f"✅ Patterns saved to: {patterns_file}")
        
        # Save report
        report_file = os.path.join(self.output_dir, 'brinks_insights_report.txt')
        with open(report_file, 'w') as f:
            f.write(report)
        print(f"✅ Report saved to: {report_file}")
        
        return patterns_file, report_file
    
    def run(self, days=360):
        """Run the full learning pipeline."""
        print("\n" + "=" * 60)
        print("🧠 BRINKS PATTERN LEARNER")
        print(f"Analyzing {days} days of BTC/USDC data")
        print("=" * 60)
        
        # Fetch data
        df = self.fetch_historical_data(days)
        
        # Add features
        df = self.add_features(df)
        
        # Analyze patterns
        patterns = self.analyze_brinks_patterns(df)
        
        # Generate report
        report = self.generate_report(patterns)
        
        # Save results
        patterns_file, report_file = self.save_results(patterns, report)
        
        # Print report
        print("\n" + report)
        
        return patterns, report


if __name__ == "__main__":
    learner = BrinksPatternLearner()
    patterns, report = learner.run(days=360)
