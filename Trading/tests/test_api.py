"""
Tests d'intégration de l'API web Flask et des endpoints de contrôle.
"""

import json
import unittest
from unittest.mock import MagicMock, patch

from app import app, bot_service


class TestTradingWebApp(unittest.TestCase):

    def setUp(self):
        self.client = app.test_client()
        self.client.testing = True

    def test_index_page(self):
        """Vérifie que la page principale se charge avec le code 200."""
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"TRADING", response.data)

    def test_api_status_endpoint(self):
        """Vérifie la structure du statut global retourné par /api/status."""
        response = self.client.get("/api/status")
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)

        self.assertIn("is_auto_trading", data)
        self.assertIn("strategy_mode", data)
        self.assertIn("snapshot", data)
        self.assertIn("financials", data)
        self.assertIn("positions", data)
        self.assertIn("logs", data)

    def test_api_intelligence_endpoint(self):
        """Vérifie l'endpoint /api/intelligence retournant les prédictions et l'explicabilité."""
        response = self.client.get("/api/intelligence")
        self.assertEqual(response.status_code, 200)

    def test_toggle_auto_endpoint(self):
        """Vérifie le basculement ON/OFF du trading autonome."""
        initial_state = bot_service.is_auto_trading
        response = self.client.post("/api/toggle-auto")
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertTrue(data.get("success"))
        self.assertEqual(data.get("is_auto_trading"), not initial_state)

    def test_set_mode_endpoint(self):
        """Vérifie le changement de mode actif / conservateur."""
        response = self.client.post(
            "/api/set-mode",
            data=json.dumps({"mode": "conservative"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(data.get("strategy_mode"), "conservative")
        self.assertEqual(bot_service.strategy_mode, "conservative")

    def test_set_timeframe_endpoint(self):
        """Vérifie la mise à jour de la timeframe."""
        response = self.client.post(
            "/api/set-timeframe",
            data=json.dumps({"timeframe": "MINUTE_5"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(data.get("timeframe"), "MINUTE_5")
        self.assertEqual(bot_service.selected_timeframe, "MINUTE_5")

    def test_manual_trade_invalid_direction(self):
        """Vérifie qu'une direction erronée renvoie un code HTTP 400."""
        response = self.client.post(
            "/api/trade",
            data=json.dumps({"direction": "INVALID"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)

    @patch.object(bot_service, "execute_manual_order")
    def test_manual_trade_valid_call(self, mock_manual_order):
        """Vérifie l'appel au service lors d'un ordre 1-Click valide."""
        mock_manual_order.return_value = {"success": True, "deal_id": "test-deal-999", "size": 0.05}
        response = self.client.post(
            "/api/trade",
            data=json.dumps({"direction": "BUY"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertTrue(data.get("success"))
        self.assertEqual(data.get("deal_id"), "test-deal-999")

    @patch.object(bot_service, "close_all_positions")
    def test_close_all_endpoint(self, mock_close_all):
        """Vérifie l'endpoint de fermeture d'urgence de toutes les positions."""
        mock_close_all.return_value = 2
        response = self.client.post("/api/close-all")
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertTrue(data.get("success"))
        self.assertEqual(data.get("closed_count"), 2)

    def test_set_risk_endpoint(self):
        """Vérifie le réglage du levier et du capital risqué via l'API."""
        # 1. Envoi sans payload -> HTTP 400
        res_empty = self.client.post(
            "/api/set-risk",
            data=json.dumps({}),
            content_type="application/json",
        )
        self.assertEqual(res_empty.status_code, 400)

        # 2. Envoi valide avec levier 10:1 et 2.5% de capital
        response = self.client.post(
            "/api/set-risk",
            data=json.dumps({"leverage": 10, "capital_percent": 2.5}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertTrue(data.get("success"))
        settings = data.get("risk_settings", {})
        self.assertEqual(settings.get("leverage"), 10)
        self.assertEqual(settings.get("capital_risk_percent"), 2.5)


if __name__ == "__main__":
    unittest.main()
