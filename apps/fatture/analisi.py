"""Aggregazioni e confronti fatturato per periodi."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from functools import lru_cache

from django.db.models import Case, Count, DateField, F, FloatField, Max, Q, Sum, Value, When
from django.db.models.functions import Abs, Cast, Coalesce, ExtractMonth, ExtractYear, TruncMonth

from apps.anagrafiche.models import Cliente
from apps.fatture.models import Fattura

METRICHE = {
    "imponibile": ("imponibile", "Imponibile senza spese"),
    "totale": ("totale_fattura", "Totale senza spese"),
}

# Filtro note di credito: '' = tutte, escludi, solo
NOTE_CREDITO_MODES = {
    "": "Tutti i documenti",
    "escludi": "Escludi note di credito",
    "solo": "Solo note di credito",
}

# Campi spese di testata 4D che compongono il "Totale spese"
CAMPI_SPESE = (
    "spese_imballo",
    "spese_trasporto",
    "spese_incasso",
    "spese_varie",
    "spese_bolli",
    "spese_e15",
)

MESI_IT = (
    "",
    "Gen",
    "Feb",
    "Mar",
    "Apr",
    "Mag",
    "Giu",
    "Lug",
    "Ago",
    "Set",
    "Ott",
    "Nov",
    "Dic",
)


@dataclass(frozen=True)
class PeriodoKPI:
    fatturato: float  # metrica al netto delle spese (base del confronto)
    lordo: float  # metrica con spese incluse
    spese: float
    n_fatture: int
    n_clienti: int
    ticket_medio: float
    media_cliente: float


def q_note_credito() -> Q:
    """Note di credito: TipoDocFE = TD04 (fattura elettronica)."""
    return Q(tipo_doc_fe__iexact="TD04")


def filtro_note_credito(qs, mode: str = ""):
    mode = (mode or "").strip().lower()
    if mode not in NOTE_CREDITO_MODES:
        mode = ""
    if mode == "escludi":
        return qs.exclude(q_note_credito())
    if mode == "solo":
        return qs.filter(q_note_credito())
    return qs


def importo_con_segno(metrica_field: str):
    """
    Importo lordo per aggregazioni.
    Le note di credito (TD04) entrano sempre con segno negativo.
    """
    return Case(
        When(q_note_credito(), then=-Abs(F(metrica_field))),
        default=F(metrica_field),
        output_field=FloatField(),
    )


def espressione_totale_spese():
    """Somma campi spese di testata (valore grezzo, senza segno NC)."""
    expr = Value(0.0, output_field=FloatField())
    for campo in CAMPI_SPESE:
        expr = expr + Coalesce(F(campo), Value(0.0))
    return expr


def totale_spese_positive():
    """Totale spese sempre positivo (anche sulle note di credito)."""
    return Abs(espressione_totale_spese())


def importo_netto_con_segno(metrica_field: str):
    """
    Metrica al netto delle spese.
    Le spese restano sempre positive; il netto è lordo_con_segno − spese.
    Così in aggregato: somma(lordo) − somma(spese) = somma(netto).
    """
    return importo_con_segno(metrica_field) - totale_spese_positive()


def sum_fatturato(metrica_field: str):
    """Somma fatturato senza spese (usata in confronti, grafici, clienti)."""
    return Coalesce(Sum(importo_netto_con_segno(metrica_field)), Value(0.0))


def sum_lordo(metrica_field: str):
    return Coalesce(Sum(importo_con_segno(metrica_field)), Value(0.0))


def sum_spese():
    """Somma spese: sempre positiva, anche per le TD04."""
    return Coalesce(Sum(totale_spese_positive()), Value(0.0))


def filtro_clienti_reali(qs):
    """Esclude fatture di clienti con Cliente_Fittizio = true."""
    codici_fittizi = Cliente.objects.filter(cliente_fittizio=True).values("codice")
    return qs.exclude(cliente__in=codici_fittizi)


def base_queryset(
    *,
    alfa: str = "",
    note_credito: str = "",
    cliente: str = "",
    iso: str = "",
    escludi_fittizi: bool = True,
):
    qs = Fattura.objects.all()
    if escludi_fittizi:
        qs = filtro_clienti_reali(qs)
    if alfa:
        qs = qs.filter(alfa__iexact=alfa.strip())
    if cliente:
        qs = qs.filter(cliente__iexact=cliente.strip())
    if iso:
        qs = filtro_iso_nazione(qs, iso)
    return filtro_note_credito(qs, note_credito)


def filtro_periodo(qs, data_da: date | None, data_a: date | None):
    """Filtra su DataFattura come data calendario 4D (senza shift timezone)."""
    if data_da or data_a:
        qs = qs.annotate(_data_fattura_cal=Cast("data_fattura", DateField()))
    if data_da:
        qs = qs.filter(_data_fattura_cal__gte=data_da)
    if data_a:
        qs = qs.filter(_data_fattura_cal__lte=data_a)
    return qs


def kpi_periodo(qs, metrica_field: str) -> PeriodoKPI:
    agg = qs.aggregate(
        fatturato=sum_fatturato(metrica_field),
        lordo=sum_lordo(metrica_field),
        spese=sum_spese(),
        n_fatture=Count("id_testa"),
        n_clienti=Count("cliente", distinct=True),
    )
    fatturato = float(agg["fatturato"] or 0)
    lordo = float(agg["lordo"] or 0)
    spese = float(agg["spese"] or 0)
    n_fatture = int(agg["n_fatture"] or 0)
    n_clienti = int(agg["n_clienti"] or 0)
    return PeriodoKPI(
        fatturato=fatturato,
        lordo=lordo,
        spese=spese,
        n_fatture=n_fatture,
        n_clienti=n_clienti,
        ticket_medio=(fatturato / n_fatture) if n_fatture else 0.0,
        media_cliente=(fatturato / n_clienti) if n_clienti else 0.0,
    )


def delta_pct(attuale: float, precedente: float) -> float | None:
    if precedente == 0:
        return None if attuale == 0 else 100.0
    return ((attuale - precedente) / precedente) * 100.0


def serie_mensile(qs, metrica_field: str) -> list[dict]:
    rows = (
        qs.annotate(mese=TruncMonth("data_fattura"))
        .values("mese")
        .annotate(
            fatturato=sum_fatturato(metrica_field),
            n_fatture=Count("id_testa"),
            n_clienti=Count("cliente", distinct=True),
        )
        .order_by("mese")
    )
    out = []
    for row in rows:
        mese = row["mese"]
        if not mese:
            continue
        out.append(
            {
                "mese": mese.date() if hasattr(mese, "date") else mese,
                "label": f"{MESI_IT[mese.month]} {mese.year}",
                "month": mese.month,
                "year": mese.year,
                "fatturato": float(row["fatturato"] or 0),
                "n_fatture": int(row["n_fatture"] or 0),
                "n_clienti": int(row["n_clienti"] or 0),
            }
        )
    return out


def serie_mensile_per_mese(qs, metrica_field: str) -> dict[int, float]:
    """Totale per mese dell'anno (1-12), utile per confronto YoY."""
    rows = (
        qs.annotate(m=ExtractMonth("data_fattura"))
        .values("m")
        .annotate(fatturato=sum_fatturato(metrica_field))
    )
    return {int(r["m"]): float(r["fatturato"] or 0) for r in rows if r["m"]}


def andamento_annuale(qs, metrica_field: str) -> list[dict]:
    rows = (
        qs.annotate(anno=ExtractYear("data_fattura"))
        .values("anno")
        .annotate(
            fatturato=sum_fatturato(metrica_field),
            n_fatture=Count("id_testa"),
            n_clienti=Count("cliente", distinct=True),
        )
        .order_by("anno")
    )
    return [
        {
            "anno": int(r["anno"]),
            "fatturato": float(r["fatturato"] or 0),
            "n_fatture": int(r["n_fatture"] or 0),
            "n_clienti": int(r["n_clienti"] or 0),
        }
        for r in rows
        if r["anno"]
    ]


def risolvi_cliente(query: str) -> tuple[Cliente | None, list[Cliente]]:
    """
    Risolve un filtro cliente: codice esatto, oppure ricerca per codice/ragione sociale/P.IVA.
    Se un solo risultato nella ricerca, lo seleziona automaticamente.
    """
    query = (query or "").strip()
    if not query:
        return None, []

    exact = Cliente.objects.filter(codice__iexact=query).first()
    if exact:
        return exact, []

    matches = list(
        Cliente.objects.filter(
            Q(codice__icontains=query)
            | Q(ragione_sociale1__icontains=query)
            | Q(ragione_sociale2__icontains=query)
            | Q(partita_iva__icontains=query)
        ).order_by("ragione_sociale1", "codice")[:20]
    )
    if len(matches) == 1:
        return matches[0], []
    return None, matches


def info_geo_cliente(cliente: Cliente) -> dict:
    """Provincia/regione del cliente dalla tabella geografia (se mappabile)."""
    from apps.geografia.models import Provincia

    sigla = (cliente.provincia or "").strip().upper()
    override = SIGLE_PROVINCIA_REGIONE_OVERRIDE.get(sigla)
    provincia = Provincia.objects.filter(sigla=sigla).select_related("regione").first()
    if provincia:
        return {
            "sigla": provincia.sigla,
            "provincia_nome": provincia.nome,
            "regione_codice": provincia.regione_id,
            "regione_nome": provincia.regione.nome,
        }
    if override:
        from apps.geografia.models import Regione

        regione = Regione.objects.filter(pk=override).first()
        return {
            "sigla": sigla,
            "provincia_nome": sigla,
            "regione_codice": override,
            "regione_nome": regione.nome if regione else override,
        }
    return {
        "sigla": sigla or "",
        "provincia_nome": "",
        "regione_codice": "",
        "regione_nome": "",
    }


def clienti_fatturati(qs, metrica_field: str) -> dict[str, dict]:
    """codice -> {fatturato, n_fatture, ultima}."""
    rows = (
        qs.exclude(cliente__isnull=True)
        .exclude(cliente="")
        .values("cliente")
        .annotate(
            fatturato=sum_fatturato(metrica_field),
            n_fatture=Count("id_testa"),
            ultima=Max("data_fattura"),
        )
    )
    return {
        str(r["cliente"]).strip(): {
            "codice": str(r["cliente"]).strip(),
            "fatturato": float(r["fatturato"] or 0),
            "n_fatture": int(r["n_fatture"] or 0),
            "ultima": r["ultima"],
        }
        for r in rows
        if r["cliente"] and str(r["cliente"]).strip()
    }


def arricchisci_clienti(
    codici_map: dict[str, dict], *, sort_key: str = "fatturato"
) -> list[dict]:
    if not codici_map:
        return []
    clienti = Cliente.objects.filter(codice__in=list(codici_map.keys())).only(
        "codice",
        "ragione_sociale1",
        "ragione_sociale2",
        "localita",
        "provincia",
    )
    anagrafica = {
        c.codice: {
            "ragione_sociale": " ".join(
                p for p in (c.ragione_sociale1 or "", c.ragione_sociale2 or "") if p
            ).strip(),
            "localita": (c.localita or "").strip(),
            "provincia": (c.provincia or "").strip().upper(),
        }
        for c in clienti
    }
    out = []
    for codice, data in codici_map.items():
        item = dict(data)
        info = anagrafica.get(codice) or {}
        item["ragione_sociale"] = info.get("ragione_sociale") or ""
        item["localita"] = info.get("localita") or ""
        item["provincia"] = info.get("provincia") or ""
        out.append(item)
    out.sort(key=lambda x: (-abs(float(x.get(sort_key) or 0)), x["codice"]))
    return out


def classifica_clienti(
    qs, metrica_field: str, *, top_n: int | None = None
) -> dict:
    """
    Classifica clienti migliori per fatturato (senza spese) nel queryset periodo.
    Aggiunge posizione, % sul totale e % cumulata (Pareto).
    """
    mappa = clienti_fatturati(qs, metrica_field)
    rows = arricchisci_clienti(mappa, sort_key="fatturato")
    totale = sum(float(r.get("fatturato") or 0) for r in rows)
    cumulato = 0.0
    classifica = []
    for i, row in enumerate(rows, start=1):
        fatt = float(row.get("fatturato") or 0)
        cumulato += fatt
        pct = (fatt / totale * 100.0) if totale else 0.0
        pct_cum = (cumulato / totale * 100.0) if totale else 0.0
        classifica.append(
            {
                **row,
                "posizione": i,
                "percentuale": pct,
                "percentuale_cumulata": pct_cum,
            }
        )

    limitati = classifica[:top_n] if top_n else classifica
    top10 = classifica[:10]
    top20 = classifica[:20]
    fatt_top10 = sum(r["fatturato"] for r in top10)
    fatt_top20 = sum(r["fatturato"] for r in top20)

    return {
        "classifica": limitati,
        "classifica_completa": classifica,
        "n_clienti": len(classifica),
        "totale": totale,
        "top1_fatturato": classifica[0]["fatturato"] if classifica else 0.0,
        "top1_percentuale": classifica[0]["percentuale"] if classifica else 0.0,
        "top10_fatturato": fatt_top10,
        "top10_percentuale": (fatt_top10 / totale * 100.0) if totale else 0.0,
        "top20_fatturato": fatt_top20,
        "top20_percentuale": (fatt_top20 / totale * 100.0) if totale else 0.0,
    }


def confronto_clienti(
    map_rif: dict[str, dict], map_con: dict[str, dict]
) -> dict[str, list[dict]]:
    set_rif = set(map_rif)
    set_con = set(map_con)
    solo_rif = {c: map_rif[c] for c in set_rif - set_con}
    solo_con = {c: map_con[c] for c in set_con - set_rif}
    entrambi = {}
    for c in set_rif & set_con:
        entrambi[c] = {
            "codice": c,
            "fatturato_rif": map_rif[c]["fatturato"],
            "fatturato_con": map_con[c]["fatturato"],
            "n_fatture_rif": map_rif[c]["n_fatture"],
            "n_fatture_con": map_con[c]["n_fatture"],
            "delta": map_rif[c]["fatturato"] - map_con[c]["fatturato"],
            "ultima_rif": map_rif[c]["ultima"],
            "ultima_con": map_con[c]["ultima"],
        }
    return {
        # Tutti i clienti che compongono il fatturato del periodo di riferimento
        "periodo": arricchisci_clienti(map_rif),
        # Comprarono nel confronto, assenti nel riferimento = persi
        "persi": arricchisci_clienti(solo_con),
        # Nel riferimento ma non nel confronto = nuovi / solo riferimento
        "nuovi": arricchisci_clienti(solo_rif),
        "entrambi": arricchisci_clienti(entrambi, sort_key="delta"),
    }


def default_periodi(oggi: date | None = None) -> tuple[date, date, date, date]:
    """Anno precedente completo vs anno ancora precedente (es. 2025 vs 2024)."""
    oggi = oggi or date.today()
    if oggi.month >= 7:
        rif_da = date(oggi.year, 1, 1)
        rif_a = oggi
        con_da = date(oggi.year - 1, 1, 1)
        try:
            con_a = date(oggi.year - 1, oggi.month, oggi.day)
        except ValueError:
            con_a = date(oggi.year - 1, oggi.month, 28)
        return rif_da, rif_a, con_da, con_a
    anno_rif = oggi.year - 1
    return (
        date(anno_rif, 1, 1),
        date(anno_rif, 12, 31),
        date(anno_rif - 1, 1, 1),
        date(anno_rif - 1, 12, 31),
    )


def periodi_anno(anno: int) -> tuple[date, date]:
    return date(anno, 1, 1), date(anno, 12, 31)


def format_euro(value: float | Decimal | None) -> str:
    v = float(value or 0)
    return f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


# Sigle provinciali obsolete / soppresse → codice ISTAT regione
SIGLE_PROVINCIA_REGIONE_OVERRIDE: dict[str, str] = {
    "OT": "20",  # Olbia-Tempio → Sardegna
    "OG": "20",  # Ogliastra → Sardegna
    "CI": "20",  # Carbonia-Iglesias → Sardegna
    "VS": "20",  # Medio Campidano → Sardegna
    "FO": "08",  # Forlì (vecchia) → Emilia-Romagna
    "PS": "11",  # Pesaro (vecchia) → Marche
}


def mappa_sigla_regione() -> dict[str, str]:
    """Sigla provincia (UPPER) → codice ISTAT regione."""
    from apps.geografia.models import Provincia

    mapping = {
        str(sigla).strip().upper(): str(regione_id)
        for sigla, regione_id in Provincia.objects.values_list("sigla", "regione_id")
    }
    mapping.update(SIGLE_PROVINCIA_REGIONE_OVERRIDE)
    return mapping


def mappa_cliente_regione_it() -> dict[str, str]:
    """
    Codice cliente IT → codice regione, via Provincia del cliente.
    Solo clienti con CodNazione = IT e provincia riconoscibile.
    """
    from django.db.models import CharField
    from django.db.models.functions import Trim, Upper

    sigla_to_reg = mappa_sigla_regione()
    rows = (
        Cliente.objects.filter(cod_nazione__iexact="IT")
        .annotate(
            prov=Upper(
                Trim(
                    Coalesce(
                        "provincia",
                        Value("", output_field=CharField()),
                    )
                ),
                output_field=CharField(),
            )
        )
        .values_list("codice", "prov")
    )
    out: dict[str, str] = {}
    for codice, prov in rows.iterator(chunk_size=2000):
        if not codice:
            continue
        reg = sigla_to_reg.get((prov or "").strip())
        if reg:
            out[str(codice).strip()] = reg
    return out


def fatturato_per_regione(qs, metrica_field: str) -> dict:
    """
    Fatturato (senza spese) per regione italiana.

    Considera solo clienti con CodNazione = IT la cui Provincia
    corrisponde a una Provincia (o alias) collegata a una Regione.
    """
    from apps.geografia.models import Regione

    codice_to_reg = mappa_cliente_regione_it()
    qs_it = qs.filter(
        cliente__in=Cliente.objects.filter(cod_nazione__iexact="IT").values("codice")
    )
    per_cliente = clienti_fatturati(qs_it, metrica_field)

    by_reg: dict[str, dict] = {}
    fatturato_mappato = 0.0
    fatturato_non_mappato = 0.0
    n_clienti_mappati = 0
    n_clienti_non_mappati = 0
    n_fatture_mappate = 0
    n_fatture_non_mappate = 0

    for codice, info in per_cliente.items():
        fatt = float(info.get("fatturato") or 0)
        n_fat = int(info.get("n_fatture") or 0)
        reg = codice_to_reg.get(codice)
        if not reg:
            fatturato_non_mappato += fatt
            n_clienti_non_mappati += 1
            n_fatture_non_mappate += n_fat
            continue
        bucket = by_reg.setdefault(
            reg,
            {"fatturato": 0.0, "n_fatture": 0, "n_clienti": 0},
        )
        bucket["fatturato"] += fatt
        bucket["n_fatture"] += n_fat
        bucket["n_clienti"] += 1
        fatturato_mappato += fatt
        n_clienti_mappati += 1
        n_fatture_mappate += n_fat

    totale_it = fatturato_mappato + fatturato_non_mappato
    regioni_db = {r.codice: r.nome for r in Regione.objects.all()}
    rows = []
    for codice, nome in sorted(regioni_db.items(), key=lambda x: x[1].casefold()):
        data = by_reg.get(codice, {"fatturato": 0.0, "n_fatture": 0, "n_clienti": 0})
        fatt = float(data["fatturato"])
        pct = (fatt / fatturato_mappato * 100.0) if fatturato_mappato else 0.0
        rows.append(
            {
                "codice": codice,
                "nome": nome,
                "fatturato": fatt,
                "percentuale": pct,
                "n_fatture": int(data["n_fatture"]),
                "n_clienti": int(data["n_clienti"]),
            }
        )
    rows.sort(key=lambda r: r["fatturato"], reverse=True)

    return {
        "regioni": rows,
        "totale_mappato": fatturato_mappato,
        "totale_non_mappato": fatturato_non_mappato,
        "totale_italia": totale_it,
        "n_clienti_mappati": n_clienti_mappati,
        "n_clienti_non_mappati": n_clienti_non_mappati,
        "n_fatture_mappate": n_fatture_mappate,
        "n_fatture_non_mappate": n_fatture_non_mappate,
        "map_data": {
            r["codice"]: {
                "nome": r["nome"],
                "fatturato": round(r["fatturato"], 2),
                "percentuale": round(r["percentuale"], 2),
                "n_fatture": r["n_fatture"],
                "n_clienti": r["n_clienti"],
            }
            for r in rows
        },
    }


def mappa_cliente_provincia_it() -> dict[str, dict]:
    """
    Codice cliente IT → {sigla, regione_codice} via Provincia.
    Solo clienti con CodNazione = IT e provincia riconoscibile.
    """
    from django.db.models import CharField
    from django.db.models.functions import Trim, Upper

    sigla_to_reg = mappa_sigla_regione()
    rows = (
        Cliente.objects.filter(cod_nazione__iexact="IT")
        .annotate(
            prov=Upper(
                Trim(
                    Coalesce(
                        "provincia",
                        Value("", output_field=CharField()),
                    )
                ),
                output_field=CharField(),
            )
        )
        .values_list("codice", "prov")
    )
    out: dict[str, dict] = {}
    for codice, prov in rows.iterator(chunk_size=2000):
        if not codice:
            continue
        sigla = (prov or "").strip().upper()
        reg = sigla_to_reg.get(sigla)
        if reg:
            out[str(codice).strip()] = {"sigla": sigla, "regione": reg}
    return out


def serialize_liste_clienti(lists: dict[str, list[dict]]) -> dict[str, list[dict]]:
    """Serializza le liste clienti per drill-down JS (senza refresh)."""

    def _ultima(v):
        if hasattr(v, "isoformat"):
            return v.isoformat()
        return v

    out: dict[str, list[dict]] = {}
    for key, rows in lists.items():
        serialized = []
        for c in rows:
            if key == "entrambi":
                serialized.append(
                    {
                        "codice": c["codice"],
                        "ragione_sociale": c.get("ragione_sociale") or "",
                        "localita": c.get("localita") or "",
                        "provincia": c.get("provincia") or "",
                        "fatturato_rif": round(float(c.get("fatturato_rif") or 0), 2),
                        "fatturato_con": round(float(c.get("fatturato_con") or 0), 2),
                        "delta": round(float(c.get("delta") or 0), 2),
                    }
                )
            else:
                serialized.append(
                    {
                        "codice": c["codice"],
                        "ragione_sociale": c.get("ragione_sociale") or "",
                        "localita": c.get("localita") or "",
                        "provincia": c.get("provincia") or "",
                        "fatturato": round(float(c.get("fatturato") or 0), 2),
                        "n_fatture": int(c.get("n_fatture") or 0),
                        "ultima": _ultima(c.get("ultima")),
                    }
                )
        out[key] = serialized
    return out


def clienti_by_provincia_sigla(clienti_rows: list[dict]) -> dict[str, list[dict]]:
    """
    Raggruppa clienti fatturati (periodo riferimento) per sigla provincia IT.
    Usato per drill-down mappa/tabella geografica.
    """
    codice_to_prov = mappa_cliente_provincia_it()
    by_prov: dict[str, list[dict]] = {}
    for c in clienti_rows:
        geo = codice_to_prov.get(c.get("codice") or "")
        if not geo:
            continue
        sigla = geo["sigla"]
        ultima = c.get("ultima")
        if hasattr(ultima, "isoformat"):
            ultima = ultima.isoformat()
        elif ultima is not None:
            ultima = str(ultima)
        by_prov.setdefault(sigla, []).append(
            {
                "codice": c["codice"],
                "ragione_sociale": c.get("ragione_sociale") or "",
                "fatturato": round(float(c.get("fatturato") or 0), 2),
                "n_fatture": int(c.get("n_fatture") or 0),
                "ultima": ultima,
            }
        )
    for rows in by_prov.values():
        rows.sort(key=lambda r: (-float(r["fatturato"]), r["codice"]))
    return by_prov


def filtro_clienti_per_provincia(
    rows: list[dict], provincia: str, codice_to_prov: dict[str, dict] | None = None
) -> list[dict]:
    """Filtra lista clienti sulla sigla provincia (IT)."""
    sigla = (provincia or "").strip().upper()
    if not sigla:
        return rows
    if codice_to_prov is None:
        codice_to_prov = mappa_cliente_provincia_it()
    out = []
    for r in rows:
        geo = codice_to_prov.get(r.get("codice") or "")
        if geo and geo["sigla"] == sigla:
            out.append(r)
    return out


def filtro_clienti_per_nazione(
    rows: list[dict], nazione: str, codice_to_iso: dict[str, str] | None = None
) -> list[dict]:
    """Filtra lista clienti sul codice ISO nazione."""
    iso = iso_canonico(nazione)
    if not iso:
        return rows
    if codice_to_iso is None:
        codice_to_iso = mappa_cliente_nazione()
    out = []
    for r in rows:
        if codice_to_iso.get(r.get("codice") or "") == iso:
            out.append(r)
    return out


def fatturato_per_provincia(qs, metrica_field: str) -> dict:
    """
    Fatturato (senza spese) per provincia italiana.
    Percentuali nel dettaglio regione = quota sul totale della regione.
    """
    from apps.geografia.models import Provincia, Regione

    codice_to_prov = mappa_cliente_provincia_it()
    qs_it = qs.filter(
        cliente__in=Cliente.objects.filter(cod_nazione__iexact="IT").values("codice")
    )
    per_cliente = clienti_fatturati(qs_it, metrica_field)

    by_prov: dict[str, dict] = {}
    for codice, info in per_cliente.items():
        geo = codice_to_prov.get(codice)
        if not geo:
            continue
        sigla = geo["sigla"]
        fatt = float(info.get("fatturato") or 0)
        n_fat = int(info.get("n_fatture") or 0)
        bucket = by_prov.setdefault(
            sigla,
            {
                "fatturato": 0.0,
                "n_fatture": 0,
                "n_clienti": 0,
                "regione": geo["regione"],
            },
        )
        bucket["fatturato"] += fatt
        bucket["n_fatture"] += n_fat
        bucket["n_clienti"] += 1

    regioni_db = {r.codice: r.nome for r in Regione.objects.all()}
    province_db = {
        p.sigla: {"nome": p.nome, "regione": p.regione_id}
        for p in Provincia.objects.all()
    }
    # Sigle override non più in anagrafica province
    for sigla, reg in SIGLE_PROVINCIA_REGIONE_OVERRIDE.items():
        province_db.setdefault(sigla, {"nome": sigla, "regione": reg})

    by_regione: dict[str, list] = {cod: [] for cod in regioni_db}
    totale_reg: dict[str, float] = {cod: 0.0 for cod in regioni_db}

    for sigla, meta in province_db.items():
        reg = meta["regione"]
        data = by_prov.get(
            sigla,
            {"fatturato": 0.0, "n_fatture": 0, "n_clienti": 0, "regione": reg},
        )
        totale_reg[reg] = totale_reg.get(reg, 0.0) + float(data["fatturato"])

    all_rows = []
    for sigla, meta in sorted(province_db.items(), key=lambda x: x[1]["nome"].casefold()):
        reg = meta["regione"]
        data = by_prov.get(
            sigla,
            {"fatturato": 0.0, "n_fatture": 0, "n_clienti": 0, "regione": reg},
        )
        fatt = float(data["fatturato"])
        tot_r = float(totale_reg.get(reg) or 0)
        pct = (fatt / tot_r * 100.0) if tot_r else 0.0
        row = {
            "sigla": sigla,
            "nome": meta["nome"],
            "regione_codice": reg,
            "regione_nome": regioni_db.get(reg, reg),
            "fatturato": fatt,
            "percentuale": pct,
            "n_fatture": int(data["n_fatture"]),
            "n_clienti": int(data["n_clienti"]),
        }
        all_rows.append(row)
        by_regione.setdefault(reg, []).append(row)

    for cod in by_regione:
        by_regione[cod].sort(key=lambda r: r["fatturato"], reverse=True)

    all_rows.sort(key=lambda r: r["fatturato"], reverse=True)

    return {
        "province": all_rows,
        "by_regione": by_regione,
        "totale_per_regione": totale_reg,
    }


def _norm_iso(value: str | None) -> str:
    return (value or "").strip().upper()


# Alias frequenti 4D / UE → ISO 3166-1 alpha-2 usato nella cartina
ISO_CANONICO: dict[str, str] = {
    "EL": "GR",  # Grecia
    "UK": "GB",  # Regno Unito
}


def iso_canonico(value: str | None) -> str:
    iso = _norm_iso(value)
    if not iso:
        return ""
    return ISO_CANONICO.get(iso, iso)


def filtro_iso_nazione(qs, iso: str):
    """
    Filtra fatture di clienti con CodNazione uguale all'ISO richiesto
    (accetta alias tipo EL→GR, UK→GB).
    """
    target = iso_canonico(iso)
    if not target:
        return qs
    raw_codes = {target}
    for alias, canon in ISO_CANONICO.items():
        if canon == target:
            raw_codes.add(alias)
    q_nazione = Q()
    for code in raw_codes:
        q_nazione |= Q(cod_nazione__iexact=code)
    return qs.filter(cliente__in=Cliente.objects.filter(q_nazione).values("codice"))


def mappa_cliente_nazione() -> dict[str, str]:
    """Codice cliente → CodNazione canonico (UPPER). Vuoto se assente."""
    out: dict[str, str] = {}
    rows = Cliente.objects.values_list("codice", "cod_nazione")
    for codice, nazione in rows.iterator(chunk_size=2000):
        if not codice:
            continue
        out[str(codice).strip()] = iso_canonico(nazione)
    return out


@lru_cache(maxsize=1)
def nomi_nazioni_da_geojson() -> dict[str, str]:
    """ISO A2 → nome nazione dal GeoJSON mondo."""
    import json
    from pathlib import Path

    from django.conf import settings

    path = (
        Path(settings.BASE_DIR)
        / "static"
        / "eureka"
        / "geo"
        / "world_countries.simple.geojson"
    )
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    out: dict[str, str] = {}
    for feat in data.get("features") or []:
        props = feat.get("properties") or {}
        iso = _norm_iso(props.get("iso"))
        nome = (props.get("name") or "").strip()
        if iso and nome:
            out[iso] = nome
    return out


def fatturato_per_nazione(
    qs, metrica_field: str, *, solo_estero: bool = False
) -> dict:
    """
    Fatturato (senza spese) per codice ISO nazione.
    Esclude ISO vuoti. Con solo_estero=True esclude anche IT.
    """
    codice_to_iso = mappa_cliente_nazione()
    nomi = nomi_nazioni_da_geojson()
    per_cliente = clienti_fatturati(qs, metrica_field)

    by_iso: dict[str, dict] = {}
    totale = 0.0
    n_clienti = 0
    n_fatture = 0

    for codice, info in per_cliente.items():
        iso = codice_to_iso.get(codice, "")
        if not iso:
            continue
        if solo_estero and iso == "IT":
            continue
        fatt = float(info.get("fatturato") or 0)
        n_fat = int(info.get("n_fatture") or 0)
        bucket = by_iso.setdefault(
            iso,
            {"fatturato": 0.0, "n_fatture": 0, "n_clienti": 0},
        )
        bucket["fatturato"] += fatt
        bucket["n_fatture"] += n_fat
        bucket["n_clienti"] += 1
        totale += fatt
        n_clienti += 1
        n_fatture += n_fat

    rows = []
    for iso, data in by_iso.items():
        fatt = float(data["fatturato"])
        pct = (fatt / totale * 100.0) if totale else 0.0
        rows.append(
            {
                "codice": iso,
                "nome": nomi.get(iso) or iso,
                "fatturato": fatt,
                "percentuale": pct,
                "n_fatture": int(data["n_fatture"]),
                "n_clienti": int(data["n_clienti"]),
            }
        )
    rows.sort(key=lambda r: r["fatturato"], reverse=True)

    return {
        "nazioni": rows,
        "totale": totale,
        "n_clienti": n_clienti,
        "n_fatture": n_fatture,
        "n_nazioni": len(rows),
        "map_data": {
            r["codice"]: {
                "nome": r["nome"],
                "fatturato": round(r["fatturato"], 2),
                "percentuale": round(r["percentuale"], 2),
                "n_fatture": r["n_fatture"],
                "n_clienti": r["n_clienti"],
            }
            for r in rows
        },
    }


def fatturato_per_nazione_estero(qs, metrica_field: str) -> dict:
    """Alias: solo nazioni con ISO ≠ IT."""
    data = fatturato_per_nazione(qs, metrica_field, solo_estero=True)
    data["totale_estero"] = data["totale"]
    return data


def fatturato_clienti_iso_mancante(qs, metrica_field: str) -> dict:
    """
    Clienti fatturati nel periodo con CodNazione vuoto/null → errori da correggere.
    """
    codice_to_iso = mappa_cliente_nazione()
    per_cliente = clienti_fatturati(qs, metrica_field)
    filtered: dict[str, dict] = {}
    for codice, info in per_cliente.items():
        iso = codice_to_iso.get(codice, "")
        if not iso:
            filtered[codice] = info

    rows = arricchisci_clienti(filtered, sort_key="fatturato")
    for row in rows:
        row["errore"] = "Codice ISO nazione mancante"
        row["cod_nazione"] = ""
    totale = sum(float(r.get("fatturato") or 0) for r in rows)
    return {
        "clienti": rows,
        "n_clienti": len(rows),
        "n_fatture": sum(int(r.get("n_fatture") or 0) for r in rows),
        "totale": totale,
    }


SORT_FIELDS_PERSI_NUOVI = ("cliente", "codice", "fatturato", "n_fatture", "ultima")
SORT_FIELDS_ENTRAMBI = (
    "cliente",
    "codice",
    "fatturato_rif",
    "fatturato_con",
    "delta",
    "n_fatture_rif",
    "n_fatture_con",
)

FATTURATO_OPS: dict[str, str] = {
    "": "Tutti",
    "gt": "Maggiore di",
    "gte": "Maggiore o uguale a",
    "lt": "Minore di",
    "lte": "Minore o uguale a",
    "eq": "Uguale a",
    "between": "Compreso tra",
}


def parse_importo(value: str | None) -> float | None:
    """Accetta 1234.56, 1234,56 oppure 1.234,56."""
    s = (value or "").strip().replace(" ", "").replace("€", "")
    if not s:
        return None
    if "," in s and "." in s:
        s = s.replace(".", "").replace(",", ".")
    elif "," in s:
        s = s.replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def filtro_clienti_per_fatturato(
    rows: list[dict],
    *,
    op: str,
    val: float | None,
    val2: float | None = None,
    field: str = "fatturato",
) -> list[dict]:
    """Filtra righe clienti per formula sul fatturato."""
    op = (op or "").strip().lower()
    if op not in FATTURATO_OPS or not op:
        return rows
    if val is None:
        return rows
    if op == "between":
        if val2 is None:
            return rows
        lo, hi = (val, val2) if val <= val2 else (val2, val)

        def ok(row: dict) -> bool:
            v = float(row.get(field) or 0)
            return lo <= v <= hi

    elif op == "gt":

        def ok(row: dict) -> bool:
            return float(row.get(field) or 0) > val

    elif op == "gte":

        def ok(row: dict) -> bool:
            return float(row.get(field) or 0) >= val

    elif op == "lt":

        def ok(row: dict) -> bool:
            return float(row.get(field) or 0) < val

    elif op == "lte":

        def ok(row: dict) -> bool:
            return float(row.get(field) or 0) <= val

    elif op == "eq":

        def ok(row: dict) -> bool:
            return abs(float(row.get(field) or 0) - val) < 0.005

    else:
        return rows

    return [r for r in rows if ok(r)]


def sort_clienti_rows(
    rows: list[dict],
    *,
    sort: str,
    direction: str,
    allowed: tuple[str, ...],
    default_sort: str = "fatturato",
    default_dir: str = "desc",
) -> list[dict]:
    """Ordina le liste clienti dell'analisi (in memoria, dopo il confronto)."""
    if sort not in allowed:
        sort = default_sort if default_sort in allowed else allowed[0]
    reverse = (direction or default_dir).lower() != "asc"

    def sort_key(row: dict):
        if sort == "cliente":
            return (row.get("ragione_sociale") or row.get("codice") or "").casefold()
        if sort == "codice":
            return (row.get("codice") or "").casefold()
        if sort == "ultima":
            val = row.get("ultima")
            # None in fondo sia in asc che in desc
            if val is None:
                return (1, None) if not reverse else (1, None)
            return (0, val)
        val = row.get(sort)
        if val is None:
            return 0
        return val

    if sort == "ultima":
        # Con reverse=True vogliamo date più recenti prima; None sempre in fondo
        present = [r for r in rows if r.get("ultima") is not None]
        missing = [r for r in rows if r.get("ultima") is None]
        present.sort(key=lambda r: r["ultima"], reverse=reverse)
        return present + missing

    return sorted(rows, key=sort_key, reverse=reverse)