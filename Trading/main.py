"""
Module main.py : Lanceur de l'Application Interactive & Orchestrateur Autonome.
Démarre le serveur local Flask, initialise la connexion Capital.com et ouvre
automatiquement l'application de trading dans votre navigateur.
"""

import threading
import time
import webbrowser
from rich.console import Console
from rich.panel import Panel

from app import app, bot_service

console = Console()


def open_browser(url: str, delay_seconds: float = 1.2) -> None:
    """Ouvre automatiquement la fenêtre de l'application dans le navigateur par défaut."""
    time.sleep(delay_seconds)
    try:
        webbrowser.open(url)
    except Exception as e:
        console.print(f"[yellow]Impossible d'ouvrir le navigateur automatiquement : {e}[/yellow]")


def main():
    port = 5000
    app_url = f"http://127.0.0.1:{port}"

    console.print(Panel(
        f"[bold gold1]GOLD TRADER PRO - TERMINAL CAPITAL.COM[/bold gold1]\n"
        f"[cyan]Connexion en direct :[/cyan] Compte Démo #330847176266952990\n"
        f"[green]Application en ligne :[/green] [bold underline]{app_url}[/bold underline]\n\n"
        f"• [bold green]ACHAT/VENTE 1-Click[/bold green] : Déclenchez des ordres immédiats avec calcul dynamique SL/TP.\n"
        f"• [bold yellow]Mode Actif (Scalping)[/bold yellow] : Déclenche des trades dès qu'une opportunité se présente.\n"
        f"• [bold red]Pour arrêter[/bold red] : Faites [bold]Ctrl + C[/bold] dans ce terminal.",
        title="Démarrage de l'Application",
        border_style="gold1",
    ))

    # Initialisation de la connexion Capital.com
    console.print("[cyan]Connexion à l'API de Capital.com...[/cyan]")
    if not bot_service.initialize():
        console.print("[bold red]Erreur lors de la connexion initiale. Vérifiez votre connexion Internet.[/bold red]")
        return

    # Démarrage de la boucle autonome en arrière-plan
    bot_service.start_background_loop()
    console.print("[bold green]Moteur de trading et surveillance de l'Or actifs ![/bold green]")

    # Ouverture automatique de l'interface graphique
    threading.Thread(target=open_browser, args=(app_url,), daemon=True).start()

    # Lancement du serveur Web Flask
    try:
        app.run(host="127.0.0.1", port=port, debug=False, use_reloader=False)
    except KeyboardInterrupt:
        console.print("\n[yellow]Fermeture ordonnée de l'application...[/yellow]")
    finally:
        bot_service.stop_background_loop()
        console.print("[bold green]Application et bot arrêtés proprement.[/bold green]")


if __name__ == "__main__":
    main()
