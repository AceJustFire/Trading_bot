"""
Tests unitaires pour src/market_data.py
"""

import unittest
import numpy as np
import pandas as pd

from src.config import TradingConfig
from src.market_data import MarketDataManager


class TestMarketData(unittest.TestCase):

    def setUp(self):
        self.config = TradingConfig.from_env()

    def test_extract_mid_price(self):
        """Vérifie le calcul correct du mid-price à partir des dictionnaires bid/ask."""
        node = {"bid": 4000.0, "ask": 4001.0}
        self.assertEqual(MarketDataManager._extract_mid_price(node), 4000.5)

        node_offer = {"bid": 4000.0, "offer": 4002.0}
        self.assertEqual(MarketDataManager._extract_mid_price(node_offer), 4001.0)

        self.assertEqual(MarketDataManager._extract_mid_price(None), 0.0)

    def test_compute_rsi_values(self):
        """Vérifie le calcul du RSI et les cas limites mathématiques."""
        # Série constante -> RSI neutre à 50
        flat = pd.Series([100.0] * 30)
        rsi_flat = MarketDataManager._compute_rsi(flat, period=14)
        self.assertEqual(rsi_flat.iloc[-1], 50.0)

        # Série en hausse perpétuelle -> RSI = 100
        uptrend = pd.Series([100.0 + i for i in range(30)])
        rsi_up = MarketDataManager._compute_rsi(uptrend, period=14)
        self.assertEqual(rsi_up.iloc[-1], 100.0)

        # Série en baisse perpétuelle -> RSI = 0
        downtrend = pd.Series([200.0 - i for i in range(30)])
        rsi_down = MarketDataManager._compute_rsi(downtrend, period=14)
        self.assertEqual(rsi_down.iloc[-1], 0.0)

    def test_compute_atr_positive(self):
        """Vérifie que l'ATR est strictement positif et non nul."""
        dates = pd.date_range("2026-01-01", periods=30, freq="15min")
        df = pd.DataFrame({
            "timestamp": dates,
            "open": [4100.0 + i for i in range(30)],
            "high": [4105.0 + i for i in range(30)],
            "low": [4095.0 + i for i in range(30)],
            "close": [4102.0 + i for i in range(30)],
            "volume": [100.0] * 30
        })

        atr = MarketDataManager._compute_atr(df, period=14)
        self.assertEqual(len(atr), 30)
        self.assertTrue((atr > 0).all())
        self.assertFalse(atr.isna().any())


if __name__ == "__main__":
    unittest.main()
