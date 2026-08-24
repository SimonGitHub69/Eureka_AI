(function () {
    "use strict";

    var STORAGE_KEY = "eureka-print-preview-zoom";
    var LEVELS = [50, 75, 90, 100, 110, 125, 150, 175, 200];
    var zoom = 100;

    function clampToLevel(value) {
        var n = Number(value);
        if (!isFinite(n)) return 100;
        var best = LEVELS[0];
        var dist = Math.abs(n - best);
        for (var i = 1; i < LEVELS.length; i++) {
            var d = Math.abs(n - LEVELS[i]);
            if (d < dist) {
                best = LEVELS[i];
                dist = d;
            }
        }
        return best;
    }

    function apply() {
        var factor = zoom / 100;
        document.documentElement.style.setProperty("--print-preview-zoom", String(factor));
        document.body.classList.toggle("eureka-print-preview--zoomed", zoom !== 100);
        var labels = document.querySelectorAll("[data-print-zoom-label]");
        for (var i = 0; i < labels.length; i++) {
            labels[i].textContent = zoom + "%";
        }
        try {
            sessionStorage.setItem(STORAGE_KEY, String(zoom));
        } catch (err) {
            /* ignore */
        }
    }

    function setZoom(value) {
        zoom = clampToLevel(value);
        apply();
    }

    function step(delta) {
        var idx = LEVELS.indexOf(zoom);
        if (idx < 0) idx = LEVELS.indexOf(100);
        idx = Math.max(0, Math.min(LEVELS.length - 1, idx + delta));
        setZoom(LEVELS[idx]);
    }

    function onClick(event) {
        var target = event.target;
        if (!target || typeof target.closest !== "function") {
            target = target && target.parentElement;
        }
        if (!target || typeof target.closest !== "function") return;

        var closeBtn = target.closest("[data-print-close]");
        if (closeBtn) {
            event.preventDefault();
            closePrintWindow();
            return;
        }

        var btn = target.closest("[data-print-zoom]");
        if (!btn) return;
        var action = btn.getAttribute("data-print-zoom");
        if (action === "in") step(1);
        else if (action === "out") step(-1);
        else if (action === "reset") setZoom(100);
    }

    function closePrintWindow() {
        // Funziona se la scheda è stata aperta con target=_blank / window.open.
        window.close();
        // Fallback: alcuni browser bloccano close() (noopener / scheda non "script-opened").
        setTimeout(function () {
            try {
                if (window.history.length > 1) {
                    window.history.back();
                    return;
                }
            } catch (err) {
                /* ignore */
            }
            try {
                window.open("", "_self");
                window.close();
            } catch (err2) {
                /* ignore */
            }
        }, 150);
    }

    function onWheel(event) {
        if (!(event.ctrlKey || event.metaKey)) return;
        event.preventDefault();
        step(event.deltaY < 0 ? 1 : -1);
    }

    function onKey(event) {
        if (!(event.ctrlKey || event.metaKey)) return;
        if (event.key === "+" || event.key === "=") {
            event.preventDefault();
            step(1);
        } else if (event.key === "-" || event.key === "_") {
            event.preventDefault();
            step(-1);
        } else if (event.key === "0") {
            event.preventDefault();
            setZoom(100);
        }
    }

    try {
        zoom = clampToLevel(sessionStorage.getItem(STORAGE_KEY) || 100);
    } catch (err) {
        zoom = 100;
    }

    document.addEventListener("click", onClick);
    document.addEventListener("keydown", onKey);
    document.addEventListener("wheel", onWheel, { passive: false });
    apply();
})();
