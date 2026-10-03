/**
 * Logout automatico solo alla chiusura reale dell'ultima finestra Eureka.
 *
 * Non deve mai scattare su:
 * - navigazione interna tra maschere
 * - voci menu Stampe / link target=_blank
 * - Ctrl/Cmd/Shift+click (nuova scheda)
 * - reload (F5 / Ctrl+R)
 * - ripristino bfcache
 * - aperture di finestre secondarie mentre l'app resta aperta
 *
 * Altrimenti l'utente, già autenticato, viene rimandato al login
 * selezionando una funzionalità e rimane spiazzato.
 */
(function () {
    "use strict";

    if (window.__eurekaLogoutOnCloseBound) {
        return;
    }
    window.__eurekaLogoutOnCloseBound = true;

    var TAB_STORE = "eureka_auth_tabs";
    // TTL lungo: schede in background vengono throttlate; 5 minuti era troppo aggressivo.
    var TAB_TTL_MS = 30 * 60 * 1000;
    // Copre la race opener→figlio su WebView/client quando si apre target=_blank.
    var CHILD_GRACE_MS = 90 * 1000;
    var tabId =
        "t" +
        Date.now().toString(36) +
        Math.random().toString(36).slice(2, 8);
    var navigating = false;
    var logoutSent = false;
    var suppressLogoutUntil = 0;

    function nowMs() {
        return Date.now();
    }

    function csrfToken() {
        var meta = document.querySelector('meta[name="csrf-token"]');
        if (meta && meta.content) {
            return meta.content;
        }
        if (document.body) {
            var fromBody =
                document.body.getAttribute("data-csrf") ||
                document.body.dataset.csrf ||
                "";
            if (fromBody) {
                return fromBody;
            }
        }
        var input = document.querySelector("input[name=csrfmiddlewaretoken]");
        return input ? input.value : "";
    }

    function readTabs() {
        try {
            return JSON.parse(localStorage.getItem(TAB_STORE) || "{}") || {};
        } catch (e) {
            return {};
        }
    }

    function writeTabs(tabs) {
        try {
            localStorage.setItem(TAB_STORE, JSON.stringify(tabs));
        } catch (e) {
            /* ignore */
        }
    }

    function pruneTabs(tabs) {
        var now = nowMs();
        Object.keys(tabs).forEach(function (id) {
            if (now - (tabs[id] || 0) > TAB_TTL_MS) {
                delete tabs[id];
            }
        });
        return tabs;
    }

    function registerTab() {
        var tabs = pruneTabs(readTabs());
        tabs[tabId] = nowMs();
        writeTabs(tabs);
    }

    /**
     * Placeholder per finestre/schede in apertura (target=_blank).
     * Evita logout se l'opener riceve pagehide prima che il figlio si registri.
     */
    function registerChildPlaceholder() {
        var tabs = pruneTabs(readTabs());
        var childId =
            "c" +
            nowMs().toString(36) +
            Math.random().toString(36).slice(2, 6);
        var ts = nowMs();
        tabs[childId] = ts;
        tabs[tabId] = ts;
        writeTabs(tabs);
        suppressLogoutUntil = Math.max(suppressLogoutUntil, ts + CHILD_GRACE_MS);
    }

    function unregisterTab() {
        var tabs = pruneTabs(readTabs());
        delete tabs[tabId];
        writeTabs(tabs);
        return Object.keys(tabs).length;
    }

    function markNavigating() {
        navigating = true;
        suppressLogoutUntil = Math.max(suppressLogoutUntil, nowMs() + 8000);
    }

    // Usato da app.js per location.assign/replace e altre navigazioni programmatiche.
    window.__eurekaMarkNavigating = markNavigating;

    function sendLogout() {
        if (logoutSent) {
            return;
        }
        if (nowMs() < suppressLogoutUntil) {
            return;
        }
        logoutSent = true;
        try {
            localStorage.removeItem(TAB_STORE);
        } catch (e0) {
            /* ignore */
        }
        var token = csrfToken();
        if (!token) {
            // Senza CSRF non si può invalidare la sessione (LogoutView POST-only).
            try {
                sessionStorage.clear();
            } catch (e1) {
                /* ignore */
            }
            return;
        }
        var body = new FormData();
        body.append("csrfmiddlewaretoken", token);
        try {
            if (navigator.sendBeacon) {
                navigator.sendBeacon("/logout/", body);
                return;
            }
        } catch (e) {
            /* fall through */
        }
        try {
            fetch("/logout/", {
                method: "POST",
                body: body,
                credentials: "same-origin",
                keepalive: true,
                headers: { "X-CSRFToken": token },
            });
        } catch (e2) {
            /* ignore */
        }
    }

    function onPageHide(event) {
        if (navigating) {
            return;
        }
        if (event && event.persisted) {
            return;
        }
        if (sessionStorage.getItem("eureka_manual_logout") === "1") {
            sessionStorage.removeItem("eureka_manual_logout");
            try {
                localStorage.removeItem(TAB_STORE);
            } catch (e) {
                /* ignore */
            }
            return;
        }
        // Durante apertura figlio (_blank): non invalidare la sessione anche se
        // questa scheda è l'ultima ancora registrata.
        if (nowMs() < suppressLogoutUntil) {
            unregisterTab();
            return;
        }
        var remaining = unregisterTab();
        if (remaining > 0) {
            return;
        }
        sendLogout();
    }

    registerTab();

    var beat = window.setInterval(registerTab, 30000);
    window.addEventListener(
        "pagehide",
        function () {
            window.clearInterval(beat);
        },
        { once: true }
    );

    document.addEventListener(
        "click",
        function (event) {
            var anchor = event.target.closest("a[href]");
            if (!anchor) {
                return;
            }
            var href = anchor.getAttribute("href") || "";
            if (!href || href.charAt(0) === "#" || href.indexOf("javascript:") === 0) {
                return;
            }

            var opensNewContext =
                event.metaKey ||
                event.ctrlKey ||
                event.shiftKey ||
                event.altKey ||
                (event.button != null && event.button === 1) ||
                (anchor.target && anchor.target !== "" && anchor.target !== "_self");

            if (opensNewContext) {
                // Menu Stampe e simili: non navigano l'opener, ma alcuni client
                // sparano comunque pagehide → senza placeholder si fa logout.
                try {
                    var childUrl = new URL(href, window.location.href);
                    if (childUrl.origin === window.location.origin) {
                        registerChildPlaceholder();
                    }
                } catch (eChild) {
                    registerChildPlaceholder();
                }
                return;
            }

            try {
                var url = new URL(href, window.location.href);
                if (url.origin === window.location.origin) {
                    markNavigating();
                }
            } catch (e) {
                /* ignore */
            }
        },
        true
    );

    document.addEventListener(
        "auxclick",
        function (event) {
            // Pulsante centrale: apre nuova scheda.
            if (event.button !== 1) {
                return;
            }
            var anchor = event.target.closest("a[href]");
            if (!anchor) {
                return;
            }
            registerChildPlaceholder();
        },
        true
    );

    document.addEventListener(
        "submit",
        function (event) {
            var form = event.target;
            if (!form) {
                markNavigating();
                return;
            }
            try {
                var action = new URL(
                    form.getAttribute("action") || window.location.href,
                    window.location.href
                );
                if (action.pathname.indexOf("/logout") === 0) {
                    sessionStorage.setItem("eureka_manual_logout", "1");
                    try {
                        localStorage.removeItem(TAB_STORE);
                    } catch (eClear) {
                        /* ignore */
                    }
                }
                if (action.origin === window.location.origin) {
                    markNavigating();
                }
            } catch (e) {
                markNavigating();
            }
        },
        true
    );

    window.addEventListener("keydown", function (event) {
        if (event.key === "F5") {
            markNavigating();
            return;
        }
        if ((event.ctrlKey || event.metaKey) && String(event.key).toLowerCase() === "r") {
            markNavigating();
        }
    });

    // Solo pagehide: `unload` è ridondante e su alcuni motori scatta in casi ambigui.
    window.addEventListener("pagehide", onPageHide);

    window.addEventListener("pageshow", function (event) {
        navigating = false;
        registerTab();
        if (event.persisted) {
            logoutSent = false;
        }
    });

    document.addEventListener("visibilitychange", function () {
        if (document.visibilityState === "visible") {
            registerTab();
        }
    });
})();
