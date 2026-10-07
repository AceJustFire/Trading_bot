"""
Module bot_service.py : Service d'orchestration asynchrone et thread-safe pour l'application interactive.
Permet le contrôle du bot en temps réel (Start/Stop, Mode Actif/Conservateur, 1-Click Orders, Clôtures).
"""

from collections import deque
from datetime import datetime
import logging
import threading
import time
from typing import Any, Dict, List, Optional
import pandas as pd

from src.auth import AuthSessionManager, CapitalAuthError
from src.config import TradingConfig
from src.execution import ExecutionManager, PositionDetails
from src.logger import setup_logger
from src.market_data import MarketDataManager, MarketSnapshot
from src.risk_manager import AccountFinancials, RiskManager
from src.strategy import SignalType, TradeSignal, TrendMomentumATRStrategy


class BotService:
    """Service singleton centralisé pour piloter le bot depuis l'interface interactive."""

    def __init__(self):
        self.logger = setup_logger(name="BotService", log_dir="logs", log_file="bot.log")
        self.config = TradingConfig.from_env()

        self.auth = AuthSessionManager(self.config, logger=self.logger)
        self.market_data = MarketDataManager(self.config, self.auth, logger=self.logger)
        self.strategy = TrendMomentumATRStrategy(self.config, mode="active", logger=self.logger)
        self.risk_manager = RiskManager(self.config, self.auth, logger=self.logger)
        self.execution = ExecutionManager(self.config, self.auth, logger=self.logger)

        # États internes thread-safe
        self._lock = threading.Lock()
        self.is_auto_trading: bool = True       # Bot autonome actif par défaut
        self.is_worker_alive: bool = False
        self.selected_timeframe: str = self.config.timeframe
        self.strategy_mode: str = "active"

        # Moteur d'Intelligence Institutionnelle & Prédictions
        self.intelligence_engine = self.strategy.intelligence
        self.latest_intelligence: Optional[Dict[str, Any]] = None

        # Caches de données temps réel
        self.latest_snapshot: Optional[MarketSnapshot] = None
        self.latest_financials: Optional[AccountFinancials] = None
        self.latest_signal: Optional[TradeSignal] = None
        self.latest_indicators: Dict[str, Any] = {}
        self.open_positions: List[PositionDetails] = []
        self.log_history: deque = deque(maxlen=60)
        self.last_candle_time: Optional[pd.Timestamp] = None
        self.last_error: Optional[str] = None

        self._thread: Optional[threading.Thread] = None

    def add_log(self, message: str, level: str = "INFO") -> None:
        """Ajoute un log dans le tampon pour affichage dans la console interactive."""
        now_str = datetime.now().strftime("%H:%M:%S")
        entry = {"time": now_str, "level": level, "msg": message}
        with self._lock:
            self.log_history.append(entry)
        if level == "ERROR":
            self.logger.error(message)
        else:
            self.logger.info(message)

    def initialize(self) -> bool:
        """Initialise la session Capital.com et démarre le worker de fond."""
        try:
            self.add_log("Connexion à l'API Capital.com (Mode Démo)...")
            self.auth.authenticate()
            self.latest_financials = self.risk_manager.fetch_account_financials()
            self.latest_snapshot = self.market_data.get_market_snapshot()
            self.add_log(f"Connecté avec succès. Solde: {self.latest_financials.equity:.2f} USD")
            return True
        except Exception as e:
            self.add_log(f"Erreur d'initialisation : {e}", level="ERROR")
            self.last_error = str(e)
            return False

    def start_background_loop(self) -> None:
        """Démarre le thread de surveillance et d'exécution automatique."""
        if self._thread and self._thread.is_alive():
            return
        self.is_worker_alive = True
        self._thread = threading.Thread(target=self._worker_loop, daemon=True)
        self._thread.start()
        self.add_log("Surveillance autonome démarrée.")

    def stop_background_loop(self) -> None:
        """Arrête le thread de fond proprement."""
        self.is_worker_alive = False
        if self._thread:
            self._thread.join(timeout=2.0)
        self.auth.logout()
        self.add_log("Surveillance autonome arrêtée.")

    def toggle_auto_trading(self) -> bool:
        """Active ou désactive le passage d'ordres automatiques."""
        with self._lock:
            self.is_auto_trading = not self.is_auto_trading
            state = "ACTIVÉ" if self.is_auto_trading else "EN PAUSE"
        self.add_log(f"Trading autonome : {state}")
        return self.is_auto_trading

    def set_strategy_mode(self, mode: str) -> None:
        """Bascule entre mode actif (scalping fréquent) et conservateur."""
        with self._lock:
            self.strategy_mode = "active" if mode == "active" else "conservative"
            self.strategy.set_mode(self.strategy_mode)  # type: ignore
        self.add_log(f"Mode de stratégie ajusté : {self.strategy_mode.upper()}")

    def set_timeframe(self, tf: str) -> None:
        """Modifie la timeframe d'analyse en direct."""
        valid_tfs = ["MINUTE", "MINUTE_5", "MINUTE_15", "MINUTE_30", "HOUR"]
        if tf in valid_tfs:
            with self._lock:
                self.selected_timeframe = tf
            self.add_log(f"Timeframe d'analyse changée : {tf}")

    def set_risk_parameters(
        self,
        leverage: Optional[int] = None,
        capital_percent: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Configure dynamiquement l'effet de levier et/ou le pourcentage de capital tradé."""
        with self._lock:
            if leverage is not None:
                self.risk_manager.set_leverage(int(leverage))
            if capital_percent is not None:
                self.risk_manager.set_capital_risk_percent(float(capital_percent))
            settings = self.risk_manager.get_risk_settings()

        msg = f"Paramètres de Risque : Levier {settings['leverage']}:1 | Risque Capital {settings['capital_risk_percent']}%"
        self.add_log(msg)
        return settings

    def execute_manual_order(self, direction: str) -> Dict[str, Any]:
        """
        Exécute immédiatement un ordre au marché (1-Click) :
        Calcule la taille optimale de lot via le Risk Manager (1% du capital)
        et applique le Stop Loss et Take Profit calculés par l'ATR.
        """
        with self._lock:
            snapshot = self.latest_snapshot
            atr = self.latest_indicators.get("atr", 3.0)
            open_count = len(self.open_positions)

        if not snapshot or not snapshot.is_tradeable:
            msg = "Marché actuellement non négociable."
            self.add_log(msg, level="ERROR")
            return {"success": False, "error": msg}

        ref_price = snapshot.ask if direction == "BUY" else snapshot.bid
        signal = self.strategy.create_immediate_signal(
            direction=direction,  # type: ignore
            current_price=ref_price,
            current_atr=atr,
        )

        risk_check = self.risk_manager.validate_and_size_order(
            signal=signal,
            snapshot=snapshot,
            current_open_positions_count=open_count,
        )

        if not risk_check.is_approved:
            self.add_log(f"Ordre manuel refusé par le risque : {risk_check.reason}", level="ERROR")
            return {"success": False, "error": risk_check.reason}

        deal_id = self.execution.execute_market_order(signal, risk_check.position_size)
        if deal_id:
            msg = f"Ordre {direction} exécuté ({risk_check.position_size} lots) | SL={signal.stop_loss}$ | TP={signal.take_profit}$"
            self.add_log(msg, level="SUCCESS")
            time.sleep(0.4)
            self.refresh_positions()
            return {"success": True, "deal_id": deal_id, "size": risk_check.position_size}

        msg = "Échec d'envoi de l'ordre auprès de Capital.com."
        self.add_log(msg, level="ERROR")
        return {"success": False, "error": msg}

    def close_single_position(self, deal_id: str) -> bool:
        """Ferme une position spécifique immédiatement."""
        ok = self.execution.close_position(deal_id)
        if ok:
            self.add_log(f"Position {deal_id} fermée avec succès.")
            time.sleep(0.4)
            self.refresh_positions()
        else:
            self.add_log(f"Échec de clôture de la position {deal_id}.", level="ERROR")
        return ok

    def close_all_positions(self) -> int:
        """Ferme toutes les positions ouvertes en 1 clic."""
        with self._lock:
            positions = list(self.open_positions)
        closed = 0
        for pos in positions:
            if self.execution.close_position(pos.deal_id):
                closed += 1
        self.add_log(f"{closed} position(s) fermée(s) en clôture d'urgence.")
        self.refresh_positions()
        return closed

    def refresh_positions(self) -> None:
        """Interroge Capital.com pour mettre à jour la liste des positions."""
        try:
            positions = self.execution.get_open_positions(self.config.epic)
            with self._lock:
                self.open_positions = positions
        except Exception as e:
            self.logger.debug("Erreur refresh positions : %s", e)

    def _worker_loop(self) -> None:
        """Boucle d'exécution continue de fond."""
        last_ping = time.time()

        while self.is_worker_alive:
            try:
                # Keep-alive toutes les 4 minutes
                if time.time() - last_ping > 240:
                    self.auth.ping()
                    last_ping = time.time()

                # 1. Snapshot du marché & Finances
                snapshot = self.market_data.get_market_snapshot()
                financials = self.risk_manager.fetch_account_financials()
                positions = self.execution.get_open_positions(self.config.epic)

                with self._lock:
                    self.latest_snapshot = snapshot
                    self.latest_financials = financials
                    self.open_positions = positions

                if not snapshot.is_tradeable:
                    time.sleep(5)
                    continue

                # 2. Récupération des cours
                df = self.market_data.fetch_historical_candles(
                    epic=self.config.epic,
                    resolution=self.selected_timeframe,
                    max_candles=350,
                )
                df_ind = self.market_data.compute_indicators(df)

                if len(df_ind) >= 3:
                    last_candle = df_ind.iloc[-2]
                    candle_time = last_candle["timestamp"]
                    close = float(last_candle["close"])
                    ema_fast = float(last_candle["ema_fast"])
                    ema_slow = float(last_candle["ema_slow"])
                    rsi = float(last_candle["rsi"])
                    atr = float(last_candle["atr"])

                    spread_val = snapshot.spread if snapshot else 0.50
                    intel_report = self.intelligence_engine.generate_intelligence_report(
                        current_spot=close,
                        df_indicators=df_ind,
                        current_spread=spread_val,
                    )
                    signal = self.strategy.generate_signal(df_ind, current_spread=spread_val)

                    with self._lock:
                        self.latest_signal = signal
                        self.latest_intelligence = {
                            "timestamp": intel_report.timestamp,
                            "composite_bias": intel_report.composite_bias,
                            "confidence_percent": intel_report.confidence_percent,
                            "bullish_probability": intel_report.bullish_probability,
                            "bearish_probability": intel_report.bearish_probability,
                            "target_1": intel_report.target_1,
                            "target_2": intel_report.target_2,
                            "invalidation_level": intel_report.invalidation_level,
                            "nearest_round_level": intel_report.nearest_round_level,
                            "decision_summary": intel_report.decision_summary,
                            "positive_catalysts": intel_report.positive_catalysts,
                            "negative_catalysts": intel_report.negative_catalysts,
                            "macro_score": intel_report.macro_score,
                            "geopolitics_score": intel_report.geopolitics_score,
                            "institutional_score": intel_report.institutional_score,
                            "price_action_score": intel_report.price_action_score,
                            "microstructure_score": intel_report.microstructure_score,
                            "macro_data": intel_report.macro_data,
                            "smc_data": intel_report.smc_data,
                            "session_data": intel_report.session_data,
                        }
                        self.latest_indicators = {
                            "close": close,
                            "ema_fast": ema_fast,
                            "ema_slow": ema_slow,
                            "rsi": rsi,
                            "atr": atr,
                            "candle_time": str(candle_time),
                        }

                    # 3. Exécution automatique si activée
                    if self.is_auto_trading and signal.action in (SignalType.BUY, SignalType.SELL):
                        # Gérer signal inverse sur positions existantes
                        reversed_closed = False
                        for pos in positions:
                            if (pos.direction == "BUY" and signal.action == SignalType.SELL) or \
                               (pos.direction == "SELL" and signal.action == SignalType.BUY):
                                self.add_log(f"Signal inverse ({signal.action.value}) -> Clôture position {pos.deal_id}")
                                if self.execution.close_position(pos.deal_id):
                                    reversed_closed = True

                        if reversed_closed:
                            time.sleep(0.4)
                            self.refresh_positions()
                            positions = list(self.open_positions)

                        # Ouverture nouvelle position si place disponible
                        if len(self.open_positions) < self.config.max_open_positions and candle_time != self.last_candle_time:
                            risk_res = self.risk_manager.validate_and_size_order(
                                signal=signal,
                                snapshot=snapshot,
                                current_open_positions_count=len(self.open_positions),
                            )
                            if risk_res.is_approved:
                                self.add_log(f">> AUTO TRADE : {signal.action.value} {risk_res.position_size} lots ({signal.reason})")
                                deal_id = self.execution.execute_market_order(signal, risk_res.position_size)
                                self.last_candle_time = candle_time
                                if deal_id:
                                    time.sleep(0.5)
                                    self.refresh_positions()
                            else:
                                self.add_log(f"Signal ignoré : {risk_res.reason}", level="WARNING")
                                self.last_candle_time = candle_time

            except CapitalAuthError as auth_err:
                self.add_log(f"Session expirée, reconnexion : {auth_err}", level="WARNING")
                try:
                    self.auth.authenticate()
                except Exception:
                    pass
            except Exception as e:
                self.logger.exception("Erreur cycle worker : %s", e)
                with self._lock:
                    self.last_error = str(e)

            time.sleep(2.0)

    def get_full_state(self) -> Dict[str, Any]:
        """Retourne un dictionnaire complet de l'état du bot pour l'API web."""
        with self._lock:
            snapshot_dict = {
                "epic": self.latest_snapshot.epic if self.latest_snapshot else "GOLD",
                "market_status": self.latest_snapshot.market_status if self.latest_snapshot else "TRADEABLE",
                "bid": self.latest_snapshot.bid if self.latest_snapshot else 4154.30,
                "ask": self.latest_snapshot.ask if self.latest_snapshot else 4154.80,
                "spread": self.latest_snapshot.spread if self.latest_snapshot else 0.500,
                "is_tradeable": self.latest_snapshot.is_tradeable if self.latest_snapshot else True,
            }

            financials_dict = {
                "account_id": self.latest_financials.account_id if self.latest_financials else "330847176266952990",
                "balance": self.latest_financials.balance if self.latest_financials else 1000.0,
                "equity": self.latest_financials.equity if self.latest_financials else 1000.0,
                "available": self.latest_financials.available if self.latest_financials else 1000.0,
                "currency": self.latest_financials.currency if self.latest_financials else "USD",
            }

            signal_dict = None
            if self.latest_signal:
                signal_dict = {
                    "action": self.latest_signal.action.value,
                    "entry_price": self.latest_signal.entry_price,
                    "stop_loss": self.latest_signal.stop_loss,
                    "take_profit": self.latest_signal.take_profit,
                    "atr": self.latest_signal.atr_value,
                    "reason": self.latest_signal.reason,
                }

            positions_list = [
                {
                    "deal_id": p.deal_id,
                    "direction": p.direction,
                    "size": p.size,
                    "open_level": p.open_level,
                    "stop_level": p.stop_level,
                    "profit_level": p.profit_level,
                    "upl": p.upl,
                    "created_date": p.created_date,
                }
                for p in self.open_positions
            ]

            return {
                "is_auto_trading": self.is_auto_trading,
                "strategy_mode": self.strategy_mode,
                "selected_timeframe": self.selected_timeframe,
                "snapshot": snapshot_dict,
                "financials": financials_dict,
                "indicators": self.latest_indicators,
                "signal": signal_dict,
                "intelligence": self.latest_intelligence,
                "risk_settings": self.risk_manager.get_risk_settings(),
                "positions": positions_list,
                "logs": list(self.log_history),
                "last_error": self.last_error,
            }
