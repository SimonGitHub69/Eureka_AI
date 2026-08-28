/**
 * Documenti — collapsible sections (testata + scadenze + righe).
 * State key: eureka.doc.{section}.{view}.{tipo}  (1 = open, 0 = collapsed)
 *
 * Markup:
 *   [data-eureka-doc-collapse]
 *   data-doc-section="testata"|"scadenze"|"righe"
 *   data-doc-view="detail"|"form"
 *   data-doc-tipo="PRV"
 *   data-doc-default="open"|"collapsed"   (optional; default open)
 *   data-doc-count / data-doc-threshold   (optional; righe auto-collapse)
 *
 * Legacy [data-eureka-doc-righe] still works (maps to section=righe).
 */
(function () {
  const THRESHOLD_DEFAULT = 10;

  function sectionOf(el) {
    return (
      (el.getAttribute("data-doc-section") || "").trim() ||
      (el.hasAttribute("data-eureka-doc-righe") ? "righe" : "section")
    );
  }

  function viewOf(el) {
    return (
      (el.getAttribute("data-doc-view") || "").trim() ||
      (el.getAttribute("data-righe-view") || "detail").trim()
    );
  }

  function tipoOf(el) {
    return (
      (el.getAttribute("data-doc-tipo") || "").trim() ||
      (el.getAttribute("data-righe-tipo") || "DOC").trim()
    );
  }

  function storageKey(el) {
    return "eureka.doc." + sectionOf(el) + "." + viewOf(el) + "." + tipoOf(el);
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

  function labelOf(el) {
    const s = sectionOf(el);
    if (s === "testata") return "testata";
    if (s === "scadenze") return "scadenze";
    if (s === "righe") return "righe";
    return "sezione";
  }

  function defaultOpen(el) {
    const forced = (el.getAttribute("data-doc-default") || "").trim().toLowerCase();
    if (forced === "open" || forced === "expanded") return true;
    if (forced === "collapsed" || forced === "closed") return false;

    const countAttr =
      el.getAttribute("data-doc-count") ?? el.getAttribute("data-righe-count");
    if (countAttr !== null && countAttr !== undefined && countAttr !== "") {
      const count = parseInt(countAttr, 10);
      const thr = parseInt(
        el.getAttribute("data-doc-threshold") ||
          el.getAttribute("data-righe-threshold") ||
          String(THRESHOLD_DEFAULT),
        10
      );
      if (!Number.isNaN(count) && !Number.isNaN(thr)) return count <= thr;
    }
    return true;
  }

  function setOpen(el, open, persist) {
    el.classList.toggle("is-collapsed", !open);
    const toggle = el.querySelector("[data-doc-toggle], [data-righe-toggle]");
    const label = labelOf(el);
    if (toggle) {
      toggle.setAttribute("aria-expanded", open ? "true" : "false");
      toggle.setAttribute(
        "title",
        open ? "Comprimi " + label : "Espandi " + label
      );
    }
    const summary = el.querySelector("[data-doc-summary]");
    if (summary) {
      summary.hidden = open;
      summary.setAttribute("aria-hidden", open ? "true" : "false");
    }
    if (persist) writeStored(storageKey(el), open);
  }

  function bind(el) {
    const key = storageKey(el);
    const stored = readStored(key);
    const open = stored === null ? defaultOpen(el) : stored;
    setOpen(el, open, false);

    const toggle = el.querySelector("[data-doc-toggle], [data-righe-toggle]");
    if (!toggle) return;

    toggle.addEventListener("click", (ev) => {
      ev.preventDefault();
      const next = el.classList.contains("is-collapsed");
      setOpen(el, next, true);
    });
  }

  function init() {
    document
      .querySelectorAll("[data-eureka-doc-collapse], [data-eureka-doc-righe]")
      .forEach(bind);
  }

  const api = {
    expand: function (el) {
      if (!el) return;
      setOpen(el, true, true);
    },
    collapse: function (el) {
      if (!el) return;
      setOpen(el, false, true);
    },
    init: init,
  };

  window.EurekaDocCollapse = api;
  /** @deprecated use EurekaDocCollapse */
  window.EurekaDocRighe = api;

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();

/**
 * Client-side filter on document line items (righe).
 * Matches codice OR descrizione (case-insensitive, trim).
 * Empty query → show all non-deleted rows.
 *
 * Markup:
 *   [data-doc-righe-filter]  — search input inside #righeCard / .eureka-doc-righe
 *   [data-riga-row]          — form rows (inputs name$=-codice / -descrizione)
 *   [data-doc-line]          — detail rows (optional data-codice / data-descrizione)
 */
(function () {
  const HIDE_CLASS = "eureka-doc-riga--nomatch";

  function cardOf(el) {
    return el.closest("#righeCard, .eureka-doc-righe, [data-eureka-doc-righe]");
  }

  function rowText(row) {
    const codiceInput =
      row.querySelector("input[name$='-codice'], textarea[name$='-codice']");
    const descInput =
      row.querySelector(
        "input[name$='-descrizione'], textarea[name$='-descrizione']"
      );
    if (codiceInput || descInput) {
      return {
        codice: ((codiceInput && codiceInput.value) || "").trim(),
        descrizione: ((descInput && descInput.value) || "").trim(),
      };
    }
    const codice =
      (row.getAttribute("data-codice") || "").trim() ||
      (
        (row.querySelector(".eureka-doc-line-code") || {}).textContent ||
        ""
      ).trim();
    const descrizione =
      (row.getAttribute("data-descrizione") || "").trim() ||
      (
        (row.querySelector("[data-long-text-view]") || {}).textContent ||
        ""
      ).trim();
    return { codice, descrizione };
  }

  function isDeleted(row) {
    if (row.classList.contains("d-none")) return true;
    const del =
      row.querySelector(
        ".riga-delete-input, input[type='checkbox'][name$='-DELETE']"
      );
    return Boolean(del && del.checked);
  }

  function matches(row, q) {
    if (!q) return true;
    const t = rowText(row);
    const needle = q.toLowerCase();
    return (
      t.codice.toLowerCase().includes(needle) ||
      t.descrizione.toLowerCase().includes(needle)
    );
  }

  function apply(input) {
    const card = cardOf(input);
    if (!card) return;
    const q = (input.value || "").trim();
    if (q && card.classList.contains("is-collapsed") && window.EurekaDocCollapse) {
      window.EurekaDocCollapse.expand(card);
    }
    const rows = card.querySelectorAll("[data-riga-row], [data-doc-line]");
    let visible = 0;
    rows.forEach((row) => {
      if (isDeleted(row)) {
        row.classList.remove(HIDE_CLASS);
        return;
      }
      const ok = matches(row, q);
      row.classList.toggle(HIDE_CLASS, !ok);
      if (ok) visible += 1;
    });
    const empty = card.querySelector("[data-doc-righe-filter-empty]");
    if (empty) {
      empty.hidden = !q || visible > 0;
    }
    const badge = card.querySelector(
      "#righeCountBadge, .eureka-doc-collapse__count"
    );
    if (badge && q) {
      const total = Array.from(rows).filter((r) => !isDeleted(r)).length;
      badge.textContent = visible + "/" + total;
      badge.title = "Righe filtrate: " + visible + " di " + total;
    } else if (badge && !q) {
      const total = Array.from(rows).filter((r) => !isDeleted(r)).length;
      badge.textContent = String(total);
      badge.title = "Numero righe";
    }
  }

  function clearAndApply(input) {
    if (!input) return;
    if (input.value) {
      input.value = "";
      apply(input);
    }
  }

  function refresh(cardOrEl) {
    const card = cardOf(cardOrEl) || cardOrEl;
    if (!card || !card.querySelector) return;
    const input = card.querySelector("[data-doc-righe-filter]");
    if (input) apply(input);
  }

  function bind(input) {
    input.addEventListener("input", () => apply(input));
    input.addEventListener("search", () => apply(input));
    input.addEventListener("keydown", (ev) => {
      if (ev.key !== "Escape") return;
      clearAndApply(input);
      input.blur();
    });
    apply(input);
  }

  function init() {
    document.querySelectorAll("[data-doc-righe-filter]").forEach(bind);

    // New row while filtering: clear filter so the blank line stays visible.
    document.addEventListener("click", (ev) => {
      const addBtn = ev.target.closest("[data-add-riga]");
      if (!addBtn) return;
      const card = cardOf(addBtn) || document.getElementById("righeCard");
      const input = card && card.querySelector("[data-doc-righe-filter]");
      clearAndApply(input);
    });

    // Re-filter when editing codice/descrizione with an active query.
    document.addEventListener("input", (ev) => {
      const field = ev.target;
      if (!field || !field.name) return;
      if (!/-(codice|descrizione)$/.test(field.name)) return;
      const card = cardOf(field);
      const input = card && card.querySelector("[data-doc-righe-filter]");
      if (input && (input.value || "").trim()) apply(input);
    });
  }

  window.EurekaDocRigheFilter = { init: init, apply: apply, refresh: refresh };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
