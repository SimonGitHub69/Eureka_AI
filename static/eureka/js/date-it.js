/**
 * EurekaDateIT — maschera date gg/mm/aaaa + calendario (Mac/Windows uguali).
 * Auto-enhance: input[type=date] e [data-eureka-date-it]
 * Al submit: value inviato in ISO YYYY-MM-DD.
 */
(function () {
  const ISO_RE = /^(\d{4})-(\d{2})-(\d{2})$/;
  const IT_RE = /^(\d{1,2})[./-](\d{1,2})[./-](\d{4})$/;

  function isoToIt(iso) {
    const m = String(iso || "").trim().match(ISO_RE);
    if (!m) return String(iso || "").trim();
    return m[3] + "/" + m[2] + "/" + m[1];
  }

  function itToIso(it) {
    const raw = String(it || "").trim();
    if (ISO_RE.test(raw)) return raw.slice(0, 10);
    const m = raw.match(IT_RE);
    if (!m) return "";
    const d = m[1].padStart(2, "0");
    const mo = m[2].padStart(2, "0");
    const y = m[3];
    const dt = new Date(Number(y), Number(mo) - 1, Number(d));
    if (
      dt.getFullYear() !== Number(y) ||
      dt.getMonth() !== Number(mo) - 1 ||
      dt.getDate() !== Number(d)
    ) {
      return "";
    }
    return y + "-" + mo + "-" + d;
  }

  function digitsOnly(s) {
    return String(s || "").replace(/\D/g, "").slice(0, 8);
  }

  function maskWhileTyping(raw) {
    const d = digitsOnly(raw);
    if (d.length <= 2) return d;
    if (d.length <= 4) return d.slice(0, 2) + "/" + d.slice(2);
    return d.slice(0, 2) + "/" + d.slice(2, 4) + "/" + d.slice(4);
  }

  function getIso(el) {
    if (!el) return "";
    return (el.dataset.iso || itToIso(el.value) || "").trim();
  }

  function syncNative(el, iso) {
    const native = el._eurekaDateNative;
    if (native && native.value !== (iso || "")) {
      native.value = iso || "";
    }
  }

  function applyDisplay(el, iso) {
    const v = String(iso || "").trim();
    if (!v) {
      el.dataset.iso = "";
      el.value = "";
      syncNative(el, "");
      el.classList.remove("is-invalid");
      return;
    }
    const norm = itToIso(v) || (ISO_RE.test(v) ? v.slice(0, 10) : "");
    el.dataset.iso = norm;
    el.value = norm ? isoToIt(norm) : v;
    syncNative(el, norm);
    el.classList.toggle("is-invalid", Boolean(el.value) && !norm);
  }

  function bindCalendarControls(el, wrap) {
    let native = wrap.querySelector(".eureka-date-it__native");
    let icon = wrap.querySelector(".eureka-date-it__cal");

    if (!icon) {
      icon = document.createElement("button");
      icon.type = "button";
      icon.className = "eureka-date-it__cal";
      icon.setAttribute("aria-label", "Apri calendario");
      icon.tabIndex = -1;
      icon.innerHTML =
        '<svg viewBox="0 0 24 24" width="16" height="16" focusable="false" aria-hidden="true">' +
        '<path fill="currentColor" d="M7 2a1 1 0 0 1 1 1v1h8V3a1 1 0 1 1 2 0v1h1a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h1V3a1 1 0 0 1 1-1zm12 8H5v10h14V10zM8 12h2v2H8v-2zm4 0h2v2h-2v-2zm4 0h2v2h-2v-2z"/>' +
        "</svg>";
      wrap.appendChild(icon);
    } else if (icon.tagName === "SPAN") {
      // Partial HTML usava <span>: rendilo cliccabile
      icon.setAttribute("role", "button");
      icon.tabIndex = 0;
      icon.setAttribute("aria-label", "Apri calendario");
    }

    if (!native) {
      native = document.createElement("input");
      native.type = "date";
      native.className = "eureka-date-it__native";
      native.tabIndex = -1;
      native.setAttribute("aria-hidden", "true");
      wrap.appendChild(native);
    }

    if (native.dataset.eurekaBound === "1") {
      el._eurekaDateNative = native;
      return native;
    }
    native.dataset.eurekaBound = "1";

    const openPicker = (ev) => {
      if (ev) {
        ev.preventDefault();
        ev.stopPropagation();
      }
      native.value = getIso(el) || "";
      // Deve restare "visibile" per showPicker (opacity > 0, dimensioni > 0)
      try {
        if (typeof native.showPicker === "function") {
          native.showPicker();
          return;
        }
      } catch (_) {
        /* fall through */
      }
      try {
        native.focus({ preventScroll: true });
        native.click();
      } catch (_) {
        /* ignore */
      }
    };

    native.addEventListener("change", () => {
      if (native.value) applyDisplay(el, native.value);
      el.dispatchEvent(new Event("input", { bubbles: true }));
      el.dispatchEvent(new Event("change", { bubbles: true }));
    });

    icon.addEventListener("click", openPicker);
    icon.addEventListener("keydown", (ev) => {
      if (ev.key === "Enter" || ev.key === " ") openPicker(ev);
    });

    el._eurekaDateNative = native;
    return native;
  }

  function wrapWithCalendar(el) {
    if (el.parentElement && el.parentElement.classList.contains("eureka-date-it")) {
      return bindCalendarControls(el, el.parentElement);
    }

    const wrap = document.createElement("div");
    wrap.className = "eureka-date-it";
    el.parentNode.insertBefore(wrap, el);
    wrap.appendChild(el);
    return bindCalendarControls(el, wrap);
  }

  function enhance(el) {
    if (!el || el.dataset.eurekaDateReady === "1") return;
    if (el.classList.contains("eureka-date-it__native")) return;
    if (!el.parentNode) return;

    const initial = (el.value || el.getAttribute("value") || "").trim();

    el.dataset.eurekaDateReady = "1";
    el.setAttribute("data-eureka-date-it", "1");
    el.setAttribute("data-lpignore", "true");
    el.setAttribute("data-1p-ignore", "true");
    el.removeAttribute("readonly");
    if (el.dataset.originalName) {
      el.setAttribute("name", el.dataset.originalName);
      delete el.dataset.originalName;
    }
    delete el.dataset.autocompleteGuard;
    delete el.dataset.fieldLocked;

    if (el.type === "date") {
      try {
        el.type = "text";
      } catch (_) {
        /* ignore */
      }
    }

    el.classList.add("eureka-date-it__input");
    if (el.classList.contains("eureka-print-input")) {
      el.classList.add("eureka-print-input--date");
    }
    el.setAttribute("inputmode", "numeric");
    el.setAttribute("placeholder", "gg/mm/aaaa");
    el.setAttribute("autocomplete", "off");
    el.setAttribute("maxlength", "10");
    el.setAttribute("spellcheck", "false");

    wrapWithCalendar(el);
    applyDisplay(el, initial);

    el.addEventListener("focus", () => {
      el.removeAttribute("readonly");
      try {
        el.select();
      } catch (_) {}
    });

    el.addEventListener("input", () => {
      const before = el.value;
      const masked = maskWhileTyping(before);
      if (masked !== before) {
        el.value = masked;
        const pos = masked.length;
        try {
          el.setSelectionRange(pos, pos);
        } catch (_) {}
      }
      const iso = itToIso(el.value);
      el.dataset.iso = iso;
      syncNative(el, iso);
      el.classList.toggle("is-invalid", Boolean(el.value) && !iso);
    });

    el.addEventListener("blur", () => {
      const iso = itToIso(el.value);
      if (iso) applyDisplay(el, iso);
      else if (!String(el.value || "").trim()) applyDisplay(el, "");
    });

    const form = el.form;
    if (form && !form.dataset.eurekaDateSubmit) {
      form.dataset.eurekaDateSubmit = "1";
      form.addEventListener(
        "submit",
        () => {
          form.querySelectorAll("[data-eureka-date-it]").forEach((field) => {
            if (field.classList.contains("eureka-date-it__native")) return;
            const iso = getIso(field);
            if (iso) field.value = iso;
          });
        },
        true
      );
    }
  }

  function matches(el) {
    if (!el || el.tagName !== "INPUT") return false;
    if (el.classList.contains("eureka-date-it__native")) return false;
    if (el.hasAttribute("data-eureka-date-it")) return true;
    if (el.getAttribute("type") === "date") return true;
    return false;
  }

  function boot(root) {
    const scope = root && root.querySelectorAll ? root : document;
    scope.querySelectorAll('input[type="date"], [data-eureka-date-it]').forEach(enhance);
  }

  function setFromIso(el, iso) {
    if (!el) return;
    if (el.dataset.eurekaDateReady !== "1") enhance(el);
    applyDisplay(el, iso);
  }

  function refresh(el) {
    if (!el) return;
    const pending = el.dataset.iso || el.value;
    if (el.dataset.eurekaDateReady !== "1") enhance(el);
    else applyDisplay(el, pending);
  }

  const api = {
    isoToIt: isoToIt,
    itToIso: itToIso,
    getIso: getIso,
    setFromIso: setFromIso,
    refresh: refresh,
    boot: boot,
    enhance: enhance,
  };

  window.EurekaDateIT = api;
  window.EurekaPrintDateIT = api;

  function start() {
    boot();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", start);
  } else {
    start();
  }

  // Conversione ISO su ogni submit (anche form aggiunti dopo)
  if (!window.__eurekaDateSubmitBound) {
    window.__eurekaDateSubmitBound = true;
    document.addEventListener(
      "submit",
      (ev) => {
        const form = ev.target;
        if (!form || !form.querySelectorAll) return;
        form.querySelectorAll("input.eureka-date-it__input, input[data-eureka-date-it]").forEach((field) => {
          if (field.classList.contains("eureka-date-it__native")) return;
          const iso = getIso(field);
          if (iso) field.value = iso;
        });
      },
      true
    );
  }

  // Rieffettua dopo un tick: cattura input resi dal browser / script successivi
  setTimeout(start, 0);
  setTimeout(start, 50);

  document.addEventListener("htmx:afterSwap", function (event) {
    if (event.detail && event.detail.target) boot(event.detail.target);
  });

  if (typeof MutationObserver === "function") {
    const mo = new MutationObserver((mutations) => {
      mutations.forEach((m) => {
        m.addedNodes.forEach((node) => {
          if (node.nodeType !== 1) return;
          if (matches(node)) enhance(node);
          if (node.querySelectorAll) {
            node
              .querySelectorAll('input[type="date"], [data-eureka-date-it]')
              .forEach(enhance);
          }
        });
      });
    });
    const startObs = () => {
      if (document.body) mo.observe(document.body, { childList: true, subtree: true });
    };
    if (document.body) startObs();
    else document.addEventListener("DOMContentLoaded", startObs);
  }
})();
