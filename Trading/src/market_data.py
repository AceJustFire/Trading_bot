"""
Module market_data.py : Récupération des données de marché et calcul des indicateurs techniques.
Interroge les endpoints /api/v1/prices/{epic} et /api/v1/markets/{epic} de Capital.com.
Transforme les cours en DataFrame pandas et calcule EMA 50, EMA 200, RSI 14 et ATR 14.
"""

import logging
from dataclasses import dataclass
from typing import Optional, Tuple
import numpy as np
import pandas as pd

from src.auth import AuthSessionManager
from src.config import TradingConfig

# Tentative d'importation de pandas-ta avec fallback robuste en pur pandas
try:
    import pandas_ta as ta  # type: ignore
    HAS_PANDAS_TA = True
except ImportError:
    HAS_PANDAS_TA = False


@dataclass
class MarketSnapshot:
    """Instantané d'un actif (prix actuels, statut, spread et règles de négociation)."""
    epic: str
    market_status: str       # TRADEABLE, CLOSED_FOR_TRADING, OFFLINE, EDITS_ONLY
    bid: float
    ask: float
    spread: float
    min_deal_size: float
    size_increment: float
    is_tradeable: bool


class MarketDataManager:
    """Gestionnaire des données de flux et d'historique de marché."""

    def __init__(
        self,
        config: TradingConfig,
        auth_manager: AuthSessionManager,
        logger: Optional[logging.Logger] = None,
    ):
        self.config = config
        self.auth = auth_manager
        self.logger = logger or logging.getLogger("TradingBot.MarketData")

    def get_market_snapshot(self, epic: Optional[str] = None) -> MarketSnapshot:
        """
        Récupère l'état instantané du marché (bid, ask, spread, statut tradeable, taille min).
        Endpoint : GET /api/v1/markets/{epic}
        """
        target_epic = epic or self.config.epic
        endpoint = f"markets/{target_epic}"

        response = self.auth.request_with_reauth("GET", endpoint)
        if response.status_code != 200:
            raise RuntimeError(
                f"Impossible de récupérer les détails du marché {target_epic}: "
                f"HTTP {response.status_code} - {response.text}"
            )

        data = response.json()
        snapshot = data.get("snapshot", {})
        dealing_rules = data.get("dealingRules", {})

        market_status = snapshot.get("marketStatus", "OFFLINE")
        bid = float(snapshot.get("bid", 0.0) or 0.0)
        # Sur Capital.com, le prix Ask est étiqueté 'offer'
        ask = float(snapshot.get("offer", snapshot.get("ask", 0.0)) or 0.0)
        spread = round(ask - bid, 4) if (bid > 0 and ask > 0) else 0.0

        min_deal_size = float(dealing_rules.get("minDealSize", {}).get("value", self.config.min_position_size))
        size_increment = float(dealing_rules.get("minSizeIncrement", {}).get("value", 0.1))

        is_tradeable = (market_status == "TRADEABLE") and (bid > 0) and (ask > 0)

        return MarketSnapshot(
            epic=target_epic,
            market_status=market_status,
            bid=bid,
            ask=ask,
            spread=spread,
            min_deal_size=min_deal_size,
            size_increment=size_increment,
            is_tradeable=is_tradeable,
        )

    def fetch_historical_candles(
        self,
        epic: Optional[str] = None,
        resolution: Optional[str] = None,
        max_candles: int = 250,
    ) -> pd.DataFrame:
        """
        Télécharge les bougies historiques depuis l'API de Capital.com.
        Endpoint : GET /api/v1/prices/{epic}?resolution={res}&max={max}

        :return: DataFrame pandas avec index temporel et colonnes ['open', 'high', 'low', 'close', 'volume']
        """
        target_epic = epic or self.config.epic
        target_resolution = resolution or self.config.timeframe
        endpoint = f"prices/{target_epic}"
        params = {
            "resolution": target_resolution,
            "max": max_candles,
        }

        response = self.auth.request_with_reauth("GET", endpoint, params=params)
        if response.status_code != 200:
            raise RuntimeError(
                f"Échec de récupération des bougies {target_epic} ({target_resolution}): "
                f"HTTP {response.status_code} - {response.text}"
            )

        payload = response.json()
        raw_prices = payload.get("prices", [])
        if not raw_prices:
            raise ValueError(f"Aucune donnée de prix reçue pour {target_epic}")

        records = []
        for p in raw_prices:
            time_str = p.get("snapshotTime") or p.get("snapshotTimeUTC")
            # Extraire cours 'mid' (moyenne bid/ask) ou bid/ask si disponible
            open_mid = self._extract_mid_price(p.get("openPrice"))
            high_mid = self._extract_mid_price(p.get("highPrice"))
            low_mid = self._extract_mid_price(p.get("lowPrice"))
            close_mid = self._extract_mid_price(p.get("closePrice"))
            volume = float(p.get("lastTradedVolume", 0.0) or 0.0)

            records.append({
                "timestamp": pd.to_datetime(time_str),
                "open": open_mid,
                "high": high_mid,
                "low": low_mid,
                "close": close_mid,
                "volume": volume,
            })

        df = pd.DataFrame(records)
        df.sort_values(by="timestamp", inplace=True)
        df.reset_index(drop=True, inplace=True)

        return df

    @staticmethod
    def _extract_mid_price(price_node: Optional[dict]) -> float:
        """Extrait le prix moyen (mid-price) à partir du sous-objet bid/ask."""
        if not price_node:
            return 0.0
        bid = float(price_node.get("bid", 0.0) or 0.0)
        ask = float(price_node.get("ask", price_node.get("offer", 0.0)) or 0.0)
        if bid > 0 and ask > 0:
            return (bid + ask) / 2.0
        return bid or ask or 0.0

    def compute_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calcule les indicateurs techniques demandés :
        - EMA 50 (Rapide)
        - EMA 200 (Lente)
        - RSI 14 (Momentum)
        - ATR 14 (Volatilité)
        Utilise pandas-ta si disponible, sinon effectue le calcul vectoriel direct avec pandas/numpy.
        """
        if len(df) < max(self.config.ema_slow_period, 50):
            self.logger.warning(
                "Nombre insuffisant de bougies (%d) pour calculer l'EMA %d.",
                len(df),
                self.config.ema_slow_period,
            )

        df = df.copy()

        # 1. Calcul des Moyennes Mobiles Exponentielles (EMA 50 & EMA 200)
        df["ema_fast"] = df["close"].ewm(span=self.config.ema_fast_period, adjust=False).mean()
        df["ema_slow"] = df["close"].ewm(span=self.config.ema_slow_period, adjust=False).mean()

        # 2. Calcul du RSI 14 (Wilder's Smoothing)
        df["rsi"] = self._compute_rsi(df["close"], period=self.config.rsi_period)

        # 3. Calcul de l'ATR 14 (Average True Range)
        df["atr"] = self._compute_atr(df, period=self.config.atr_period)

        return df

    @staticmethod
    def _compute_rsi(series: pd.Series, period: int = 14) -> pd.Series:
        """Calcul robuste et vectorisé du RSI selon la méthode de Wilder avec gestion des cas limites."""
        delta = series.diff()
        gain = delta.clip(lower=0.0)
        loss = -delta.clip(upper=0.0)

        avg_gain = gain.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()
        avg_loss = loss.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()

        with np.errstate(divide="ignore", invalid="ignore"):
            rs = avg_gain / avg_loss
            rsi = 100.0 - (100.0 / (1.0 + rs))
            # Cas limites : zéro perte => 100, plat total => 50
            rsi = rsi.where(avg_loss != 0, 100.0)
            rsi = rsi.where((avg_gain != 0) | (avg_loss != 0), 50.0)

        return rsi.fillna(50.0)

    @staticmethod
    def _compute_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
        """Calcul vectorisé du True Range (TR) et de l'ATR selon Wilder avec remplissage garanti."""
        high = df["high"]
        low = df["low"]
        close_prev = df["close"].shift(1)

        tr1 = high - low
        tr2 = (high - close_prev).abs()
        tr3 = (low - close_prev).abs()

        true_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = true_range.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()
        return atr.bfill().fillna(3.0)
