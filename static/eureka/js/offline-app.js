/**
 * UI offline: sync + clienti, fatture, classifica, analisi, geografico.
 */
(function () {
    "use strict";

    function $(sel, root) {
        return (root || document).querySelector(sel);
    }

    function $all(sel, root) {
        return Array.prototype.slice.call((root || document).querySelectorAll(sel));
    }

    function formatEuro(value) {
        return (Number(value) || 0).toLocaleString("it-IT", {
            style: "currency",
            currency: "EUR",
            minimumFractionDigits: 2,
            maximumFractionDigits: 2,
        });
    }

    function formatPct(value) {
        return (Number(value) || 0).toLocaleString("it-IT", {
            minimumFractionDigits: 1,
            maximumFractionDigits: 1,
        }) + "%";
    }

    function escapeHtml(s) {
        return String(s || "")
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;");
    }

    function ymd(d) {
        return (
            d.getFullYear()
            + "-"
            + String(d.getMonth() + 1).padStart(2, "0")
            + "-"
            + String(d.getDate()).padStart(2, "0")
        );
    }

    function defaultPeriod() {
        const oggi = new Date();
        return { da: ymd(new Date(oggi.getFullYear(), 0, 1)), a: ymd(oggi) };
    }

    function defaultAnalisiPeriodi() {
        const oggi = new Date();
        if (oggi.getMonth() >= 6) {
            const conA = new Date(oggi.getFullYear() - 1, oggi.getMonth(), oggi.getDate());
            return {
                rifDa: ymd(new Date(oggi.getFullYear(), 0, 1)),
                rifA: ymd(oggi),
                conDa: ymd(new Date(oggi.getFullYear() - 1, 0, 1)),
                conA: ymd(conA),
            };
        }
        const y = oggi.getFullYear() - 1;
        return {
            rifDa: ymd(new Date(y, 0, 1)),
            rifA: ymd(new Date(y, 11, 31)),
            conDa: ymd(new Date(y - 1, 0, 1)),
            conA: ymd(new Date(y - 1, 11, 31)),
        };
    }

    async function fetchJson(url) {
        const res = await fetch(url, {
            credentials: "same-origin",
            headers: { Accept: "application/json" },
        });
        if (!res.ok) throw new Error("HTTP " + res.status);
        return res.json();
    }

    let state = {
        tab: "clienti",
        cliPage: 1,
        fatPage: 1,
        anList: "periodo",
        anData: null,
        geoView: "regioni",
    };

    async function syncAll(cfg, onProgress) {
        const api = cfg.apiUrl;
        const fromDate = cfg.fromDate;
        const DB = window.EurekaOfflineDB;

        onProgress({ message: "Lettura metadati…", pct: 2 });
        const meta = await fetchJson(api + "?dataset=meta");
        DB.clearBusinessData();

        onProgress({ message: "Geografia…", pct: 5 });
        const geo = await fetchJson(api + "?dataset=geo");
        DB.replaceGeo(geo.regioni || [], geo.province || [], geo.nazioni || []);

        let offset = 0;
        let clientiTotal = 1;
        let clientiDone = 0;
        while (true) {
            const chunk = await fetchJson(api + "?dataset=clienti&offset=" + offset + "&limit=1500");
            clientiTotal = chunk.total || clientiTotal;
            DB.upsertClienti(chunk.rows || []);
            clientiDone += (chunk.rows || []).length;
            if (clientiDone % 4500 < (chunk.rows || []).length + 1) await DB.persist();
            onProgress({
                message: "Clienti " + clientiDone + " / " + clientiTotal,
                pct: Math.min(40, 5 + (clientiTotal ? (clientiDone / clientiTotal) * 35 : 35)),
            });
            if (chunk.done || !chunk.next_offset) break;
            offset = chunk.next_offset;
        }

        offset = 0;
        let fattTotal = 1;
        let fattDone = 0;
        while (true) {
            const chunk = await fetchJson(
                api + "?dataset=fatture&from=" + encodeURIComponent(fromDate)
                + "&offset=" + offset + "&limit=1500"
            );
            fattTotal = chunk.total || fattTotal;
            DB.upsertFatture(chunk.rows || []);
            fattDone += (chunk.rows || []).length;
            if (fattDone % 4500 < (chunk.rows || []).length + 1) await DB.persist();
            onProgress({
                message: "Fatture " + fattDone + " / " + fattTotal,
                pct: Math.min(95, 40 + (fattTotal ? (fattDone / fattTotal) * 55 : 55)),
            });
            if (chunk.done || !chunk.next_offset) break;
            offset = chunk.next_offset;
        }

        onProgress({ message: "Salvataggio sul dispositivo…", pct: 97 });
        await DB.saveSyncMeta({
            synced_at: new Date().toISOString(),
            from_date: fromDate,
            server_counts: meta.counts || {},
            local_counts: DB.counts(),
        });
        onProgress({ message: "Sincronizzazione completata", pct: 100 });
        return DB.counts();
    }

    function setProgress(pct, message) {
        const bar = $("#offline-progress-bar");
        const label = $("#offline-progress-label");
        const wrap = $("#offline-progress");
        if (wrap) wrap.hidden = false;
        if (bar) {
            bar.style.width = Math.max(0, Math.min(100, pct)) + "%";
            bar.setAttribute("aria-valuenow", String(Math.round(pct)));
        }
        if (label) label.textContent = message || "";
    }

    function renderStatus() {
        const DB = window.EurekaOfflineDB;
        const counts = DB.counts();
        const syncedAt = DB.metaGet("synced_at");
        const fromDate = DB.metaGet("from_date");
        const el = $("#offline-status");
        if (!el) return;
        if (!counts.fatture && !counts.clienti) {
            el.innerHTML = '<span class="text-secondary">Nessun dato locale. Tocca <strong>Scarica dati</strong>.</span>';
            return;
        }
        el.innerHTML =
            '<div class="d-flex flex-wrap gap-3 small">'
            + '<div><span class="text-secondary">Clienti</span> <strong>'
            + counts.clienti.toLocaleString("it-IT") + "</strong></div>"
            + '<div><span class="text-secondary">Fatture</span> <strong>'
            + counts.fatture.toLocaleString("it-IT") + "</strong></div>"
            + '<div><span class="text-secondary">Dal</span> <strong>'
            + (fromDate || "—") + "</strong></div>"
            + '<div><span class="text-secondary">Sync</span> <strong>'
            + (syncedAt ? new Date(syncedAt).toLocaleString("it-IT") : "—")
            + "</strong></div></div>";
    }

    function setOnlineBadge() {
        const el = $("#offline-network");
        if (!el) return;
        if (navigator.onLine) {
            el.className = "badge bg-green-lt";
            el.textContent = "Online";
        } else {
            el.className = "badge bg-orange-lt";
            el.textContent = "Offline — dati locali";
        }
    }

    function switchTab(name) {
        state.tab = name;
        $all("#offline-tabs [data-offline-tab]").forEach(function (btn) {
            btn.classList.toggle("active", btn.getAttribute("data-offline-tab") === name);
        });
        $all(".offline-panel").forEach(function (panel) {
            panel.classList.toggle("d-none", panel.getAttribute("data-panel") !== name);
        });
        refreshTab(name);
    }

    function pagerHtml(idPrefix, page, perPage, total) {
        const pages = Math.max(1, Math.ceil(total / perPage));
        return (
            '<div class="text-secondary small">'
            + total.toLocaleString("it-IT") + " risultati · pagina " + page + " / " + pages
            + "</div>"
            + '<div class="btn-list">'
            + '<button type="button" class="btn btn-sm btn-outline-secondary" data-page-prev="'
            + idPrefix + '" ' + (page <= 1 ? "disabled" : "") + ">Prec</button>"
            + '<button type="button" class="btn btn-sm btn-outline-secondary" data-page-next="'
            + idPrefix + '" ' + (page >= pages ? "disabled" : "") + ">Succ</button>"
            + "</div>"
        );
    }

    function renderClienti() {
        const DB = window.EurekaOfflineDB;
        const result = DB.listClienti({
            q: ($("#cli-q") || {}).value || "",
            page: state.cliPage,
            perPage: Number(($("#cli-per") || {}).value || 50),
        });
        const body = $("#cli-body");
        if (!body) return;
        if (!result.rows.length) {
            body.innerHTML = '<tr><td colspan="6" class="text-center text-secondary py-4">Nessun cliente</td></tr>';
        } else {
            body.innerHTML = result.rows.map(function (r) {
                return (
                    "<tr>"
                    + "<td class=\"text-secondary\">" + escapeHtml(r.codice) + "</td>"
                    + "<td class=\"fw-semibold\">" + escapeHtml(r.ragione_sociale) + "</td>"
                    + "<td>" + escapeHtml(r.localita) + "</td>"
                    + "<td>" + escapeHtml(r.provincia) + "</td>"
                    + "<td>" + escapeHtml(r.cod_nazione) + "</td>"
                    + "<td>" + escapeHtml(r.telefono) + "</td>"
                    + "</tr>"
                );
            }).join("");
        }
        const pager = $("#cli-pager");
        if (pager) pager.innerHTML = pagerHtml("cli", result.page, result.perPage, result.total);
    }

    function renderFatture() {
        const DB = window.EurekaOfflineDB;
        const result = DB.listFatture({
            q: ($("#fat-q") || {}).value || "",
            dataDa: ($("#fat-da") || {}).value || "",
            dataA: ($("#fat-a") || {}).value || "",
            page: state.fatPage,
            perPage: Number(($("#fat-per") || {}).value || 50),
        });
        const body = $("#fat-body");
        if (!body) return;
        if (!result.rows.length) {
            body.innerHTML = '<tr><td colspan="6" class="text-center text-secondary py-4">Nessuna fattura</td></tr>';
        } else {
            body.innerHTML = result.rows.map(function (r) {
                return (
                    "<tr>"
                    + "<td>" + escapeHtml(r.data_fattura) + "</td>"
                    + "<td>" + escapeHtml(r.numero) + "</td>"
                    + "<td><div class=\"fw-semibold\">" + escapeHtml(r.ragione_sociale) + "</div>"
                    + '<div class="text-secondary small">' + escapeHtml(r.cliente) + "</div></td>"
                    + '<td class="text-end">' + formatEuro(r.imponibile) + "</td>"
                    + '<td class="text-end">' + formatEuro(r.netto) + "</td>"
                    + "<td>" + (r.is_nc ? '<span class="badge bg-orange-lt">NC</span>' : "") + "</td>"
                    + "</tr>"
                );
            }).join("");
        }
        const pager = $("#fat-pager");
        if (pager) pager.innerHTML = pagerHtml("fat", result.page, result.perPage, result.total);
    }

    function renderClassifica() {
        const DB = window.EurekaOfflineDB;
        const opts = {
            dataDa: ($("#cls-da") || {}).value || "",
            dataA: ($("#cls-a") || {}).value || "",
            metrica: ($("#cls-metrica") || {}).value || "imponibile",
            topN: Number(($("#cls-top") || {}).value || 50),
            nc: ($("#cls-nc") || {}).value || "",
        };
        const kpi = DB.kpiPeriodo(opts);
        const result = DB.classificaClienti(opts);
        const kpiEl = $("#cls-kpi");
        if (kpiEl) {
            kpiEl.innerHTML =
                '<div class="row g-2">'
                + '<div class="col-6 col-md-3"><div class="text-secondary small">Fatturato</div>'
                + '<div class="fs-3 fw-bold">' + formatEuro(kpi.fatturato) + "</div></div>"
                + '<div class="col-6 col-md-3"><div class="text-secondary small">Documenti</div>'
                + '<div class="fs-3 fw-bold">' + kpi.n_fatture.toLocaleString("it-IT") + "</div></div>"
                + '<div class="col-6 col-md-3"><div class="text-secondary small">Clienti</div>'
                + '<div class="fs-3 fw-bold">' + kpi.n_clienti.toLocaleString("it-IT") + "</div></div>"
                + '<div class="col-6 col-md-3"><div class="text-secondary small">Top 1</div>'
                + '<div class="fs-3 fw-bold">' + formatPct(result.top1_percentuale) + "</div></div>"
                + "</div>";
        }
        const body = $("#cls-body");
        if (!body) return;
        if (!result.classifica.length) {
            body.innerHTML = '<tr><td colspan="6" class="text-center text-secondary py-4">Nessun dato</td></tr>';
            return;
        }
        body.innerHTML = result.classifica.map(function (r) {
            return (
                "<tr>"
                + "<td class=\"text-secondary\">" + r.posizione + "</td>"
                + "<td><div class=\"fw-semibold\">" + escapeHtml(r.ragione_sociale) + "</div>"
                + '<div class="text-secondary small">' + escapeHtml(r.codice) + "</div></td>"
                + "<td>" + escapeHtml([r.localita, r.provincia].filter(Boolean).join(" · ")) + "</td>"
                + '<td class="text-end">' + formatEuro(r.fatturato) + "</td>"
                + '<td class="text-end">' + formatPct(r.percentuale) + "</td>"
                + '<td class="text-end text-secondary">' + r.n_fatture + "</td>"
                + "</tr>"
            );
        }).join("");
    }

    function renderAnalisiList() {
        const data = state.anData;
        const kind = state.anList;
        const head = $("#an-head");
        const body = $("#an-body");
        if (!data || !head || !body) return;

        $all("#an-list-tabs [data-an-list]").forEach(function (btn) {
            const active = btn.getAttribute("data-an-list") === kind;
            btn.className = "btn btn-sm " + (active ? "btn-primary" : "btn-outline-secondary");
        });

        const rows = data[kind] || [];
        if (kind === "entrambi") {
            head.innerHTML =
                "<tr><th>Cliente</th><th class=\"text-end\">Rif.</th>"
                + "<th class=\"text-end\">Confr.</th><th class=\"text-end\">Delta</th></tr>";
            body.innerHTML = rows.length
                ? rows.map(function (r) {
                    return (
                        "<tr><td><div class=\"fw-semibold\">" + escapeHtml(r.ragione_sociale) + "</div>"
                        + '<div class="text-secondary small">' + escapeHtml(r.codice) + "</div></td>"
                        + '<td class="text-end">' + formatEuro(r.fatturato_rif) + "</td>"
                        + '<td class="text-end">' + formatEuro(r.fatturato_con) + "</td>"
                        + '<td class="text-end">' + formatEuro(r.delta) + "</td></tr>"
                    );
                }).join("")
                : '<tr><td colspan="4" class="text-center text-secondary py-3">Nessun dato</td></tr>';
        } else {
            head.innerHTML =
                "<tr><th>Cliente</th><th>Località</th>"
                + "<th class=\"text-end\">Fatturato</th><th class=\"text-end\">Doc.</th></tr>";
            body.innerHTML = rows.length
                ? rows.map(function (r) {
                    return (
                        "<tr><td><div class=\"fw-semibold\">" + escapeHtml(r.ragione_sociale) + "</div>"
                        + '<div class="text-secondary small">' + escapeHtml(r.codice) + "</div></td>"
                        + "<td>" + escapeHtml([r.localita, r.provincia].filter(Boolean).join(" · ")) + "</td>"
                        + '<td class="text-end">' + formatEuro(r.fatturato) + "</td>"
                        + '<td class="text-end text-secondary">' + r.n_fatture + "</td></tr>"
                    );
                }).join("")
                : '<tr><td colspan="4" class="text-center text-secondary py-3">Nessun dato</td></tr>';
        }
    }

    function renderAnalisi() {
        const DB = window.EurekaOfflineDB;
        state.anData = DB.analisiFatturato({
            rifDa: ($("#an-rif-da") || {}).value || "",
            rifA: ($("#an-rif-a") || {}).value || "",
            conDa: ($("#an-con-da") || {}).value || "",
            conA: ($("#an-con-a") || {}).value || "",
            metrica: ($("#an-metrica") || {}).value || "imponibile",
            nc: "",
            listLimit: 50,
        });
        const d = state.anData;
        const kpiEl = $("#an-kpi");
        if (kpiEl) {
            const deltaLabel =
                d.delta_pct == null ? "—" : ((d.delta_pct >= 0 ? "+" : "") + formatPct(d.delta_pct));
            kpiEl.innerHTML =
                '<div class="row g-2">'
                + '<div class="col-6 col-md-3"><div class="text-secondary small">Fatturato rif.</div>'
                + '<div class="fs-3 fw-bold">' + formatEuro(d.kpi_rif.fatturato) + "</div></div>"
                + '<div class="col-6 col-md-3"><div class="text-secondary small">Fatturato confr.</div>'
                + '<div class="fs-3 fw-bold">' + formatEuro(d.kpi_con.fatturato) + "</div></div>"
                + '<div class="col-6 col-md-3"><div class="text-secondary small">Delta %</div>'
                + '<div class="fs-3 fw-bold">' + deltaLabel + "</div></div>"
                + '<div class="col-6 col-md-3"><div class="text-secondary small">Nuovi / Persi</div>'
                + '<div class="fs-3 fw-bold">' + d.n_nuovi + " / " + d.n_persi + "</div></div>"
                + "</div>";
        }
        const serieEl = $("#an-serie");
        if (serieEl) {
            serieEl.innerHTML = (d.serie_rif || []).map(function (r) {
                return "<div>" + escapeHtml(r.mese) + ": <strong>" + formatEuro(r.fatturato) + "</strong></div>";
            }).join("") || "Nessuna serie";
        }
        renderAnalisiList();
    }

    function renderGeo() {
        const DB = window.EurekaOfflineDB;
        const opts = {
            dataDa: ($("#geo-da") || {}).value || "",
            dataA: ($("#geo-a") || {}).value || "",
            metrica: ($("#geo-metrica") || {}).value || "imponibile",
            nc: "",
        };
        const view = state.geoView || "regioni";

        $all("#geo-view-tabs [data-geo-view]").forEach(function (btn) {
            const active = btn.getAttribute("data-geo-view") === view;
            btn.className = "btn btn-sm " + (active ? "btn-primary" : "btn-outline-secondary");
        });

        const head = $("#geo-head");
        const body = $("#geo-body");
        const kpiEl = $("#geo-kpi");
        if (!head || !body) return;

        if (view === "province") {
            const result = DB.fatturatoPerProvincia(opts);
            if (kpiEl) {
                kpiEl.innerHTML =
                    '<div class="row g-2">'
                    + '<div class="col-6 col-md-4"><div class="text-secondary small">Italia mappata</div>'
                    + '<div class="fs-3 fw-bold">' + formatEuro(result.totale_mappato) + "</div></div>"
                    + '<div class="col-6 col-md-4"><div class="text-secondary small">Province con fatturato</div>'
                    + '<div class="fs-3 fw-bold">' + (result.n_province || 0) + "</div></div>"
                    + "</div>";
            }
            head.innerHTML =
                "<tr><th>Provincia</th><th>Regione</th>"
                + "<th class=\"text-end\">Fatturato</th><th class=\"text-end\">% reg.</th>"
                + "<th class=\"text-end\">Clienti</th><th class=\"text-end\">Doc.</th></tr>";
            const rows = (result.province || []).filter(function (r) {
                return r.fatturato;
            });
            body.innerHTML = rows.length
                ? rows.map(function (r) {
                    return (
                        "<tr>"
                        + "<td><span class=\"fw-semibold\">" + escapeHtml(r.nome) + "</span>"
                        + ' <span class="text-secondary">(' + escapeHtml(r.sigla) + ")</span></td>"
                        + "<td>" + escapeHtml(r.regione_nome) + "</td>"
                        + '<td class="text-end">' + formatEuro(r.fatturato) + "</td>"
                        + '<td class="text-end">' + formatPct(r.percentuale) + "</td>"
                        + '<td class="text-end">' + r.n_clienti + "</td>"
                        + '<td class="text-end text-secondary">' + r.n_fatture + "</td>"
                        + "</tr>"
                    );
                }).join("")
                : '<tr><td colspan="6" class="text-center text-secondary py-4">Nessun dato</td></tr>';
            return;
        }

        if (view === "nazioni" || view === "estero") {
            const result = DB.fatturatoPerNazione(
                Object.assign({}, opts, { soloEstero: view === "estero" })
            );
            if (kpiEl) {
                kpiEl.innerHTML =
                    '<div class="row g-2">'
                    + '<div class="col-6 col-md-4"><div class="text-secondary small">'
                    + (view === "estero" ? "Totale estero" : "Totale nazioni")
                    + "</div>"
                    + '<div class="fs-3 fw-bold">' + formatEuro(result.totale) + "</div></div>"
                    + '<div class="col-6 col-md-4"><div class="text-secondary small">Nazioni</div>'
                    + '<div class="fs-3 fw-bold">' + (result.n_nazioni || 0) + "</div></div>"
                    + '<div class="col-6 col-md-4"><div class="text-secondary small">Clienti</div>'
                    + '<div class="fs-3 fw-bold">' + (result.n_clienti || 0).toLocaleString("it-IT") + "</div></div>"
                    + "</div>";
            }
            head.innerHTML =
                "<tr><th>Nazione</th><th>ISO</th>"
                + "<th class=\"text-end\">Fatturato</th><th class=\"text-end\">%</th>"
                + "<th class=\"text-end\">Clienti</th><th class=\"text-end\">Doc.</th></tr>";
            const rows = result.nazioni || [];
            body.innerHTML = rows.length
                ? rows.map(function (r) {
                    return (
                        "<tr>"
                        + "<td class=\"fw-semibold\">" + escapeHtml(r.nome) + "</td>"
                        + "<td class=\"text-secondary\">" + escapeHtml(r.codice) + "</td>"
                        + '<td class="text-end">' + formatEuro(r.fatturato) + "</td>"
                        + '<td class="text-end">' + formatPct(r.percentuale) + "</td>"
                        + '<td class="text-end">' + r.n_clienti + "</td>"
                        + '<td class="text-end text-secondary">' + r.n_fatture + "</td>"
                        + "</tr>"
                    );
                }).join("")
                : '<tr><td colspan="6" class="text-center text-secondary py-4">Nessun dato</td></tr>';
            return;
        }

        // regioni (default)
        const result = DB.fatturatoPerRegione(opts);
        if (kpiEl) {
            kpiEl.innerHTML =
                '<div class="row g-2">'
                + '<div class="col-6 col-md-4"><div class="text-secondary small">Italia mappata</div>'
                + '<div class="fs-3 fw-bold">' + formatEuro(result.totale_mappato) + "</div></div>"
                + '<div class="col-6 col-md-4"><div class="text-secondary small">Non mappata</div>'
                + '<div class="fs-3 fw-bold">' + formatEuro(result.totale_non_mappato) + "</div></div>"
                + '<div class="col-6 col-md-4"><div class="text-secondary small">Clienti mappati</div>'
                + '<div class="fs-3 fw-bold">' + (result.n_clienti_mappati || 0).toLocaleString("it-IT") + "</div></div>"
                + "</div>";
        }
        head.innerHTML =
            "<tr><th>Regione</th>"
            + "<th class=\"text-end\">Fatturato</th><th class=\"text-end\">%</th>"
            + "<th class=\"text-end\">Clienti</th><th class=\"text-end\">Doc.</th></tr>";
        const rows = (result.regioni || []).filter(function (r) {
            return r.fatturato;
        });
        body.innerHTML = rows.length
            ? rows.map(function (r) {
                return (
                    "<tr>"
                    + "<td class=\"fw-semibold\">" + escapeHtml(r.nome) + "</td>"
                    + '<td class="text-end">' + formatEuro(r.fatturato) + "</td>"
                    + '<td class="text-end">' + formatPct(r.percentuale) + "</td>"
                    + '<td class="text-end">' + r.n_clienti + "</td>"
                    + '<td class="text-end text-secondary">' + r.n_fatture + "</td>"
                    + "</tr>"
                );
            }).join("")
            : '<tr><td colspan="5" class="text-center text-secondary py-4">Nessun dato</td></tr>';
    }

    function refreshTab(name) {
        if (name === "clienti") renderClienti();
        else if (name === "fatture") renderFatture();
        else if (name === "classifica") renderClassifica();
        else if (name === "analisi") renderAnalisi();
        else if (name === "geo") renderGeo();
    }

    async function boot() {
        const root = $("#offline-app");
        if (!root || !window.EurekaOfflineDB) return;

        const period = defaultPeriod();
        const an = defaultAnalisiPeriodi();
        [
            ["fat-da", period.da], ["fat-a", period.a],
            ["cls-da", period.da], ["cls-a", period.a],
            ["geo-da", period.da], ["geo-a", period.a],
            ["an-rif-da", an.rifDa], ["an-rif-a", an.rifA],
            ["an-con-da", an.conDa], ["an-con-a", an.conA],
        ].forEach(function (pair) {
            const el = document.getElementById(pair[0]);
            if (el && !el.value) el.value = pair[1];
        });

        setOnlineBadge();
        window.addEventListener("online", setOnlineBadge);
        window.addEventListener("offline", setOnlineBadge);

        setProgress(0, "Apertura database locale…");
        try {
            await window.EurekaOfflineDB.openDatabase(
                root.dataset.wasmUrl,
                root.dataset.sqlScriptUrl
            );
            $("#offline-progress").hidden = true;
        } catch (err) {
            setProgress(0, "Errore DB: " + (err && err.message ? err.message : err));
            return;
        }

        renderStatus();
        switchTab("clienti");

        $all("#offline-tabs [data-offline-tab]").forEach(function (btn) {
            btn.addEventListener("click", function () {
                switchTab(btn.getAttribute("data-offline-tab"));
            });
        });

        $("#cli-run") && $("#cli-run").addEventListener("click", function () {
            state.cliPage = 1;
            renderClienti();
        });
        $("#fat-run") && $("#fat-run").addEventListener("click", function () {
            state.fatPage = 1;
            renderFatture();
        });
        $("#cls-run") && $("#cls-run").addEventListener("click", renderClassifica);
        $("#an-run") && $("#an-run").addEventListener("click", renderAnalisi);
        $("#geo-run") && $("#geo-run").addEventListener("click", renderGeo);

        $all("#an-list-tabs [data-an-list]").forEach(function (btn) {
            btn.addEventListener("click", function () {
                state.anList = btn.getAttribute("data-an-list");
                renderAnalisiList();
            });
        });

        $all("#geo-view-tabs [data-geo-view]").forEach(function (btn) {
            btn.addEventListener("click", function () {
                state.geoView = btn.getAttribute("data-geo-view");
                renderGeo();
            });
        });

        document.addEventListener("click", function (event) {
            const prev = event.target.closest("[data-page-prev]");
            const next = event.target.closest("[data-page-next]");
            if (prev) {
                const which = prev.getAttribute("data-page-prev");
                if (which === "cli" && state.cliPage > 1) {
                    state.cliPage -= 1;
                    renderClienti();
                }
                if (which === "fat" && state.fatPage > 1) {
                    state.fatPage -= 1;
                    renderFatture();
                }
            }
            if (next) {
                const which = next.getAttribute("data-page-next");
                if (which === "cli") {
                    state.cliPage += 1;
                    renderClienti();
                }
                if (which === "fat") {
                    state.fatPage += 1;
                    renderFatture();
                }
            }
        });

        const syncBtn = $("#offline-sync-btn");
        if (syncBtn) {
            syncBtn.addEventListener("click", async function () {
                if (!navigator.onLine) {
                    window.alert("Serve Wi‑Fi per scaricare i dati.");
                    return;
                }
                syncBtn.disabled = true;
                try {
                    await syncAll(
                        {
                            apiUrl: root.dataset.apiUrl,
                            fromDate: root.dataset.fromDate || "",
                        },
                        function (p) {
                            setProgress(p.pct, p.message);
                        }
                    );
                    renderStatus();
                    refreshTab(state.tab);
                    window.setTimeout(function () {
                        const wrap = $("#offline-progress");
                        if (wrap) wrap.hidden = true;
                    }, 800);
                } catch (err) {
                    setProgress(0, "Sync fallita: " + (err && err.message ? err.message : err));
                } finally {
                    syncBtn.disabled = false;
                }
            });
        }
    }

    document.addEventListener("DOMContentLoaded", boot);
})();
