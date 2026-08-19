"""
Assistente AI — genera query SQL dal linguaggio naturale via OpenAI,
le esegue sul database PostgreSQL e restituisce i risultati.
"""
import json
import logging
import re
import time
import urllib.error
import urllib.request
from django.conf import settings
from django.db import connection

logger = logging.getLogger(__name__)

MAX_ROWS = 200
GROQ_RATE_LIMIT_MESSAGE = (
    "Limite Groq raggiunto, riprova tra qualche minuto. "
    "Puoi anche avviare Ollama in locale come alternativa."
)

DB_SCHEMA = """
Database PostgreSQL — ERP gestionale italiano (Eureka AI).
Colonne CamelCase: usa SEMPRE virgolette doppie ("DataReg", "Codice", ecc.).

PK "Codice": articoli, clienti, fornitori, agenti, aliquote, causali_contabili,
  pdc, condizioni, categorie, banche, valuta, zone, gruppi_articoli
PK "ID": primanota, primanota_dettaglio, valuta_det
PK id: teste_documenti, righe_documenti

Tabelle principali:
- primanota: "ID", "NumeroReg", "DataReg", "NumeroDoc", "DataDoc", "Causale", "Registro",
  "Tipo" (1=Generico,2=IVA,3=Corrispettivi,4=IvaAutofattura), "CodicePartita", "Valuta",
  "TotaleDoc_Controllo", "Acconto"
- primanota_dettaglio: "ID", "id_added_by_converter" (FK primanota."ID"), "ContoDare",
  "ContoAvere", "Dare", "Avere_Imponibile", "Imp_Val", "CodiceIva", "ImportoIva", "Descrizione"
- clienti/fornitori: "Codice", "RagioneSociale1", "RagioneSociale2", "Indirizzo", "Localita",
  "Cap", "Provincia", "PartitaIva", "CodFiscale", "Telefono", "Email"/"E_Mail", "PEC",
  "Fl_Disattivato"; clienti anche "Agente", "Zona", "CondPaga", "Listino"
- agenti: "Codice", "RagioneSociale", "Provvigione", "email"
- articoli: "Codice", "Descrizione", "CatOmogenea", "CodGruppo", "CodIva", "UnitaMisura",
  "CodFornitore", "Listino1"-"Listino3", "PrezzoUltCar", "Giacenza", "Disponibile", "FlDisattivato"
- gruppi_articoli: "Codice", "Descrizione" (lookup articoli."CodGruppo")
- categorie: "Codice", "Descrizione" (lookup articoli."CatOmogenea")
- teste_documenti: id, tipo_doc, numero, alfa, data_documento, codice_clifor, totale, imponibile, valuta
- righe_documenti: id, testa_id, codice, descrizione, quantita, prezzo_unitario, iva, sconto
- aliquote: "Codice", "Descrizione", "Percentuale"
- causali_contabili: "Codice", "Descrizione", "RegistroIva", "TipoCausale"
- pdc: "Codice", "Descrizione", "TipoConto", "Gruppo"
- condizioni: "Codice", "Descrizione", "TipoPagamento", "NumeroRate"
- banche: "Codice", "Descrizione", "IBAN"
- valuta/valuta_det: "Codice"/"ID", "Descrizione"/"Cod_Valuta", "Cambio", "Data"
- zone: "Codice", "Descrizione"
"""

SYSTEM_PROMPT = f"""Sei un assistente AI per un ERP gestionale italiano chiamato Eureka AI.
Il tuo compito è tradurre richieste in linguaggio naturale in query SQL PostgreSQL
e restituire i risultati in formato leggibile.

{DB_SCHEMA}

REGOLE IMPORTANTI:
1. Genera SOLO query SELECT (nessuna INSERT, UPDATE, DELETE, DROP, ALTER, TRUNCATE).
2. Limita i risultati a {MAX_ROWS} righe (aggiungi LIMIT {MAX_ROWS}).
3. Usa il formato date italiano quando possibile (DD/MM/YYYY con TO_CHAR).
4. "Anno in corso" = EXTRACT(YEAR FROM CURRENT_DATE).
5. Per la primanota IVA (tipo=2 o tipo=4), l'imponibile da filtrare è in primanota_dettaglio."Avere_Imponibile", e l'importo IVA è in primanota_dettaglio."ImportoIva".
6. La colonna FK da primanota_dettaglio a primanota è "id_added_by_converter" (= primanota."ID").
7. Rispondi SEMPRE in formato JSON con questa struttura:
   {{"sql": "SELECT ...", "spiegazione": "Descrizione di cosa fa la query"}}
8. Se la richiesta non è chiara o non riguarda il database, rispondi:
   {{"sql": null, "spiegazione": "Motivo per cui non puoi generare la query"}}
9. Non includere mai commenti SQL nella query.
10. Usa nomi tabella e colonna esatti come indicato nello schema.
11. Includi SEMPRE la colonna PK nei risultati SELECT. articoli NON ha "ID" (PK = "Codice").
    Esempio corretto: SELECT "Codice", "Descrizione" FROM articoli WHERE "Descrizione" ILIKE '%calzature%'
    Esempio SBAGLIATO: SELECT "ID", "Codice" FROM articoli
12. CRITICO: TUTTE le colonne CamelCase DEVONO essere tra virgolette doppie. Esempi corretti:
    - SELECT "ID", "DataReg", "Causale" FROM primanota
    - SELECT "Codice", "Descrizione" FROM articoli
    - WHERE "Imp_Val" > 2500
    - WHERE "Dare" > 0 OR "Avere_Imponibile" > 0
    Esempio SBAGLIATO (senza virgolette): SELECT ID, DataReg, Imp_Val FROM primanota
13. Per richieste su articoli per categoria/merceologia/settore/gruppo/famiglia:
    - usa SOLO campi strutturati reali del dominio articoli, in particolare articoli."CatOmogenea" e articoli."CodGruppo"
    - se serve la descrizione del codice gruppo, puoi fare JOIN con gruppi_articoli su articoli."CodGruppo" = gruppi_articoli."Codice"
    - se serve la descrizione della categoria merceologica, puoi fare JOIN con categorie su articoli."CatOmogenea" = categorie."Codice"
    - NON dedurre categorie dalla sola articoli."Descrizione" e NON fare inferenze semantiche creative
    - usa articoli."Descrizione" o altri campi testuali SOLO se l'utente chiede esplicitamente una ricerca per descrizione/nome/testo/contenuto
    - se il termine richiesto (es. "abbigliamento") non corrisponde con affidabilità a un codice/campo strutturato disponibile nello schema, rispondi con {{"sql": null, "spiegazione": "..."}} spiegando che serve indicare categoria/gruppo/codice reale o chiedere una ricerca testuale esplicita
14. Esempi per articoli:
    - "articoli della categoria merceologica CAT01" -> filtra articoli."CatOmogenea" = 'CAT01'
    - "articoli del gruppo GR10" -> filtra articoli."CodGruppo" = 'GR10'
    - "articoli del gruppo con descrizione minuteria" -> JOIN gruppi_articoli e filtra gruppi_articoli."Descrizione" ILIKE '%minuteria%'
    - "cerca articoli con abbigliamento nella descrizione" -> SOLO qui è consentito filtrare articoli."Descrizione" ILIKE '%abbigliamento%'
    - "articoli con calzature nella descrizione" -> SELECT "Codice", "Descrizione" FROM articoli WHERE "Descrizione" ILIKE '%calzature%'
"""


def _get_ollama_client():
    from openai import OpenAI

    base_url = getattr(settings, "OLLAMA_URL", "http://localhost:11434") + "/v1"
    return OpenAI(base_url=base_url, api_key="ollama")


def _get_client():
    from openai import OpenAI
    backend = getattr(settings, "AI_BACKEND", "ollama")
    if backend == "ollama":
        return _get_ollama_client()
    if backend == "groq":
        api_key = getattr(settings, "GROQ_API_KEY", None)
        if not api_key:
            raise ValueError(
                "GROQ_API_KEY non configurata. "
                "Ottieni una chiave gratuita da https://console.groq.com/ "
                "e aggiungi GROQ_API_KEY=gsk_... nel file .env"
            )
        return OpenAI(
            base_url="https://api.groq.com/openai/v1",
            api_key=api_key,
        )
    api_key = getattr(settings, "OPENAI_API_KEY", None)
    if not api_key:
        raise ValueError(
            "OPENAI_API_KEY non configurata. "
            "Aggiungi OPENAI_API_KEY=sk-... nel file .env"
        )
    return OpenAI(api_key=api_key)


def _get_model() -> str:
    backend = getattr(settings, "AI_BACKEND", "ollama")
    if backend == "ollama":
        return getattr(settings, "OLLAMA_MODEL", "llama3.1")
    if backend == "groq":
        return getattr(settings, "GROQ_MODEL", "groq/compound-mini")
    return getattr(settings, "OPENAI_MODEL", "gpt-4o-mini")


def _get_groq_max_tokens() -> int:
    return int(getattr(settings, "GROQ_MAX_TOKENS", 550))


def _is_groq_rate_limit_error(exc: Exception) -> bool:
    if type(exc).__name__ == "RateLimitError":
        return True
    err = str(exc).lower()
    return "429" in err or "rate limit" in err or "tokens per day" in err


def _is_ollama_available() -> bool:
    url = getattr(settings, "OLLAMA_URL", "http://localhost:11434").rstrip("/") + "/api/tags"
    try:
        with urllib.request.urlopen(url, timeout=2) as resp:
            return resp.status == 200
    except (urllib.error.URLError, TimeoutError, OSError):
        return False


def _chat_completion(client, model: str, messages: list, max_tokens: int):
    return client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=0,
        max_tokens=max_tokens,
    )


def _call_llm(messages: list, max_tokens: int):
    """
    Chiama il backend LLM configurato. Se Groq risponde 429 e Ollama è attivo,
    effettua fallback locale.
    """
    backend = getattr(settings, "AI_BACKEND", "ollama")
    client = _get_client()
    model = _get_model()
    try:
        return _chat_completion(client, model, messages, max_tokens)
    except Exception as exc:
        if backend != "groq" or not _is_groq_rate_limit_error(exc):
            raise
        if _is_ollama_available():
            logger.warning("Groq rate limit (429), fallback su Ollama")
            ollama_model = getattr(settings, "OLLAMA_MODEL", "llama3.1")
            return _chat_completion(
                _get_ollama_client(),
                ollama_model,
                messages,
                max(2000, max_tokens),
            )
        raise ValueError(GROQ_RATE_LIMIT_MESSAGE) from exc


def _parse_ai_response(content: str) -> dict:
    """Estrae il JSON dalla risposta del modello."""
    content = content.strip()
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", content, re.DOTALL)
    if fence:
        content = fence.group(1)
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        return {"sql": None, "spiegazione": content}


_ARTICLE_CATEGORY_KEYWORDS = (
    "categoria",
    "categorie",
    "categoria merceologica",
    "categorie merceologiche",
    "cat. merceologica",
    "cat merceologica",
    "merceologia",
    "merceologico",
    "merceologica",
    "settore",
    "settori",
    "gruppo",
    "gruppi",
    "famiglia",
    "famiglie",
    "catomogenea",
    "cat omogenea",
    "codgruppo",
    "cod gruppo",
)

_ARTICLE_DOMAIN_KEYWORDS = (
    "articolo",
    "articoli",
    "prodotto",
    "prodotti",
    "art.",
)

_EXPLICIT_TEXT_SEARCH_KEYWORDS = (
    "descrizione",
    "descrizioni",
    "nome",
    "nomi",
    "testo",
    "testuale",
    "match testo",
    "contiene",
    "contengono",
    "cerca testo",
    "stringa",
    "parola",
)


def _normalize_prompt_text(prompt: str) -> str:
    return re.sub(r"\s+", " ", (prompt or "").strip().lower())


def _is_article_category_request(prompt: str) -> bool:
    normalized = _normalize_prompt_text(prompt)
    has_article_domain = any(token in normalized for token in _ARTICLE_DOMAIN_KEYWORDS)
    has_category_intent = any(token in normalized for token in _ARTICLE_CATEGORY_KEYWORDS)
    return has_article_domain and has_category_intent


def _is_explicit_article_text_search(prompt: str) -> bool:
    normalized = _normalize_prompt_text(prompt)
    if not any(token in normalized for token in _ARTICLE_DOMAIN_KEYWORDS):
        return False
    return any(token in normalized for token in _EXPLICIT_TEXT_SEARCH_KEYWORDS)


def _build_ai_user_prompt(prompt: str) -> str:
    base_prompt = (prompt or "").strip()
    if not _is_article_category_request(base_prompt):
        return base_prompt
    if _is_explicit_article_text_search(base_prompt):
        return base_prompt
    return (
        f"{base_prompt}\n\n"
        "Vincolo per questa richiesta: riguarda categorie/merceologia/gruppi di articoli. "
        "Usa solo classificazioni strutturate reali del database articoli: "
        'articoli."CatOmogenea" e articoli."CodGruppo", con eventuali join a '
        'categorie."Codice"/"Descrizione" e gruppi_articoli."Codice"/"Descrizione". '
        'Non usare articoli."Descrizione" per indovinare la categoria. '
        "Se il termine richiesto non e' riconducibile in modo affidabile a questi campi strutturati, "
        'rispondi con {"sql": null, "spiegazione": "..."} chiedendo un codice/gruppo/categoria reale '
        "oppure una esplicita ricerca testuale in descrizione."
    )


_KNOWN_COLUMNS = {
    "ID", "NumeroReg", "DataReg", "NumeroDoc", "DataDoc", "NumeroProt",
    "AlfaProt", "Causale", "Registro", "Tipo", "CodicePartita", "CodicePaga",
    "Valuta", "FornitoreCEE", "TotaleDoc_Controllo", "Acconto", "ScadenzeIns",
    "ContoDare", "ContoAvere", "Dare", "Avere_Imponibile", "Imp_Val", "CodiceIva",
    "ImportoIva", "Descrizione", "AnnoDoc", "Pos",
    "Codice", "RagioneSociale1", "RagioneSociale2", "Indirizzo", "Localita",
    "Cap", "Provincia", "CodNazione", "PartitaIva", "CodFiscale", "Telefono",
    "Email", "E_Mail", "PEC", "Agente", "Zona", "Gruppo", "CondPaga", "Listino",
    "Fl_Disattivato", "FlDisattivato", "RagioneSociale", "Provvigione",
    "CatOmogenea", "CodGruppo", "CodIva", "UnitaMisura", "CodFornitore",
    "Listino1", "Listino2", "Listino3", "PrezzoUltCar", "Giacenza", "Disponibile",
    "Percentuale", "RegistroIva", "TipoCausale", "TipoConto",
    "TipoPagamento", "NumeroRate", "IBAN", "Abbrev", "Cambio",
    "Cod_Valuta", "Data", "DesContoDare", "DesContoAvere",
    "Banca", "Sconto", "DataModifica", "DataValuta", "CodiceAgente",
    "Nr_Fatt_Anno", "GUID", "Cellulare",
}


def _fix_column_quoting(sql: str) -> str:
    """Add double-quotes around known CamelCase column names if missing."""
    for col in _KNOWN_COLUMNS:
        sql = re.sub(
            rf'(?<!")(?<!\w)\b{re.escape(col)}\b(?!")(?!\w*\()',
            f'"{col}"',
            sql,
        )
    return sql


def _is_safe_sql(sql: str) -> bool:
    """Verifica che la query sia solo SELECT."""
    normalized = re.sub(r"--.*$", "", sql, flags=re.MULTILINE)
    normalized = re.sub(r"/\*.*?\*/", "", normalized, flags=re.DOTALL)
    normalized = normalized.strip().upper()
    forbidden = ("INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "TRUNCATE",
                 "CREATE", "GRANT", "REVOKE", "EXEC", "EXECUTE")
    first_word = normalized.split()[0] if normalized.split() else ""
    if first_word not in ("SELECT", "WITH"):
        return False
    for kw in forbidden:
        if re.search(rf"\b{kw}\b", normalized):
            return False
    return True


TABLE_LIST_ROUTES = {
    "clienti":           "anagrafiche:clienti_list",
    "fornitori":         "anagrafiche:fornitori_list",
    "agenti":            "anagrafiche:agenti_list",
    "articoli":          "articoli:list",
    "aliquote":          "aliquote:list",
    "causali_contabili": "causali_contabili:list",
    "condizioni":        "condizioni:list",
    "categorie":         "categorie:list",
    "banche":            "banche:list",
}

TABLE_DETAIL_ROUTES = {
    "primanota":            {"url": "primanota:detail",              "pk": "ID",      "param": "pk"},
    "primanota_dettaglio":  {"url": "primanota:detail",              "pk": "id_added_by_converter", "param": "pk"},
    "clienti":              {"url": "anagrafiche:cliente_detail",    "pk": "Codice",  "param": "codice"},
    "fornitori":            {"url": "anagrafiche:fornitore_detail",  "pk": "Codice",  "param": "codice"},
    "agenti":               {"url": "anagrafiche:agente_detail",     "pk": "Codice",  "param": "codice"},
    "articoli":             {"url": "articoli:detail",               "pk": "Codice",  "param": "codice"},
    "fatture":              {"url": "fatture:detail",                "pk": "id_testa","param": "id_testa"},
    "teste_documenti":      {"url": "documenti:detail",              "pk": "id",      "param": "pk"},
    "aliquote":             {"url": "aliquote:detail",               "pk": "Codice",  "param": "codice"},
    "causali_contabili":    {"url": "causali_contabili:detail",      "pk": "Codice",  "param": "codice"},
    "pdc":                  {"url": "pdc:detail",                    "pk": "Codice",  "param": "codice"},
    "condizioni":           {"url": "condizioni:detail",             "pk": "Codice",  "param": "codice"},
    "categorie":            {"url": "categorie:detail",              "pk": "Codice",  "param": "codice"},
    "banche":               {"url": "banche:detail",                 "pk": "Codice",  "param": "codice"},
    "valuta":               {"url": "valute:detail",                 "pk": "Codice",  "param": "codice"},
    "zone":                 {"url": "zone:detail",                   "pk": "Codice",  "param": "codice"},
    "registri_iva":         {"url": "registri_iva:detail",           "pk": "Codice",  "param": "codice"},
    "sconti":               {"url": "sconti:detail",                 "pk": "Codice",  "param": "codice"},
    "vettori":              {"url": "vettori:detail",                "pk": "CodiceVet","param": "codice"},
    "causali_trasp":        {"url": "causali_trasp:detail",          "pk": "Codice",  "param": "codice"},
    "causali_maga":         {"url": "causali_magazzino:detail",      "pk": "Codice",  "param": "codice"},
    "gruppi_articoli":      {"url": "gruppi_articoli:detail",        "pk": "Codice",  "param": "codice"},
    "magazzini":            {"url": "magazzini:detail",              "pk": "Codice",  "param": "codice"},
    "gruppi_magazzini":     {"url": "gruppi_magazzini:detail",       "pk": "Cod",     "param": "cod"},
    "stampi":               {"url": "stampi:detail",                 "pk": "ID",      "param": "pk"},
    "operatori":            {"url": "operatori:detail",              "pk": "Codice",  "param": "codice"},
    "dest_cli_for":         {"url": "destinazioni:detail",           "pk": "ID",      "param": "pk"},
    "distinte_base":        {"url": "distinte_base:detail",          "pk": "ID",      "param": "pk"},
}


def _fix_primary_key_columns(sql: str) -> str:
    """
    Correct erroneous "ID" references for tables whose primary key is not "ID".
    Safety net when the LLM assumes every table has an "ID" column.
    """
    if not sql:
        return sql

    for table, route in TABLE_DETAIL_ROUTES.items():
        pk = route["pk"]
        if pk == "ID":
            continue
        pk_quoted = f'"{pk}"'
        qualified_id = rf'\b{re.escape(table)}\."ID"\b'
        qualified_pk = rf'\b{re.escape(table)}\.{re.escape(pk_quoted)}\b'
        if not re.search(qualified_id, sql, re.IGNORECASE):
            continue
        if re.search(qualified_pk, sql, re.IGNORECASE) or (
            pk == "Codice" and re.search(r'(?<![.\w])"Codice"(?!\w)', sql)
        ):
            sql = re.sub(rf'\b{re.escape(table)}\."ID"\s*,\s*', "", sql, flags=re.IGNORECASE)
            sql = re.sub(rf',\s*{qualified_id}', "", sql, flags=re.IGNORECASE)
            sql = re.sub(qualified_id, "", sql, flags=re.IGNORECASE)
        else:
            sql = re.sub(qualified_id, f'{table}.{pk_quoted}', sql, flags=re.IGNORECASE)

    main_table = _detect_table(sql)
    if main_table and main_table in TABLE_DETAIL_ROUTES:
        pk = TABLE_DETAIL_ROUTES[main_table]["pk"]
        if pk != "ID":
            pk_quoted = f'"{pk}"'
            has_pk = re.search(re.escape(pk_quoted), sql, re.IGNORECASE)
            has_wrong_id = re.search(r'(?<![.\w])"ID"(?!\w)', sql)
            if has_wrong_id:
                if has_pk:
                    sql = re.sub(r'"ID"\s*,\s*', "", sql)
                    sql = re.sub(r',\s*"ID"(?!\w)', "", sql)
                    sql = re.sub(
                        r'SELECT\s+"ID"\s+FROM',
                        f"SELECT {pk_quoted} FROM",
                        sql,
                        flags=re.IGNORECASE,
                    )
                else:
                    sql = re.sub(r'(?<![.\w])"ID"(?!\w)', pk_quoted, sql)

    return sql


def _ensure_limit(sql: str, limit: int) -> str:
    """
    Ensures the SQL is capped with LIMIT for SELECT queries.
    This is a safety net in case the LLM forgets to include LIMIT.
    """
    sql = (sql or "").strip().rstrip(";").strip()
    if not sql:
        return sql

    # If the model already produced a numeric LIMIT (e.g. LIMIT 200),
    # override it so we can reliably detect if there are more than `limit`.
    if re.search(r"\bLIMIT\s+\d+\b", sql, flags=re.IGNORECASE):
        return re.sub(r"\bLIMIT\s+\d+\b", f"LIMIT {int(limit)}", sql, flags=re.IGNORECASE)

    # At this point we only allow SELECT queries (checked elsewhere via _is_safe_sql),
    # so appending LIMIT at the end is safe for both SELECT and WITH queries.
    return f"{sql} LIMIT {int(limit)}"


def _detect_table(sql: str) -> str | None:
    """Rileva la tabella principale dalla query."""
    m = re.search(r'\bFROM\s+(\w+)', sql, re.IGNORECASE)
    return m.group(1).lower() if m else None


def _build_detail_links(risultati: list[dict], sql: str) -> dict | None:
    """Restituisce info per costruire link ai dettagli, se possibile."""
    table = _detect_table(sql)
    if not table or table not in TABLE_DETAIL_ROUTES:
        return None
    route = TABLE_DETAIL_ROUTES[table]
    pk_col = route["pk"]
    pk_lower = pk_col.lower()
    found_col = None
    if risultati:
        for col in risultati[0].keys():
            if col.lower() == pk_lower or col == pk_col:
                found_col = col
                break
    if not found_col:
        return None
    return {
        "url_name": route["url"],
        "pk_column": found_col,
        "pk_param": route["param"],
    }


def _execute_query(sql: str, limit: int = MAX_ROWS) -> tuple[list[dict], bool]:
    """Esegue la query SELECT e restituisce (risultati, has_more)."""
    with connection.cursor() as cursor:
        cursor.execute(sql)
        columns = [col.name for col in cursor.description]
        rows = cursor.fetchmany(limit + 1)
    has_more = len(rows) > limit
    rows = rows[:limit]
    results = []
    for row in rows:
        record = {}
        for col_name, value in zip(columns, row):
            if hasattr(value, "isoformat"):
                value = value.strftime("%d/%m/%Y") if hasattr(value, "year") else str(value)
            record[col_name] = value
        results.append(record)
    return results, has_more


def _strip_limit_offset(sql: str) -> str:
    """
    Removes trailing LIMIT/OFFSET from a SELECT statement.

    We only strip the outer pagination clauses (at the end of the query),
    so other LIMITs inside subqueries/CTEs (if any) are preserved.
    """
    sql = (sql or "").strip().rstrip(";").strip()
    # ... LIMIT n OFFSET m
    sql = re.sub(r"\s*\bLIMIT\s+\d+\s+OFFSET\s+\d+\s*$", "", sql, flags=re.IGNORECASE)
    # ... LIMIT n
    sql = re.sub(r"\s*\bLIMIT\s+\d+\s*$", "", sql, flags=re.IGNORECASE)
    # ... OFFSET m (rare, but handle it)
    sql = re.sub(r"\s*\bOFFSET\s+\d+\s*$", "", sql, flags=re.IGNORECASE)
    return sql.strip()


def _execute_total_count(sql_with_limit: str) -> int | None:
    """
    Computes total matching rows for the given SELECT by running:
      SELECT COUNT(*) FROM (<sql_without_limit>) t
    """
    try:
        sql_no_limit = _strip_limit_offset(sql_with_limit)
        if not sql_no_limit:
            return None

        count_sql = f"SELECT COUNT(*) AS total_count FROM ({sql_no_limit}) t"
        if not _is_safe_sql(count_sql):
            return None

        with connection.cursor() as cursor:
            cursor.execute(count_sql)
            row = cursor.fetchone()
            return int(row[0]) if row and row[0] is not None else None
    except Exception:
        logger.exception("Errore calcolo total_count query AI")
        return None


def ask_ai(prompt: str, limit: int = MAX_ROWS) -> dict:
    """
    Riceve una richiesta in linguaggio naturale, la invia a OpenAI,
    esegue la query generata e restituisce i risultati.

    Returns:
        {
            "ok": bool,
            "spiegazione": str,
            "sql": str | None,
            "risultati": list[dict] | None,
            "conteggio": int,
            "total_count": int | None,
            "errore": str | None,
        }
    """
    if not prompt or not prompt.strip():
        return {"ok": False, "spiegazione": "", "sql": None,
                "risultati": None, "conteggio": 0, "total_count": None,
                "errore": "Richiesta vuota."}

    try:
        _get_client()
    except ValueError as e:
        return {"ok": False, "spiegazione": "", "sql": None,
                "risultati": None, "conteggio": 0, "total_count": None,
                "errore": str(e)}

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": _build_ai_user_prompt(prompt)},
    ]
    backend = getattr(settings, "AI_BACKEND", "ollama")
    max_tokens = _get_groq_max_tokens() if backend == "groq" else 2000

    try:
        t_llm_start = time.perf_counter()
        response = _call_llm(messages, max_tokens)
        t_llm_end = time.perf_counter()
        content = response.choices[0].message.content or ""
    except ValueError as e:
        return {"ok": False, "spiegazione": "", "sql": None,
                "risultati": None, "conteggio": 0, "total_count": None,
                "errore": str(e)}
    except Exception as e:
        if backend == "groq" and _is_groq_rate_limit_error(e):
            logger.warning("Groq rate limit: %s", e)
            return {"ok": False, "spiegazione": "", "sql": None,
                    "risultati": None, "conteggio": 0, "total_count": None,
                    "errore": GROQ_RATE_LIMIT_MESSAGE}
        logger.exception("Errore chiamata LLM")
        return {"ok": False, "spiegazione": "", "sql": None,
                "risultati": None, "conteggio": 0, "total_count": None,
                "errore": f"Errore comunicazione con il servizio AI: {e}"}

    raw_content = content or ""
    parsed = _parse_ai_response(raw_content)
    sql = parsed.get("sql")
    spiegazione = parsed.get("spiegazione", "")

    # Se la risposta contiene comunque '"sql"' ma sembra troncata (JSON non chiusa),
    # facciamo un retry con più token per far arrivare la SQL completa.
    if not sql and '"sql"' in raw_content and not raw_content.strip().endswith("}"):
        try:
            if backend == "groq":
                max_tokens_retry = min(int(_get_groq_max_tokens() * 1.5), 900)
            else:
                max_tokens_retry = 2500

            retry_messages = [
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": _build_ai_user_prompt(prompt)
                    + "\n\nRispondi SOLO con JSON valido e NON troncare la risposta.",
                },
            ]
            response = _call_llm(retry_messages, max_tokens_retry)
            raw_content = response.choices[0].message.content or ""
            parsed = _parse_ai_response(raw_content)
            sql = parsed.get("sql")
            spiegazione = parsed.get("spiegazione", "")
        except ValueError as e:
            return {"ok": False, "spiegazione": "", "sql": None,
                    "risultati": None, "conteggio": 0, "total_count": None,
                    "errore": str(e)}
        except Exception:
            # Se retry fallisce, gestiamo come prima (sql None).
            pass

    if not sql:
        return {"ok": True, "spiegazione": spiegazione, "sql": None,
                "risultati": None, "conteggio": 0, "total_count": None,
                "errore": None}

    sql = _fix_column_quoting(sql)
    sql = _fix_primary_key_columns(sql)
    sql_has_limit_generated = bool(re.search(r"\bLIMIT\b", sql, flags=re.IGNORECASE))

    if not _is_safe_sql(sql):
        return {"ok": False, "spiegazione": spiegazione, "sql": sql,
                "risultati": None, "conteggio": 0, "total_count": None,
                "errore": "Query non consentita: sono ammesse solo query SELECT."}

    # Esecuzione con LIMIT (limit+1) per poter capire se esistono "più risultati del limite"
    # (così la UI può mostrare correttamente il bottone "Tutti").
    sql_before_execute = _ensure_limit(sql, limit + 1)
    sql_has_limit_effective = bool(re.search(r"\bLIMIT\b", sql_before_execute, flags=re.IGNORECASE))

    try:
        t_sql_start = time.perf_counter()
        risultati, has_more = _execute_query(sql_before_execute, limit)
        t_sql_end = time.perf_counter()
    except Exception as e:
        logger.exception("Errore esecuzione query AI")
        return {"ok": False, "spiegazione": spiegazione, "sql": sql_before_execute,
                "risultati": None, "conteggio": 0, "has_more": False, "total_count": None,
                "errore": f"Errore nell'esecuzione della query: {e}"}

    link_info = _build_detail_links(risultati, sql_before_execute)
    table = _detect_table(sql_before_execute)
    total_count: int | None = None
    # The AI modal shows the "Tutti" button only when the backend reports has_more.
    # To keep DB load reasonable, we compute total_count only when the list flow
    # is actually possible and there are more rows than the displayed window.
    if has_more and table and table in TABLE_LIST_ROUTES:
        total_count = _execute_total_count(sql_before_execute)

    return {
        "ok": True,
        "spiegazione": spiegazione,
        "sql": sql_before_execute,
        "risultati": risultati,
        "conteggio": len(risultati),
        "has_more": has_more,
        "total_count": total_count,
        "errore": None,
        "link": link_info,
        "table": table,
        "time_spent_llm_request": t_llm_end - t_llm_start,
        "time_spent_sql_execution": t_sql_end - t_sql_start,
        "rows_returned": len(risultati),
        "sql_has_limit_generated": sql_has_limit_generated,
        "sql_has_limit_effective": sql_has_limit_effective,
    }
