"""
Exécuteur global de la suite de tests unitaires et d'intégration du Trading Bot.
Usage : python run_tests.py
"""

import sys
import unittest
from datetime import datetime


def run_all_tests():
    print("=" * 75)
    print("  SUITE DE TESTS QUALITÉ & SÉCURITÉ - TRADING BOT CAPITAL.COM (XAU/USD)  ")
    print(f"  Horodatage : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 75)

    loader = unittest.TestLoader()
    suite = loader.discover(start_dir="tests", pattern="test_*.py")

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    print("\n" + "=" * 75)
    print(f"  RÉSULTATS DE LA SUITE DE TESTS :")
    print(f"  - Tests exécutés   : {result.testsRun}")
    print(f"  - Succès           : {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"  - Échecs (Failures): {len(result.failures)}")
    print(f"  - Erreurs (Errors) : {len(result.errors)}")
    print("=" * 75)

    if result.wasSuccessful():
        print("  >>> TOUS LES TESTS SONT AU VERT ! LE BOT EST 100% OPÉRATIONNEL. <<<")
        print("=" * 75 + "\n")
        return 0
    else:
        print("  >>> DES ANOMALIES ONT ÉTÉ DÉTECTÉES DANS LES TESTS. <<<")
        print("=" * 75 + "\n")
        return 1


if __name__ == "__main__":
    exit_code = run_all_tests()
    sys.exit(exit_code)
