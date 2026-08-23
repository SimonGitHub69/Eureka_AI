"""Risoluzione descrizioni per codici collegati in Articoli."""

from __future__ import annotations


LOOKUP_TIPI = (
    "cliente",
    "fornitore",
    "clifor",
    "magazzino",
    "categoria",
    "gruppo",
    "iva",
    "condizione",
    "articolo",
    "destinazione",
    "pdc",
    "pdc_clifor",
    "agente",
    "porto",
    "causale_trasp",
    "causale_contabile",
    "banca",
    "sconto",
)


def _norm(codice: str | None) -> str:
    return (codice or "").strip()


def _text_attr(obj, *names: str) -> str:
    """Primo attributo testuale non vuoto (ignora MagicMock / tipi non str)."""
    for name in names:
        value = getattr(obj, name, None)
        if isinstance(value, str):
            text = value.strip()
            if text:
                return text
    return ""


def descrizione_cliente(codice: str | None) -> str:
    codice = _norm(codice)
    if not codice:
        return ""
    try:
        from apps.anagrafiche.models import Cliente, get_by_codice

        obj = get_by_codice(
            Cliente, codice, only=("ragione_sociale1", "ragione_sociale2")
        )
        if obj is None:
            return ""
        return (obj.ragione_sociale or "").strip()
    except Exception:
        return ""


def descrizione_fornitore(codice: str | None) -> str:
    codice = _norm(codice)
    if not codice:
        return ""
    try:
        from apps.anagrafiche.models import Fornitore, get_by_codice

        obj = get_by_codice(
            Fornitore, codice, only=("ragione_sociale1", "ragione_sociale2")
        )
        if obj is None:
            return ""
        return (obj.ragione_sociale or "").strip()
    except Exception:
        return ""


def descrizione_clifor(codice: str | None) -> str:
    """Ragione sociale cliente o fornitore (codici C… / F…)."""
    return resolve_clifor("clifor", codice).get("descrizione") or ""


def descrizione_magazzino(codice: str | None) -> str:
    codice = _norm(codice)
    if not codice:
        return ""
    try:
        from apps.magazzini.models import Magazzino

        obj = (
            Magazzino.objects.filter(codice__iexact=codice)
            .only("descrizione")
            .first()
        )
        return ((obj.descrizione if obj else "") or "").strip()
    except Exception:
        return ""


def descrizione_categoria(codice: str | None) -> str:
    codice = _norm(codice)
    if not codice:
        return ""
    try:
        from apps.categorie.models import Categoria

        obj = (
            Categoria.objects.filter(codice__iexact=codice)
            .only("descrizione")
            .first()
        )
        return ((obj.descrizione if obj else "") or "").strip()
    except Exception:
        return ""


def descrizione_gruppo(codice: str | None) -> str:
    codice = _norm(codice)
    if not codice:
        return ""
    try:
        from apps.gruppi_articoli.models import GruppoArticolo

        obj = (
            GruppoArticolo.objects.filter(codice__iexact=codice)
            .only("descrizione")
            .first()
        )
        return ((obj.descrizione if obj else "") or "").strip()
    except Exception:
        return ""


def descrizione_condizione(codice: str | None) -> str:
    codice = _norm(codice)
    if not codice:
        return ""
    try:
        from apps.condizioni.models import Condizione

        obj = (
            Condizione.objects.filter(codice__iexact=codice)
            .only("descrizione")
            .first()
        )
        return ((obj.descrizione if obj else "") or "").strip()
    except Exception:
        return ""


def descrizione_agente(codice: str | None) -> str:
    codice = _norm(codice)
    if not codice:
        return ""
    try:
        from apps.anagrafiche.models import Agente, get_by_codice

        obj = get_by_codice(Agente, codice, only=("ragione_sociale",))
        if obj is None:
            return ""
        return (obj.ragione_sociale or "").strip()
    except Exception:
        return ""


def descrizione_porto(codice: str | None) -> str:
    """Chip lookup: Porto1 memorizza TabPorto.Descrizione, il chip mostra l'Incoterm."""
    codice = _norm(codice)
    if not codice:
        return ""
    try:
        from apps.documenti.models import Porto

        obj = (
            Porto.objects.filter(descrizione__iexact=codice)
            .only("cod_incoterm")
            .first()
        )
        return ((obj.cod_incoterm if obj else "") or "").strip()
    except Exception:
        return ""


def descrizione_causale_trasp(codice: str | None) -> str:
    codice = _norm(codice)
    if not codice:
        return ""
    try:
        from apps.causali_trasp.models import CausaleTrasporto

        obj = (
            CausaleTrasporto.objects.filter(codice__iexact=codice)
            .only("descrizione")
            .first()
        )
        return ((obj.descrizione if obj else "") or "").strip()
    except Exception:
        return ""


def descrizione_causale_contabile(codice: str | None) -> str:
    codice = _norm(codice)
    if not codice:
        return ""
    try:
        from apps.causali_contabili.models import CausaleContabile

        obj = (
            CausaleContabile.objects.filter(codice__iexact=codice)
            .only("descrizione", "desc_pn")
            .first()
        )
        if obj is None:
            return ""
        return (obj.descrizione or obj.desc_pn or "").strip()
    except Exception:
        return ""


def descrizione_banca(codice: str | None) -> str:
    codice = _norm(codice)
    if not codice:
        return ""
    try:
        from apps.banche.models import Banca

        obj = Banca.objects.filter(codice__iexact=codice).only("descrizione").first()
        return ((obj.descrizione if obj else "") or "").strip()
    except Exception:
        return ""


def descrizione_sconto(codice: str | None) -> str:
    codice = _norm(codice)
    if not codice:
        return ""
    try:
        from apps.sconti.models import Sconto

        obj = Sconto.objects.filter(codice__iexact=codice).only("sconto").first()
        return ((obj.sconto if obj else "") or "").strip()
    except Exception:
        return ""


def descrizione_iva(codice: str | None) -> str:
    codice = _norm(codice)
    if not codice:
        return ""
    try:
        from apps.aliquote.models import Aliquota

        obj = (
            Aliquota.objects.filter(codice__iexact=codice)
            .only("descrizione", "percentuale")
            .first()
        )
        if obj is None:
            return ""
        desc = (obj.descrizione or "").strip()
        if desc:
            return desc
        if obj.percentuale is not None:
            return f"IVA {obj.percentuale:g}%"
        return ""
    except Exception:
        return ""


def descrizione_pdc(codice: str | None) -> str:
    """Risolve descrizione solo per contropartite PDC (non mastri/conti)."""
    codice = _norm(codice)
    if not codice:
        return ""
    try:
        from apps.pdc.hierarchy import pdc_contropartite_qs, pdc_is_contropartita

        if not pdc_is_contropartita(codice):
            return ""
        obj = (
            pdc_contropartite_qs()
            .filter(codice__iexact=codice)
            .only("descrizione")
            .first()
        )
        return ((obj.descrizione if obj else "") or "").strip()
    except Exception:
        return ""


def descrizione_pdc_clifor(codice: str | None) -> str:
    """Contropartita PDC, oppure ragione sociale cliente/fornitore."""
    return descrizione_pdc(codice) or descrizione_clifor(codice)


def descrizione_articolo(codice: str | None) -> str:
    info = resolve_articolo(codice)
    return info.get("descrizione") or ""


_CLIFOR_ONLY = (
    "codice",
    "ragione_sociale1",
    "ragione_sociale2",
    "cond_paga",
    "agente",
    "telefono",
    "cellulare",
    "indirizzo",
    "localita",
    "cap",
    "provincia",
    "cod_nazione",
)


def _clifor_empty(codice: str | None) -> dict:
    return {
        "found": False,
        "codice": _norm(codice),
        "descrizione": "",
        "cond_paga": "",
        "cond_paga_descrizione": "",
        "agente": "",
        "agente_descrizione": "",
        "destinatario": "",
        "indirizzo": "",
        "localita": "",
        "cap": "",
        "provincia": "",
        "nazione": "",
        "telefono": "",
    }


def _clifor_from_obj(
    obj,
    cond_labels: dict[str, str] | None = None,
    agente_labels: dict[str, str] | None = None,
) -> dict:
    """Campi anagrafica da copiare sulla testata documento (come 4D)."""
    desc = (obj.ragione_sociale or "").strip()
    cond = (getattr(obj, "cond_paga", None) or "").strip()
    agente = _text_attr(obj, "agente")
    label = ""
    if cond:
        if cond_labels:
            label = (
                cond_labels.get(cond)
                or cond_labels.get(cond.upper())
                or cond_labels.get(cond.lower())
                or ""
            )
        else:
            label = descrizione_condizione(cond)
    agente_desc = ""
    if agente:
        if agente_labels:
            agente_desc = (
                agente_labels.get(agente)
                or agente_labels.get(agente.upper())
                or agente_labels.get(agente.lower())
                or ""
            )
        else:
            agente_desc = descrizione_agente(agente)
    return {
        "found": True,
        "codice": (obj.codice or "").strip(),
        "descrizione": desc,
        "cond_paga": cond,
        "cond_paga_descrizione": label,
        "agente": agente,
        "agente_descrizione": agente_desc,
        "destinatario": desc,
        "indirizzo": (getattr(obj, "indirizzo", None) or "").strip(),
        "localita": (getattr(obj, "localita", None) or "").strip(),
        "cap": (getattr(obj, "cap", None) or "").strip(),
        "provincia": (getattr(obj, "provincia", None) or "").strip(),
        "nazione": _text_attr(obj, "cod_nazione"),
        "telefono": _text_attr(obj, "cellulare", "telefono"),
    }


def resolve_clifor(tipo: str, codice: str | None) -> dict:
    """Cliente/fornitore: ragione sociale, sede e condizione di pagamento.

    ``tipo=clifor`` risolve C… su Clienti, F… su Fornitori; senza prefisso
    prova prima il cliente poi il fornitore (come Primanota CodicePartita).
    """
    empty = _clifor_empty(codice)
    code = _norm(codice)
    tipo = (tipo or "").strip().lower()
    if not code or tipo not in ("cliente", "fornitore", "clifor"):
        return empty
    if tipo == "clifor":
        from apps.destinazioni.models import tipo_clifor

        kind = tipo_clifor(code)
        if kind == "F":
            return resolve_clifor("fornitore", code)
        info = resolve_clifor("cliente", code)
        if info.get("found") or kind == "C":
            return info
        return resolve_clifor("fornitore", code)
    try:
        from apps.anagrafiche.models import Cliente, Fornitore, get_by_codice

        model = Cliente if tipo == "cliente" else Fornitore
        obj = get_by_codice(model, code, only=_CLIFOR_ONLY)
    except Exception:
        return empty
    if obj is None:
        return empty
    info = _clifor_from_obj(obj)
    info["kind"] = tipo
    return info


def resolve_articolo(codice: str | None) -> dict:
    """Dati riga documento da scheda articolo (codice → descrizione, IVA, UM, listino)."""
    empty = {
        "found": False,
        "codice": _norm(codice),
        "descrizione": "",
        "iva": "",
        "unita_misura": "",
        "prezzo_unitario": None,
    }
    code = _norm(codice)
    if not code:
        return empty
    try:
        from apps.articoli.models import Articolo

        obj = (
            Articolo.objects.filter(codice__iexact=code)
            .only(
                "codice",
                "descrizione",
                "cod_iva",
                "unita_misura",
                "listino1",
            )
            .first()
        )
        if obj is None:
            return empty
        return {
            "found": True,
            "codice": (obj.codice or "").strip(),
            "descrizione": (obj.descrizione or "").strip(),
            "iva": (obj.cod_iva or "").strip(),
            "unita_misura": (obj.unita_misura or "").strip(),
            "prezzo_unitario": obj.listino1,
        }
    except Exception:
        return empty


_RESOLVERS = {
    "cliente": descrizione_cliente,
    "fornitore": descrizione_fornitore,
    "clifor": descrizione_clifor,
    "magazzino": descrizione_magazzino,
    "categoria": descrizione_categoria,
    "gruppo": descrizione_gruppo,
    "iva": descrizione_iva,
    "condizione": descrizione_condizione,
    "articolo": descrizione_articolo,
    "pdc": descrizione_pdc,
    "pdc_clifor": descrizione_pdc_clifor,
    "agente": descrizione_agente,
    "porto": descrizione_porto,
    "causale_trasp": descrizione_causale_trasp,
    "causale_contabile": descrizione_causale_contabile,
    "banca": descrizione_banca,
    "sconto": descrizione_sconto,
}


def resolve_descrizione(tipo: str, codice: str | None) -> str:
    fn = _RESOLVERS.get((tipo or "").strip().lower())
    if not fn:
        return ""
    return fn(codice)


def _row(codice: str | None, descrizione: str | None) -> dict[str, str]:
    return {
        "codice": (codice or "").strip(),
        "descrizione": (descrizione or "").strip(),
    }


def search_opzioni(
    tipo: str,
    q: str | None = None,
    *,
    limit: int = 40,
    codice_clifor: str | None = None,
) -> list[dict]:
    """Elenco codice/descrizione per combobox (filtro opzionale).

    Per ``tipo=articolo`` include anche ``iva``, ``unita_misura``, ``prezzo_unitario``.
    Per ``tipo=cliente`` / ``fornitore`` include sede, ``cond_paga`` e ``agente``.
    Per ``tipo=clifor`` cerca in Clienti e Fornitori.
    Per ``tipo=destinazione`` richiede ``codice_clifor`` (DestCliFor).
    """
    tipo = (tipo or "").strip().lower()
    q = _norm(q)
    # PDC e PDC+clifor hanno centinaia di voci: limite più alto degli altri lookup.
    max_limit = 500 if tipo in ("pdc", "pdc_clifor") else 100
    default_limit = 400 if tipo in ("pdc", "pdc_clifor") else 40
    try:
        limit = int(limit or default_limit)
    except (TypeError, ValueError):
        limit = default_limit
    limit = max(1, min(limit, max_limit))

    try:
        if tipo == "destinazione":
            from apps.destinazioni.lookups import search_destinazioni

            return search_destinazioni(codice_clifor, q, limit=limit)

        if tipo == "clifor":
            clienti = [
                {**row, "kind": "cliente"}
                for row in search_opzioni("cliente", q, limit=limit)
            ]
            fornitori = [
                {**row, "kind": "fornitore"}
                for row in search_opzioni("fornitore", q, limit=limit)
            ]
            merged = clienti + fornitori
            merged.sort(
                key=lambda r: (
                    (r.get("descrizione") or "").casefold(),
                    (r.get("codice") or "").casefold(),
                )
            )
            return merged[:limit]

        if tipo == "pdc_clifor":
            per = max(limit, 40)
            pdc_rows = [
                {**row, "kind": "pdc"}
                for row in search_opzioni("pdc", q, limit=per)
            ]
            clifor_rows = search_opzioni("clifor", q, limit=per)
            merged = pdc_rows + list(clifor_rows)
            merged.sort(
                key=lambda r: (
                    (r.get("descrizione") or "").casefold(),
                    (r.get("codice") or "").casefold(),
                )
            )
            return merged[:limit]

        if tipo == "magazzino":
            from apps.magazzini.models import Magazzino

            qs = Magazzino.objects.all().only("codice", "descrizione")
            if q:
                from django.db.models import Q

                qs = qs.filter(Q(codice__icontains=q) | Q(descrizione__icontains=q))
            return [
                _row(o.codice, o.descrizione)
                for o in qs.order_by("descrizione", "codice")[:limit]
            ]

        if tipo == "categoria":
            from apps.categorie.models import Categoria
            from django.db.models import Q

            qs = Categoria.objects.all().only("codice", "descrizione")
            if q:
                qs = qs.filter(Q(codice__icontains=q) | Q(descrizione__icontains=q))
            return [
                _row(o.codice, o.descrizione)
                for o in qs.order_by("descrizione", "codice")[:limit]
            ]

        if tipo == "gruppo":
            from apps.gruppi_articoli.models import GruppoArticolo
            from django.db.models import Q

            qs = GruppoArticolo.objects.all().only("codice", "descrizione")
            if q:
                qs = qs.filter(Q(codice__icontains=q) | Q(descrizione__icontains=q))
            return [
                _row(o.codice, o.descrizione)
                for o in qs.order_by("descrizione", "codice")[:limit]
            ]

        if tipo == "cliente":
            from apps.anagrafiche.models import Cliente
            from django.db.models import Q

            qs = Cliente.objects.all().only(*_CLIFOR_ONLY)
            if q:
                qs = qs.filter(
                    Q(codice__icontains=q)
                    | Q(ragione_sociale1__icontains=q)
                    | Q(ragione_sociale2__icontains=q)
                )
            objects = list(qs.order_by("ragione_sociale1", "codice")[:limit])
            cond_labels = resolve_many(
                "condizione", [getattr(o, "cond_paga", "") for o in objects]
            )
            agente_labels = resolve_many(
                "agente", [getattr(o, "agente", "") for o in objects]
            )
            return [_clifor_from_obj(o, cond_labels, agente_labels) for o in objects]

        if tipo == "fornitore":
            from apps.anagrafiche.models import Fornitore
            from django.db.models import Q

            qs = Fornitore.objects.all().only(*_CLIFOR_ONLY)
            if q:
                qs = qs.filter(
                    Q(codice__icontains=q)
                    | Q(ragione_sociale1__icontains=q)
                    | Q(ragione_sociale2__icontains=q)
                )
            objects = list(qs.order_by("ragione_sociale1", "codice")[:limit])
            cond_labels = resolve_many(
                "condizione", [getattr(o, "cond_paga", "") for o in objects]
            )
            agente_labels = resolve_many(
                "agente", [getattr(o, "agente", "") for o in objects]
            )
            return [_clifor_from_obj(o, cond_labels, agente_labels) for o in objects]

        if tipo == "iva":
            from apps.aliquote.models import Aliquota
            from django.db.models import Q

            qs = Aliquota.objects.all().only("codice", "descrizione", "percentuale")
            if q:
                qs = qs.filter(Q(codice__icontains=q) | Q(descrizione__icontains=q))
            rows: list[dict[str, str]] = []
            for o in qs.order_by("codice")[:limit]:
                desc = (o.descrizione or "").strip()
                if not desc and o.percentuale is not None:
                    desc = f"IVA {o.percentuale:g}%"
                rows.append(_row(o.codice, desc))
            return rows

        if tipo == "pdc":
            # Solo contropartite (4D Tipo=1 / sottoconti), non mastri né conti.
            from apps.pdc.hierarchy import pdc_contropartite_qs
            from django.db.models import Q

            qs = pdc_contropartite_qs().only("codice", "descrizione")
            if q:
                qs = qs.filter(Q(codice__icontains=q) | Q(descrizione__icontains=q))
            return [
                _row(o.codice, o.descrizione)
                for o in qs.order_by("codice")[:limit]
            ]

        if tipo == "condizione":
            from apps.condizioni.models import Condizione
            from django.db.models import Q

            qs = Condizione.objects.all().only("codice", "descrizione")
            if q:
                qs = qs.filter(Q(codice__icontains=q) | Q(descrizione__icontains=q))
            return [
                _row(o.codice, o.descrizione)
                for o in qs.order_by("descrizione", "codice")[:limit]
            ]

        if tipo == "agente":
            from apps.anagrafiche.models import Agente
            from django.db.models import Q

            qs = Agente.objects.all().only("codice", "ragione_sociale")
            if q:
                qs = qs.filter(
                    Q(codice__icontains=q) | Q(ragione_sociale__icontains=q)
                )
            return [
                _row(o.codice, o.ragione_sociale)
                for o in qs.order_by("ragione_sociale", "codice")[:limit]
            ]

        if tipo == "porto":
            from apps.documenti.models import Porto
            from django.db.models import Q

            qs = Porto.objects.all().only("descrizione", "cod_incoterm")
            if q:
                qs = qs.filter(
                    Q(descrizione__icontains=q) | Q(cod_incoterm__icontains=q)
                )
            rows = []
            for o in qs.order_by("descrizione", "id")[:limit]:
                desc = (o.descrizione or "").strip()
                if not desc:
                    continue
                rows.append(_row(desc, o.cod_incoterm))
            return rows

        if tipo == "causale_trasp":
            from apps.causali_trasp.models import CausaleTrasporto
            from django.db.models import Q

            qs = CausaleTrasporto.objects.all().only("codice", "descrizione")
            if q:
                qs = qs.filter(Q(codice__icontains=q) | Q(descrizione__icontains=q))
            return [
                _row(o.codice, o.descrizione)
                for o in qs.order_by("descrizione", "codice")[:limit]
            ]

        if tipo == "causale_contabile":
            from apps.causali_contabili.models import CausaleContabile
            from django.db.models import Q

            qs = CausaleContabile.objects.all().only("codice", "descrizione", "desc_pn")
            if q:
                qs = qs.filter(
                    Q(codice__icontains=q)
                    | Q(descrizione__icontains=q)
                    | Q(desc_pn__icontains=q)
                )
            rows = []
            for o in qs.order_by("codice")[:limit]:
                rows.append(_row(o.codice, (o.descrizione or o.desc_pn or "").strip()))
            return rows

        if tipo == "banca":
            from apps.banche.models import Banca
            from django.db.models import Q

            qs = Banca.objects.all().only("codice", "descrizione")
            if q:
                qs = qs.filter(Q(codice__icontains=q) | Q(descrizione__icontains=q))
            return [
                _row(o.codice, o.descrizione)
                for o in qs.order_by("descrizione", "codice")[:limit]
            ]

        if tipo == "sconto":
            from apps.sconti.models import Sconto
            from django.db.models import Q

            qs = Sconto.objects.all().only("codice", "sconto")
            if q:
                qs = qs.filter(Q(codice__icontains=q) | Q(sconto__icontains=q))
            return [
                _row(o.codice, o.sconto)
                for o in qs.order_by("codice")[:limit]
            ]

        if tipo == "articolo":
            from apps.articoli.models import Articolo
            from django.db.models import Case, IntegerField, Q, Value, When

            qs = Articolo.objects.all().only(
                "codice",
                "descrizione",
                "cod_iva",
                "unita_misura",
                "listino1",
            )
            if q:
                # Ranking: exact/prefix codice first. Otherwise "VA" matches
                # STI*VA*LETTO / VALVOLA in descrizione and buries VA12/VA22.
                qs = qs.filter(Q(codice__icontains=q) | Q(descrizione__icontains=q))
                qs = qs.annotate(
                    _rank=Case(
                        When(codice__iexact=q, then=Value(0)),
                        When(codice__istartswith=q, then=Value(1)),
                        When(codice__icontains=q, then=Value(2)),
                        When(descrizione__istartswith=q, then=Value(3)),
                        default=Value(4),
                        output_field=IntegerField(),
                    )
                ).order_by("_rank", "codice", "descrizione")
            else:
                qs = qs.order_by("codice", "descrizione")
            rows: list[dict] = []
            for o in qs[:limit]:
                row = _row(o.codice, o.descrizione)
                row["iva"] = (o.cod_iva or "").strip()
                row["unita_misura"] = (o.unita_misura or "").strip()
                row["prezzo_unitario"] = o.listino1
                row["found"] = True
                rows.append(row)
            return rows
    except Exception:
        return []
    return []


def resolve_many(tipo: str, codici: list[str]) -> dict[str, str]:
    """Mappa codice → descrizione (chiavi originali + upper/lower)."""
    cleaned = sorted({_norm(c) for c in codici if _norm(c)})
    if not cleaned:
        return {}

    mapping: dict[str, str] = {}
    for codice in cleaned:
        label = resolve_descrizione(tipo, codice)
        if not label:
            continue
        mapping[codice] = label
        mapping[codice.upper()] = label
        mapping[codice.lower()] = label
    return mapping


def attach_articolo_linked_labels(articolo) -> None:
    """Imposta attributi *_label sull'istanza articolo per i template."""
    articolo.magazzino_label = descrizione_magazzino(getattr(articolo, "cod_magazzino", None))
    articolo.categoria_label = descrizione_categoria(getattr(articolo, "cat_omogenea", None))
    articolo.gruppo_label = descrizione_gruppo(getattr(articolo, "cod_gruppo", None))
    articolo.fornitore_label = descrizione_fornitore(getattr(articolo, "cod_fornitore", None))
    articolo.iva_label = descrizione_iva(getattr(articolo, "cod_iva", None))


def linked_labels_for_articolo(articolo) -> dict[str, str]:
    return {
        "magazzino": descrizione_magazzino(getattr(articolo, "cod_magazzino", None)),
        "categoria": descrizione_categoria(getattr(articolo, "cat_omogenea", None)),
        "gruppo": descrizione_gruppo(getattr(articolo, "cod_gruppo", None)),
        "fornitore": descrizione_fornitore(getattr(articolo, "cod_fornitore", None)),
        "iva": descrizione_iva(getattr(articolo, "cod_iva", None)),
        "c_partita_vend": descrizione_pdc(getattr(articolo, "c_partita_vend", None)),
        "c_partita_acq": descrizione_pdc(getattr(articolo, "c_partita_acq", None)),
    }


def attach_articoli_list_labels(articoli) -> None:
    """Batch (per-tipo) delle descrizioni per la lista articoli."""
    articoli = list(articoli)
    if not articoli:
        return

    mag = resolve_many("magazzino", [a.cod_magazzino for a in articoli])
    cat = resolve_many("categoria", [a.cat_omogenea for a in articoli])
    grp = resolve_many("gruppo", [a.cod_gruppo for a in articoli])
    forn = resolve_many("fornitore", [a.cod_fornitore for a in articoli])
    iva = resolve_many("iva", [a.cod_iva for a in articoli])

    def pick(mapping: dict[str, str], codice: str | None) -> str:
        c = _norm(codice)
        if not c:
            return ""
        return mapping.get(c) or mapping.get(c.upper()) or mapping.get(c.lower()) or ""

    for articolo in articoli:
        articolo.magazzino_label = pick(mag, articolo.cod_magazzino)
        articolo.categoria_label = pick(cat, articolo.cat_omogenea)
        articolo.gruppo_label = pick(grp, articolo.cod_gruppo)
        articolo.fornitore_ragione_sociale = pick(forn, articolo.cod_fornitore)
        articolo.fornitore_label = articolo.fornitore_ragione_sociale
        articolo.iva_label = pick(iva, articolo.cod_iva)
