"""
Module risk_manager.py : Moteur de contrôle et de gestion du risque pré-ordre.
Fonctionnalités :
- Calcul dynamique du dimensionnement de position selon le risque du capital (ex: 1% max).
- Validation stricte des niveaux obligatoires de Stop Loss et Take Profit.
- Coupe-circuit contre la perte journalière maximale (Daily Drawdown, ex: 3%).
- Filtre sur le spread maximal autorisé.
- Contrôle du nombre maximal de positions ouvertes simultanées.
"""

from dataclasses import dataclass
from datetime import date, datetime
import logging
import math
from typing import Optional, Tuple
import requests

from src.auth import AuthSessionManager
from src.config import TradingConfig
from src.market_data import MarketSnapshot
from src.strategy import SignalType, TradeSignal


@dataclass
class AccountFinancials:
    """Représentation de l'état financier du compte de trading."""
    account_id: str
    balance: float
    equity: float
    available: float
    currency: str


@dataclass
class RiskCheckResult:
    """Résultat de l'analyse de risque avant émission d'un ordre."""
    is_approved: bool
    position_size: float
    reason: str


class RiskManager:
    """Gestionnaire de risque quantitatif et contrôle des pertes."""

    def __init__(
        self,
        config: TradingConfig,
        auth_manager: AuthSessionManager,
        logger: Optional[logging.Logger] = None,
    ):
        self.config = config
        self.auth = auth_manager
        self.logger = logger or logging.getLogger("TradingBot.RiskManager")

        # Suivi du Daily Drawdown
        self.current_trading_day: date = datetime.utcnow().date()
        self.start_day_equity: Optional[float] = None
        self.daily_drawdown_limit_hit: bool = False

        # Paramètres configurables de levier (jusqu'à 20:1) et de % de capital
        self.leverage: int = 20  # Levier standard max réglementaire pour l'or
        self.capital_risk_percent: float = self.config.risk_per_trade_percent

    def set_leverage(self, leverage: int) -> int:
        """Configure l'effet de levier maximal utilisé (entre 1:1 et 20:1)."""
        clamped = max(1, min(20, int(leverage)))
        self.leverage = clamped
        self.logger.info("Effet de levier configuré à : %d:1", self.leverage)
        return self.leverage

    def set_capital_risk_percent(self, percent: float) -> float:
        """
        Configure le pourcentage de capital alloué/risqué par trade (entre 0.1% et 25%).
        Exemple : passer 1.5 pour 1.5% de capital.
        """
        val = float(percent)
        # Si valeur fournie sous forme décimale (ex: 0.02 au lieu de 2.0)
        if val <= 0.25:
            val = val * 100.0
        clamped = max(0.1, min(25.0, val))
        self.capital_risk_percent = round(clamped / 100.0, 4)
        self.logger.info("Risque en capital configuré à : %.2f%%", self.capital_risk_percent * 100.0)
        return round(self.capital_risk_percent * 100.0, 2)

    def get_risk_settings(self) -> dict:
        """Retourne les paramètres de risque actuels."""
        return {
            "leverage": self.leverage,
            "leverage_label": f"{self.leverage}:1",
            "capital_risk_percent": round(self.capital_risk_percent * 100.0, 2),
        }

    def fetch_account_financials(self) -> AccountFinancials:
        """
        Récupère le solde et l'équité actuelle du compte de trading.
        Endpoint : GET /api/v1/accounts
        """
        response = self.auth.request_with_reauth("GET", "accounts")
        if response.status_code != 200:
            raise RuntimeError(
                f"Échec de récupération des comptes: HTTP {response.status_code} - {response.text}"
            )

        data = response.json()
        accounts = data.get("accounts", [])
        if not accounts:
            raise ValueError("Aucun compte de trading trouvé sur le profil Capital.com.")

        # Trouver le compte actif ou prendre le premier compte disponible
        target_acc = None
        if self.auth.current_account_id:
            for acc in accounts:
                if acc.get("accountId") == self.auth.current_account_id:
                    target_acc = acc
                    break

        if not target_acc:
            target_acc = accounts[0]

        balance_obj = target_acc.get("balance", {})
        balance = float(balance_obj.get("balance", 0.0) or 0.0)
        profit = float(balance_obj.get("profit", 0.0) or 0.0)
        available = float(balance_obj.get("available", 0.0) or 0.0)
        equity = balance + profit
        currency = target_acc.get("currency", "USD")

        # Initialisation ou réinitialisation journalière de l'équité de référence
        today = datetime.utcnow().date()
        if self.start_day_equity is None or self.current_trading_day != today:
            self.current_trading_day = today
            self.start_day_equity = equity
            self.daily_drawdown_limit_hit = False
            self.logger.info(
                "Nouvelle journée de trading (%s). Équité de référence initialisée à: %.2f %s",
                today,
                self.start_day_equity,
                currency,
            )

        return AccountFinancials(
            account_id=str(target_acc.get("accountId", "")),
            balance=balance,
            equity=equity,
            available=available,
            currency=currency,
        )

    def evaluate_daily_drawdown(self, current_equity: float) -> bool:
        """
        Vérifie si la limite de perte maximale journalière (Daily Drawdown) est dépassée.
        Si la perte dépasse le seuil (ex: 3%), active le coupe-circuit pour la journée.
        """
        if self.start_day_equity is None or self.start_day_equity <= 0:
            self.start_day_equity = current_equity
            return True

        loss = self.start_day_equity - current_equity
        drawdown_pct = loss / self.start_day_equity

        if drawdown_pct >= self.config.max_daily_drawdown_percent:
            self.daily_drawdown_limit_hit = True
            self.logger.critical(
                "COUPE-CIRCUIT ACTIVÉ : Perte journalière de %.2f%% (%.2f USD), supérieure au max autorisé (%.2f%%). "
                "Trading suspendu pour la journée !",
                drawdown_pct * 100.0,
                loss,
                self.config.max_daily_drawdown_percent * 100.0,
            )
            return False

        return True

    def validate_and_size_order(
        self,
        signal: TradeSignal,
        snapshot: MarketSnapshot,
        current_open_positions_count: int,
    ) -> RiskCheckResult:
        """
        Effectue tous les contrôles de sécurité pré-ordre :
        1. Vérification du statut du marché (ouvert / tradeable).
        2. Vérification du coupe-circuit de perte journalière (Daily Drawdown).
        3. Vérification du nombre maximal de positions ouvertes autorisées.
        4. Vérification du filtre de spread.
        5. Vérification de la présence et cohérence du Stop Loss et Take Profit.
        6. Calcul mathématique de la taille de position basée sur le risque en capital (1%).
        """
        if signal.action == SignalType.WAIT:
            return RiskCheckResult(is_approved=False, position_size=0.0, reason="Signal d'attente (WAIT)")

        # 1. Vérification de l'ouverture du marché
        if not snapshot.is_tradeable:
            return RiskCheckResult(
                is_approved=False,
                position_size=0.0,
                reason=f"Marché fermé ou non négociable (Statut: {snapshot.market_status})",
            )

        # 2. Récupération des finances et test du Daily Drawdown
        try:
            financials = self.fetch_account_financials()
        except Exception as e:
            return RiskCheckResult(
                is_approved=False,
                position_size=0.0,
                reason=f"Erreur de lecture du solde compte: {e}",
            )

        if self.daily_drawdown_limit_hit or not self.evaluate_daily_drawdown(financials.equity):
            return RiskCheckResult(
                is_approved=False,
                position_size=0.0,
                reason="Coupe-circuit de perte journalière déclenché. Aucun nouvel ordre autorisé.",
            )

        # 3. Limite de positions ouvertes
        if current_open_positions_count >= self.config.max_open_positions:
            return RiskCheckResult(
                is_approved=False,
                position_size=0.0,
                reason=(
                    f"Plafond de positions atteint ({current_open_positions_count}/"
                    f"{self.config.max_open_positions})"
                ),
            )

        # 4. Filtre de spread
        if snapshot.spread > self.config.max_allowed_spread:
            return RiskCheckResult(
                is_approved=False,
                position_size=0.0,
                reason=(
                    f"Spread trop élevé ({snapshot.spread:.3f} > "
                    f"max {self.config.max_allowed_spread:.3f})"
                ),
            )

        # 5. Validation impérative du Stop Loss et Take Profit
        if signal.stop_loss is None or signal.take_profit is None:
            return RiskCheckResult(
                is_approved=False,
                position_size=0.0,
                reason="Rejet : Stop Loss et Take Profit obligatoires à l'ouverture de position.",
            )

        if signal.action == SignalType.BUY and signal.stop_loss >= snapshot.ask:
            return RiskCheckResult(
                is_approved=False,
                position_size=0.0,
                reason=f"Incohérence SL ACHAT : SL ({signal.stop_loss}) >= Prix Ask ({snapshot.ask})",
            )

        if signal.action == SignalType.SELL and signal.stop_loss <= snapshot.bid:
            return RiskCheckResult(
                is_approved=False,
                position_size=0.0,
                reason=f"Incohérence SL VENTE : SL ({signal.stop_loss}) <= Prix Bid ({snapshot.bid})",
            )

        # 6. Calcul de la taille de position (en contrats / lots)
        # Montant risqué = Équité * % de risque sélectionné (ex: 1 000 $ * 0.02 = 20 $)
        capital_at_risk = financials.equity * self.capital_risk_percent

        reference_price = snapshot.ask if signal.action == SignalType.BUY else snapshot.bid
        sl_distance = abs(reference_price - signal.stop_loss)

        if sl_distance <= 0:
            return RiskCheckResult(
                is_approved=False,
                position_size=0.0,
                reason="Distance de Stop Loss invalide (distance nulle).",
            )

        # Sur le CFD Or de Capital.com : 1 contrat d'or représente 1 once troy.
        # Une variation de 1.00 USD sur 1 contrat = 1.00 USD de PnL.
        raw_size = capital_at_risk / sl_distance

        # Contrôle du levier choisi (1:1 à 20:1) et de la marge disponible :
        # Marge requise pour 1 contrat = reference_price / leverage
        # Capacité notionnelle max = financials.available * leverage
        if reference_price > 0:
            max_leverage_notional = financials.available * self.leverage
            max_allowed_by_leverage = max_leverage_notional / reference_price
            if raw_size > max_allowed_by_leverage:
                self.logger.warning(
                    "Taille brute (%.2f lots) limitée par le levier %d:1 et la marge dispo (Max: %.2f lots)",
                    raw_size,
                    self.leverage,
                    max_allowed_by_leverage,
                )
                raw_size = max_allowed_by_leverage

        # Ajustement par pas d'incrément (ex: 0.01) et taille minimum du courtier
        step = max(snapshot.size_increment, 0.01)
        rounded_size = math.floor(raw_size / step) * step
        rounded_size = round(rounded_size, 2)

        min_size = max(snapshot.min_deal_size, self.config.min_position_size)
        if rounded_size < min_size:
            # Si la taille calculée est inférieure au minimum autorisé par le broker,
            # on vérifie si le risque avec la taille minimale reste acceptable (< 1.5x le risque cible)
            potential_risk_with_min = min_size * sl_distance
            if potential_risk_with_min <= capital_at_risk * 1.5:
                rounded_size = min_size
                self.logger.info(
                    "Taille ajustée au minimum broker (%s) avec risque toléré de %.2f USD (Cible: %.2f USD)",
                    min_size,
                    potential_risk_with_min,
                    capital_at_risk,
                )
            else:
                return RiskCheckResult(
                    is_approved=False,
                    position_size=0.0,
                    reason=(
                        f"Taille calculée ({raw_size:.3f}) inférieure au minimum broker ({min_size}) "
                        f"et risque excédentaire ({potential_risk_with_min:.2f} USD > max {capital_at_risk:.2f} USD)"
                    ),
                )

        self.logger.info(
            "Validation Risque OK : Équité=%.2f %s | Risque max=%.2f USD | Distance SL=%.2f USD | Taille=%s lots",
            financials.equity,
            financials.currency,
            capital_at_risk,
            sl_distance,
            rounded_size,
        )

        return RiskCheckResult(
            is_approved=True,
            position_size=rounded_size,
            reason="Contrôles de risque validés avec succès.",
        )
