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

    if (!toggleButton) {
        return;
    }

    toggleButton.addEventListener("click", function () {
        applyTheme(getCurrentTheme() === "dark" ? "light" : "dark");
    });
});

document.addEventListener("DOMContentLoaded", function () {
    const STORAGE_KEY = "eureka-sidebar-sections";
    const sections = Array.from(document.querySelectorAll("[data-nav-section]"));

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
        });
    });
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
