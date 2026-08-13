(function () {
    "use strict";

    function isVisibleError(el) {
        if (!el) {
            return false;
        }
        if (el.closest(".d-none, [hidden]")) {
            return false;
        }
        if (el.closest(".modal:not(.show)")) {
            return false;
        }
        const style = window.getComputedStyle(el);
        if (style.display === "none" || style.visibility === "hidden") {
            return false;
        }
        return true;
    }

    function hasVisibleMatch(selector) {
        return Array.from(document.querySelectorAll(selector)).some(isVisibleError);
    }

    function pageHasErrors() {
        if (hasVisibleMatch("[data-eureka-error-sound]")) {
            return true;
        }
        if (hasVisibleMatch(".alert-danger, .alert-error")) {
            return true;
        }
        if (hasVisibleMatch(".is-invalid, ul.errorlist, .invalid-feedback.d-block")) {
            return true;
        }
        return false;
    }

    function getConfiguredSoundUrl() {
        if (window.EUREKA_ERROR_SOUND_ENABLED === false) {
            return "";
        }
        return (window.EUREKA_ERROR_SOUND_URL || "").trim();
    }

    async function playErrorSound(urlOverride) {
        const url = (urlOverride || getConfiguredSoundUrl()).trim();
        if (!url) {
            return;
        }

        const audio = new Audio(url);
        audio.preload = "auto";
        audio.volume = 1;

        try {
            await audio.play();
        } catch (error) {
            /* autoplay policy: ignora silenziosamente */
        }
    }

    function focusFirstInvalidField() {
        const target = document.querySelector(
            ".is-invalid, ul.errorlist li, .alert-danger, .alert-error"
        );
        if (!target) {
            return;
        }
        const field = target.closest(".col-sm-4, .col-12, .col-md-4, .col-sm-6")
            || target.closest("form")
            || target;
        if (typeof field.scrollIntoView === "function") {
            field.scrollIntoView({ behavior: "smooth", block: "center" });
        }
        const input = field.querySelector
            ? field.querySelector("input:not([type='hidden']), select, textarea")
            : null;
        if (input && typeof input.focus === "function") {
            window.setTimeout(function () {
                input.focus({ preventScroll: true });
            }, 350);
        }
    }

    function initErrorFeedback() {
        if (!pageHasErrors()) {
            return;
        }
        playErrorSound();
        focusFirstInvalidField();
    }

    function initSoundTestButtons() {
        document.querySelectorAll("[data-test-error-sound]").forEach(function (button) {
            button.addEventListener("click", function () {
                const url = button.getAttribute("data-sound-url") || getConfiguredSoundUrl();
                playErrorSound(url);
            });
        });
    }

    window.EurekaErrorSound = {
        play: playErrorSound,
    };

    document.addEventListener("DOMContentLoaded", function () {
        initErrorFeedback();
        initSoundTestButtons();
    });
})();
