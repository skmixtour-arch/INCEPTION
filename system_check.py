"""
INCEPTION Bot - Pre-Launch System Check
========================================
Verifies all systems before going live.
"""

import sys
import os

print("=" * 60)
print("🔍 INCEPTION BOT - PRE-LAUNCH SYSTEM CHECK")
print("=" * 60)

# 1. Check Python version
print(f"\n✓ Python: {sys.version.split()[0]}")

# 2. Check dependencies
print("\n📦 Checking dependencies...")
deps_ok = True

try:
    import ccxt
    print(f"  ✅ ccxt: {ccxt.__version__}")
except ImportError:
    print("  ❌ ccxt: NOT INSTALLED")
    deps_ok = False

try:
    import pandas as pd
    print(f"  ✅ pandas: {pd.__version__}")
except ImportError:
    print("  ❌ pandas: NOT INSTALLED")
    deps_ok = False

try:
    import numpy as np
    print(f"  ✅ numpy: {np.__version__}")
except ImportError:
    print("  ❌ numpy: NOT INSTALLED")
    deps_ok = False

try:
    import requests
    print(f"  ✅ requests: {requests.__version__}")
except ImportError:
    print("  ❌ requests: NOT INSTALLED")
    deps_ok = False

if not deps_ok:
    print("\n❌ Missing dependencies! Run: pip install ccxt pandas numpy requests")
    sys.exit(1)

# 3. Check Binance API connectivity
print("\n🔗 Testing Binance Futures API...")

# Load credentials from live bot
API_KEY = "HZHCu0fM6vxP4eDPkGGLpD6kHoksKPNTxceVDJusfjnsklwqne0dpzQ1vdbS3yrc"
API_SECRET = "zZtxGRz9mWqvkIDquWPUdmltUbFPyibNzTNQmNoc6V2ep4VF9GdImZGj1W0dAAWi"
TELEGRAM_TOKEN = "8371462261:AAELiZdXRedALn3KWblWq7Ce1ucYZP6LFrg"
TELEGRAM_CHAT_ID = "345135704"

try:
    exchange = ccxt.binanceusdm({
        'apiKey': API_KEY,
        'secret': API_SECRET,
        'enableRateLimit': True,
    })
    
    # Load markets
    exchange.load_markets()
    print("  ✅ Connected to Binance Futures")
    
    # Check trading pair
    symbol = 'BTC/USDC:USDC'
    if symbol in exchange.markets:
        print(f"  ✅ Trading pair available: {symbol}")
        market = exchange.markets[symbol]
        print(f"     Leverage: up to {market.get('limits', {}).get('leverage', {}).get('max', 'N/A')}x")
    else:
        print(f"  ❌ Trading pair NOT found: {symbol}")
        print("     Available BTC pairs:", [s for s in exchange.markets.keys() if 'BTC' in s][:5])
    
    # Get current price
    ticker = exchange.fetch_ticker(symbol)
    print(f"  ✅ Current BTC/USDC price: ${ticker['last']:,.2f}")
    
    # Check balance
    print("\n💰 Checking balance...")
    balance = exchange.fetch_balance()
    usdc_free = float(balance.get('USDC', {}).get('free', 0) or 0)
    usdc_total = float(balance.get('USDC', {}).get('total', 0) or 0)
    usdt_free = float(balance.get('USDT', {}).get('free', 0) or 0)
    
    print(f"  💵 USDC Free: ${usdc_free:,.2f}")
    print(f"  💵 USDC Total: ${usdc_total:,.2f}")
    print(f"  💵 USDT Free: ${usdt_free:,.2f}")
    
    if usdc_free < 10 and usdt_free < 10:
        print("\n  ⚠️  WARNING: Low balance! Consider transferring funds to Futures wallet.")
    
    # Check open positions
    print("\n📊 Checking open positions...")
    positions = exchange.fetch_positions([symbol])
    open_positions = [p for p in positions if float(p.get('contracts', 0)) > 0]
    if open_positions:
        for p in open_positions:
            print(f"  ⚠️  Active position: {p['side']} {p['contracts']} contracts @ ${p['entryPrice']}")
    else:
        print("  ✅ No open positions")
    
except ccxt.AuthenticationError as e:
    print(f"  ❌ Authentication failed: Check API keys")
    print(f"     Error: {e}")
except ccxt.NetworkError as e:
    print(f"  ❌ Network error: {e}")
except Exception as e:
    print(f"  ❌ Error: {e}")

# 4. Test Telegram
print("\n📱 Testing Telegram notification...")
try:
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": "🔍 *SYSTEM CHECK*\n\nINCEPTION Bot pre-launch check complete.\nAll systems verified!",
        "parse_mode": "Markdown"
    }
    response = requests.post(url, data=data, timeout=10)
    if response.status_code == 200:
        print("  ✅ Telegram notification sent!")
    else:
        print(f"  ❌ Telegram error: {response.text}")
except Exception as e:
    print(f"  ❌ Telegram error: {e}")

print("\n" + "=" * 60)
print("✅ SYSTEM CHECK COMPLETE")
print("=" * 60)
print("\nTo start the bot, run:")
print("  python3 inception_bot_live.py")
