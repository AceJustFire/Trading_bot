"""
Module logger.py : Configuration centralisée de la journalisation (Logging).
Assure un affichage console lisible et formaté ainsi qu'une persistance sur fichier.
"""

import logging
import sys
from pathlib import Path


def setup_logger(
    name: str = "TradingBot",
    log_dir: str = "logs",
    log_file: str = "bot.log",
    level: int = logging.INFO,
) -> logging.Logger:
    """
    Initialise et configure le logger principal de l'application.

    :param name: Nom du logger
    :param log_dir: Répertoire de stockage des fichiers journaux
    :param log_file: Nom du fichier de log
    :param level: Niveau de logging minimum (défaut: INFO)
    :return: Instance configurée de logging.Logger
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)

    # Éviter les handlers dupliqués si réinitialisé
    if logger.hasHandlers():
        logger.handlers.clear()

    # Création du dossier logs s'il n'existe pas
    log_path = Path(log_dir)
    log_path.mkdir(parents=True, exist_ok=True)

    file_formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)-8s] (%(filename)s:%(lineno)d) - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    console_formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)-8s] %(message)s",
        datefmt="%H:%M:%S",
    )

    # Handler fichier
    file_handler = logging.FileHandler(
        filename=log_path / log_file,
        encoding="utf-8",
        mode="a",
    )
    file_handler.setLevel(level)
    file_handler.setFormatter(file_formatter)
    logger.addHandler(file_handler)

    # Handler console (stdout)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)

    return logger
