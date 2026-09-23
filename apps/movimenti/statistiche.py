"""Statistiche movimenti magazzino (elaborazione stile 4D)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from itertools import groupby

from django.db import connection
from django.db.models import DateField
from django.db.models.functions import Cast
from django.utils.dateparse import parse_date

from apps.causali_magazzino.models import CausaleMagazzino
from apps.movimenti.models import MovimentoT, MovimentoTDettaglio


LAYOUT_FLAT = "flat"
LAYOUT_TESTATA_DETTAGLIO = "testata_dettaglio"


_DIM_HEADER_LINK: dict[str, str] = {
    "articolo": "articolo",
    "cliente": "cliente",
    "zona": "zona",
    "agente": "agente",
    "categoria": "categoria",
    "fornitore": "fornitore",
    "gruppo_cli": "gruppo_cli",
}


def _apply_articoli_dettaglio_layout(
    tipi: tuple[dict[str, object], ...],
) -> tuple[dict[str, object], ...]:
    """
    Layout testata + dettaglio per tipologiche multi-dimensione:
    - dimensioni precedenti → testata (annidate se >1)
    - ultima dimensione → righe dettaglio
    """
    out: list[dict[str, object]] = []
    for raw in tipi:
        spec = dict(raw)
        dims = tuple(spec.get("dims") or ())
        if len(dims) >= 2:
            last = str(dims[-1])
            first = str(dims[0])
            spec["layout"] = LAYOUT_TESTATA_DETTAGLIO
            spec.setdefault("detail_link", _DIM_HEADER_LINK.get(last, last))
            spec.setdefault("header_link", _DIM_HEADER_LINK.get(first, first))
        out.append(spec)
    return tuple(out)


# Tipi statistica come combo 4D «Statistiche (Movimenti Magazzino)».
_STATISTICHE_TIPI_RAW: tuple[dict[str, object], ...] = (
    {"key": "articoli", "label": "Articoli di Magazzino", "dims": ("articolo",)},
    {"key": "clienti", "label": "Clienti", "dims": ("cliente",)},
    {"key": "zone", "label": "Zone", "dims": ("zona",)},
    {"key": "agenti", "label": "Agenti", "dims": ("agente",)},
    {"key": "categorie", "label": "Categorie Merceologiche", "dims": ("categoria",)},
    {
        "key": "cliente_articolo",
        "label": "Cliente/Articolo (dettaglio)",
        "dims": ("cliente", "articolo"),
    },
    {"key": "zone_articoli", "label": "Zone/Articoli", "dims": ("zona", "articolo")},
    {"key": "agenti_articoli", "label": "Agenti/Articoli", "dims": ("agente", "articolo")},
    {
        "key": "categorie_articoli",
        "label": "Cat. Merceologiche/Articoli",
        "dims": ("categoria", "articolo"),
    },
    {"key": "articoli_cliente", "label": "Articoli/Cliente", "dims": ("articolo", "cliente")},
    {"key": "temporali", "label": "Temporali", "dims": ("periodo",)},
    {
        "key": "fornitore_articolo",
        "label": "Fornitore/Articolo (dettaglio)",
        "dims": ("fornitore", "articolo"),
    },
    {"key": "agenti_clienti", "label": "Agenti/Clienti", "dims": ("agente", "cliente")},
    {"key": "zone_clienti", "label": "Zone/Clienti", "dims": ("zona", "cliente")},
    {
        "key": "zone_clienti_articoli",
        "label": "Zone/Clienti/Articoli",
        "dims": ("zona", "cliente", "articolo"),
    },
    {
        "key": "ricarico_zone_clienti_articoli",
        "label": "Ricarico Zone/Clienti/Articoli",
        "dims": ("zona", "cliente", "articolo"),
        "ricarico": True,
    },
    {
        "key": "agenti_zone_articoli",
        "label": "Agenti/Zone/Articoli",
        "dims": ("agente", "zona", "articolo"),
    },
    {"key": "gruppo_clienti", "label": "Gruppo Clienti (dettaglio)", "dims": ("gruppo_cli",)},
    {
        "key": "agenti_zone_clienti",
        "label": "Agenti/Zone/Clienti",
        "dims": ("agente", "zona", "cliente"),
    },
    {
        "key": "articoli_fornitori",
        "label": "Articoli/Fornitori",
        "dims": ("articolo", "fornitore"),
    },
    {"key": "magazzini", "label": "Magazzini", "dims": ("magazzino",)},
    {
        "key": "categorie_cliente",
        "label": "Categorie Merceologiche/Cliente (dettaglio)",
        "dims": ("categoria", "cliente"),
    },
    {
        "key": "cliente_categorie",
        "label": "Cliente/Categorie Merceologiche",
        "dims": ("cliente", "categoria"),
    },
)

STATISTICHE_TIPI = _apply_articoli_dettaglio_layout(_STATISTICHE_TIPI_RAW)
_STATISTICHE_TIPI_BY_KEY = {str(t["key"]): t for t in STATISTICHE_TIPI}
DEFAULT_STATISTICA_TIPO = "articoli"

_DIM_SQL: dict[str, dict[str, object]] = {
    "articolo": {
        "group": 'COALESCE(NULLIF(TRIM(d."CodiceArt"), \'\'), \'—\')',
        "code": 'COALESCE(NULLIF(TRIM(d."CodiceArt"), \'\'), \'—\')',
        "label": (
            'COALESCE(NULLIF(TRIM(MAX(d."Descrizione")), \'\'), '
            'NULLIF(TRIM(MAX(a."Descrizione")), \'\'), \'\')'
        ),
        "joins": ("articoli",),
    },
    "cliente": {
        "group": 'COALESCE(NULLIF(TRIM(t."Cliente"), \'\'), \'—\')',
        "code": 'COALESCE(NULLIF(TRIM(t."Cliente"), \'\'), \'—\')',
        "label": 'COALESCE(NULLIF(TRIM(MAX(c."RagioneSociale1")), \'\'), \'\')',
        "joins": ("clienti",),
    },
    "zona": {
        "group": 'COALESCE(NULLIF(TRIM(c."Zona"), \'\'), \'—\')',
        "code": 'COALESCE(NULLIF(TRIM(c."Zona"), \'\'), \'—\')',
        "label": 'COALESCE(NULLIF(TRIM(MAX(z."Descrizione")), \'\'), \'\')',
        "joins": ("clienti", "zone"),
    },
    "agente": {
        "group": 'COALESCE(NULLIF(TRIM(c."Agente"), \'\'), \'—\')',
        "code": 'COALESCE(NULLIF(TRIM(c."Agente"), \'\'), \'—\')',
        "label": 'COALESCE(NULLIF(TRIM(MAX(ag."RagioneSociale")), \'\'), \'\')',
        "joins": ("clienti", "agenti"),
    },
    "categoria": {
        "group": 'COALESCE(NULLIF(TRIM(a."CatOmogenea"), \'\'), \'—\')',
        "code": 'COALESCE(NULLIF(TRIM(a."CatOmogenea"), \'\'), \'—\')',
        "label": 'COALESCE(NULLIF(TRIM(MAX(cat."Descrizione")), \'\'), \'\')',
        "joins": ("articoli", "categorie"),
    },
    "fornitore": {
        "group": (
            'COALESCE(NULLIF(TRIM(t."Fornitore"), \'\'), '
            'NULLIF(TRIM(a."CodFornitore"), \'\'), \'—\')'
        ),
        "code": (
            'COALESCE(NULLIF(TRIM(t."Fornitore"), \'\'), '
            'NULLIF(TRIM(a."CodFornitore"), \'\'), \'—\')'
        ),
        "label": 'COALESCE(NULLIF(TRIM(MAX(f."RagioneSociale1")), \'\'), \'\')',
        "joins": ("articoli", "fornitori"),
    },
    "magazzino": {
        "group": (
            'COALESCE(NULLIF(TRIM(t."DepUscita"), \'\'), '
            'NULLIF(TRIM(t."DepEntrata"), \'\'), \'—\')'
        ),
        "code": (
            'COALESCE(NULLIF(TRIM(t."DepUscita"), \'\'), '
            'NULLIF(TRIM(t."DepEntrata"), \'\'), \'—\')'
        ),
        "label": 'COALESCE(NULLIF(TRIM(MAX(dep."Descrizione")), \'\'), \'\')',
        "joins": ("depositi",),
    },
    "periodo": {
        "group": "TO_CHAR(CAST(t.\"DataRegistraz\" AS date), 'YYYY-MM')",
        "code": "TO_CHAR(CAST(t.\"DataRegistraz\" AS date), 'YYYY-MM')",
        "label": "TO_CHAR(MAX(CAST(t.\"DataRegistraz\" AS date)), 'MM/YYYY')",
        "joins": (),
    },
    "gruppo_cli": {
        "group": 'COALESCE(NULLIF(TRIM(c."Gruppo"), \'\'), \'—\')',
        "code": 'COALESCE(NULLIF(TRIM(c."Gruppo"), \'\'), \'—\')',
        "label": 'COALESCE(NULLIF(TRIM(MAX(gcf."Descrizione")), \'\'), \'\')',
        "joins": ("clienti", "gruppi_clifor"),
    },
}


def resolve_statistica_tipo(key: str | None) -> dict[str, object]:
    text = (key or "").strip()
    return _STATISTICHE_TIPI_BY_KEY.get(text) or _STATISTICHE_TIPI_BY_KEY[DEFAULT_STATISTICA_TIPO]


def statistica_tipo_label(key: str | None) -> str:
    return str(resolve_statistica_tipo(key)["label"])


@dataclass(frozen=True)
class StatisticaRiga:
    codice: str
    descrizione: str
    quantita: float
    valore: float
    valore_un: float | None = None
    incidenza: float | None = None
    kind: str = "row"  # row | header | detail
    link_kind: str = ""  # articolo | cliente | …
    level: int = 0  # indentazione testate annidate / dettaglio

    @property
    def is_header(self) -> bool:
        return self.kind == "header"

    @property
    def is_detail(self) -> bool:
        return self.kind == "detail"

    @property
    def quantita_fmt(self) -> float:
        return self.quantita

    @property
    def valore_fmt(self) -> float:
        return self.valore


@dataclass(frozen=True)
class _RawStatRow:
    dims: tuple[tuple[str, str], ...]  # ((codice, label), …)
    quantita: float
    valore: float


def is_data_riga(row: StatisticaRiga) -> bool:
    """Righe che concorrono ai totali (esclude testate raggruppate)."""
    return row.kind != "header"


def finalize_righe_articoli(rows: list[StatisticaRiga]) -> list[StatisticaRiga]:
    """Calcola Val. Un. e % Incidenza come stampa 4D Articoli di Magazzino."""
    tot_val = sum(r.valore for r in rows if is_data_riga(r))
    out: list[StatisticaRiga] = []
    for r in rows:
        valore_un = None
        if r.quantita:
            valore_un = r.valore / r.quantita
        incidenza = (r.valore / tot_val * 100.0) if tot_val else 0.0
        out.append(
            StatisticaRiga(
                codice=r.codice,
                descrizione=r.descrizione,
                quantita=r.quantita,
                valore=r.valore,
                valore_un=valore_un,
                incidenza=incidenza,
                kind=r.kind,
                link_kind=r.link_kind,
                level=r.level,
            )
        )
    return out


def _layout_flat(
    raw_rows: list[_RawStatRow],
    *,
    dim_keys: tuple[str, ...] = (),
) -> list[StatisticaRiga]:
    rows: list[StatisticaRiga] = []
    single_link = ""
    if len(dim_keys) == 1:
        single_link = _DIM_HEADER_LINK.get(dim_keys[0], "")
    for raw in raw_rows:
        codice = raw.dims[0][0]
        labels = [lab for _cod, lab in raw.dims if lab and lab != "—"]
        extras = [
            f"{cod} {lab}".strip() if lab else cod
            for cod, lab in raw.dims[1:]
        ]
        if extras:
            descrizione = " · ".join(
                part for part in [raw.dims[0][1], *extras] if part and part != "—"
            )
        else:
            descrizione = raw.dims[0][1]
        rows.append(
            StatisticaRiga(
                codice=codice,
                descrizione=descrizione or (labels[0] if labels else ""),
                quantita=raw.quantita,
                valore=raw.valore,
                kind="row",
                link_kind=single_link,
            )
        )
    return rows


def _layout_testata_dettaglio(
    raw_rows: list[_RawStatRow],
    *,
    dim_keys: tuple[str, ...],
    detail_link: str = "articolo",
) -> list[StatisticaRiga]:
    """
    Dimensioni precedenti all'ultima in testata (annidate se >1);
    ultima dimensione come righe dettaglio (es. Articoli oppure Clienti).
    """
    n = len(dim_keys)
    if n < 2:
        return _layout_flat(raw_rows, dim_keys=dim_keys)

    out: list[StatisticaRiga] = []
    last_key = dim_keys[-1]
    detail = (
        (detail_link or "").strip()
        or _DIM_HEADER_LINK.get(last_key, last_key)
        or "articolo"
    )

    def walk(rows: list[_RawStatRow], level: int) -> None:
        if not rows or level >= n - 1:
            return
        # Solo codice: etichette disallineate non spezzano i gruppi.
        for h_code, group_iter in groupby(rows, key=lambda r: r.dims[level][0]):
            group = list(group_iter)
            h_label = next(
                (lab for _cod, lab in (r.dims[level] for r in group) if lab),
                "",
            )
            out.append(
                StatisticaRiga(
                    codice=h_code,
                    descrizione=(h_label or "").strip(),
                    quantita=sum(r.quantita for r in group),
                    valore=sum(r.valore for r in group),
                    kind="header",
                    link_kind=_DIM_HEADER_LINK.get(dim_keys[level], ""),
                    level=level,
                )
            )
            if level == n - 2:
                for raw in group:
                    d_code, d_label = raw.dims[-1]
                    out.append(
                        StatisticaRiga(
                            codice=d_code,
                            descrizione=(d_label or "").strip(),
                            quantita=raw.quantita,
                            valore=raw.valore,
                            kind="detail",
                            link_kind=detail,
                            level=level + 1,
                        )
                    )
            else:
                walk(group, level + 1)

    walk(list(raw_rows), 0)
    return out


def parse_period(get) -> tuple[date, date]:
    today = date.today()
    preset = (get.get("anno") or "").strip()
    if preset.isdigit():
        year = int(preset)
        return date(year, 1, 1), date(year, 12, 31)
    data_da = parse_date((get.get("data_da") or "").strip()) or date(today.year, 1, 1)
    data_a = parse_date((get.get("data_a") or "").strip()) or date(today.year, 12, 31)
    if data_a < data_da:
        data_da, data_a = data_a, data_da
    return data_da, data_a


def selected_causali(get) -> list[str]:
    raw = get.getlist("causale") if hasattr(get, "getlist") else []
    codes = []
    seen = set()
    for item in raw:
        code = (item or "").strip()
        if not code or code in seen:
            continue
        seen.add(code)
        codes.append(code)
    return codes


def selected_set_ids(get) -> list[int]:
    """Uno o più set articoli (GET set_id ripetuto; compatibile con set_id singolo)."""
    if hasattr(get, "getlist"):
        raw = list(get.getlist("set_id"))
    else:
        single = get.get("set_id") if hasattr(get, "get") else None
        raw = [single] if single not in (None, "") else []
    ids: list[int] = []
    seen: set[int] = set()
    for item in raw:
        text = str(item or "").strip()
        if not text.isdigit():
            continue
        value = int(text)
        if value in seen:
            continue
        seen.add(value)
        ids.append(value)
    return ids


def selected_articoli(get) -> list[str]:
    """Codici articolo selezionati (GET art ripetuto)."""
    if hasattr(get, "getlist"):
        raw = list(get.getlist("art"))
    else:
        single = get.get("art") if hasattr(get, "get") else None
        raw = [single] if single not in (None, "") else []
    codes: list[str] = []
    seen: set[str] = set()
    for item in raw:
        code = str(item or "").strip()
        if not code:
            continue
        key = code.casefold()
        if key in seen:
            continue
        seen.add(key)
        codes.append(code)
    return codes


def articoli_da_set(set_ids: list[int]) -> list[dict[str, str]]:
    """Unisce le righe dei set (codice univoco, prima descrizione trovata)."""
    ids = [int(x) for x in (set_ids or []) if x is not None]
    if not ids:
        return []
    from apps.set_articoli.models import SetArticoloD

    rows = (
        SetArticoloD.objects.filter(testa_id__in=ids)
        .exclude(cod_art__isnull=True)
        .exclude(cod_art="")
        .order_by("pos", "id")
        .values_list("cod_art", "desc_art")
    )
    out: list[dict[str, str]] = []
    seen: set[str] = set()
    for cod, desc in rows:
        code = (cod or "").strip()
        if not code:
            continue
        key = code.casefold()
        if key in seen:
            continue
        seen.add(key)
        out.append({"codice": code, "descrizione": (desc or "").strip()})
    return out


def resolve_articoli_selection(codes: list[str]) -> list[dict[str, str]]:
    """Arricchisce i codici con descrizione da set_d / anagrafica articoli."""
    cleaned: list[str] = []
    seen: set[str] = set()
    for item in codes or []:
        code = (item or "").strip()
        if not code:
            continue
        key = code.casefold()
        if key in seen:
            continue
        seen.add(key)
        cleaned.append(code)
    if not cleaned:
        return []

    from apps.articoli.models import Articolo
    from apps.set_articoli.models import SetArticoloD

    desc_map: dict[str, str] = {}
    for cod, desc in (
        SetArticoloD.objects.filter(cod_art__in=cleaned)
        .exclude(desc_art__isnull=True)
        .exclude(desc_art="")
        .values_list("cod_art", "desc_art")
    ):
        key = (cod or "").strip().casefold()
        if key and key not in desc_map:
            desc_map[key] = (desc or "").strip()

    art_map = {
        (a.codice or "").strip().casefold(): (a.descrizione or "").strip()
        for a in Articolo.objects.filter(codice__in=cleaned).only("codice", "descrizione")
    }

    out: list[dict[str, str]] = []
    for code in cleaned:
        key = code.casefold()
        out.append(
            {
                "codice": code,
                "descrizione": desc_map.get(key) or art_map.get(key) or "",
            }
        )
    return out


def default_causali_selection() -> list[str]:
    """Come maschera 4D tipica vendite: scarichi clienti / visione."""
    preferred = {"05", "07"}
    existing = set(
        CausaleMagazzino.objects.filter(codice__in=preferred).values_list(
            "codice", flat=True
        )
    )
    return sorted(preferred & {str(c) for c in existing})


def list_causali() -> list[CausaleMagazzino]:
    return list(CausaleMagazzino.objects.all().order_by("codice", "descrizione"))


def _join_sql(needed: set[str]) -> str:
    parts = ['LEFT JOIN articoli a ON a."Codice" = d."CodiceArt"']
    if "clienti" in needed:
        parts.append('LEFT JOIN clienti c ON c."Codice" = t."Cliente"')
    if "zone" in needed:
        parts.append('LEFT JOIN zone z ON z."Codice" = c."Zona"')
    if "agenti" in needed:
        parts.append('LEFT JOIN agenti ag ON ag."Codice" = c."Agente"')
    if "gruppi_clifor" in needed:
        parts.append(
            'LEFT JOIN raggruppamento_clifor gcf ON gcf."Codice" = NULLIF(TRIM(c."Gruppo"), \'\')'
        )
    if "categorie" in needed:
        parts.append('LEFT JOIN categorie cat ON cat."Codice" = a."CatOmogenea"')
    if "fornitori" in needed:
        parts.append(
            'LEFT JOIN fornitori f ON f."Codice" = COALESCE('
            'NULLIF(TRIM(t."Fornitore"), \'\'), NULLIF(TRIM(a."CodFornitore"), \'\'))'
        )
    if "depositi" in needed:
        parts.append(
            'LEFT JOIN depositi dep ON dep."Numero" = COALESCE('
            'NULLIF(TRIM(t."DepUscita"), \'\'), NULLIF(TRIM(t."DepEntrata"), \'\'))'
        )
    return "\n        ".join(parts)


def elabora_statistiche(
    *,
    data_da: date,
    data_a: date,
    causali: list[str],
    articolo_da: str = "",
    articolo_a: str = "",
    set_ids: list[int] | None = None,
    set_id: int | None = None,
    articoli: list[str] | None = None,
    tipo: str | None = None,
) -> list[StatisticaRiga]:
    if not causali:
        return []

    spec = resolve_statistica_tipo(tipo)
    dim_keys = tuple(spec["dims"])  # type: ignore[arg-type]
    dims = [_DIM_SQL[k] for k in dim_keys]

    articolo_da = (articolo_da or "").strip()
    articolo_a = (articolo_a or "").strip()
    ids = list(set_ids or [])
    if not ids and set_id:
        ids = [int(set_id)]
    art_codes = [(c or "").strip() for c in (articoli or []) if (c or "").strip()]

    needed: set[str] = {"articoli"}
    for dim in dims:
        needed.update(dim.get("joins") or ())  # type: ignore[arg-type]

    select_parts = [
        f'{dims[0]["code"]} AS codice',
        f'{dims[0]["label"]} AS des_main',
    ]
    group_parts = [str(dims[0]["group"])]
    for i, dim in enumerate(dims[1:], start=2):
        select_parts.append(f'{dim["code"]} AS cod_{i}')
        select_parts.append(f'{dim["label"]} AS des_{i}')
        group_parts.append(str(dim["group"]))

    select_parts.append('COALESCE(SUM(d."Quantita"), 0) AS quantita')
    select_parts.append('COALESCE(SUM(d."ValoreTotale"), 0) AS valore')

    placeholders = ", ".join(["%s"] * len(causali))
    params: list = list(causali) + [data_da, data_a]
    sql = f"""
        SELECT
            {", ".join(select_parts)}
        FROM movimentit_dettaglio d
        INNER JOIN movimentit t
            ON t."ID_Testa" = d.id_added_by_converter
        {_join_sql(needed)}
        WHERE t."Causale" IN ({placeholders})
          AND CAST(t."DataRegistraz" AS date) >= %s
          AND CAST(t."DataRegistraz" AS date) <= %s
    """
    if articolo_da:
        sql += ' AND COALESCE(d."CodiceArt", \'\') >= %s'
        params.append(articolo_da)
    if articolo_a:
        sql += ' AND COALESCE(d."CodiceArt", \'\') <= %s'
        params.append(articolo_a)
    if art_codes:
        art_ph = ", ".join(["%s"] * len(art_codes))
        sql += f' AND d."CodiceArt" IN ({art_ph})'
        params.extend(art_codes)
    elif ids:
        set_ph = ", ".join(["%s"] * len(ids))
        sql += f"""
          AND EXISTS (
            SELECT 1
            FROM set_articoli_d sd
            WHERE sd."ID_Testa" IN ({set_ph})
              AND sd."CodArt" = d."CodiceArt"
          )
        """
        params.extend(int(x) for x in ids)
    sql += f"""
        GROUP BY {", ".join(group_parts)}
        ORDER BY {", ".join(str(1 + i * 2) for i in range(len(group_parts)))}
    """

    rows_raw: list[_RawStatRow] = []
    n_dims = len(dims)
    with connection.cursor() as cur:
        cur.execute(sql, params)
        for tup in cur.fetchall():
            dim_pairs: list[tuple[str, str]] = []
            idx = 0
            for _ in range(n_dims):
                cod = str(tup[idx] or "—").strip() or "—"
                lab = str(tup[idx + 1] or "").strip()
                dim_pairs.append((cod, lab))
                idx += 2
            quantita = float(tup[idx] or 0)
            valore = float(tup[idx + 1] or 0)
            rows_raw.append(
                _RawStatRow(dims=tuple(dim_pairs), quantita=quantita, valore=valore)
            )

    layout = str(spec.get("layout") or LAYOUT_FLAT)
    if layout == LAYOUT_TESTATA_DETTAGLIO and n_dims >= 2:
        rows = _layout_testata_dettaglio(
            rows_raw,
            dim_keys=dim_keys,
            detail_link=str(spec.get("detail_link") or "articolo"),
        )
    else:
        rows = _layout_flat(rows_raw, dim_keys=dim_keys)
    return finalize_righe_articoli(rows)


def filter_summary(
    *,
    titolo: str,
    data_da: date,
    data_a: date,
    causali: list[str],
    articolo_da: str = "",
    articolo_a: str = "",
    set_label: str = "",
    n_articoli: int = 0,
    tipo_label: str = "",
) -> str:
    parts = [
        (titolo or "Statistiche magazzino").strip(),
        f"Periodo {data_da.strftime('%d/%m/%Y')} – {data_a.strftime('%d/%m/%Y')}",
    ]
    if tipo_label:
        parts.append(tipo_label)
    if causali:
        parts.append("Causali: " + ", ".join(causali))
    if articolo_da or articolo_a:
        parts.append(
            f"Articoli {articolo_da or '…'} → {articolo_a or '…'}"
        )
    if set_label:
        parts.append(f"Set: {set_label}")
    if n_articoli:
        parts.append(f"Selezione: {n_articoli} articoli")
    return " · ".join(parts)


def movimenti_count_preview(data_da: date, data_a: date, causali: list[str]) -> int:
    if not causali:
        return 0
    qs = MovimentoT.objects.filter(causale__in=causali).annotate(
        _d=Cast("data_registraz", DateField())
    )
    return qs.filter(_d__gte=data_da, _d__lte=data_a).count()
