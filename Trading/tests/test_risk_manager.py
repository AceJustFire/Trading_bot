"""
Tests unitaires pour src/risk_manager.py
"""

from datetime import datetime
import unittest
from unittest.mock import MagicMock

from src.config import TradingConfig
from src.market_data import MarketSnapshot
from src.risk_manager import AccountFinancials, RiskCheckResult, RiskManager
from src.strategy import SignalType, TradeSignal
import pandas as pd


class TestRiskManager(unittest.TestCase):

    def setUp(self):
        self.config = TradingConfig.from_env()
        self.mock_auth = MagicMock()
        self.risk_manager = RiskManager(self.config, self.mock_auth)

        # Mock finances pour tests déterministes sans appel réseau
        self.mock_financials = AccountFinancials(
            account_id="330847176266952990",
            balance=1000.0,
            equity=1000.0,
            available=1000.0,
            currency="USD",
        )
        self.risk_manager.fetch_account_financials = MagicMock(return_value=self.mock_financials)
        self.risk_manager.start_day_equity = 1000.0

    def test_daily_drawdown_limit(self):
        """Vérifie le déclenchement du coupe-circuit de perte journalière (3%)."""
        # Perte de 1% (10 USD) -> OK
        self.assertTrue(self.risk_manager.evaluate_daily_drawdown(990.0))
        self.assertFalse(self.risk_manager.daily_drawdown_limit_hit)

        # Perte de 4% (40 USD > 3% max) -> Coupe-circuit
        self.assertFalse(self.risk_manager.evaluate_daily_drawdown(960.0))
        self.assertTrue(self.risk_manager.daily_drawdown_limit_hit)

    def test_reject_wait_signal(self):
        """Vérifie le rejet immédiat d'un signal d'attente (WAIT)."""
        snapshot = MarketSnapshot(
            epic="GOLD",
            market_status="TRADEABLE",
            bid=4150.0,
            ask=4150.5,
            spread=0.5,
            min_deal_size=0.01,
            size_increment=0.01,
            is_tradeable=True,
        )
        sig = TradeSignal(
            action=SignalType.WAIT,
            entry_price=4150.0,
            stop_loss=None,
            take_profit=None,
            atr_value=5.0,
            reason="Attente",
            timestamp=pd.Timestamp.now(),
        )
        res = self.risk_manager.validate_and_size_order(sig, snapshot, 0)
        self.assertFalse(res.is_approved)

    def test_reject_market_closed(self):
        """Vérifie le rejet si le marché est fermé ou non négociable."""
        snapshot = MarketSnapshot(
            epic="GOLD",
            market_status="CLOSED",
            bid=4150.0,
            ask=4150.5,
            spread=0.5,
            min_deal_size=0.01,
            size_increment=0.01,
            is_tradeable=False,
        )
        sig = TradeSignal(
            action=SignalType.BUY,
            entry_price=4150.5,
            stop_loss=4135.0,
            take_profit=4175.0,
            atr_value=5.0,
            reason="Achat",
            timestamp=pd.Timestamp.now(),
        )
        res = self.risk_manager.validate_and_size_order(sig, snapshot, 0)
        self.assertFalse(res.is_approved)
        self.assertIn("non négociable", res.reason.lower())

    def test_reject_max_positions_reached(self):
        """Vérifie le rejet si le nombre max de positions est atteint."""
        snapshot = MarketSnapshot(
            epic="GOLD",
            market_status="TRADEABLE",
            bid=4150.0,
            ask=4150.5,
            spread=0.5,
            min_deal_size=0.01,
            size_increment=0.01,
            is_tradeable=True,
        )
        sig = TradeSignal(
            action=SignalType.BUY,
            entry_price=4150.5,
            stop_loss=4135.0,
            take_profit=4175.0,
            atr_value=5.0,
            reason="Achat",
            timestamp=pd.Timestamp.now(),
        )
        # 1 position déjà ouverte alors que max = 1
        res = self.risk_manager.validate_and_size_order(sig, snapshot, current_open_positions_count=1)
        self.assertFalse(res.is_approved)
        self.assertIn("positions atteint", res.reason.lower())

    def test_reject_excessive_spread(self):
        """Vérifie le rejet si le spread dépasse la limite configurée."""
        snapshot = MarketSnapshot(
            epic="GOLD",
            market_status="TRADEABLE",
            bid=4150.0,
            ask=4152.0,  # Spread = 2.0 > 1.0 max
            spread=2.0,
            min_deal_size=0.01,
            size_increment=0.01,
            is_tradeable=True,
        )
        sig = TradeSignal(
            action=SignalType.BUY,
            entry_price=4152.0,
            stop_loss=4135.0,
            take_profit=4175.0,
            atr_value=5.0,
            reason="Achat",
            timestamp=pd.Timestamp.now(),
        )
        res = self.risk_manager.validate_and_size_order(sig, snapshot, 0)
        self.assertFalse(res.is_approved)
        self.assertIn("spread trop élevé", res.reason.lower())

    def test_reject_incoherent_stop_loss(self):
        """Vérifie le rejet si le Stop Loss est au-dessus du prix Ask en BUY."""
        snapshot = MarketSnapshot(
            epic="GOLD",
            market_status="TRADEABLE",
            bid=4150.0,
            ask=4150.5,
            spread=0.5,
            min_deal_size=0.01,
            size_increment=0.01,
            is_tradeable=True,
        )
        sig = TradeSignal(
            action=SignalType.BUY,
            entry_price=4150.5,
            stop_loss=4160.0,  # Incohérent : SL > Ask
            take_profit=4175.0,
            atr_value=5.0,
            reason="Achat erroné",
            timestamp=pd.Timestamp.now(),
        )
        res = self.risk_manager.validate_and_size_order(sig, snapshot, 0)
        self.assertFalse(res.is_approved)
        self.assertIn("incohérence sl", res.reason.lower())

    def test_valid_position_sizing_calculation(self):
        """Vérifie le dimensionnement de position exact (1% de risque)."""
        snapshot = MarketSnapshot(
            epic="GOLD",
            market_status="TRADEABLE",
            bid=4150.0,
            ask=4150.5,
            spread=0.5,
            min_deal_size=0.01,
            size_increment=0.01,
            is_tradeable=True,
        )
        # Équité = 1000 USD, 1% de risque = 10 USD
        # Distance SL = 4150.5 - 4135.5 = 15.0 USD
        # Taille théorique = 10 / 15 = 0.666 -> arrondi à 0.66
        sig = TradeSignal(
            action=SignalType.BUY,
            entry_price=4150.5,
            stop_loss=4135.5,
            take_profit=4180.0,
            atr_value=5.0,
            reason="Achat valide",
            timestamp=pd.Timestamp.now(),
        )
        res = self.risk_manager.validate_and_size_order(sig, snapshot, 0)
        self.assertTrue(res.is_approved)
        self.assertEqual(res.position_size, 0.66)

    def test_set_leverage_clamping(self):
        """Vérifie que l'effet de levier est bien contraint entre 1:1 et 20:1 maximum."""
        self.assertEqual(self.risk_manager.set_leverage(1), 1)
        self.assertEqual(self.risk_manager.set_leverage(20), 20)
        # Clamping au-delà du max légal 20:1
        self.assertEqual(self.risk_manager.set_leverage(50), 20)
        # Clamping sous le min 1:1
        self.assertEqual(self.risk_manager.set_leverage(0), 1)

    def test_set_capital_risk_percent(self):
        """Vérifie la mise à jour dynamique du % de capital tradé."""
        self.assertEqual(self.risk_manager.set_capital_risk_percent(2.0), 2.0)
        self.assertAlmostEqual(self.risk_manager.capital_risk_percent, 0.02)
        # Gestion des entrées décimales (ex: 0.05 -> 5%)
        self.assertEqual(self.risk_manager.set_capital_risk_percent(0.05), 5.0)

    def test_leverage_caps_max_size_when_low(self):
        """Vérifie qu'un levier faible (ex: 1:1) bride la taille de position pour ne pas excéder la marge."""
        snapshot = MarketSnapshot(
            epic="GOLD",
            market_status="TRADEABLE",
            bid=4150.0,
            ask=4150.0,
            spread=0.5,
            min_deal_size=0.01,
            size_increment=0.01,
            is_tradeable=True,
        )
        # Avec Equity=1000$ et Levier 1:1 (Cash), capacité notionnelle max = 1000$
        # À 4150$, taille max autorisée = 1000 / 4150 = 0.24 lot
        self.risk_manager.set_leverage(1)
        self.risk_manager.set_capital_risk_percent(5.0)  # 5% risque = 50$
        # Avec SL à 10$ de distance, la formule de risque pure donnerait 50/10 = 5.0 lots
        # Mais le levier 1:1 doit brider la position à 0.24 lot max !
        sig = TradeSignal(
            action=SignalType.BUY,
            entry_price=4150.0,
            stop_loss=4140.0,
            take_profit=4170.0,
            atr_value=5.0,
            reason="Achat test levier 1:1",
            timestamp=pd.Timestamp.now(),
        )
        res = self.risk_manager.validate_and_size_order(sig, snapshot, 0)
        self.assertTrue(res.is_approved)
        self.assertLessEqual(res.position_size, 0.25)


if __name__ == "__main__":
    unittest.main()
