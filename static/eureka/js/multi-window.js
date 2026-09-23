(function () {
    "use strict";

    var STORAGE_KEY = "eureka-multi-window";
    var CASCADE = { x: 36, y: 36 };
    var nextOffset = 0;
    var zCounter = 1;
    var windows = new Map();
    var desktop = null;
    var taskbar = null;
    var enabled = false;

    function isEmbedContext() {
        return document.body.classList.contains("st-embed");
    }

    function readEnabled() {
        try {
            return localStorage.getItem(STORAGE_KEY) === "1";
        } catch (e) {
            return false;
        }
    }

    function writeEnabled(value) {
        try {
            localStorage.setItem(STORAGE_KEY, value ? "1" : "0");
        } catch (e) {
            /* ignore */
        }
    }

    function withEmbed(url) {
        try {
            var u = new URL(url, window.location.origin);
            if (u.origin !== window.location.origin) {
                return null;
            }
            u.searchParams.set("embed", "1");
            return u.pathname + u.search + u.hash;
        } catch (e) {
            return null;
        }
    }

    function shouldSkip(url, link) {
        if (link && link.getAttribute("target") === "_blank") {
            return true;
        }
        try {
            var u = new URL(url, window.location.origin);
            if (u.origin !== window.location.origin) {
                return true;
            }
            var path = u.pathname || "";
            if (path.indexOf("/admin/") === 0) {
                return true;
            }
            if (path.indexOf("/logout") === 0) {
                return true;
            }
            return false;
        } catch (e) {
            return true;
        }
    }

    function titleFromLink(link, url) {
        var label = link && link.querySelector(".st-nav-label");
        if (label && label.textContent.trim()) {
            return label.textContent.trim();
        }
        if (link && link.getAttribute("title")) {
            return link.getAttribute("title");
        }
        if (link && link.textContent.trim()) {
            return link.textContent.trim().replace(/\s+/g, " ").slice(0, 48);
        }
        try {
            return new URL(url, window.location.origin).pathname;
        } catch (e) {
            return "Finestra";
        }
    }

    function ensureUi() {
        if (!desktop) {
            desktop = document.createElement("div");
            desktop.className = "mw-desktop";
            desktop.setAttribute("aria-hidden", "true");
            document.body.appendChild(desktop);
        }
        if (!taskbar) {
            taskbar = document.createElement("div");
            taskbar.className = "mw-taskbar";
            taskbar.setAttribute("role", "toolbar");
            taskbar.setAttribute("aria-label", "Finestre aperte");
            document.body.appendChild(taskbar);
        }
    }

    function focusWindow(id) {
        var entry = windows.get(id);
        if (!entry) {
            return;
        }
        zCounter += 1;
        entry.el.style.zIndex = String(1200 + zCounter);
        windows.forEach(function (w, wid) {
            w.el.classList.toggle("is-focused", wid === id);
        });
        renderTaskbar();
    }

    function closeWindow(id) {
        var entry = windows.get(id);
        if (!entry) {
            return;
        }
        entry.el.remove();
        windows.delete(id);
        renderTaskbar();
        if (windows.size === 0) {
            nextOffset = 0;
        }
    }

    function toggleMaximize(id) {
        var entry = windows.get(id);
        if (!entry) {
            return;
        }
        entry.el.classList.toggle("is-maximized");
        focusWindow(id);
    }

    function renderTaskbar() {
        if (!taskbar) {
            return;
        }
        taskbar.innerHTML = "";
        windows.forEach(function (entry, id) {
            var chip = document.createElement("button");
            chip.type = "button";
            chip.className =
                "mw-taskbar__chip" +
                (entry.el.classList.contains("is-focused") ? " is-active" : "");
            chip.textContent = entry.title;
            chip.title = entry.title;
            chip.addEventListener("click", function () {
                if (entry.el.classList.contains("is-minimized")) {
                    entry.el.classList.remove("is-minimized");
                    entry.el.style.display = "";
                }
                focusWindow(id);
            });
            taskbar.appendChild(chip);
        });
    }

    function bindDrag(titlebar, winEl, id) {
        var startX = 0;
        var startY = 0;
        var origLeft = 0;
        var origTop = 0;
        var dragging = false;

        function onMove(ev) {
            if (!dragging || winEl.classList.contains("is-maximized")) {
                return;
            }
            var dx = ev.clientX - startX;
            var dy = ev.clientY - startY;
            winEl.style.left = Math.max(0, origLeft + dx) + "px";
            winEl.style.top = Math.max(0, origTop + dy) + "px";
        }

        function onUp() {
            dragging = false;
            document.removeEventListener("pointermove", onMove);
            document.removeEventListener("pointerup", onUp);
        }

        titlebar.addEventListener("pointerdown", function (ev) {
            if (ev.button !== 0) {
                return;
            }
            if (ev.target.closest(".mw-window__btn")) {
                return;
            }
            if (winEl.classList.contains("is-maximized")) {
                focusWindow(id);
                return;
            }
            if (window.matchMedia("(max-width: 767.98px)").matches) {
                focusWindow(id);
                return;
            }
            dragging = true;
            startX = ev.clientX;
            startY = ev.clientY;
            origLeft = winEl.offsetLeft;
            origTop = winEl.offsetTop;
            focusWindow(id);
            titlebar.setPointerCapture(ev.pointerId);
            document.addEventListener("pointermove", onMove);
            document.addEventListener("pointerup", onUp);
        });
    }

    function openWindow(url, title) {
        if (!enabled || isEmbedContext()) {
            return false;
        }
        var embedUrl = withEmbed(url);
        if (!embedUrl || shouldSkip(url)) {
            return false;
        }

        ensureUi();

        var existing = null;
        windows.forEach(function (entry) {
            if (entry.url === embedUrl) {
                existing = entry;
            }
        });
        if (existing) {
            focusWindow(existing.id);
            return true;
        }

        var id = "mw-" + Date.now() + "-" + Math.floor(Math.random() * 1000);
        var offset = (nextOffset % 8) * CASCADE.x;
        nextOffset += 1;

        var sidebarWidth = 0;
        var sidebar = document.querySelector(".st-sidebar");
        if (sidebar && window.matchMedia("(min-width: 1400px)").matches) {
            sidebarWidth = document.body.classList.contains("st-sidebar-compact")
                ? 72
                : 260;
        }

        var winEl = document.createElement("div");
        winEl.className = "mw-window";
        winEl.dataset.mwId = id;
        winEl.style.left = sidebarWidth + 24 + offset + "px";
        winEl.style.top = 72 + offset + "px";

        var titlebar = document.createElement("div");
        titlebar.className = "mw-window__titlebar";
        titlebar.innerHTML =
            '<span class="mw-window__icon"><i class="ti ti-layout-board"></i></span>' +
            '<span class="mw-window__title"></span>' +
            '<span class="mw-window__actions">' +
            '<button type="button" class="mw-window__btn" data-mw-max title="Ingrandisci" aria-label="Ingrandisci"><i class="ti ti-square"></i></button>' +
            '<button type="button" class="mw-window__btn mw-window__btn--close" data-mw-close title="Chiudi" aria-label="Chiudi"><i class="ti ti-x"></i></button>' +
            "</span>";
        titlebar.querySelector(".mw-window__title").textContent = title || "Finestra";

        var body = document.createElement("div");
        body.className = "mw-window__body";
        var frame = document.createElement("iframe");
        frame.className = "mw-window__frame";
        frame.src = embedUrl;
        frame.title = title || "Finestra";
        body.appendChild(frame);

        winEl.appendChild(titlebar);
        winEl.appendChild(body);
        desktop.appendChild(winEl);

        titlebar.querySelector("[data-mw-close]").addEventListener("click", function () {
            closeWindow(id);
        });
        titlebar.querySelector("[data-mw-max]").addEventListener("click", function () {
            toggleMaximize(id);
        });
        winEl.addEventListener("mousedown", function () {
            focusWindow(id);
        });
        bindDrag(titlebar, winEl, id);

        windows.set(id, {
            id: id,
            el: winEl,
            url: embedUrl,
            title: title || "Finestra",
            frame: frame,
        });
        focusWindow(id);
        return true;
    }

    function setEnabled(value) {
        enabled = !!value;
        writeEnabled(enabled);
        document.body.classList.toggle("st-mw-on", enabled);
        var btn = document.querySelector("[data-mw-toggle]");
        if (btn) {
            btn.classList.toggle("is-mw-active", enabled);
            var label = enabled ? "Disattiva multi-finestra" : "Attiva multi-finestra";
            btn.setAttribute("aria-label", label);
            btn.setAttribute("title", label + " (i link del menu aprono finestre)");
            btn.setAttribute("aria-pressed", enabled ? "true" : "false");
        }
        if (!enabled) {
            windows.forEach(function (_entry, id) {
                closeWindow(id);
            });
            if (taskbar) {
                taskbar.innerHTML = "";
            }
        } else {
            ensureUi();
        }
    }

    function onSidebarClick(ev) {
        if (!enabled || isEmbedContext()) {
            return;
        }
        if (ev.defaultPrevented || ev.button !== 0) {
            return;
        }
        if (ev.metaKey || ev.ctrlKey || ev.shiftKey || ev.altKey) {
            return;
        }
        var link = ev.target.closest("a[href]");
        if (!link || !link.closest(".st-sidebar")) {
            return;
        }
        var href = link.getAttribute("href");
        if (!href || href.charAt(0) === "#") {
            return;
        }
        if (shouldSkip(href, link)) {
            return;
        }
        ev.preventDefault();
        openWindow(href, titleFromLink(link, href));
        if (window.matchMedia("(max-width: 1399.98px)").matches) {
            document.body.classList.remove("st-sidebar-open");
            var backdrop = document.querySelector("[data-sidebar-backdrop]");
            if (backdrop) {
                backdrop.hidden = true;
            }
        }
    }

    function init() {
        if (isEmbedContext()) {
            return;
        }

        ensureUi();
        setEnabled(readEnabled());

        var btn = document.querySelector("[data-mw-toggle]");
        if (btn) {
            btn.addEventListener("click", function () {
                setEnabled(!enabled);
            });
        }

        document.addEventListener("click", onSidebarClick, true);
        window.addEventListener("eureka:sidebar-compact", function () {
            if (enabled) {
                ensureUi();
            }
        });

        window.EurekaMultiWindow = {
            open: openWindow,
            enable: function () {
                setEnabled(true);
            },
            disable: function () {
                setEnabled(false);
            },
            isEnabled: function () {
                return enabled;
            },
        };
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", init);
    } else {
        init();
    }
})();
