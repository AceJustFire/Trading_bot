# Gold Trader Pro - Application Interactive & Bot Autonome Capital.com

Application interactive de trading algorithmique dédiée à l'or (**XAU/USD**, symbole `GOLD`), connectée directement à l'API officielle de **Capital.com** (Compte Démo #330847176266952990).

---

## 1. Fonctionnalités & Innovations de l'Application

### A. Interface Visuelle Interactive (S'ouvre automatiquement)
* **Tableau de bord financier haute fidélité** : S'ouvre directement dans votre navigateur comme une application de bureau (`http://127.0.0.1:5000`).
* **Cotation en temps réel de l'Or** : Affichage instantané du Bid, Ask, Spread en USD, et statut du marché.
* **Télémétrie technique en direct** : Moyennes mobiles EMA 50 et EMA 200, jauge de momentum RSI 14, volatilité ATR 14.
* **Tableau des positions ouvertes** : Suivi des gains/pertes latents (PnL) en temps réel, niveaux de SL/TP, et bouton de clôture unitaire.
* **Console d'événements en direct** : Historique des signaux, des ordres et des requêtes réseau.

### B. Prise de Position Active & Fin des "Attentes" Passives
* **Boutons 1-Click "ACHETER (LONG)" et "VENDRE (SHORT)"** : 
  * Ouvrez une position à n'importe quel moment en un seul clic.
  * Le Stop Loss et Take Profit dynamiques (basés sur l'ATR actuel) sont automatiquement attachés à l'ordre.
* **Gestion Dynamique du Risque & Effet de Levier en Direct** :
  * **Choix de l'Effet de Levier (jusqu'à 20:1)** : Slider interactif et boutons rapides (1:1 Cash, 5:1, 10:1, 20:1 Max ESMA) adaptant la marge requise et la capacité d'exposition maximale.
  * **Pourcentage de Capital par Trade** : Slider précis de 0.5% à 10.0% pour calibrer exactement la perte maximale tolérée sur le Stop Loss (ex: 1% de 1 000 $ = 10 $ risqués).
  * **Simulation en Temps Réel** : Affichage instantané du montant en dollars risqué, de la marge requise par lot et du dimensionnement estimé en lots.
* **Mode Actif / Scalping (Activé par défaut)** :
  * Ne reste plus passif à attendre des croisements rares.
  * Détecte les flux directionnels et les accélérations de momentum sur les bougies M1, M5 ou M15 pour entrer régulièrement sur les mouvements du marché.
* **Sélecteur de Timeframe en direct** : Basculez entre M1, M5, M15 et H1 sans redémarrer le bot.
* **Bouton d'Arrêt d'Urgence** : "🛑 Clôturer Toutes les Positions" en 1 clic.

---

## 2. Lancement Rapide

Dans votre terminal PowerShell :

```powershell
cd c:\Users\tomro\Documents\Trading
python main.py
```

L'application :
1. Se connecte automatiquement à votre compte Capital.com.
2. Démarre la surveillance active du cours de l'or.
3. **Ouvre automatiquement l'interface graphique** dans votre navigateur à l'adresse `http://127.0.0.1:5000`.

Pour quitter à tout moment, appuyez sur `Ctrl + C` dans votre terminal.

---

## 3. Cerveau d'Intelligence Multi-Factoriel (Les 5 Piliers d'Analyse)

Le bot intègre désormais un onglet dédié **"INTELLIGENCE & PRÉDICTIONS EN DIRECT"** décortiquant en temps réel l'ensemble des catalyseurs fondamentaux, techniques et institutionnels :

1. **🏛️ Macroéconomie & Taux Réels** : Rendement des obligations US 10 ans (`^TNX`), Dollar Index DXY (`DX-Y.NYB`, corrélation inverse), taux réels (US 10Y - TIPS), anticipations de politique monétaire de la Fed.
2. **🌍 Géopolitique & Sentiment de Risque** : Indice de volatilité VIX (`^VIX`, régime Risk-On vs Risk-Off), valeur refuge (Safe Haven), tensions internationales et dédollarisation BRICS.
3. **🏦 Flux Institutionnels & Physique** : Achats records continus des banques centrales (PBOC Chine, Turquie, etc.), flux de l'ETF SPDR Gold Shares (`GLD`), saisonnalité physique (mariages en Inde / Diwali, Nouvel An lunaire chinois), et coût de maintien minier AISC.
4. **📊 Price Action & Smart Money Concepts (SMC)** : Détection des figures de chandeliers clés (Marteau / Pin Bar haussière, Étoile Filante, Doji d'indécision, Marubozu, Avalement), Fair Value Gaps (FVG haussiers/baissiers), seuils psychologiques ($50 / $100), PDH/PDL (veille) et divergences RSI 14.
5. **⏱️ Microstructure & Timing de Session** : Détection des sessions (Asie, Londres, Overlap Londres/New York avec pic de volatilité journalière), proximité des Fixings LBMA à Londres (10h30 et 15h00 GMT), et filtre de sécurité lors du rollover interbancaire (23h-00h Paris).

### Console d'Explicabilité "Pourquoi cette décision ?" :
* Synthèse textuelle claire du raisonnement pour chaque décision prise ou différée.
* Colonnes dynamiques listant les catalyseurs positifs (acheteurs) et les risques / vents contraires (vendeurs).
* Cibles de cours prédictives chiffrées : Target 1, Target 2, Invalidation, et prochain chiffre rond d'attraction.

---

### Origine et Sources des Données en Temps Réel (Pipeline de Données)

Au lieu de dépendre d'un simple site de presse ou d'actualité textuel (dont la lecture par scraping serait lente, imprécise et subjective), les algorithmes de trading institutionnels s'appuient sur des **flux de cotation bruts et des indicateurs de marché officiels**. 

Voici comment et où le bot puise chacune de ses informations en direct :

| Catégorie d'Information | Données Extraites | Source & Protocole d'Ingestion | Explication & Rôle |
| :--- | :--- | :--- | :--- |
| **Cours Spot XAU/USD & Carnet** | Prix Bid, Ask, Spread, Bougies OHLCV | **API REST officielle de Capital.com** (`/api/v1/prices/GOLD` & `/api/v1/markets/GOLD`) | Flux direct interbancaire avec rafraîchissement continu toutes les 1.5 secondes. |
| **Taux d'Intérêt US & Taux Réels** | Rendement US 10 Ans (`^TNX`), Taux réels (10Y - TIPS) | **Flux de Marché Yahoo Finance API** (`%5ETNX`) | Rendement des emprunts d'État américains à 10 ans. Si les rendements montent, le coût d'opportunité de l'or augmente. |
| **Dollar Index (DXY)** | Indice ICE du Dollar américain (`DX-Y.NYB`) | **Flux de Marché Yahoo Finance API** (`DX-Y.NYB`) | Mesure la force du dollar contre un panier de devises mondiales. Corrélation inverse historique avec l'or. |
| **Volatilité & Sentiment de Risque** | Indice CBOE VIX (`^VIX`) | **Flux de Marché Yahoo Finance API** (`%5EVIX`) | Mesure le sentiment *Risk-On* (VIX ≤ 14) vs *Risk-Off* (VIX ≥ 20, recherche de la valeur refuge de l'or). |
| **Flux Institutionnels (ETF)** | SPDR Gold Shares (`GLD`) | **Flux de Marché Yahoo Finance API** (`GLD`) | Le plus grand ETF d'or physique au monde. Reflète les achats/ventes réels des fonds institutionnels. |
| **Achats des Banques Centrales** | Réserves PBOC (Chine), Turquie, Pologne | **Modèle quantitatif de soutien structurel** (données officielles du World Gold Council - WGC) | Crée un plancher de soutien durable sous le cours grâce aux achats physiques records des banques centrales. |
| **Saisonnalité Physique** | Demande joaillerie & industrie | **Algorithme calendaire physique mondial** | Détecte les périodes de forte demande physique (Diwali & mariages en Inde en automne, Nouvel An lunaire chinois). |
| **Price Action & Smart Money (SMC)** | Chandeliers clés, FVG, PDH/PDL, Chiffres ronds | **Moteur mathématique local vectorisé** ([src/gold_intelligence.py](file:///c:/Users/tomro/Documents/Trading/src/gold_intelligence.py)) | Calculé en direct sur le flux de bougies Capital.com (détection des Pin Bars, Marteaux, déséquilibres FVG à 3 bougies, et seuils psychologiques à 50$/100$). |
| **Microstructure & Fixings** | Sessions (Londres, NY), Fixings LBMA | **Horloge mondiale synchronisée UTC (GMT)** | Identifie en temps réel les sessions ouvertes, l'Overlap Londres/NY (pic de volatilité), et les Fixings officiels de la LBMA à 10h30 et 15h00 GMT. |

#### Robustesse & Cache Asynchrone :
* Les appels de marché externes sont exécutés dans un **thread d'arrière-plan dédié** avec un **cache mémoire de 60 à 120 secondes**.
* Ainsi, le cycle de trading local sur Capital.com n'est **jamais ralenti** (< 3 ms) et fonctionne en permanence même en cas de latence sur un flux externe.

---

## 4. Suite de Tests Automatisée (36 Tests - 100% Succès)

Un ensemble complet de **36 tests unitaires et d'intégration** couvre l'intégralité du pipeline logique, des calculs financiers et du moteur d'intelligence :

```powershell
python run_tests.py
```

### Couverture des tests :
* **[tests/test_gold_intelligence.py](file:///c:/Users/tomro/Documents/Trading/tests/test_gold_intelligence.py)** : Détection des figures de chandeliers (Pin Bar, Marteau, Étoile filante, Doji), détection des Fair Value Gaps (FVG), calcul des seuils psychologiques ($50/$100), microstructure de session et rapport de synthèse.
* **[tests/test_config.py](file:///c:/Users/tomro/Documents/Trading/tests/test_config.py)** : Chargement et validation stricte du `.env`, valeurs par défaut, vérification de l'identifiant.
* **[tests/test_market_data.py](file:///c:/Users/tomro/Documents/Trading/tests/test_market_data.py)** : Calcul du Mid-Price, RSI 14 (Wilder avec protection division par zéro), ATR 14.
* **[tests/test_strategy.py](file:///c:/Users/tomro/Documents/Trading/tests/test_strategy.py)** : Ordres 1-Click BUY/SELL, respect de la distance minimale Guaranteed Stop Loss, modes actif et conservateur avec intelligence intégrée.
* **[tests/test_risk_manager.py](file:///c:/Users/tomro/Documents/Trading/tests/test_risk_manager.py)** : Coupe-circuit Daily Drawdown (3%), filtre de spread, plafond de positions, incohérence SL/Ask/Bid, dimensionnement quantitatif à 1% du capital.
* **[tests/test_execution.py](file:///c:/Users/tomro/Documents/Trading/tests/test_execution.py)** : Payload obligatoire `guaranteedStop: True`, extraction `market.epic`, confirmation asynchrone des ordres, clôture de deal.
* **[tests/test_api.py](file:///c:/Users/tomro/Documents/Trading/tests/test_api.py)** : Endpoints Flask `/api/status`, `/api/intelligence`, `/api/trade`, `/api/toggle-auto`, `/api/set-mode`, `/api/close-all`.

---

## 5. Architecture des Modules

* **[src/gold_intelligence.py](file:///c:/Users/tomro/Documents/Trading/src/gold_intelligence.py)** : Moteur multi-factoriel (5 piliers, SMC, chandeliers, macro, sessions, explicabilité).
* **[src/config.py](file:///c:/Users/tomro/Documents/Trading/src/config.py)** : Configuration typée et paramètres de trading.
* **[src/auth.py](file:///c:/Users/tomro/Documents/Trading/src/auth.py)** : Gestion des jetons CST / X-SECURITY-TOKEN et reconnexion automatique 401.
* **[src/market_data.py](file:///c:/Users/tomro/Documents/Trading/src/market_data.py)** : Ingestion des cours de l'or, calcul vectorisé d'indicateurs (EMA, RSI, ATR).
* **[src/strategy.py](file:///c:/Users/tomro/Documents/Trading/src/strategy.py)** : Moteur de décision connecté aux prédictions des 5 piliers.
* **[src/risk_manager.py](file:///c:/Users/tomro/Documents/Trading/src/risk_manager.py)** : Dimensionnement du risque, filtres de sécurité, coupe-circuit journalier.
* **[src/execution.py](file:///c:/Users/tomro/Documents/Trading/src/execution.py)** : Transmission d'ordres, suivi des positions, clôtures d'urgence.
* **[src/bot_service.py](file:///c:/Users/tomro/Documents/Trading/src/bot_service.py)** : Orchestration asynchrone, thread de fond, synchronisation d'état et d'intelligence.
* **[app.py](file:///c:/Users/tomro/Documents/Trading/app.py)** : Serveur d'interface et API REST (`/api/status`, `/api/intelligence`).
* **[main.py](file:///c:/Users/tomro/Documents/Trading/main.py)** : Point d'entrée avec ouverture automatique du navigateur.


