"""
Base Strategy Class
====================
Abstract class that all strategies must inherit from.
"""

from abc import ABC, abstractmethod
import pandas as pd


class BaseStrategy(ABC):
    """
    Abstract base for all trading strategies.
    
    All strategies must implement:
    - generate_signals(df) -> pd.Series of floats between -1.0 and 1.0
    """
    
    def __init__(self, name: str):
        self.name = name
    
    def get_name(self) -> str:
        return self.name
    
    @abstractmethod
    def generate_signals(self, df: pd.DataFrame) -> pd.Series:
        """
        Analyze the DataFrame and return a Series of signals.
        
        Returns:
            pd.Series with values:
                1.0  = Strong BUY
                0.5  = Weak BUY
                0.0  = No Signal
               -0.5  = Weak SELL
               -1.0  = Strong SELL
        """
        pass
