(function () {
    function isLoginForm(field) {
        const form = field.closest("form");

        if (!form) {
            return false;
        }

        const action = (form.getAttribute("action") || "").toLowerCase();
        const path = window.location.pathname.toLowerCase();

        return (
            path.includes("/login") ||
            path.includes("/admin/login") ||
            action.includes("/login") ||
            form.id === "login-form"
        );
    }

    function shouldSkipField(field) {
        if (field.closest('[data-autocomplete="on"]')) {
            return true;
        }

        const type = (field.getAttribute("type") || "").toLowerCase();

        if (type === "password" && isLoginForm(field)) {
            return true;
        }

        return (
            type === "hidden" ||
            type === "submit" ||
            type === "button" ||
            type === "reset" ||
            type === "checkbox" ||
            type === "radio" ||
            type === "file" ||
            field.id === "searchbar" ||
            field.name === "q"
        );
    }

    function isTextLikeField(field) {
        const type = (field.getAttribute("type") || "").toLowerCase();

        return (
            field.tagName === "TEXTAREA" ||
            type === "text" ||
            type === "search" ||
            type === "email" ||
            type === "tel" ||
            type === "url" ||
            type === "number" ||
            type === ""
        );
    }

    function isAutofillSensitiveField(field) {
        const type = (field.getAttribute("type") || "").toLowerCase();
        const name = (field.getAttribute("name") || "").toLowerCase();
        const id = (field.getAttribute("id") || "").toLowerCase();
        const labelText =
            field.labels && field.labels.length
                ? Array.from(field.labels)
                      .map(function (label) {
                          return label.textContent || "";
                      })
                      .join(" ")
                      .toLowerCase()
                : "";
        const haystack = name + " " + id + " " + labelText;

        return (
            type === "email" ||
            type === "tel" ||
            /email|e-mail|mail|telefono|phone|tel|cellulare|pec|indirizzo|address|citta|city|cap|zip|denominazione|ragione|nome|cognome|titolo|username|password|host|porta|smtp|mittente|destinatari|partita|piva|fiscale|codice_fiscale|codice fiscale|vat|tax|valore|contatto|contatti|civico|comune|provincia|nazione|descrizione/.test(
                haystack
            )
        );
    }

    function neutralizeAutofillType(field) {
        const type = (field.getAttribute("type") || "").toLowerCase();

        if (type === "email") {
            field.setAttribute("type", "text");
            field.setAttribute("inputmode", "email");
        } else if (type === "tel") {
            field.setAttribute("type", "text");
            field.setAttribute("inputmode", "tel");
        }
    }

    function shouldApplyReadonlyGuard(field) {
        if (isLoginForm(field)) {
            return false;
        }

        const type = (field.getAttribute("type") || "").toLowerCase();

        return isTextLikeField(field) || type === "password";
    }

    function obfuscateFieldName(field) {
        if (!isAutofillSensitiveField(field) || field.dataset.originalName) {
            return;
        }

        const originalName = field.getAttribute("name");

        if (!originalName) {
            return;
        }

        field.dataset.originalName = originalName;
        field.setAttribute(
            "name",
            "st_" + Math.random().toString(36).slice(2, 10) + "_" + originalName.replace(/[^a-z0-9_]/gi, "")
        );
    }

    function restoreFieldNames(form) {
        form.querySelectorAll("[data-original-name]").forEach(function (field) {
            field.setAttribute("name", field.dataset.originalName);
        });
    }

    function bindFormSubmitRestore(form) {
        if (form.dataset.autocompleteSubmitBound === "true") {
            return;
        }

        form.dataset.autocompleteSubmitBound = "true";

        form.addEventListener(
            "submit",
            function () {
                restoreFieldNames(form);
            },
            true
        );
    }

    function disableField(field) {
        if (shouldSkipField(field)) {
            return;
        }

        neutralizeAutofillType(field);
        obfuscateFieldName(field);

        if (isTextLikeField(field) || (field.getAttribute("type") || "").toLowerCase() === "password") {
            field.setAttribute("autocomplete", "new-password");
        } else {
            field.setAttribute("autocomplete", "off");
        }

        field.setAttribute("autocorrect", "off");
        field.setAttribute("autocapitalize", "off");
        field.setAttribute("spellcheck", "false");
        field.setAttribute("data-lpignore", "true");
        field.setAttribute("data-1p-ignore", "true");

        if (!shouldApplyReadonlyGuard(field) || field.dataset.autocompleteGuard === "true") {
            return;
        }

        field.dataset.autocompleteGuard = "true";

        function clearReadonlyGuard() {
            field.removeAttribute("readonly");
        }

        function restoreReadonlyGuard() {
            field.setAttribute("readonly", "readonly");
        }

        if (!field.hasAttribute("readonly")) {
            field.setAttribute("readonly", "readonly");
        }

        field.addEventListener("mousedown", clearReadonlyGuard);
        field.addEventListener("touchstart", clearReadonlyGuard, { passive: true });
        field.addEventListener("focus", clearReadonlyGuard);
        field.addEventListener("blur", restoreReadonlyGuard);
    }

    function disableBrowserAutocomplete(root) {
        const scope = root && root.querySelectorAll ? root : document;

        scope.querySelectorAll("form").forEach(function (form) {
            if (form.dataset.autocomplete === "on") {
                return;
            }

            form.setAttribute("autocomplete", "off");
            bindFormSubmitRestore(form);
        });

        scope.querySelectorAll("input, textarea, select").forEach(disableField);
    }

    function initAutocompleteGuard() {
        disableBrowserAutocomplete(document);

        if (typeof MutationObserver === "undefined" || !document.body) {
            return;
        }

        const observer = new MutationObserver(function (mutations) {
            mutations.forEach(function (mutation) {
                mutation.addedNodes.forEach(function (node) {
                    if (node.nodeType === 1) {
                        disableBrowserAutocomplete(node);
                    }
                });
            });
        });

        observer.observe(document.body, { childList: true, subtree: true });
    }

    window.SecurtekDisableAutocomplete = disableBrowserAutocomplete;

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", initAutocompleteGuard);
    } else {
        initAutocompleteGuard();
    }

    document.addEventListener("htmx:afterSwap", function (event) {
        if (event.detail && event.detail.target) {
            disableBrowserAutocomplete(event.detail.target);
        }
    });
})();
