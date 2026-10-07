"""
Module auth.py : Gestionnaire d'authentification et de session pour Capital.com.
Gère la connexion initiale, l'extraction et la mise à jour dynamique des en-têtes CST et X-SECURITY-TOKEN,
la reconnexion automatique en cas d'expiration et la déconnexion propre.
"""

import logging
import threading
import time
from typing import Any, Dict, Optional
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from src.config import TradingConfig


class CapitalAuthError(Exception):
    """Exception levée en cas d'échec d'authentification ou d'invalidation de session."""
    pass


class AuthSessionManager:
    """
    Gestionnaire de cycle de vie de session Capital.com thread-safe.
    Maintient les tokens CST et X-SECURITY-TOKEN et fournit une session requests configurée.
    """

    def __init__(self, config: TradingConfig, logger: Optional[logging.Logger] = None):
        self.config = config
        self.logger = logger or logging.getLogger("TradingBot.Auth")

        self._lock = threading.Lock()
        self.cst: Optional[str] = None
        self.security_token: Optional[str] = None
        self.current_account_id: Optional[str] = None
        self.last_auth_time: float = 0.0

        # Session HTTP persistante avec pooling de connexions
        self.session = requests.Session()
        self._configure_http_adapters()

    def _configure_http_adapters(self) -> None:
        """Configure les retries au niveau transport HTTP pour les erreurs de réseau transitoires."""
        retries = Retry(
            total=3,
            backoff_factor=1.0,
            status_forcelist=[500, 502, 503, 504],
            raise_on_status=False,
        )
        adapter = HTTPAdapter(max_retries=retries, pool_connections=10, pool_maxsize=10)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)

    def is_authenticated(self) -> bool:
        """Vérifie si les tokens sont présents en mémoire."""
        return bool(self.cst and self.security_token)

    def authenticate(self) -> bool:
        """
        Effectue une requête POST /api/v1/session pour initier la session.
        Extrait les headers CST et X-SECURITY-TOKEN ainsi que l'identifiant de compte actif.
        """
        url = f"{self.config.base_url}session"
        headers = {
            "X-CAP-API-KEY": self.config.api_key,
            "Content-Type": "application/json",
        }
        payload = {
            "identifier": self.config.identifier,
            "password": self.config.password,
        }

        self.logger.info("Connexion en cours à Capital.com (%s)...", self.config.environment)

        with self._lock:
            try:
                response = self.session.post(url, headers=headers, json=payload, timeout=15)

                if response.status_code == 200:
                    cst_token = response.headers.get("CST")
                    sec_token = response.headers.get("X-SECURITY-TOKEN")

                    if not cst_token or not sec_token:
                        raise CapitalAuthError(
                            "En-têtes d'authentification manquants dans la réponse de Capital.com "
                            f"(CST={bool(cst_token)}, X-SECURITY-TOKEN={bool(sec_token)})"
                        )

                    self.cst = cst_token
                    self.security_token = sec_token
                    self.last_auth_time = time.time()

                    data = response.json()
                    self.current_account_id = data.get("currentAccountId")

                    self.logger.info(
                        "Authentification réussie. Compte ID: %s",
                        self.current_account_id or "Non spécifié",
                    )
                    return True

                error_msg = response.text
                try:
                    error_json = response.json()
                    error_msg = error_json.get("errorCode", response.text)
                except Exception:
                    pass

                self.logger.error("Échec d'authentification (HTTP %d): %s", response.status_code, error_msg)
                raise CapitalAuthError(f"HTTP {response.status_code}: {error_msg}")

            except requests.RequestException as e:
                self.logger.error("Erreur réseau lors de la tentative d'authentification: %s", e)
                raise CapitalAuthError(f"Erreur réseau: {e}") from e

    def get_auth_headers(self) -> Dict[str, str]:
        """
        Renvoie les en-têtes HTTP obligatoires pour toute requête protégée.
        Si la session n'est pas initialisée, tente une authentification.
        """
        if not self.is_authenticated():
            self.authenticate()

        with self._lock:
            return {
                "X-CAP-API-KEY": self.config.api_key,
                "CST": self.cst or "",
                "X-SECURITY-TOKEN": self.security_token or "",
                "Content-Type": "application/json",
            }

    def update_tokens_from_response(self, response: requests.Response) -> None:
        """
        Met à jour dynamiquement les tokens CST et X-SECURITY-TOKEN si le serveur
        les renouvelle dans les en-têtes d'une réponse ultérieure.
        """
        new_cst = response.headers.get("CST")
        new_sec = response.headers.get("X-SECURITY-TOKEN")

        with self._lock:
            if new_cst:
                self.cst = new_cst
            if new_sec:
                self.security_token = new_sec

            if new_cst or new_sec:
                self.last_auth_time = time.time()

    def request_with_reauth(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        json: Optional[Dict[str, Any]] = None,
        timeout: int = 15,
    ) -> requests.Response:
        """
        Envoie une requête HTTP à l'API en injectant les en-têtes de session.
        Gère automatiquement la ré-authentification si une erreur 401 Unauthorized survient.
        """
        url = f"{self.config.base_url}{endpoint.lstrip('/')}"

        for attempt in range(2):
            headers = self.get_auth_headers()
            try:
                response = self.session.request(
                    method=method.upper(),
                    url=url,
                    headers=headers,
                    params=params,
                    json=json,
                    timeout=timeout,
                )

                # Capture de tokens potentiellement renouvelés
                self.update_tokens_from_response(response)

                if response.status_code == 401 and attempt == 0:
                    self.logger.warning("Session expirée (HTTP 401). Ré-authentification en cours...")
                    self.cst = None
                    self.security_token = None
                    self.authenticate()
                    continue

                return response

            except requests.RequestException as e:
                if attempt == 1:
                    raise
                self.logger.warning("Erreur requête (%s %s) : %s. Nouvelle tentative...", method, endpoint, e)
                time.sleep(1.0)

        raise CapitalAuthError(f"Échec de la requête {method} {endpoint} après ré-authentification.")

    def ping(self) -> bool:
        """
        Maintient la session active en effectuant un appel léger (Keep-Alive).
        """
        try:
            response = self.request_with_reauth("GET", "ping")
            return response.status_code == 200
        except Exception as e:
            self.logger.debug("Ping échoué: %s", e)
            return False

    def logout(self) -> None:
        """Ferme proprement la session sur le serveur Capital.com."""
        if not self.is_authenticated():
            return

        try:
            url = f"{self.config.base_url}session"
            headers = self.get_auth_headers()
            self.session.delete(url, headers=headers, timeout=5)
            self.logger.info("Session Capital.com clôturée proprement.")
        except Exception as e:
            self.logger.warning("Erreur lors de la déconnexion: %s", e)
        finally:
            self.cst = None
            self.security_token = None
            self.session.close()
