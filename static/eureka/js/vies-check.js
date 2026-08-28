(() => {
  const panel = document.getElementById("viesPanel");
  if (!panel) return;

  const btn = document.getElementById("btnViesCheck");
  const metaEl = document.getElementById("viesMeta");
  const statusEl = document.getElementById("viesStatus");
  const resultEl = document.getElementById("viesResult");
  const validEl = document.getElementById("viesResultValid");
  const dateEl = document.getElementById("viesResultDate");
  const nameEl = document.getElementById("viesResultName");
  const addressEl = document.getElementById("viesResultAddress");
  const url = panel.dataset.viesUrl;
  const mode = panel.dataset.viesMode || "detail";
  const autofillEnabled = panel.dataset.viesAutofill === "1";

  function queryField(selector) {
    return selector ? document.querySelector(selector) : null;
  }

  const pivaField = queryField(panel.dataset.viesPartitaIvaField);
  const nazioneField = queryField(panel.dataset.viesNazioneField);
  const ragione1Field = queryField(panel.dataset.viesRagione1Field);
  const ragione2Field = queryField(panel.dataset.viesRagione2Field);
  const indirizzoField = queryField(panel.dataset.viesIndirizzoField);
  const capField = queryField(panel.dataset.viesCapField);
  const localitaField = queryField(panel.dataset.viesLocalitaField);
  const provinciaField = queryField(panel.dataset.viesProvinciaField);

  let previewTimer = null;

  function csrfToken() {
    const input = document.querySelector("[name=csrfmiddlewaretoken]");
    return input ? input.value : "";
  }

  function currentValues() {
    if (mode === "form") {
      return {
        partita_iva: pivaField?.value?.trim() || "",
        cod_nazione: nazioneField?.value?.trim() || "",
      };
    }
    return {
      partita_iva: panel.dataset.viesPartitaIva || "",
      cod_nazione: panel.dataset.viesCodNazione || "",
    };
  }

  function setEligible(eligible) {
    panel.dataset.viesEligible = eligible ? "1" : "0";
    if (btn) btn.disabled = !eligible;
  }

  function showStatus(kind, text) {
    statusEl.className = `alert alert-${kind} py-2 mb-3`;
    statusEl.textContent = text;
    statusEl.classList.remove("d-none");
  }

  function hideStatus() {
    statusEl.classList.add("d-none");
    statusEl.textContent = "";
  }

  function formatDate(value) {
    if (!value) return "—";
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return value;
    return date.toLocaleString("it-IT");
  }

  function isMeaningfulViesValue(value) {
    const text = (value || "").trim();
    return Boolean(text) && text !== "---" && text !== "—";
  }

  function setFieldValue(field, value, { force = false } = {}) {
    if (!field || !isMeaningfulViesValue(value)) return false;
    const next = value.trim();
    if (!force && field.value.trim()) return false;
    field.value = next;
    field.dispatchEvent(new Event("input", { bubbles: true }));
    field.dispatchEvent(new Event("change", { bubbles: true }));
    return true;
  }

  function splitViesName(name) {
    if (!isMeaningfulViesValue(name)) {
      return { ragione1: "", ragione2: "" };
    }
    const lines = name
      .split(/\r?\n/)
      .map((line) => line.trim())
      .filter(Boolean);
    return {
      ragione1: lines[0] || "",
      ragione2: lines.slice(1).join(" ") || "",
    };
  }

  function parseViesAddress(address) {
    if (!isMeaningfulViesValue(address)) return {};

    const lines = address
      .split(/\r?\n/)
      .map((line) => line.trim())
      .filter(Boolean);
    if (!lines.length) return {};

    const parsed = {};
    if (lines.length === 1) {
      parsed.indirizzo = lines[0];
      return parsed;
    }

    parsed.indirizzo = lines.slice(0, -1).join(", ");
    const lastLine = lines[lines.length - 1];

    const itMatch = lastLine.match(/^(\d{5})\s+(.+)$/);
    if (itMatch) {
      parsed.cap = itMatch[1];
      const rest = itMatch[2].trim();
      const provMatch = rest.match(/^(.+?)\s+([A-Z]{2})$/);
      if (provMatch) {
        parsed.localita = provMatch[1].trim();
        parsed.provincia = provMatch[2];
      } else {
        parsed.localita = rest;
      }
      return parsed;
    }

    const euMatch = lastLine.match(/^(\d[\dA-Z\- ]{2,})\s+(.+)$/);
    if (euMatch && lines.length > 1) {
      parsed.cap = euMatch[1].trim();
      parsed.localita = euMatch[2].trim();
      return parsed;
    }

    parsed.indirizzo = lines.join(", ");
    return parsed;
  }

  function applyViesAutofill(data) {
    if (!autofillEnabled || !data.valid) return 0;

    let filled = 0;
    const names = splitViesName(data.name);
    const address = parseViesAddress(data.address);

    if (setFieldValue(ragione1Field, names.ragione1)) filled += 1;
    if (setFieldValue(ragione2Field, names.ragione2)) filled += 1;
    if (setFieldValue(indirizzoField, address.indirizzo)) filled += 1;
    if (setFieldValue(capField, address.cap)) filled += 1;
    if (setFieldValue(localitaField, address.localita)) filled += 1;
    if (setFieldValue(provinciaField, address.provincia)) filled += 1;
    if (setFieldValue(nazioneField, data.country_code)) filled += 1;

    return filled;
  }

  function setResult(data) {
    resultEl.classList.remove("d-none");
    if (data.valid === true) {
      validEl.innerHTML = '<span class="badge bg-success-lt text-success">Valida</span>';
    } else if (data.valid === false) {
      validEl.innerHTML = '<span class="badge bg-danger-lt text-danger">Non valida</span>';
    } else {
      validEl.textContent = "—";
    }
    dateEl.textContent = formatDate(data.request_date);
    nameEl.textContent = data.name || "—";
    addressEl.textContent = (data.address || "—").replace(/\n+/g, ", ");
  }

  function setMetaFromPreview(data) {
    if (!metaEl) return;
    if (data.eligible && data.country_code && data.vat_number) {
      metaEl.innerHTML = `Controllo UE su <strong>${data.country_code} ${data.vat_number}</strong>`;
      return;
    }
    metaEl.textContent = data.message || "Inserire partita IVA e nazione per abilitare la verifica VIES.";
  }

  async function postVies(payload) {
    const response = await fetch(url, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": csrfToken(),
        Accept: "application/json",
      },
      credentials: "same-origin",
      body: JSON.stringify(payload),
    });
    return response.json();
  }

  async function refreshPreview() {
    const values = currentValues();
    resultEl.classList.add("d-none");
    hideStatus();

    if (!values.partita_iva && !values.cod_nazione) {
      metaEl.textContent = "Inserire partita IVA e nazione per abilitare la verifica VIES.";
      setEligible(false);
      return;
    }

    try {
      const data = await postVies({ ...values, preview: true });
      setMetaFromPreview(data);
      setEligible(Boolean(data.eligible));
    } catch (error) {
      metaEl.textContent = "Impossibile valutare i dati VIES inseriti.";
      setEligible(false);
    }
  }

  function schedulePreview() {
    if (mode !== "form") return;
    clearTimeout(previewTimer);
    previewTimer = setTimeout(refreshPreview, 350);
  }

  if (mode === "form") {
    pivaField?.addEventListener("input", schedulePreview);
    nazioneField?.addEventListener("input", schedulePreview);
    pivaField?.addEventListener("change", schedulePreview);
    nazioneField?.addEventListener("change", schedulePreview);
    refreshPreview();
  } else {
    setEligible(panel.dataset.viesEligible === "1");
  }

  btn?.addEventListener("click", async () => {
    if (!url || panel.dataset.viesEligible !== "1") return;

    const values = currentValues();
    btn.disabled = true;
    hideStatus();
    resultEl.classList.add("d-none");
    showStatus("info", "Verifica VIES in corso…");

    try {
      const data = await postVies(values);

      if (!data.ok) {
        showStatus("warning", data.message || "Verifica VIES non riuscita.");
        return;
      }

      hideStatus();
      setResult(data);

      let statusMessage =
        data.message || (data.valid ? "Partita IVA valida." : "Partita IVA non valida.");

      if (data.valid && autofillEnabled) {
        const filled = applyViesAutofill(data);
        if (filled > 0) {
          statusMessage += ` ${filled} campi compilati automaticamente da VIES.`;
        } else if (isMeaningfulViesValue(data.name) || isMeaningfulViesValue(data.address)) {
          statusMessage += " I campi già valorizzati non sono stati sovrascritti.";
        }
      }

      showStatus(data.valid ? "success" : "danger", statusMessage);
    } catch (error) {
      showStatus("warning", "Errore di rete durante la verifica VIES.");
    } finally {
      if (mode === "form") {
        refreshPreview();
      } else {
        setEligible(panel.dataset.viesEligible === "1");
      }
    }
  });
})();
