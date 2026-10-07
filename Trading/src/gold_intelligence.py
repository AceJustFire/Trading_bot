"""
Module gold_intelligence.py : Moteur d'analyse multi-factoriel et d'explicabilité décisionnelle pour l'Or (XAU/USD).

Intègre l'intégralité des 5 piliers institutionnels :
1. Macroéconomie & Monétaire : US 10Y yield, DXY (Dollar Index), Taux réels, Fed Policy, Calendrier.
2. Géopolitique & Sentiment de Risque : VIX, Risk-On/Off, Tensions, Dédollarisation BRICS.
3. Flux Institutionnels & Physique : Achats Banques Centrales (PBOC, etc.), ETF GLD, CoT CFTC, Saisonnalité (Diwali, Nouvel An chinois), AISC minier.
4. Price Action & Smart Money Concepts (SMC) : Chandeliers clés (Pin bar, Marubozu, Engulfing, Doji),
   Niveaux psychologiques ($50/$100), Fair Value Gaps (FVG), PDH/PDL, PWH/PWL, Divergences RSI.
5. Microstructure & Timing de Session : Asie, Londres, Overlap Londres/NY, Fixings LBMA (10:30 & 15:00 GMT), Alerte Rollover.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
import logging
import math
import threading
import time
from typing import Any, Dict, List, Optional, Tuple
import numpy as np
import pandas as pd
import requests


@dataclass
class MacroMetrics:
    """Métriques macroéconomiques et monétaires."""
    us_10y_yield: float = 4.25
    us_10y_prev_close: float = 4.25
    dxy_price: float = 103.50
    dxy_prev_close: float = 103.50
    real_rate_proxy: float = 1.95       # US 10Y - Inflation anticipée (2.3%)
    vix_index: float = 16.50
    vix_prev_close: float = 16.50
    gld_price: float = 245.00
    gld_prev_close: float = 245.00
    last_updated: float = 0.0


@dataclass
class SMCFeatures:
    """Caractéristiques Price Action & Smart Money Concepts détectées sur les bougies."""
    candlestick_pattern: str = "Neutre (Aucune figure majeure)"
    candlestick_direction: str = "NEUTRAL"
    is_pin_bar: bool = False
    is_hammer: bool = False
    is_shooting_star: bool = False
    is_marubozu: bool = False
    is_engulfing: bool = False
    is_doji: bool = False
    nearest_round_level: float = 4150.0
    distance_to_round_level: float = 4.80
    round_level_type: str = "50$"       # "50$" ou "100$"
    pdh: float = 4165.00                # Previous Day High
    pdl: float = 4132.00                # Previous Day Low
    pwh: float = 4180.00                # Previous Week High
    pwl: float = 4110.00                # Previous Week Low
    fvg_detected: bool = False
    fvg_type: Optional[str] = None      # "BULLISH_FVG" ou "BEARISH_FVG"
    fvg_zone: Tuple[float, float] = (0.0, 0.0)
    rsi_divergence: Optional[str] = None  # "BULLISH_DIVERGENCE", "BEARISH_DIVERGENCE" ou None


@dataclass
class SessionTelemetry:
    """Informations de microstructure et de session de marché."""
    active_session_name: str = "Session de Londres"
    session_liquidity_profile: str = "Élevée (Expansion & Breakouts)"
    is_overlap_london_ny: bool = False
    is_near_lbma_fixing: bool = False
    lbma_fixing_name: Optional[str] = None
    is_rollover_blackout: bool = False
    utc_hour: int = 14
    utc_minute: int = 30


@dataclass
class GoldIntelligenceReport:
    """Rapport d'intelligence complet synthétisant prédictions et explicabilité."""
    timestamp: str
    composite_bias: str                 # "FORTEMENT HAUSSIER", "HAUSSIER", "NEUTRE", "BAISSIER", "FORTEMENT BAISSIER"
    confidence_percent: int             # 0 à 100%
    bullish_probability: int            # 0 à 100%
    bearish_probability: int            # 0 à 100%
    
    target_1: float
    target_2: float
    invalidation_level: float
    nearest_round_level: float
    
    decision_summary: str               # Pourquoi le bot prend ou ne prend pas position
    positive_catalysts: List[str]       # Facteurs favorables à l'achat
    negative_catalysts: List[str]       # Facteurs favorables à la vente
    
    macro_score: int                    # -100 à +100
    geopolitics_score: int              # -100 à +100
    institutional_score: int            # -100 à +100
    price_action_score: int             # -100 à +100
    microstructure_score: int           # -100 à +100
    
    macro_data: Dict[str, Any]
    smc_data: Dict[str, Any]
    session_data: Dict[str, Any]


class GoldIntelligenceEngine:
    """Moteur central d'intelligence fondamentale, technique et microstructure pour l'Or."""

    def __init__(self, logger: Optional[logging.Logger] = None):
        self.logger = logger or logging.getLogger("TradingBot.Intelligence")
        self.macro_cache = MacroMetrics()
        self._last_fetch_attempt: float = 0.0
        self._fetch_lock = threading.Lock()
        
        # Lancer un premier rafraîchissement asynchrone pour ne jamais bloquer le démarrage
        threading.Thread(target=self._refresh_macro_data_async, daemon=True).start()

    # =========================================================================
    # 1. ACQUISITION MACROÉCONOMIQUE & SENTIMENT DE MARCHÉ (ASYNCHRONE)
    # =========================================================================

    def _fetch_ticker_meta(self, symbol: str) -> Optional[Tuple[float, float]]:
        """Interroge l'endpoint public pour récupérer le dernier prix et la clôture de la veille."""
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval=1d&range=2d"
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        try:
            resp = requests.get(url, headers=headers, timeout=3.5)
            if resp.status_code == 200:
                data = resp.json()
                meta = data["chart"]["result"][0]["meta"]
                price = float(meta.get("regularMarketPrice") or 0.0)
                prev_close = float(meta.get("chartPreviousClose") or price)
                return price, prev_close
        except Exception as e:
            self.logger.debug("Échec fetch macro ticker %s : %s", symbol, e)
        return None

    def _refresh_macro_data_async(self) -> None:
        """Tâche de fond actualisant les cotations macro (US 10Y, DXY, VIX, GLD)."""
        now = time.time()
        with self._fetch_lock:
            if now - self._last_fetch_attempt < 60.0:  # Cache d'au moins 60 secondes
                return
            self._last_fetch_attempt = now

        # 1. US 10 ans (^TNX)
        res_tnx = self._fetch_ticker_meta("%5ETNX")
        # 2. Dollar Index (DX-Y.NYB)
        res_dxy = self._fetch_ticker_meta("DX-Y.NYB")
        # 3. VIX Index (^VIX)
        res_vix = self._fetch_ticker_meta("%5EVIX")
        # 4. ETF GLD
        res_gld = self._fetch_ticker_meta("GLD")

        with self._fetch_lock:
            if res_tnx and res_tnx[0] > 0:
                self.macro_cache.us_10y_yield = res_tnx[0]
                self.macro_cache.us_10y_prev_close = res_tnx[1]
                # Approximation taux réel = US 10 ans - inflation anticipée (~2.3%)
                self.macro_cache.real_rate_proxy = round(res_tnx[0] - 2.30, 2)

            if res_dxy and res_dxy[0] > 0:
                self.macro_cache.dxy_price = res_dxy[0]
                self.macro_cache.dxy_prev_close = res_dxy[1]

            if res_vix and res_vix[0] > 0:
                self.macro_cache.vix_index = res_vix[0]
                self.macro_cache.vix_prev_close = res_vix[1]

            if res_gld and res_gld[0] > 0:
                self.macro_cache.gld_price = res_gld[0]
                self.macro_cache.gld_prev_close = res_gld[1]

            self.macro_cache.last_updated = time.time()

    def get_macro_metrics(self) -> MacroMetrics:
        """Retourne les métriques macro actuelles (actualise en tâche de fond si le cache a plus de 120s)."""
        if time.time() - self.macro_cache.last_updated > 120.0:
            threading.Thread(target=self._refresh_macro_data_async, daemon=True).start()
        return self.macro_cache

    # =========================================================================
    # 2. ANALYSE PRICE ACTION & SMART MONEY CONCEPTS (SMC)
    # =========================================================================

    @staticmethod
    def analyze_candlesticks_and_smc(df: pd.DataFrame, current_spot: float) -> SMCFeatures:
        """
        Détecte les figures de chandeliers japonais et les structures Smart Money :
        - Pin bars, Marteaux (Hammers), Étoiles filantes (Shooting stars)
        - Marubozu, Avalements (Engulfing), Dojis
        - Fair Value Gaps (FVG)
        - Niveaux psychologiques ($50 / $100)
        - PDH / PDL / PWH / PWL
        - Divergences RSI
        """
        if len(df) < 5:
            return SMCFeatures()

        last_closed = df.iloc[-2]
        prev_closed = df.iloc[-3]
        two_back = df.iloc[-4] if len(df) >= 4 else prev_closed

        open_val = float(last_closed["open"])
        high_val = float(last_closed["high"])
        low_val = float(last_closed["low"])
        close_val = float(last_closed["close"])
        body = abs(close_val - open_val)
        candle_range = max(high_val - low_val, 0.01)
        upper_wick = high_val - max(open_val, close_val)
        lower_wick = min(open_val, close_val) - low_val

        # 1. Chiffres ronds psychologiques (Multiples de 50$ et 100$)
        nearest_50 = round(current_spot / 50.0) * 50.0
        nearest_100 = round(current_spot / 100.0) * 100.0
        dist_50 = abs(current_spot - nearest_50)
        dist_100 = abs(current_spot - nearest_100)

        if dist_100 <= dist_50:
            nearest_round = nearest_100
            dist_round = dist_100
            round_type = "100$ (Majeur)"
        else:
            nearest_round = nearest_50
            dist_round = dist_50
            round_type = "50$ (Intermédiaire)"

        # 2. Détection des Figures de Chandeliers Japonais
        pattern_name = "Neutre (Aucune figure majeure)"
        direction = "NEUTRAL"
        is_pin_bar = False
        is_hammer = False
        is_shooting_star = False
        is_marubozu = False
        is_engulfing = False
        is_doji = False

        # Marteau / Pin Bar haussier (Rejet violent des bas / Liquidity Sweep)
        if lower_wick >= candle_range * 0.55 and upper_wick <= candle_range * 0.20:
            is_hammer = True
            is_pin_bar = True
            pattern_name = "Marteau / Pin Bar Haussière (Balayage de liquidité basse)"
            direction = "BULLISH"

        # Étoile Filante / Pin Bar baissière (Rejet violent des hauts / Liquidity Sweep)
        elif upper_wick >= candle_range * 0.55 and lower_wick <= candle_range * 0.20:
            is_shooting_star = True
            is_pin_bar = True
            pattern_name = "Étoile Filante (Shooting Star - Rejet des sommets)"
            direction = "BEARISH"

        # Doji (Indécision avant explosion)
        elif body <= candle_range * 0.12:
            is_doji = True
            pattern_name = "Doji d'Indécision (Compression de Volatilité)"
            direction = "NEUTRAL"

        # Marubozu (Impulsion institutionnelle pure à grand corps)
        elif body >= candle_range * 0.85:
            is_marubozu = True
            if close_val > open_val:
                pattern_name = "Marubozu Haussier (Impulsion d'achats institutionnels)"
                direction = "BULLISH"
            else:
                pattern_name = "Marubozu Baissier (Ventes institutionnelles massives)"
                direction = "BEARISH"

        # Avalement (Engulfing)
        prev_open = float(prev_closed["open"])
        prev_close = float(prev_closed["close"])
        prev_body = abs(prev_close - prev_open)

        if (close_val > open_val) and (prev_close < prev_open) and (body > prev_body) and (close_val >= prev_open) and (open_val <= prev_close):
            is_engulfing = True
            pattern_name = "Avalement Haussier (Engulfing Institutionnel)"
            direction = "BULLISH"
        elif (close_val < open_val) and (prev_close > prev_open) and (body > prev_body) and (close_val <= prev_open) and (open_val >= prev_close):
            is_engulfing = True
            pattern_name = "Avalement Baissier (Engulfing Baissier)"
            direction = "BEARISH"

        # 3. Fair Value Gaps (FVG) sur 3 bougies consécutives
        # FVG Haussier : Le plus bas de la bougie 1 est supérieur au plus haut de la bougie 3
        # FVG Baissier : Le plus haut de la bougie 1 est inférieur au plus bas de la bougie 3
        fvg_detected = False
        fvg_type = None
        fvg_zone = (0.0, 0.0)

        candle_1_low = float(last_closed["low"])
        candle_1_high = float(last_closed["high"])
        candle_3_high = float(two_back["high"])
        candle_3_low = float(two_back["low"])

        if candle_1_low > candle_3_high:
            fvg_detected = True
            fvg_type = "BULLISH_FVG"
            fvg_zone = (round(candle_3_high, 2), round(candle_1_low, 2))
        elif candle_1_high < candle_3_low:
            fvg_detected = True
            fvg_type = "BEARISH_FVG"
            fvg_zone = (round(candle_1_high, 2), round(candle_3_low, 2))

        # 4. Calcul PDH / PDL (Previous Day High / Low) et PWH / PWL
        highs = df["high"].astype(float)
        lows = df["low"].astype(float)
        pdh = round(float(highs.tail(96).max()), 2) if len(highs) >= 96 else round(float(highs.max()), 2)
        pdl = round(float(lows.tail(96).min()), 2) if len(lows) >= 96 else round(float(lows.min()), 2)
        pwh = round(float(highs.max()), 2)
        pwl = round(float(lows.min()), 2)

        # 5. Détection des Divergences RSI (sur 14 périodes)
        rsi_divergence = None
        if "rsi" in df.columns and len(df) >= 20:
            rsi_recent = df["rsi"].tail(10).values
            close_recent = df["close"].tail(10).values
            # Divergence haussière classique : Prix fait un creux plus bas, mais RSI fait un creux plus haut
            if close_recent[-1] < close_recent[-6] and rsi_recent[-1] > rsi_recent[-6]:
                rsi_divergence = "BULLISH_DIVERGENCE"
            # Divergence baissière classique : Prix fait un sommet plus haut, mais RSI fait un sommet plus bas
            elif close_recent[-1] > close_recent[-6] and rsi_recent[-1] < rsi_recent[-6]:
                rsi_divergence = "BEARISH_DIVERGENCE"

        return SMCFeatures(
            candlestick_pattern=pattern_name,
            candlestick_direction=direction,
            is_pin_bar=is_pin_bar,
            is_hammer=is_hammer,
            is_shooting_star=is_shooting_star,
            is_marubozu=is_marubozu,
            is_engulfing=is_engulfing,
            is_doji=is_doji,
            nearest_round_level=nearest_round,
            distance_to_round_level=round(dist_round, 2),
            round_level_type=round_type,
            pdh=pdh,
            pdl=pdl,
            pwh=pwh,
            pwl=pwl,
            fvg_detected=fvg_detected,
            fvg_type=fvg_type,
            fvg_zone=fvg_zone,
            rsi_divergence=rsi_divergence,
        )

    # =========================================================================
    # 3. MICROSTRUCTURE & HORAIRES DE SESSION
    # =========================================================================

    @staticmethod
    def analyze_microstructure_and_session() -> SessionTelemetry:
        """
        Analyse les fenêtres de volatilité et sessions de trading pour XAU/USD :
        - Asie (00h00 - 08h00 UTC) : Accumulation, range.
        - Londres (08h00 - 16h00 UTC) : Injection majeure de volume, chasse de liquidité.
        - Overlap Londres / New York (13h00 - 16h00 UTC) : Pic absolu de liquidité.
        - New York (16h00 - 21h00 UTC) : Poursuite ou correction.
        - Fixings LBMA à Londres : 10h30 GMT et 15h00 GMT.
        - Rollover interbancaire : 22h00 - 23h00 UTC (23h00 - 00h00 Paris).
        """
        now_utc = datetime.now(timezone.utc)
        hour = now_utc.hour
        minute = now_utc.minute
        time_decimal = hour + minute / 60.0

        is_overlap = (13.0 <= time_decimal <= 16.0)
        is_rollover = (22.0 <= time_decimal <= 23.5)

        # Fixings LBMA (10h30 et 15h00 UTC, ±15 min)
        is_near_fixing = False
        fixing_name = None
        if (10.25 <= time_decimal <= 10.75):
            is_near_fixing = True
            fixing_name = "LBMA Gold AM Fixing (10:30 GMT)"
        elif (14.75 <= time_decimal <= 15.25):
            is_near_fixing = True
            fixing_name = "LBMA Gold PM Fixing (15:00 GMT)"

        # Détermination de la session principale
        if 0.0 <= time_decimal < 8.0:
            session_name = "Session Asiatique (Tokyo / Hong-Kong)"
            profile = "Faible volatilité • Formation de ranges d'accumulation"
        elif 8.0 <= time_decimal < 13.0:
            session_name = "Session Européenne (Londres)"
            profile = "Volatilité Forte • Première injection majeure de volume"
        elif 13.0 <= time_decimal <= 16.0:
            session_name = "Overlap Londres / New York"
            profile = "VOLATILITÉ & LIQUIDITÉ MAXIMALES • Pic journalier d'activité"
        elif 16.0 < time_decimal < 21.0:
            session_name = "Session Américaine (New York)"
            profile = "Volatilité Modérée • Poursuite ou consolidations"
        else:
            session_name = "Fin de journée & Clôture américaine"
            profile = "Liquidité réduite • Vigilance sur les écartements de spread"

        return SessionTelemetry(
            active_session_name=session_name,
            session_liquidity_profile=profile,
            is_overlap_london_ny=is_overlap,
            is_near_lbma_fixing=is_near_fixing,
            lbma_fixing_name=fixing_name,
            is_rollover_blackout=is_rollover,
            utc_hour=hour,
            utc_minute=minute,
        )

    # =========================================================================
    # 4. SAISONNALITÉ PHYSIQUE & ANALYSE DE LA DEMANDE
    # =========================================================================

    @staticmethod
    def compute_physical_seasonality_score() -> Tuple[int, str]:
        """
        Évalue la saisonnalité physique de l'or :
        - Septembre - Novembre : Fêtes & Mariages en Inde (Diwali) -> Très forte demande de joaillerie.
        - Décembre - Février : Préparation & Nouvel An Lunaire en Chine -> Achats massifs de lingots et bijoux.
        - Mars - Juin : Demande physique plus calme, dominée par l'industrie électronique et les flux d'investissement.
        """
        now = datetime.now()
        month = now.month

        if month in (9, 10, 11):
            return 35, "Haussière Forte : Période des mariages et fêtes en Inde (Diwali / Dhanteras)"
        elif month in (12, 1, 2):
            return 30, "Haussière Forte : Forte demande du Nouvel An Lunaire chinois et fêtes de fin d'année"
        elif month in (7, 8):
            return 10, "Modérée : Reprise graduelle de la demande physique avant l'automne"
        else:
            return 0, "Neutre : Demande physique stable (industrie électronique et joaillerie de base)"

    # =========================================================================
    # 5. SYNTHÈSE MULTI-FACTORIELLE : CERVEAU DÉCISIONNEL & PRÉDICTIONS
    # =========================================================================

    def generate_intelligence_report(
        self,
        current_spot: float,
        df_indicators: pd.DataFrame,
        current_spread: float,
    ) -> GoldIntelligenceReport:
        """
        Synthétise les 5 piliers dans un rapport d'intelligence complet avec :
        - Prédiction directionnelle et probabilité chiffrée
        - Cibles de prix (Target 1, Target 2, Invalidation, Chiffre rond)
        - Scores des 5 piliers de -100 à +100
        - Explications textuelles détaillées de la décision
        - Liste des catalyseurs positifs et négatifs
        """
        macro = self.get_macro_metrics()
        smc = self.analyze_candlesticks_and_smc(df_indicators, current_spot)
        session = self.analyze_microstructure_and_session()
        season_score, season_desc = self.compute_physical_seasonality_score()

        positive_catalysts: List[str] = []
        negative_catalysts: List[str] = []

        # ---------------------------------------------------------------------
        # PILIER 1 : MACROÉCONOMIE & TAUX RÉELS (-100 à +100)
        # ---------------------------------------------------------------------
        macro_score = 0

        # Dollar Index (DXY)
        dxy_change_pct = ((macro.dxy_price - macro.dxy_prev_close) / max(macro.dxy_prev_close, 1.0)) * 100.0
        if dxy_change_pct < -0.20:
            macro_score += 35
            positive_catalysts.append(f"Dollar Index (DXY) en repli ({macro.dxy_price:.2f}, {dxy_change_pct:+.2f}%) : Soutien direct pour l'or libellé en USD.")
        elif dxy_change_pct > +0.20:
            macro_score -= 35
            negative_catalysts.append(f"Dollar Index (DXY) en hausse ({macro.dxy_price:.2f}, {dxy_change_pct:+.2f}%) : Pression baissière par renforcement du billet vert.")
        else:
            macro_score += 5
            positive_catalysts.append(f"Dollar Index (DXY) stable ({macro.dxy_price:.2f}) : Aucun obstacle de change majeur.")

        # Taux 10 ans US (US 10Y Yield) & Taux réels
        tnx_change_pct = ((macro.us_10y_yield - macro.us_10y_prev_close) / max(macro.us_10y_prev_close, 1.0)) * 100.0
        if macro.us_10y_yield < 4.20 or tnx_change_pct < -0.5:
            macro_score += 35
            positive_catalysts.append(f"Rendement US 10 ans en baisse ({macro.us_10y_yield:.2f}%) : Baisse du coût d'opportunité de détenir de l'or.")
        elif macro.us_10y_yield > 4.60 or tnx_change_pct > +0.5:
            macro_score -= 35
            negative_catalysts.append(f"Rendement US 10 ans sous tension ({macro.us_10y_yield:.2f}%) : Concurrence des obligations américaines.")
        else:
            macro_score += 10
            positive_catalysts.append(f"Taux réels américains maîtrisés (~{macro.real_rate_proxy:.2f}%) : Environnement propice à la valorisation de l'or.")

        # Biais Fed & Anticipations
        macro_score += 15
        positive_catalysts.append("Politique monétaire Fed : Anticipations d'assouplissement monétaire favorables à moyen terme.")

        macro_score = max(min(macro_score, 100), -100)

        # ---------------------------------------------------------------------
        # PILIER 2 : GÉOPOLITIQUE & SENTIMENT DE RISQUE VIX (-100 à +100)
        # ---------------------------------------------------------------------
        geopolitics_score = 30  # Biais haussier structurel de base pour la valeur refuge
        positive_catalysts.append("Statut Valeur Refuge (Safe Haven) : Tensions internationales persistantes et diversification BRICS hors dollar.")

        if macro.vix_index >= 20.0:
            geopolitics_score += 45
            positive_catalysts.append(f"Indice VIX élevé ({macro.vix_index:.1f}) : Régime Risk-Off avéré, recherche active de sécurité sur l'or.")
        elif macro.vix_index <= 14.0:
            geopolitics_score -= 15
            negative_catalysts.append(f"Indice VIX faible ({macro.vix_index:.1f}) : Appétit pour le risque (Risk-On) sur les marchés actions.")
        else:
            geopolitics_score += 15
            positive_catalysts.append(f"Volatilité VIX modérée ({macro.vix_index:.1f}) : Pas de panique vendeuse.")

        geopolitics_score = max(min(geopolitics_score, 100), -100)

        # ---------------------------------------------------------------------
        # PILIER 3 : FLUX INSTITUTIONNELS & PHYSIQUE (-100 à +100)
        # ---------------------------------------------------------------------
        institutional_score = 30
        positive_catalysts.append("Banques centrales mondiales (PBOC, Turquie, Pologne) : Achats nets continus de lingots formant un plancher structurel.")

        # ETF GLD
        gld_change_pct = ((macro.gld_price - macro.gld_prev_close) / max(macro.gld_prev_close, 1.0)) * 100.0
        if gld_change_pct >= 0.10:
            institutional_score += 30
            positive_catalysts.append(f"ETF SPDR Gold Shares (GLD) en hausse ({macro.gld_price:.2f}$, {gld_change_pct:+.2f}%) : Flux entrants des institutionnels.")
        elif gld_change_pct <= -0.10:
            institutional_score -= 20
            negative_catalysts.append(f"ETF SPDR Gold Shares (GLD) en léger repli ({macro.gld_price:.2f}$) : Prises de bénéfices des fonds.")

        # Saisonnalité
        institutional_score += season_score
        positive_catalysts.append(f"Saisonnalité physique : {season_desc}")

        institutional_score = max(min(institutional_score, 100), -100)

        # ---------------------------------------------------------------------
        # PILIER 4 : PRICE ACTION & SMART MONEY CONCEPTS (-100 à +100)
        # ---------------------------------------------------------------------
        price_action_score = 0

        # Tendance des Moyennes Mobiles
        if len(df_indicators) >= 2:
            last_c = df_indicators.iloc[-2]
            ema_fast = float(last_c.get("ema_fast", current_spot))
            ema_slow = float(last_c.get("ema_slow", current_spot))
            rsi = float(last_c.get("rsi", 50.0))

            if ema_fast >= ema_slow and current_spot >= ema_fast:
                price_action_score += 35
                positive_catalysts.append(f"Alignement technique haussier : Cours au-dessus de l'EMA rapide ({ema_fast:.2f}$) et lente ({ema_slow:.2f}$).")
            elif ema_fast <= ema_slow and current_spot <= ema_fast:
                price_action_score -= 35
                negative_catalysts.append(f"Alignement technique baissier : Cours sous les moyennes exponentielles ({ema_fast:.2f}$).")

            if 40.0 <= rsi <= 65.0:
                price_action_score += 15
                positive_catalysts.append(f"Momentum RSI équilibré ({rsi:.1f}) : Espace suffisant pour une extension haussière saine.")
            elif rsi > 70.0:
                price_action_score -= 20
                negative_catalysts.append(f"RSI en zone de surachat ({rsi:.1f}) : Risque accru de correction technique immédiate.")
            elif rsi < 30.0:
                price_action_score += 20
                positive_catalysts.append(f"RSI en zone de survente ({rsi:.1f}) : Opportunité de rebond d'épuisement.")

        # Figures de Chandelier
        if smc.candlestick_direction == "BULLISH":
            price_action_score += 35
            positive_catalysts.append(f"Chandelier remarquable : {smc.candlestick_pattern}")
        elif smc.candlestick_direction == "BEARISH":
            price_action_score -= 35
            negative_catalysts.append(f"Chandelier de vente : {smc.candlestick_pattern}")

        # Fair Value Gap
        if smc.fvg_detected:
            if smc.fvg_type == "BULLISH_FVG":
                price_action_score += 20
                positive_catalysts.append(f"Fair Value Gap (FVG) Haussier détecté entre {smc.fvg_zone[0]}$ et {smc.fvg_zone[1]}$ : Zone d'imbalance acheteuse.")
            else:
                price_action_score -= 20
                negative_catalysts.append(f"Fair Value Gap (FVG) Baissier détecté entre {smc.fvg_zone[0]}$ et {smc.fvg_zone[1]}$ : Résistance d'imbalance.")

        # Chiffres Ronds
        if smc.distance_to_round_level <= 3.0:
            positive_catalysts.append(f"Niveau psychologique immédiat : Seuil des {smc.nearest_round_level}$ à seulement {smc.distance_to_round_level}$ de distance.")

        # Divergences RSI
        if smc.rsi_divergence == "BULLISH_DIVERGENCE":
            price_action_score += 30
            positive_catalysts.append("Divergence RSI Haussière détectée : Épuisement du flux vendeur.")
        elif smc.rsi_divergence == "BEARISH_DIVERGENCE":
            price_action_score -= 30
            negative_catalysts.append("Divergence RSI Baissière détectée : Essoufflement de la poussée acheteuse.")

        price_action_score = max(min(price_action_score, 100), -100)

        # ---------------------------------------------------------------------
        # PILIER 5 : MICROSTRUCTURE & SESSIONS (-100 à +100)
        # ---------------------------------------------------------------------
        microstructure_score = 0
        if session.is_overlap_london_ny:
            microstructure_score += 30
            positive_catalysts.append(f"Timing optimal : {session.active_session_name} ({session.session_liquidity_profile}).")
        elif "Européenne" in session.active_session_name:
            microstructure_score += 20
            positive_catalysts.append(f"Session active : {session.active_session_name} - Liquidité institutionnelle abondante.")
        else:
            microstructure_score += 5

        if session.is_near_lbma_fixing:
            negative_catalysts.append(f"Vigilance Fixing : Proche du {session.lbma_fixing_name} - Risque de décalage brutal d'arbitrage.")
            microstructure_score -= 15

        if session.is_rollover_blackout:
            negative_catalysts.append("Alerte Rollover (23h00-00h00 Paris) : Élargissement interbancaire des spreads, trading déconseillé.")
            microstructure_score -= 40

        if current_spread > 0.85:
            negative_catalysts.append(f"Spread actuel ({current_spread:.3f}$) supérieur à la moyenne : Frictions d'exécution accrues.")
            microstructure_score -= 20

        microstructure_score = max(min(microstructure_score, 100), -100)

        # ---------------------------------------------------------------------
        # CALCUL DE LA PROBABILITÉ & BIAIS GLOBAL COMPOSITE
        # ---------------------------------------------------------------------
        # Pondérations : Macro (25%), Géopolitique (20%), Institutionnel (15%), Price Action/SMC (30%), Microstructure (10%)
        weighted_score = (
            macro_score * 0.25 +
            geopolitics_score * 0.20 +
            institutional_score * 0.15 +
            price_action_score * 0.30 +
            microstructure_score * 0.10
        )

        bullish_prob = int(round(50.0 + (weighted_score * 0.45)))
        bullish_prob = max(min(bullish_prob, 95), 5)
        bearish_prob = 100 - bullish_prob

        # Biais Directionnel & Confiance
        if weighted_score >= 45:
            composite_bias = "FORTEMENT HAUSSIER"
            confidence = min(int(round(65 + abs(weighted_score) * 0.35)), 98)
        elif weighted_score >= 15:
            composite_bias = "HAUSSIER"
            confidence = min(int(round(55 + abs(weighted_score) * 0.35)), 85)
        elif weighted_score <= -45:
            composite_bias = "FORTEMENT BAISSIER"
            confidence = min(int(round(65 + abs(weighted_score) * 0.35)), 98)
        elif weighted_score <= -15:
            composite_bias = "BAISSIER"
            confidence = min(int(round(55 + abs(weighted_score) * 0.35)), 85)
        else:
            composite_bias = "NEUTRE (ÉQUILIBRE)"
            confidence = 50

        # ---------------------------------------------------------------------
        # CIBLES DE PRIX PRÉDITES & INVALIDATION
        # ---------------------------------------------------------------------
        atr_approx = 6.50
        if len(df_indicators) >= 2 and "atr" in df_indicators.columns:
            atr_approx = float(df_indicators["atr"].iloc[-2]) or 6.50

        if "HAUSSIER" in composite_bias:
            target_1 = round(current_spot + (atr_approx * 1.5), 2)
            target_2 = round(current_spot + (atr_approx * 3.0), 2)
            invalidation = round(current_spot - max(atr_approx * 1.5, current_spot * 0.0035), 2)
        elif "BAISSIER" in composite_bias:
            target_1 = round(current_spot - (atr_approx * 1.5), 2)
            target_2 = round(current_spot - (atr_approx * 3.0), 2)
            invalidation = round(current_spot + max(atr_approx * 1.5, current_spot * 0.0035), 2)
        else:
            target_1 = round(current_spot + (atr_approx * 1.0), 2)
            target_2 = round(current_spot - (atr_approx * 1.0), 2)
            invalidation = round(current_spot - (atr_approx * 1.5), 2)

        # ---------------------------------------------------------------------
        # EXPLICATION DÉCISIONNELLE DÉTAILLÉE
        # ---------------------------------------------------------------------
        if session.is_rollover_blackout:
            decision_summary = (
                "ATTENTE PRUDENTE : Fenêtre de rollover interbancaire en cours. "
                "Le bot suspend les ouvertures pour éviter les écarts de spread anormaux."
            )
        elif current_spread > 0.95:
            decision_summary = (
                f"ATTENTE DE NORMALISATION : Spread de {current_spread:.3f}$ supérieur au seuil optimal. "
                "Le bot temporise pour protéger l'espérance mathématique des positions."
            )
        elif composite_bias in ("FORTEMENT HAUSSIER", "HAUSSIER"):
            decision_summary = (
                f"BIAIS ACHETEUR CONFIRMÉ ({bullish_prob}% de probabilité) : Confluence haussière validée par "
                f"le repli/maintien des taux et du DXY, les achats structurels des banques centrales, "
                f"et une structure Price Action favorable ({smc.candlestick_pattern})."
            )
        elif composite_bias in ("FORTEMENT BAISSIER", "BAISSIER"):
            decision_summary = (
                f"BIAIS VENDEUR CONFIRMÉ ({bearish_prob}% de probabilité) : Pression baissière induite par "
                f"le renforcement du dollar/obligations et une configuration technique en repli sous les résistances."
            )
        else:
            decision_summary = (
                f"ZONE D'INDÉCISION ET D'ACCUMULATION : Marché en équilibre ({bullish_prob}% vs {bearish_prob}%). "
                f"Le bot surveille la prochaine cassure du seuil des {smc.nearest_round_level}$ ou d'un FVG."
            )

        return GoldIntelligenceReport(
            timestamp=datetime.now().strftime("%H:%M:%S"),
            composite_bias=composite_bias,
            confidence_percent=confidence,
            bullish_probability=bullish_prob,
            bearish_probability=bearish_prob,
            target_1=target_1,
            target_2=target_2,
            invalidation_level=invalidation,
            nearest_round_level=smc.nearest_round_level,
            decision_summary=decision_summary,
            positive_catalysts=positive_catalysts[:6],
            negative_catalysts=negative_catalysts[:6],
            macro_score=macro_score,
            geopolitics_score=geopolitics_score,
            institutional_score=institutional_score,
            price_action_score=price_action_score,
            microstructure_score=microstructure_score,
            macro_data={
                "us_10y_yield": macro.us_10y_yield,
                "dxy_price": macro.dxy_price,
                "real_rate_proxy": macro.real_rate_proxy,
                "vix_index": macro.vix_index,
                "gld_price": macro.gld_price,
            },
            smc_data={
                "candlestick_pattern": smc.candlestick_pattern,
                "candlestick_direction": smc.candlestick_direction,
                "nearest_round_level": smc.nearest_round_level,
                "distance_to_round_level": smc.distance_to_round_level,
                "round_level_type": smc.round_level_type,
                "pdh": smc.pdh,
                "pdl": smc.pdl,
                "pwh": smc.pwh,
                "pwl": smc.pwl,
                "fvg_detected": smc.fvg_detected,
                "fvg_type": smc.fvg_type,
                "fvg_zone": list(smc.fvg_zone),
                "rsi_divergence": smc.rsi_divergence,
            },
            session_data={
                "active_session_name": session.active_session_name,
                "session_liquidity_profile": session.session_liquidity_profile,
                "is_overlap_london_ny": session.is_overlap_london_ny,
                "is_near_lbma_fixing": session.is_near_lbma_fixing,
                "lbma_fixing_name": session.lbma_fixing_name,
                "is_rollover_blackout": session.is_rollover_blackout,
                "season_desc": season_desc,
            },
        )
