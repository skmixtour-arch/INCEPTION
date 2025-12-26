# INCEPTION Bot
## Brinks Box V4 Trading Strategy

```
██╗███╗   ██╗ ██████╗███████╗██████╗ ████████╗██╗ ██████╗ ███╗   ██╗
██║████╗  ██║██╔════╝██╔════╝██╔══██╗╚══██╔══╝██║██╔═══██╗████╗  ██║
██║██╔██╗ ██║██║     █████╗  ██████╔╝   ██║   ██║██║   ██║██╔██╗ ██║
██║██║╚██╗██║██║     ██╔══╝  ██╔═══╝    ██║   ██║██║   ██║██║╚██╗██║
██║██║ ╚████║╚██████╗███████╗██║        ██║   ██║╚██████╔╝██║ ╚████║
╚═╝╚═╝  ╚═══╝ ╚═════╝╚══════╝╚═╝        ╚═╝   ╚═╝ ╚═════╝ ╚═╝  ╚═══╝
```

### 90-Day Backtest Results
| Metric | Value |
|--------|-------|
| **Win Rate** | 45.6% |
| **Return** | +441.92% |
| **Max Drawdown** | -57.0% |
| **Total Trades** | 57 |

### Configuration
| Setting | Value |
|---------|-------|
| Stop Loss | 1.0% |
| Take Profit | 2.1% |
| Leverage | 10x |
| Timeframe | 1H |
| Sessions | Mon-Fri only |

### Strategy Features (V4)
- ✅ Vector Recovery Logic
- ✅ Stop-Hunt Detection (14:15-14:45)
- ✅ Brinks Position Analysis
- ✅ Premium/Discount Zones (Monday Asian)
- ✅ Asian Sweep Traps
- ✅ Trend Alignment (EMA 50/200)
- ✅ London Direction
- ✅ Scoring System (require >= 3)

## Quick Start

### Paper Trading (Default)
```bash
cd trading_bot
python3 inception_bot.py
```

### Run Continuously
Edit `inception_bot.py` and uncomment:
```python
bot.run(interval_seconds=60)
```

## Project Structure
```
trading_bot/
├── inception_bot.py      # Main trading bot
├── strategies/
│   ├── brinks_box_v4.py  # V4 Strategy (current)
│   ├── brinks_box_v3.py  # V3 Strategy
│   ├── brinks_box_v2.py  # V2 Strategy
│   └── brinks_box.py     # V1 Strategy
├── config/
│   └── settings.py       # Configuration
├── exchange/
│   └── mexc.py           # Exchange connector
├── data/
│   └── candles.py        # Data handling
└── docs/
    └── liquidity_knowledge_base.md
```

## License
Private - All Rights Reserved
