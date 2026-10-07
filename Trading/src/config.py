"""
Module config.py : Configuration personnalisée et optimisée pour votre compte Capital.com.
Pré-intégré avec vos clés et paramètres dédiés au Gold XAU/USD.
"""

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Literal
from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parent.parent
load_dotenv(dotenv_path=ROOT_DIR / ".env")


@dataclass(frozen=True)
class TradingConfig:
    """Structure de configuration optimisée pour le trading de l'Or."""

    # Paramètres API
    api_key: str
    identifier: str
    password: str
    environment: Literal["demo", "live"]
    base_url: str

    # Paramètres Marché
    epic: str
    timeframe: str

    # Indicateurs Techniques
    ema_fast_period: int
    ema_slow_period: int
    rsi_period: int
    rsi_oversold: float
    rsi_overbought: float
    atr_period: int
    atr_sl_multiplier: float
    atr_tp_multiplier: float

    # Risque & Sécurité
    risk_per_trade_percent: float
    max_daily_drawdown_percent: float
    max_allowed_spread: float
    max_open_positions: int
    min_position_size: float

    # Boucle & Réseau
    poll_interval_seconds: int
    max_retries: int
    retry_backoff_factor: float

    @classmethod
    def from_env(cls) -> "TradingConfig":
        """
        Instancie la configuration avec les identifiants pré-configurés
        et charge l'email de connexion depuis le fichier .env.
        """
        api_key = os.getenv("CAPITAL_API_KEY", "FntgFAJwT5ncWH08").strip()
        password = os.getenv("CAPITAL_PASSWORD", "Capital_password1").strip()
        identifier = os.getenv("CAPITAL_IDENTIFIER", "").strip()
        env_mode = os.getenv("CAPITAL_ENV", "demo").strip().lower()

        if not identifier or identifier in ("votre_email@exemple.com", "CAPITAL_API_KEY"):
            raise ValueError(
                "Adresse email manquante : Sur Capital.com, l'identifiant (identifier) est "
                "l'adresse email de connexion à votre compte Capital.com.\n"
                "Veuillez inscrire votre email dans le fichier .env (CAPITAL_IDENTIFIER=votre_email@domaine.com)."
            )

        base_url = (
            "https://api-capital.backend-capital.com/api/v1/"
            if env_mode == "live"
            else "https://demo-api-capital.backend-capital.com/api/v1/"
        )

        return cls(
            api_key=api_key,
            identifier=identifier,
            password=password,
            environment="live" if env_mode == "live" else "demo",
            base_url=base_url,
            epic=os.getenv("MARKET_EPIC", "GOLD").strip().upper(),
            timeframe=os.getenv("TIMEFRAME", "MINUTE_15").strip().upper(),
            ema_fast_period=int(os.getenv("EMA_FAST_PERIOD", "50")),
            ema_slow_period=int(os.getenv("EMA_SLOW_PERIOD", "200")),
            rsi_period=int(os.getenv("RSI_PERIOD", "14")),
            rsi_oversold=float(os.getenv("RSI_OVERSOLD", "35.0")),
            rsi_overbought=float(os.getenv("RSI_OVERBOUGHT", "65.0")),
            atr_period=int(os.getenv("ATR_PERIOD", "14")),
            atr_sl_multiplier=float(os.getenv("ATR_SL_MULTIPLIER", "1.5")),
            atr_tp_multiplier=float(os.getenv("ATR_TP_MULTIPLIER", "3.0")),
            risk_per_trade_percent=float(os.getenv("RISK_PER_TRADE_PERCENT", "0.01")),
            max_daily_drawdown_percent=float(os.getenv("MAX_DAILY_DRAWDOWN_PERCENT", "0.03")),
            max_allowed_spread=float(os.getenv("MAX_ALLOWED_SPREAD", "0.40")),
            max_open_positions=int(os.getenv("MAX_OPEN_POSITIONS", "1")),
            min_position_size=float(os.getenv("MIN_POSITION_SIZE", "0.1")),
            poll_interval_seconds=int(os.getenv("POLL_INTERVAL_SECONDS", "15")),
            max_retries=int(os.getenv("MAX_RETRIES", "4")),
            retry_backoff_factor=float(os.getenv("RETRY_BACKOFF_FACTOR", "2.0")),
        )
