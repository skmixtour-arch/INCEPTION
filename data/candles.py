"""
Candle Data Handler
===================
Converts raw kline data to pandas DataFrame with indicators.
"""

import pandas as pd
import numpy as np
from config import settings


def klines_to_dataframe(klines: list) -> pd.DataFrame:
    """
    Convert list of kline dicts to a pandas DataFrame.
    
    Args:
        klines: List of dicts with timestamp, open, high, low, close, volume
    
    Returns:
        DataFrame indexed by timestamp
    """
    if not klines:
        return pd.DataFrame()
    
    df = pd.DataFrame(klines)
    df.set_index("timestamp", inplace=True)
    df.sort_index(inplace=True)
    return df


def add_emas(df: pd.DataFrame, periods: list = [5, 13, 50, 200, 800]) -> pd.DataFrame:
    """Add EMA columns to dataframe."""
    for period in periods:
        df[f"ema_{period}"] = df["close"].ewm(span=period, adjust=False).mean()
    return df


def add_volume_average(df: pd.DataFrame, period: int = None) -> pd.DataFrame:
    """Add average volume column."""
    period = period or settings.VOLUME_AVG_PERIOD
    df["vol_avg"] = df["volume"].rolling(window=period).mean()
    return df


def prepare_dataframe(klines: list) -> pd.DataFrame:
    """
    Full pipeline: klines -> DataFrame with all indicators.
    """
    df = klines_to_dataframe(klines)
    if df.empty:
        return df
    
    df = add_emas(df)
    df = add_volume_average(df)
    
    return df
