/**
 * SQLite locale (sql.js) + query offline: clienti, fatture, classifica, analisi, geo.
 */
(function (global) {
    "use strict";

    const DB_NAME = "eureka-offline";
    const STORE = "sqlite";
    const KEY = "db";
    const META_KEY = "meta";

    const PROV_REG_OVERRIDE = {
        OT: "20", OG: "20", CI: "20", VS: "20", FO: "08", PS: "11",
    };

    const SCHEMA_SQL = `
CREATE TABLE IF NOT EXISTS meta (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS clienti (
  codice TEXT PRIMARY KEY,
  ragione_sociale1 TEXT,
  ragione_sociale2 TEXT,
  indirizzo TEXT,
  localita TEXT,
  cap TEXT,
  provincia TEXT,
  cod_nazione TEXT,
  partita_iva TEXT,
  telefono TEXT,
  email TEXT,
  cliente_fittizio INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS fatture (
  id_testa INTEGER PRIMARY KEY,
  numero_fatt INTEGER,
  data_fattura TEXT,
  cliente TEXT,
  imponibile REAL,
  totale_fattura REAL,
  alfa TEXT,
  tipo_doc_fe TEXT,
  spese_imballo REAL,
  spese_trasporto REAL,
  spese_incasso REAL,
  spese_varie REAL,
  spese_bolli REAL,
  spese_e15 REAL
);
CREATE INDEX IF NOT EXISTS idx_fatture_data ON fatture(data_fattura);
CREATE INDEX IF NOT EXISTS idx_fatture_cliente ON fatture(cliente);
CREATE INDEX IF NOT EXISTS idx_clienti_rs ON clienti(ragione_sociale1);
CREATE TABLE IF NOT EXISTS regioni (
  codice TEXT PRIMARY KEY,
  nome TEXT
);
CREATE TABLE IF NOT EXISTS province (
  sigla TEXT PRIMARY KEY,
  nome TEXT,
  regione TEXT
);
CREATE TABLE IF NOT EXISTS nazioni (
  codice TEXT PRIMARY KEY,
  nome TEXT
);
`;

    let SQL = null;
    let db = null;

    function openIdb() {
        return new Promise(function (resolve, reject) {
            const req = indexedDB.open(DB_NAME, 1);
            req.onupgradeneeded = function () {
                const idb = req.result;
                if (!idb.objectStoreNames.contains(STORE)) {
                    idb.createObjectStore(STORE);
                }
            };
            req.onsuccess = function () {
                resolve(req.result);
            };
            req.onerror = function () {
                reject(req.error || new Error("IndexedDB non disponibile"));
            };
        });
    }

    function idbGet(key) {
        return openIdb().then(function (idb) {
            return new Promise(function (resolve, reject) {
                const tx = idb.transaction(STORE, "readonly");
                const req = tx.objectStore(STORE).get(key);
                req.onsuccess = function () {
                    resolve(req.result || null);
                };
                req.onerror = function () {
                    reject(req.error);
                };
            });
        });
    }

    function idbSet(key, value) {
        return openIdb().then(function (idb) {
            return new Promise(function (resolve, reject) {
                const tx = idb.transaction(STORE, "readwrite");
                tx.objectStore(STORE).put(value, key);
                tx.oncomplete = function () {
                    resolve();
                };
                tx.onerror = function () {
                    reject(tx.error);
                };
            });
        });
    }

    async function initSqlJs(wasmUrl, scriptUrl) {
        if (SQL) return SQL;
        if (typeof global.initSqlJs !== "function") {
            await new Promise(function (resolve, reject) {
                const s = document.createElement("script");
                s.src = scriptUrl;
                s.onload = resolve;
                s.onerror = function () {
                    reject(new Error("Impossibile caricare sql.js"));
                };
                document.head.appendChild(s);
            });
        }
        SQL = await global.initSqlJs({
            locateFile: function () {
                return wasmUrl;
            },
        });
        return SQL;
    }

    function migrateSchema() {
        const alters = [
            "ALTER TABLE clienti ADD COLUMN indirizzo TEXT",
            "ALTER TABLE clienti ADD COLUMN cap TEXT",
            "ALTER TABLE clienti ADD COLUMN telefono TEXT",
            "ALTER TABLE clienti ADD COLUMN email TEXT",
            "ALTER TABLE fatture ADD COLUMN numero_fatt INTEGER",
        ];
        alters.forEach(function (sql) {
            try {
                db.run(sql);
            } catch (e) { /* column exists */ }
        });
    }

    async function openDatabase(wasmUrl, scriptUrl) {
        await initSqlJs(wasmUrl, scriptUrl);
        const saved = await idbGet(KEY);
        if (saved && saved.byteLength) {
            db = new SQL.Database(new Uint8Array(saved));
        } else {
            db = new SQL.Database();
        }
        db.run(SCHEMA_SQL);
        migrateSchema();
        return db;
    }

    async function persist() {
        if (!db) return;
        const data = db.export();
        await idbSet(KEY, data.buffer.slice(data.byteOffset, data.byteOffset + data.byteLength));
    }

    function getDb() {
        return db;
    }

    function metaGet(key) {
        if (!db) return null;
        const stmt = db.prepare("SELECT value FROM meta WHERE key = ?");
        stmt.bind([key]);
        let value = null;
        if (stmt.step()) {
            value = stmt.getAsObject().value;
        }
        stmt.free();
        return value;
    }

    function metaSet(key, value) {
        if (!db) return;
        db.run(
            "INSERT INTO meta(key, value) VALUES(?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            [key, String(value)]
        );
    }

    function counts() {
        if (!db) {
            return { clienti: 0, fatture: 0, regioni: 0, province: 0 };
        }
        function one(sql) {
            const r = db.exec(sql);
            if (!r.length || !r[0].values.length) return 0;
            return r[0].values[0][0] || 0;
        }
        return {
            clienti: one("SELECT COUNT(*) FROM clienti"),
            fatture: one("SELECT COUNT(*) FROM fatture"),
            regioni: one("SELECT COUNT(*) FROM regioni"),
            province: one("SELECT COUNT(*) FROM province"),
            nazioni: one("SELECT COUNT(*) FROM nazioni"),
        };
    }

    function clearBusinessData() {
        if (!db) return;
        db.run("DELETE FROM fatture");
        db.run("DELETE FROM clienti");
        db.run("DELETE FROM regioni");
        db.run("DELETE FROM province");
        db.run("DELETE FROM nazioni");
    }

    function upsertClienti(rows) {
        if (!db || !rows || !rows.length) return;
        const stmt = db.prepare(
            "INSERT OR REPLACE INTO clienti(codice,ragione_sociale1,ragione_sociale2,indirizzo,localita,cap,provincia,cod_nazione,partita_iva,telefono,email,cliente_fittizio) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)"
        );
        db.run("BEGIN");
        try {
            rows.forEach(function (r) {
                stmt.run([
                    r.codice,
                    r.ragione_sociale1 || "",
                    r.ragione_sociale2 || "",
                    r.indirizzo || "",
                    r.localita || "",
                    r.cap || "",
                    r.provincia || "",
                    r.cod_nazione || "",
                    r.partita_iva || "",
                    r.telefono || "",
                    r.email || "",
                    r.cliente_fittizio ? 1 : 0,
                ]);
            });
            db.run("COMMIT");
        } catch (e) {
            db.run("ROLLBACK");
            throw e;
        } finally {
            stmt.free();
        }
    }

    function upsertFatture(rows) {
        if (!db || !rows || !rows.length) return;
        const stmt = db.prepare(
            "INSERT OR REPLACE INTO fatture(id_testa,numero_fatt,data_fattura,cliente,imponibile,totale_fattura,alfa,tipo_doc_fe,spese_imballo,spese_trasporto,spese_incasso,spese_varie,spese_bolli,spese_e15) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)"
        );
        db.run("BEGIN");
        try {
            rows.forEach(function (r) {
                stmt.run([
                    r.id_testa,
                    r.numero_fatt != null ? r.numero_fatt : null,
                    r.data_fattura || "",
                    r.cliente || "",
                    r.imponibile || 0,
                    r.totale_fattura || 0,
                    r.alfa || "",
                    r.tipo_doc_fe || "",
                    r.spese_imballo || 0,
                    r.spese_trasporto || 0,
                    r.spese_incasso || 0,
                    r.spese_varie || 0,
                    r.spese_bolli || 0,
                    r.spese_e15 || 0,
                ]);
            });
            db.run("COMMIT");
        } catch (e) {
            db.run("ROLLBACK");
            throw e;
        } finally {
            stmt.free();
        }
    }

    function replaceGeo(regioni, province, nazioni) {
        if (!db) return;
        db.run("BEGIN");
        try {
            db.run("DELETE FROM regioni");
            db.run("DELETE FROM province");
            db.run("DELETE FROM nazioni");
            const sr = db.prepare("INSERT INTO regioni(codice,nome) VALUES(?,?)");
            (regioni || []).forEach(function (r) {
                sr.run([r.codice, r.nome]);
            });
            sr.free();
            const sp = db.prepare("INSERT INTO province(sigla,nome,regione) VALUES(?,?,?)");
            (province || []).forEach(function (p) {
                sp.run([p.sigla, p.nome, p.regione]);
            });
            sp.free();
            const sn = db.prepare("INSERT INTO nazioni(codice,nome) VALUES(?,?)");
            (nazioni || []).forEach(function (n) {
                sn.run([n.codice, n.nome]);
            });
            sn.free();
            db.run("COMMIT");
        } catch (e) {
            db.run("ROLLBACK");
            throw e;
        }
    }

    const ISO_CANONICO = { EL: "GR", UK: "GB" };

    function isoCanonico(value) {
        const iso = String(value || "").trim().toUpperCase();
        if (!iso) return "";
        return ISO_CANONICO[iso] || iso;
    }

    function loadProvinciaMeta() {
        const siglaToReg = {};
        const provMeta = {};
        const pStmt = db.prepare("SELECT sigla, nome, regione FROM province");
        while (pStmt.step()) {
            const o = pStmt.getAsObject();
            const sigla = String(o.sigla || "").toUpperCase();
            siglaToReg[sigla] = String(o.regione || "");
            provMeta[sigla] = { nome: o.nome || sigla, regione: String(o.regione || "") };
        }
        pStmt.free();
        Object.keys(PROV_REG_OVERRIDE).forEach(function (k) {
            siglaToReg[k] = PROV_REG_OVERRIDE[k];
            if (!provMeta[k]) {
                provMeta[k] = { nome: k, regione: PROV_REG_OVERRIDE[k] };
            }
        });
        return { siglaToReg: siglaToReg, provMeta: provMeta };
    }

    function loadRegioniNomi() {
        const regNomi = {};
        const rStmt = db.prepare("SELECT codice, nome FROM regioni");
        while (rStmt.step()) {
            const o = rStmt.getAsObject();
            regNomi[o.codice] = o.nome;
        }
        rStmt.free();
        return regNomi;
    }

    function loadNazioniNomi() {
        const nomi = {};
        const stmt = db.prepare("SELECT codice, nome FROM nazioni");
        while (stmt.step()) {
            const o = stmt.getAsObject();
            nomi[String(o.codice || "").toUpperCase()] = o.nome || o.codice;
        }
        stmt.free();
        return nomi;
    }

    function clienteGeo(codice) {
        const cStmt = db.prepare(
            "SELECT provincia, UPPER(TRIM(COALESCE(cod_nazione,''))) AS iso FROM clienti WHERE codice = ?"
        );
        cStmt.bind([codice]);
        let out = { provincia: "", iso: "" };
        if (cStmt.step()) {
            const o = cStmt.getAsObject();
            out = {
                provincia: String(o.provincia || "").toUpperCase(),
                iso: isoCanonico(o.iso || ""),
            };
        }
        cStmt.free();
        return out;
    }

    function metricaCol(metrica) {
        return metrica === "totale" ? "totale_fattura" : "imponibile";
    }

    function ncFilterSql(nc, alias) {
        alias = alias || "f";
        nc = (nc || "").toLowerCase();
        if (nc === "escludi") {
            return " AND UPPER(TRIM(COALESCE(" + alias + ".tipo_doc_fe,''))) != 'TD04' ";
        }
        if (nc === "solo") {
            return " AND UPPER(TRIM(COALESCE(" + alias + ".tipo_doc_fe,''))) = 'TD04' ";
        }
        return "";
    }

    function nettoExpr(metrica, alias) {
        alias = alias || "f";
        const col = metricaCol(metrica);
        return (
            "(CASE WHEN UPPER(TRIM(COALESCE(" + alias + ".tipo_doc_fe,''))) = 'TD04' "
            + "THEN -ABS(COALESCE(" + alias + "." + col + ",0)) "
            + "ELSE COALESCE(" + alias + "." + col + ",0) END "
            + "- ABS("
            + "COALESCE(" + alias + ".spese_imballo,0)+COALESCE(" + alias + ".spese_trasporto,0)"
            + "+COALESCE(" + alias + ".spese_incasso,0)+COALESCE(" + alias + ".spese_varie,0)"
            + "+COALESCE(" + alias + ".spese_bolli,0)+COALESCE(" + alias + ".spese_e15,0)"
            + "))"
        );
    }

    function ragioneSociale(rs1, rs2, fallback) {
        const rs = [rs1 || "", rs2 || ""].filter(Boolean).join(" ");
        return rs || fallback || "";
    }

    function numeroDocumento(numero, alfa) {
        const n = numero == null || numero === "" ? null : numero;
        const a = (alfa || "").trim();
        if (n == null && !a) return "—";
        if (n == null) return a;
        if (!a) return String(n);
        return n + "/" + a;
    }

    function listClienti(opts) {
        opts = opts || {};
        const q = (opts.q || "").trim().toLowerCase();
        const page = Math.max(1, Number(opts.page) || 1);
        const perPage = Math.min(100, Math.max(10, Number(opts.perPage) || 50));
        if (!db) return { rows: [], total: 0, page: page, perPage: perPage };

        let where = " WHERE (cliente_fittizio IS NULL OR cliente_fittizio = 0) ";
        const params = [];
        if (q) {
            where +=
                " AND (LOWER(codice) LIKE ? OR LOWER(COALESCE(ragione_sociale1,'')) LIKE ? "
                + "OR LOWER(COALESCE(ragione_sociale2,'')) LIKE ? OR LOWER(COALESCE(localita,'')) LIKE ? "
                + "OR LOWER(COALESCE(partita_iva,'')) LIKE ?) ";
            const like = "%" + q + "%";
            params.push(like, like, like, like, like);
        }

        const countStmt = db.prepare("SELECT COUNT(*) AS n FROM clienti" + where);
        countStmt.bind(params);
        let total = 0;
        if (countStmt.step()) total = Number(countStmt.getAsObject().n) || 0;
        countStmt.free();

        const offset = (page - 1) * perPage;
        const stmt = db.prepare(
            "SELECT * FROM clienti" + where
            + " ORDER BY ragione_sociale1 COLLATE NOCASE, codice LIMIT ? OFFSET ?"
        );
        stmt.bind(params.concat([perPage, offset]));
        const rows = [];
        while (stmt.step()) {
            const o = stmt.getAsObject();
            rows.push({
                codice: o.codice,
                ragione_sociale: ragioneSociale(o.ragione_sociale1, o.ragione_sociale2, o.codice),
                indirizzo: o.indirizzo || "",
                localita: o.localita || "",
                cap: o.cap || "",
                provincia: o.provincia || "",
                cod_nazione: o.cod_nazione || "",
                partita_iva: o.partita_iva || "",
                telefono: o.telefono || "",
                email: o.email || "",
            });
        }
        stmt.free();
        return { rows: rows, total: total, page: page, perPage: perPage };
    }

    function listFatture(opts) {
        opts = opts || {};
        const q = (opts.q || "").trim().toLowerCase();
        const dataDa = opts.dataDa || "";
        const dataA = opts.dataA || "";
        const page = Math.max(1, Number(opts.page) || 1);
        const perPage = Math.min(100, Math.max(10, Number(opts.perPage) || 50));
        if (!db) return { rows: [], total: 0, page: page, perPage: perPage };

        let where =
            " WHERE f.cliente IS NOT NULL AND TRIM(f.cliente) != '' "
            + "AND (c.cliente_fittizio IS NULL OR c.cliente_fittizio = 0) ";
        const params = [];
        if (dataDa) {
            where += " AND f.data_fattura >= ? ";
            params.push(dataDa);
        }
        if (dataA) {
            where += " AND f.data_fattura <= ? ";
            params.push(dataA);
        }
        if (q) {
            where +=
                " AND (LOWER(f.cliente) LIKE ? OR LOWER(COALESCE(c.ragione_sociale1,'')) LIKE ? "
                + "OR CAST(f.numero_fatt AS TEXT) LIKE ? OR LOWER(COALESCE(f.alfa,'')) LIKE ?) ";
            const like = "%" + q + "%";
            params.push(like, like, like, like);
        }

        const countSql =
            "SELECT COUNT(*) AS n FROM fatture f LEFT JOIN clienti c ON c.codice = f.cliente" + where;
        const countStmt = db.prepare(countSql);
        countStmt.bind(params);
        let total = 0;
        if (countStmt.step()) total = Number(countStmt.getAsObject().n) || 0;
        countStmt.free();

        const offset = (page - 1) * perPage;
        const sql =
            "SELECT f.*, c.ragione_sociale1 AS rs1, c.ragione_sociale2 AS rs2, c.localita AS localita "
            + "FROM fatture f LEFT JOIN clienti c ON c.codice = f.cliente"
            + where
            + " ORDER BY f.data_fattura DESC, f.id_testa DESC LIMIT ? OFFSET ?";
        const stmt = db.prepare(sql);
        stmt.bind(params.concat([perPage, offset]));
        const rows = [];
        while (stmt.step()) {
            const o = stmt.getAsObject();
            const spese =
                Math.abs(Number(o.spese_imballo) || 0)
                + Math.abs(Number(o.spese_trasporto) || 0)
                + Math.abs(Number(o.spese_incasso) || 0)
                + Math.abs(Number(o.spese_varie) || 0)
                + Math.abs(Number(o.spese_bolli) || 0)
                + Math.abs(Number(o.spese_e15) || 0);
            const isNc = String(o.tipo_doc_fe || "").trim().toUpperCase() === "TD04";
            let netto = (Number(o.imponibile) || 0) - spese;
            if (isNc) netto = -Math.abs(Number(o.imponibile) || 0) - spese;
            rows.push({
                id_testa: o.id_testa,
                numero: numeroDocumento(o.numero_fatt, o.alfa),
                data_fattura: o.data_fattura || "",
                cliente: o.cliente || "",
                ragione_sociale: ragioneSociale(o.rs1, o.rs2, o.cliente),
                localita: o.localita || "",
                imponibile: Number(o.imponibile) || 0,
                totale: Number(o.totale_fattura) || 0,
                netto: netto,
                is_nc: isNc,
                alfa: o.alfa || "",
            });
        }
        stmt.free();
        return { rows: rows, total: total, page: page, perPage: perPage };
    }

    function clientiFatturatiMap(dataDa, dataA, metrica, nc) {
        const map = {};
        if (!db) return map;
        const sql =
            "SELECT f.cliente AS codice, "
            + "SUM(" + nettoExpr(metrica, "f") + ") AS fatturato, "
            + "COUNT(*) AS n_fatture, MAX(f.data_fattura) AS ultima, "
            + "MAX(c.ragione_sociale1) AS rs1, MAX(c.ragione_sociale2) AS rs2, "
            + "MAX(c.localita) AS localita, MAX(c.provincia) AS provincia "
            + "FROM fatture f LEFT JOIN clienti c ON c.codice = f.cliente "
            + "WHERE f.cliente IS NOT NULL AND TRIM(f.cliente) != '' "
            + "AND (c.cliente_fittizio IS NULL OR c.cliente_fittizio = 0) "
            + "AND f.data_fattura >= ? AND f.data_fattura <= ? "
            + ncFilterSql(nc, "f")
            + "GROUP BY f.cliente";
        const stmt = db.prepare(sql);
        stmt.bind([dataDa, dataA]);
        while (stmt.step()) {
            const o = stmt.getAsObject();
            map[o.codice] = {
                codice: o.codice,
                fatturato: Number(o.fatturato) || 0,
                n_fatture: Number(o.n_fatture) || 0,
                ultima: o.ultima || "",
                ragione_sociale: ragioneSociale(o.rs1, o.rs2, o.codice),
                localita: o.localita || "",
                provincia: o.provincia || "",
            };
        }
        stmt.free();
        return map;
    }

    function classificaClienti(opts) {
        opts = opts || {};
        const topN = opts.topN != null ? Number(opts.topN) : 50;
        const map = clientiFatturatiMap(opts.dataDa || "", opts.dataA || "", opts.metrica, opts.nc);
        const rows = Object.keys(map).map(function (k) {
            return map[k];
        });
        rows.sort(function (a, b) {
            return b.fatturato - a.fatturato;
        });
        const totale = rows.reduce(function (s, r) {
            return s + r.fatturato;
        }, 0);
        let cumulato = 0;
        const classifica = rows.map(function (r, i) {
            cumulato += r.fatturato;
            return Object.assign({}, r, {
                posizione: i + 1,
                percentuale: totale ? (r.fatturato / totale) * 100 : 0,
                percentuale_cumulata: totale ? (cumulato / totale) * 100 : 0,
            });
        });
        const limited = topN > 0 ? classifica.slice(0, topN) : classifica;
        return {
            classifica: limited,
            classifica_completa: classifica,
            totale: totale,
            n_clienti: classifica.length,
            top1_fatturato: classifica[0] ? classifica[0].fatturato : 0,
            top1_percentuale: classifica[0] ? classifica[0].percentuale : 0,
        };
    }

    function kpiPeriodo(opts) {
        opts = opts || {};
        const dataDa = opts.dataDa || "";
        const dataA = opts.dataA || "";
        const metrica = opts.metrica;
        const nc = opts.nc;
        if (!db) return { fatturato: 0, n_fatture: 0, n_clienti: 0, ticket_medio: 0 };
        const sql =
            "SELECT SUM(" + nettoExpr(metrica, "f") + ") AS fatturato, "
            + "COUNT(*) AS n_fatture, COUNT(DISTINCT f.cliente) AS n_clienti "
            + "FROM fatture f LEFT JOIN clienti c ON c.codice = f.cliente "
            + "WHERE f.cliente IS NOT NULL AND TRIM(f.cliente) != '' "
            + "AND (c.cliente_fittizio IS NULL OR c.cliente_fittizio = 0) "
            + "AND f.data_fattura >= ? AND f.data_fattura <= ? "
            + ncFilterSql(nc, "f");
        const stmt = db.prepare(sql);
        stmt.bind([dataDa, dataA]);
        let out = { fatturato: 0, n_fatture: 0, n_clienti: 0, ticket_medio: 0 };
        if (stmt.step()) {
            const o = stmt.getAsObject();
            const n = Number(o.n_fatture) || 0;
            const fatt = Number(o.fatturato) || 0;
            out = {
                fatturato: fatt,
                n_fatture: n,
                n_clienti: Number(o.n_clienti) || 0,
                ticket_medio: n ? fatt / n : 0,
            };
        }
        stmt.free();
        return out;
    }

    function serieMensile(opts) {
        opts = opts || {};
        if (!db) return [];
        const sql =
            "SELECT substr(f.data_fattura, 1, 7) AS ym, "
            + "SUM(" + nettoExpr(opts.metrica, "f") + ") AS fatturato "
            + "FROM fatture f LEFT JOIN clienti c ON c.codice = f.cliente "
            + "WHERE f.cliente IS NOT NULL AND TRIM(f.cliente) != '' "
            + "AND (c.cliente_fittizio IS NULL OR c.cliente_fittizio = 0) "
            + "AND f.data_fattura >= ? AND f.data_fattura <= ? "
            + ncFilterSql(opts.nc, "f")
            + "GROUP BY ym ORDER BY ym";
        const stmt = db.prepare(sql);
        stmt.bind([opts.dataDa || "", opts.dataA || ""]);
        const rows = [];
        while (stmt.step()) {
            const o = stmt.getAsObject();
            rows.push({ mese: o.ym, fatturato: Number(o.fatturato) || 0 });
        }
        stmt.free();
        return rows;
    }

    function analisiFatturato(opts) {
        opts = opts || {};
        const rifDa = opts.rifDa || "";
        const rifA = opts.rifA || "";
        const conDa = opts.conDa || "";
        const conA = opts.conA || "";
        const metrica = opts.metrica;
        const nc = opts.nc;
        const listLimit = opts.listLimit != null ? Number(opts.listLimit) : 50;

        const mapRif = clientiFatturatiMap(rifDa, rifA, metrica, nc);
        const mapCon = clientiFatturatiMap(conDa, conA, metrica, nc);
        const setRif = Object.keys(mapRif);
        const setCon = Object.keys(mapCon);
        const setRifObj = {};
        const setConObj = {};
        setRif.forEach(function (c) {
            setRifObj[c] = true;
        });
        setCon.forEach(function (c) {
            setConObj[c] = true;
        });

        function enrichList(codici, getter) {
            const rows = codici.map(getter);
            rows.sort(function (a, b) {
                return (b.sort || 0) - (a.sort || 0);
            });
            return listLimit > 0 ? rows.slice(0, listLimit) : rows;
        }

        const periodo = enrichList(setRif, function (c) {
            const r = mapRif[c];
            return Object.assign({}, r, { sort: r.fatturato });
        });
        const persi = enrichList(
            setCon.filter(function (c) {
                return !setRifObj[c];
            }),
            function (c) {
                const r = mapCon[c];
                return Object.assign({}, r, { sort: r.fatturato });
            }
        );
        const nuovi = enrichList(
            setRif.filter(function (c) {
                return !setConObj[c];
            }),
            function (c) {
                const r = mapRif[c];
                return Object.assign({}, r, { sort: r.fatturato });
            }
        );
        const entrambi = enrichList(
            setRif.filter(function (c) {
                return setConObj[c];
            }),
            function (c) {
                const a = mapRif[c];
                const b = mapCon[c];
                const delta = a.fatturato - b.fatturato;
                return {
                    codice: c,
                    ragione_sociale: a.ragione_sociale,
                    localita: a.localita,
                    provincia: a.provincia,
                    fatturato_rif: a.fatturato,
                    fatturato_con: b.fatturato,
                    delta: delta,
                    n_fatture_rif: a.n_fatture,
                    n_fatture_con: b.n_fatture,
                    sort: delta,
                };
            }
        );

        const kpiRif = kpiPeriodo({ dataDa: rifDa, dataA: rifA, metrica: metrica, nc: nc });
        const kpiCon = kpiPeriodo({ dataDa: conDa, dataA: conA, metrica: metrica, nc: nc });
        const deltaPct =
            kpiCon.fatturato
                ? ((kpiRif.fatturato - kpiCon.fatturato) / Math.abs(kpiCon.fatturato)) * 100
                : null;

        return {
            kpi_rif: kpiRif,
            kpi_con: kpiCon,
            delta_pct: deltaPct,
            n_periodo: setRif.length,
            n_persi: setCon.filter(function (c) {
                return !setRifObj[c];
            }).length,
            n_nuovi: setRif.filter(function (c) {
                return !setConObj[c];
            }).length,
            n_entrambi: setRif.filter(function (c) {
                return setConObj[c];
            }).length,
            periodo: periodo,
            persi: persi,
            nuovi: nuovi,
            entrambi: entrambi,
            serie_rif: serieMensile({ dataDa: rifDa, dataA: rifA, metrica: metrica, nc: nc }),
        };
    }

    function fatturatoPerRegione(opts) {
        opts = opts || {};
        if (!db) {
            return { regioni: [], totale_italia: 0, totale_mappato: 0, totale_non_mappato: 0 };
        }

        const meta = loadProvinciaMeta();
        const regNomi = loadRegioniNomi();
        const map = clientiFatturatiMap(opts.dataDa || "", opts.dataA || "", opts.metrica, opts.nc);
        const byReg = {};
        let mappato = 0;
        let nonMappato = 0;
        let nMap = 0;
        let nNon = 0;

        Object.keys(map).forEach(function (codice) {
            const info = map[codice];
            const geo = clienteGeo(codice);
            if (geo.iso !== "IT") return;
            const reg = meta.siglaToReg[geo.provincia];
            if (!reg) {
                nonMappato += info.fatturato;
                nNon += 1;
                return;
            }
            const b = byReg[reg] || { fatturato: 0, n_fatture: 0, n_clienti: 0 };
            b.fatturato += info.fatturato;
            b.n_fatture += info.n_fatture;
            b.n_clienti += 1;
            byReg[reg] = b;
            mappato += info.fatturato;
            nMap += 1;
        });

        const rows = Object.keys(regNomi).map(function (codice) {
            const d = byReg[codice] || { fatturato: 0, n_fatture: 0, n_clienti: 0 };
            return {
                codice: codice,
                nome: regNomi[codice],
                fatturato: d.fatturato,
                percentuale: mappato ? (d.fatturato / mappato) * 100 : 0,
                n_fatture: d.n_fatture,
                n_clienti: d.n_clienti,
            };
        });
        rows.sort(function (a, b) {
            return b.fatturato - a.fatturato;
        });

        return {
            regioni: rows,
            totale_mappato: mappato,
            totale_non_mappato: nonMappato,
            totale_italia: mappato + nonMappato,
            n_clienti_mappati: nMap,
            n_clienti_non_mappati: nNon,
        };
    }

    function fatturatoPerProvincia(opts) {
        opts = opts || {};
        if (!db) return { province: [], totale_mappato: 0 };

        const meta = loadProvinciaMeta();
        const regNomi = loadRegioniNomi();
        const map = clientiFatturatiMap(opts.dataDa || "", opts.dataA || "", opts.metrica, opts.nc);
        const byProv = {};
        let mappato = 0;

        Object.keys(map).forEach(function (codice) {
            const info = map[codice];
            const geo = clienteGeo(codice);
            if (geo.iso !== "IT") return;
            const sigla = geo.provincia;
            const pm = meta.provMeta[sigla];
            if (!pm) return;
            const b = byProv[sigla] || {
                fatturato: 0,
                n_fatture: 0,
                n_clienti: 0,
                regione: pm.regione,
            };
            b.fatturato += info.fatturato;
            b.n_fatture += info.n_fatture;
            b.n_clienti += 1;
            byProv[sigla] = b;
            mappato += info.fatturato;
        });

        const totaleReg = {};
        Object.keys(byProv).forEach(function (sigla) {
            const reg = byProv[sigla].regione;
            totaleReg[reg] = (totaleReg[reg] || 0) + byProv[sigla].fatturato;
        });

        const rows = Object.keys(meta.provMeta).map(function (sigla) {
            const pm = meta.provMeta[sigla];
            const d = byProv[sigla] || {
                fatturato: 0,
                n_fatture: 0,
                n_clienti: 0,
                regione: pm.regione,
            };
            const totR = totaleReg[pm.regione] || 0;
            return {
                sigla: sigla,
                nome: pm.nome,
                regione_codice: pm.regione,
                regione_nome: regNomi[pm.regione] || pm.regione,
                fatturato: d.fatturato,
                percentuale: totR ? (d.fatturato / totR) * 100 : 0,
                percentuale_italia: mappato ? (d.fatturato / mappato) * 100 : 0,
                n_fatture: d.n_fatture,
                n_clienti: d.n_clienti,
            };
        });
        rows.sort(function (a, b) {
            return b.fatturato - a.fatturato;
        });

        return {
            province: rows,
            totale_mappato: mappato,
            n_province: rows.filter(function (r) {
                return r.fatturato;
            }).length,
        };
    }

    function fatturatoPerNazione(opts) {
        opts = opts || {};
        const soloEstero = Boolean(opts.soloEstero);
        if (!db) return { nazioni: [], totale: 0 };

        const nomi = loadNazioniNomi();
        const map = clientiFatturatiMap(opts.dataDa || "", opts.dataA || "", opts.metrica, opts.nc);
        const byIso = {};
        let totale = 0;
        let nClienti = 0;
        let nFatture = 0;

        Object.keys(map).forEach(function (codice) {
            const info = map[codice];
            const geo = clienteGeo(codice);
            const iso = geo.iso;
            if (!iso) return;
            if (soloEstero && iso === "IT") return;
            const b = byIso[iso] || { fatturato: 0, n_fatture: 0, n_clienti: 0 };
            b.fatturato += info.fatturato;
            b.n_fatture += info.n_fatture;
            b.n_clienti += 1;
            byIso[iso] = b;
            totale += info.fatturato;
            nClienti += 1;
            nFatture += info.n_fatture;
        });

        const rows = Object.keys(byIso).map(function (iso) {
            const d = byIso[iso];
            return {
                codice: iso,
                nome: nomi[iso] || iso,
                fatturato: d.fatturato,
                percentuale: totale ? (d.fatturato / totale) * 100 : 0,
                n_fatture: d.n_fatture,
                n_clienti: d.n_clienti,
            };
        });
        rows.sort(function (a, b) {
            return b.fatturato - a.fatturato;
        });

        return {
            nazioni: rows,
            totale: totale,
            n_clienti: nClienti,
            n_fatture: nFatture,
            n_nazioni: rows.length,
        };
    }

    async function saveSyncMeta(info) {
        metaSet("synced_at", info.synced_at || new Date().toISOString());
        metaSet("from_date", info.from_date || "");
        await idbSet(META_KEY, info);
        await persist();
    }

    global.EurekaOfflineDB = {
        openDatabase: openDatabase,
        persist: persist,
        getDb: getDb,
        metaGet: metaGet,
        metaSet: metaSet,
        counts: counts,
        clearBusinessData: clearBusinessData,
        upsertClienti: upsertClienti,
        upsertFatture: upsertFatture,
        replaceGeo: replaceGeo,
        listClienti: listClienti,
        listFatture: listFatture,
        classificaClienti: classificaClienti,
        kpiPeriodo: kpiPeriodo,
        analisiFatturato: analisiFatturato,
        fatturatoPerRegione: fatturatoPerRegione,
        fatturatoPerProvincia: fatturatoPerProvincia,
        fatturatoPerNazione: fatturatoPerNazione,
        serieMensile: serieMensile,
        saveSyncMeta: saveSyncMeta,
        idbGet: idbGet,
    };
})(window);
