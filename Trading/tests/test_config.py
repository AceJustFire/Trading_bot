"""
Tests unitaires pour src/config.py
"""

import os
import unittest
from src.config import TradingConfig


class TestTradingConfig(unittest.TestCase):

    def test_config_from_env(self):
        """Vérifie le bon chargement des variables d'environnement."""
        config = TradingConfig.from_env()
        self.assertIsNotNone(config.api_key)
        self.assertEqual(config.epic, "GOLD")
        self.assertIn(config.environment, ("demo", "live"))
        self.assertGreater(config.poll_interval_seconds, 0)
        self.assertGreater(config.max_allowed_spread, 0)
        self.assertEqual(config.max_open_positions, 1)

    def test_missing_identifier_raises_value_error(self):
        """Vérifie qu'un identifiant manquant ou factice soulève une ValueError explicite."""
        old_val = os.environ.get("CAPITAL_IDENTIFIER")
        try:
            os.environ["CAPITAL_IDENTIFIER"] = "votre_email@exemple.com"
            with self.assertRaises(ValueError):
                TradingConfig.from_env()
        finally:
            if old_val:
                os.environ["CAPITAL_IDENTIFIER"] = old_val


if __name__ == "__main__":
    unittest.main()
