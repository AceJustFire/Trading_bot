"""
Module execution.py : Gestion et transmission des ordres à l'API Capital.com.
Gère :
- L'émission d'ordres au marché avec Stop Loss et Take Profit (POST /api/v1/positions).
- La confirmation asynchrone des ordres (GET /api/v1/confirms/{dealReference}).
- La consultation des positions ouvertes (GET /api/v1/positions).
- La clôture de position (DELETE /api/v1/positions/{dealId}).
"""

from dataclasses import dataclass
import logging
import time
from typing import Any, Dict, List, Optional
import requests

from src.auth import AuthSessionManager
from src.config import TradingConfig
from src.strategy import SignalType, TradeSignal


@dataclass
class PositionDetails:
    """Détails d'une position ouverte sur Capital.com."""
    deal_id: str
    epic: str
    direction: str          # BUY ou SELL
    size: float
    open_level: float
    stop_level: Optional[float]
    profit_level: Optional[float]
    upl: float              # Unrealized Profit / Loss
    created_date: str


class ExecutionManager:
    """Gestionnaire d'exécution des ordres et du portefeuille actif."""

    def __init__(
        self,
        config: TradingConfig,
        auth_manager: AuthSessionManager,
        logger: Optional[logging.Logger] = None,
    ):
        self.config = config
        self.auth = auth_manager
        self.logger = logger or logging.getLogger("TradingBot.Execution")

    def get_open_positions(self, epic: Optional[str] = None) -> List[PositionDetails]:
        """
        Récupère la liste des positions ouvertes pour le compte.
        Endpoint : GET /api/v1/positions
        """
        target_epic = epic or self.config.epic
        response = self.auth.request_with_reauth("GET", "positions")

        if response.status_code != 200:
            self.logger.error("Échec de récupération des positions : HTTP %d - %s", response.status_code, response.text)
            return []

        data = response.json()
        positions_raw = data.get("positions", [])
        result: List[PositionDetails] = []

        for p in positions_raw:
            pos_info = p.get("position", {})
            market_info = p.get("market", {})
            pos_epic = market_info.get("epic") or pos_info.get("epic", "")

            # Filtrer par epic si demandé
            if target_epic and pos_epic.upper() != target_epic.upper():
                continue

            deal_id = str(pos_info.get("dealId", ""))
            direction = str(pos_info.get("direction", "")).upper()
            size = float(pos_info.get("size", 0.0) or 0.0)
            open_level = float(pos_info.get("level", 0.0) or 0.0)
            stop_level = float(pos_info.get("stopLevel")) if pos_info.get("stopLevel") is not None else None
            profit_level = float(pos_info.get("profitLevel")) if pos_info.get("profitLevel") is not None else None
            upl = float(pos_info.get("upl", 0.0) or 0.0)
            created_date = str(pos_info.get("createdDate", ""))

            result.append(
                PositionDetails(
                    deal_id=deal_id,
                    epic=pos_epic,
                    direction=direction,
                    size=size,
                    open_level=open_level,
                    stop_level=stop_level,
                    profit_level=profit_level,
                    upl=upl,
                    created_date=created_date,
                )
            )

        return result

    def execute_market_order(self, signal: TradeSignal, size: float) -> Optional[str]:
        """
        Crée un ordre au marché avec Stop Loss et Take Profit obligatoires.
        Endpoint : POST /api/v1/positions

        Format JSON :
        {
            "epic": "GOLD",
            "direction": "BUY" | "SELL",
            "size": 1.0,
            "guaranteedStop": false,
            "stopLevel": 2640.50,
            "profitLevel": 2680.00
        }
        """
        if signal.action not in (SignalType.BUY, SignalType.SELL):
            self.logger.warning("Tentative d'exécution d'un signal non exécutable: %s", signal.action)
            return None

        if signal.stop_loss is None or signal.take_profit is None:
            self.logger.error("Ordre rejeté : Stop Loss ou Take Profit manquant !")
            return None

        payload: Dict[str, Any] = {
            "epic": self.config.epic,
            "direction": signal.action.value,
            "size": size,
            "guaranteedStop": True,
            "stopLevel": round(signal.stop_loss, 2),
            "profitLevel": round(signal.take_profit, 2),
        }

        self.logger.info(
            "Envoi de l'ordre au marché : %s %s lots sur %s | SL: %s | TP: %s | Motif: %s",
            signal.action.value,
            size,
            self.config.epic,
            signal.stop_loss,
            signal.take_profit,
            signal.reason,
        )

        try:
            response = self.auth.request_with_reauth("POST", "positions", json=payload)

            if response.status_code == 200:
                resp_data = response.json()
                deal_reference = resp_data.get("dealReference")
                self.logger.info("Ordre transmis avec succès. DealReference: %s", deal_reference)

                # Validation asynchrone de confirmation
                deal_id = self._wait_for_order_confirmation(deal_reference)
                return deal_id or deal_reference

            self.logger.error(
                "Échec de création de position (HTTP %d): %s",
                response.status_code,
                response.text,
            )
            return None

        except Exception as e:
            self.logger.exception("Exception lors de l'exécution de l'ordre : %s", e)
            return None

    def _wait_for_order_confirmation(self, deal_reference: Optional[str], max_attempts: int = 5) -> Optional[str]:
        """
        Interroge l'endpoint GET /api/v1/confirms/{dealReference} pour confirmer l'exécution de l'ordre.
        """
        if not deal_reference:
            return None

        endpoint = f"confirms/{deal_reference}"
        for attempt in range(max_attempts):
            time.sleep(1.0)
            try:
                resp = self.auth.request_with_reauth("GET", endpoint)
                if resp.status_code == 200:
                    data = resp.json()
                    status = data.get("status", "")
                    deal_status = data.get("dealStatus", "")

                    # Identifier l'ID de deal réel dans affectedDeals ou dealId
                    affected = data.get("affectedDeals", [])
                    if affected and isinstance(affected, list) and "dealId" in affected[0]:
                        deal_id = affected[0]["dealId"]
                    else:
                        deal_id = data.get("dealId")

                    if status in ("OPEN", "ACCEPTED") or deal_status == "ACCEPTED":
                        self.logger.info(
                            "Position CONFIRMÉE par Capital.com (DealId: %s, Niveau: %s)",
                            deal_id,
                            data.get("level"),
                        )
                        return str(deal_id)
                    elif status == "REJECTED" or deal_status == "REJECTED":
                        reason = data.get("reason", "Inconnu")
                        self.logger.error("Ordre REJETÉ par Capital.com ! Motif: %s", reason)
                        return None

            except Exception as e:
                self.logger.debug("Tentative de confirmation %d/%d échouée: %s", attempt + 1, max_attempts, e)

        self.logger.warning("Délai de confirmation dépassé pour dealReference: %s", deal_reference)
        return None

    def close_position(self, deal_id: str) -> bool:
        """
        Ferme une position existante au prix du marché.
        Endpoint : DELETE /api/v1/positions/{dealId}
        """
        endpoint = f"positions/{deal_id}"
        self.logger.info("Clôture de la position %s...", deal_id)

        try:
            response = self.auth.request_with_reauth("DELETE", endpoint)

            if response.status_code == 200:
                data = response.json()
                close_ref = data.get("dealReference", "")
                self.logger.info("Position %s fermée avec succès (Ref: %s)", deal_id, close_ref)
                return True

            self.logger.error(
                "Impossible de fermer la position %s (HTTP %d): %s",
                deal_id,
                response.status_code,
                response.text,
            )
            return False

        except Exception as e:
            self.logger.exception("Exception lors de la fermeture de la position %s : %s", deal_id, e)
            return False
