(function () {
  const body = document.body;
  const stylePage = document.getElementById("eureka-libro-page-start");
  const btnBozza = document.getElementById("btnStampaBozza");
  const btn = document.getElementById("btnStampaDefinitiva");
  const dlg = document.getElementById("dlgStampaDefinitiva");
  const form = document.getElementById("formStampaDefinitiva");
  const elData = document.getElementById("dlgDataFinale");
  const elProt = document.getElementById("dlgUltimoProt");
  const elPaginaDa = document.getElementById("dlgPaginaDa");
  const elNumPagine = document.getElementById("dlgNumPagine");
  const elUltimaPagina = document.getElementById("dlgUltimaPagina");
  const elWarn = document.getElementById("dlgWarningSovrappone");

  /**
   * Su macOS Safari (e «Salva come PDF») WebKit:
   * - spezza tabelle troppo alte → fogli fantasma (usiamo blocchi pagina)
   * - intestazioni/piè browser NON si possono disattivare da JS (solo dal dialogo Stampa)
   *
   * La misura DEVE usare la larghezza utile A4 (non quella a schermo):
   * su finestra stretta le celle vanno a capo → altezza gonfiata → mezzo foglio vuoto.
   *
   * @page margin:0 + padding sul foglio: riduce lo spazio riservato alle
   * intestazioni browser dove il motore lo consente; Safari richiede comunque
   * di togliere la spunta nel dialogo Stampa.
   */
  const ua = (typeof navigator !== "undefined" && navigator.userAgent) || "";
  const isMacOS =
    /Macintosh|Mac OS X|MacIntel/i.test(ua) ||
    (typeof navigator !== "undefined" &&
      /Mac/i.test(navigator.platform || ""));
  const isSafariWebKit =
    /AppleWebKit/i.test(ua) &&
    !/Chrome|Chromium|CriOS|Edg|EdgiOS|OPR|Firefox|FxiOS/i.test(ua);
  const isApplePrint = isMacOS || isSafariWebKit;
  /** Margini contenuto (padding foglio); @page resta a 0. */
  const SHEET_PAD_TOP_MM = 5;
  const SHEET_PAD_SIDE_MM = 6;
  const SHEET_PAD_BOTTOM_MM = 4;
  /** Area tabella ≈ 297 − pad top/bottom − piccolo buffer WebKit. */
  const PAGE_INNER_MM = isApplePrint ? 284 : 286;
  const MAX_ROWS_PER_PAGE = 0;
  const APPLE_SAFETY_ROWS = 0;
  const PAGE_MARGIN_CSS = "margin: 0;";
  const SHEET_PAD_CSS =
    "padding: " +
    SHEET_PAD_TOP_MM +
    "mm " +
    SHEET_PAD_SIDE_MM +
    "mm " +
    SHEET_PAD_BOTTOM_MM +
    "mm !important;";

  let paginatedBackup = null;

  const buildPrintCss = (paginaDa) => {
    const da = Math.max(1, parseInt(paginaDa, 10) || 1);
    const reset = da - 1;
    return (
      "@media print {" +
      `html { counter-reset: page ${reset}; }` +
      "body.eureka-print-body--libro-iva { page: auto !important; margin: 0 !important; }" +
      "@page {" +
      "size: A4 portrait;" +
      PAGE_MARGIN_CSS +
      "@top-right { content: none; }" +
      "@top-left { content: none; }" +
      "@bottom-right { content: none; }" +
      "@bottom-left { content: none; }" +
      "}" +
      "body.eureka-print-body--libro-iva .eureka-print-libro-masthead__date { display: none !important; }" +
      "body.eureka-print-body--libro-iva .eureka-print-libro-masthead__doctype { display: block !important; }" +
      "body.eureka-print-body--libro-iva .eureka-print-libro-masthead__page { display: block !important; visibility: visible !important; margin-top: 0.12rem !important; font-size: 8.5pt !important; font-weight: 700 !important; color: #0f172a !important; }" +
      "body.eureka-print-body--libro-iva .eureka-print-libro-riepilogo__head { display: block !important; }" +
      "body.eureka-print-body--libro-iva .eureka-print-sheet { margin: 0 !important; box-shadow: none !important; " +
      SHEET_PAD_CSS +
      " }" +
      "body.eureka-print-body--libro-iva .eureka-print-libro-page {" +
      "page-break-after: always !important; break-after: page !important;" +
      "page-break-inside: avoid !important; break-inside: avoid-page !important;" +
      "}" +
      "body.eureka-print-body--libro-iva .eureka-print-libro-page:last-of-type {" +
      "page-break-after: auto !important; break-after: auto !important;" +
      "}" +
      /* break-before solo per sezioni fuori dai blocchi-pagina (es. riepilogo). */
      "body.eureka-print-body--libro-iva .eureka-print-libro-page-break { page-break-before: always !important; break-before: page !important; }" +
      "body.eureka-print-body--libro-iva .eureka-print-libro-page.eureka-print-libro-page-break { page-break-before: auto !important; break-before: auto !important; }" +
      "body.eureka-print-body--libro-iva .eureka-print-table--libro-iva.eureka-print-libro-page-table {" +
      "page-break-inside: avoid !important; break-inside: avoid !important;" +
      "}" +
      "}"
    );
  };

  const mmToPx = (mm) => {
    const probe = document.createElement("div");
    probe.style.cssText =
      "position:absolute;left:-10000px;top:0;height:" + mm + "mm;width:1px;visibility:hidden;";
    document.body.appendChild(probe);
    const px = probe.offsetHeight;
    probe.remove();
    return px || mm * 3.78;
  };

  const setMastheadPage = (root, pagina) => {
    const da = Math.max(1, parseInt(pagina, 10) || 1);
    const label = "Pag. " + da;
    (root || document).querySelectorAll(".eureka-print-libro-masthead__page").forEach((el) => {
      el.removeAttribute("style");
      el.textContent = label;
    });
  };

  const syncMastheadPagine = (paginaDa) => setMastheadPage(document, paginaDa);

  /**
   * Spezza le righe misurando l'altezza reale (masthead + colonne + righe).
   * Pagine intermedie: tutta l'altezza utile (+ tetto righe su Mac).
   * Ultima pagina: riserva spazio per i «Totali generali» (tfoot).
   */
  const splitRowsByHeight = (table, rows, thead, colClone, tableClass, reserveFooterPx) => {
    const fullMaxPx = mmToPx(PAGE_INNER_MM);
    const footerPx = Math.max(0, reserveFooterPx || 0);
    const maxRows = Math.max(0, MAX_ROWS_PER_PAGE || 0);
    // Larghezza utile A4 (non quella della finestra): evita wrapping falso → margine basso.
    const widthPx = Math.max(mmToPx(210 - SHEET_PAD_SIDE_MM * 2), 500);

    const host = document.createElement("div");
    host.style.cssText =
      "position:absolute;left:-10000px;top:0;width:" +
      widthPx +
      "px;visibility:hidden;pointer-events:none;font-size:7pt;";
    const probe = document.createElement("table");
    probe.className = tableClass;
    probe.style.width = "100%";
    probe.style.tableLayout = "fixed";
    if (colClone) probe.appendChild(colClone.cloneNode(true));
    if (thead) probe.appendChild(thead.cloneNode(true));
    const tbody = document.createElement("tbody");
    probe.appendChild(tbody);
    host.appendChild(probe);
    document.body.appendChild(host);

    const clearBody = () => {
      while (tbody.firstChild) {
        tbody.removeChild(tbody.firstChild);
      }
    };

    const measureRows = (rowList) => {
      clearBody();
      rowList.forEach((tr) => tbody.appendChild(tr.cloneNode(true)));
      return probe.offsetHeight;
    };

    const chunks = [];
    let current = [];

    const flush = () => {
      if (current.length) {
        chunks.push(current);
        current = [];
      }
      clearBody();
    };

    const exceeds = (rowCount, heightPx, limitPx) =>
      heightPx > limitPx || (maxRows > 0 && rowCount > maxRows);

    // 1) Riempi ogni foglio fino a fullMaxPx / tetto righe (senza tfoot).
    rows.forEach((tr) => {
      const clone = tr.cloneNode(true);
      tbody.appendChild(clone);
      const h = probe.offsetHeight;
      const nextCount = current.length + 1;
      if (exceeds(nextCount, h, fullMaxPx) && current.length > 0) {
        tbody.removeChild(clone);
        flush();
        tbody.appendChild(clone);
        current = [tr];
      } else {
        current.push(tr);
      }
    });
    flush();

    // 2) Ultima pagina + totali: se non ci stanno, peela su foglio nuovo.
    if (footerPx > 0 && chunks.length) {
      const lastMaxPx = Math.max(fullMaxPx - footerPx, mmToPx(40));
      let guard = 0;
      while (guard++ < 80 && chunks.length) {
        const last = chunks[chunks.length - 1];
        const h = measureRows(last);
        if (!exceeds(last.length, h, lastMaxPx) || last.length <= 1) break;
        const peeled = [];
        while (
          exceeds(last.length, measureRows(last), lastMaxPx) &&
          last.length > 1
        ) {
          peeled.unshift(last.pop());
        }
        if (!peeled.length) break;
        chunks.push(peeled);
      }
    }

    // 3) Mac: sposta le ultime N righe di ogni pagina alla successiva
    //    (cuscinetto anti-overflow Safari senza lasciare mezzo foglio vuoto).
    if (APPLE_SAFETY_ROWS > 0 && chunks.length > 1) {
      for (let i = 0; i < chunks.length - 1; i++) {
        const n = Math.min(APPLE_SAFETY_ROWS, Math.max(0, chunks[i].length - 8));
        if (n <= 0) continue;
        const moved = chunks[i].splice(chunks[i].length - n, n);
        chunks[i + 1] = moved.concat(chunks[i + 1]);
      }
      // Ripeti peela footer sull'ultima pagina (può essere cresciuta).
      if (footerPx > 0) {
        const lastMaxPx = Math.max(fullMaxPx - footerPx, mmToPx(40));
        let guard = 0;
        while (guard++ < 40 && chunks.length) {
          const last = chunks[chunks.length - 1];
          if (!exceeds(last.length, measureRows(last), lastMaxPx) || last.length <= 1) {
            break;
          }
          const peeled = [];
          while (
            exceeds(last.length, measureRows(last), lastMaxPx) &&
            last.length > 1
          ) {
            peeled.unshift(last.pop());
          }
          if (!peeled.length) break;
          chunks.push(peeled);
        }
      }
    }

    host.remove();
    return chunks.length ? chunks : [rows];
  };

  const restorePagination = () => {
    if (!paginatedBackup) return;
    const { wrap, html, riepilogoBreak } = paginatedBackup;
    if (wrap && html != null) wrap.innerHTML = html;
    if (riepilogoBreak && riepilogoBreak.el) {
      riepilogoBreak.el.classList.toggle(
        "eureka-print-libro-page-break",
        riepilogoBreak.hadBreak
      );
    }
    paginatedBackup = null;
  };

  const preparePaginatedPrint = (paginaDa) => {
    restorePagination();
    const wrap = document.querySelector(
      ".eureka-print-sheet--libro-iva .eureka-print-table-wrap"
    );
    const table = wrap && wrap.querySelector("table.eureka-print-table--libro-iva");
    if (!wrap || !table) {
      setMastheadPage(document, paginaDa);
      return Math.max(1, parseInt(paginaDa, 10) || 1);
    }

    const tbody = table.tBodies[0];
    if (!tbody) {
      setMastheadPage(document, paginaDa);
      return Math.max(1, parseInt(paginaDa, 10) || 1);
    }

    const rows = Array.from(tbody.rows);
    const da = Math.max(1, parseInt(paginaDa, 10) || 1);
    if (!rows.length) {
      setMastheadPage(document, da);
      return da;
    }

    const thead = table.tHead ? table.tHead.cloneNode(true) : null;
    const tfoot = table.tFoot ? table.tFoot.cloneNode(true) : null;
    const colgroup = table.querySelector("colgroup");
    const colClone = colgroup ? colgroup.cloneNode(true) : null;
    const tableClass = table.className;
    const riepilogo = document.querySelector(".eureka-print-libro-riepilogo");
    const riepilogoBreak = riepilogo
      ? {
          el: riepilogo,
          hadBreak: riepilogo.classList.contains("eureka-print-libro-page-break"),
        }
      : null;

    const footerPx = tfoot ? Math.ceil((tfoot.getBoundingClientRect().height || 24) + 4) : 0;

    paginatedBackup = { wrap, html: wrap.innerHTML, riepilogoBreak };

    const chunks = splitRowsByHeight(
      table,
      rows,
      thead,
      colClone,
      tableClass,
      footerPx
    );

    wrap.innerHTML = "";
    chunks.forEach((chunkRowsList, idx) => {
      const pageNum = da + idx;
      // Blocco pagina: Safari rispetta i break tra DIV meglio che dentro TABLE.
      const page = document.createElement("div");
      page.className = "eureka-print-libro-page";
      if (idx > 0) page.classList.add("eureka-print-libro-page-break");

      const pageTable = document.createElement("table");
      pageTable.className = tableClass + " eureka-print-libro-page-table";

      if (colClone) pageTable.appendChild(colClone.cloneNode(true));
      if (thead) {
        const head = thead.cloneNode(true);
        setMastheadPage(head, pageNum);
        pageTable.appendChild(head);
      }

      const bodyEl = document.createElement("tbody");
      chunkRowsList.forEach((tr) => bodyEl.appendChild(tr.cloneNode(true)));
      pageTable.appendChild(bodyEl);

      if (tfoot && idx === chunks.length - 1) {
        pageTable.appendChild(tfoot.cloneNode(true));
      }

      page.appendChild(pageTable);
      wrap.appendChild(page);
    });

    const lastDataPage = da + chunks.length - 1;
    if (riepilogo) {
      // Riepilogo sempre su foglio proprio intestato (sezione fiscale distinta)
      riepilogo.classList.add("eureka-print-libro-page-break");
      setMastheadPage(riepilogo, lastDataPage + 1);
      return lastDataPage + 1;
    }
    return lastDataPage;
  };

  const safePreparePaginatedPrint = (paginaDa) => {
    try {
      return preparePaginatedPrint(paginaDa);
    } catch (err) {
      // Non bloccare la stampa (Safari/WebKit può fallire sulla misura altezza)
      if (typeof console !== "undefined" && console.warn) {
        console.warn("preparePaginatedPrint:", err);
      }
      try {
        setMastheadPage(document, paginaDa);
      } catch (_) {}
      return Math.max(1, parseInt(paginaDa, 10) || 1);
    }
  };

  const usesServerPdf = () => !!(body.dataset.pdfUrl || "").trim();
  let stampaInCorso = false;

  const buildLibroQueryParams = () => {
    const params = new URLSearchParams(window.location.search);
    const pick = (name, el) => {
      if (!el) return;
      const v = (el.value || "").trim();
      if (v) params.set(name, v);
    };
    // Date widget: a schermo è gg/mm/aaaa — per il PDF serve sempre ISO.
    const pickDateIso = (name, el) => {
      if (!el) return;
      const api = window.EurekaPrintDateIT || window.EurekaDateIT;
      let iso = "";
      if (api && typeof api.getIso === "function") {
        iso = (api.getIso(el) || "").trim();
      }
      if (!iso) {
        const raw = (el.value || "").trim();
        if (/^\d{4}-\d{2}-\d{2}$/.test(raw)) iso = raw;
        else if (/^\d{1,2}\/\d{1,2}\/\d{4}$/.test(raw) && api && api.itToIso) {
          iso = (api.itToIso(raw) || "").trim();
        }
      }
      if (iso) params.set(name, iso);
    };
    pick("registro", document.getElementById("id_registro_stampa") || document.getElementById("id_registro"));
    pickDateIso("data_da", document.getElementById("id_data_da"));
    pickDateIso("data_a", document.getElementById("id_data_a"));
    pick("pagina_da", document.getElementById("id_pagina_da") || elPaginaDa);
    const incl = document.getElementById("id_incl_reg_succ");
    if (incl) {
      params.delete("incl_reg_succ");
      params.append("incl_reg_succ", incl.checked ? "1" : "0");
    }
    params.set("anteprima", "1");
    return params;
  };

  const buildServerPdfUrl = () => {
    const base = (body.dataset.pdfUrl || "").trim();
    if (!base) return "";
    let u;
    try {
      u = new URL(base, window.location.origin);
    } catch (_) {
      return "";
    }
    u.search = buildLibroQueryParams().toString();
    return u.toString();
  };

  const buildServerPdfStimaUrl = () => {
    const base = (body.dataset.pdfStimaUrl || "").trim();
    if (!base) return "";
    let u;
    try {
      u = new URL(base, window.location.origin);
    } catch (_) {
      return "";
    }
    u.search = buildLibroQueryParams().toString();
    return u.toString();
  };

  /** Allinea num. pagine / ultima pagina ai fogli reali del PDF (con riepilogo). */
  const applyConteggioPagine = (pagine, paginaDa, ultimaPagina) => {
    const da = Math.max(1, parseInt(paginaDa, 10) || parseInt(body.dataset.paginaDa, 10) || 1);
    const n = Math.max(1, parseInt(pagine, 10) || 1);
    const ultima =
      ultimaPagina != null && String(ultimaPagina).trim() !== ""
        ? Math.max(da, parseInt(ultimaPagina, 10) || da + n - 1)
        : da + n - 1;
    body.dataset.paginaDa = String(da);
    body.dataset.stimaPagine = String(n);
    body.dataset.ultimaPaginaPrevista = String(ultima);
    if (elPaginaDa) elPaginaDa.value = String(da);
    if (elNumPagine) elNumPagine.value = String(n);
    if (elUltimaPagina) elUltimaPagina.value = String(ultima);
    return { da, n, ultima };
  };

  const fetchStimaPaginePdf = () => {
    const url = buildServerPdfStimaUrl();
    if (!url) {
      return Promise.resolve(null);
    }
    return fetch(url, {
      credentials: "same-origin",
      headers: { Accept: "application/json" },
    }).then(async (r) => {
      let data = {};
      try {
        data = await r.json();
      } catch (_) {
        data = {};
      }
      if (!r.ok || !data.ok) {
        throw new Error((data && data.error) || "Conteggio pagine non disponibile");
      }
      return applyConteggioPagine(data.pagine, data.pagina_da, data.ultima_pagina);
    });
  };

  const setStampaBusy = (on, msg) => {
    let el = document.getElementById("eurekaStampaBusy");
    if (on) {
      if (!el) {
        el = document.createElement("div");
        el.id = "eurekaStampaBusy";
        el.setAttribute("role", "status");
        el.setAttribute("aria-live", "polite");
        el.innerHTML =
          '<div class="eureka-pdf-busy__card">' +
          '<div class="eureka-pdf-busy__spin" aria-hidden="true"></div>' +
          '<div class="eureka-pdf-busy__brand">Eureka AI</div>' +
          '<div class="eureka-pdf-busy__title" data-busy-title></div>' +
          '<div class="eureka-pdf-busy__hint">Attendere qualche istante…</div>' +
          "</div>";
        const style = document.createElement("style");
        style.textContent =
          "#eurekaStampaBusy{position:fixed;inset:0;z-index:99999;display:flex;align-items:center;justify-content:center;" +
          "padding:1.5rem;background:rgba(15,23,42,.48);backdrop-filter:blur(4px);-webkit-backdrop-filter:blur(4px)}" +
          "#eurekaStampaBusy[hidden]{display:none!important}" +
          ".eureka-pdf-busy__card{width:min(100%,22rem);background:#fff;border-radius:14px;padding:1.75rem 1.5rem 1.5rem;" +
          "box-shadow:0 24px 48px rgba(15,23,42,.22);text-align:center;font-family:system-ui,-apple-system,Segoe UI,sans-serif}" +
          ".eureka-pdf-busy__spin{width:2.25rem;height:2.25rem;margin:0 auto .9rem;border-radius:50%;" +
          "border:3px solid #e2e8f0;border-top-color:#1d4ed8;animation:eurekaPdfSpin .7s linear infinite}" +
          "@keyframes eurekaPdfSpin{to{transform:rotate(360deg)}}" +
          ".eureka-pdf-busy__brand{font-size:.75rem;font-weight:700;letter-spacing:.08em;text-transform:uppercase;color:#64748b;margin-bottom:.35rem}" +
          ".eureka-pdf-busy__title{font-size:1.05rem;font-weight:700;color:#0f172a;line-height:1.35}" +
          ".eureka-pdf-busy__hint{margin-top:.45rem;font-size:.85rem;color:#64748b}";
        document.head.appendChild(style);
        document.body.appendChild(el);
      }
      el.hidden = false;
      const title = el.querySelector("[data-busy-title]");
      if (title) title.textContent = msg || "Generazione PDF Registro IVA";
    } else if (el) {
      el.hidden = true;
    }
    if (btnBozza) btnBozza.disabled = !!on;
    if (btn) btn.disabled = !!on;
  };

  const avviaStampaBrowser = () => {
    const daRaw = body.dataset.paginaDa || "1";
    applyPageStart(daRaw, { syncLabels: false });
    const ultima = safePreparePaginatedPrint(daRaw);
    const da = Math.max(1, parseInt(daRaw, 10) || 1);
    body.dataset.stimaPagine = String(Math.max(1, ultima - da + 1));
    try {
      window.print();
    } catch (err) {
      if (typeof console !== "undefined" && console.warn) {
        console.warn("window.print:", err);
      }
      alert("Impossibile aprire la finestra di stampa. Usa Cmd+P / Ctrl+P.");
    }
  };

  let pdfPreviewUrl = null;

  const ensurePdfPreviewStyles = () => {
    if (document.getElementById("eurekaPdfPreviewStyles")) return;
    const style = document.createElement("style");
    style.id = "eurekaPdfPreviewStyles";
    style.textContent =
      "#eurekaPdfPreview{position:fixed;inset:0;z-index:100000;display:flex;flex-direction:column;" +
      "background:#0f172a;font-family:system-ui,-apple-system,Segoe UI,sans-serif}" +
      "#eurekaPdfPreview[hidden]{display:none!important}" +
      ".eureka-pdf-app__bar{flex:0 0 auto;display:flex;align-items:center;gap:.75rem;padding:.55rem 1rem;" +
      "background:#111827;color:#e5e7eb;border-bottom:1px solid rgba(255,255,255,.08)}" +
      ".eureka-pdf-app__brand{font-size:.68rem;font-weight:700;letter-spacing:.1em;text-transform:uppercase;color:#94a3b8}" +
      ".eureka-pdf-app__title{flex:1;min-width:0;font-size:.95rem;font-weight:600;color:#f8fafc;white-space:nowrap;" +
      "overflow:hidden;text-overflow:ellipsis}" +
      ".eureka-pdf-app__actions{display:flex;align-items:center;gap:.4rem}" +
      ".eureka-pdf-app__btn{appearance:none;border:1px solid rgba(255,255,255,.14);background:rgba(255,255,255,.06);" +
      "color:#f1f5f9;border-radius:8px;padding:.4rem .75rem;font-size:.82rem;font-weight:600;cursor:pointer}" +
      ".eureka-pdf-app__btn:hover{background:rgba(255,255,255,.12)}" +
      ".eureka-pdf-app__btn--primary{background:#1d4ed8;border-color:#1d4ed8;color:#fff}" +
      ".eureka-pdf-app__btn--primary:hover{background:#1e40af}" +
      ".eureka-pdf-app__frame{flex:1 1 auto;width:100%;border:0;background:#525659}";
    document.head.appendChild(style);
  };

  const closePdfPreview = () => {
    const el = document.getElementById("eurekaPdfPreview");
    if (el) {
      const frame = el.querySelector("iframe");
      if (frame) frame.src = "about:blank";
      el.hidden = true;
    }
    if (pdfPreviewUrl) {
      try {
        URL.revokeObjectURL(pdfPreviewUrl);
      } catch (_) {}
      pdfPreviewUrl = null;
    }
    document.removeEventListener("keydown", onPdfPreviewKeydown, true);
  };

  const onPdfPreviewKeydown = (ev) => {
    if (ev.key === "Escape") {
      ev.preventDefault();
      closePdfPreview();
    }
  };

  const openPdfBlob = (blob) => {
    const pdfBlob =
      blob && blob.type === "application/pdf"
        ? blob
        : new Blob([blob], { type: "application/pdf" });
    ensurePdfPreviewStyles();
    closePdfPreview();
    pdfPreviewUrl = URL.createObjectURL(pdfBlob);

    let el = document.getElementById("eurekaPdfPreview");
    if (!el) {
      el = document.createElement("div");
      el.id = "eurekaPdfPreview";
      el.setAttribute("role", "dialog");
      el.setAttribute("aria-modal", "true");
      el.setAttribute("aria-label", "Anteprima PDF Registro IVA");
      el.innerHTML =
        '<div class="eureka-pdf-app__bar">' +
        '<div class="eureka-pdf-app__brand">Eureka AI</div>' +
        '<div class="eureka-pdf-app__title">Registro IVA — anteprima</div>' +
        '<div class="eureka-pdf-app__actions">' +
        '<button type="button" class="eureka-pdf-app__btn" data-pdf-download>Scarica</button>' +
        '<button type="button" class="eureka-pdf-app__btn eureka-pdf-app__btn--primary" data-pdf-close>Chiudi</button>' +
        "</div></div>" +
        '<iframe class="eureka-pdf-app__frame" title="Anteprima PDF"></iframe>';
      document.body.appendChild(el);
      el.querySelector("[data-pdf-close]").addEventListener("click", closePdfPreview);
      el.querySelector("[data-pdf-download]").addEventListener("click", function () {
        if (!pdfPreviewUrl) return;
        const a = document.createElement("a");
        a.href = pdfPreviewUrl;
        a.download =
          "Registro_IVA_" +
          String(body.dataset.registro || "reg").replace(/[^\w.-]+/g, "_") +
          ".pdf";
        a.rel = "noopener";
        document.body.appendChild(a);
        a.click();
        a.remove();
      });
    }
    const frame = el.querySelector("iframe");
    frame.src = pdfPreviewUrl;
    el.hidden = false;
    document.addEventListener("keydown", onPdfPreviewKeydown, true);
  };

  const avviaStampaPdfServer = () => {
    const pdfUrl = buildServerPdfUrl();
    if (!pdfUrl) {
      avviaStampaBrowser();
      return;
    }
    setStampaBusy(true, "Generazione PDF Registro IVA");
    const ctrl = typeof AbortController !== "undefined" ? new AbortController() : null;
    const timer = setTimeout(function () {
      if (ctrl) ctrl.abort();
    }, 20000);
    fetch(pdfUrl, {
      credentials: "same-origin",
      headers: { Accept: "application/pdf,application/json" },
      signal: ctrl ? ctrl.signal : undefined,
    })
      .then(async (r) => {
        const ctype = (r.headers.get("content-type") || "").toLowerCase();
        if (!r.ok || ctype.indexOf("pdf") < 0) {
          let msg = "PDF non disponibile (HTTP " + r.status + ")";
          try {
            const data = await r.json();
            if (data && data.error) msg = data.error;
          } catch (_) {}
          throw new Error(msg);
        }
        const pagesHdr = r.headers.get("X-Eureka-Pdf-Pages");
        const daHdr = r.headers.get("X-Eureka-Pdf-Pagina-Da");
        const ultimaHdr = r.headers.get("X-Eureka-Pdf-Ultima-Pagina");
        if (pagesHdr) {
          applyConteggioPagine(pagesHdr, daHdr, ultimaHdr);
        }
        return r.blob();
      })
      .then((blob) => {
        openPdfBlob(blob);
      })
      .catch((err) => {
        const msg = (err && err.message) || "Errore generazione PDF";
        if (typeof console !== "undefined" && console.warn) {
          console.warn("PDF server:", err);
        }
        alert(msg + "\n\nApro la stampa dal browser come alternativa.");
        avviaStampaBrowser();
      })
      .finally(() => {
        clearTimeout(timer);
        setStampaBusy(false);
        stampaInCorso = false;
      });
  };

  const avviaStampa = () => {
    if (stampaInCorso) return;
    stampaInCorso = true;
    if (usesServerPdf()) {
      avviaStampaPdfServer();
      return;
    }
    try {
      avviaStampaBrowser();
    } finally {
      stampaInCorso = false;
    }
  };

  const applyPageStart = (paginaDa, { syncLabels = true } = {}) => {
    const da = Math.max(1, parseInt(paginaDa, 10) || 1);
    body.dataset.paginaDa = String(da);
    // Non riscrivere le etichette se la tabella è già spezzata in pagine (Pag. 1, 2, 3…)
    if (syncLabels) {
      syncMastheadPagine(da);
    }
    if (stylePage) stylePage.textContent = buildPrintCss(da);
  };

  const stampaConNumerazione = () => {
    avviaStampa();
  };

  // Anteprima a schermo: un solo masthead → etichetta = pagina da
  applyPageStart(body.dataset.paginaDa || "1", { syncLabels: true });

  window.addEventListener("beforeprint", () => {
    // BUG FIX: non chiamare syncMastheadPagine qui — azzerava tutte le pagine a "Pag. 1"
    // dopo preparePaginatedPrint (che aveva già messo Pag. 1, 2, 3…).
    if (paginatedBackup) {
      applyPageStart(body.dataset.paginaDa || "1", { syncLabels: false });
      return;
    }
    applyPageStart(body.dataset.paginaDa || "1", { syncLabels: false });
    safePreparePaginatedPrint(body.dataset.paginaDa || "1");
  });
  window.addEventListener("afterprint", restorePagination);

  if (btnBozza) {
    btnBozza.addEventListener("click", (ev) => {
      ev.preventDefault();
      stampaConNumerazione();
    });
  }

  const applySuggerimentiPeriodo = (data) => {
    if (!data || !data.ok) return;
    const elDa = document.getElementById("id_data_da");
    const elA = document.getElementById("id_data_a");
    const elPag = document.getElementById("id_pagina_da");
    const dateApi = window.EurekaPrintDateIT;
    if (dateApi) {
      dateApi.setFromIso(elDa, data.data_da || "");
      dateApi.setFromIso(elA, data.data_a || "");
    } else {
      if (elDa) elDa.value = data.data_da || "";
      if (elA) elA.value = data.data_a || "";
    }
    if (elPag) elPag.value = String(data.pagina_da || 1);
    body.dataset.registro = data.registro || body.dataset.registro || "";
    body.dataset.paginaDa = String(data.pagina_da || 1);
    if (data.data_a) body.dataset.dataFinale = data.data_a;
    const meta = document.querySelector(".eureka-print-toolbar__meta");
    if (meta) {
      let span = meta.querySelector("[data-stampa-stato]");
      if (!data.data_finale) {
        if (span) {
          span.textContent = "";
          span.hidden = true;
        }
      } else {
        if (!span) {
          span = document.createElement("span");
          span.className = "eureka-print-toolbar__summary";
          span.setAttribute("data-stampa-stato", "1");
          span.title = "Ultima stampa definitiva";
          meta.appendChild(span);
        }
        const d = String(data.data_finale);
        const parts = d.split("-");
        const label =
          parts.length === 3 ? parts[2] + "/" + parts[1] + "/" + parts[0] : d;
        span.hidden = false;
        span.textContent =
          "Ultima definitiva: " +
          label +
          " · prot. " +
          (data.ultimo_protocollo != null && data.ultimo_protocollo !== ""
            ? data.ultimo_protocollo
            : "—") +
          " · pag. " +
          (data.ultima_pagina != null ? data.ultima_pagina : "0");
      }
    }
  };

  const caricaSuggerimentiRegistro = (codice) => {
    const base = (body.dataset.statoUrl || "").trim();
    const code = (codice || "").trim();
    if (!base || !code) return Promise.resolve(false);
    const url =
      base +
      (base.indexOf("?") >= 0 ? "&" : "?") +
      "registro=" +
      encodeURIComponent(code);
    return fetch(url, {
      headers: { Accept: "application/json" },
      credentials: "same-origin",
    })
      .then(async (r) => {
        let data = {};
        try {
          data = await r.json();
        } catch (_) {
          data = {};
        }
        if (!r.ok || !data.ok) return false;
        applySuggerimentiPeriodo(data);
        return true;
      })
      .catch(() => false);
  };

  /** Ricarica il form con solo il registro: il server propone date/pagina. */
  const ricaricaConRegistro = (codice) => {
    const code = (codice || "").trim();
    if (!code) return;
    const params = new URLSearchParams();
    params.set("registro", code);
    const incl = document.getElementById("id_incl_reg_succ");
    params.set("incl_reg_succ", incl && incl.checked ? "1" : "0");
    window.location.assign(
      window.location.pathname + "?" + params.toString()
    );
  };

  // IMPORTANTE: prima del return su btn/dlg — senza anteprima non c'è btn definitiva
  const selRegistro = document.getElementById("id_registro_stampa");
  if (selRegistro) {
    selRegistro.addEventListener("change", () => {
      const code = (selRegistro.value || "").trim();
      if (!code) return;
      ricaricaConRegistro(code);
    });
    const elDa0 = document.getElementById("id_data_da");
    const code0 = (selRegistro.value || "").trim();
    const daVuota = elDa0
      ? !(window.EurekaPrintDateIT
          ? window.EurekaPrintDateIT.getIso(elDa0)
          : elDa0.value)
      : true;
    if (code0 && elDa0 && daVuota) {
      if (body.dataset.statoUrl) {
        caricaSuggerimentiRegistro(code0).then((ok) => {
          if (!ok) ricaricaConRegistro(code0);
        });
      } else {
        ricaricaConRegistro(code0);
      }
    }
  }

  if (!btn || !dlg) return;

  const syncDefinitivaEnabled = () => {
    const reg =
      (body.dataset.registro || "").trim() ||
      (document.getElementById("id_registro_stampa") || {}).value ||
      "";
    const elA = document.getElementById("id_data_a");
    const dateApi = window.EurekaPrintDateIT;
    const dataA = dateApi
      ? dateApi.getIso(elA)
      : (elA && elA.value) || (body.dataset.dataFinale || "").trim() || "";
    const ok = Boolean(String(reg).trim());
    btn.disabled = !ok;
    if (!ok) {
      btn.title = "Seleziona un registro";
    } else if (!String(dataA).trim()) {
      btn.removeAttribute("title");
    } else {
      btn.removeAttribute("title");
    }
  };

  const btnConferma = document.getElementById("btnConfermaDefinitiva");

  const syncUltima = () => {
    const da = Math.max(1, parseInt(elPaginaDa.value || "1", 10) || 1);
    const n = Math.max(1, parseInt(elNumPagine.value || "1", 10) || 1);
    elUltimaPagina.value = String(da + n - 1);
  };

  elPaginaDa?.addEventListener("input", syncUltima);
  elNumPagine?.addEventListener("input", syncUltima);
  document.getElementById("id_data_a")?.addEventListener("input", syncDefinitivaEnabled);
  document.getElementById("id_registro_stampa")?.addEventListener("change", syncDefinitivaEnabled);
  syncDefinitivaEnabled();

  btn.addEventListener("click", () => {
    const elA = document.getElementById("id_data_a");
    const dateApi = window.EurekaPrintDateIT;
    const dataA = dateApi
      ? dateApi.getIso(elA)
      : (elA && elA.value) || body.dataset.dataFinale || "";
    if (dateApi) {
      dateApi.setFromIso(elData, dataA || body.dataset.dataFinale || "");
    } else {
      elData.value = dataA || body.dataset.dataFinale || "";
    }
    if (!(dateApi ? dateApi.getIso(elData) : elData.value)) {
      alert("Indica la data finale (A data del periodo), poi Applica filtri oppure compilala qui.");
    }
    elProt.value = body.dataset.maxProtocollo || "";
    elPaginaDa.value = body.dataset.paginaDa || "1";
    elNumPagine.value = body.dataset.stimaPagine || "1";
    syncUltima();
    if (elWarn) elWarn.hidden = body.dataset.sovrappone !== "1";
    if (typeof dlg.showModal === "function") dlg.showModal();
    else dlg.setAttribute("open", "");
    // Ricalcola dai fogli PDF reali (riepilogo incluso, anche multi-foglio).
    if (usesServerPdf()) {
      fetchStimaPaginePdf().catch((err) => {
        if (typeof console !== "undefined" && console.warn) {
          console.warn("stima PDF:", err);
        }
      });
    }
  });

  const saveStato = () => {
    const url = body.dataset.confermaUrl;
    const csrf = body.dataset.csrf;
    const registro = (body.dataset.registro || "").trim();
    if (!url || !csrf) return Promise.reject(new Error("URL conferma o CSRF assenti"));
    if (!registro) return Promise.reject(new Error("Codice registro assente"));
    if (!(elData && (window.EurekaPrintDateIT ? window.EurekaPrintDateIT.getIso(elData) : elData.value))) {
      return Promise.reject(new Error("Data finale obbligatoria"));
    }
    syncUltima();
    const fd = new FormData();
    fd.append("registro", registro);
    const dataFinale = window.EurekaPrintDateIT
      ? window.EurekaPrintDateIT.getIso(elData)
      : elData.value;
    fd.append("data_finale", dataFinale);
    fd.append("ultimo_protocollo", (elProt && elProt.value) || "");
    fd.append("ultima_pagina", (elUltimaPagina && elUltimaPagina.value) || "0");
    if ((body.dataset.syncPeriodoLiquidazione || "") === "1") {
      fd.append("sync_periodo_liquidazione", "1");
    }
    return fetch(url, {
      method: "POST",
      headers: { "X-CSRFToken": csrf, Accept: "application/json" },
      body: fd,
      credentials: "same-origin",
    }).then(async (r) => {
      let data = {};
      try {
        data = await r.json();
      } catch (_) {
        data = {};
      }
      if (!r.ok || !data.ok) {
        const err = (data && data.error) || "Salvataggio non riuscito (HTTP " + r.status + ")";
        throw new Error(err);
      }
      return data;
    });
  };

  const aggiornaToolbarStato = (data) => {
    const meta = document.querySelector(".eureka-print-toolbar__meta");
    if (!meta) return;
    let span = meta.querySelector("[data-stampa-stato]");
    if (!data || !data.data_finale) {
      if (span) {
        span.textContent = "";
        span.hidden = true;
      }
      return;
    }
    if (!span) {
      span = document.createElement("span");
      span.className = "eureka-print-toolbar__summary";
      span.setAttribute("data-stampa-stato", "1");
      span.title = "Ultima stampa definitiva";
      meta.appendChild(span);
    }
    const d = String(data.data_finale);
    const parts = d.split("-");
    const label =
      parts.length === 3 ? parts[2] + "/" + parts[1] + "/" + parts[0] : d;
    span.hidden = false;
    span.textContent =
      "Ultima definitiva: " +
      label +
      " · prot. " +
      (data.ultimo_protocollo != null && data.ultimo_protocollo !== ""
        ? data.ultimo_protocollo
        : "—") +
      " · pag. " +
      (data.ultima_pagina != null ? data.ultima_pagina : "0");
  };

  const eseguiDefinitiva = () => {
    const dateApi = window.EurekaPrintDateIT;
    if (dateApi && elData) {
      const iso = dateApi.getIso(elData);
      if (iso) dateApi.setFromIso(elData, iso);
    }
    const dataFinaleIso = dateApi ? dateApi.getIso(elData) : elData && elData.value;
    if (!dataFinaleIso) {
      alert("Indica la data finale (A data del periodo).");
      return;
    }
    // Per il POST: valore ISO nel campo
    if (elData) elData.value = dataFinaleIso;
    applyPageStart(elPaginaDa.value, { syncLabels: false });

    const chiudiDlg = () => {
      if (typeof dlg.close === "function") dlg.close();
      else dlg.removeAttribute("open");
    };

    const dopoConteggio = (conteggio) => {
      let ultima;
      let n;
      if (conteggio) {
        n = conteggio.n;
        ultima = conteggio.ultima;
      } else if (usesServerPdf()) {
        const da = Math.max(1, parseInt(body.dataset.paginaDa, 10) || 1);
        n = Math.max(1, parseInt(body.dataset.stimaPagine, 10) || 1);
        ultima = da + n - 1;
        applyConteggioPagine(n, da, ultima);
      } else {
        ultima = safePreparePaginatedPrint(body.dataset.paginaDa || "1");
        const da = Math.max(1, parseInt(body.dataset.paginaDa, 10) || 1);
        n = Math.max(1, ultima - da + 1);
        applyConteggioPagine(n, da, ultima);
      }

      // Salva e stampa: se il fetch è lento, su Safari print può fallire fuori gesto;
      // in quel caso Cmd+P funziona comunque sul layout già paginato.
      return saveStato()
        .then((data) => {
          aggiornaToolbarStato(data);
          const prevUltima = data.ultima_pagina;
          if (String(prevUltima) !== String(ultima)) {
            return saveStato().then((data2) => aggiornaToolbarStato(data2));
          }
        })
        .then(() => {
          chiudiDlg();
          avviaStampa();
        });
    };

    const avvio = usesServerPdf()
      ? fetchStimaPaginePdf().catch((err) => {
          if (typeof console !== "undefined" && console.warn) {
            console.warn("stima PDF definitiva:", err);
          }
          return null;
        })
      : Promise.resolve(null);

    avvio.then(dopoConteggio).catch((err) => {
      alert((err && err.message) || "Errore di rete nel salvataggio");
    });
  };

  if (btnConferma) {
    btnConferma.addEventListener("click", (ev) => {
      ev.preventDefault();
      eseguiDefinitiva();
    });
  }

  // Fallback se il dialog usa ancora submit
  form?.addEventListener("submit", (ev) => {
    const submitter = ev.submitter || document.activeElement;
    const value = submitter && submitter.value ? submitter.value : "cancel";
    if (value === "confirm") {
      ev.preventDefault();
      eseguiDefinitiva();
    }
  });
})();
