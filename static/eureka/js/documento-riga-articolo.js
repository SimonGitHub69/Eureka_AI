/**
 * Documento righe: ricerca articolo in CODICE / DESCRIZIONE (combobox portaled)
 * + blur/Enter exact lookup via /articoli/lookup-codice/?tipo=articolo&codice=...
 *
 * Markup: #documentoForm[data-articolo-lookup-url]
 * Ricerca lista: ?tipo=articolo&q=...&limit=40
 * Combo shell + freccia: .eureka-combo[data-articolo-combo] su codice/descrizione
 */
(() => {
  const form = document.getElementById("documentoForm");
  if (!form) return;
  const url = (form.getAttribute("data-articolo-lookup-url") || "").trim();
  if (!url) return;
  const lastResolved = new WeakMap();
  const inflight = new WeakMap();
  const searchTimers = new WeakMap();
  let openMenu = null;
  let searchSeq = 0;
  let suppressSearch = false;
  const menu = document.createElement("div");
  menu.className = "eureka-combo__menu eureka-doc-articolo-combo-menu";
  menu.setAttribute("data-articolo-combo-menu", "");
  menu.setAttribute("role", "listbox");
  menu.hidden = true;
  document.body.appendChild(menu);
  function rowOf(el) {
    return el && el.closest ? el.closest("[data-riga-row]") : null;
  }
  function field(row, name) {
    return (
      row.querySelector(`[name$='-${name}']`) ||
      row.querySelector(`[id$='-${name}']`)
    );
  }
  function fieldKind(el) {
    if (!el || !el.name || !rowOf(el)) return null;
    if (/-(codice)$/.test(el.name)) return "codice";
    if (/-(descrizione)$/.test(el.name)) return "descrizione";
    return null;
  }
  function isCodiceInput(el) {
    return fieldKind(el) === "codice";
  }
  function isArticoloSearchInput(el) {
    return fieldKind(el) === "codice" || fieldKind(el) === "descrizione";
  }
  function setValue(el, value, { force } = {}) {
    if (!el) return false;
    const next = value == null ? "" : String(value);
    if (!force && String(el.value || "") === next) return false;
    el.value = next;
    el.dispatchEvent(new Event("input", { bubbles: true }));
    el.dispatchEvent(new Event("change", { bubbles: true }));
    return true;
  }
  function formatPrezzoUnitario(value) {
    if (value == null || value === "") return "";
    const n = Number(String(value).trim().replace(",", "."));
    if (!Number.isFinite(n)) return String(value);
    return n.toFixed(3);
  }
  function recalcCastelletto() {
    if (window.EurekaDocCastelletto && typeof window.EurekaDocCastelletto.recalc === "function") {
      window.EurekaDocCastelletto.recalc(form);
    }
  }
  function applyArticolo(row, data) {
    if (!row || !data || !data.found) return;
    suppressSearch = true;
    try {
      if (data.codice) {
        setValue(field(row, "codice"), data.codice, { force: true });
      }
      setValue(field(row, "descrizione"), data.descrizione || "", { force: true });
      if (data.iva) {
        setValue(field(row, "iva"), data.iva, { force: true });
      }
      const umEl = field(row, "unita_misura");
      if (umEl && data.unita_misura && !String(umEl.value || "").trim()) {
        setValue(umEl, data.unita_misura, { force: true });
      }
      const prezzoEl = field(row, "prezzo_unitario");
      if (
        prezzoEl &&
        data.prezzo_unitario != null &&
        data.prezzo_unitario !== "" &&
        !String(prezzoEl.value || "").trim()
      ) {
        setValue(prezzoEl, formatPrezzoUnitario(data.prezzo_unitario), { force: true });
      }
    } finally {
      suppressSearch = false;
    }
    recalcCastelletto();
  }
  function resolveCodice(input) {
    const row = rowOf(input);
    if (!row) return;
    const codice = String(input.value || "").trim();
    if (!codice) {
      lastResolved.set(input, "");
      return;
    }
    const key = codice.toUpperCase();
    if (lastResolved.get(input) === key) return;
    if (inflight.get(input) === key) return;
    inflight.set(input, key);
    const qs = "?tipo=articolo&codice=" + encodeURIComponent(codice);
    fetch(url + qs, { headers: { "X-Requested-With": "XMLHttpRequest" } })
      .then((r) => r.json())
      .then((data) => {
        if (inflight.get(input) !== key) return;
        inflight.delete(input);
        const current = String(input.value || "").trim().toUpperCase();
        if (current !== key) return;
        if (data && data.found) {
          applyArticolo(row, data);
          lastResolved.set(input, key);
        } else {
          lastResolved.set(input, "");
        }
      })
      .catch(() => {
        if (inflight.get(input) === key) inflight.delete(input);
      });
  }
  function layoutMenu(input) {
    const rect = input.getBoundingClientRect();
    const maxH = 240;
    const gap = 2;
    const spaceBelow = window.innerHeight - rect.bottom - gap;
    const spaceAbove = rect.top - gap;
    let top = rect.bottom + gap;
    let maxHeight = maxH;
    const minW = 280;
    if (spaceBelow < 120 && spaceAbove > spaceBelow) {
      maxHeight = Math.min(maxH, spaceAbove);
      top = Math.max(8, rect.top - gap - maxHeight);
    } else {
      maxHeight = Math.min(maxH, Math.max(120, spaceBelow));
    }
    const width = Math.min(Math.max(rect.width, minW), window.innerWidth - 16);
    let left = Math.max(8, rect.left);
    if (left + width > window.innerWidth - 8) {
      left = Math.max(8, window.innerWidth - 8 - width);
    }
    menu.style.position = "fixed";
    menu.style.left = left + "px";
    menu.style.width = width + "px";
    menu.style.top = top + "px";
    menu.style.maxHeight = maxHeight + "px";
    menu.style.zIndex = "1060";
    menu.classList.add("is-portaled");
  }
  function closeMenu() {
    menu.hidden = true;
    menu.innerHTML = "";
    menu.classList.remove("is-portaled");
    menu.removeAttribute("style");
    menu._input = null;
    openMenu = null;
  }
  function showMenu(input) {
    menu._input = input;
    layoutMenu(input);
    menu.hidden = false;
    openMenu = menu;
  }
  function menuItems() {
    return Array.from(menu.querySelectorAll(".eureka-combo__item"));
  }
  function moveActive(delta) {
    const items = menuItems();
    if (!items.length) return;
    let idx = items.findIndex((el) => el.classList.contains("is-active"));
    if (idx < 0) idx = 0;
    else idx = (idx + delta + items.length) % items.length;
    items.forEach((el, i) => el.classList.toggle("is-active", i === idx));
    items[idx].scrollIntoView({ block: "nearest" });
  }
  function selectResult(rowData) {
    const input = menu._input;
    const row = input && rowOf(input);
    closeMenu();
    if (!row || !rowData) return;
    const data = {
      found: true,
      codice: rowData.codice || "",
      descrizione: rowData.descrizione || "",
      iva: rowData.iva || "",
      unita_misura: rowData.unita_misura || "",
      prezzo_unitario: rowData.prezzo_unitario,
    };
    applyArticolo(row, data);
    const codiceEl = field(row, "codice");
    if (codiceEl && data.codice) {
      lastResolved.set(codiceEl, String(data.codice).trim().toUpperCase());
      if (!data.iva) {
        lastResolved.delete(codiceEl);
        resolveCodice(codiceEl);
      }
    }
    if (input) input.focus();
  }
  function selectActive() {
    const active = menu.querySelector(".eureka-combo__item.is-active");
    if (!active) return false;
    selectResult({
      codice: active.dataset.codice || "",
      descrizione: active.dataset.descrizione || "",
      iva: active.dataset.iva || "",
      unita_misura: active.dataset.unitaMisura || "",
      prezzo_unitario: active.dataset.prezzoUnitario || null,
    });
    return true;
  }
  function renderMenu(results, input) {
    menu.innerHTML = "";
    if (!results.length) {
      const empty = document.createElement("div");
      empty.className = "eureka-combo__empty";
      empty.textContent = "Nessun articolo";
      menu.appendChild(empty);
      layoutMenu(input);
      return;
    }
    results.forEach((row, idx) => {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "eureka-combo__item" + (idx === 0 ? " is-active" : "");
      btn.setAttribute("role", "option");
      btn.dataset.codice = row.codice || "";
      btn.dataset.descrizione = row.descrizione || "";
      btn.dataset.iva = row.iva || "";
      btn.dataset.unitaMisura = row.unita_misura || "";
      if (row.prezzo_unitario != null && row.prezzo_unitario !== "") {
        btn.dataset.prezzoUnitario = String(row.prezzo_unitario);
      }
      btn.innerHTML =
        '<span class="eureka-combo__item-code"></span>' +
        '<span class="eureka-combo__item-desc"></span>';
      btn.querySelector(".eureka-combo__item-code").textContent = row.codice || "—";
      btn.querySelector(".eureka-combo__item-desc").textContent = row.descrizione || "";
      btn.addEventListener("mousedown", (ev) => {
        ev.preventDefault();
        selectResult(row);
      });
      menu.appendChild(btn);
    });
    layoutMenu(input);
  }
  function searchArticoli(input, q) {
    const query = String(q || "").trim();
    showMenu(input);
    menu.innerHTML = '<div class="eureka-combo__loading">Caricamento...</div>';
    layoutMenu(input);
    const seq = ++searchSeq;
    const qs =
      "?tipo=articolo&q=" +
      encodeURIComponent(query) +
      "&limit=40" +
      (query ? "" : "&list=1");
    fetch(url + qs, { headers: { "X-Requested-With": "XMLHttpRequest" } })
      .then((r) => {
        if (!r.ok) throw new Error("lookup " + r.status);
        return r.json();
      })
      .then((data) => {
        if (seq !== searchSeq || menu._input !== input) return;
        renderMenu(data.results || [], input);
      })
      .catch(() => {
        if (seq !== searchSeq || menu._input !== input) return;
        menu.innerHTML = '<div class="eureka-combo__empty">Errore di ricerca</div>';
        layoutMenu(input);
      });
  }
  function scheduleSearch(input) {
    if (suppressSearch) return;
    clearTimeout(searchTimers.get(input));
    searchTimers.set(
      input,
      setTimeout(() => {
        const q = String(input.value || "").trim();
        if (!q) {
          closeMenu();
          return;
        }
        searchArticoli(input, q);
      }, 220)
    );
  }
  /** Wrappa codice/descrizione con freccia combobox (come linked-lookups). */
  function ensureComboShell(input) {
    if (!input || !isArticoloSearchInput(input)) return;
    if (input.closest("[data-articolo-combo]")) return;
    const wrap = document.createElement("div");
    wrap.className = "eureka-combo eureka-doc-articolo-combo";
    wrap.setAttribute("data-articolo-combo", "");
    input.parentNode.insertBefore(wrap, input);
    wrap.appendChild(input);
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "eureka-combo__toggle";
    btn.setAttribute("data-articolo-combo-toggle", "");
    btn.tabIndex = -1;
    btn.title = "Cerca articolo";
    btn.setAttribute("aria-label", "Cerca articolo");
    btn.innerHTML = '<i class="ti ti-chevron-down" aria-hidden="true"></i>';
    wrap.appendChild(btn);
  }
  function enhanceRow(row) {
    if (!row) return;
    const codice = field(row, "codice");
    const descrizione = field(row, "descrizione");
    if (codice) ensureComboShell(codice);
    if (descrizione) ensureComboShell(descrizione);
  }
  function enhanceAll() {
    form.querySelectorAll("[data-riga-row]").forEach(enhanceRow);
  }
  function onViewportChange() {
    if (openMenu && openMenu._input) {
      layoutMenu(openMenu._input);
    }
  }
  window.addEventListener("scroll", onViewportChange, true);
  window.addEventListener("resize", onViewportChange);
  form.addEventListener("input", (ev) => {
    const el = ev.target;
    if (!isArticoloSearchInput(el)) return;
    if (suppressSearch) return;
    if (isCodiceInput(el)) lastResolved.delete(el);
    scheduleSearch(el);
  });
  form.addEventListener("change", (ev) => {
    if (suppressSearch) return;
    if (isCodiceInput(ev.target) && menu.hidden) resolveCodice(ev.target);
  });
  form.addEventListener(
    "blur",
    (ev) => {
      if (!isArticoloSearchInput(ev.target)) return;
      const el = ev.target;
      setTimeout(() => {
        if (menu.contains(document.activeElement)) return;
        if (menu._input === el) closeMenu();
        if (isCodiceInput(el)) resolveCodice(el);
      }, 120);
    },
    true
  );
  form.addEventListener("keydown", (ev) => {
    const el = ev.target;
    if (!isArticoloSearchInput(el)) return;
    const menuOpen = !menu.hidden && menu._input === el;
    if (ev.key === "ArrowDown") {
      ev.preventDefault();
      if (menuOpen && menuItems().length) moveActive(1);
      else searchArticoli(el, el.value);
      return;
    }
    if (ev.key === "ArrowUp") {
      if (!menuOpen) return;
      ev.preventDefault();
      moveActive(-1);
      return;
    }
    if (ev.key === "Escape") {
      if (!menuOpen) return;
      ev.preventDefault();
      closeMenu();
      return;
    }
    if (ev.key === "Enter") {
      if (menuOpen) {
        ev.preventDefault();
        if (!selectActive() && isCodiceInput(el)) {
          closeMenu();
          lastResolved.delete(el);
          resolveCodice(el);
        }
        return;
      }
      if (isCodiceInput(el)) {
        ev.preventDefault();
        lastResolved.delete(el);
        resolveCodice(el);
      }
    }
  });
  form.addEventListener("mousedown", (ev) => {
    const toggle = ev.target.closest("[data-articolo-combo-toggle]");
    if (!toggle || !form.contains(toggle)) return;
    ev.preventDefault();
    const combo = toggle.closest("[data-articolo-combo]");
    const input = combo && combo.querySelector("input, textarea");
    if (!input || !isArticoloSearchInput(input)) return;
    if (!menu.hidden && menu._input === input) {
      closeMenu();
      return;
    }
    searchArticoli(input, input.value);
    input.focus();
  });
  document.addEventListener("mousedown", (ev) => {
    if (!openMenu) return;
    const input = openMenu._input;
    const combo = input && input.closest("[data-articolo-combo]");
    const toggle = combo && combo.querySelector("[data-articolo-combo-toggle]");
    if (openMenu.contains(ev.target)) return;
    if (input && ev.target === input) return;
    if (toggle && toggle.contains(ev.target)) return;
    closeMenu();
  });
  const body = document.getElementById("righeBody");
  if (body) {
    new MutationObserver((mutations) => {
      mutations.forEach((m) => {
        m.addedNodes.forEach((node) => {
          if (node.nodeType !== 1) return;
          // Dopo EurekaLongText.enhance (sync su Aggiungi riga)
          setTimeout(() => {
            if (node.matches && node.matches("[data-riga-row]")) {
              enhanceRow(node);
            } else if (node.querySelectorAll) {
              node.querySelectorAll("[data-riga-row]").forEach(enhanceRow);
            }
          }, 0);
        });
      });
    }).observe(body, { childList: true });
  }
  // Dopo long-text-editor (DOMContentLoaded): altrimenti descrizione esce dallo shell combo
  function bootEnhance() {
    setTimeout(enhanceAll, 0);
  }
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", bootEnhance);
  } else {
    bootEnhance();
  }
  window.EurekaDocArticoloCombo = { enhanceRow, enhanceAll, searchArticoli };
})();

