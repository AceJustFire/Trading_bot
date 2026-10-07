"""
Application Flask interactive pour le bot de trading Capital.com (Gold XAU/USD).
Fournit l'interface utilisateur en temps réel et l'API de contrôle.
"""

from typing import Any, Dict
from flask import Flask, jsonify, render_template, request

from src.bot_service import BotService

app = Flask(__name__)
bot_service = BotService()


@app.route("/")
def index():
    """Page d'accueil de l'application de trading."""
    return render_template("index.html")


@app.route("/api/status", methods=["GET"])
def get_status():
    """Renvoie l'état complet du bot (prix, indicateurs, positions, logs, intelligence)."""
    return jsonify(bot_service.get_full_state())


@app.route("/api/intelligence", methods=["GET"])
def get_intelligence():
    """Renvoie le rapport d'intelligence en direct et l'explicabilité décisionnelle."""
    state = bot_service.get_full_state()
    return jsonify(state.get("intelligence") or {})


@app.route("/api/trade", methods=["POST"])
def manual_trade():
    """Déclenche un ordre d'achat ou de vente immédiat 1-Click."""
    data = request.get_json() or {}
    direction = data.get("direction", "").upper()
    if direction not in ("BUY", "SELL"):
        return jsonify({"success": False, "error": "Direction invalide (BUY ou SELL attendu)"}), 400

    result = bot_service.execute_manual_order(direction)
    return jsonify(result)


@app.route("/api/close/<deal_id>", methods=["POST"])
def close_deal(deal_id: str):
    """Ferme une position spécifique."""
    ok = bot_service.close_single_position(deal_id)
    return jsonify({"success": ok})


@app.route("/api/close-all", methods=["POST"])
def close_all():
    """Ferme toutes les positions ouvertes."""
    count = bot_service.close_all_positions()
    return jsonify({"success": True, "closed_count": count})


@app.route("/api/toggle-auto", methods=["POST"])
def toggle_auto():
    """Active / Désactive le trading autonome."""
    is_active = bot_service.toggle_auto_trading()
    return jsonify({"success": True, "is_auto_trading": is_active})


@app.route("/api/set-mode", methods=["POST"])
def set_strategy_mode():
    """Bascule entre le mode actif et conservateur."""
    data = request.get_json() or {}
    mode = data.get("mode", "active")
    bot_service.set_strategy_mode(mode)
    return jsonify({"success": True, "strategy_mode": mode})


@app.route("/api/set-timeframe", methods=["POST"])
def set_timeframe():
    """Modifie la timeframe d'analyse."""
    data = request.get_json() or {}
    tf = data.get("timeframe", "MINUTE_15")
    bot_service.set_timeframe(tf)
    return jsonify({"success": True, "timeframe": tf})


@app.route("/api/set-risk", methods=["POST"])
def set_risk():
    """Configure l'effet de levier (jusqu'à 20:1) et le % de capital tradé."""
    data = request.get_json() or {}
    leverage = data.get("leverage")
    capital_percent = data.get("capital_percent")

    if leverage is None and capital_percent is None:
        return jsonify({"success": False, "error": "Paramètre 'leverage' ou 'capital_percent' requis"}), 400

    settings = bot_service.set_risk_parameters(leverage=leverage, capital_percent=capital_percent)
    return jsonify({"success": True, "risk_settings": settings})


def start_server(port: int = 5000, debug: bool = False):
    """Initialise le bot et démarre le serveur web Flask."""
    if bot_service.initialize():
        bot_service.start_background_loop()
    app.run(host="127.0.0.1", port=port, debug=debug, use_reloader=False)


if __name__ == "__main__":
    start_server()
