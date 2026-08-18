/**
 * Primanota — scadenze da condizione di pagamento (stesso algoritmo documenti).
 */
(() => {
  const form = document.getElementById("primanotaForm");
  if (!form) return;
  const url = form.getAttribute("data-calc-scadenze-url");
  const scadenzeIns = document.getElementById("id_scadenze_ins");
  const pay = document.getElementById("id_codice_paga");
  const dataDoc = document.getElementById("id_data_doc");
  const dataReg = document.getElementById("id_data_reg");
  const tipo = document.getElementById("id_tipo");
  let timer = 0;

  function isIva() {
    return tipo && (tipo.value === "2" || tipo.value === "4");
  }

  function isGenerico() {
    return tipo && tipo.value === "1";
  }

  function isManual() {
    return Boolean(scadenzeIns && scadenzeIns.checked);
  }

  function isoDate(value) {
    const s = String(value || "").trim();
    if (!s) return "";
    if (/^\d{4}-\d{2}-\d{2}/.test(s)) return s.slice(0, 10);
    const m = s.match(/^(\d{1,2})\/(\d{1,2})\/(\d{4})/);
    if (!m) return "";
    return m[3] + "-" + m[2].padStart(2, "0") + "-" + m[1].padStart(2, "0");
  }

  function baseDate() {
    return isoDate(dataDoc && dataDoc.value) || isoDate(dataReg && dataReg.value);
  }

  function totale() {
    const totals =
      window.EurekaPrimanotaRighe && typeof window.EurekaPrimanotaRighe.getTotals === "function"
        ? window.EurekaPrimanotaRighe.getTotals()
        : { documento: 0, dare: 0, avere: 0 };
    if (isIva()) return totals.documento || 0;
    return totals.dare || totals.avere || 0;
  }

  function slotEls(n) {
    return {
      data: document.getElementById("id_scad" + n),
      importo: document.getElementById("id_imp_scad" + n),
    };
  }

  function clearSlots() {
    for (let i = 1; i <= 10; i += 1) {
      const els = slotEls(i);
      if (els.data) els.data.value = "";
      if (els.importo) els.importo.value = "";
    }
  }

  function fillSlots(rows) {
    clearSlots();
    (rows || []).slice(0, 10).forEach((row, idx) => {
      const els = slotEls(idx + 1);
      const iso = isoDate(row && row.data);
      if (els.data) els.data.value = iso;
      if (els.importo) {
        const imp = row && row.importo;
        els.importo.value =
          imp == null || imp === "" ? "" : Number(imp).toFixed(2);
      }
    });
  }

  function recalc(immediate) {
    if (isGenerico()) {
      clearSlots();
      return;
    }
    if (isManual()) return;
    const run = () => {
      const codice = ((pay && pay.value) || "").trim();
      const data = baseDate();
      if (!codice) {
        clearSlots();
        return;
      }
      if (!url || !data) {
        clearSlots();
        return;
      }
      const qs =
        "?codice=" +
        encodeURIComponent(codice) +
        "&data=" +
        encodeURIComponent(data) +
        "&totale=" +
        encodeURIComponent(String(totale() || "")) +
        "&max_n=10";
      fetch(url + qs, { headers: { "X-Requested-With": "XMLHttpRequest" } })
        .then((r) => (r.ok ? r.json() : null))
        .then((payload) => {
          if (isManual()) return;
          if (!payload || !payload.ok) return;
          fillSlots(payload.scadenze || []);
        })
        .catch(() => {});
    };
    if (immediate) {
      if (timer) window.clearTimeout(timer);
      run();
      return;
    }
    if (timer) window.clearTimeout(timer);
    timer = window.setTimeout(run, 250);
  }

  ["change", "blur"].forEach((ev) => {
    pay?.addEventListener(ev, () => recalc(true));
    dataDoc?.addEventListener(ev, () => recalc(true));
    dataReg?.addEventListener(ev, () => recalc(true));
  });
  tipo?.addEventListener("change", () => recalc(true));
  scadenzeIns?.addEventListener("change", () => {
    if (!isManual()) recalc(true);
  });

  window.EurekaPrimanotaScadenze = { recalc };
  recalc(true);
})();
