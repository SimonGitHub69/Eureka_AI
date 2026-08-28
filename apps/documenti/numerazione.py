"""Numerazione automatica documenti (id_4d / numero / contatori)."""

from __future__ import annotations

from django.db import transaction
from django.db.models import Max, Q

from apps.documenti.models import ContatoreDocumento, RigaDocumento, TestaDocumento, TipoDocumento


def format_numero_documento(numero, serie="", *, empty: str = "") -> str:
    """Numero visibile: ``1/FF`` se c'è serie, altrimenti solo il numero (niente slash)."""
    serie = (serie or "").strip()
    if numero is None or numero == "":
        return serie or empty
    if not serie:
        return str(numero)
    return f"{numero}/{serie}"


def next_testa_id_4d(tipo_doc: str) -> int:
    current = (
        TestaDocumento.objects.filter(tipo_doc_id=tipo_doc).aggregate(m=Max("id_4d"))[
            "m"
        ]
        or 0
    )
    return int(current) + 1


def next_numero_documento(tipo_doc: str, alfa: str = "") -> int:
    """Fallback legacy: max(numero) + 1 per tipo documento e serie (alfa)."""
    qs = TestaDocumento.objects.filter(tipo_doc_id=tipo_doc)
    serie = (alfa or "").strip()
    if serie:
        qs = qs.filter(alfa=serie)
    else:
        qs = qs.filter(Q(alfa="") | Q(alfa__isnull=True))
    current = qs.aggregate(m=Max("numero"))["m"] or 0
    return int(current) + 1


def _resolve_tipo(tipo: TipoDocumento | str) -> TipoDocumento:
    if isinstance(tipo, TipoDocumento):
        return tipo
    return TipoDocumento.objects.select_related("contatore").get(
        pk=(tipo or "").strip().upper()
    )


def resolve_contatore(
    tipo: TipoDocumento | str,
    contatore: ContatoreDocumento | str | None = None,
) -> ContatoreDocumento | None:
    """Contatore effettivo: esplicito (se ammesso), altrimenti predefinito del tipo.

    Il default usa solo i contatori del tipo corrente (non quelli affini).
    I contatori affini (es. Ordini su Nuovo Preventivo) restano selezionabili
    esplicitamente dal combo Serie.
    """
    tipo = _resolve_tipo(tipo)
    if contatore is not None and contatore != "":
        if isinstance(contatore, ContatoreDocumento):
            chosen = contatore
        else:
            chosen = None
            raw = contatore
            if isinstance(raw, int) or (isinstance(raw, str) and str(raw).isdigit()):
                chosen = ContatoreDocumento.objects.filter(pk=int(raw)).first()
            if chosen is None and isinstance(raw, str):
                chosen = (
                    ContatoreDocumento.objects.filter(
                        codice=(raw or "").strip().upper(),
                        tipo_contatore=ContatoreDocumento.TIPO_DOCUMENTI,
                    )
                    .order_by("-esercizio")
                    .first()
                )
        if chosen is None:
            return None
        ammessi = {c.pk for c in tipo.contatori_disponibili()}
        if ammessi and chosen.pk not in ammessi:
            return None
        return chosen
    if tipo.contatore_id:
        return tipo.contatore
    propri = TipoDocumento._contatori_del_tipo(tipo)
    return propri[0] if propri else None


def label_contatore_serie(contatore: ContatoreDocumento) -> str:
    """Etichetta combo Serie: tipi di origine + serie distinta + descrizione.

    Senza serie (o se coincide col codice tipo, es. PRV == PRV) mostra solo il
    tipo: ``PRV — Numero Preventivo``. Con serie distinta: ``PRV · FF — …``.
    """
    tipicodes = getattr(contatore, "_tipi_origine_codici", None) or []
    tipo = "/".join(tipicodes) or (contatore.codice or "").strip()
    serie = (contatore.serie_default or "").strip()
    year = getattr(contatore, "esercizio", None)
    if serie and serie.upper() != tipo.upper():
        label = f"{tipo} · {serie} — {contatore.label}"
    else:
        label = f"{tipo} — {contatore.label}"
    if year:
        return f"{label} ({year})"
    return label


def peek_next_numero(
    tipo: TipoDocumento | str,
    alfa: str = "",
    contatore: ContatoreDocumento | str | None = None,
) -> int:
    """Prossimo numero in anteprima (non incrementa il contatore)."""
    tipo = _resolve_tipo(tipo)
    c = resolve_contatore(tipo, contatore)
    if c is not None:
        return int(c.ultimo_numero or 0) + 1
    return next_numero_documento(tipo.codice, alfa)


def allocate_next_numero(
    tipo: TipoDocumento | str,
    alfa: str = "",
    contatore: ContatoreDocumento | str | None = None,
) -> int:
    """Assegna il prossimo numero documento in modo atomico.

    Se è risolvibile un Contatore, incrementa ``ultimo_numero`` con
    ``select_for_update`` (più tipi possono condividere lo stesso contatore).
    Altrimenti usa la numerazione legacy per tipo + serie.
    """
    tipo = _resolve_tipo(tipo)
    c = resolve_contatore(tipo, contatore)
    if c is None:
        return next_numero_documento(tipo.codice, alfa)

    with transaction.atomic():
        locked = ContatoreDocumento.objects.select_for_update().get(pk=c.pk)
        next_n = int(locked.ultimo_numero or 0) + 1
        locked.ultimo_numero = next_n
        locked.save(update_fields=["ultimo_numero"])
        return next_n


def serie_default_for(
    tipo: TipoDocumento,
    contatore: ContatoreDocumento | str | None = None,
) -> str:
    """Serie (alfa) predefinita.

    Senza contatore esplicito: tipo.serie, altrimenti serie del contatore predefinito.
    Con contatore esplicito: se è il predefinito del tipo e tipo.serie è valorizzata,
    usa tipo.serie; altrimenti serie del contatore scelto.
    """
    tipo = _resolve_tipo(tipo)
    explicit = contatore is not None and contatore != ""
    c = resolve_contatore(tipo, contatore if explicit else None)
    if explicit:
        if c is None:
            return ""
        if tipo.contatore_id and c.pk == tipo.contatore_id:
            serie_tipo = (getattr(tipo, "serie", None) or "").strip()
            if serie_tipo:
                return serie_tipo
        return (c.serie_default or "").strip()
    serie_tipo = (getattr(tipo, "serie", None) or "").strip()
    if serie_tipo:
        return serie_tipo
    if c is None:
        return ""
    return (c.serie_default or "").strip()


def initial_numerazione(
    tipo: TipoDocumento,
    contatore: ContatoreDocumento | str | None = None,
) -> dict:
    """Valori iniziali numero/serie/contatore per Nuovo documento (solo anteprima)."""
    c = resolve_contatore(tipo, contatore)
    alfa = serie_default_for(tipo, c)
    return {
        "numero": peek_next_numero(tipo, alfa, contatore=c),
        "alfa": alfa,
        "contatore_scelto": c.pk if c is not None else None,
    }


def next_riga_id_4d(testa: TestaDocumento) -> int:
    current = (
        RigaDocumento.objects.filter(testa=testa).aggregate(m=Max("id_4d"))["m"] or 0
    )
    return int(current) + 1


def next_numero_riga(existing_nums) -> int:
    """Prossimo numero riga = max(existing) + 10. Se nessuno, parte da 10.

    Allineato al JS Aggiungi riga: max tra i numeri presenti (ignora blank),
    così una riga extra vuota o fuori ordine non fa ripartire da 10.
    """
    nums = []
    for n in existing_nums:
        if n is None or n == "":
            continue
        try:
            nums.append(int(n))
        except (TypeError, ValueError):
            continue
    if not nums:
        return 10
    return max(nums) + 10
