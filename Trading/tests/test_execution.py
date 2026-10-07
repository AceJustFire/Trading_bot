"""
Tests unitaires pour src/execution.py
"""

import unittest
from unittest.mock import MagicMock, patch
import pandas as pd
import requests

from src.config import TradingConfig
from src.execution import ExecutionManager, PositionDetails
from src.strategy import SignalType, TradeSignal


class TestExecutionManager(unittest.TestCase):

    def setUp(self):
        self.config = TradingConfig.from_env()
        self.mock_auth = MagicMock()
        self.execution = ExecutionManager(self.config, self.mock_auth)

    def test_get_open_positions_parsing(self):
        """Vérifie l'extraction rigoureuse des positions et le fallback market.epic."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "positions": [
                {
                    "position": {
                        "dealId": "deal-12345",
                        "direction": "BUY",
                        "size": 0.50,
                        "level": 4150.25,
                        "stopLevel": 4135.0,
                        "profitLevel": 4180.0,
                        "upl": 12.50,
                        "createdDate": "2026-10-06T14:00:00",
                    },
                    "market": {
                        "epic": "GOLD",
                        "instrumentName": "Spot Gold",
                    },
                },
                {
                    "position": {
                        "dealId": "deal-99999",
                        "direction": "SELL",
                        "size": 1.0,
                        "level": 1.0850,
                        "stopLevel": 1.0900,
                        "profitLevel": 1.0750,
                        "upl": -5.0,
                        "createdDate": "2026-10-06T14:10:00",
                    },
                    "market": {
                        "epic": "EURUSD",
                    },
                },
            ]
        }
        self.mock_auth.request_with_reauth.return_value = mock_response

        # Filtrage par défaut sur GOLD
        positions = self.execution.get_open_positions(epic="GOLD")
        self.assertEqual(len(positions), 1)
        pos = positions[0]
        self.assertEqual(pos.deal_id, "deal-12345")
        self.assertEqual(pos.epic, "GOLD")
        self.assertEqual(pos.direction, "BUY")
        self.assertEqual(pos.size, 0.50)
        self.assertEqual(pos.open_level, 4150.25)
        self.assertEqual(pos.upl, 12.50)

    def test_execute_market_order_guaranteed_stop_payload(self):
        """Vérifie que guaranteedStop est bien True dans le payload envoyé à Capital.com."""
        mock_post_resp = MagicMock()
        mock_post_resp.status_code = 200
        mock_post_resp.json.return_value = {"dealReference": "ref-abc-123"}
        self.mock_auth.request_with_reauth.return_value = mock_post_resp

        # Mock de la méthode de confirmation pour retourner directement l'ID
        self.execution._wait_for_order_confirmation = MagicMock(return_value="deal-real-id-777")

        sig = TradeSignal(
            action=SignalType.BUY,
            entry_price=4150.0,
            stop_loss=4135.0,
            take_profit=4180.0,
            atr_value=5.0,
            reason="Test Buy",
            timestamp=pd.Timestamp.now(),
        )

        result = self.execution.execute_market_order(sig, size=0.25)
        self.assertEqual(result, "deal-real-id-777")

        # Vérification du payload envoyé
        self.mock_auth.request_with_reauth.assert_called_with(
            "POST",
            "positions",
            json={
                "epic": "GOLD",
                "direction": "BUY",
                "size": 0.25,
                "guaranteedStop": True,
                "stopLevel": 4135.0,
                "profitLevel": 4180.0,
            },
        )

    def test_close_position_success(self):
        """Vérifie l'envoi de la requête DELETE pour clôturer une position."""
        mock_del_resp = MagicMock()
        mock_del_resp.status_code = 200
        mock_del_resp.json.return_value = {"dealReference": "close-ref-999"}
        self.mock_auth.request_with_reauth.return_value = mock_del_resp

        ok = self.execution.close_position("deal-12345")
        self.assertTrue(ok)
        self.mock_auth.request_with_reauth.assert_called_with("DELETE", "positions/deal-12345")


if __name__ == "__main__":
    unittest.main()
