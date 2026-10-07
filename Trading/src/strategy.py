"""
Module strategy.py : Moteur de génération des signaux de trading (Achat / Vente / Attente).
Intègre l'analyse multi-factorielle des 5 piliers institutionnels :
1. Macroéconomie & Taux réels (US 10Y, DXY, Taux réels, Fed)
2. Géopolitique & Sentiment de risque (VIX, Risk-On/Off, Safe Haven)
3. Flux Institutionnels & Physique (Achats PBOC, ETF GLD, Saisonnalité)
4. Price Action & Smart Money Concepts (Chandeliers clés, Chiffres ronds, FVG, Divergences RSI)
5. Microstructure & Timing de Session (Asie, Londres, Overlap NY, Fixings LBMA, Rollover)
"""

from dataclasses import dataclass
from enum import Enum
import logging
from typing import Any, Dict, Literal, Optional
import pandas as pd

from src.config import TradingConfig
from src.gold_intelligence import GoldIntelligenceEngine, GoldIntelligenceReport


class SignalType(str, Enum):
    """Types d'actions signalées par la stratégie."""
    BUY = "BUY"
    SELL = "SELL"
    WAIT = "WAIT"


@dataclass
class TradeSignal:
    """Structure représentant un signal d'arbitrage généré par la stratégie."""
    action: SignalType
    entry_price: float
    stop_loss: Optional[float]
    take_profit: Optional[float]
    atr_value: float
    reason: str
    timestamp: pd.Timestamp
    intelligence: Optional[Dict[str, Any]] = None


class TrendMomentumATRStrategy:
    """
    Stratégie réactive enrichie des 5 piliers d'intelligence institutionnelle :
    - Mode ACTIF (Scalping régulier assisté par SMC et Macro)
    - Mode CONSERVATEUR (Confluence stricte multi-piliers > 60% de probabilité)
    - Mode MANUEL 1-CLICK (Exécution immédiate calibrée ATR)
    """

    def __init__(
        self,
        config: TradingConfig,
        mode: Literal["active", "conservative"] = "active",
        intelligence_engine: Optional[GoldIntelligenceEngine] = None,
        logger: Optional[logging.Logger] = None,
    ):
        self.config = config
        self.mode: Literal["active", "conservative"] = mode
        self.logger = logger or logging.getLogger("TradingBot.Strategy")
        self.intelligence = intelligence_engine or GoldIntelligenceEngine(logger=self.logger)

    def set_mode(self, new_mode: Literal["active", "conservative"]) -> None:
        """Modifie le niveau d'agressivité de la stratégie."""
        self.mode = new_mode
        self.logger.info("Mode de stratégie changé en : %s", new_mode)

    def create_immediate_signal(
        self,
        direction: Literal["BUY", "SELL"],
        current_price: float,
        current_atr: float,
    ) -> TradeSignal:
        """
        Génère un signal manuel instantané avec calcul automatique et strict
        du Stop Loss et Take Profit basé sur l'ATR actuel et le plancher GSL Capital.com.
        """
        atr = max(current_atr, 3.0)
        min_gsl_dist = round(current_price * 0.0035, 2)  # Plancher contractuel Capital.com
        sl_distance = max(self.config.atr_sl_multiplier * atr, min_gsl_dist)
        tp_distance = max(self.config.atr_tp_multiplier * atr, sl_distance * 1.5)

        if direction == "BUY":
            sl_price = round(current_price - sl_distance, 2)
            tp_price = round(current_price + tp_distance, 2)
            action = SignalType.BUY
        else:
            sl_price = round(current_price + sl_distance, 2)
            tp_price = round(current_price - tp_distance, 2)
            action = SignalType.SELL

        return TradeSignal(
            action=action,
            entry_price=current_price,
            stop_loss=sl_price,
            take_profit=tp_price,
            atr_value=atr,
            reason=f"Ordre Manuel 1-Click ({direction}) avec Stop Garanti ({sl_distance:.2f}$ | ATR={atr:.2f}$)",
            timestamp=pd.Timestamp.now(),
        )

    def generate_signal(self, df: pd.DataFrame, current_spread: float = 0.50) -> TradeSignal:
        """
        Analyse les séries temporelles et synthétise les 5 piliers d'intelligence pour
        déterminer si un ordre doit être ouvert ou pourquoi le bot reste en attente.
        """
        min_required_rows = 30
        if len(df) < min_required_rows:
            return TradeSignal(
                action=SignalType.WAIT,
                entry_price=0.0,
                stop_loss=None,
                take_profit=None,
                atr_value=0.0,
                reason=f"Historique insuffisant ({len(df)} bougies, {min_required_rows} requises)",
                timestamp=pd.Timestamp.now(),
            )

        closed_candle = df.iloc[-2]
        prev_closed_candle = df.iloc[-3]

        timestamp = closed_candle["timestamp"]
        close = float(closed_candle["close"])
        open_price = float(closed_candle["open"])
        ema_fast = float(closed_candle.get("ema_fast", close))
        ema_slow = float(closed_candle.get("ema_slow", close))
        rsi = float(closed_candle.get("rsi", 50.0))
        atr = float(closed_candle.get("atr", 5.0))

        prev_rsi = float(prev_closed_candle.get("rsi", 50.0))
        prev_close = float(prev_closed_candle.get("close", close))

        # 1. Génération du Rapport d'Intelligence des 5 Piliers
        intel_report: GoldIntelligenceReport = self.intelligence.generate_intelligence_report(
            current_spot=close,
            df_indicators=df,
            current_spread=current_spread,
        )

        intel_dict = {
            "bias": intel_report.composite_bias,
            "confidence": intel_report.confidence_percent,
            "bullish_prob": intel_report.bullish_probability,
            "bearish_prob": intel_report.bearish_probability,
            "pattern": intel_report.smc_data.get("candlestick_pattern"),
            "target_1": intel_report.target_1,
            "target_2": intel_report.target_2,
            "invalidation": intel_report.invalidation_level,
            "nearest_round": intel_report.nearest_round_level,
            "decision_summary": intel_report.decision_summary,
        }

        # 2. Protection Microstructure : Rollover
        if intel_report.session_data.get("is_rollover_blackout"):
            return TradeSignal(
                action=SignalType.WAIT,
                entry_price=close,
                stop_loss=None,
                take_profit=None,
                atr_value=atr,
                reason="Attente de sécurité : Fenêtre de rollover interbancaire (23h-00h Paris)",
                timestamp=timestamp,
                intelligence=intel_dict,
            )

        # Garde-fou volatilité et Stop Loss Garanti
        min_gsl_dist = round(close * 0.0035, 2)
        sl_distance = max(self.config.atr_sl_multiplier * atr, min_gsl_dist)
        tp_distance = max(self.config.atr_tp_multiplier * atr, sl_distance * 1.5)

        pattern = intel_report.smc_data.get("candlestick_pattern", "")
        smc_dir = intel_report.smc_data.get("candlestick_direction", "NEUTRAL")

        # =====================================================================
        # 1. MODE ACTIF (Intraday / Scalping dynamique assisté par les 5 Piliers)
        # =====================================================================
        if self.mode == "active":
            is_bullish_bias = (ema_fast >= ema_slow) or (close >= ema_fast) or (smc_dir == "BULLISH")
            # Entrée active BUY si biais haussier, pas de surachat critique, et pas de veto baissier macro
            if is_bullish_bias and (38.0 <= rsi <= 72.0) and (close >= open_price or rsi > prev_rsi or smc_dir == "BULLISH") and intel_report.bearish_probability < 75:
                sl_price = round(close - sl_distance, 2)
                tp_price = round(close + tp_distance, 2)
                return TradeSignal(
                    action=SignalType.BUY,
                    entry_price=close,
                    stop_loss=sl_price,
                    take_profit=tp_price,
                    atr_value=atr,
                    reason=(
                        f"ACHAT Actif ({intel_report.bullish_probability}% proba) : "
                        f"Flux haussier, {pattern}, RSI {rsi:.1f}, Cible {intel_report.target_1}$"
                    ),
                    timestamp=timestamp,
                    intelligence=intel_dict,
                )

            is_bearish_bias = (ema_fast <= ema_slow) or (close <= ema_fast) or (smc_dir == "BEARISH")
            # Entrée active SELL si biais baissier, pas de survente critique, et pas de veto haussier macro
            if is_bearish_bias and (28.0 <= rsi <= 62.0) and (close <= open_price or rsi < prev_rsi or smc_dir == "BEARISH") and intel_report.bullish_probability < 75:
                sl_price = round(close + sl_distance, 2)
                tp_price = round(close - tp_distance, 2)
                return TradeSignal(
                    action=SignalType.SELL,
                    entry_price=close,
                    stop_loss=sl_price,
                    take_profit=tp_price,
                    atr_value=atr,
                    reason=(
                        f"VENTE Active ({intel_report.bearish_probability}% proba) : "
                        f"Flux baissier, {pattern}, RSI {rsi:.1f}, Cible {intel_report.target_1}$"
                    ),
                    timestamp=timestamp,
                    intelligence=intel_dict,
                )

        # =====================================================================
        # 2. MODE CONSERVATEUR (Filtre de Confluence Stricte > 60% Probabilité)
        # =====================================================================
        else:
            is_bullish_trend = (ema_fast > ema_slow) and (close > ema_slow)
            if is_bullish_trend and intel_report.bullish_probability >= 60 and rsi < self.config.rsi_overbought:
                sl_price = round(close - sl_distance, 2)
                tp_price = round(close + tp_distance, 2)
                return TradeSignal(
                    action=SignalType.BUY,
                    entry_price=close,
                    stop_loss=sl_price,
                    take_profit=tp_price,
                    atr_value=atr,
                    reason=(
                        f"ACHAT Conservateur Fort ({intel_report.bullish_probability}% proba) : "
                        f"Alignement 5 Piliers, {pattern}, RSI={rsi:.1f}"
                    ),
                    timestamp=timestamp,
                    intelligence=intel_dict,
                )

            is_bearish_trend = (ema_fast < ema_slow) and (close < ema_slow)
            if is_bearish_trend and intel_report.bearish_probability >= 60 and rsi > self.config.rsi_oversold:
                sl_price = round(close + sl_distance, 2)
                tp_price = round(close - tp_distance, 2)
                return TradeSignal(
                    action=SignalType.SELL,
                    entry_price=close,
                    stop_loss=sl_price,
                    take_profit=tp_price,
                    atr_value=atr,
                    reason=(
                        f"VENTE Conservatrice Forte ({intel_report.bearish_probability}% proba) : "
                        f"Alignement 5 Piliers, {pattern}, RSI={rsi:.1f}"
                    ),
                    timestamp=timestamp,
                    intelligence=intel_dict,
                )

        # =====================================================================
        # 3. ÉTAT D'ATTENTE AVEC EXPLICATION EXHAUSTIVE
        # =====================================================================
        return TradeSignal(
            action=SignalType.WAIT,
            entry_price=close,
            stop_loss=None,
            take_profit=None,
            atr_value=atr,
            reason=f"Attente : {intel_report.decision_summary}",
            timestamp=timestamp,
            intelligence=intel_dict,
        )
