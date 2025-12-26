"""
MEXC Exchange Connector
=======================
Handles all communication with MEXC API for:
- Fetching OHLCV candles
- Fetching Order Book
- Placing orders (Paper & Live)
"""

import requests
import hmac
import hashlib
import time
from datetime import datetime
from config import settings

class MEXCConnector:
    BASE_URL = "https://api.mexc.com"
    
    def __init__(self):
        self.api_key = settings.API_KEY
        self.api_secret = settings.API_SECRET
        self.session = requests.Session()
        # Don't add API key to default headers - only for authenticated requests
        self.session.headers.update({
            "Content-Type": "application/json"
        })
    
    def _sign(self, params: dict) -> str:
        """Generate HMAC SHA256 signature for authenticated requests."""
        query_string = "&".join([f"{k}={v}" for k, v in sorted(params.items())])
        signature = hmac.new(
            self.api_secret.encode('utf-8'),
            query_string.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        return signature
    
    def get_server_time(self) -> int:
        """Get MEXC server time in milliseconds."""
        resp = self.session.get(f"{self.BASE_URL}/api/v3/time")
        return resp.json().get("serverTime", int(time.time() * 1000))
    
    def get_klines(self, symbol: str = None, interval: str = None, limit: int = 500) -> list:
        """
        Fetch OHLCV candlestick data.
        
        Args:
            symbol: Trading pair (default from settings)
            interval: Timeframe (1m, 5m, 15m, 1h, 4h, 1d)
            limit: Number of candles (max 1000)
        
        Returns:
            List of [timestamp, open, high, low, close, volume]
        """
        symbol = symbol or settings.SYMBOL
        interval = interval or settings.TIMEFRAME
        
        params = {
            "symbol": symbol,
            "interval": interval,
            "limit": limit
        }
        
        resp = self.session.get(f"{self.BASE_URL}/api/v3/klines", params=params)
        
        if resp.status_code != 200:
            print(f"Error fetching klines: {resp.text}")
            return []
        
        # MEXC returns: [openTime, open, high, low, close, volume, closeTime, ...]
        raw = resp.json()
        candles = []
        for k in raw:
            candles.append({
                "timestamp": datetime.fromtimestamp(k[0] / 1000),
                "open": float(k[1]),
                "high": float(k[2]),
                "low": float(k[3]),
                "close": float(k[4]),
                "volume": float(k[5])
            })
        return candles
    
    def get_order_book(self, symbol: str = None, limit: int = 20) -> dict:
        """
        Fetch Order Book depth.
        
        Returns:
            {"bids": [[price, qty], ...], "asks": [[price, qty], ...]}
        """
        symbol = symbol or settings.SYMBOL
        params = {"symbol": symbol, "limit": limit}
        
        resp = self.session.get(f"{self.BASE_URL}/api/v3/depth", params=params)
        
        if resp.status_code != 200:
            print(f"Error fetching order book: {resp.text}")
            return {"bids": [], "asks": []}
        
        data = resp.json()
        return {
            "bids": [[float(p), float(q)] for p, q in data.get("bids", [])],
            "asks": [[float(p), float(q)] for p, q in data.get("asks", [])]
        }
    
    def get_ticker_price(self, symbol: str = None) -> float:
        """Get current price for a symbol."""
        symbol = symbol or settings.SYMBOL
        resp = self.session.get(f"{self.BASE_URL}/api/v3/ticker/price", params={"symbol": symbol})
        
        if resp.status_code != 200:
            return 0.0
        
        return float(resp.json().get("price", 0))
    
    def get_account_balance(self) -> dict:
        """
        Get account balances (Authenticated).
        
        Returns:
            {"USDT": 10000.0, "BTC": 0.5, ...}
        """
        timestamp = self.get_server_time()
        params = {"timestamp": timestamp}
        params["signature"] = self._sign(params)
        
        resp = self.session.get(f"{self.BASE_URL}/api/v3/account", params=params)
        
        if resp.status_code != 200:
            print(f"Error fetching balance: {resp.text}")
            return {}
        
        balances = {}
        for asset in resp.json().get("balances", []):
            free = float(asset.get("free", 0))
            if free > 0:
                balances[asset["asset"]] = free
        
        return balances


# Quick test
if __name__ == "__main__":
    mexc = MEXCConnector()
    
    print("--- Testing MEXC Connector ---")
    
    # Test public endpoints (no API key needed)
    print(f"Server Time: {mexc.get_server_time()}")
    print(f"BTC Price: ${mexc.get_ticker_price():.2f}")
    
    candles = mexc.get_klines(limit=5)
    print(f"Last 5 Candles:")
    for c in candles[-5:]:
        print(f"  {c['timestamp']} | O:{c['open']:.2f} H:{c['high']:.2f} L:{c['low']:.2f} C:{c['close']:.2f}")
    
    ob = mexc.get_order_book(limit=5)
    print(f"Order Book (Top 5):")
    print(f"  Bids: {ob['bids'][:3]}")
    print(f"  Asks: {ob['asks'][:3]}")
