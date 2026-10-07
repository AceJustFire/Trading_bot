"""
Tests unitaires pour src/strategy.py
"""

import unittest
import numpy as np
import pandas as pd

from src.config import TradingConfig
from src.strategy import SignalType, TradeSignal, TrendMomentumATRStrategy


class TestTrendMomentumATRStrategy(unittest.TestCase):

    def setUp(self):
        self.config = TradingConfig.from_env()
        self.strategy = TrendMomentumATRStrategy(self.config, mode="active")

    def test_immediate_buy_signal(self):
        """Vérifie la génération d'un signal d'achat manuel 1-Click."""
        current_price = 4150.0
        current_atr = 5.0
        signal = self.strategy.create_immediate_signal(
            direction="BUY",
            current_price=current_price,
            current_atr=current_atr,
        )

        self.assertEqual(signal.action, SignalType.BUY)
        self.assertEqual(signal.entry_price, current_price)
        self.assertIsNotNone(signal.stop_loss)
        self.assertIsNotNone(signal.take_profit)
        self.assertLess(signal.stop_loss, current_price)
        self.assertGreater(signal.take_profit, current_price)
        # Vérifie la distance minimale garantie (GSL) de 0.35% minimum
        min_gsl = current_price * 0.0035
        self.assertGreaterEqual(current_price - signal.stop_loss, min_gsl - 0.01)

    def test_immediate_sell_signal(self):
        """Vérifie la génération d'un signal de vente manuel 1-Click."""
        current_price = 4150.0
        current_atr = 5.0
        signal = self.strategy.create_immediate_signal(
            direction="SELL",
            current_price=current_price,
            current_atr=current_atr,
        )

        self.assertEqual(signal.action, SignalType.SELL)
        self.assertEqual(signal.entry_price, current_price)
        self.assertIsNotNone(signal.stop_loss)
        self.assertIsNotNone(signal.take_profit)
        self.assertGreater(signal.stop_loss, current_price)
        self.assertLess(signal.take_profit, current_price)
        min_gsl = current_price * 0.0035
        self.assertGreaterEqual(signal.stop_loss - current_price, min_gsl - 0.01)

    def test_insufficient_candles_returns_wait(self):
        """Vérifie qu'un DataFrame de moins de 30 bougies retourne SignalType.WAIT."""
        df_short = pd.DataFrame({
            "timestamp": pd.date_range("2026-01-01", periods=10, freq="15min"),
            "open": [4100.0] * 10,
            "high": [4110.0] * 10,
            "low": [4090.0] * 10,
            "close": [4105.0] * 10,
            "volume": [100.0] * 10,
            "ema_fast": [4102.0] * 10,
            "ema_slow": [4100.0] * 10,
            "rsi": [55.0] * 10,
            "atr": [5.0] * 10,
        })
        sig = self.strategy.generate_signal(df_short)
        self.assertEqual(sig.action, SignalType.WAIT)
        self.assertIn("insuffisant", sig.reason.lower())

    def test_active_mode_bullish_signal(self):
        """Vérifie qu'une tendance haussière active déclenche un signal BUY."""
        n = 40
        dates = pd.date_range("2026-01-01", periods=n, freq="15min")
        # Série haussière
        closes = [4100.0 + i * 2.0 for i in range(n)]
        opens = [c - 1.0 for c in closes]
        df = pd.DataFrame({
            "timestamp": dates,
            "open": opens,
            "high": [c + 2.0 for c in closes],
            "low": [o - 1.0 for o in opens],
            "close": closes,
            "volume": [100.0] * n,
            "ema_fast": [c - 2.0 for c in closes],
            "ema_slow": [c - 5.0 for c in closes],
            "rsi": [55.0] * n,
            "atr": [6.0] * n,
        })

        self.strategy.set_mode("active")
        signal = self.strategy.generate_signal(df)
        self.assertEqual(signal.action, SignalType.BUY)
        self.assertIsNotNone(signal.stop_loss)
        self.assertIsNotNone(signal.take_profit)

    def test_active_mode_bearish_signal(self):
        """Vérifie qu'une tendance baissière active déclenche un signal SELL."""
        n = 40
        dates = pd.date_range("2026-01-01", periods=n, freq="15min")
        # Série baissière
        closes = [4200.0 - i * 2.0 for i in range(n)]
        opens = [c + 1.0 for c in closes]
        df = pd.DataFrame({
            "timestamp": dates,
            "open": opens,
            "high": [o + 1.0 for o in opens],
            "low": [c - 2.0 for c in closes],
            "close": closes,
            "volume": [100.0] * n,
            "ema_fast": [c + 2.0 for c in closes],
            "ema_slow": [c + 5.0 for c in closes],
            "rsi": [45.0] * n,
            "atr": [6.0] * n,
        })

        self.strategy.set_mode("active")
        signal = self.strategy.generate_signal(df)
        self.assertEqual(signal.action, SignalType.SELL)
        self.assertIsNotNone(signal.stop_loss)
        self.assertIsNotNone(signal.take_profit)


if __name__ == "__main__":
    unittest.main()
