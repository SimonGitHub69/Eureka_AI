(() => {
  const panel = document.getElementById("cfPanel");
  if (!panel) return;

  const btn = document.getElementById("btnCfCheck");
  const metaEl = document.getElementById("cfMeta");
  const statusEl = document.getElementById("cfStatus");
  const resultEl = document.getElementById("cfResult");
  const validEl = document.getElementById("cfResultValid");
  const kindEl = document.getElementById("cfResultKind");
  const messageEl = document.getElementById("cfResultMessage");
  const url = panel.dataset.cfUrl;
  const mode = panel.dataset.cfMode || "detail";

  function queryField(selector) {
    return selector ? document.querySelector(selector) : null;
  }

  const cfField = queryField(panel.dataset.cfField);
  const nazioneField = queryField(panel.dataset.cfNazioneField);
  const pivaField = queryField(panel.dataset.cfPartitaIvaField);
  const personaField = queryField(panel.dataset.cfPersonaField);

  let previewTimer = null;

  function csrfToken() {
    const input = document.querySelector("[name=csrfmiddlewaretoken]");
    return input ? input.value : "";
  }

  function personaFisicaValue() {
    if (mode === "form") {
      if (!personaField) return null;
      return personaField.type === "checkbox" ? personaField.checked : personaField.value === "on";
    }
    const raw = panel.dataset.cfPersonaFisica;
    if (raw === undefined || raw === "") return null;
    return raw === "1";
  }

  function currentValues() {
    if (mode === "form") {
      return {
        cod_fiscale: cfField?.value?.trim() || "",
        cod_nazione: nazioneField?.value?.trim() || "",
        partita_iva: pivaField?.value?.trim() || "",
        persona_fisica: personaFisicaValue(),
      };
    }
    return {
      cod_fiscale: panel.dataset.cfValue || "",
      cod_nazione: panel.dataset.cfCodNazione || "",
      partita_iva: panel.dataset.cfPartitaIva || "",
      persona_fisica: personaFisicaValue(),
    };
  }

  function setEligible(eligible) {
    panel.dataset.cfEligible = eligible ? "1" : "0";
    if (btn) btn.disabled = !eligible;
  }

  function kindLabel(kind) {
    if (kind === "persona") return "Persona fisica";
    if (kind === "partita_iva") return "Persona giuridica / numerico";
    if (kind === "foreign") return "Estero";
    if (kind === "empty") return "—";
    return kind || "—";
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

  function renderResult(data) {
    if (!data || data.valid == null) {
      resultEl.classList.add("d-none");
      return;
    }
    resultEl.classList.remove("d-none");
    validEl.textContent = data.valid ? "Valido" : "Non valido";
    validEl.className = "eureka-mask-field__value " + (data.valid ? "text-success" : "text-danger");
    kindEl.textContent = kindLabel(data.kind);
    messageEl.textContent = data.message || "—";
  }

  function applyPreview(data) {
    if (!metaEl) return;
    if (data.eligible && data.normalized) {
      metaEl.innerHTML = `Controllo formale su <strong>${data.normalized}</strong>`;
    } else {
      metaEl.textContent = data.message || "Inserire codice fiscale e nazione per abilitare il controllo formale.";
    }
    setEligible(Boolean(data.eligible));
  }

  function applyCheck(data) {
    hideStatus();
    if (!data.eligible) {
      showStatus("secondary", data.message || "Controllo non applicato.");
      renderResult(null);
      return;
    }
    if (data.valid) {
      showStatus("success", data.message || "Codice fiscale valido.");
    } else {
      showStatus("danger", data.message || "Codice fiscale non valido.");
    }
    renderResult(data);
    if (mode === "form" && data.normalized && cfField && cfField.value.trim().toUpperCase() !== data.normalized) {
      cfField.value = data.normalized;
    }
  }

  function postCheck(payload) {
    return fetch(url, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Requested-With": "XMLHttpRequest",
        "X-CSRFToken": csrfToken(),
      },
      body: JSON.stringify(payload),
    }).then((response) => response.json());
  }

  function runPreview() {
    const values = currentValues();
    if (!values.cod_fiscale) {
      applyPreview({ eligible: false, message: "Inserire un codice fiscale per abilitare il controllo formale." });
      renderResult(null);
      hideStatus();
      return;
    }
    postCheck({ preview: true, ...values }).then(applyPreview).catch(() => {
      setEligible(false);
    });
  }

  function runCheck() {
    const values = currentValues();
    if (btn) btn.disabled = true;
    hideStatus();
    postCheck(values)
      .then(applyCheck)
      .catch(() => showStatus("danger", "Errore durante il controllo del codice fiscale."))
      .finally(() => {
        if (panel.dataset.cfEligible === "1") {
          if (btn) btn.disabled = false;
        }
      });
  }

  if (btn) {
    btn.addEventListener("click", runCheck);
  }

  if (mode === "form") {
    const watchFields = [cfField, nazioneField, pivaField, personaField].filter(Boolean);
    watchFields.forEach((field) => {
      field.addEventListener("input", () => {
        clearTimeout(previewTimer);
        previewTimer = setTimeout(runPreview, 220);
      });
      field.addEventListener("change", runPreview);
    });
    runPreview();
  } else {
    const eligible = panel.dataset.cfEligible === "1";
    setEligible(eligible);
    if (eligible && panel.dataset.cfValid !== undefined) {
      applyCheck({
        eligible: true,
        valid: panel.dataset.cfValid === "1",
        kind: panel.dataset.cfKind || "",
        message: panel.dataset.cfMessage || "",
        normalized: panel.dataset.cfValue || "",
      });
    }
  }
})();
