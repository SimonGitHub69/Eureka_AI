/**
 * Card maschera comprimibili.
 * Markup: [data-eureka-mask-collapse] + [data-mask-toggle]
 * Opzionale: data-mask-section, data-mask-view, data-mask-default="open"|"collapsed"
 * Riepilogo chiuso: [data-mask-summary] [data-summary-from="id_campo"]
 */
(function () {
  function storageKey(el) {
    const section = (el.getAttribute("data-mask-section") || "card").trim();
    const view = (el.getAttribute("data-mask-view") || "form").trim();
    return "eureka.mask." + section + "." + view;
  }

  function readStored(key) {
    try {
      const v = localStorage.getItem(key);
      if (v === "1") return true;
      if (v === "0") return false;
    } catch (_) { /* ignore */ }
    return null;
  }

  function writeStored(key, open) {
    try {
      localStorage.setItem(key, open ? "1" : "0");
    } catch (_) { /* ignore */ }
  }

  function defaultOpen(el) {
    const forced = (el.getAttribute("data-mask-default") || "").trim().toLowerCase();
    if (forced === "collapsed" || forced === "closed") return false;
    return true;
  }

  function formatDate(value) {
    const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(value || "");
    if (m) return m[3] + "/" + m[2] + "/" + m[1];
    return value || "";
  }

  function linkedLabelText(id) {
    if (!id) return "";
    const sel = '[data-linked-label][data-for-input="' + id + '"] .eureka-linked-label__text';
    const label = document.querySelector(sel);
    return (label && label.textContent ? label.textContent : "").trim();
  }

  function selectExtraLabel(id) {
    const src = document.getElementById(id);
    if (!src || src.tagName !== "SELECT") return "";
    const opt = src.options[src.selectedIndex];
    const text = (opt && opt.text ? opt.text : "").trim();
    const value = (src.value || "").trim();
    if (!text || text === "—" || text === "---------") return "";
    const prefix = value + " — ";
    if (value && text.startsWith(prefix)) return text.slice(prefix.length).trim();
    return "";
  }

  function fieldText(id, kind) {
    if (kind === "linked-label") return linkedLabelText(id);
    if (kind === "select-extra") return selectExtraLabel(id);
    const src = document.getElementById(id);
    if (!src) return "";
    if (kind === "value") return (src.value || "").trim();
    if (src.tagName === "SELECT") {
      const opt = src.options[src.selectedIndex];
      const text = (opt && opt.text ? opt.text : "").trim();
      if (!text || text === "—" || text === "---------") return "";
      return text;
    }
    const raw = (src.value || "").trim();
    if (!raw) return "";
    if (kind === "date") return formatDate(raw);
    return raw;
  }

  function fillSummary(el) {
    el.querySelectorAll("[data-summary-from]").forEach((chip) => {
      const text = fieldText(
        chip.getAttribute("data-summary-from"),
        chip.getAttribute("data-summary-kind")
      );
      chip.textContent = text;
      chip.hidden = !text;
    });
  }

  function setOpen(el, open, persist) {
    el.classList.toggle("is-collapsed", !open);
    const toggle = el.querySelector("[data-mask-toggle]");
    const label = (el.getAttribute("data-mask-section") || "sezione").trim();
    if (toggle) {
      toggle.setAttribute("aria-expanded", open ? "true" : "false");
      toggle.setAttribute(
        "title",
        open ? "Comprimi " + label : "Espandi " + label
      );
    }
    const summary = el.querySelector("[data-mask-summary]");
    if (summary) {
      if (!open) fillSummary(el);
      summary.hidden = open;
      summary.setAttribute("aria-hidden", open ? "true" : "false");
    }
    if (persist) writeStored(storageKey(el), open);
  }

  function fieldIsVisible(id) {
    const src = document.getElementById(id);
    if (!src) return false;
    return !src.closest(".d-none");
  }

  function isCardEmpty(el) {
    const ids = (el.getAttribute("data-mask-empty-from") || "")
      .trim()
      .split(/\s+/)
      .filter(Boolean);
    if (!ids.length) return false;
    const visible = ids.filter(fieldIsVisible);
    if (!visible.length) return true;
    return visible.every((id) => !fieldText(id, "value"));
  }

  function bind(el) {
    const stored = readStored(storageKey(el));
    let open = stored === null ? defaultOpen(el) : stored;
    if ((el.getAttribute("data-mask-empty") || "").trim() === "collapsed" && isCardEmpty(el)) {
      open = false;
    }
    setOpen(el, open, false);
    const toggle = el.querySelector("[data-mask-toggle]");
    if (toggle) {
      toggle.addEventListener("click", (ev) => {
        ev.preventDefault();
        setOpen(el, el.classList.contains("is-collapsed"), true);
      });
    }
    el.querySelectorAll("[data-add-riga]").forEach((btn) => {
      btn.addEventListener("click", () => setOpen(el, true, true));
    });
  }

  function init() {
    document.querySelectorAll("[data-eureka-mask-collapse]").forEach(bind);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
