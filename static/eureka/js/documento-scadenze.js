(() => {
  const card = document.getElementById("scadenzeCard");
  const form = document.getElementById("documentoForm");
  const list = document.getElementById("scadenzeList");
  if (!card || !form || !list) return;
  const url = card.dataset.calcScadenzeUrl;
  const addBtn = document.getElementById("btnAddScadenza");

  const pay = document.getElementById("id_cod_pagamento");
  const dataEl = document.getElementById("id_data_documento");
  const totEl = document.getElementById("id_totale");

  function isoDate(value) {
    const s = String(value || "").trim();
    if (!s) return "";
    if (/^\d{4}-\d{2}-\d{2}/.test(s)) return s.slice(0, 10);
    const m = s.match(/^(\d{1,2})\/(\d{1,2})\/(\d{4})/);
    if (!m) return s;
    return m[3] + "-" + m[2].padStart(2, "0") + "-" + m[1].padStart(2, "0");
  }

  function inputs() {
    return Array.from(list.querySelectorAll('input[name="scadenza"]'));
  }

  function formatDateIT(iso) {
    const m = String(iso || "").trim().match(/^(\d{4})-(\d{2})-(\d{2})/);
    if (!m) return String(iso || "").trim();
    return m[3] + "/" + m[2] + "/" + m[1];
  }

  function updateSummary() {
    const badge = document.getElementById("scadenzeCountBadge");
    const slots = list.querySelectorAll(".eureka-doc-scadenze__slot");
    const dates = inputs()
      .map((el) => (el.value || "").trim())
      .filter(Boolean);
    if (badge) {
      badge.textContent = String(slots.length);
      badge.title = "Numero scadenze";
    }
    const range = card.querySelector("[data-doc-summary-range]");
    if (!range) return;
    if (!dates.length) {
      range.hidden = true;
      range.setAttribute("aria-hidden", "true");
      range.textContent = "";
      return;
    }
    range.hidden = false;
    range.setAttribute("aria-hidden", "false");
    if (dates.length === 1) {
      range.textContent = formatDateIT(dates[0]);
      range.title = "Scadenza";
    } else {
      range.textContent =
        formatDateIT(dates[0]) + " → " + formatDateIT(dates[dates.length - 1]);
      range.title = "Prima / ultima scadenza";
    }
  }

  function renumber() {
    list.querySelectorAll(".eureka-doc-scadenze__num").forEach((el, idx) => {
      el.textContent = String(idx + 1);
    });
    updateSummary();
  }

  function makeSlot(value) {
    const wrap = document.createElement("div");
    wrap.className = "eureka-doc-scadenze__slot";
    wrap.setAttribute("role", "listitem");
    const head = document.createElement("div");
    head.className = "eureka-doc-scadenze__head";
    const label = document.createElement("label");
    label.className = "eureka-doc-scadenze__num";
    const remove = document.createElement("button");
    remove.type = "button";
    remove.className =
      "btn btn-ghost-danger btn-icon btn-sm eureka-doc-scadenze__remove";
    remove.setAttribute("data-remove-scadenza", "");
    remove.title = "Rimuovi scadenza";
    remove.setAttribute("aria-label", "Rimuovi scadenza");
    remove.innerHTML = '<i class="ti ti-x"></i>';
    const input = document.createElement("input");
    input.type = "date";
    input.name = "scadenza";
    input.className = "form-control";
    input.autocomplete = "off";
    input.value = value || "";
    head.appendChild(label);
    head.appendChild(remove);
    wrap.appendChild(head);
    wrap.appendChild(input);
    return wrap;
  }

  function removeSlot(slot) {
    if (!slot) return;
    const slots = list.querySelectorAll(".eureka-doc-scadenze__slot");
    if (slots.length <= 1) {
      const input = slot.querySelector('input[name="scadenza"]');
      if (input) input.value = "";
      updateSummary();
      return;
    }
    slot.remove();
    renumber();
  }

  function renderSlots(values) {
    const rows = values && values.length ? values : [""];
    list.innerHTML = "";
    rows.forEach((value) => list.appendChild(makeSlot(value)));
    renumber();
  }

  function apply(rows, overwrite) {
    const current = inputs().map((el) => (el.value || "").trim());
    const filled = current.some(Boolean);
    if (!overwrite && filled) return;
    const values = (rows || [])
      .map((row) => (row && row.data ? String(row.data) : ""))
      .filter(Boolean);
    renderSlots(values);
  }

  function recalc(overwrite) {
    if (!url) return;
    const codice = ((pay && pay.value) || "").trim();
    const data = isoDate(dataEl && dataEl.value);
    if (!codice || !data) return;
    const qs =
      "?codice=" + encodeURIComponent(codice.trim()) +
      "&data=" + encodeURIComponent(data) +
      "&totale=" + encodeURIComponent((totEl && totEl.value) || "");
    fetch(url + qs, { headers: { "X-Requested-With": "XMLHttpRequest" } })
      .then((r) => r.json())
      .then((payload) => {
        if (!payload || !payload.ok) return;
        apply(payload.scadenze || [], overwrite);
      })
      .catch(() => {});
  }

  window.EurekaDocScadenze = { recalc, renderSlots };

  if (addBtn) {
    addBtn.addEventListener("click", () => {
      list.appendChild(makeSlot(""));
      renumber();
      const last = inputs().pop();
      if (last) last.focus();
    });
  }

  list.addEventListener("click", (ev) => {
    const btn = ev.target.closest("[data-remove-scadenza]");
    if (!btn || !list.contains(btn)) return;
    ev.preventDefault();
    removeSlot(btn.closest(".eureka-doc-scadenze__slot"));
  });

  list.addEventListener("change", (ev) => {
    if (ev.target && ev.target.matches('input[name="scadenza"]')) {
      updateSummary();
    }
  });

  ["change", "blur"].forEach((ev) => {
    if (pay) pay.addEventListener(ev, () => recalc(true));
    if (dataEl) dataEl.addEventListener(ev, () => recalc(true));
  });
  updateSummary();
  recalc(false);
})();
