/**
 * Castelletto IVA — ricalcolo live su form documenti.
 * Legge righe [data-riga-row] + spese testata, aggiorna tabella e imponibile/totale.
 *
 * Markup root: [data-castelletto]
 * Trigger recalc: input/change/blur (capture) su
 *   righe-*-quantita|prezzo_unitario|sconto|iva|DELETE,
 *   spese_*; add/delete riga; MutationObserver #righeBody;
 *   EurekaDocCastelletto.recalc(form) (es. lookup articolo).
 * Opzionale: window.EUREKA_ALIQUOTE_MAP = {
 *   "VA22": {pct:22, descrizione:"IVA 22%", label:"IVA 22%"}, ...
 * }
 * Opzionale: window.EUREKA_ALIQUOTA_IVA_SPESE = "VA22" (Parametri contabili);
 * se valorizzato, le spese usano quella aliquota invece della prima riga merce.
 * label / Tipo Aliquota Iva = Aliquota.descrizione (fallback: codice).
 */
(function () {
  const MONEY = 2;
  const PREZZO_DECIMALS = 3;

  function parseNum(value) {
    if (value == null) return 0;
    let s = String(value).trim();
    if (!s) return 0;
    // 1.234,56 → 1234.56 ; 1234.56 → 1234.56
    if (s.indexOf(",") >= 0) {
      s = s.replace(/\./g, "").replace(",", ".");
    }
    const n = Number(s);
    return Number.isFinite(n) ? n : 0;
  }

  function round2(n) {
    return Math.round((n + Number.EPSILON) * 100) / 100;
  }

  function formatEuro(n) {
    const v = round2(n);
    const parts = v.toFixed(MONEY).split(".");
    const intPart = parts[0].replace(/\B(?=(\d{3})+(?!\d))/g, ".");
    return intPart + "," + parts[1];
  }

  function formatPrezzoUnitario(n) {
    const v = Number(n);
    if (!Number.isFinite(v)) return "";
    return v.toFixed(PREZZO_DECIMALS);
  }

  /** Parti % da testo riga (es. "10+5", "10%", "10-5"). */
  function parseScontoParts(raw) {
    const s = String(raw || "")
      .trim()
      .replace(/,/g, ".");
    if (!s) return [];
    const parts = [];
    const re = /\d+(?:\.\d+)?/g;
    let m;
    while ((m = re.exec(s)) !== null) {
      const n = Number(m[0]);
      if (Number.isFinite(n) && n > 0) parts.push(n);
    }
    return parts;
  }

  /**
   * Codice tabella Sconti → formula % (es. 50A → 50+10).
   * Riga + testata in cascata (calcolo, non scrittura sulle righe).
   */
  function lookupScontoFormula(raw) {
    const key = String(raw || "").trim();
    if (!key) return "";
    const map = window.EUREKA_SCONTI_MAP || {};
    const hit = map[key] || map[key.toUpperCase()];
    return String(hit || key).trim();
  }

  function headerScontoFormula() {
    const scontoEl = document.getElementById("id_sconto");
    if (scontoEl && String(scontoEl.value || "").trim()) {
      return lookupScontoFormula(scontoEl.value);
    }
    const codeEl = document.getElementById("id_codice_sconto");
    if (codeEl && String(codeEl.value || "").trim()) {
      return lookupScontoFormula(codeEl.value);
    }
    return "";
  }

  function effectiveSconto(lineRaw) {
    const line = lookupScontoFormula(lineRaw);
    const header = headerScontoFormula();
    if (line && header && line !== header) return line + "+" + header;
    return line || header || "";
  }

  /**
   * Sconto a cascata ERP IT: merce × (1 − Π(1 − pᵢ/100)).
   * Es. 10+5 → fattore 0.9×0.95 = 0.855 → sconto = merce × 0.145.
   */
  function scontoImporto(merce, raw) {
    const parts = parseScontoParts(effectiveSconto(raw));
    if (!parts.length) return 0;
    let factor = 1;
    for (let i = 0; i < parts.length; i++) {
      factor *= 1 - parts[i] / 100;
    }
    return round2(merce * (1 - factor));
  }

  function aliquotaLabel(code, hit) {
    const key = String(code || "").trim() || "22";
    if (hit) {
      const desc = String(hit.descrizione || "").trim();
      if (desc) return desc;
      const mapped = String(hit.label || "").trim();
      if (mapped) return mapped;
    }
    return key;
  }

  function aliquotaInfo(code) {
    // Preferisci mappa server (Aliquota.percentuale / descrizione da AliquoteIva)
    const map = window.EUREKA_ALIQUOTE_MAP || {};
    const key = String(code || "22").trim();
    const hit = map[key] || map[key.toUpperCase()];
    if (hit && hit.pct != null) {
      return {
        code: key || "22",
        pct: Number(hit.pct) || 0,
        label: aliquotaLabel(key, hit),
      };
    }
    // Fallback solo se codice assente dalla mappa anagrafica
    const m = key.toUpperCase().match(/^(\d{1,2}(?:[.,]\d+)?)/);
    const pct = m ? parseNum(m[1]) : 0;
    return {
      code: key || "22",
      pct: pct,
      label: aliquotaLabel(key, null),
    };
  }

  function isRowDeleted(row) {
    if (row.classList.contains("d-none")) return true;
    const checkbox = row.querySelector(
      ".riga-delete-input, input[type='checkbox'][name$='-DELETE'], input[type='checkbox'][data-original-name$='-DELETE']"
    );
    return !!(checkbox && checkbox.checked);
  }

  /** Nome logico Django (righe-0-quantita), anche se disable-autocomplete ha offuscato name. */
  function fieldNameKey(el) {
    if (!el || el.nodeType !== 1) return "";
    return String(
      el.getAttribute("data-original-name") || el.name || el.getAttribute("name") || ""
    ).trim();
  }

  function fieldEl(row, name) {
    if (!row) return null;
    // Preferisci input formset righe-N-<campo> (evita collisioni con name testata).
    const formset =
      `input[name^="righe-"][name$="-${name}"],` +
      `textarea[name^="righe-"][name$="-${name}"],` +
      `select[name^="righe-"][name$="-${name}"]`;
    return (
      row.querySelector(formset) ||
      row.querySelector(`[data-original-name$='-${name}']`) ||
      row.querySelector(`[name$='-${name}']`) ||
      row.querySelector(`[id$='-${name}']`)
    );
  }

  function fieldVal(row, name) {
    const el = fieldEl(row, name);
    return el ? el.value : "";
  }

  function collectLines(form) {
    const body = form.querySelector("#righeBody");
    if (!body) return [];
    const lines = [];
    body.querySelectorAll("[data-riga-row]").forEach((row) => {
      if (isRowDeleted(row)) return;
      const codice = String(fieldVal(row, "codice") || "").trim();
      const descrizione = String(fieldVal(row, "descrizione") || "").trim();
      const quantita = parseNum(fieldVal(row, "quantita"));
      const prezzo = parseNum(fieldVal(row, "prezzo_unitario"));
      const sconto = fieldVal(row, "sconto");
      const iva = String(fieldVal(row, "iva") || "").trim();
      if (!codice && !descrizione && !quantita && !prezzo && !sconto && !iva) return;
      lines.push({ codice, descrizione, quantita, prezzo, sconto, iva: iva || "22" });
    });
    return lines;
  }

  function addSpeseEnabled(form) {
    if (!form) return true;
    const el =
      form.querySelector("[name='add_spese']") ||
      form.querySelector("#id_add_spese");
    if (!el) return true;
    if (el.type === "checkbox") return Boolean(el.checked);
    const v = String(el.value || "").trim().toLowerCase();
    return v === "1" || v === "true" || v === "si" || v === "on";
  }

  function speseTotal(form) {
    if (!addSpeseEnabled(form)) return 0;
    const named = [
      "spese_imballo",
      "spese_trasporto",
      "spese_incasso",
      "spese_varie",
      "spese_bolli",
      "spese_e15",
    ];
    const seen = new Set();
    let tot = 0;
    form.querySelectorAll("[data-spese-importo]").forEach((el) => {
      seen.add(el);
      tot += parseNum(el.value);
    });
    named.forEach((name) => {
      const el =
        form.querySelector(`[data-original-name='${name}']`) ||
        form.querySelector(`[name='${name}']`) ||
        form.querySelector(`#id_${name}`);
      if (el && !seen.has(el)) tot += parseNum(el.value);
    });
    return round2(tot);
  }

  function compute(lines, spese) {
    const groups = new Map();
    const order = [];
    let defaultIva = "22";
    let first = true;

    function ensure(code, isSpese) {
      const info = aliquotaInfo(code);
      const key = info.code.toUpperCase() + "|" + (isSpese ? "S" : "M");
      if (!groups.has(key)) {
        const label = isSpese
          ? /\bSPESE\b/i.test(info.label)
            ? info.label
            : info.label + " SPESE"
          : info.label;
        groups.set(key, {
          code: info.code,
          pct: info.pct,
          label,
          isSpese,
          merce: 0,
          sconto: 0,
        });
        order.push(key);
      }
      return groups.get(key);
    }

    lines.forEach((line) => {
      if (first) {
        defaultIva = line.iva || "22";
        first = false;
      }
      let qty = line.quantita;
      const prezzo = line.prezzo;
      if (!qty && !prezzo && !line.codice && !line.descrizione) return;
      if (!qty && prezzo) qty = 1;
      const merce = round2(qty * prezzo);
      const scontoImp = scontoImporto(merce, line.sconto);
      const g = ensure(line.iva || "22", false);
      g.merce = round2(g.merce + merce);
      g.sconto = round2(g.sconto + scontoImp);
    });

    if (spese > 0 || order.length) {
      const configured = String(window.EUREKA_ALIQUOTA_IVA_SPESE || "").trim();
      const speseIva = configured || defaultIva;
      const info = aliquotaInfo(speseIva);
      const merceKey = info.code.toUpperCase() + "|M";
      const speseKey = info.code.toUpperCase() + "|S";
      if (!groups.has(speseKey)) {
        const g = ensure(speseIva, true);
        // reposition after merce group
        const idx = order.indexOf(merceKey);
        const cur = order.indexOf(speseKey);
        if (idx >= 0 && cur >= 0 && cur !== idx + 1) {
          order.splice(cur, 1);
          order.splice(idx + 1, 0, speseKey);
        }
        void g;
      }
      const g = groups.get(speseKey);
      if (g) g.merce = round2(g.merce + spese);
    }

    const rows = [];
    let totMerce = 0;
    let totSconto = 0;
    let totNetto = 0;
    let totIva = 0;
    let totQty = 0;
    order.forEach((key) => {
      const g = groups.get(key);
      const netto = round2(g.merce - g.sconto);
      const iva = round2((netto * g.pct) / 100);
      rows.push({
        merce: g.merce,
        sconto: g.sconto,
        netto,
        iva,
        label: g.label,
        isSpese: g.isSpese,
      });
      totMerce = round2(totMerce + g.merce);
      totSconto = round2(totSconto + g.sconto);
      totNetto = round2(totNetto + netto);
      totIva = round2(totIva + iva);
    });
    lines.forEach((line) => {
      let qty = line.quantita;
      const prezzo = line.prezzo;
      if (!qty && !prezzo && !line.codice && !line.descrizione) return;
      totQty = round2(totQty + (qty || 0));
    });
    return {
      rows,
      totale_merce: totMerce,
      totale_sconto: totSconto,
      totale_netto: totNetto,
      totale_iva: totIva,
      totale_documento: round2(totNetto + totIva),
      totale_quantita: totQty,
    };
  }

  function setTextAll(selector, text) {
    document.querySelectorAll(selector).forEach((el) => {
      el.textContent = text;
    });
  }

  function render(root, result) {
    const tbody = root.querySelector("[data-castelletto-body]");
    if (!tbody) return;
    tbody.innerHTML = "";
    if (!result.rows.length) {
      const tr = document.createElement("tr");
      tr.className = "eureka-doc-castelletto__empty";
      tr.setAttribute("data-castelletto-empty", "");
      tr.innerHTML =
        '<td colspan="6" class="text-secondary text-center py-3">Nessuna riga valorizzata</td>';
      tbody.appendChild(tr);
    } else {
      result.rows.forEach((row) => {
        const tr = document.createElement("tr");
        if (row.isSpese) tr.className = "eureka-doc-castelletto__row--spese";
        tr.innerHTML =
          '<td class="text-end text-nowrap">' +
          formatEuro(row.merce) +
          "</td>" +
          '<td class="text-end text-nowrap">' +
          formatEuro(row.sconto) +
          "</td>" +
          '<td class="text-end text-nowrap">' +
          formatEuro(row.netto) +
          "</td>" +
          "<td>" +
          escapeHtml(row.label) +
          "</td>" +
          '<td class="text-end text-nowrap">' +
          formatEuro(row.iva) +
          "</td>" +
          '<td class="text-end text-nowrap">' +
          formatEuro(round2(row.netto + row.iva)) +
          "</td>";
        tbody.appendChild(tr);
      });
    }
    const merceEl = root.querySelector("[data-castelletto-totale-merce]");
    const scontoEl = root.querySelector("[data-castelletto-totale-sconto]");
    const nettoEl = root.querySelector("[data-castelletto-totale-netto]");
    const ivaEl = root.querySelector("[data-castelletto-totale-iva]");
    const imponIvaEl = root.querySelector("[data-castelletto-totale-imponibile-iva]");
    const docEl = root.querySelector("[data-castelletto-totale-doc]");
    if (merceEl) merceEl.textContent = formatEuro(result.totale_merce || 0);
    if (scontoEl) scontoEl.textContent = formatEuro(result.totale_sconto || 0);
    if (nettoEl) nettoEl.textContent = formatEuro(result.totale_netto);
    if (ivaEl) ivaEl.textContent = formatEuro(result.totale_iva);
    if (imponIvaEl) imponIvaEl.textContent = formatEuro(result.totale_documento);
    if (docEl) docEl.textContent = "EUR " + formatEuro(result.totale_documento);
    setTextAll("[data-totale-quantita]", formatEuro(result.totale_quantita || 0));
  }

  function escapeHtml(s) {
    return String(s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function syncHeaderFields(form, result) {
    const imponibile =
      form.querySelector("[data-castelletto-field='imponibile']") ||
      form.querySelector("#id_imponibile");
    const totale =
      form.querySelector("[data-castelletto-field='totale']") ||
      form.querySelector("#id_totale");
    // Input number vuole punto; display italiano gestito dal browser locale a volte
    if (imponibile) imponibile.value = String(result.totale_netto);
    if (totale) totale.value = String(result.totale_documento);
    const chip = document.querySelector("[data-doc-summary-totale]");
    if (chip) chip.textContent = "€ " + formatEuro(result.totale_documento);
    syncTotaleSpese(form);
  }

  function syncTotaleSpese(form) {
    if (!form) return;
    const el =
      form.querySelector("[data-totale-spese]") ||
      form.querySelector("#id_totale_spese");
    if (!el) return;
    const tot = speseTotal(form);
    el.textContent = formatEuro(tot);
  }

  function isSpeseField(el) {
    const name = fieldNameKey(el);
    return /^(spese_imballo|spese_trasporto|spese_incasso|spese_varie|spese_bolli|spese_e15)$/.test(
      name
    );
  }

  function bindTotaleSpese(form) {
    if (!form) return;
    function onSpese(ev) {
      const name = fieldNameKey(ev.target);
      if (name === "add_spese") {
        syncTotaleSpese(form);
        return;
      }
      if (!isSpeseField(ev.target) || !form.contains(ev.target)) return;
      syncTotaleSpese(form);
    }
    form.addEventListener("input", onSpese, true);
    form.addEventListener("change", onSpese, true);
    syncTotaleSpese(form);
  }

  function recalc(form) {
    const root = document.getElementById("castellettoIva");
    if (!form || !root) return;
    const result = compute(collectLines(form), speseTotal(form));
    render(root, result);
    syncHeaderFields(form, result);
  }

  function csrfToken() {
    const el = document.querySelector("#documentoForm [name=csrfmiddlewaretoken]");
    return el ? el.value : "";
  }

  async function calcPeso(form, root) {
    const url = root.getAttribute("data-calc-peso-url");
    if (!url) return;
    const lines = collectLines(form).map((l) => ({
      codice: l.codice,
      quantita: l.quantita,
    }));
    setTextAll("[data-totale-peso]", "…");
    try {
      const res = await fetch(url, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": csrfToken(),
        },
        body: JSON.stringify({ lines }),
        credentials: "same-origin",
      });
      const data = await res.json();
      const text =
        data && data.ok ? data.totale_peso_fmt || formatEuro(data.totale_peso) : "—";
      setTextAll("[data-totale-peso]", text);
    } catch (_) {
      setTextAll("[data-totale-peso]", "—");
    }
  }

  /**
   * Campi che influenzano il castelletto (formset: righe-N-quantita, …).
   * Capture + whitelist: evita miss se qualcosa ferma il bubble, e ignora
   * filtri/ricerca/numero_riga/imponibile readonly.
   */
  function affectsCastelletto(el) {
    if (!el || el.nodeType !== 1) return false;
    if (el.getAttribute("data-castelletto-field")) return false;
    const name = fieldNameKey(el);
    if (!name) return false;
    if (/-(quantita|prezzo_unitario|sconto|iva|DELETE)$/.test(name)) return true;
    if (
      /^(add_spese|spese_imballo|spese_trasporto|spese_incasso|spese_varie|spese_bolli|spese_e15|codice_sconto|sconto)$/.test(
        name
      )
    ) {
      return true;
    }
    return false;
  }

  function bind(form) {
    const root = document.getElementById("castellettoIva");
    if (!form || !root) return;

    let timer = null;
    let pesoTimer = null;
    function schedulePeso() {
      if (pesoTimer) clearTimeout(pesoTimer);
      pesoTimer = setTimeout(() => calcPeso(form, root), 250);
    }
    function schedule() {
      if (timer) clearTimeout(timer);
      timer = setTimeout(() => {
        recalc(form);
        schedulePeso();
      }, 80);
    }

    function onFieldEvent(ev) {
      const el = ev.target;
      if (!affectsCastelletto(el)) return;
      if (!form.contains(el)) return;
      schedule();
    }

    // Capture: gira prima di stopPropagation su discendenti
    form.addEventListener("input", onFieldEvent, true);
    form.addEventListener("change", onFieldEvent, true);
    form.addEventListener(
      "blur",
      (ev) => {
        const el = ev.target;
        if (!affectsCastelletto(el) || !form.contains(el)) return;
        const key = fieldNameKey(el);
        if (/-(prezzo_unitario)$/.test(key) && String(el.value || "").trim()) {
          const formatted = formatPrezzoUnitario(parseNum(el.value));
          if (formatted && el.value !== formatted) {
            el.value = formatted;
          }
        }
        // qta / prezzo / sconto / iva: ricalcola anche su blur
        schedule();
      },
      true
    );

    const body = form.querySelector("#righeBody");
    if (body && typeof MutationObserver !== "undefined") {
      new MutationObserver(() => schedule()).observe(body, {
        childList: true,
        subtree: false,
      });
    }

    document.addEventListener("click", (ev) => {
      if (ev.target.closest("[data-add-riga], .btn-elimina-riga")) {
        // Dopo add/delete DOM (checkbox DELETE settato senza change nativo)
        setTimeout(() => schedule(), 0);
      }
      const calcBtn = ev.target.closest("[data-castelletto-calc-peso]");
      if (calcBtn && root.contains(calcBtn)) {
        ev.preventDefault();
        calcPeso(form, root);
      }
    });

    form.addEventListener("eureka:castelletto-recalc", () => schedule());

    // Init + ritardo: disable-autocomplete gira su DOMContentLoaded e può
    // arrivare prima; un secondo pass assicura il castelletto in modifica.
    recalc(form);
    schedulePeso();
    setTimeout(() => schedule(), 0);
  }

  function init() {
    const form = document.getElementById("documentoForm");
    if (!form) return;
    if (form.dataset.castellettoBound === "1") {
      recalc(form);
      return;
    }
    form.dataset.castellettoBound = "1";
    bindTotaleSpese(form);
    bind(form);
  }

  window.EurekaDocCastelletto = {
    recalc,
    compute,
    formatEuro,
    formatPrezzoUnitario,
    affectsCastelletto,
    fieldNameKey,
    fieldEl,
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
