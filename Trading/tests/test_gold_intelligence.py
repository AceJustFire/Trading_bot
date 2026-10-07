"""
Tests unitaires pour src/gold_intelligence.py
Valide l'analyse multi-factorielle des 5 piliers :
1. Macro & Taux Réels
2. Géopolitique & Sentiment VIX
3. Flux Institutionnels & Physique
4. Price Action & Smart Money Concepts (SMC)
5. Microstructure & Horaires de session
"""

import unittest
from datetime import datetime, timezone
import pandas as pd
import numpy as np

from src.gold_intelligence import GoldIntelligenceEngine, SMCFeatures, SessionTelemetry


class TestGoldIntelligence(unittest.TestCase):

    def setUp(self):
        self.engine = GoldIntelligenceEngine()

    def test_hammer_pin_bar_detection(self):
        """Vérifie la détection d'un marteau / pin bar haussière avec rejet de liquidité."""
        # Bougie avec très longue mèche basse (75% du range) et petit corps en haut
        df = pd.DataFrame({
            "timestamp": pd.date_range("2026-01-01", periods=6, freq="15min"),
            "open": [4150.0, 4150.0, 4150.0, 4150.0, 4148.0, 4150.0],
            "high": [4155.0, 4155.0, 4155.0, 4155.0, 4150.0, 4150.0],
            "low": [4145.0, 4145.0, 4145.0, 4145.0, 4120.0, 4145.0],  # Longue mèche basse sur bougie -2
            "close": [4150.0, 4150.0, 4150.0, 4150.0, 4149.0, 4150.0],
            "volume": [100.0] * 6,
        })

        smc = self.engine.analyze_candlesticks_and_smc(df, current_spot=4150.0)
        self.assertTrue(smc.is_hammer or smc.is_pin_bar)
        self.assertEqual(smc.candlestick_direction, "BULLISH")
        self.assertIn("Marteau", smc.candlestick_pattern)

    def test_shooting_star_detection(self):
        """Vérifie la détection d'une étoile filante (Shooting Star / rejet des sommets)."""
        # Bougie avec très longue mèche haute et petit corps en bas
        df = pd.DataFrame({
            "timestamp": pd.date_range("2026-01-01", periods=6, freq="15min"),
            "open": [4150.0, 4150.0, 4150.0, 4150.0, 4122.0, 4120.0],
            "high": [4155.0, 4155.0, 4155.0, 4155.0, 4150.0, 4125.0],  # Longue mèche haute sur bougie -2
            "low": [4145.0, 4145.0, 4145.0, 4145.0, 4120.0, 4118.0],
            "close": [4150.0, 4150.0, 4150.0, 4150.0, 4121.0, 4120.0],
            "volume": [100.0] * 6,
        })

        smc = self.engine.analyze_candlesticks_and_smc(df, current_spot=4120.0)
        self.assertTrue(smc.is_shooting_star or smc.is_pin_bar)
        self.assertEqual(smc.candlestick_direction, "BEARISH")
        self.assertIn("Étoile Filante", smc.candlestick_pattern)

    def test_doji_indecision_detection(self):
        """Vérifie la détection d'un Doji d'indécision (corps minuscule < 12% du range)."""
        df = pd.DataFrame({
            "timestamp": pd.date_range("2026-01-01", periods=6, freq="15min"),
            "open": [4150.0, 4150.0, 4150.0, 4150.0, 4140.0, 4140.0],
            "high": [4155.0, 4155.0, 4155.0, 4155.0, 4150.0, 4145.0],
            "low": [4145.0, 4145.0, 4145.0, 4145.0, 4130.0, 4135.0],
            "close": [4150.0, 4150.0, 4150.0, 4150.0, 4140.1, 4140.0],  # Corps = 0.1 sur range de 20
            "volume": [100.0] * 6,
        })

        smc = self.engine.analyze_candlesticks_and_smc(df, current_spot=4140.0)
        self.assertTrue(smc.is_doji)
        self.assertEqual(smc.candlestick_direction, "NEUTRAL")
        self.assertIn("Doji", smc.candlestick_pattern)

    def test_fvg_bullish_detection(self):
        """Vérifie la détection d'un Fair Value Gap (déséquilibre) haussier."""
        # 3 bougies consécutives : candle_1 low > candle_3 high
        df = pd.DataFrame({
            "timestamp": pd.date_range("2026-01-01", periods=6, freq="15min"),
            "open": [4100.0, 4100.0, 4110.0, 4110.0, 4135.0, 4140.0],
            "high": [4105.0, 4105.0, 4115.0, 4125.0, 4145.0, 4150.0],
            "low": [4095.0, 4095.0, 4105.0, 4110.0, 4130.0, 4138.0],  # candle_1 low = 4130 > candle_3 high (4115)
            "close": [4102.0, 4102.0, 4112.0, 4124.0, 4142.0, 4145.0],
            "volume": [100.0] * 6,
        })

        smc = self.engine.analyze_candlesticks_and_smc(df, current_spot=4142.0)
        self.assertTrue(smc.fvg_detected)
        self.assertEqual(smc.fvg_type, "BULLISH_FVG")
        self.assertGreater(smc.fvg_zone[1], smc.fvg_zone[0])

    def test_psychological_round_level_distance(self):
        """Vérifie le calcul exact du chiffre rond psychologique ($50 ou $100)."""
        df = pd.DataFrame({
            "timestamp": pd.date_range("2026-01-01", periods=6, freq="15min"),
            "open": [4150.0] * 6, "high": [4155.0] * 6, "low": [4145.0] * 6, "close": [4150.0] * 6, "volume": [100.0] * 6,
        })

        # Cours à 4154.80 -> Proche de 4150.00 (distance = 4.80)
        smc_50 = self.engine.analyze_candlesticks_and_smc(df, current_spot=4154.80)
        self.assertEqual(smc_50.nearest_round_level, 4150.0)
        self.assertAlmostEqual(smc_50.distance_to_round_level, 4.80, places=2)

        # Cours à 4198.20 -> Proche de 4200.00 (distance = 1.80, Seuil Majeur 100$)
        smc_100 = self.engine.analyze_candlesticks_and_smc(df, current_spot=4198.20)
        self.assertEqual(smc_100.nearest_round_level, 4200.0)
        self.assertAlmostEqual(smc_100.distance_to_round_level, 1.80, places=2)
        self.assertIn("100$", smc_100.round_level_type)

    def test_microstructure_telemetry(self):
        """Vérifie la télémétrie de session et les règles de microstructure."""
        session = self.engine.analyze_microstructure_and_session()
        self.assertIsNotNone(session.active_session_name)
        self.assertIsNotNone(session.session_liquidity_profile)
        self.assertIn(session.is_overlap_london_ny, (True, False))
        self.assertIn(session.is_rollover_blackout, (True, False))

    def test_complete_intelligence_report_synthesis(self):
        """Vérifie que la synthèse complète des 5 piliers produit toutes les métriques requises."""
        n = 35
        df = pd.DataFrame({
            "timestamp": pd.date_range("2026-01-01", periods=n, freq="15min"),
            "open": [4140.0 + i * 0.5 for i in range(n)],
            "high": [4145.0 + i * 0.5 for i in range(n)],
            "low": [4138.0 + i * 0.5 for i in range(n)],
            "close": [4143.0 + i * 0.5 for i in range(n)],
            "volume": [100.0] * n,
            "ema_fast": [4142.0 + i * 0.5 for i in range(n)],
            "ema_slow": [4140.0 + i * 0.5 for i in range(n)],
            "rsi": [58.0] * n,
            "atr": [6.5] * n,
        })

        report = self.engine.generate_intelligence_report(
            current_spot=4160.0,
            df_indicators=df,
            current_spread=0.50,
        )

        self.assertIn(report.composite_bias, ("FORTEMENT HAUSSIER", "HAUSSIER", "NEUTRE (ÉQUILIBRE)", "BAISSIER", "FORTEMENT BAISSIER"))
        self.assertGreaterEqual(report.confidence_percent, 50)
        self.assertEqual(report.bullish_probability + report.bearish_probability, 100)
        self.assertGreater(report.target_1, 0)
        self.assertGreater(report.target_2, 0)
        self.assertGreater(report.invalidation_level, 0)
        self.assertIsNotNone(report.decision_summary)
        self.assertGreater(len(report.positive_catalysts), 0)
        self.assertIn("us_10y_yield", report.macro_data)
        self.assertIn("candlestick_pattern", report.smc_data)
        self.assertIn("active_session_name", report.session_data)


if __name__ == "__main__":
    unittest.main()
