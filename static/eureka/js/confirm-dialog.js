(() => {
  const modal = document.getElementById("eurekaConfirmModal");
  if (!modal) return;

  const titleEl = document.getElementById("eurekaConfirmTitle");
  const messageEl = document.getElementById("eurekaConfirmMessage");
  const hintEl = document.getElementById("eurekaConfirmHint");
  const iconEl = document.getElementById("eurekaConfirmIcon");
  const iconGlyphEl = document.getElementById("eurekaConfirmIconGlyph");
  const cancelButtons = modal.querySelectorAll("[data-eureka-confirm-cancel]");
  const acceptButton = modal.querySelector("[data-eureka-confirm-accept]");

  let resolver = null;

  function close(result) {
    modal.hidden = true;
    modal.classList.remove("is-open");
    document.body.classList.remove("eureka-confirm-open");
    if (resolver) {
      const resolve = resolver;
      resolver = null;
      resolve(!!result);
    }
  }

  function applyVariant(variant) {
    if (!iconEl || !iconGlyphEl) return;
    iconEl.classList.remove("is-info", "is-danger", "is-warning");
    iconGlyphEl.className = "ti";
    if (variant === "info") {
      iconEl.classList.add("is-info");
      iconGlyphEl.classList.add("ti-help-circle");
      return;
    }
    if (variant === "warning") {
      iconEl.classList.add("is-warning");
      iconGlyphEl.classList.add("ti-alert-triangle");
      return;
    }
    iconEl.classList.add("is-danger");
    iconGlyphEl.classList.add("ti-trash");
  }

  function ask(options) {
    options = options || {};
    if (!titleEl || !messageEl || !acceptButton) {
      return Promise.resolve(false);
    }
    if (resolver) {
      const previous = resolver;
      resolver = null;
      previous(false);
    }

    const mode = (options.mode || "confirm").trim().toLowerCase();
    const isAlert = mode === "alert" || mode === "info" || mode === "notify";

    titleEl.textContent = options.title || (isAlert ? "Avviso" : "Conferma operazione");
    const message = options.message || "";
    if (options.html) {
      messageEl.innerHTML = message;
    } else {
      messageEl.textContent = message;
    }
    if (hintEl) {
      const hint = (options.hint || "").trim();
      hintEl.textContent = hint;
      hintEl.hidden = !hint;
    }
    acceptButton.textContent = options.confirmLabel || (isAlert ? "Ok" : "Conferma");
    cancelButtons.forEach((btn) => {
      if (btn.tagName === "BUTTON" && btn.classList.contains("btn")) {
        btn.textContent = options.cancelLabel || "Annulla";
        btn.hidden = isAlert;
      }
    });
    acceptButton.className =
      options.confirmClass || (isAlert ? "btn btn-primary" : "btn btn-danger");
    applyVariant(options.variant || (isAlert ? "info" : "danger"));

    modal.hidden = false;
    modal.classList.add("is-open");
    document.body.classList.add("eureka-confirm-open");
    acceptButton.focus();

    return new Promise((resolve) => {
      resolver = resolve;
    });
  }

  function alertDialog(options) {
    if (typeof options === "string") {
      options = { message: options };
    }
    options = options || {};
    return ask({
      mode: "alert",
      title: options.title || "Avviso",
      message: options.message || "",
      hint: options.hint || "",
      confirmLabel: options.confirmLabel || "Ok",
      confirmClass: options.confirmClass || "btn btn-primary",
      variant: options.variant || "info",
      html: !!options.html,
    }).then(() => true);
  }

  cancelButtons.forEach((btn) => {
    btn.addEventListener("click", () => close(false));
  });
  if (acceptButton) {
    acceptButton.addEventListener("click", () => close(true));
  }
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && !modal.hidden) {
      event.preventDefault();
      close(false);
    }
  });

  function confirmAttrs(el) {
    if (!el || !el.getAttribute) return null;
    const message = (el.getAttribute("data-confirm") || "").trim();
    if (!message) return null;
    return {
      title: (el.getAttribute("data-confirm-title") || "").trim() || "Conferma",
      message,
      confirmLabel: (el.getAttribute("data-confirm-ok") || "").trim() || "Elimina",
      cancelLabel: (el.getAttribute("data-confirm-cancel") || "").trim() || "Annulla",
      confirmClass: (el.getAttribute("data-confirm-class") || "").trim() || "btn btn-danger",
      variant: (el.getAttribute("data-confirm-variant") || "").trim() || "danger",
      hint: (el.getAttribute("data-confirm-hint") || "").trim(),
    };
  }

  document.addEventListener(
    "submit",
    (event) => {
      const form = event.target;
      if (!(form instanceof HTMLFormElement)) return;
      if (form.dataset.eurekaConfirmSkip === "1") {
        delete form.dataset.eurekaConfirmSkip;
        return;
      }
      const opts = confirmAttrs(form);
      if (!opts) return;
      event.preventDefault();
      event.stopPropagation();
      ask(opts).then((ok) => {
        if (!ok) return;
        form.dataset.eurekaConfirmSkip = "1";
        if (typeof form.requestSubmit === "function") {
          form.requestSubmit();
        } else {
          form.submit();
        }
      });
    },
    true
  );

  document.addEventListener(
    "click",
    (event) => {
      const btn = event.target.closest("[data-confirm]");
      if (!btn || btn.tagName === "FORM") return;
      if (btn.closest("form[data-confirm]")) return;
      const opts = confirmAttrs(btn);
      if (!opts) return;
      if (btn.type === "submit") return;
      event.preventDefault();
      event.stopPropagation();
      ask(opts).then((ok) => {
        if (!ok) return;
        if (typeof btn.onclick === "function") {
          btn.onclick();
          return;
        }
        const href = btn.getAttribute("href");
        if (href) window.location.href = href;
      });
    },
    true
  );

  window.EurekaConfirm = { ask, alert: alertDialog, close };

  // Sostituisce alert nativo del browser con il dialog Eureka.
  window.alert = function eurekaAlert(message) {
    return alertDialog({ message: String(message == null ? "" : message) });
  };
})();
