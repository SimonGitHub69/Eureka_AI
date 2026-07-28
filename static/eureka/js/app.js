function getCurrentTheme() {
    return document.documentElement.getAttribute("data-bs-theme") || "light";
}

function applyTheme(theme) {
    const normalizedTheme = theme === "dark" ? "dark" : "light";
    const toggleButton = document.querySelector("[data-theme-toggle]");
    const toggleIcon = document.querySelector("[data-theme-toggle-icon]");
    const label = normalizedTheme === "dark" ? "Attiva tema chiaro" : "Attiva tema scuro";

    document.documentElement.setAttribute("data-bs-theme", normalizedTheme);
    localStorage.setItem("eureka-theme", normalizedTheme);

    if (toggleButton) {
        toggleButton.setAttribute("aria-label", label);
        toggleButton.setAttribute("title", label);
    }

    if (toggleIcon) {
        toggleIcon.classList.toggle("ti-moon", normalizedTheme !== "dark");
        toggleIcon.classList.toggle("ti-sun", normalizedTheme === "dark");
    }
}

document.addEventListener("DOMContentLoaded", function () {
    const toggleButton = document.querySelector("[data-theme-toggle]");

    applyTheme(getCurrentTheme());

    // ID stabile del dispositivo (necessario su iPad: non c'è COMPUTERNAME)
    try {
        ensureEurekaDeviceId();
        syncEurekaDeviceToServer();
    } catch (e) { /* ignore */ }

    // Segnala tablet/touch al server
    try {
        const ua = navigator.userAgent || "";
        const isTouchApple = /iPad|iPhone|iPod/.test(ua)
            || (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1);
        if (isTouchApple || navigator.maxTouchPoints > 1) {
            document.cookie = "eureka_touch=1; path=/; max-age=31536000; SameSite=Lax";
        }
    } catch (e) { /* ignore */ }

    if (!toggleButton) {
        return;
    }

    toggleButton.addEventListener("click", function () {
        applyTheme(getCurrentTheme() === "dark" ? "light" : "dark");
    });
});

function isTouchAppleDevice() {
    const ua = navigator.userAgent || "";
    if (/iPad|iPhone|iPod/.test(ua)) return true;
    return navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1;
}

function isTabletLikeDevice() {
    return isTouchAppleDevice() || navigator.maxTouchPoints > 1;
}

function getCookieValue(name) {
    const prefix = name + "=";
    const parts = (document.cookie || "").split(";");
    for (let i = 0; i < parts.length; i += 1) {
        const part = parts[i].trim();
        if (part.indexOf(prefix) === 0) {
            try {
                return decodeURIComponent(part.slice(prefix.length));
            } catch (e) {
                return part.slice(prefix.length);
            }
        }
    }
    return "";
}

/**
 * Su iPad: ID stabile IPAD-XXXX (il browser non ha COMPUTERNAME).
 * Su PC desktop: non toccare il cookie — il server usa il nome Windows reale.
 */
function ensureEurekaDeviceId() {
    if (!isTabletLikeDevice()) {
        return getCookieValue("eureka_pc");
    }

    const key = "eureka_device_id";
    let id = "";
    try {
        id = (localStorage.getItem(key) || "").trim();
    } catch (e) {
        id = "";
    }

    const valid = /^[A-Za-z0-9][A-Za-z0-9_-]{0,62}$/.test(id);
    if (!valid) {
        const prefix = isTouchAppleDevice() ? "IPAD" : "TABLET";
        id = prefix + "-" + Math.random().toString(36).slice(2, 8).toUpperCase();
        try {
            localStorage.setItem(key, id);
        } catch (e2) { /* ignore */ }
    }

    document.cookie = "eureka_pc=" + encodeURIComponent(id)
        + "; path=/; max-age=31536000; SameSite=Lax";
    return id;
}

function syncEurekaDeviceToServer() {
    // Solo tablet/iPad: sul PC Windows il middleware impone COMPUTERNAME
    if (!isTabletLikeDevice()) {
        return;
    }

    const path = window.location.pathname || "";
    if (path.indexOf("/parametri/pc") !== 0) {
        return;
    }

    const id = ensureEurekaDeviceId();
    if (!id) {
        return;
    }

    const params = new URLSearchParams(window.location.search || "");
    if (params.get("pc") === id) {
        return;
    }

    try {
        if (sessionStorage.getItem("eureka_pc_synced") === id) {
            return;
        }
        sessionStorage.setItem("eureka_pc_synced", id);
    } catch (e) { /* continue */ }

    params.set("pc", id);
    const qs = params.toString();
    window.location.replace(path + (qs ? ("?" + qs) : ""));
}

document.addEventListener("DOMContentLoaded", function () {
    const body = document.body;
    const toggle = document.querySelector("[data-sidebar-toggle]");
    const backdrop = document.querySelector("[data-sidebar-backdrop]");
    const sidebar = document.querySelector(".st-sidebar");

    if (!toggle || !sidebar) {
        return;
    }

    function setOpen(open) {
        body.classList.toggle("st-sidebar-open", open);
        toggle.setAttribute("aria-expanded", open ? "true" : "false");
        toggle.setAttribute("aria-label", open ? "Chiudi menu" : "Apri menu");
        if (backdrop) {
            backdrop.hidden = !open;
        }
    }

    function closeSidebar() {
        setOpen(false);
    }

    toggle.addEventListener("click", function () {
        setOpen(!body.classList.contains("st-sidebar-open"));
    });

    if (backdrop) {
        backdrop.addEventListener("click", closeSidebar);
    }

    window.addEventListener("resize", function () {
        if (window.matchMedia("(min-width: 1400px)").matches) {
            closeSidebar();
        }
    });

    document.addEventListener("keydown", function (event) {
        if (event.key === "Escape") {
            closeSidebar();
        }
    });
});

document.addEventListener("DOMContentLoaded", function () {
    const STORAGE_KEY = "eureka-sidebar-sections";
    const SCROLL_KEY = "eureka-sidebar-scroll-top";
    const sections = Array.from(document.querySelectorAll("[data-nav-section]"));
    const nav = document.querySelector(".st-sidebar-nav");

    if (!sections.length) {
        return;
    }

    let saved = {};
    try {
        saved = JSON.parse(localStorage.getItem(STORAGE_KEY) || "{}") || {};
    } catch (error) {
        saved = {};
    }

    function persist() {
        const state = {};
        sections.forEach(function (section) {
            state[section.dataset.navSection] = section.classList.contains("is-open");
        });
        localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
    }

    function saveScroll() {
        if (!nav) {
            return;
        }
        localStorage.setItem(SCROLL_KEY, String(nav.scrollTop || 0));
    }

    function setOpen(section, open) {
        const toggle = section.querySelector("[data-nav-toggle]");
        section.classList.toggle("is-open", open);
        if (toggle) {
            toggle.setAttribute("aria-expanded", open ? "true" : "false");
        }
    }

    sections.forEach(function (section) {
        const key = section.dataset.navSection;
        const hasActive = Boolean(section.querySelector(".st-nav-link.active"));
        const toggle = section.querySelector("[data-nav-toggle]");

        if (Object.prototype.hasOwnProperty.call(saved, key)) {
            setOpen(section, Boolean(saved[key]) || hasActive);
        } else {
            setOpen(section, section.classList.contains("is-open") || hasActive);
        }

        if (!toggle) {
            return;
        }

        toggle.addEventListener("click", function () {
            setOpen(section, !section.classList.contains("is-open"));
            persist();
            saveScroll();
        });
    });

    if (nav) {
        const savedScroll = parseInt(localStorage.getItem(SCROLL_KEY) || "0", 10);
        function restoreScroll() {
            if (!Number.isNaN(savedScroll) && savedScroll > 0) {
                nav.scrollTop = savedScroll;
            }
        }

        restoreScroll();
        window.requestAnimationFrame(function () {
            window.requestAnimationFrame(restoreScroll);
        });
        window.setTimeout(restoreScroll, 60);

        nav.addEventListener("scroll", saveScroll, { passive: true });
        nav.querySelectorAll("a.st-nav-link, a.st-nav-sub-link").forEach(function (link) {
            link.addEventListener("click", saveScroll);
        });
    }
});

document.addEventListener("DOMContentLoaded", function () {
    const guardedForms = Array.from(document.querySelectorAll('form[method="post"]')).filter(function (form) {
        const hasEditableFields = form.querySelector(
            'input:not([type="hidden"]):not([type="submit"]):not([type="button"]), textarea, select'
        );

        return form.dataset.unsavedGuard !== "false" && Boolean(hasEditableFields);
    });

    if (!guardedForms.length) {
        return;
    }

    let hasUnsavedChanges = false;
    let isSubmitting = false;

    function markUnsaved() {
        if (!isSubmitting) {
            hasUnsavedChanges = true;
        }
    }

    guardedForms.forEach(function (form) {
        form.addEventListener("input", markUnsaved);
        form.addEventListener("change", markUnsaved);
        form.addEventListener("submit", function () {
            isSubmitting = true;
            hasUnsavedChanges = false;
        });
    });

    document.addEventListener("click", function (event) {
        const button = event.target.closest("button");

        if (!button || button.type === "submit" || button.dataset.unsavedIgnore === "true") {
            return;
        }

        const form = button.closest('form[method="post"]');

        if (form && guardedForms.includes(form)) {
            markUnsaved();
        }
    });

    window.addEventListener("beforeunload", function (event) {
        if (!hasUnsavedChanges || isSubmitting) {
            return;
        }

        event.preventDefault();
        event.returnValue = "";
    });
});

/**
 * Helper locale Eureka: apre/condivide file export con programmi Windows.
 */
window.EurekaFileHelper = (function () {
    const OPEN_URL = "/api/helper/open/";
    const SHARE_URL = "/api/helper/share/";
    const LOCAL_OPEN_URL = "http://127.0.0.1:8765/open";
    const LOCAL_SHARE_URL = "http://127.0.0.1:8765/share";

    function csrfToken() {
        const meta = document.querySelector('meta[name="csrf-token"]');
        if (meta && meta.content) {
            return meta.content;
        }
        const match = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
        if (match) {
            return decodeURIComponent(match[1]);
        }
        const input = document.querySelector("input[name=csrfmiddlewaretoken]");
        return input ? input.value : "";
    }

    function isTouchApple() {
        const ua = navigator.userAgent || "";
        if (/iPad|iPhone|iPod/.test(ua)) return true;
        return navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1;
    }

    function isWindowsDesktop() {
        return /Windows/i.test(navigator.userAgent || "") && !isTouchApple();
    }

    async function blobToBase64(blob) {
        const arrayBuffer = await blob.arrayBuffer();
        const bytes = new Uint8Array(arrayBuffer);
        let binary = "";
        for (let i = 0; i < bytes.length; i += 1) {
            binary += String.fromCharCode(bytes[i]);
        }
        return btoa(binary);
    }

    async function postJson(url, body, withCsrf) {
        const headers = { "Content-Type": "application/json" };
        if (withCsrf) {
            headers["X-CSRFToken"] = csrfToken();
        }
        const response = await fetch(url, {
            method: "POST",
            credentials: withCsrf ? "same-origin" : "omit",
            headers: headers,
            body: JSON.stringify(body),
        });
        if (!response.ok) {
            const payload = await response.json().catch(function () { return {}; });
            throw new Error(payload.error || ("Errore " + response.status));
        }
        return response;
    }

    async function postToHelper(action, fileName, blob) {
        const body = {
            filename: fileName,
            content_b64: await blobToBase64(blob),
        };
        const djangoUrl = action === "share" ? SHARE_URL : OPEN_URL;
        const localUrl = action === "share" ? LOCAL_SHARE_URL : LOCAL_OPEN_URL;

        // Su Windows preferisci l'helper locale: apre direttamente la maschera di sistema.
        if (isWindowsDesktop()) {
            try {
                await postJson(localUrl, body, false);
                return;
            } catch (localErr) {
                // fallback su proxy Django
            }
        }

        try {
            await postJson(djangoUrl, body, true);
            return;
        } catch (djangoErr) {
            if (!isWindowsDesktop()) {
                throw djangoErr;
            }
            await postJson(localUrl, body, false);
        }
    }

    async function openBlob(fileName, blob) {
        await postToHelper("open", fileName, blob);
    }

    async function shareBlob(fileName, blob, mimeType) {
        // Su Windows: maschera Condividi di sistema via helper locale.
        if (isWindowsDesktop()) {
            await postToHelper("share", fileName, blob);
            return;
        }

        if (isTouchApple()) {
            const file = new File([blob], fileName, {
                type: blob.type || mimeType || "application/octet-stream",
            });
            if (navigator.canShare && navigator.canShare({ files: [file] })) {
                try {
                    await navigator.share({ files: [file], title: fileName });
                    return;
                } catch (shareErr) {
                    if (shareErr && shareErr.name === "AbortError") {
                        return;
                    }
                }
            }
        }

        await postToHelper("share", fileName, blob);
    }

    async function shareFromUrl(url, fileName, mimeType) {
        const response = await fetch(url, {
            credentials: "same-origin",
            headers: { Accept: "*/*" },
        });
        if (!response.ok) {
            throw new Error("Export non riuscito");
        }
        const blob = await response.blob();
        const resolvedName = fileName || "export.bin";
        await shareBlob(resolvedName, blob, mimeType);
    }

    function helperUnavailableMessage() {
        return (
            "Per usare Condividi su Windows avvia l'helper locale Eureka.\n\n" +
            "Si avvia automaticamente con Django; se serve:\n" +
            "powershell -ExecutionPolicy Bypass -File scripts\\start_eureka_open_helper.ps1"
        );
    }

    return {
        OPEN_URL: OPEN_URL,
        SHARE_URL: SHARE_URL,
        isWindowsDesktop: isWindowsDesktop,
        isTouchApple: isTouchApple,
        openBlob: openBlob,
        shareBlob: shareBlob,
        shareFromUrl: shareFromUrl,
        helperUnavailableMessage: helperUnavailableMessage,
    };
}());

/**
 * Export CSV/XLSX: foglio con due azioni
 * 1) Scarica → fetch Blob + <a download> (salva in File, Eureka resta)
 * 2) Apri in Numbers → inline (?open=1), anteprima di sistema
 */
document.addEventListener("DOMContentLoaded", function () {
    function isShareExportAnchor(anchor) {
        return Boolean(anchor && anchor.hasAttribute("data-eureka-share-export"));
    }

    function isExportAnchor(anchor) {
        if (isShareExportAnchor(anchor)) return false;
        if (!anchor || !anchor.getAttribute("href")) return false;
        try {
            const url = new URL(anchor.getAttribute("href"), window.location.href);
            if (url.origin !== window.location.origin) return false;
            return Boolean((url.searchParams.get("export") || "").trim());
        } catch (e) {
            return false;
        }
    }

    function isTouchApple() {
        const ua = navigator.userAgent || "";
        if (/iPad|iPhone|iPod/.test(ua)) return true;
        return navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1;
    }

    function exportFormatLabel(url) {
        const fmt = (url.searchParams.get("fmt") || "").toLowerCase();
        if (fmt === "xlsx" || fmt === "xls" || fmt === "excel") return "XLSX";
        const exp = (url.searchParams.get("export") || "").toLowerCase();
        if (exp === "xlsx" || exp === "xls" || exp === "excel") return "XLSX";
        return "CSV";
    }

    function fileNameFromDisposition(header, fallback) {
        if (!header) return fallback;
        const utf = /filename\*=UTF-8''([^;]+)/i.exec(header);
        if (utf && utf[1]) {
            try {
                return decodeURIComponent(utf[1].trim().replace(/["']/g, ""));
            } catch (e) { /* ignore */ }
        }
        const plain = /filename="?([^";]+)"?/i.exec(header);
        if (plain && plain[1]) return plain[1].trim();
        return fallback;
    }

    function buildExportUrl(anchor, openInline) {
        const url = new URL(anchor.getAttribute("href"), window.location.href);
        url.searchParams.delete("bridge");
        url.searchParams.delete("dl");
        if (openInline) {
            url.searchParams.set("open", "1");
        } else {
            url.searchParams.delete("open");
        }
        return url;
    }

    function triggerBlobDownload(blob, filename) {
        const objectUrl = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = objectUrl;
        a.download = filename;
        a.rel = "noopener";
        a.style.display = "none";
        document.body.appendChild(a);
        a.click();
        a.remove();
        window.setTimeout(function () {
            URL.revokeObjectURL(objectUrl);
        }, 2000);
    }

    /** Fallback iOS: data: URL + download (a volte salva in File senza aprire Numbers). */
    function triggerDataUrlDownload(blob, filename) {
        return new Promise(function (resolve, reject) {
            const reader = new FileReader();
            reader.onerror = function () {
                reject(new Error("Lettura file non riuscita"));
            };
            reader.onloadend = function () {
                try {
                    const a = document.createElement("a");
                    a.href = String(reader.result || "");
                    a.download = filename;
                    a.rel = "noopener";
                    a.style.display = "none";
                    document.body.appendChild(a);
                    a.click();
                    a.remove();
                    resolve();
                } catch (err) {
                    reject(err);
                }
            };
            reader.readAsDataURL(blob);
        });
    }

    async function downloadViaBlob(url, label) {
        const fallbackName = "export." + (label === "XLSX" ? "xlsx" : "csv");
        const response = await fetch(url.href, {
            credentials: "same-origin",
            headers: { Accept: "*/*" },
        });
        if (!response.ok) {
            throw new Error("Download fallito (" + response.status + ")");
        }
        const blob = await response.blob();
        const filename = fileNameFromDisposition(
            response.headers.get("Content-Disposition"),
            fallbackName
        );

        // Preferisci Condividi / Salva in File quando disponibile (HTTPS)
        try {
            const file = new File([blob], filename, {
                type: blob.type || (label === "XLSX"
                    ? "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    : "text/csv"),
            });
            if (navigator.canShare && navigator.canShare({ files: [file] })) {
                await navigator.share({ files: [file], title: filename });
                return "shared";
            }
        } catch (shareErr) {
            if (shareErr && shareErr.name === "AbortError") return "cancelled";
        }

        if (isTouchApple()) {
            await triggerDataUrlDownload(blob, filename);
        } else {
            triggerBlobDownload(blob, filename);
        }
        return "downloaded";
    }

    function ensureExportSheet() {
        let overlay = document.getElementById("eureka-export-overlay");
        if (overlay) return overlay;

        overlay = document.createElement("div");
        overlay.id = "eureka-export-overlay";
        overlay.className = "eureka-export-overlay";
        overlay.setAttribute("hidden", "");
        overlay.innerHTML =
            '<div class="eureka-export-sheet" role="dialog" aria-modal="true" aria-labelledby="eureka-export-title">'
            + '<div class="eureka-export-sheet__handle" aria-hidden="true"></div>'
            + '<h3 id="eureka-export-title" class="eureka-export-sheet__title">Esporta</h3>'
            + '<p class="eureka-export-sheet__hint" data-export-hint></p>'
            + '<div class="eureka-export-sheet__actions">'
            + '<button type="button" class="btn btn-primary w-100" data-export-action="download">'
            + '<i class="ti ti-download me-1"></i><span data-export-download-label>Scarica</span>'
            + "</button>"
            + '<button type="button" class="btn btn-outline-secondary w-100" data-export-action="open">'
            + '<i class="ti ti-file-spreadsheet me-1"></i><span data-export-open-label>Apri in Numbers</span>'
            + "</button>"
            + '<button type="button" class="btn btn-ghost-secondary w-100" data-export-action="cancel">Annulla</button>'
            + "</div>"
            + '<p class="eureka-export-sheet__status" data-export-status hidden></p>'
            + "</div>";
        document.body.appendChild(overlay);

        overlay.addEventListener("click", function (event) {
            if (event.target === overlay) closeExportSheet();
        });
        return overlay;
    }

    let activeAnchor = null;

    function closeExportSheet() {
        const overlay = document.getElementById("eureka-export-overlay");
        if (!overlay) return;
        overlay.classList.remove("is-open");
        overlay.setAttribute("hidden", "");
        activeAnchor = null;
        const status = overlay.querySelector("[data-export-status]");
        if (status) {
            status.hidden = true;
            status.textContent = "";
        }
        overlay.querySelectorAll("button").forEach(function (btn) {
            btn.disabled = false;
        });
    }

    function openExportSheet(anchor) {
        const overlay = ensureExportSheet();
        const url = buildExportUrl(anchor, false);
        const label = exportFormatLabel(url);
        activeAnchor = anchor;

        overlay.querySelector("#eureka-export-title").textContent = "Esporta " + label;
        const hint = overlay.querySelector("[data-export-hint]");
        hint.textContent = isTouchApple()
            ? "Scarica salva il file (File / Download). Apri in Numbers mostra l’anteprima di sistema."
            : "Scarica salva il file sul computer. Apri apre l’anteprima nel browser.";
        overlay.querySelector("[data-export-download-label]").textContent =
            "Scarica " + label;
        overlay.querySelector("[data-export-open-label]").textContent = isTouchApple()
            ? "Apri in Numbers"
            : "Apri file";

        overlay.removeAttribute("hidden");
        requestAnimationFrame(function () {
            overlay.classList.add("is-open");
        });
    }

    function setSheetBusy(busy, message) {
        const overlay = document.getElementById("eureka-export-overlay");
        if (!overlay) return;
        overlay.querySelectorAll("button").forEach(function (btn) {
            btn.disabled = busy;
        });
        const status = overlay.querySelector("[data-export-status]");
        if (!status) return;
        if (message) {
            status.hidden = false;
            status.textContent = message;
        } else {
            status.hidden = true;
            status.textContent = "";
        }
    }

    document.addEventListener("click", function (event) {
        const actionBtn = event.target.closest("[data-export-action]");
        if (actionBtn) {
            event.preventDefault();
            event.stopPropagation();
            const action = actionBtn.getAttribute("data-export-action");
            if (action === "cancel") {
                closeExportSheet();
                return;
            }
            if (!activeAnchor) return;

            if (action === "open") {
                const openUrl = buildExportUrl(activeAnchor, true);
                closeExportSheet();
                // Navigazione diretta: maschera Numbers di sistema
                window.location.assign(openUrl.href);
                return;
            }

            if (action === "download") {
                const downloadUrl = buildExportUrl(activeAnchor, false);
                const label = exportFormatLabel(downloadUrl);
                setSheetBusy(true, "Preparazione file…");
                downloadViaBlob(downloadUrl, label)
                    .then(function (result) {
                        if (result === "cancelled") {
                            setSheetBusy(false, "");
                            return;
                        }
                        setSheetBusy(
                            false,
                            result === "shared"
                                ? "Condivisione aperta. Puoi salvare in File."
                                : (isTouchApple()
                                    ? "Download avviato. Se compare l’anteprima: Condividi → Salva su File."
                                    : "Download avviato. Controlla la cartella Download.")
                        );
                        window.setTimeout(closeExportSheet, 1200);
                    })
                    .catch(function (err) {
                        setSheetBusy(
                            false,
                            (err && err.message) || "Download non riuscito. Riprova."
                        );
                    });
            }
            return;
        }

        const anchor = event.target.closest("a[href]");
        if (!isExportAnchor(anchor)) return;
        if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
        if (event.button != null && event.button !== 0) return;

        event.preventDefault();
        event.stopPropagation();
        openExportSheet(anchor);
    }, true);

    document.addEventListener("keydown", function (event) {
        if (event.key === "Escape") closeExportSheet();
    });

    document.addEventListener("click", function (event) {
        const anchor = event.target.closest("a[data-eureka-share-export][href]");
        if (!anchor) return;
        if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
        if (event.button != null && event.button !== 0) return;

        event.preventDefault();
        event.stopPropagation();

        const url = new URL(anchor.getAttribute("href"), window.location.href);
        url.searchParams.delete("open");
        url.searchParams.delete("bridge");
        url.searchParams.delete("dl");
        url.searchParams.delete("page");
        const fmt = (url.searchParams.get("fmt") || "csv").toLowerCase();
        const exportKind = (url.searchParams.get("export") || "export").trim();
        const fileName = exportKind + "." + fmt;
        const mimeType = fmt === "xlsx"
            ? "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            : "text/csv";

        const helper = window.EurekaFileHelper;
        if (!helper) return;

        helper.shareFromUrl(url.href, fileName, mimeType).catch(function (err) {
            const message = String((err && err.message) || "");
            if (message.indexOf("Helper non disponibile") >= 0) {
                window.alert(helper.helperUnavailableMessage());
                return;
            }
            window.alert(message || "Condivisione non riuscita.");
        });
    }, true);
});

/**
 * Offline: senza rete solo «Dati offline» funziona (SQLite locale).
 * Blocca i link al server e registra il service worker su HTTPS.
 */
document.addEventListener("DOMContentLoaded", function () {
    function ensureOfflineBanner() {
        let bar = document.getElementById("eureka-offline-banner");
        if (bar) return bar;
        bar = document.createElement("div");
        bar.id = "eureka-offline-banner";
        bar.className = "eureka-offline-banner";
        bar.hidden = true;
        bar.innerHTML =
            '<div class="eureka-offline-banner__inner">'
            + "<strong>Sei offline.</strong> "
            + "Le pagine online non sono disponibili. "
            + '<a href="/offline/">Apri Dati offline</a> per le statistiche locali.'
            + "</div>";
        document.body.prepend(bar);
        return bar;
    }

    function syncOfflineUi() {
        const bar = ensureOfflineBanner();
        const offline = !navigator.onLine;
        bar.hidden = !offline;
        document.documentElement.classList.toggle("eureka-is-offline", offline);

        if (!offline) return;

        // Disabilita voci di menu che non sono Dati offline
        document.querySelectorAll(".st-sidebar a[href], .navbar a[href]").forEach(function (a) {
            const href = a.getAttribute("href") || "";
            if (!href || href.charAt(0) === "#") return;
            try {
                const u = new URL(href, window.location.href);
                if (u.origin !== window.location.origin) return;
                const ok = u.pathname === "/offline/" || u.pathname.indexOf("/offline") === 0;
                a.classList.toggle("eureka-nav-disabled", !ok);
                if (!ok) {
                    a.setAttribute("aria-disabled", "true");
                } else {
                    a.removeAttribute("aria-disabled");
                }
            } catch (e) { /* ignore */ }
        });
    }

    document.addEventListener(
        "click",
        function (event) {
            if (navigator.onLine) return;
            const anchor = event.target.closest("a[href]");
            if (!anchor) return;
            const href = anchor.getAttribute("href") || "";
            if (!href || href.charAt(0) === "#") return;
            if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
            try {
                const u = new URL(href, window.location.href);
                if (u.origin !== window.location.origin) return;
                if (u.pathname === "/offline/" || u.pathname.indexOf("/offline") === 0) {
                    return;
                }
                event.preventDefault();
                event.stopPropagation();
                window.alert(
                    "Sei senza Wi‑Fi.\n\n"
                    + "Funziona solo «Dati offline» (statistiche sul dispositivo).\n"
                    + "Le altre pagine richiedono la connessione al PC."
                );
                if (window.location.pathname.indexOf("/offline") !== 0) {
                    window.location.assign("/offline/");
                }
            } catch (e) { /* ignore */ }
        },
        true
    );

    window.addEventListener("online", syncOfflineUi);
    window.addEventListener("offline", syncOfflineUi);
    syncOfflineUi();

    // Service worker: solo in contesto sicuro (HTTPS / localhost)
    if ("serviceWorker" in navigator && window.isSecureContext) {
        const swUrl = (window.EUREKA_SW_URL || "/sw.js");
        navigator.serviceWorker.register(swUrl).catch(function () { /* ignore */ });
    }
});
