(function () {
    "use strict";

    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    const routes = window.EUREKA_VOICE_ROUTES || {};

    const NAV_KEYWORDS = {
        dashboard: ["dashboard", "home", "inizio", "principale"],
        agenda: ["agenda", "calendario", "appuntamenti", "impegni"],
        clienti: ["clienti", "cliente", "anagrafica clienti"],
        fornitori: ["fornitori", "fornitore", "fornitura"],
        agenti: ["agenti", "agente"],
        articoli: ["articoli", "articolo", "magazzino"],
        fatture: ["fatture", "fattura", "documenti"],
        categorie: ["categorie", "categoria"],
        aziende: ["azienda", "aziende", "ditta", "societa", "società"],
        gruppi_articoli: ["gruppi articoli", "gruppo articoli", "gruppi articolo"],
        operatori: ["operatori", "operatore"],
        timbrature: ["timbrature", "timbratura", "presenze", "presenza"],
        vettori: ["vettori", "vettore", "spedizionieri", "spedizioniere"],
        spedizionieri: ["spedizionieri", "spedizioniere", "vettori", "vettore"],
        parametri_4d: ["parametri 4d", "parametri quattro d", "parametri", "configurazione 4d"],
        parametri4d: ["parametri 4d", "parametri quattro d", "parametri", "configurazione 4d"],
        sistema: ["sistema", "impostazioni", "settings"],
    };

    const NAV_VERBS = [
        "apri",
        "aprire",
        "vai",
        "vai a",
        "vai agli",
        "vai alle",
        "vai ai",
        "vai al",
        "vai alla",
        "mostra",
        "mostrami",
        "visualizza",
        "portami",
        "portami a",
        "portami agli",
        "portami alle",
        "portami ai",
        "portami al",
        "portami alla",
    ];

    const SEARCH_ENTITIES = {
        clienti: ["cliente", "clienti"],
        fornitori: ["fornitore", "fornitori"],
        agenti: ["agente", "agenti"],
        articoli: ["articolo", "articoli"],
        fatture: ["fattura", "fatture"],
        categorie: ["categoria", "categorie"],
        aziende: ["azienda", "aziende", "ditta", "societa", "società"],
        gruppi_articoli: ["gruppo articoli", "gruppi articoli", "gruppo articolo", "gruppi articolo"],
        vettori: ["vettore", "vettori", "spedizioniere", "spedizionieri"],
        spedizionieri: ["spedizioniere", "spedizionieri", "vettore", "vettori"],
    };

    const SEARCH_ACTIVE_ONLY_DESTINATIONS = new Set([
        "clienti",
        "fornitori",
        "articoli",
        "gruppi_articoli",
    ]);

    const PANEL_VISIBLE_STATUSES = new Set([
        "Ascolto...",
        "Elaborazione...",
        "Comando riconosciuto",
    ]);

    const LISTENING_INACTIVITY_MS = 7000;
    const TOAST_DURATION_MS = {
        info: 2800,
        danger: 3800,
        success: 3800,
    };

    let recognition = null;
    let isListening = false;
    let inactivityTimer = null;
    let voiceRoot = null;
    let panelEl = null;
    let statusEl = null;
    let transcriptEl = null;
    let toggleBtn = null;
    let unsupportedEl = null;

    function normalize(text) {
        return (text || "")
            .toLowerCase()
            .normalize("NFD")
            .replace(/[\u0300-\u036f]/g, "")
            .replace(/['']/g, "'")
            .replace(/[^\w\s']/g, " ")
            .replace(/\s+/g, " ")
            .trim();
    }

    function stripLeadingVerbs(text) {
        let result = text;

        NAV_VERBS.forEach(function (verb) {
            if (result.startsWith(verb + " ")) {
                result = result.slice(verb.length + 1);
            } else if (result === verb) {
                result = "";
            }
        });

        return result.trim();
    }

    function matchesKeyword(text, keywords) {
        return keywords.some(function (keyword) {
            return text === keyword || text.startsWith(keyword + " ") || text.endsWith(" " + keyword) || text.includes(" " + keyword + " ");
        });
    }

    function buildSearchUrl(routeKey, query) {
        const base = routes[routeKey];
        if (!base || !query) {
            return null;
        }

        const url = new URL(base, window.location.origin);
        url.searchParams.set("q", query);
        if (SEARCH_ACTIVE_ONLY_DESTINATIONS.has(routeKey)) {
            url.searchParams.set("stato", "attivi");
        }
        return url.pathname + url.search;
    }

    function resolveRoute(routeKey) {
        return routes[routeKey] || routes[routeKey.replace(/_/g, "")] || null;
    }

    function phraseMatches(text, phrase, matchMode) {
        const mode = matchMode || "contains";

        if (mode === "exact") {
            return text === phrase;
        }

        if (mode === "starts_with") {
            return text.startsWith(phrase);
        }

        return text.includes(phrase);
    }

    function extractRemainder(text, phrase, matchMode) {
        const mode = matchMode || "contains";

        if (mode === "exact") {
            return "";
        }

        if (mode === "starts_with") {
            return text.slice(phrase.length).trim();
        }

        const index = text.indexOf(phrase);
        if (index === -1) {
            return "";
        }

        return text.slice(index + phrase.length).trim();
    }

    function parseConfiguredCommand(text) {
        const commands = window.EUREKA_VOICE_COMMANDS || [];

        for (let i = 0; i < commands.length; i += 1) {
            const command = commands[i];
            const phrase = normalize(command.frase || "");
            if (!phrase || !phraseMatches(text, phrase, command.match_mode)) {
                continue;
            }

            const destination = command.destinazione;
            if (command.azione === "navigate") {
                return resolveRoute(destination);
            }

            if (command.azione === "search") {
                const fixedQuery = (command.query || "").trim();
                const dynamicQuery = extractRemainder(text, phrase, command.match_mode);
                const query = fixedQuery || dynamicQuery;
                if (query) {
                    return buildSearchUrl(destination, query);
                }
            }
        }

        return null;
    }

    function parseSearchIntent(text) {
        const searchMatch = text.match(/^cerca(?:re)?(?:\s+(?:il|la|lo|i|gli|le|un|una|l'))?\s*(.+)$/);
        if (!searchMatch) {
            return null;
        }

        const remainder = searchMatch[1].trim();
        if (!remainder) {
            return null;
        }

        for (const [routeKey, labels] of Object.entries(SEARCH_ENTITIES)) {
            for (const label of labels) {
                if (remainder.startsWith(label + " ")) {
                    const query = remainder.slice(label.length + 1).trim();
                    if (query) {
                        return buildSearchUrl(routeKey, query);
                    }
                }
            }
        }

        return null;
    }

    function parseNavigationIntent(text) {
        const stripped = stripLeadingVerbs(text);
        const target = stripped || text;

        for (const [routeKey, keywords] of Object.entries(NAV_KEYWORDS)) {
            if (matchesKeyword(target, keywords) || matchesKeyword(text, keywords)) {
                return resolveRoute(routeKey);
            }
        }

        return null;
    }

    function parseIntent(transcript) {
        const text = normalize(transcript);
        if (!text) {
            return null;
        }

        return parseConfiguredCommand(text) || parseSearchIntent(text) || parseNavigationIntent(text);
    }

    function speak(message) {
        if (!window.speechSynthesis || !message) {
            return;
        }

        window.speechSynthesis.cancel();
        const utterance = new SpeechSynthesisUtterance(message);
        utterance.lang = "it-IT";
        utterance.rate = 1.05;

        const voices = window.speechSynthesis.getVoices();
        const italianVoice = voices.find(function (voice) {
            return voice.lang && voice.lang.toLowerCase().startsWith("it");
        });

        if (italianVoice) {
            utterance.voice = italianVoice;
        }

        window.speechSynthesis.speak(utterance);
    }

    function showToast(message, type) {
        const toastType = type === "danger" ? "danger" : type === "success" ? "success" : "info";
        const toast = document.createElement("div");
        toast.className = "eureka-voice-toast alert alert-" + toastType;
        toast.setAttribute("role", "alert");
        toast.textContent = message;
        document.body.appendChild(toast);

        const duration = TOAST_DURATION_MS[toastType] || TOAST_DURATION_MS.info;

        window.setTimeout(function () {
            toast.classList.add("is-hiding");
            window.setTimeout(function () {
                toast.remove();
            }, 300);
        }, duration);
    }

    function updatePanelVisibility(statusLabel) {
        const showPanel = PANEL_VISIBLE_STATUSES.has(statusLabel);

        if (voiceRoot) {
            voiceRoot.classList.toggle("is-active", showPanel);
        }
        if (panelEl) {
            panelEl.hidden = !showPanel;
            panelEl.setAttribute("aria-hidden", showPanel ? "false" : "true");
        }
    }

    function setStatus(label, detail) {
        if (statusEl) {
            statusEl.textContent = label;
        }
        if (transcriptEl) {
            transcriptEl.textContent = detail || "";
        }
        updatePanelVisibility(label);
    }

    function clearInactivityTimer() {
        if (inactivityTimer) {
            window.clearTimeout(inactivityTimer);
            inactivityTimer = null;
        }
    }

    function resetToIdle() {
        clearInactivityTimer();
        setListeningState(false);
        setStatus("Pronto", "");
    }

    function startInactivityTimer() {
        clearInactivityTimer();
        inactivityTimer = window.setTimeout(function () {
            cancelListening();
        }, LISTENING_INACTIVITY_MS);
    }

    function resetInactivityTimer() {
        if (!isListening) {
            return;
        }
        startInactivityTimer();
    }

    function isVoiceControlTarget(target) {
        if (!target || !(target instanceof Element)) {
            return false;
        }

        if (voiceRoot && voiceRoot.contains(target)) {
            return true;
        }

        return Boolean(target.closest("[data-voice-toggle]"));
    }

    function cancelListening() {
        clearInactivityTimer();

        if (recognition && isListening) {
            try {
                recognition.abort();
            } catch (error) {
                try {
                    recognition.stop();
                } catch (stopError) {
                    /* ignore */
                }
            }
        }

        resetToIdle();
    }

    function setListeningState(active) {
        isListening = active;

        document.querySelectorAll("[data-voice-toggle]").forEach(function (button) {
            button.classList.toggle("is-listening", active);
            button.setAttribute("aria-pressed", active ? "true" : "false");
            button.setAttribute(
                "aria-label",
                active ? "Interrompi ascolto vocale" : "Avvia comando vocale"
            );
            button.title = active ? "Interrompi ascolto" : "Comando vocale";
        });
    }

    function handleTranscript(transcript, isFinal) {
        if (!transcript) {
            return;
        }

        resetInactivityTimer();
        setStatus(isFinal ? "Elaborazione..." : "Ascolto...", transcript);

        if (!isFinal) {
            return;
        }

        clearInactivityTimer();

        const destination = parseIntent(transcript);
        if (destination) {
            setStatus("Comando riconosciuto", transcript);
            speak("Ok");
            window.setTimeout(function () {
                window.location.href = destination;
            }, 350);
            return;
        }

        resetToIdle();
        showToast('Comando non riconosciuto: "' + transcript + '". Prova "apri clienti" o "cerca cliente Rossi".', "danger");
        speak("Comando non riconosciuto");
    }

    function stopListening() {
        clearInactivityTimer();

        if (recognition && isListening) {
            try {
                recognition.stop();
            } catch (error) {
                /* ignore */
            }
        }

        resetToIdle();
    }

    function startListening() {
        if (!SpeechRecognition) {
            showToast("Il riconoscimento vocale non e supportato in questo browser. Usa Chrome o Edge.", "danger");
            return;
        }

        if (!recognition) {
            recognition = new SpeechRecognition();
            recognition.lang = "it-IT";
            recognition.continuous = false;
            recognition.interimResults = true;
            recognition.maxAlternatives = 1;

            recognition.addEventListener("start", function () {
                setListeningState(true);
                setStatus("Ascolto...", "Parla ora...");
                startInactivityTimer();
            });

            recognition.addEventListener("result", function (event) {
                let interim = "";
                let finalText = "";

                for (let i = event.resultIndex; i < event.results.length; i += 1) {
                    const result = event.results[i];
                    const piece = result[0].transcript.trim();
                    if (result.isFinal) {
                        finalText += (finalText ? " " : "") + piece;
                    } else {
                        interim += (interim ? " " : "") + piece;
                    }
                }

                handleTranscript(finalText || interim, Boolean(finalText));
            });

            recognition.addEventListener("error", function (event) {
                clearInactivityTimer();

                if (event.error === "not-allowed") {
                    resetToIdle();
                    showToast("Permesso microfono negato. Consenti l'accesso al microfono nelle impostazioni del browser.", "danger");
                    return;
                }

                if (event.error === "no-speech") {
                    resetToIdle();
                    showToast("Nessun audio rilevato. Riprova parlando piu vicino al microfono.", "info");
                    return;
                }

                if (event.error === "aborted") {
                    resetToIdle();
                    return;
                }

                resetToIdle();
                showToast("Errore riconoscimento vocale: " + event.error, "danger");
            });

            recognition.addEventListener("end", function () {
                clearInactivityTimer();
                setListeningState(false);

                if (!statusEl) {
                    return;
                }

                const status = statusEl.textContent;
                if (status === "Ascolto..." || status === "Elaborazione...") {
                    resetToIdle();
                }
            });
        }

        try {
            recognition.start();
        } catch (error) {
            if (isListening) {
                recognition.stop();
            } else {
                showToast("Impossibile avviare il microfono. Riprova.", "danger");
            }
        }
    }

    function toggleListening() {
        if (isListening) {
            stopListening();
            return;
        }
        startListening();
    }

    function buildUi() {
        const root = document.createElement("div");
        root.className = "eureka-voice";
        root.innerHTML =
            '<div class="eureka-voice-panel" aria-live="polite" hidden aria-hidden="true">' +
            '<div class="eureka-voice-panel-title">Assistente vocale</div>' +
            '<div class="eureka-voice-status">Pronto</div>' +
            '<div class="eureka-voice-transcript"></div>' +
            "</div>";

        document.body.appendChild(root);

        voiceRoot = root;
        panelEl = root.querySelector(".eureka-voice-panel");
        statusEl = root.querySelector(".eureka-voice-status");
        transcriptEl = root.querySelector(".eureka-voice-transcript");
        toggleBtn = document.querySelector("[data-voice-toggle]");

        if (toggleBtn) {
            toggleBtn.addEventListener("click", toggleListening);
        }

        document.addEventListener("keydown", function (event) {
            if (event.key !== "Escape" || !isListening) {
                return;
            }

            event.preventDefault();
            cancelListening();
        });

        document.addEventListener("mousedown", function (event) {
            if (!isListening || isVoiceControlTarget(event.target)) {
                return;
            }

            cancelListening();
        });
    }

    function showUnsupportedMessage() {
        unsupportedEl = document.createElement("div");
        unsupportedEl.className = "eureka-voice-unsupported alert alert-warning";
        unsupportedEl.textContent = "Comandi vocali non disponibili: usa Chrome o Edge con microfono abilitato.";
        document.body.appendChild(unsupportedEl);
    }

    document.addEventListener("DOMContentLoaded", function () {
        if (!window.EUREKA_VOICE_ENABLED) {
            return;
        }

        buildUi();

        if (!SpeechRecognition) {
            showUnsupportedMessage();
            document.querySelectorAll("[data-voice-toggle]").forEach(function (button) {
                button.disabled = true;
                button.classList.add("is-disabled");
            });
        }

        if (window.speechSynthesis) {
            window.speechSynthesis.getVoices();
            window.speechSynthesis.addEventListener("voiceschanged", function () {
                window.speechSynthesis.getVoices();
            });
        }
    });
})();
