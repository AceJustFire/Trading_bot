/**
 * TRADING — XAU/USD Terminal Client.
 * Orchestre la séquence de démarrage cinématique Steam Deck,
 * le flux de données en direct, les ordres 1-Click haute précision,
 * et le tableau de bord d'Intelligence Multi-Factorielle (5 Piliers) en temps réel.
 */

let lastLogCount = 0;

document.addEventListener("DOMContentLoaded", () => {
    // 1. Séquence de démarrage cinématique Steam Deck
    initSteamDeckBootSequence();

    // 2. Initialisation des écouteurs d'événements & Onglets
    initEventListeners();
    initTabNavigation();

    // 3. Boucle de rafraîchissement des données (Polling 1.5s)
    fetchStatus();
    setInterval(fetchStatus, 1500);
});

/**
 * Séquence de démarrage cinématique inspirée du Steam Deck
 * Joue une douce tonalité harmonique (Web Audio) et effectue un fondu lent vers le terminal.
 */
function initSteamDeckBootSequence() {
    const bootScreen = document.getElementById("bootScreen");
    const appWrapper = document.getElementById("appWrapper");

    try {
        const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
        const osc = audioCtx.createOscillator();
        const gain = audioCtx.createGain();

        osc.type = "sine";
        osc.frequency.setValueAtTime(220, audioCtx.currentTime);
        osc.frequency.exponentialRampToValueAtTime(440, audioCtx.currentTime + 0.6);
        osc.frequency.exponentialRampToValueAtTime(880, audioCtx.currentTime + 1.2);

        gain.gain.setValueAtTime(0.001, audioCtx.currentTime);
        gain.gain.linearRampToValueAtTime(0.08, audioCtx.currentTime + 0.4);
        gain.gain.exponentialRampToValueAtTime(0.0001, audioCtx.currentTime + 2.2);

        osc.connect(gain);
        gain.connect(audioCtx.destination);
        osc.start();
        osc.stop(audioCtx.currentTime + 2.3);
    } catch (e) {
        // Audio facultatif si bloqué par les politiques de navigateur
    }

    setTimeout(() => {
        if (bootScreen) bootScreen.classList.add("fade-out");
        if (appWrapper) appWrapper.classList.add("loaded");
    }, 2400);
}

/**
 * Gestion du basculement d'onglets (Cockpit vs Intelligence & Prédictions)
 */
function initTabNavigation() {
    const tabBtns = document.querySelectorAll(".nav-tab-btn");
    const paneCockpit = document.getElementById("paneCockpit");
    const paneIntel = document.getElementById("paneIntelligence");

    tabBtns.forEach(btn => {
        btn.addEventListener("click", () => {
            tabBtns.forEach(b => b.classList.remove("active"));
            btn.classList.add("active");

            const targetTab = btn.dataset.tab;
            if (targetTab === "cockpit") {
                paneCockpit.style.display = "block";
                paneCockpit.classList.add("active");
                paneIntel.style.display = "none";
                paneIntel.classList.remove("active");
            } else if (targetTab === "intelligence") {
                paneCockpit.style.display = "none";
                paneCockpit.classList.remove("active");
                paneIntel.style.display = "block";
                paneIntel.classList.add("active");
            }
        });
    });
}

function initEventListeners() {
    // Ordres manuels 1-Click
    document.getElementById("btnBuyManual").addEventListener("click", () => executeOrder("BUY"));
    document.getElementById("btnSellManual").addEventListener("click", () => executeOrder("SELL"));

    // Clôture d'urgence
    document.getElementById("btnCloseAll").addEventListener("click", closeAllPositions);

    // Rafraîchissement manuel des positions
    document.getElementById("btnRefreshPositions").addEventListener("click", fetchStatus);

    // Bascule du trading autonome
    const autoToggle = document.getElementById("autoTradingToggle");
    autoToggle.addEventListener("change", async () => {
        try {
            const res = await fetch("/api/toggle-auto", { method: "POST" });
            const data = await res.json();
            showToast(`Système Autonome : ${data.is_auto_trading ? "ENGAGÉ" : "EN PAUSE"}`);
        } catch (e) {
            console.error(e);
        }
    });

    // Sélecteur de mode de stratégie
    const modeButtons = document.querySelectorAll("#strategyModeGroup .seg-btn");
    modeButtons.forEach(btn => {
        btn.addEventListener("click", async () => {
            modeButtons.forEach(b => b.classList.remove("active"));
            btn.classList.add("active");
            const mode = btn.dataset.mode;
            await fetch("/api/set-mode", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ mode })
            });
            showToast(`Mode Stratégie : ${mode === "active" ? "ACTIF (SCALPING)" : "CONSERVATEUR"}`);
        });
    });

    // Sélecteur de timeframe
    const tfButtons = document.querySelectorAll("#timeframeGroup .seg-btn");
    tfButtons.forEach(btn => {
        btn.addEventListener("click", async () => {
            tfButtons.forEach(b => b.classList.remove("active"));
            btn.classList.add("active");
            const timeframe = btn.dataset.tf;
            await fetch("/api/set-timeframe", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ timeframe })
            });
            showToast(`Périodicité active : ${timeframe}`);
        });
    });

    // 4. Contrôle d'effet de levier (Slider & Raccourcis)
    const levSlider = document.getElementById("leverageSlider");
    const levBadge = document.getElementById("leverageValueBadge");
    const levQuickBtns = document.querySelectorAll("#leverageQuickGroup .btn-micro");

    if (levSlider) {
        levSlider.addEventListener("input", (e) => {
            isUserInteractingWithRisk = true;
            currentLeverage = parseInt(e.target.value, 10);
            if (levBadge) levBadge.textContent = `${currentLeverage}:1`;
            levQuickBtns.forEach(b => {
                b.classList.toggle("active", parseInt(b.dataset.lev, 10) === currentLeverage);
            });
            updateRiskTelemetry();
        });

        levSlider.addEventListener("change", async (e) => {
            isUserInteractingWithRisk = false;
            await sendRiskSettings({ leverage: currentLeverage });
        });
    }

    levQuickBtns.forEach(btn => {
        btn.addEventListener("click", async () => {
            const lev = parseInt(btn.dataset.lev, 10);
            currentLeverage = lev;
            if (levSlider) levSlider.value = lev;
            if (levBadge) levBadge.textContent = `${lev}:1`;
            levQuickBtns.forEach(b => b.classList.remove("active"));
            btn.classList.add("active");
            updateRiskTelemetry();
            await sendRiskSettings({ leverage: currentLeverage });
        });
    });

    // 5. Contrôle du % de capital risqué (Slider & Raccourcis)
    const capSlider = document.getElementById("capitalRiskSlider");
    const capBadge = document.getElementById("capitalRiskBadge");
    const capQuickBtns = document.querySelectorAll("#capitalQuickGroup .btn-micro");

    if (capSlider) {
        capSlider.addEventListener("input", (e) => {
            isUserInteractingWithRisk = true;
            currentCapitalRisk = parseFloat(e.target.value);
            if (capBadge) capBadge.textContent = `${currentCapitalRisk.toFixed(1)} %`;
            capQuickBtns.forEach(b => {
                b.classList.toggle("active", parseFloat(b.dataset.cap) === currentCapitalRisk);
            });
            updateRiskTelemetry();
        });

        capSlider.addEventListener("change", async (e) => {
            isUserInteractingWithRisk = false;
            await sendRiskSettings({ capital_percent: currentCapitalRisk });
        });
    }

    capQuickBtns.forEach(btn => {
        btn.addEventListener("click", async () => {
            const cap = parseFloat(btn.dataset.cap);
            currentCapitalRisk = cap;
            if (capSlider) capSlider.value = cap;
            if (capBadge) capBadge.textContent = `${cap.toFixed(1)} %`;
            capQuickBtns.forEach(b => b.classList.remove("active"));
            btn.classList.add("active");
            updateRiskTelemetry();
            await sendRiskSettings({ capital_percent: currentCapitalRisk });
        });
    });
}

let currentLeverage = 20;
let currentCapitalRisk = 1.0;
let isUserInteractingWithRisk = false;
let lastKnownState = null;

async function sendRiskSettings(payload) {
    try {
        const res = await fetch("/api/set-risk", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
        });
        const data = await res.json();
        if (data.success && data.risk_settings) {
            showToast(`Paramètres : Levier ${data.risk_settings.leverage}:1 | Risque ${data.risk_settings.capital_risk_percent}%`);
        }
    } catch (e) {
        console.error("Erreur sendRiskSettings :", e);
    }
}

function updateRiskTelemetry() {
    const equity = (lastKnownState && lastKnownState.financials) ? lastKnownState.financials.equity : 1000.0;
    const askPrice = (lastKnownState && lastKnownState.snapshot) ? lastKnownState.snapshot.ask : 4160.0;
    const atr = (lastKnownState && lastKnownState.indicators && lastKnownState.indicators.atr) ? lastKnownState.indicators.atr : 7.0;

    const riskAmount = (equity * currentCapitalRisk) / 100.0;
    const marginPerLot = askPrice / currentLeverage;
    const slDistance = atr * 1.5;
    const rawSize = slDistance > 0 ? (riskAmount / slDistance) : 0.1;
    const estSize = Math.max(0.1, Math.round(rawSize * 100) / 100);

    const riskEl = document.getElementById("liveRiskAmount");
    if (riskEl) riskEl.textContent = `~${riskAmount.toFixed(2)} USD`;

    const marginEl = document.getElementById("liveMarginPerLot");
    if (marginEl) marginEl.textContent = `~${marginPerLot.toFixed(2)} $`;

    const sizeEl = document.getElementById("liveEstimatedSize");
    if (sizeEl) sizeEl.textContent = `~${estSize.toFixed(2)} lot(s)`;
}

async function fetchStatus() {
    const connPill = document.getElementById("connPill");
    const connText = document.getElementById("connStatusText");

    try {
        const response = await fetch("/api/status");
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const state = await response.json();

        if (connPill && connText) {
            connPill.classList.remove("feed-disconnected");
            connText.textContent = "FLUX DIRECT CONNECTÉ";
        }

        updateUI(state);
    } catch (err) {
        console.debug("Erreur polling :", err);
        if (connPill && connText) {
            connPill.classList.add("feed-disconnected");
            connText.textContent = "RECONNEXION DU FLUX...";
        }
    }
}

function updateUI(state) {
    lastKnownState = state;

    // Synchronisation des paramètres de levier et de capital depuis le backend
    if (state.risk_settings && !isUserInteractingWithRisk) {
        const r = state.risk_settings;
        if (r.leverage !== undefined && r.leverage !== currentLeverage) {
            currentLeverage = r.leverage;
            const levSlider = document.getElementById("leverageSlider");
            const levBadge = document.getElementById("leverageValueBadge");
            if (levSlider) levSlider.value = currentLeverage;
            if (levBadge) levBadge.textContent = `${currentLeverage}:1`;
            document.querySelectorAll("#leverageQuickGroup .btn-micro").forEach(b => {
                b.classList.toggle("active", parseInt(b.dataset.lev, 10) === currentLeverage);
            });
        }
        if (r.capital_risk_percent !== undefined && r.capital_risk_percent !== currentCapitalRisk) {
            currentCapitalRisk = r.capital_risk_percent;
            const capSlider = document.getElementById("capitalRiskSlider");
            const capBadge = document.getElementById("capitalRiskBadge");
            if (capSlider) capSlider.value = currentCapitalRisk;
            if (capBadge) capBadge.textContent = `${currentCapitalRisk.toFixed(1)} %`;
            document.querySelectorAll("#capitalQuickGroup .btn-micro").forEach(b => {
                b.classList.toggle("active", parseFloat(b.dataset.cap) === currentCapitalRisk);
            });
        }
    }
    updateRiskTelemetry();

    // 1. Finances du compte
    if (state.financials) {
        document.getElementById("accountEquity").textContent = `${state.financials.equity.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} ${state.financials.currency}`;
        document.getElementById("accountId").textContent = `#${state.financials.account_id}`;
    }

    // 2. Cotation Or
    if (state.snapshot) {
        const snap = state.snapshot;
        const askStr = snap.ask.toFixed(2);
        const bidStr = snap.bid.toFixed(2);

        document.getElementById("liveAsk").textContent = askStr;
        document.getElementById("liveAskSub").textContent = askStr;
        document.getElementById("liveBid").textContent = bidStr;

        const spreadEl = document.getElementById("liveSpread");
        spreadEl.textContent = `${snap.spread.toFixed(3)} $`;
        spreadEl.className = `metric-val font-mono ${snap.spread <= 0.60 ? "text-cyan" : "text-danger"}`;

        const statusEl = document.getElementById("liveMarketStatus");
        statusEl.textContent = snap.is_tradeable ? "TRADEABLE" : snap.market_status;
        statusEl.className = `market-status-pill font-mono ${snap.is_tradeable ? "status-open" : "text-danger"}`;

        document.getElementById("buyPriceSub").textContent = `${askStr} $`;
        document.getElementById("sellPriceSub").textContent = `${bidStr} $`;
    }

    // 3. Indicateurs Quantitatifs
    if (state.indicators && state.indicators.close) {
        const ind = state.indicators;
        document.getElementById("emaFastSlow").textContent = `${ind.ema_fast.toFixed(2)} / ${ind.ema_slow.toFixed(2)}`;

        const trendEl = document.getElementById("trendBadge");
        const isBull = ind.ema_fast >= ind.ema_slow;
        trendEl.textContent = isBull ? "HAUSSIÈRE" : "BAISSIÈRE";
        trendEl.className = `state-badge ${isBull ? "trend-bull" : "trend-bear"}`;

        document.getElementById("rsiValue").textContent = ind.rsi.toFixed(1);
        const rsiVal = Math.min(100, Math.max(0, ind.rsi));
        const rsiFill = document.getElementById("rsiFill");
        rsiFill.style.width = `${rsiVal}%`;
        if (rsiVal >= 70) {
            rsiFill.style.background = "linear-gradient(90deg, #f59e0b, #ef4444)";
        } else if (rsiVal <= 30) {
            rsiFill.style.background = "linear-gradient(90deg, #06b6d4, #3b82f6)";
        } else {
            rsiFill.style.background = "linear-gradient(90deg, var(--gold-primary), var(--gold-light))";
        }

        document.getElementById("atrValue").textContent = `${ind.atr.toFixed(2)} $`;
        const slEst = (ind.atr * 1.5).toFixed(1);
        const tpEst = (ind.atr * 3.0).toFixed(1);
        document.getElementById("atrDetails").textContent = `SL ~${slEst}$ | TP ~${tpEst}$`;
    }

    // 4. Directive Signal Algorithmique
    if (state.signal) {
        const sig = state.signal;
        const tagEl = document.getElementById("signalTag");
        let displayAction = "EN ATTENTE";
        if (sig.action === "BUY") displayAction = "ACHAT";
        if (sig.action === "SELL") displayAction = "VENTE";

        tagEl.textContent = displayAction;
        tagEl.className = `signal-badge sig-${sig.action.toLowerCase()}`;
        document.getElementById("signalReason").textContent = sig.reason;
    }

    // 5. Mise à jour de l'onglet d'Intelligence & Prédictions en Direct
    if (state.intelligence) {
        updateIntelligenceUI(state.intelligence, state);
    }

    // 6. Positions en direct
    updatePositionsTable(state.positions || []);

    // 7. Journal d'audit
    updateTerminalLogs(state.logs || []);

    // 8. Statut du switch autonome
    const autoToggle = document.getElementById("autoTradingToggle");
    if (autoToggle.checked !== state.is_auto_trading) {
        autoToggle.checked = state.is_auto_trading;
    }
}

/**
 * Règle la largeur en % et la couleur dynamique d'une jauge de pilier
 */
function setPillarGauge(barId, score) {
    const bar = document.getElementById(barId);
    if (!bar) return;
    const clampedPct = Math.max(10, Math.min(100, 50 + score / 2));
    bar.style.width = `${clampedPct}%`;
    bar.classList.remove("score-pos", "score-neg", "score-neu");
    if (score >= 20) {
        bar.classList.add("score-pos");
    } else if (score <= -20) {
        bar.classList.add("score-neg");
    } else {
        bar.classList.add("score-neu");
    }
}

/**
 * Met à jour l'ensemble des données du tableau de bord d'Intelligence & Prédictions
 */
function updateIntelligenceUI(intel, state) {
    if (!intel) return;

    // Horodatage
    if (intel.timestamp) {
        document.getElementById("intelTimestamp").textContent = `ACTUALISÉ À ${intel.timestamp}`;
    }

    // Biais Composite Global
    const biasEl = document.getElementById("intelCompositeBias");
    biasEl.textContent = intel.composite_bias || "NEUTRE";
    if (intel.composite_bias && intel.composite_bias.includes("HAUSSIER")) {
        biasEl.className = "bias-badge-lg font-mono bias-bull";
    } else if (intel.composite_bias && intel.composite_bias.includes("BAISSIER")) {
        biasEl.className = "bias-badge-lg font-mono bias-bear";
    } else {
        biasEl.className = "bias-badge-lg font-mono bias-neutral";
    }

    // Indice de confiance & Probabilités
    document.getElementById("intelConfidence").textContent = `${intel.confidence_percent || 50}%`;
    const bullP = intel.bullish_probability || 50;
    const bearP = intel.bearish_probability || 50;

    document.getElementById("intelBullProb").textContent = `${bullP}% HAUSSIER`;
    document.getElementById("intelBearProb").textContent = `${bearP}% BAISSIER`;
    document.getElementById("intelBullBar").style.width = `${bullP}%`;
    document.getElementById("intelBearBar").style.width = `${bearP}%`;

    // Cibles prédictives
    if (intel.target_1) document.getElementById("intelTarget1").textContent = `${intel.target_1.toFixed(2)} $`;
    if (intel.target_2) document.getElementById("intelTarget2").textContent = `${intel.target_2.toFixed(2)} $`;
    if (intel.invalidation_level) document.getElementById("intelInvalidation").textContent = `${intel.invalidation_level.toFixed(2)} $`;
    if (intel.nearest_round_level) document.getElementById("intelNearestRound").textContent = `${intel.nearest_round_level.toFixed(2)} $`;

    if (intel.smc_data && intel.smc_data.distance_to_round_level !== undefined) {
        document.getElementById("intelRoundDist").textContent = `Distance : ~${intel.smc_data.distance_to_round_level.toFixed(2)} $ (${intel.smc_data.round_level_type})`;
    }

    // Explicabilité Décisionnelle
    if (intel.decision_summary) {
        document.getElementById("intelDecisionSummary").textContent = intel.decision_summary;
    }

    // Catalyseurs Positifs
    const posUl = document.getElementById("positiveCatalystsList");
    if (intel.positive_catalysts && intel.positive_catalysts.length > 0) {
        posUl.innerHTML = intel.positive_catalysts.map(c => `<li>${c}</li>`).join("");
    } else {
        posUl.innerHTML = "<li>Aucun catalyseur haussier dominant à cet instant.</li>";
    }

    // Catalyseurs Négatifs
    const negUl = document.getElementById("negativeCatalystsList");
    if (intel.negative_catalysts && intel.negative_catalysts.length > 0) {
        negUl.innerHTML = intel.negative_catalysts.map(c => `<li>${c}</li>`).join("");
    } else {
        negUl.innerHTML = "<li>Aucun risque de liquidité ou obstacle majeur détecté.</li>";
    }

    // Pilier 1 : Macro & Monétaire
    const mScore = intel.macro_score !== undefined ? intel.macro_score : 20;
    document.getElementById("pillarMacroScore").textContent = `${mScore >= 0 ? "+" : ""}${mScore} / 100`;
    setPillarGauge("pillarMacroBar", mScore);
    if (intel.macro_data) {
        const tnx = intel.macro_data.us_10y_yield;
        const realRate = intel.macro_data.real_rate_proxy;
        document.getElementById("intelTNX").textContent = `${tnx.toFixed(2)} %`;
        document.getElementById("intelDXY").textContent = `${intel.macro_data.dxy_price.toFixed(2)}`;
        document.getElementById("intelRealRate").textContent = `${realRate.toFixed(2)} %`;

        const fedEl = document.getElementById("intelFedPolicy");
        if (fedEl) {
            if (realRate < 1.85 || tnx < 4.20) {
                fedEl.textContent = "Anticipation Baisse des Taux (Dovish / Bullish)";
            } else if (realRate > 2.25 || tnx > 4.50) {
                fedEl.textContent = "Taux Élevés Prolongés (Hawkish / Risque Pression)";
            } else {
                fedEl.textContent = "Maintien des Taux (Équilibré)";
            }
        }
    }

    // Pilier 2 : Géopolitique & VIX
    const gScore = intel.geopolitics_score !== undefined ? intel.geopolitics_score : 30;
    document.getElementById("pillarGeopoliticsScore").textContent = `${gScore >= 0 ? "+" : ""}${gScore} / 100`;
    setPillarGauge("pillarGeopoliticsBar", gScore);
    if (intel.macro_data) {
        const vix = intel.macro_data.vix_index;
        const vixRegime = vix >= 20 ? "Risk-Off (Panique)" : (vix <= 14 ? "Risk-On (Serein)" : "Neutre / Équilibré");
        document.getElementById("intelVIX").textContent = `${vix.toFixed(2)} (${vixRegime})`;

        const safeHavenEl = document.getElementById("intelSafeHaven");
        if (safeHavenEl) {
            if (vix >= 22) {
                safeHavenEl.textContent = "Forte Demande Refuge (Volatilité Élevée)";
            } else if (vix >= 16) {
                safeHavenEl.textContent = "Actif & Plébiscité (Soutien Régulier)";
            } else {
                safeHavenEl.textContent = "Climat Détendu (Flux d'Arbitrage)";
            }
        }

        const bricsEl = document.getElementById("intelBrics");
        if (bricsEl) {
            bricsEl.textContent = gScore >= 35 
                ? "Accélération Dé-dollarisation (Achats Hors USD)" 
                : "Flux Physiques Réguliers (Asie & Moyen-Orient)";
        }

        const bankingEl = document.getElementById("intelBanking");
        if (bankingEl) {
            bankingEl.textContent = gScore >= 40 
                ? "Inquiétudes Dettes Souveraines (Pression Haussière)" 
                : "Surveillance Risques Systémiques (Normal)";
        }
    }

    // Pilier 3 : Flux Institutionnels
    const iScore = intel.institutional_score !== undefined ? intel.institutional_score : 35;
    document.getElementById("pillarInstScore").textContent = `${iScore >= 0 ? "+" : ""}${iScore} / 100`;
    setPillarGauge("pillarInstBar", iScore);
    if (intel.macro_data) {
        document.getElementById("intelGLD").textContent = `${intel.macro_data.gld_price.toFixed(2)} $ (GLD Shares)`;
    }
    if (intel.session_data && intel.session_data.season_desc) {
        document.getElementById("intelSeasonality").textContent = intel.session_data.season_desc.split(":")[0];
    }
    const cbEl = document.getElementById("intelCentralBanks");
    if (cbEl) {
        cbEl.textContent = iScore >= 50 
            ? "Achats Continus Records (PBOC, RBI, BCT)" 
            : "Accumulation Stratégique Modérée";
    }
    const aiscEl = document.getElementById("intelAISC");
    if (aiscEl) {
        const spotPrice = (state && state.snapshot && state.snapshot.ask) ? state.snapshot.ask : 4154.80;
        const margin = Math.max(0, spotPrice - 1420);
        aiscEl.textContent = `~1 420 $ / oz (Marge nette : +${margin.toFixed(0)} $ / oz)`;
    }

    // Pilier 4 : Price Action & SMC
    const paScore = intel.price_action_score !== undefined ? intel.price_action_score : 15;
    document.getElementById("pillarPAScore").textContent = `${paScore >= 0 ? "+" : ""}${paScore} / 100`;
    setPillarGauge("pillarPABar", paScore);
    if (intel.smc_data) {
        document.getElementById("intelPattern").textContent = intel.smc_data.candlestick_pattern || "Neutre";
        
        if (intel.smc_data.fvg_detected) {
            const fType = intel.smc_data.fvg_type === "BULLISH_FVG" ? "Haussier" : "Baissier";
            document.getElementById("intelFVG").textContent = `${fType} (${intel.smc_data.fvg_zone[0]}$ - ${intel.smc_data.fvg_zone[1]}$)`;
        } else {
            document.getElementById("intelFVG").textContent = "Non détecté";
        }

        document.getElementById("intelPDHPDL").textContent = `${intel.smc_data.pdh.toFixed(2)} $ / ${intel.smc_data.pdl.toFixed(2)} $`;
        
        if (intel.smc_data.rsi_divergence) {
            document.getElementById("intelDivergence").textContent = intel.smc_data.rsi_divergence === "BULLISH_DIVERGENCE" ? "Divergence Haussière Active" : "Divergence Baissière Active";
        } else {
            document.getElementById("intelDivergence").textContent = "Aucune divergence";
        }
    }

    // Pilier 5 : Microstructure & Timing
    const miScore = intel.microstructure_score !== undefined ? intel.microstructure_score : 20;
    document.getElementById("pillarMicroScore").textContent = `${miScore >= 0 ? "+" : ""}${miScore} / 100`;
    setPillarGauge("pillarMicroBar", miScore);
    if (intel.session_data) {
        document.getElementById("intelActiveSession").textContent = intel.session_data.active_session_name || "Londres";
        document.getElementById("intelSessionProfile").textContent = intel.session_data.session_liquidity_profile || "Normale";
        
        if (intel.session_data.is_near_lbma_fixing) {
            document.getElementById("intelLBMA").textContent = `⚠️ PROCHE ${intel.session_data.lbma_fixing_name}`;
        } else {
            document.getElementById("intelLBMA").textContent = "Horaires clés : 10h30 & 15h00 GMT";
        }

        if (intel.session_data.is_rollover_blackout) {
            document.getElementById("intelRolloverStatus").textContent = "⚠️ ROLLOVER EN COURS (23h-00h Paris)";
            document.getElementById("intelRolloverStatus").className = "p-metric-val font-mono text-danger";
        } else {
            document.getElementById("intelRolloverStatus").textContent = "Marché Ouvert (Normal)";
            document.getElementById("intelRolloverStatus").className = "p-metric-val font-mono text-emerald";
        }
    }
}

function updatePositionsTable(positions) {
    const tbody = document.getElementById("positionsTableBody");
    document.getElementById("posCount").textContent = `${positions.length} ACTIVE(S)`;

    if (positions.length === 0) {
        tbody.innerHTML = `
            <tr class="empty-state-row">
                <td colspan="8">
                    <div class="empty-state">
                        <span class="empty-text">Aucune position active en cours. Le moteur est prêt à intervenir dès confirmation de flux.</span>
                    </div>
                </td>
            </tr>
        `;
        return;
    }

    let html = "";
    positions.forEach(p => {
        const isBuy = p.direction === "BUY";
        const uplColor = p.upl >= 0 ? "style='color: #34d399; font-weight: 700;'" : "style='color: #f87171; font-weight: 700;'";

        html += `
            <tr>
                <td>#${p.deal_id}</td>
                <td><span class="pos-tag ${isBuy ? "pos-buy" : "pos-sell"}">${p.direction}</span></td>
                <td>${p.size} lot(s)</td>
                <td>${p.open_level.toFixed(2)} $</td>
                <td>${p.stop_level ? p.stop_level.toFixed(2) + " $" : "-"}</td>
                <td>${p.profit_level ? p.profit_level.toFixed(2) + " $" : "-"}</td>
                <td ${uplColor}>${p.upl >= 0 ? "+" : ""}${p.upl.toFixed(2)} USD</td>
                <td class="text-right">
                    <button class="btn-row-close" onclick="closeSinglePosition('${p.deal_id}')">LIQUIDER</button>
                </td>
            </tr>
        `;
    });
    tbody.innerHTML = html;
}

function updateTerminalLogs(logs) {
    const win = document.getElementById("terminalWindow");
    if (logs.length === lastLogCount) return;
    lastLogCount = logs.length;

    let html = "";
    logs.forEach(l => {
        html += `
            <div class="audit-line">
                <span class="audit-time">[${l.time}]</span>
                <span class="audit-${l.level}">${l.msg}</span>
            </div>
        `;
    });
    win.innerHTML = html;
    win.scrollTop = win.scrollHeight;
}

async function executeOrder(direction) {
    showToast(`Transmission de l'ordre ${direction}...`);
    try {
        const res = await fetch("/api/trade", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ direction })
        });
        const data = await res.json();
        if (data.success) {
            showToast(`CONFIRMATION : Ordre ${direction} exécuté (#${data.deal_id})`);
            fetchStatus();
        } else {
            showToast(`REJET DE RISQUE : ${data.error}`);
        }
    } catch (e) {
        showToast("ERREUR RÉSEAU");
    }
}

async function closeSinglePosition(dealId) {
    showToast(`Liquidation de la position #${dealId}...`);
    try {
        const res = await fetch(`/api/close/${dealId}`, { method: "POST" });
        const data = await res.json();
        if (data.success) {
            showToast(`Position #${dealId} clôturée avec succès.`);
            fetchStatus();
        } else {
            showToast("Échec de liquidation.");
        }
    } catch (e) {
        showToast("ERREUR RÉSEAU");
    }
}

async function closeAllPositions() {
    if (!confirm("CONFIRMATION : Liquider l'intégralité des positions ouvertes immédiatement ?")) return;
    showToast("Liquidation générale en cours...");
    try {
        const res = await fetch("/api/close-all", { method: "POST" });
        const data = await res.json();
        showToast(`${data.closed_count} position(s) liquidée(s).`);
        fetchStatus();
    } catch (e) {
        showToast("ERREUR RÉSEAU");
    }
}

function showToast(message) {
    const container = document.getElementById("toastContainer");
    const toast = document.createElement("div");
    toast.className = "toast-msg font-mono";
    toast.textContent = message;
    container.appendChild(toast);
    setTimeout(() => {
        toast.style.opacity = "0";
        setTimeout(() => toast.remove(), 400);
    }, 3800);
}
