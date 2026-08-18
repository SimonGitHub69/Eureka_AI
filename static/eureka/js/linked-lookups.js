(() => {
  const root = document.querySelector("[data-linked-lookups]");
  if (!root) return;
  const url = root.dataset.lookupUrl;
  const timers = new WeakMap();
  let openMenu = null;

  function setLabel(el, text, loading) {
    const field = el.closest("[data-linked-field]");
    const textEl = el.querySelector(".eureka-linked-label__text") || el;
    const value = (text || "").trim();

    if (loading) {
      if (!(textEl.textContent || "").trim()) {
        textEl.textContent = "…";
      }
      el.hidden = false;
      if (field) {
        field.classList.add("is-resolved", "is-loading");
      }
      return;
    }

    textEl.textContent = value;
    el.hidden = !value;
    if (field) {
      field.classList.toggle("is-resolved", Boolean(value));
      field.classList.remove("is-loading");
    }
  }

  function isCliforLookupTipo(tipo) {
    return tipo === "pdc_clifor" || tipo === "clifor" || tipo === "cliente" || tipo === "fornitore";
  }

  function uppercaseCliforCode(value, kind) {
    const code = String(value || "");
    const k = String(kind || "").toLowerCase();
    if (k === "cliente" || k === "fornitore" || k === "clifor") {
      return code.toUpperCase();
    }
    const trimmed = code.trim();
    if (trimmed && /^[A-Za-z]/.test(trimmed)) {
      return code.toUpperCase();
    }
    return code;
  }

  function forceUppercaseCliforInput(input, tipo) {
    if (!input || !isCliforLookupTipo(tipo)) return;
    const next = uppercaseCliforCode(input.value || "", tipo);
    if (input.value === next) return;
    const start = input.selectionStart;
    const end = input.selectionEnd;
    input.value = next;
    try {
      if (typeof start === "number") input.setSelectionRange(start, end);
    } catch (e) {}
  }

  function cliforDetailPath(tipo, codice, kind) {
    const code = String(codice || "").trim();
    if (!code) return "";
    let which = String(kind || tipo || "").toLowerCase();
    if (which === "clifor") {
      const letter = code.replace(/\s/g, "").charAt(0).toUpperCase();
      which = letter === "F" ? "fornitore" : "cliente";
    }
    if (which === "fornitore") {
      return "/fornitori/" + encodeURIComponent(code) + "/";
    }
    if (which === "cliente") {
      return "/clienti/" + encodeURIComponent(code) + "/";
    }
    return "";
  }

  function updateLinkedOpen(field, data) {
    const a = field && field.querySelector("[data-linked-open]");
    if (!a) return;
    const tipo = (field.dataset.lookupTipo || "").trim();
    const codice = String((data && data.codice) || "").trim();
    const found = Boolean(
      data && (data.found || data.descrizione || data.url)
    );
    const path =
      (data && data.url) ||
      (found ? cliforDetailPath(tipo, codice, data.kind) : "");
    if (!path) {
      a.hidden = true;
      a.setAttribute("href", "#");
      return;
    }
    a.setAttribute("href", path);
    a.hidden = false;
  }

  const ANAGRAFICA_FIELDS = [
    ["id_destinatario", "destinatario"],
    ["id_indirizzo", "indirizzo"],
    ["id_localita", "localita"],
    ["id_cap", "cap"],
    ["id_provincia", "provincia"],
    ["id_nazione", "nazione"],
    ["id_telefono", "telefono"],
  ];

  function currentCodiceClifor() {
    const el = document.getElementById("id_codice_clifor");
    return el ? String(el.value || "").trim() : "";
  }

  function destinazioneField() {
    return root.querySelector('[data-linked-field][data-lookup-tipo="destinazione"]');
  }

  function clearDestinazionePicker() {
    const field = destinazioneField();
    if (!field) return;
    const input =
      document.getElementById("id_codice_dest") ||
      field.querySelector(".form-control, input");
    const label = field.querySelector("[data-linked-label]");
    if (input) input.value = "";
    if (label) setLabel(label, "", false);
    field.dataset.anagraficaApplied = "";
  }

  function fillAnagraficaPanel(data) {
    const panel = root.querySelector("[data-anagrafica-panel]");
    if (!panel) return;
    const src = data || {};
    panel.querySelectorAll("[data-anagrafica-field]").forEach((el) => {
      const key = el.getAttribute("data-anagrafica-field");
      el.value = String(src[key] || src[key === "destinatario" ? "descrizione" : key] || "").trim();
    });
    updateAnagraficaLink(panel, src);
  }

  function updateAnagraficaLink(panel, data) {
    const link = panel.querySelector("[data-anagrafica-link]");
    if (!link) return;
    const tipo = (panel.getAttribute("data-clifor-tipo") || "").trim().toLowerCase();
    const codice = String((data && (data.codice || data.codice_clifor)) || "").trim();
    const found = Boolean(data && (data.found || data.destinatario || data.descrizione));
    if (!found || !codice || (tipo !== "cliente" && tipo !== "fornitore")) {
      link.hidden = true;
      link.setAttribute("href", "#");
      return;
    }
    const path =
      tipo === "fornitore"
        ? "/fornitori/" + encodeURIComponent(codice) + "/"
        : "/clienti/" + encodeURIComponent(codice) + "/";
    link.setAttribute("href", path);
    link.hidden = false;
  }

  function applyScontoTestata(percentuale) {
    const formula = String(percentuale || "").trim();
    const scontoEl = document.getElementById("id_sconto");
    if (scontoEl) {
      scontoEl.value = formula;
      scontoEl.dispatchEvent(new Event("input", { bubbles: true }));
      scontoEl.dispatchEvent(new Event("change", { bubbles: true }));
    }
    // Solo calcolo castelletto: non scrivere lo sconto sulle righe.
    const form = document.getElementById("documentoForm");
    if (
      form &&
      window.EurekaDocCastelletto &&
      typeof window.EurekaDocCastelletto.recalc === "function"
    ) {
      window.EurekaDocCastelletto.recalc(form);
    }
  }

  function applyLuogoDestinazione(data, overwrite) {
    if (!data) return;
    ANAGRAFICA_FIELDS.forEach(([id, key]) => {
      const el = document.getElementById(id);
      if (!el) return;
      const next = String(data[key] || "").trim();
      if (!overwrite && (el.value || "").trim()) return;
      if (overwrite || next) el.value = next;
    });
  }

  function applyLinkedCodeFill(inputId, code, descrizione, overwrite) {
    const el = document.getElementById(inputId);
    if (!el) return;
    if (!overwrite && (el.value || "").trim()) return;
    if (!overwrite && !code) return;
    el.value = code;
    const field = el.closest("[data-linked-field]");
    const label = field && field.querySelector("[data-linked-label]");
    if (label) {
      if (descrizione) {
        setLabel(label, descrizione, false);
      } else if (code) {
        resolveLabel(el, label);
      } else {
        setLabel(label, "", false);
      }
    }
    el.dispatchEvent(new Event("change", { bubbles: true }));
  }

  function applyAnagraficaFill(data, overwrite) {
    if (!root.hasAttribute("data-fill-from-anagrafica") || !data) return;

    applyLuogoDestinazione(data, overwrite);

    applyLinkedCodeFill(
      "id_cod_pagamento",
      String(data.cond_paga || "").trim(),
      String(data.cond_paga_descrizione || "").trim(),
      overwrite
    );
    applyLinkedCodeFill(
      "id_codice_agente",
      String(data.agente || "").trim(),
      String(data.agente_descrizione || "").trim(),
      overwrite
    );
  }

  function markAnagraficaApplied(input, codice) {
    const field = input && input.closest("[data-linked-field]");
    if (field) field.dataset.anagraficaApplied = codice || "";
  }

  function fillFromAnagrafica(input, data, forceOverwrite) {
    const field = input && input.closest("[data-linked-field]");
    if (!field) return;
    const tipo = field.dataset.lookupTipo;
    if (tipo !== "cliente" && tipo !== "fornitore") return;
    const codice = (input.value || "").trim();
    const applied = field.dataset.anagraficaApplied || "";
    const overwrite = forceOverwrite || (Boolean(applied) && applied !== codice);
    fillAnagraficaPanel(data);
    applyAnagraficaFill(data, overwrite);
    markAnagraficaApplied(input, codice);
    if (overwrite || forceOverwrite) {
      clearDestinazionePicker();
    }
  }

  function fillFromDestinazione(input, data, forceOverwrite) {
    const field = input && input.closest("[data-linked-field]");
    if (!field || field.dataset.lookupTipo !== "destinazione") return;
    if (!data || !data.found) return;
    applyLuogoDestinazione(data, true);
    markAnagraficaApplied(input, (input.value || "").trim());
    if (forceOverwrite) {
      const dest = document.getElementById("id_destinatario");
      if (dest) dest.dispatchEvent(new Event("change", { bubbles: true }));
    }
  }

  function resolveLabel(input, label) {
    const tipo = label.dataset.lookupTipo;
    const codice = (input.value || "").trim();
    if (!codice) {
      setLabel(label, "", false);
      updateLinkedOpen(label.closest("[data-linked-field]"), {});
      if (tipo === "cliente" || tipo === "fornitore") fillAnagraficaPanel({});
      if (tipo === "sconto") applyScontoTestata("");
      return;
    }
    setLabel(label, "", true);
    let qs =
      "?tipo=" + encodeURIComponent(tipo) + "&codice=" + encodeURIComponent(codice);
    if (tipo === "destinazione") {
      const clifor = currentCodiceClifor();
      if (!clifor) {
        setLabel(label, "", false);
        return;
      }
      qs += "&codice_clifor=" + encodeURIComponent(clifor);
    }
    fetch(url + qs, {
      headers: { "X-Requested-With": "XMLHttpRequest" },
    })
      .then((r) => r.json())
      .then((data) => {
        setLabel(label, data.descrizione || "", false);
        updateLinkedOpen(label.closest("[data-linked-field]"), data);
        if (tipo === "destinazione") {
          fillFromDestinazione(input, data, false);
        } else if (tipo === "sconto") {
          applyScontoTestata(data.descrizione || "");
        } else {
          fillFromAnagrafica(input, data, false);
        }
      })
      .catch(() => {
        setLabel(label, "", false);
        updateLinkedOpen(label.closest("[data-linked-field]"), {});
      });
  }

  function layoutMenu(menu, input) {
    const rect = input.getBoundingClientRect();
    const maxH = 240;
    const gap = 2;
    const spaceBelow = window.innerHeight - rect.bottom - gap;
    const spaceAbove = rect.top - gap;
    let top = rect.bottom + gap;
    let maxHeight = maxH;

    if (spaceBelow < 120 && spaceAbove > spaceBelow) {
      maxHeight = Math.min(maxH, spaceAbove);
      top = Math.max(8, rect.top - gap - maxHeight);
    } else {
      maxHeight = Math.min(maxH, Math.max(120, spaceBelow));
    }

    menu.style.position = "fixed";
    menu.style.left = Math.max(8, rect.left) + "px";
    menu.style.width = Math.max(rect.width, 220) + "px";
    menu.style.top = top + "px";
    menu.style.maxHeight = maxHeight + "px";
    menu.style.zIndex = "1060";
  }

  function showMenu(menu, input) {
    menu._input = input;
    menu._combo = input.closest(".eureka-combo");
    if (menu.parentElement !== document.body) {
      document.body.appendChild(menu);
    }
    menu.classList.add("is-portaled");
    layoutMenu(menu, input);
    menu.hidden = false;
    openMenu = menu;
  }

  function closeMenu(menu) {
    if (!menu) return;
    menu.hidden = true;
    menu.innerHTML = "";
    menu.classList.remove("is-portaled");
    menu.removeAttribute("style");
    menu._input = null;
    const combo = menu._combo;
    menu._combo = null;
    if (combo && menu.parentElement === document.body) {
      combo.appendChild(menu);
    }
    if (openMenu === menu) openMenu = null;
  }

  function closeAllMenus(except) {
    root.querySelectorAll("[data-combo-menu]").forEach((menu) => {
      if (menu !== except) closeMenu(menu);
    });
    if (openMenu && openMenu !== except) closeMenu(openMenu);
  }

  function lookupLimit(tipo) {
    // PDC / PDC+clifor: molte voci; 40 tagliava la lista all'apertura senza ricerca.
    return tipo === "pdc" || tipo === "pdc_clifor" ? 400 : 40;
  }

  function renderMenu(menu, results, input, label, opts) {
    menu.innerHTML = "";
    if (!results.length) {
      const empty = document.createElement("div");
      empty.className = "eureka-combo__empty";
      empty.textContent = "Nessun risultato";
      menu.appendChild(empty);
      layoutMenu(menu, input);
      return;
    }
    results.forEach((row, idx) => {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "eureka-combo__item" + (idx === 0 ? " is-active" : "");
      btn.setAttribute("role", "option");
      btn.dataset.codice = row.codice || "";
      btn.dataset.descrizione = row.descrizione || "";
      btn.innerHTML =
        '<span class="eureka-combo__item-code"></span>' +
        '<span class="eureka-combo__item-desc"></span>';
      btn.querySelector(".eureka-combo__item-code").textContent = row.codice || "—";
      const kindLabel = ({ cliente: "Cliente", fornitore: "Fornitore", pdc: "PDC" })[
        String(row.kind || "").toLowerCase()
      ];
      const desc = row.descrizione || "";
      btn.querySelector(".eureka-combo__item-desc").textContent = kindLabel
        ? kindLabel + " · " + desc
        : desc;
      btn.addEventListener("mousedown", (ev) => {
        ev.preventDefault();
        const tipoPick = (label.dataset.lookupTipo || "").trim();
        input.value = uppercaseCliforCode(
          row.codice || "",
          row.kind || tipoPick
        );
        setLabel(label, row.descrizione || "", false);
        updateLinkedOpen(input.closest("[data-linked-field]"), row);
        const tipo = (label.dataset.lookupTipo || "").trim();
        if (tipo === "destinazione") {
          fillFromDestinazione(input, row, true);
        } else if (tipo === "sconto") {
          applyScontoTestata(row.descrizione || "");
        } else {
          fillFromAnagrafica(input, row, true);
        }
        closeMenu(menu);
        input.dispatchEvent(new Event("change", { bubbles: true }));
        input.focus();
      });
      menu.appendChild(btn);
    });
    if (opts && opts.truncated) {
      const hint = document.createElement("div");
      hint.className = "eureka-combo__empty";
      hint.textContent = "Digita codice o descrizione per cercare…";
      menu.appendChild(hint);
    }
    layoutMenu(menu, input);
  }

  function searchList(field, input, label, menu, q) {
    const tipo = field.dataset.lookupTipo;
    const limit = lookupLimit(tipo);
    showMenu(menu, input);
    menu.innerHTML = '<div class="eureka-combo__loading">Caricamento…</div>';
    let qs =
      "?tipo=" + encodeURIComponent(tipo) +
      "&q=" + encodeURIComponent(q || "") +
      "&limit=" + encodeURIComponent(String(limit));
    if (tipo === "destinazione") {
      const clifor = currentCodiceClifor();
      if (!clifor) {
        menu.innerHTML =
          '<div class="eureka-combo__empty">Seleziona prima il cliente/fornitore</div>';
        layoutMenu(menu, input);
        return;
      }
      qs += "&codice_clifor=" + encodeURIComponent(clifor);
    }
    fetch(url + qs, { headers: { "X-Requested-With": "XMLHttpRequest" } })
      .then((r) => r.json())
      .then((data) => {
        const results = data.results || [];
        renderMenu(menu, results, input, label, {
          truncated: results.length >= limit,
        });
      })
      .catch(() => {
        menu.innerHTML = '<div class="eureka-combo__empty">Errore di ricerca</div>';
        layoutMenu(menu, input);
      });
  }

  function onViewportChange() {
    if (openMenu && openMenu._input) {
      layoutMenu(openMenu, openMenu._input);
    }
  }

  function bindLinkedField(field) {
    if (!field || field.dataset.lookupBound === "1") return;
    const label = field.querySelector("[data-linked-label]");
    const combo = field.querySelector(".eureka-combo");
    if (!label || !combo) return;
    const input = document.getElementById(label.dataset.forInput) || combo.querySelector(".form-control, input");
    const menu = combo.querySelector("[data-combo-menu]");
    const toggle = combo.querySelector("[data-combo-toggle]");
    if (!input || !menu) return;

    field.dataset.lookupBound = "1";
    menu._combo = combo;

    const runResolve = () => resolveLabel(input, label);
    const runSearch = () => {
      closeAllMenus(menu);
      searchList(field, input, label, menu, (input.value || "").trim());
    };

    input.addEventListener("input", () => {
      forceUppercaseCliforInput(input, field.dataset.lookupTipo);
      clearTimeout(timers.get(input));
      timers.set(
        input,
        setTimeout(() => {
          runResolve();
          // Apri/aggiorna la lista mentre digiti (non solo se già aperta).
          runSearch();
        }, 220)
      );
    });
    input.addEventListener("change", runResolve);
    input.addEventListener("blur", () => {
      setTimeout(() => {
        if (!menu.contains(document.activeElement)) closeMenu(menu);
      }, 120);
      runResolve();
    });
    input.addEventListener("keydown", (ev) => {
      if (ev.key === "ArrowDown") {
        ev.preventDefault();
        runSearch();
      } else if (ev.key === "Escape") {
        closeMenu(menu);
      } else if (ev.key === "Enter" && !menu.hidden) {
        const active = menu.querySelector(".eureka-combo__item.is-active");
        if (active) {
          ev.preventDefault();
          active.dispatchEvent(new Event("mousedown"));
        }
      }
    });

    if (toggle) {
      toggle.addEventListener("mousedown", (ev) => {
        ev.preventDefault();
        if (menu.hidden) {
          closeAllMenus(menu);
          searchList(field, input, label, menu, "");
          input.focus();
        } else {
          closeMenu(menu);
        }
      });
    }

    runResolve();
  }

  function bindLinkedFields(scope) {
    const rootScope = scope || root;
    if (!rootScope || !rootScope.querySelectorAll) return;
    rootScope.querySelectorAll("[data-linked-field]").forEach(bindLinkedField);
    if (rootScope.matches && rootScope.matches("[data-linked-field]")) {
      bindLinkedField(rootScope);
    }
  }

  window.addEventListener("scroll", onViewportChange, true);
  window.addEventListener("resize", onViewportChange);

  bindLinkedFields(root);
  window.EurekaLinkedLookups = { bind: bindLinkedFields };

  // Cambio Cli/For: azzera il selettore destinazione (lista dipende dal codice).
  // Timer dedicato: non riusare WeakMap su #id_codice_clifor, altrimenti
  // clearTimeout cancella il debounce di resolve/search del linked-field.
  const cliforInput = document.getElementById("id_codice_clifor");
  if (cliforInput) {
    let lastClifor = (cliforInput.value || "").trim();
    let cliforClearTimer = null;
    const onCliforChange = () => {
      const next = (cliforInput.value || "").trim();
      if (next === lastClifor) return;
      lastClifor = next;
      clearDestinazionePicker();
    };
    cliforInput.addEventListener("change", onCliforChange);
    cliforInput.addEventListener("input", () => {
      clearTimeout(cliforClearTimer);
      cliforClearTimer = setTimeout(onCliforChange, 280);
    });
  }

  document.addEventListener("mousedown", (ev) => {
    if (!openMenu) return;
    const input = openMenu._input;
    const toggle = input?.closest(".eureka-combo")?.querySelector("[data-combo-toggle]");
    if (openMenu.contains(ev.target)) return;
    if (input && (ev.target === input || toggle?.contains(ev.target))) return;
    closeMenu(openMenu);
  });
})();
