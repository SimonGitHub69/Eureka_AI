/**
 * Primanota — lookup conti/IVA nelle righe + calcolo importo IVA da AliquoteIva.
 */
(function () {
  const form = document.getElementById("primanotaForm") || document.querySelector("[data-primanota-riga-form]");
  if (!form) return;

  function parseNum(value) {
    if (value == null) return 0;
    let s = String(value).trim().replace(/\s/g, "");
    if (!s) return 0;
    if (s.indexOf(",") >= 0) {
      s = s.replace(/\./g, "").replace(",", ".");
    } else if ((s.match(/\./g) || []).length > 1) {
      s = s.replace(/\./g, "");
    } else if (/^\d{1,3}(\.\d{3})+$/.test(s)) {
      s = s.replace(/\./g, "");
    }
    const n = Number(s);
    return Number.isFinite(n) ? n : 0;
  }

  function round2(n) {
    return Math.round((n + Number.EPSILON) * 100) / 100;
  }

  function aliquotaPct(code) {
    const map = window.EUREKA_ALIQUOTE_MAP || {};
    const key = String(code || "").trim();
    if (!key) return 0;
    const hit = map[key] || map[key.toUpperCase()];
    if (hit && hit.pct != null) return Number(hit.pct) || 0;
    const m = key.toUpperCase().match(/^(\d{1,2}(?:[.,]\d+)?)/);
    return m ? parseNum(m[1]) : 0;
  }

  function fieldEl(container, name) {
    const root = container || form;
    if (!root) return null;
    return (
      root.querySelector(`[data-original-name$="-${name}"]`) ||
      root.querySelector(`[data-original-name="${name}"]`) ||
      root.querySelector(`[name$="-${name}"]`) ||
      root.querySelector(`[name="${name}"]`) ||
      root.querySelector(`#id_${name}`) ||
      root.querySelector(`[id$="-${name}"]`)
    );
  }

  function fieldKey(el) {
    return String(el?.getAttribute("data-original-name") || el?.name || el?.id || "");
  }

  function isNamedField(el, names) {
    const key = fieldKey(el);
    const id = String(el?.id || "");
    return names.some(
      (n) =>
        key === n ||
        key.endsWith("-" + n) ||
        id === "id_" + n ||
        id.endsWith("-" + n)
    );
  }

  function isIvaMode() {
    const tipo = document.getElementById("id_tipo");
    if (tipo) return tipo.value === "2" || tipo.value === "4";
    return form.hasAttribute("data-primanota-riga-form") && form.querySelector("#id_conto_partita") != null;
  }

  function baseImponibile(container) {
    if (isIvaMode()) {
      return parseNum(fieldEl(container, "imponibile")?.value);
    }
    const dare = parseNum(fieldEl(container, "dare")?.value);
    if (dare) return dare;
    return parseNum(fieldEl(container, "avere")?.value);
  }

  function recalcRowIva(container) {
    const scope = container || form;
    const codeEl = fieldEl(scope, "codice_iva");
    const importoEl = fieldEl(scope, "importo_iva");
    if (!codeEl || !importoEl) return;
    const code = String(codeEl.value || "").trim();
    const base = baseImponibile(scope);
    if (!code || !base) {
      if (!importoEl.dataset.manualIva) {
        importoEl.value = "";
      }
      return;
    }
    const iva = round2((base * aliquotaPct(code)) / 100);
    // input type=number accetta solo il punto nello .value (la UI può mostrare la virgola).
    importoEl.value = iva.toFixed(2);
    importoEl.dataset.autoIva = "1";
    delete importoEl.dataset.manualIva;
  }

  function recalcAllRows() {
    if (form.id === "primanotaForm") {
      form.querySelectorAll("#righeTable tbody tr").forEach((row) => recalcRowIva(row));
    } else {
      recalcRowIva(form);
    }
    updateTotals();
  }

  function rowDeleted(row) {
    const del = row.querySelector('input[type="checkbox"][name$="-DELETE"]');
    return Boolean(del && del.checked);
  }

  function sumNamed(name) {
    if (form.id !== "primanotaForm") return 0;
    let tot = 0;
    form.querySelectorAll("#righeTable tbody tr").forEach((row) => {
      if (rowDeleted(row)) return;
      tot += parseNum(fieldEl(row, name)?.value);
    });
    return round2(tot);
  }

  function formatEuro(n) {
    const sign = n < 0 ? "-" : "";
    const abs = round2(Math.abs(Number(n) || 0));
    const parts = abs.toFixed(2).split(".");
    parts[0] = parts[0].replace(/\B(?=(\d{3})+(?!\d))/g, ".");
    return sign + parts[0] + "," + parts[1];
  }

  function formatImportoInput(el) {
    if (!el) return;
    el.value = formatEuro(parseNum(el.value));
  }

  function bindImportoFields(scope) {
    const root = scope || form;
    root.querySelectorAll("input").forEach((el) => {
      if (!isNamedField(el, ["dare", "avere"])) return;
      if (el.dataset.importoBound === "1") return;
      el.dataset.importoBound = "1";
      el.addEventListener("blur", () => {
        formatImportoInput(el);
        updateTotals();
      });
      formatImportoInput(el);
    });
  }

  function setTotale(selector, value) {
    document.querySelectorAll(selector).forEach((el) => {
      el.textContent = "€ " + formatEuro(value);
    });
  }

  function getTotals() {
    const totImp = sumNamed("imponibile");
    const totIva = sumNamed("importo_iva");
    const totDare = sumNamed("dare");
    const totAvere = sumNamed("avere");
    return {
      imponibile: totImp,
      iva: totIva,
      documento: round2(totImp + totIva),
      dare: totDare,
      avere: totAvere,
      sbilancio: round2(totDare - totAvere),
    };
  }

  function needsBalance() {
    return form.id === "primanotaForm" && !isIvaMode();
  }

  function syncBalanceGate() {
    if (form.id !== "primanotaForm") return;
    const totals = getTotals();
    const unbalanced = needsBalance() && Math.abs(totals.sbilancio) > 0.005;
    const banner = form.querySelector("[data-sbilancio-banner]");
    if (banner) {
      banner.hidden = !unbalanced;
      const amt = banner.querySelector("[data-sbilancio-banner-amt]");
      if (amt) amt.textContent = "€ " + formatEuro(totals.sbilancio);
    }
    form.querySelectorAll('button[type="submit"]').forEach((btn) => {
      btn.disabled = unbalanced;
      if (unbalanced) {
        btn.setAttribute(
          "title",
          "Impossibile salvare: la registrazione è sbilanciata."
        );
      } else {
        btn.removeAttribute("title");
      }
    });
  }

  function updateTotals() {
    if (form.id !== "primanotaForm") return;
    const totals = getTotals();
    setTotale("[data-totale-imponibile]", totals.imponibile);
    setTotale("[data-totale-iva]", totals.iva);
    setTotale("[data-totale-documento]", totals.documento);
    setTotale("[data-totale-dare]", totals.dare);
    setTotale("[data-totale-avere]", totals.avere);
    setTotale("[data-sbilancio]", totals.sbilancio);
    document.querySelectorAll("[data-sbilancio]").forEach((el) => {
      el.classList.toggle("text-danger", Math.abs(totals.sbilancio) > 0.005);
    });
    syncBalanceGate();
    if (window.EurekaPrimanotaScadenze && typeof window.EurekaPrimanotaScadenze.recalc === "function") {
      window.EurekaPrimanotaScadenze.recalc();
    }
  }

  form.addEventListener(
    "input",
    (e) => {
      const t = e.target;
      if (!t || t.nodeType !== 1) return;
      if (isNamedField(t, ["importo_iva"])) {
        if (t.dataset.autoIva) delete t.dataset.autoIva;
        else t.dataset.manualIva = "1";
        updateTotals();
        return;
      }
      if (isNamedField(t, ["imponibile", "codice_iva", "dare", "avere"])) {
        recalcRowIva(t.closest("tr") || form);
        updateTotals();
      }
    },
    true
  );

  form.addEventListener(
    "change",
    (e) => {
      const t = e.target;
      if (!t || t.nodeType !== 1) return;
      if (isNamedField(t, ["imponibile", "codice_iva", "dare", "avere"])) {
        recalcRowIva(t.closest("tr") || form);
        updateTotals();
      }
      if (t.matches && t.matches('input[type="checkbox"][name$="-DELETE"]')) {
        updateTotals();
      }
    },
    true
  );

  document.getElementById("id_tipo")?.addEventListener("change", recalcAllRows);

  form.addEventListener("submit", (ev) => {
    if (!needsBalance()) return;
    const totals = getTotals();
    if (Math.abs(totals.sbilancio) <= 0.005) return;
    ev.preventDefault();
    syncBalanceGate();
    const banner = form.querySelector("[data-sbilancio-banner]");
    if (banner && typeof banner.scrollIntoView === "function") {
      banner.scrollIntoView({ behavior: "smooth", block: "center" });
    }
    if (window.EurekaErrorSound && typeof window.EurekaErrorSound.play === "function") {
      window.EurekaErrorSound.play();
    }
  });

  window.EurekaPrimanotaRighe = { recalcAllRows, recalcRowIva, updateTotals, getTotals };
  bindImportoFields();
  recalcAllRows();

  const totalInput =
    document.getElementById("id_righe-TOTAL_FORMS") ||
    form.querySelector("input[name$='-TOTAL_FORMS']");
  const body = document.getElementById("righeBody");
  const tpl = document.getElementById("rigaEmptyFormTemplate");
  if (form.id === "primanotaForm" && totalInput && body && tpl) {
    const POS_STEP = 10;

    function isRowDeleted(row) {
      if (!row || row.hasAttribute("data-riga-empty-hint")) return true;
      if (row.classList.contains("d-none")) return true;
      const checkbox = row.querySelector('input[type="checkbox"][name$="-DELETE"]');
      return Boolean(checkbox && checkbox.checked);
    }

    function posInput(row) {
      return row.querySelector('input[name$="-pos"]') || row.querySelector('[id$="-pos"]');
    }

    function parsePos(value) {
      if (value == null) return null;
      const n = Number(String(value).trim().replace(",", "."));
      return Number.isFinite(n) ? n : null;
    }

    function nextPos() {
      let max = 0;
      body.querySelectorAll("[data-riga-row]").forEach((row) => {
        if (isRowDeleted(row)) return;
        const n = parsePos(posInput(row)?.value);
        if (n != null && n > max) max = n;
      });
      return max + POS_STEP;
    }

    function setPos(row, value) {
      const input = posInput(row);
      if (input) input.value = String(value);
      const label = row.querySelector("[data-riga-pos]");
      if (label) label.textContent = String(value);
    }

    function applyTipoVisibility(scope) {
      const tipo = document.getElementById("id_tipo");
      const iva = tipo && (tipo.value === "2" || tipo.value === "4");
      scope.querySelectorAll("[data-iva-col]").forEach((el) => {
        el.classList.toggle("d-none", !iva);
      });
      scope.querySelectorAll("[data-gen-col]").forEach((el) => {
        el.classList.toggle("d-none", iva);
      });
    }

    function addRow(ev) {
      if (ev) {
        ev.preventDefault();
        ev.stopPropagation();
      }
      const index = parseInt(totalInput.value, 10);
      if (Number.isNaN(index)) return;
      const html = tpl.innerHTML.replace(/__prefix__/g, String(index));
      const wrap = document.createElement("tbody");
      wrap.innerHTML = html.trim();
      const row = wrap.querySelector("[data-riga-row]");
      if (!row) return;
      setPos(row, nextPos());
      const hint = body.querySelector("[data-riga-empty-hint]");
      if (hint) hint.remove();
      body.appendChild(row);
      totalInput.value = String(index + 1);
      applyTipoVisibility(row);
      if (window.EurekaLinkedLookups && typeof window.EurekaLinkedLookups.bind === "function") {
        window.EurekaLinkedLookups.bind(row);
      }
      bindImportoFields(row);
      updateTotals();
      const focus = row.querySelector(
        'input:not([type="hidden"]):not([type="checkbox"])'
      );
      if (focus) {
        focus.removeAttribute("readonly");
        focus.focus();
      }
    }

    function markDelete(row) {
      const checkbox = row.querySelector('input[type="checkbox"][name$="-DELETE"]');
      if (checkbox) {
        checkbox.checked = true;
        checkbox.dispatchEvent(new Event("change", { bubbles: true }));
      }
      row.classList.add("d-none");
      updateTotals();
    }

    form.addEventListener("click", (ev) => {
      const addBtn = ev.target.closest("[data-add-riga]");
      if (addBtn) {
        addRow(ev);
        return;
      }
      const delBtn = ev.target.closest(".btn-elimina-riga");
      if (!delBtn || !body.contains(delBtn)) return;
      const row = delBtn.closest("[data-riga-row]");
      if (row) markDelete(row);
    });
  }
})();
