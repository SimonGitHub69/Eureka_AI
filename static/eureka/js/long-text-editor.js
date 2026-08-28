/**
 * Eureka long-text editor — expand textarea/input into a large modal for comfortable editing,
 * or open a read-only viewer for truncated detail text.
 *
 * Markup (edit):
 *   <textarea data-long-text-edit data-long-text-title="Note"></textarea>
 *   <input data-long-text-edit data-long-text-title="Descrizione">
 *
 * Markup (view):
 *   <span data-long-text-view data-long-text-title="Descrizione"
 *         data-long-text-edit-url="/path/to/edit" data-long-text-max="80">
 *     full text here
 *   </span>
 *
 * Public API:
 *   EurekaLongText.enhance(root?)  — wrap fields / truncate views under root
 */
(() => {
  const MODAL_ID = "eurekaLongTextModal";
  const EDIT_ATTR = "data-long-text-edit";
  const VIEW_ATTR = "data-long-text-view";
  const ENHANCED = "data-long-text-enhanced";

  let modalEl = null;
  let bsModal = null;
  let titleEl = null;
  let textareaEl = null;
  let applyBtn = null;
  let editLink = null;
  let footerEdit = null;
  let activeSource = null;
  let activeMode = "edit"; // edit | view

  function ensureModal() {
    if (modalEl) return;
    modalEl = document.createElement("div");
    modalEl.className = "modal modal-blur fade";
    modalEl.id = MODAL_ID;
    modalEl.tabIndex = -1;
    modalEl.setAttribute("aria-hidden", "true");
    modalEl.innerHTML = `
      <div class="modal-dialog modal-lg modal-dialog-centered modal-dialog-scrollable">
        <div class="modal-content eureka-long-text-modal">
          <div class="modal-header py-2">
            <h5 class="modal-title" id="${MODAL_ID}Title">Testo</h5>
            <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Chiudi"></button>
          </div>
          <div class="modal-body py-3">
            <label class="visually-hidden" for="${MODAL_ID}Textarea">Testo</label>
            <textarea id="${MODAL_ID}Textarea" class="form-control eureka-long-text-modal__textarea" rows="14" spellcheck="true"></textarea>
          </div>
          <div class="modal-footer py-2">
            <a href="#" class="btn btn-outline-primary btn-sm me-auto d-none" id="${MODAL_ID}EditLink">
              <i class="ti ti-pencil"></i> Modifica
            </a>
            <button type="button" class="btn btn-outline-secondary btn-sm" data-bs-dismiss="modal">Annulla</button>
            <button type="button" class="btn btn-primary btn-sm" id="${MODAL_ID}Apply">
              <i class="ti ti-check"></i> Applica
            </button>
          </div>
        </div>
      </div>`;
    document.body.appendChild(modalEl);
    titleEl = modalEl.querySelector(`#${MODAL_ID}Title`);
    textareaEl = modalEl.querySelector(`#${MODAL_ID}Textarea`);
    applyBtn = modalEl.querySelector(`#${MODAL_ID}Apply`);
    editLink = modalEl.querySelector(`#${MODAL_ID}EditLink`);
    footerEdit = editLink;

    // Explicit dismiss: Tabler exposes Modal on window.tabler (not window.bootstrap).
    // Relying only on data-bs-dismiss fails when the modal was opened via CSS fallback,
    // because Bootstrap's hide() no-ops when _isShown is false.
    modalEl.querySelectorAll('[data-bs-dismiss="modal"]').forEach((btn) => {
      btn.addEventListener("click", (ev) => {
        ev.preventDefault();
        hideModal();
      });
    });

    applyBtn.addEventListener("click", () => {
      if (activeMode !== "edit" || !activeSource) {
        hideModal();
        return;
      }
      const value = textareaEl.value;
      activeSource.value = value;
      activeSource.dispatchEvent(new Event("input", { bubbles: true }));
      activeSource.dispatchEvent(new Event("change", { bubbles: true }));
      const source = activeSource;
      hideModal();
      try {
        source.focus({ preventScroll: true });
      } catch (_) {
        /* ignore */
      }
    });

    modalEl.addEventListener("hidden.bs.modal", () => {
      resetModalState();
    });

    modalEl.addEventListener("shown.bs.modal", () => {
      textareaEl.focus();
      if (!textareaEl.readOnly) {
        const len = textareaEl.value.length;
        try {
          textareaEl.setSelectionRange(len, len);
        } catch (_) {
          /* ignore */
        }
      }
    });
  }

  function resetModalState() {
    activeSource = null;
    activeMode = "edit";
    if (textareaEl) {
      textareaEl.value = "";
      textareaEl.readOnly = false;
    }
  }

  function getModalCtor() {
    // Tabler UMD factory(global.tabler = {}): Modal lives on window.tabler.Modal
    // (and also window.tabler.bootstrap.Modal). Standalone Bootstrap uses window.bootstrap.
    return (
      (window.bootstrap && window.bootstrap.Modal) ||
      (window.tabler && window.tabler.Modal) ||
      (window.tabler && window.tabler.bootstrap && window.tabler.bootstrap.Modal) ||
      null
    );
  }

  function getBootstrapModal() {
    ensureModal();
    if (bsModal) return bsModal;
    const ModalCtor = getModalCtor();
    if (!ModalCtor) return null;
    bsModal = ModalCtor.getOrCreateInstance
      ? ModalCtor.getOrCreateInstance(modalEl)
      : new ModalCtor(modalEl);
    return bsModal;
  }

  function showModal() {
    const m = getBootstrapModal();
    if (m) {
      m.show();
      return;
    }
    // Last-resort fallback when neither bootstrap nor tabler Modal is available
    modalEl.classList.add("show");
    modalEl.style.display = "block";
    modalEl.removeAttribute("aria-hidden");
    modalEl.setAttribute("aria-modal", "true");
    document.body.classList.add("modal-open");
    if (!document.getElementById(`${MODAL_ID}Backdrop`)) {
      const backdrop = document.createElement("div");
      backdrop.id = `${MODAL_ID}Backdrop`;
      backdrop.className = "modal-backdrop fade show";
      document.body.appendChild(backdrop);
      backdrop.addEventListener("click", () => hideModal());
    }
  }

  function hideModal() {
    const m = getBootstrapModal();
    if (m) {
      m.hide();
      return;
    }
    modalEl.classList.remove("show");
    modalEl.style.display = "none";
    modalEl.setAttribute("aria-hidden", "true");
    modalEl.removeAttribute("aria-modal");
    document.body.classList.remove("modal-open");
    const backdrop = document.getElementById(`${MODAL_ID}Backdrop`);
    if (backdrop) backdrop.remove();
    resetModalState();
  }

  function fieldTitle(el, fallback) {
    const custom = (el.getAttribute("data-long-text-title") || "").trim();
    if (custom) return custom;
    const id = el.id;
    if (id) {
      const label = document.querySelector(`label[for="${CSS.escape(id)}"]`);
      if (label) {
        const t = (label.textContent || "").trim();
        if (t) return t;
      }
    }
    return fallback || "Testo";
  }

  function openEdit(source) {
    ensureModal();
    activeSource = source;
    activeMode = "edit";
    titleEl.textContent = fieldTitle(source, "Modifica testo");
    textareaEl.value = source.value || "";
    textareaEl.readOnly = false;
    applyBtn.classList.remove("d-none");
    footerEdit.classList.add("d-none");
    footerEdit.removeAttribute("href");
    showModal();
  }

  function openView(viewEl) {
    ensureModal();
    activeSource = null;
    activeMode = "view";
    const title = (viewEl.getAttribute("data-long-text-title") || "Testo").trim();
    titleEl.textContent = title;
    const tpl = viewEl.querySelector("template.eureka-long-text-full");
    const full =
      (tpl && tpl.content && tpl.content.textContent) ||
      viewEl.getAttribute("data-long-text-full") ||
      viewEl.textContent ||
      "";
    textareaEl.value = full;
    textareaEl.readOnly = true;
    applyBtn.classList.add("d-none");
    const editUrl = (viewEl.getAttribute("data-long-text-edit-url") || "").trim();
    if (editUrl) {
      footerEdit.href = editUrl;
      footerEdit.classList.remove("d-none");
    } else {
      footerEdit.classList.add("d-none");
      footerEdit.removeAttribute("href");
    }
    showModal();
  }

  function wrapEditField(field) {
    if (field.getAttribute(ENHANCED)) return;
    field.setAttribute(ENHANCED, "1");

    const wrap = document.createElement("div");
    wrap.className = "eureka-long-text";
    field.parentNode.insertBefore(wrap, field);
    wrap.appendChild(field);

    const titleHint = (field.getAttribute("data-long-text-title") || "").toLowerCase();
    const isDescrizione = titleHint.indexOf("descrizione") !== -1;
    const tip = isDescrizione ? "Allarga descrizione" : "Allarga testo";
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "btn btn-icon btn-sm eureka-long-text__btn eureka-long-text__btn--expand";
    btn.title = tip;
    btn.setAttribute("aria-label", tip);
    btn.setAttribute("data-long-text-open", "edit");
    btn.innerHTML = '<i class="ti ti-arrows-maximize" aria-hidden="true"></i>';
    wrap.appendChild(btn);
  }

  function enhanceView(el) {
    if (el.getAttribute(ENHANCED)) return;
    el.setAttribute(ENHANCED, "1");

    let full = "";
    const existingTpl = el.querySelector("template.eureka-long-text-full");
    if (existingTpl) {
      full = existingTpl.content.textContent || "";
    } else {
      full = el.textContent || "";
      el.textContent = "";
      const tpl = document.createElement("template");
      tpl.className = "eureka-long-text-full";
      tpl.content.appendChild(document.createTextNode(full));
      el.appendChild(tpl);
    }

    const max = parseInt(el.getAttribute("data-long-text-max") || "80", 10);
    const needsExpand =
      full.length > max || full.indexOf("\n") !== -1 || full.indexOf("\r") !== -1;

    const short = document.createElement("span");
    short.className = "eureka-long-text-view__text";
    if (!full.trim()) {
      short.textContent = "—";
    } else if (needsExpand) {
      const clipped = full.replace(/\s+/g, " ").trim();
      short.textContent =
        clipped.length > max ? clipped.slice(0, max).trimEnd() + "…" : clipped;
      short.title = clipped.slice(0, 200) + (clipped.length > 200 ? "…" : "");
    } else {
      short.textContent = full;
    }
    el.insertBefore(short, el.firstChild);

    if (needsExpand) {
      el.classList.add("eureka-long-text-view", "eureka-long-text-view--expandable");
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "btn btn-icon btn-sm eureka-long-text__btn eureka-long-text__btn--expand";
      btn.title = "Leggi testo completo";
      btn.setAttribute("aria-label", "Leggi testo completo");
      btn.setAttribute("data-long-text-open", "view");
      btn.innerHTML = '<i class="ti ti-arrows-maximize" aria-hidden="true"></i>';
      el.appendChild(btn);
    } else {
      el.classList.add("eureka-long-text-view");
    }
  }

  function enhance(root) {
    const scope = root && root.querySelectorAll ? root : document;
    scope.querySelectorAll(`[${EDIT_ATTR}]`).forEach(wrapEditField);
    scope.querySelectorAll(`[${VIEW_ATTR}]`).forEach(enhanceView);
    // Also enhance the root itself if it matches
    if (root && root.matches) {
      if (root.matches(`[${EDIT_ATTR}]`)) wrapEditField(root);
      if (root.matches(`[${VIEW_ATTR}]`)) enhanceView(root);
    }
  }

  document.addEventListener("click", (ev) => {
    const btn = ev.target.closest("[data-long-text-open]");
    if (!btn) return;
    ev.preventDefault();
    const mode = btn.getAttribute("data-long-text-open");
    if (mode === "view") {
      const view = btn.closest(`[${VIEW_ATTR}]`);
      if (view) openView(view);
      return;
    }
    const wrap = btn.closest(".eureka-long-text");
    const field =
      (wrap && wrap.querySelector(`[${EDIT_ATTR}]`)) ||
      btn.previousElementSibling;
    if (field && field.matches(`[${EDIT_ATTR}]`)) openEdit(field);
  });

  // Double-click on enhanced field opens modal (edit)
  document.addEventListener("dblclick", (ev) => {
    const field = ev.target.closest(`[${EDIT_ATTR}]`);
    if (!field || !field.getAttribute(ENHANCED)) return;
    openEdit(field);
  });

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", () => enhance(document));
  } else {
    enhance(document);
  }

  window.EurekaLongText = { enhance, openEdit, openView };
})();
