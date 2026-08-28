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
MAX_SYNONYM_OR_CLAUSES = 8
EXPORT_MAX_ROWS = 10000
GROQ_RATE_LIMIT_MESSAGE = (
    "Limite Groq raggiunto, riprova tra qualche minuto. "
    "Puoi anche avviare Ollama in locale come alternativa."
)
GROQ_TPD_LIMIT_MESSAGE = (
    "Limite giornaliero Groq esaurito. Riprova domani oppure "
    "configura Ollama in locale (AI_BACKEND=ollama)."
)

# Sinonimi comuni per ricerche testuali articoli (fast path senza LLM).
_ARTICLE_SYNONYM_MAP: dict[str, list[str]] = {
    "calzature": ["calzature", "scarpe", "stivali", "sandali", "ciabatte", "scarpette", "calzatura"],
    "calzatura": ["calzature", "scarpe", "stivali", "sandali", "ciabatte", "scarpette", "calzatura"],
    "scarpe": ["scarpe", "calzature", "stivali", "sandali", "ciabatte", "scarpette", "calzatura"],
    "abbigliamento": ["abbigliamento", "vestiti", "capi", "magliette", "pantaloni", "camicie", "giacche"],
    "elettronica": ["elettronica", "elettrico", "elettrici", "componenti", "circuiti"],
    "minuteria": ["minuteria", "viti", "bulloni", "dadi", "rondelle", "ferramenta"],
    "alimentari": ["alimentari", "alimento", "cibo", "bevande", "gastronomia"],
    "mobili": ["mobili", "mobile", "arredamento", "sedie", "tavoli", "armadi"],
}

DB_SCHEMA = """
Database PostgreSQL — ERP gestionale italiano (Eureka AI).
Colonne CamelCase: usa SEMPRE virgolette doppie ("DataReg", "Codice", ecc.).

PK "Codice": articoli, clienti, fornitori, agenti, aliquote, causali_contabili,
  pdc, condizioni, categorie, banche, valuta, zone, gruppi_articoli
PK "ID": primanota, valuta_det
PK "ID" riga + FK testa: primanota_dettaglio ("ID" = PK riga; "id_added_by_converter" = FK verso primanota."ID", SOLO su primanota_dettaglio)
PK id: teste_documenti, righe_documenti

Tabelle principali:
- primanota: "ID" (PK testa), "NumeroReg", "DataReg", "NumeroDoc", "DataDoc", "Causale", "Registro",
  "Tipo" (1=Generico,2=IVA,3=Corrispettivi,4=IvaAutofattura), "CodicePartita", "Valuta",
  "TotaleDoc_Controllo", "Acconto"
- primanota_dettaglio: "ID" (PK riga), "id_added_by_converter" (FK verso primanota."ID", NON esiste su primanota),
  "ContoDare", "ContoAvere", "Dare", "Avere_Imponibile", "Imp_Val", "CodiceIva", "ImportoIva", "Descrizione", "dummy"
  (totale documento IVA per testa = SUM(COALESCE("Avere_Imponibile",0)+COALESCE("ImportoIva",0)) GROUP BY primanota."ID", escludi dummy)
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
   Il totale documento IVA per testa = SUM(COALESCE(pd."Avere_Imponibile", 0) + COALESCE(pd."ImportoIva", 0)) sulle righe di primanota_dettaglio (escludi righe dummy: pd."dummy" IS NOT TRUE).
6. JOIN primanota ↔ primanota_dettaglio: usa SEMPRE primanota."ID" = primanota_dettaglio."id_added_by_converter".
   "id_added_by_converter" esiste SOLO su primanota_dettaglio (mai su primanota).
   Esempio corretto (imponibile riga):
   SELECT p."ID", p."DataReg", pd."Avere_Imponibile"
   FROM primanota p
   JOIN primanota_dettaglio pd ON p."ID" = pd."id_added_by_converter"
   WHERE p."Tipo" IN (2, 4) AND pd."Avere_Imponibile" BETWEEN 1500 AND 1750
     AND EXTRACT(YEAR FROM p."DataReg") = EXTRACT(YEAR FROM CURRENT_DATE)
   Esempio corretto (totale documento per testa):
   SELECT p."ID", p."DataReg", p."NumeroReg", p."Causale"
   FROM primanota p
   JOIN primanota_dettaglio pd ON p."ID" = pd."id_added_by_converter"
   WHERE p."Tipo" IN (2, 4) AND pd."dummy" IS NOT TRUE
     AND EXTRACT(YEAR FROM p."DataReg") = EXTRACT(YEAR FROM CURRENT_DATE)
   GROUP BY p."ID", p."DataReg", p."NumeroReg", p."Causale"
   HAVING SUM(COALESCE(pd."Avere_Imponibile", 0) + COALESCE(pd."ImportoIva", 0)) BETWEEN 1500 AND 1750
   Esempio SBAGLIATO: ... ON p."ID" = p."id_added_by_converter"
   Esempio SBAGLIATO: ... ON p."ID" = pd."ID" (pd."ID" è la PK riga, non la FK testa)
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
    - usa articoli."Descrizione" o altri campi testuali SOLO se l'utente chiede esplicitamente una ricerca per descrizione/nome/testo/contenuto/sinonimi
    - se il termine richiesto (es. "abbigliamento") non corrisponde con affidabilità a un codice/campo strutturato disponibile nello schema, rispondi con {{"sql": null, "spiegazione": "..."}} spiegando che serve indicare categoria/gruppo/codice reale o chiedere una ricerca testuale esplicita
    - se l'utente chiede esplicitamente sinonimi in descrizione/nome/testo, ESPANDI i sinonimi comuni del termine e genera la query con ILIKE collegati da OR (includi sempre anche il termine originale)
14. Esempi per articoli:
    - "articoli della categoria merceologica CAT01" -> filtra articoli."CatOmogenea" = 'CAT01'
    - "articoli del gruppo GR10" -> filtra articoli."CodGruppo" = 'GR10'
    - "articoli del gruppo con descrizione minuteria" -> JOIN gruppi_articoli e filtra gruppi_articoli."Descrizione" ILIKE '%minuteria%'
    - "cerca articoli con abbigliamento nella descrizione" -> SOLO qui è consentito filtrare articoli."Descrizione" ILIKE '%abbigliamento%'
    - "articoli con calzature nella descrizione" -> SELECT "Codice", "Descrizione" FROM articoli WHERE "Descrizione" ILIKE '%calzature%'
    - "articoli con descrizione sinonimi di calzature" -> SELECT "Codice", "Descrizione" FROM articoli WHERE ("Descrizione" ILIKE '%calzature%' OR "Descrizione" ILIKE '%scarpe%' OR "Descrizione" ILIKE '%stivali%' OR "Descrizione" ILIKE '%sandali%' OR "Descrizione" ILIKE '%ciabatte%')
15. Per filtri su articoli attivi/disattivati (colonna articoli."FlDisattivato"):
    - articoli disattivati -> WHERE "FlDisattivato" IS TRUE (NON usare = true né IS NOT TRUE)
    - articoli attivi -> WHERE "FlDisattivato" IS NOT TRUE (include NULL e false; NON usare = true)
    - se l'utente non specifica lo stato, non filtrare su "FlDisattivato"
    Esempio: "articoli disattivati con descrizione sinonimi di calzature" ->
    SELECT "Codice", "Descrizione" FROM articoli WHERE "FlDisattivato" IS TRUE AND ("Descrizione" ILIKE '%calzature%' OR "Descrizione" ILIKE '%scarpe%' OR "Descrizione" ILIKE '%stivali%' OR "Descrizione" ILIKE '%sandali%' OR "Descrizione" ILIKE '%ciabatte%')
16. Per ricerche testuali sul Piano dei Conti (tabella pdc):
    - usa pdc."Descrizione" con ILIKE quando l'utente chiede esplicitamente descrizione/nome/testo/contenuto
    - includi sempre "Codice" e "Descrizione" nel SELECT (PK = "Codice")
    Esempio: "cerca nel Piano dei conti dove descrizione è cassa" ->
    SELECT "Codice", "Descrizione" FROM pdc WHERE "Descrizione" ILIKE '%cassa%'
17. Per aggregazioni mensili con grafico (es. primanota IVA per mese), i tipi supportati sono:
    - barre verticali (default): "grafico", "istogramma", "chart"
    - torta: "torta", "pie", "grafico a torta"
    - linee: "linee", "andamento", "trend", "grafico a linee"
    - area: "area", "grafico ad area"
    - barre orizzontali: "barre orizzontali", "istogramma orizzontale"
    - radar: "radar", "ragnatela"
    Se l'utente chiede solo "grafico" senza tipo esplicito, usa barre verticali.
18. Per export XLSX/CSV: genera SOLO un SELECT con le colonne richieste.
    NON usare INTO OUTFILE, COPY TO, \\copy né altre sintassi di scrittura file:
    l'applicazione genera il file dopo l'esecuzione della SELECT.
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


def _is_groq_tpd_limit_error(exc: Exception) -> bool:
    err = str(exc).lower()
    return "tokens per day" in err or "tpd" in err


def _get_ollama_fallback_timeout() -> float:
    return float(getattr(settings, "OLLAMA_FALLBACK_TIMEOUT", 5))


def _is_ollama_available() -> bool:
    url = getattr(settings, "OLLAMA_URL", "http://localhost:11434").rstrip("/") + "/api/tags"
    try:
        with urllib.request.urlopen(url, timeout=2) as resp:
            return resp.status == 200
    except (urllib.error.URLError, TimeoutError, OSError):
        return False


def _chat_completion(
    client,
    model: str,
    messages: list,
    max_tokens: int,
    timeout: float | None = None,
):
    kwargs = {
        "model": model,
        "messages": messages,
        "temperature": 0,
        "max_tokens": max_tokens,
    }
    if timeout is not None:
        kwargs["timeout"] = timeout
    return client.chat.completions.create(**kwargs)


def _call_llm(messages: list, max_tokens: int):
    """
    Chiama il backend LLM configurato. Se Groq risponde 429/TPD e Ollama è attivo,
    effettua fallback locale con timeout breve.
    """
    backend = getattr(settings, "AI_BACKEND", "ollama")
    client = _get_client()
    model = _get_model()
    try:
        return _chat_completion(client, model, messages, max_tokens)
    except Exception as exc:
        if backend != "groq" or not _is_groq_rate_limit_error(exc):
            raise
        if not _is_ollama_available():
            if _is_groq_tpd_limit_error(exc):
                raise ValueError(GROQ_TPD_LIMIT_MESSAGE) from exc
            raise ValueError(GROQ_RATE_LIMIT_MESSAGE) from exc
        tpd = _is_groq_tpd_limit_error(exc)
        logger.warning(
            "Groq rate limit%s, fallback su Ollama (timeout %.0fs)",
            " TPD" if tpd else "",
            _get_ollama_fallback_timeout(),
        )
        ollama_model = getattr(settings, "OLLAMA_MODEL", "llama3.1")
        try:
            return _chat_completion(
                _get_ollama_client(),
                ollama_model,
                messages,
                max(2000, max_tokens),
                timeout=_get_ollama_fallback_timeout(),
            )
        except Exception as ollama_exc:
            logger.warning("Fallback Ollama fallito: %s", ollama_exc)
            if tpd:
                raise ValueError(GROQ_TPD_LIMIT_MESSAGE) from ollama_exc
            raise ValueError(GROQ_RATE_LIMIT_MESSAGE) from ollama_exc


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
    "sinonimi",
    "sinonimo",
)

_SYNONYM_TEXT_SEARCH_KEYWORDS = (
    "sinonimi",
    "sinonimo",
)

_ARTICLE_ACTIVE_KEYWORDS = (
    "attivi",
    "attivo",
    "non disattivati",
    "non disattivato",
    "solo attivi",
    "solo attivo",
)

_ARTICLE_INACTIVE_KEYWORDS = (
    "disattivati",
    "disattivato",
    "non attivi",
    "non attivo",
    "solo disattivati",
    "solo disattivato",
)

_PDC_DOMAIN_KEYWORDS = (
    "piano dei conti",
    "piano conti",
    "pdc",
)

_PRIMANOTA_KEYWORDS = (
    "primanota",
    "prima nota",
    "registrazioni iva",
    "registrazione iva",
)

_TOTALE_DOCUMENTO_KEYWORDS = (
    "totale documento",
    "totaledocumento",
    "totale doc",
)

_CURRENT_YEAR_KEYWORDS = (
    "anno in corso",
    "nell'anno in corso",
    "anno corrente",
    "quest'anno",
    "questo anno",
    "anno attuale",
)

_CHART_KEYWORDS = (
    "grafico",
    "grafici",
    "chart",
    "diagramma",
    "istogramma",
    "visualizza",
)

_FILE_EXPORT_KEYWORDS = (
    "xlsx",
    "excel",
    "csv",
    "genera un file",
    "genera file",
    "crea un file",
    "crea file",
    "file xlsx",
    "file excel",
    "file csv",
    "esporta",
    "esportare",
    "esportazione",
    "export",
    "scarica",
    "scaricare",
    "download",
)
_CSV_EXPORT_KEYWORDS = (
    "csv",
    "file csv",
    "in csv",
)
_XLSX_FORMAT_KEYWORDS = (
    "xlsx",
    "excel",
    "file xlsx",
    "file excel",
)
_XLSX_EXPORT_KEYWORDS = _FILE_EXPORT_KEYWORDS

_MONTHLY_CHART_KEYWORDS = (
    "per mese",
    "mensile",
    "mese per mese",
    "raggruppa per mese",
    "aggregato per mese",
    "ogni mese",
    "al mese",
)

_PIE_CHART_KEYWORDS = (
    "grafico a torta",
    "a torta",
    "pie chart",
    "torta",
    "pie",
)

_LINE_CHART_KEYWORDS = (
    "grafico a linee",
    "a linee",
    "line chart",
    "linee",
    "andamento",
    "trend",
)

_AREA_CHART_KEYWORDS = (
    "grafico ad area",
    "grafico a area",
    "area chart",
    "tipo area",
)

_HORIZONTAL_BAR_CHART_KEYWORDS = (
    "barre orizzontali",
    "barra orizzontale",
    "barre orizzontale",
    "istogramma orizzontale",
    "horizontal bar",
    "horizontal chart",
)

_RADAR_CHART_KEYWORDS = (
    "grafico radar",
    "radar chart",
    "radar",
    "ragnatela",
)

_PERCENTAGE_KEYWORDS = (
    "percentuali",
    "percentuale",
    "con percentuali",
    "%",
)

_MONTH_LABELS_IT = (
    "Gen", "Feb", "Mar", "Apr", "Mag", "Giu",
    "Lug", "Ago", "Set", "Ott", "Nov", "Dic",
)


def _normalize_prompt_text(prompt: str) -> str:
    return re.sub(r"\s+", " ", (prompt or "").strip().casefold())


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


def _is_pdc_domain(prompt: str) -> bool:
    normalized = _normalize_prompt_text(prompt)
    return any(token in normalized for token in _PDC_DOMAIN_KEYWORDS)


def _is_explicit_pdc_text_search(prompt: str) -> bool:
    if not _is_pdc_domain(prompt):
        return False
    normalized = _normalize_prompt_text(prompt)
    return any(token in normalized for token in _EXPLICIT_TEXT_SEARCH_KEYWORDS)


def _is_synonym_description_search(prompt: str) -> bool:
    normalized = _normalize_prompt_text(prompt)
    if not _is_explicit_article_text_search(prompt):
        return False
    return any(token in normalized for token in _SYNONYM_TEXT_SEARCH_KEYWORDS)


def _is_article_active_status_request(prompt: str) -> bool:
    normalized = _normalize_prompt_text(prompt)
    if not any(token in normalized for token in _ARTICLE_DOMAIN_KEYWORDS):
        return False
    return any(token in normalized for token in _ARTICLE_ACTIVE_KEYWORDS)


def _is_article_inactive_status_request(prompt: str) -> bool:
    normalized = _normalize_prompt_text(prompt)
    if not any(token in normalized for token in _ARTICLE_DOMAIN_KEYWORDS):
        return False
    return any(token in normalized for token in _ARTICLE_INACTIVE_KEYWORDS)


def _extract_article_search_term(prompt: str) -> str | None:
    """Estrae il termine di ricerca testuale da prompt articoli comuni."""
    normalized = _normalize_prompt_text(prompt)
    patterns = (
        r"sinonim[io]\s+(?:di\s+)?([a-zàèéìòù0-9\-]+)",
        r"(?:con|cerca)\s+([a-zàèéìòù0-9\-]+)\s+(?:nella\s+)?descrizione",
        r"descrizione\s+(?:che\s+)?(?:contiene|con)\s+([a-zàèéìòù0-9\-]+)",
        r"descrizione\s+sinonim[io]\s+di\s+([a-zàèéìòù0-9\-]+)",
        r"([a-zàèéìòù0-9\-]+)\s+descrizione(?:\s|$)",
    )
    skip_words = {
        "articoli", "articolo", "prodotto", "prodotti", "descrizione",
        "descrizioni", "sinonimi", "sinonimo", "attivi", "attivo",
        "disattivati", "disattivato", "cerca", "mostra", "mostrami",
        "con", "nella", "nel", "della", "delle", "degli", "dei", "del",
    }
    for pattern in patterns:
        match = re.search(pattern, normalized)
        if match:
            term = match.group(1).strip()
            if term and term not in skip_words and len(term) >= 3:
                return term
    return None


def _extract_pdc_search_term(prompt: str) -> str | None:
    """Estrae il termine di ricerca testuale da prompt Piano dei Conti comuni."""
    normalized = _normalize_prompt_text(prompt)
    patterns = (
        r"dove\s+descrizione\s+(?:è|e)\s+([a-zàèéìòù0-9\-]+)",
        r"descrizione\s+(?:è|e|=\s*)\s*([a-zàèéìòù0-9\-]+)",
        r"(?:con|cerca)\s+([a-zàèéìòù0-9\-]+)\s+(?:nella\s+)?descrizione",
        r"descrizione\s+(?:che\s+)?(?:contiene|con)\s+([a-zàèéìòù0-9\-]+)",
    )
    skip_words = {
        "piano", "conti", "conto", "pdc", "descrizione", "descrizioni",
        "cerca", "mostra", "mostrami", "con", "nella", "nel", "della",
        "delle", "degli", "dei", "del", "dove", "nel", "nei",
    }
    for pattern in patterns:
        match = re.search(pattern, normalized)
        if match:
            term = match.group(1).strip()
            if term and term not in skip_words and len(term) >= 2:
                return term
    return None


def _expand_article_search_terms(term: str, use_synonyms: bool) -> list[str]:
    """Espande un termine con sinonimi noti, limitando il numero di clausole OR."""
    term = (term or "").strip().lower()
    if not term:
        return []
    if use_synonyms and term in _ARTICLE_SYNONYM_MAP:
        expanded = list(_ARTICLE_SYNONYM_MAP[term])
    elif use_synonyms:
        expanded = [term]
    else:
        expanded = [term]
    seen: set[str] = set()
    unique: list[str] = []
    for item in expanded:
        key = item.lower()
        if key not in seen:
            seen.add(key)
            unique.append(item)
        if len(unique) >= MAX_SYNONYM_OR_CLAUSES:
            break
    return unique


def _export_columns_for_table(
    prompt: str, table: str | None
) -> tuple[list[str], list[str], dict[str, str]]:
    """Colonne export richieste nel prompt (con warning per token sconosciuti)."""
    from apps.core.ai_export import resolve_export_columns

    return resolve_export_columns(
        prompt,
        table,
        for_export=_wants_xlsx_export(prompt),
    )


def _export_columns_sql_hint(prompt: str, table: str | None) -> str | None:
    """Istruzione LLM per includere colonne richieste nel SELECT."""
    if not _wants_xlsx_export(prompt):
        return None
    from apps.core.ai_export import detect_export_table_from_prompt

    table = table or detect_export_table_from_prompt(prompt)
    columns, unknown, _header_overrides = _export_columns_for_table(prompt, table)
    if not columns:
        return None
    from apps.core.ai_export import (
        articoli_export_needs_any_join,
        build_articoli_sql_from_clause,
        build_articoli_sql_select_list,
        build_sql_select_list,
        format_export_columns_warning,
    )

    fmt_label = "CSV" if _resolve_export_format(prompt) == "csv" else "XLSX"
    if (table or "").strip().lower() == "articoli" and articoli_export_needs_any_join(columns):
        select_hint = build_articoli_sql_select_list(columns, qualified=True)
        from_hint = build_articoli_sql_from_clause(columns)
        hint = (
            f"Istruzione export: l'utente chiede un file {fmt_label}. "
            f"Includi nel SELECT: {select_hint}. "
            f"Usa FROM {from_hint}. "
            "NON usare INTO OUTFILE né COPY TO: solo SELECT."
        )
    else:
        from_table = (table or "").strip().lower()
        from_clause = f" FROM {from_table}" if from_table else ""
        hint = (
            f"Istruzione export: l'utente chiede un file {fmt_label}. "
            f"Genera SOLO SELECT {build_sql_select_list(columns)}{from_clause}. "
            "NON usare INTO OUTFILE né COPY TO: solo SELECT."
        )
    warning = format_export_columns_warning(unknown)
    if warning:
        hint += warning
    return hint


def _try_fast_path_table_export_sql(prompt: str) -> tuple[str, str] | None:
    """Bypass LLM per export tabella mirror (agenti, articoli senza filtri testuali, …)."""
    if not _wants_file_export(prompt):
        return None
    from apps.core.ai_export import (
        build_primanota_export_sql,
        build_table_export_sql,
        detect_export_table_from_prompt,
        extract_export_where_clauses,
        extract_primanota_export_filters,
        format_export_columns_warning,
        get_table_db_columns,
        resolve_export_columns,
    )

    table = detect_export_table_from_prompt(prompt)
    if not table or not get_table_db_columns(table):
        return None
    if table == "articoli" and _is_explicit_article_text_search(prompt):
        return None
    # Export completo tabella: non applicare filtri di ricerca testuale PDC
    # (la parola "descrizione" come colonna non è una ricerca).
    if table == "pdc" and _extract_pdc_search_term(prompt):
        return None

    export_columns, unknown, _ = resolve_export_columns(prompt, table, for_export=True)
    if not export_columns:
        return None

    if table == "primanota":
        where_clauses = extract_primanota_export_filters(prompt)
        sql = build_primanota_export_sql(export_columns, where_clauses)
    else:
        where_clauses = extract_export_where_clauses(prompt, table)
        sql = build_table_export_sql(table, export_columns, where_clauses)
    labels = ", ".join(export_columns)
    filter_label = f" Filtri: {' AND '.join(where_clauses)}." if where_clauses else ""
    spiegazione = (
        f"Export tabella {table} con colonne: {labels}.{filter_label}"
        f"{format_export_columns_warning(unknown)}"
    )
    return sql, spiegazione


def _try_fast_path_articoli_sql(prompt: str) -> tuple[str, str] | None:
    """
    Bypass LLM per ricerche articoli per descrizione (con optional sinonimi/stato).
    Restituisce (sql, spiegazione) oppure None.
    """
    if not _is_explicit_article_text_search(prompt):
        return None
    term = _extract_article_search_term(prompt)
    if not term:
        return None

    use_synonyms = _is_synonym_description_search(prompt)
    terms = _expand_article_search_terms(term, use_synonyms)
    if not terms:
        return None

    ilike_parts = [f'"Descrizione" ILIKE \'%{t}%\'' for t in terms]
    where_clauses: list[str] = []
    if _is_article_inactive_status_request(prompt):
        where_clauses.append('"FlDisattivato" IS TRUE')
    elif _is_article_active_status_request(prompt):
        where_clauses.append('"FlDisattivato" IS NOT TRUE')
    where_clauses.append(f"({' OR '.join(ilike_parts)})")

    from apps.core.ai_export import (
        build_articoli_fast_path_sql,
        format_export_columns_warning,
    )

    export_columns, unknown = _export_columns_for_table(prompt, "articoli")[:2]
    sql = build_articoli_fast_path_sql(export_columns, where_clauses)
    status_label = ""
    if _is_article_inactive_status_request(prompt):
        status_label = " disattivati"
    elif _is_article_active_status_request(prompt):
        status_label = " attivi"
    terms_label = ", ".join(terms)
    spiegazione = (
        f"Articoli{status_label} con descrizione contenente: {terms_label}."
        f"{format_export_columns_warning(unknown)}"
    )
    return sql, spiegazione


def _try_fast_path_pdc_sql(prompt: str) -> tuple[str, str] | None:
    """
    Bypass LLM per ricerche Piano dei Conti per descrizione.
    Restituisce (sql, spiegazione) oppure None.
    """
    if not _is_explicit_pdc_text_search(prompt):
        return None
    term = _extract_pdc_search_term(prompt)
    if not term:
        return None

    sql = (
        'SELECT "Codice", "Descrizione" FROM pdc '
        f'WHERE "Descrizione" ILIKE \'%{term}%\''
    )
    spiegazione = (
        f"Conti del piano dei conti con descrizione contenente: {term}."
    )
    return sql, spiegazione


def _is_primanota_iva_context(prompt: str) -> bool:
    normalized = _normalize_prompt_text(prompt)
    has_primanota = any(token in normalized for token in _PRIMANOTA_KEYWORDS)
    has_iva = "iva" in normalized
    return has_primanota or has_iva


def _is_primanota_iva_imponibile_request(prompt: str) -> bool:
    normalized = _normalize_prompt_text(prompt)
    return _is_primanota_iva_context(prompt) and "imponibile" in normalized


def _is_primanota_iva_totale_documento_request(prompt: str) -> bool:
    normalized = _normalize_prompt_text(prompt)
    has_totale_documento = any(
        token in normalized for token in _TOTALE_DOCUMENTO_KEYWORDS
    )
    return _is_primanota_iva_context(prompt) and has_totale_documento


def _parse_amount(value: str) -> float | None:
    cleaned = (value or "").strip().replace(".", "").replace(",", ".")
    try:
        return float(cleaned)
    except ValueError:
        return None


def _extract_imponibile_range(prompt: str) -> tuple[float, float] | None:
    normalized = _normalize_prompt_text(prompt)
    patterns = (
        r"compreso\s+tra\s+([\d.,]+)\s+e\s+([\d.,]+)",
        r"tra\s+([\d.,]+)\s+e\s+([\d.,]+)\s*(?:euro|€)?",
        r"da\s+([\d.,]+)\s+a\s+([\d.,]+)",
        r"between\s+([\d.,]+)\s+and\s+([\d.,]+)",
    )
    for pattern in patterns:
        match = re.search(pattern, normalized)
        if not match:
            continue
        low = _parse_amount(match.group(1))
        high = _parse_amount(match.group(2))
        if low is None or high is None:
            continue
        if low > high:
            low, high = high, low
        return low, high
    return None


def _is_current_year_request(prompt: str) -> bool:
    normalized = _normalize_prompt_text(prompt)
    return any(token in normalized for token in _CURRENT_YEAR_KEYWORDS)


def _wants_chart(prompt: str) -> bool:
    normalized = _normalize_prompt_text(prompt)
    if any(token in normalized for token in _CHART_KEYWORDS):
        return True
    return any(token in normalized for token in _MONTHLY_CHART_KEYWORDS)


def _wants_file_export(prompt: str) -> bool:
    normalized = _normalize_prompt_text(prompt)
    return any(token in normalized for token in _FILE_EXPORT_KEYWORDS)


def _wants_xlsx_export(prompt: str) -> bool:
    """True se l'utente chiede un export file (XLSX o CSV)."""
    return _wants_file_export(prompt)


def _resolve_export_format(prompt: str) -> str:
    """Restituisce ``csv`` o ``xlsx`` (default) in base al prompt."""
    normalized = _normalize_prompt_text(prompt)
    wants_csv = any(token in normalized for token in _CSV_EXPORT_KEYWORDS)
    wants_xlsx = any(token in normalized for token in _XLSX_FORMAT_KEYWORDS)
    if wants_csv and not wants_xlsx:
        return "csv"
    return "xlsx"


def _is_monthly_chart_request(prompt: str) -> bool:
    normalized = _normalize_prompt_text(prompt)
    return any(token in normalized for token in _MONTHLY_CHART_KEYWORDS)


def _wants_pie_chart(prompt: str) -> bool:
    normalized = _normalize_prompt_text(prompt)
    return any(token in normalized for token in _PIE_CHART_KEYWORDS)


def _wants_line_chart(prompt: str) -> bool:
    normalized = _normalize_prompt_text(prompt)
    return any(token in normalized for token in _LINE_CHART_KEYWORDS)


def _wants_area_chart(prompt: str) -> bool:
    normalized = _normalize_prompt_text(prompt)
    if any(token in normalized for token in _AREA_CHART_KEYWORDS):
        return True
    return _wants_chart(prompt) and re.search(r"\barea\b", normalized) is not None


def _wants_horizontal_bar_chart(prompt: str) -> bool:
    normalized = _normalize_prompt_text(prompt)
    return any(token in normalized for token in _HORIZONTAL_BAR_CHART_KEYWORDS)


def _wants_radar_chart(prompt: str) -> bool:
    normalized = _normalize_prompt_text(prompt)
    return any(token in normalized for token in _RADAR_CHART_KEYWORDS)


def _wants_percentages(prompt: str) -> bool:
    normalized = _normalize_prompt_text(prompt)
    return any(token in normalized for token in _PERCENTAGE_KEYWORDS)


def _resolve_chart_type_from_prompt(prompt: str) -> str:
    """
    Restituisce il tipo grafico richiesto nel prompt.
    Valori: pie, line, area, horizontalBar, radar, bar (default).
    """
    if _wants_pie_chart(prompt):
        return "pie"
    if _wants_horizontal_bar_chart(prompt):
        return "horizontalBar"
    if _wants_area_chart(prompt):
        return "area"
    if _wants_line_chart(prompt):
        return "line"
    if _wants_radar_chart(prompt):
        return "radar"
    return "bar"


def _resolve_chart_type(prompt: str) -> str:
    """Alias retrocompatibile per _resolve_chart_type_from_prompt."""
    return _resolve_chart_type_from_prompt(prompt)


def _build_primanota_iva_imponibile_monthly_chart_sql(
    low: float,
    high: float,
    current_year_only: bool,
) -> str:
    where_clauses = [
        'p."Tipo" IN (2, 4)',
        f'pd."Avere_Imponibile" BETWEEN {low:g} AND {high:g}',
    ]
    if current_year_only:
        where_clauses.append(
            'EXTRACT(YEAR FROM p."DataReg") = EXTRACT(YEAR FROM CURRENT_DATE)'
        )
    return (
        "SELECT EXTRACT(MONTH FROM p.\"DataReg\")::int AS mese, COUNT(*) AS conteggio "
        "FROM primanota p "
        'JOIN primanota_dettaglio pd ON p."ID" = pd."id_added_by_converter" '
        f'WHERE {" AND ".join(where_clauses)} '
        'GROUP BY EXTRACT(MONTH FROM p."DataReg") '
        "ORDER BY mese"
    )


def _monthly_chart_percentages(values: list[int]) -> list[int]:
    total = sum(values)
    if not total:
        return [0 for _ in values]
    return [round(value / total * 100) for value in values]


def _execute_monthly_chart(
    sql: str,
    *,
    title: str,
    dataset_label: str,
    chart_type: str = "bar",
    show_percentages: bool = False,
) -> dict:
    """Esegue aggregazione mensile e restituisce payload Chart.js."""
    with connection.cursor() as cursor:
        cursor.execute(sql)
        rows = cursor.fetchall()

    counts = [0] * 12
    for row in rows:
        month = int(row[0])
        if 1 <= month <= 12:
            counts[month - 1] = int(row[1])

    if chart_type == "pie":
        labels = []
        data = []
        for index, count in enumerate(counts):
            if count > 0:
                labels.append(_MONTH_LABELS_IT[index])
                data.append(count)
        chart = {
            "type": "pie",
            "title": title,
            "labels": labels,
            "datasets": [
                {
                    "label": dataset_label,
                    "data": data,
                    "percentages": _monthly_chart_percentages(data),
                }
            ],
            "showPercentages": True,
        }
        return chart

    resolved_type = chart_type if chart_type in (
        "bar", "line", "area", "horizontalBar", "radar",
    ) else "bar"
    chart = {
        "type": resolved_type,
        "title": title,
        "labels": list(_MONTH_LABELS_IT),
        "datasets": [
            {
                "label": dataset_label,
                "data": counts,
            }
        ],
    }
    if show_percentages:
        chart["showPercentages"] = True
        chart["datasets"][0]["percentages"] = _monthly_chart_percentages(counts)
    return chart


def _execute_monthly_bar_chart(
    sql: str,
    *,
    title: str,
    dataset_label: str,
) -> dict:
    """Compatibilità: grafico a barre mensile."""
    return _execute_monthly_chart(
        sql,
        title=title,
        dataset_label=dataset_label,
        chart_type="bar",
    )


def _try_build_primanota_iva_imponibile_chart(prompt: str) -> dict | None:
    """
    Costruisce un grafico mensile per primanota IVA per fascia imponibile.
    Tipi: bar, line, area, horizontalBar, radar, pie.
    Restituisce None se la richiesta non è supportata per i grafici.
    """
    if not _wants_chart(prompt):
        return None
    if not _is_monthly_chart_request(prompt):
        return None
    if not _is_primanota_iva_imponibile_request(prompt):
        return None

    amount_range = _extract_imponibile_range(prompt)
    if not amount_range:
        return None

    low, high = amount_range
    current_year_only = _is_current_year_request(prompt)
    sql = _build_primanota_iva_imponibile_monthly_chart_sql(
        low, high, current_year_only
    )
    year_label = " nell'anno in corso" if current_year_only else ""
    title = (
        f"Primanota IVA per mese di registrazione ({low:g}–{high:g} €)"
        f"{year_label}"
    )
    if not _is_safe_sql(sql):
        return None
    chart_type = _resolve_chart_type(prompt)
    return _execute_monthly_chart(
        sql,
        title=title,
        dataset_label="Registrazioni",
        chart_type=chart_type,
        show_percentages=_wants_percentages(prompt) and chart_type != "pie",
    )


def _try_fast_path_primanota_iva_imponibile_sql(prompt: str) -> tuple[str, str] | None:
    """
    Bypass LLM per ricerche primanota IVA per fascia imponibile (riga dettaglio).
    Restituisce (sql, spiegazione) oppure None.
    """
    if not _is_primanota_iva_imponibile_request(prompt):
        return None
    amount_range = _extract_imponibile_range(prompt)
    if not amount_range:
        return None

    low, high = amount_range
    where_clauses = [
        'p."Tipo" IN (2, 4)',
        f'pd."Avere_Imponibile" BETWEEN {low:g} AND {high:g}',
    ]
    if _is_current_year_request(prompt):
        where_clauses.append(
            'EXTRACT(YEAR FROM p."DataReg") = EXTRACT(YEAR FROM CURRENT_DATE)'
        )

    sql = (
        'SELECT p."ID", p."DataReg", p."NumeroReg", p."Causale", '
        'pd."Avere_Imponibile", pd."ImportoIva" '
        "FROM primanota p "
        'JOIN primanota_dettaglio pd ON p."ID" = pd."id_added_by_converter" '
        f'WHERE {" AND ".join(where_clauses)}'
    )
    year_label = " nell'anno in corso" if _is_current_year_request(prompt) else ""
    spiegazione = (
        f"Registrazioni primanota IVA con imponibile tra {low:g} e {high:g} euro"
        f"{year_label}."
    )
    return sql, spiegazione


def _try_fast_path_primanota_iva_totale_documento_sql(
    prompt: str,
) -> tuple[str, str] | None:
    """
    Bypass LLM per ricerche primanota IVA per fascia totale documento (testa).
    Restituisce (sql, spiegazione) oppure None.
    """
    if not _is_primanota_iva_totale_documento_request(prompt):
        return None
    amount_range = _extract_imponibile_range(prompt)
    if not amount_range:
        return None

    low, high = amount_range
    where_clauses = [
        'p."Tipo" IN (2, 4)',
        'pd."dummy" IS NOT TRUE',
    ]
    if _is_current_year_request(prompt):
        where_clauses.append(
            'EXTRACT(YEAR FROM p."DataReg") = EXTRACT(YEAR FROM CURRENT_DATE)'
        )

    sql = (
        'SELECT p."ID", p."DataReg", p."NumeroReg", p."Causale" '
        "FROM primanota p "
        'JOIN primanota_dettaglio pd ON p."ID" = pd."id_added_by_converter" '
        f'WHERE {" AND ".join(where_clauses)} '
        'GROUP BY p."ID", p."DataReg", p."NumeroReg", p."Causale" '
        "HAVING SUM(COALESCE(pd.\"Avere_Imponibile\", 0) + "
        f'COALESCE(pd."ImportoIva", 0)) BETWEEN {low:g} AND {high:g}'
    )
    year_label = " nell'anno in corso" if _is_current_year_request(prompt) else ""
    spiegazione = (
        f"Registrazioni primanota IVA con totale documento tra {low:g} e {high:g} euro"
        f"{year_label}."
    )
    return sql, spiegazione


# Alias retrocompatibile per test e import esterni.
_try_fast_path_primanota_iva_sql = _try_fast_path_primanota_iva_imponibile_sql


def _try_fast_path_sql(prompt: str) -> tuple[str, str] | None:
    """Prova i fast path noti prima della chiamata LLM."""
    return (
        _try_fast_path_table_export_sql(prompt)
        or _try_fast_path_articoli_sql(prompt)
        or _try_fast_path_pdc_sql(prompt)
        or _try_fast_path_primanota_iva_totale_documento_sql(prompt)
        or _try_fast_path_primanota_iva_imponibile_sql(prompt)
    )


def _primanota_join_sql_hint(prompt: str) -> str | None:
    if not (
        _is_primanota_iva_imponibile_request(prompt)
        or _is_primanota_iva_totale_documento_request(prompt)
    ):
        return None
    return (
        'Per il JOIN primanota ↔ primanota_dettaglio usa SEMPRE '
        'primanota."ID" = primanota_dettaglio."id_added_by_converter". '
        '"id_added_by_converter" esiste SOLO su primanota_dettaglio (mai sull\'alias di primanota). '
        'NON usare primanota."id_added_by_converter" né primanota_dettaglio."ID" come FK testa.'
    )


def _primanota_totale_documento_sql_hint(prompt: str) -> str | None:
    if not _is_primanota_iva_totale_documento_request(prompt):
        return None
    return (
        'Per filtrare per totale documento IVA aggrega per testa primanota: '
        'GROUP BY primanota."ID" (e campi testa in SELECT) con '
        'HAVING SUM(COALESCE(primanota_dettaglio."Avere_Imponibile", 0) + '
        'COALESCE(primanota_dettaglio."ImportoIva", 0)) nella fascia richiesta. '
        'Escludi righe dummy: primanota_dettaglio."dummy" IS NOT TRUE.'
    )


def _article_status_sql_hint(prompt: str) -> str | None:
    if _is_article_inactive_status_request(prompt):
        return (
            'Filtra gli articoli disattivati con WHERE "FlDisattivato" IS TRUE '
            '(NON usare = true né IS NOT TRUE; IS TRUE sfrutta l\'indice parziale).'
        )
    if _is_article_active_status_request(prompt):
        return (
            'Filtra gli articoli attivi con WHERE "FlDisattivato" IS NOT TRUE '
            '(NON usare = true).'
        )
    return None


def _build_ai_user_prompt(prompt: str) -> str:
    base_prompt = (prompt or "").strip()
    primanota_hint = _primanota_join_sql_hint(base_prompt)
    totale_documento_hint = _primanota_totale_documento_sql_hint(base_prompt)
    status_hint = _article_status_sql_hint(base_prompt)
    if _is_explicit_article_text_search(base_prompt):
        extra_hints = []
        if _is_synonym_description_search(base_prompt):
            extra_hints.append(
                "Istruzione per questa ricerca testuale: l'utente chiede sinonimi in descrizione. "
                'Genera una query SELECT su articoli filtrando articoli."Descrizione" con ILIKE '
                "collegati da OR. Espandi i sinonimi comuni del termine richiesto "
                "(es. calzature -> calzature, scarpe, stivali, sandali, ciabatte, "
                "scarpette, calzatura) includendo sempre anche il termine originale."
            )
        if status_hint:
            extra_hints.append(status_hint)
        export_hint = _export_columns_sql_hint(base_prompt, "articoli")
        if export_hint:
            extra_hints.append(export_hint)
        if extra_hints:
            return f"{base_prompt}\n\n" + "\n".join(extra_hints)
        return base_prompt
    if _is_explicit_pdc_text_search(base_prompt):
        return (
            f"{base_prompt}\n\n"
            "Istruzione: genera SELECT su pdc filtrando pdc.\"Descrizione\" con ILIKE "
            "per il termine richiesto. Includi sempre \"Codice\" e \"Descrizione\"."
        )
    extra_hints = []
    if primanota_hint:
        extra_hints.append(primanota_hint)
    if totale_documento_hint:
        extra_hints.append(totale_documento_hint)
    if status_hint:
        extra_hints.append(status_hint)
    export_hint = _export_columns_sql_hint(base_prompt, "articoli")
    if export_hint:
        extra_hints.append(export_hint)
    if extra_hints:
        return f"{base_prompt}\n\n" + "\n".join(extra_hints)
    if not _is_article_category_request(base_prompt):
        export_hint = _export_columns_sql_hint(base_prompt, None)
        if export_hint:
            return f"{base_prompt}\n\n{export_hint}"
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
    "Nr_Fatt_Anno", "GUID", "Cellulare", "id_added_by_converter",
}


def _fix_column_quoting(sql: str) -> str:
    """Add double-quotes around known CamelCase column names if missing."""
    for col in _KNOWN_COLUMNS:
        sql = re.sub(
            rf'(?<!")(?<!\w)\b{re.escape(col)}\b(?!")(?!\w*\()',
            f'"{col}"',
            sql,
            flags=re.IGNORECASE,
        )
    return sql


def _ensure_case_insensitive_text_search(sql: str) -> str:
    """
    Converte LIKE in ILIKE per ricerche testuali PostgreSQL (case-insensitive).
    Non modifica ILIKE già presente.
    """
    if not sql:
        return sql
    sql = re.sub(r"\bNOT\s+LIKE\b", "NOT ILIKE", sql, flags=re.IGNORECASE)
    sql = re.sub(r"(?<!I)\bLIKE\b", "ILIKE", sql, flags=re.IGNORECASE)
    return sql


def _is_safe_sql(sql: str) -> bool:
    """Verifica che la query sia solo SELECT."""
    normalized = re.sub(r"--.*$", "", sql, flags=re.MULTILINE)
    normalized = re.sub(r"/\*.*?\*/", "", normalized, flags=re.DOTALL)
    normalized = normalized.strip().upper()
    forbidden = ("INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "TRUNCATE",
                 "CREATE", "GRANT", "REVOKE", "EXEC", "EXECUTE", "INTO", "COPY")
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
    "primanota":         "primanota:list",
    "pdc":               "pdc:list",
}

# Query che partono da tabelle figlie → lista della testa (stesso db_table del ListView).
TABLE_LIST_TABLE_ALIASES = {
    "primanota_dettaglio": "primanota",
}


def resolve_ai_list_table(table: str | None) -> str | None:
    """Normalizza il nome tabella SQL verso la chiave di TABLE_LIST_ROUTES."""
    if not table:
        return None
    normalized = table.strip().lower()
    return TABLE_LIST_TABLE_ALIASES.get(normalized, normalized)

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
    "movimentit":           {"url": "movimenti:detail",              "pk": "ID_Testa", "param": "pk"},
    "gruppi_articoli":      {"url": "gruppi_articoli:detail",        "pk": "Codice",  "param": "codice"},
    "magazzini":            {"url": "magazzini:detail",              "pk": "Codice",  "param": "codice"},
    "depositi":             {"url": "depositi:detail",               "pk": "Numero",  "param": "codice"},
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


def _extract_table_aliases(sql: str, table: str) -> list[str]:
    """Restituisce il nome tabella e gli alias SQL eventualmente usati."""
    aliases = [table]
    reserved = {
        "ON", "WHERE", "JOIN", "LEFT", "RIGHT", "INNER", "OUTER", "CROSS", "AS",
        "AND", "OR", "GROUP", "ORDER", "LIMIT", "SELECT", "FROM",
    }
    for match in re.finditer(
        rf"\b(?:FROM|JOIN)\s+{re.escape(table)}\s+(?:AS\s+)?(\w+)\b",
        sql,
        re.IGNORECASE,
    ):
        alias = match.group(1)
        if alias.upper() not in reserved:
            aliases.append(alias)
    return aliases


def _preferred_table_ref(aliases: list[str]) -> str:
    """Preferisce l'alias SQL breve al nome tabella completo, se presente."""
    if len(aliases) > 1:
        return aliases[1]
    return aliases[0]


def _fix_primanota_dettaglio_joins(sql: str) -> str:
    """
    Corregge JOIN errati tra primanota e primanota_dettaglio quando la FK
    id_added_by_converter viene referenziata sull'alias di primanota.
    """
    if not sql:
        return sql
    lowered = sql.lower()
    if "primanota" not in lowered:
        return sql
    if "primanota_dettaglio" not in lowered and "id_added_by_converter" not in lowered:
        return sql

    pn_aliases = _extract_table_aliases(sql, "primanota")
    pd_aliases = _extract_table_aliases(sql, "primanota_dettaglio")
    if len(pd_aliases) == 1 and "primanota_dettaglio" not in lowered:
        pd_aliases = ["primanota_dettaglio"]

    pn_ref = _preferred_table_ref(pn_aliases)
    pd_ref = _preferred_table_ref(pd_aliases)
    fk_col = '"id_added_by_converter"'
    id_tail = r'(?=\s|$|\)|,|;)'

    for pn in pn_aliases:
        for pd in pd_aliases:
            if pn == pd:
                continue
            sql = re.sub(
                rf'(\b{re.escape(pn)}\."ID"\s*=\s*){re.escape(pn)}\."id_added_by_converter"',
                rf"\1{pd_ref}.{fk_col}",
                sql,
                flags=re.IGNORECASE,
            )
            sql = re.sub(
                rf"(\b{re.escape(pn)}\.\"ID\"\s*=\s*){re.escape(pn)}\.id_added_by_converter\b",
                rf"\1{pd_ref}.{fk_col}",
                sql,
                flags=re.IGNORECASE,
            )
            sql = re.sub(
                rf'(\b{re.escape(pn)}\."ID"\s*=\s*){re.escape(pd)}\."ID"{id_tail}',
                rf"\1{pd_ref}.{fk_col}",
                sql,
                flags=re.IGNORECASE,
            )
            sql = re.sub(
                rf'{re.escape(pn)}\."id_added_by_converter"\s*=\s*{re.escape(pn)}\."ID"',
                f'{pn_ref}."ID" = {pd_ref}.{fk_col}',
                sql,
                flags=re.IGNORECASE,
            )
            sql = re.sub(
                rf"{re.escape(pn)}\.id_added_by_converter\s*=\s*{re.escape(pn)}\.\"ID\"",
                f'{pn_ref}."ID" = {pd_ref}.{fk_col}',
                sql,
                flags=re.IGNORECASE,
            )
            sql = re.sub(
                rf'(\b{re.escape(pd)}\."ID"\s*=\s*){re.escape(pn)}\."ID"{id_tail}',
                rf'{pd_ref}.{fk_col} = {pn_ref}."ID"',
                sql,
                flags=re.IGNORECASE,
            )
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
    if not sql:
        return None

    # Ignore FROM inside expressions such as TRIM(BOTH FROM CONCAT(...)).
    main_from = re.search(
        r"\bFROM\s+([a-zA-Z_][\w]*)(?:\s+(?:AS\s+)?[a-zA-Z_][\w]*)?\s*(?:"
        r"(?:LEFT|RIGHT|INNER|CROSS|FULL)?\s*(?:OUTER\s+)?JOIN\b|"
        r"WHERE\b|GROUP\s+BY\b|ORDER\s+BY\b|HAVING\b|LIMIT\b|OFFSET\b|;|\Z)",
        sql,
        re.IGNORECASE | re.DOTALL,
    )
    if main_from:
        return main_from.group(1).lower()

    expr_from_names = {
        "concat",
        "coalesce",
        "trim",
        "cast",
        "extract",
        "substring",
        "nullif",
        "greatest",
        "least",
        "current_date",
        "current_timestamp",
        "now",
    }
    matches = list(re.finditer(r"\bFROM\s+([a-zA-Z_][\w]*)", sql, re.IGNORECASE))
    for match in reversed(matches):
        name = match.group(1).lower()
        if name in expr_from_names:
            continue
        # EXTRACT(YEAR FROM p."DataReg") — skip column refs after FROM
        if match.end(1) < len(sql) and sql[match.end(1)] == ".":
            continue
        return name
    return matches[-1].group(1).lower() if matches else None


def resolve_ai_pk_column(risultati: list[dict], table: str | None) -> tuple[str | None, dict | None]:
    """Trova la colonna PK nei risultati e la route dettaglio associata."""
    list_table = resolve_ai_list_table(table)
    if not list_table or list_table not in TABLE_DETAIL_ROUTES:
        return None, None
    route = TABLE_DETAIL_ROUTES[list_table]
    pk_col = route["pk"]
    pk_lower = pk_col.lower()
    found_col = None
    if risultati:
        for col in risultati[0].keys():
            if col.lower() == pk_lower or col == pk_col:
                found_col = col
                break
    if not found_col:
        return None, None
    return found_col, route


def collect_ai_pk_values(risultati: list[dict], pk_col: str) -> list[str]:
    """Estrae i valori PK (deduplicati, ordine preservato) dai risultati AI."""
    pk_list: list[str] = []
    seen: set[str] = set()
    for row in risultati:
        pk_val = row.get(pk_col)
        if pk_val is None:
            continue
        pk_str = str(pk_val).strip()
        if not pk_str or pk_str in seen:
            continue
        seen.add(pk_str)
        pk_list.append(pk_str)
    return pk_list


def _ensure_export_includes_list_pk(
    sql: str,
    table: str | None,
    export_columns: list[str],
) -> tuple[str, list[str]]:
    """Aggiunge la PK al SELECT export se serve per filtrare la lista."""
    list_table = resolve_ai_list_table(table)
    if not list_table or list_table not in TABLE_LIST_ROUTES:
        return sql, export_columns
    route = TABLE_DETAIL_ROUTES.get(list_table)
    if not route:
        return sql, export_columns
    pk = route["pk"]
    columns = list(export_columns)
    if pk.lower() not in {col.lower() for col in columns}:
        columns.insert(0, pk)
        from apps.core.ai_export import ensure_sql_select_columns

        sql = ensure_sql_select_columns(sql, [pk])
    return sql, columns


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

    # Fast path (articoli, primanota IVA imponibile/totale documento, ...): nessuna chiamata LLM.
    fast_path = _try_fast_path_sql(prompt)
    used_fast_path = fast_path is not None
    sql: str | None = None
    spiegazione = ""
    t_llm_start = t_llm_end = 0.0

    if used_fast_path:
        sql, spiegazione = fast_path
        logger.info("AI fast path (no LLM): %s", prompt[:80])
    else:
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
                err_msg = (
                    GROQ_TPD_LIMIT_MESSAGE
                    if _is_groq_tpd_limit_error(e)
                    else GROQ_RATE_LIMIT_MESSAGE
                )
                return {"ok": False, "spiegazione": "", "sql": None,
                        "risultati": None, "conteggio": 0, "total_count": None,
                        "errore": err_msg}
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
                t_retry_start = time.perf_counter()
                response = _call_llm(retry_messages, max_tokens_retry)
                t_llm_end = time.perf_counter()
                logger.info(
                    "AI JSON retry LLM: %.3fs", t_llm_end - t_retry_start
                )
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
    sql = _fix_primanota_dettaglio_joins(sql)
    sql = _fix_primary_key_columns(sql)
    sql = _ensure_case_insensitive_text_search(sql)
    sql_has_limit_generated = bool(re.search(r"\bLIMIT\b", sql, flags=re.IGNORECASE))
    wants_export = _wants_xlsx_export(prompt)
    exec_limit = EXPORT_MAX_ROWS if wants_export else limit
    export_columns: list[str] = []
    export_unknown: list[str] = []
    export_header_overrides: dict[str, str] = {}
    if wants_export:
        table_for_export = _detect_table(sql)
        export_columns, export_unknown, export_header_overrides = _export_columns_for_table(
            prompt, table_for_export
        )
        if export_columns:
            from apps.core.ai_export import ensure_sql_select_columns

            sql, export_columns = _ensure_export_includes_list_pk(
                sql, table_for_export, export_columns
            )
            sql = ensure_sql_select_columns(sql, export_columns)
        if export_unknown:
            from apps.core.ai_export import format_export_columns_warning

            spiegazione = (
                spiegazione + format_export_columns_warning(export_unknown)
            )

    if not _is_safe_sql(sql):
        return {"ok": False, "spiegazione": spiegazione, "sql": sql,
                "risultati": None, "conteggio": 0, "total_count": None,
                "errore": "Query non consentita: sono ammesse solo query SELECT."}

    # Esecuzione con LIMIT (limit+1) per poter capire se esistono "più risultati del limite"
    # (così la UI può mostrare correttamente il bottone "Tutti").
    sql_before_execute = _ensure_limit(sql, exec_limit + 1)
    sql_has_limit_effective = bool(re.search(r"\bLIMIT\b", sql_before_execute, flags=re.IGNORECASE))

    try:
        t_sql_start = time.perf_counter()
        risultati, has_more = _execute_query(sql_before_execute, exec_limit)
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
    list_table = resolve_ai_list_table(table)
    if has_more and list_table and list_table in TABLE_LIST_ROUTES:
        total_count = _execute_total_count(sql_before_execute)

    chart = None
    if _wants_chart(prompt):
        try:
            chart = _try_build_primanota_iva_imponibile_chart(prompt)
        except Exception:
            logger.exception("Errore generazione grafico AI")

    export_token = None
    download_filename = None
    export_headers = None
    if wants_export and risultati:
        try:
            from apps.core.ai_export import save_ai_export

            sheet_title = (table or "Dati").replace("_", " ").title()[:31]
            saved = save_ai_export(
                rows=risultati,
                table=table,
                requested_columns=export_columns or None,
                header_overrides=export_header_overrides or None,
                filename_stem=table or "export",
                sheet_title=sheet_title,
                fmt=_resolve_export_format(prompt),
            )
            export_token = saved["token"]
            download_filename = saved["filename"]
            export_headers = saved["headers"]
        except Exception:
            logger.exception("Errore generazione export AI")

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
        "chart": chart,
        "chart_requested": _wants_chart(prompt),
        "export_requested": wants_export,
        "export_token": export_token,
        "download_filename": download_filename,
        "export_headers": export_headers,
        "time_spent_llm_request": t_llm_end - t_llm_start,
        "time_spent_sql_execution": t_sql_end - t_sql_start,
        "fast_path": used_fast_path,
        "rows_returned": len(risultati),
        "sql_has_limit_generated": sql_has_limit_generated,
        "sql_has_limit_effective": sql_has_limit_effective,
    }
