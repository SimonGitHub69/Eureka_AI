"""
Sync ODBC 4D → teste_documenti / righe_documenti (schema unificato).

Flusso:
1. Per ogni tabella testata 4D: introspection ODBC, fetch batch, map_header_row, upsert TestaDocumento
2. Se Parametri documento hanno una serie (es. PRF/FF), due letture 4D: Alfa = serie e residuo
3. Per ogni tabella dettaglio: stesso filtro Alfa se la colonna esiste, altrimenti mappa dalla testata
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Mapping, Sequence, Union

OnlySelection = Union[str, Sequence[str], None]

CancelCheck = Callable[[], bool] | None

from django.db import connection, transaction
from django.utils import timezone

from apps.core.quattro_d import open_4d_connection
from apps.core.sync_4d import (
    SyncResult,
    fetch_4d_rows,
    introspect_columns,
    is_empty_pk_value,
    normalize_value,
    sync_tables,
)
from apps.core.sync_incremental import (
    build_incremental_where,
    clear_all_watermarks,
    detect_modifica_columns,
    ensure_modifica_columns_in_list,
    format_incremental_message,
    get_watermark,
    max_modifica_from_rows,
    set_watermark,
    sync_full_from_request,
)
from apps.core.programma import DOC_MENU_FIELDS, is_documento_menu_enabled
from apps.documenti.mapping import (
    DEFAULT_TIPI_DOCUMENTO,
    DETAIL_SOURCES,
    HEADER_FIELD_ALIASES,
    HEADER_SOURCES,
    PREVENTIVI_SERIE_TIPO,
    PREVENTIVI_TIPI,
    DetailSourceSpec,
    HeaderSourceSpec,
    line_id_testa,
    map_header_row,
    map_line_row,
    resolve_detail_tipo_doc,
    resolve_header_tipo_doc,
)
from apps.documenti.models import RigaDocumento, TestaDocumento

FATTURE_TIPI = ("FAT", "NCR", "NDB")

PORTO_TABLES = (
    {
        "source": "TabPorto",
        "target": "tab_porto",
        "pk": "ID",
    },
)

CANCELLED_MESSAGE = "Sincronizzazione interrotta dall'utente."

DEFAULT_SYNC_BATCH_SIZE = 5000
DEFAULT_SYNC_PAGE_SIZE = 50000

_DOCUMENTI_MANAGED_MODELS = (TestaDocumento, RigaDocumento)


def _pg_table_exists(table_name: str) -> bool:
    with connection.cursor() as cur:
        cur.execute(
            """
            SELECT EXISTS (
                SELECT 1
                FROM information_schema.tables
                WHERE table_schema = 'public' AND table_name = %s
            )
            """,
            [table_name],
        )
        return bool(cur.fetchone()[0])


def ensure_documenti_tables() -> list[str]:
    """
    Ricrea teste_documenti / righe_documenti se assenti (es. dopo Azzera tabelle).
    Ritorna i nomi delle tabelle create.
    """
    created: list[str] = []
    with connection.schema_editor() as schema_editor:
        for model in _DOCUMENTI_MANAGED_MODELS:
            table = model._meta.db_table
            if _pg_table_exists(table):
                continue
            schema_editor.create_model(model)
            created.append(table)
    return created


class SyncCancelledError(Exception):
    """Richiesta di interruzione sync da parte dell'utente."""


def should_cancel_sync(log_id: int | None) -> bool:
    if log_id is None:
        return False
    from apps.documenti.models import SyncDocumentiLog

    return SyncDocumentiLog.objects.filter(
        pk=log_id,
        cancel_requested=True,
    ).exists()


def request_cancel_sync(log_id: int) -> bool:
    from apps.documenti.models import SyncDocumentiLog

    updated = SyncDocumentiLog.objects.filter(
        pk=log_id,
        finished_at__isnull=True,
    ).update(cancel_requested=True)
    return updated > 0


def _is_cancelled(log_id: int | None, cancel_check: CancelCheck) -> bool:
    if cancel_check is not None and cancel_check():
        return True
    return should_cancel_sync(log_id)


def _raise_if_cancelled(log_id: int | None, cancel_check: CancelCheck) -> None:
    if _is_cancelled(log_id, cancel_check):
        raise SyncCancelledError()


@dataclass
class DocTableSyncResult:
    source: str
    target: str
    rows: int = 0
    ok: bool = True
    message: str = ""
    rows_by_tipo: dict[str, int] = field(default_factory=dict)


@dataclass
class SerieImportSlice:
    """Una lettura 4D filtrata per serie (Alfa) → tipo documento."""

    tipo_doc: str
    serie: str
    extra_where: str


def _sql_str(value: str) -> str:
    return "'" + str(value).replace("'", "''") + "'"


def _bump_count(counts: dict[str, int], key: str, amount: int = 1) -> None:
    if not key or amount <= 0:
        return
    counts[key] = counts.get(key, 0) + amount


def _merge_counts(target: dict[str, int], source: Mapping[str, int]) -> None:
    for key, amount in source.items():
        _bump_count(target, key, int(amount or 0))


def format_counts_by_tipo(
    teste_by_tipo: Mapping[str, int],
    righe_by_tipo: Mapping[str, int],
) -> str:
    """Righe leggibili: «ORV: 10 teste / 40 righe» ordinate per codice tipo."""
    tipos = sorted({*teste_by_tipo.keys(), *righe_by_tipo.keys()})
    if not tipos:
        return ""
    lines: list[str] = []
    for tipo in tipos:
        lines.append(
            f"{tipo}: {int(teste_by_tipo.get(tipo, 0))} teste / "
            f"{int(righe_by_tipo.get(tipo, 0))} righe"
        )
    return "\n".join(lines)


def _format_rows_by_tipo_inline(rows_by_tipo: Mapping[str, int]) -> str:
    if not rows_by_tipo:
        return ""
    parts = [f"{tipo}={rows_by_tipo[tipo]}" for tipo in sorted(rows_by_tipo)]
    return ": " + ", ".join(parts)


def resolve_alfa_column_name(columns: Sequence[Any]) -> str | None:
    """Nome colonna Alfa/Serie reale dallo schema 4D."""
    names: dict[str, str] = {}
    for col in columns:
        name = col["name"] if isinstance(col, Mapping) else str(col)
        if name:
            names[name.casefold()] = name
    for alias in HEADER_FIELD_ALIASES.get("alfa", ()):
        found = names.get(alias.casefold())
        if found:
            return found
    return None


def build_alfa_where(
    column: str,
    serie: str,
    claimed: Sequence[str],
) -> str:
    """WHERE 4D: Alfa = serie, oppure Alfa non nelle serie configurate (tipo default)."""
    col = f"[{column.replace(']', '')}]"
    serie_norm = (serie or "").strip()
    if serie_norm:
        variants = []
        for value in (serie_norm, serie_norm.upper(), serie_norm.lower()):
            lit = _sql_str(value)
            if lit not in variants:
                variants.append(lit)
        return "(" + " OR ".join(f"{col} = {lit}" for lit in variants) + ")"
    claimed_norm = []
    for raw in claimed:
        text = (raw or "").strip()
        if not text:
            continue
        for value in (text, text.upper(), text.lower()):
            if value not in claimed_norm:
                claimed_norm.append(value)
    if not claimed_norm:
        return ""
    differ = " AND ".join(f"{col} <> {_sql_str(value)}" for value in claimed_norm)
    return f"(({differ}) OR {col} IS NULL OR {col} = '')"


@dataclass
class DocumentiSyncResult:
    ok: bool = True
    cancelled: bool = False
    tables: list[DocTableSyncResult] = field(default_factory=list)
    teste_count: int = 0
    righe_count: int = 0
    teste_by_tipo: dict[str, int] = field(default_factory=dict)
    righe_by_tipo: dict[str, int] = field(default_factory=dict)
    message: str = ""


HEADER_UPDATE_FIELDS = [
    f.name
    for f in TestaDocumento._meta.fields
    if f.name not in {"id", "tipo_doc"}
]

LINE_UPDATE_FIELDS = [
    f.name
    for f in RigaDocumento._meta.fields
    if f.name not in {"id", "testa"}
]


def _load_cambio_by_valuta() -> dict[str, float]:
    """Cambio da tabella Valuta / Valuta_Det (ultimo storico per codice)."""
    try:
        from apps.valute.models import Valuta, ValutaDet
    except Exception:
        return {}
    out: dict[str, float] = {}
    try:
        for det in ValutaDet.objects.exclude(cambio=None).order_by(
            "valuta_id", "-data", "-id"
        ):
            key = (det.valuta_id or "").strip().lower()
            if key and key not in out:
                out[key] = float(det.cambio)
        for v in Valuta.objects.all().only("codice", "cambio"):
            key = (v.codice or "").strip().lower()
            if not key or key in out:
                continue
            if v.cambio is not None:
                out[key] = float(v.cambio)
    except Exception:
        return out
    for alias in ("euro", "eur", "eu"):
        if alias not in out:
            out[alias] = out.get("euro") or out.get("eur") or 1.0
    return out


def _fill_cambio_from_valuta(
    mapped: dict[str, Any], lookup: dict[str, float]
) -> None:
    """Se Cambio 4D manca/zero, usa il cambio della valuta anagrafica."""
    if mapped.get("cambio") not in (None, 0, 0.0):
        return
    valuta = (mapped.get("valuta") or "").strip()
    if not valuta:
        return
    rate = lookup.get(valuta.lower())
    if rate is not None:
        mapped["cambio"] = rate


def _fill_sconto_from_tabella(mapped: dict[str, Any]) -> None:
    """Valorizza testata.sconto da Sconto1+2+3 oppure da tabella Sconti via codice."""
    from apps.documenti.sconto import resolve_sconto_percentuale

    if (mapped.get("sconto") or "").strip():
        return
    mapped["sconto"] = resolve_sconto_percentuale(mapped.get("codice_sconto") or "")


def _header_source_for_detail(detail_source: str) -> str:
    if detail_source.endswith("_Dettaglio"):
        return detail_source[: -len("_Dettaglio")]
    return detail_source


def _db_tipi_for_source(source: str) -> tuple[str, ...]:
    """Tipi attivi la cui tabella 4D testata è ``source``."""
    try:
        from apps.documenti.models import TipoDocumento

        return tuple(
            TipoDocumento.objects.filter(
                attivo=True,
                source_table_4d__iexact=source,
            )
            .exclude(codice="")
            .values_list("codice", flat=True)
        )
    except Exception:
        return ()


def _tipos_for_header_spec(spec: HeaderSourceSpec) -> tuple[str, ...]:
    if spec.source == "Preventivi":
        codes = list(PREVENTIVI_TIPI)
    elif spec.tipo_doc is None:
        codes = list(FATTURE_TIPI)
    else:
        codes = [spec.tipo_doc]
    for codice in _db_tipi_for_source(spec.source):
        if codice not in codes:
            codes.append(codice)
    return tuple(codes)


def _tipos_for_detail_spec(spec: DetailSourceSpec) -> tuple[str, ...]:
    header = next(
        (s for s in HEADER_SOURCES if s.source == _header_source_for_detail(spec.source)),
        None,
    )
    if header is not None:
        return _tipos_for_header_spec(header)
    if spec.tipo_doc is None:
        return FATTURE_TIPI
    return (spec.tipo_doc,)


def _serie_tipi_for_spec(spec: HeaderSourceSpec) -> dict[str, str]:
    """Mappa serie (Alfa 4D) → codice tipo, dai Parametri documento della stessa tabella 4D."""
    lookup: dict[str, str] = {}
    if spec.source == "Preventivi":
        lookup.update(PREVENTIVI_SERIE_TIPO)
    try:
        from apps.documenti.models import TipoDocumento

        rows = TipoDocumento.objects.filter(
            attivo=True,
            codice__in=_tipos_for_header_spec(spec),
        ).exclude(serie="").values_list("codice", "serie")
        for codice, serie in rows:
            key = (serie or "").strip().upper()
            if key and codice:
                lookup[key] = codice
    except Exception:
        pass
    return lookup


def _serie_by_tipo_for_spec(spec: HeaderSourceSpec) -> dict[str, str]:
    """codice tipo → serie (uppercase; vuota se non configurata)."""
    out = {codice: "" for codice in _tipos_for_header_spec(spec)}
    try:
        from apps.documenti.models import TipoDocumento

        rows = TipoDocumento.objects.filter(
            attivo=True,
            codice__in=list(out.keys()),
        ).values_list("codice", "serie")
        for codice, serie in rows:
            out[codice] = (serie or "").strip().upper()
    except Exception:
        if spec.source == "Preventivi":
            for serie, tipo in PREVENTIVI_SERIE_TIPO.items():
                if tipo in out:
                    out[tipo] = serie
    return out


def import_slices_for_spec(
    spec: HeaderSourceSpec,
    *,
    enabled: Sequence[str],
    tipos_filter: frozenset[str] | None,
    alfa_column: str | None,
) -> list[SerieImportSlice]:
    """Una slice per ogni tipo con serie; più una residua per il tipo senza serie."""
    if not alfa_column:
        return []
    serie_by_tipo = _serie_by_tipo_for_spec(spec)
    claimed = sorted(
        {
            serie_by_tipo.get(tipo, "")
            for tipo in enabled
            if serie_by_tipo.get(tipo, "")
        }
    )
    if not claimed:
        return []
    slices: list[SerieImportSlice] = []
    residual: list[str] = []
    for tipo in enabled:
        if tipos_filter is not None and tipo not in tipos_filter:
            continue
        serie = serie_by_tipo.get(tipo, "")
        if serie:
            slices.append(
                SerieImportSlice(
                    tipo_doc=tipo,
                    serie=serie,
                    extra_where=build_alfa_where(alfa_column, serie, claimed),
                )
            )
        else:
            residual.append(tipo)
    if len(residual) > 1:
        # Più tipi senza serie (es. FAT/NCR/NDB): niente split, classificazione riga per riga.
        return []
    if residual:
        extra = build_alfa_where(alfa_column, "", claimed)
        if extra:
            slices.append(
                SerieImportSlice(
                    tipo_doc=residual[0], serie="", extra_where=extra
                )
            )
    return slices


def _header_spec_for_detail(spec: DetailSourceSpec) -> HeaderSourceSpec | None:
    header_source = _header_source_for_detail(spec.source)
    return next((s for s in HEADER_SOURCES if s.source == header_source), None)


def _has_serie_split(spec: HeaderSourceSpec, enabled: Sequence[str]) -> bool:
    serie_by_tipo = _serie_by_tipo_for_spec(spec)
    return any(bool(serie_by_tipo.get(tipo, "")) for tipo in enabled)


def _slices_for_sync(
    spec: HeaderSourceSpec,
    *,
    enabled: Sequence[str],
    tipos_filter: frozenset[str] | None,
    source_table: str,
) -> list[SerieImportSlice]:
    """Slice 4D per serie solo se Parametri documento hanno almeno una serie."""
    serie_by_tipo = _serie_by_tipo_for_spec(spec)
    if not any(serie_by_tipo.get(tipo, "") for tipo in enabled):
        return []
    alfa_column = resolve_alfa_column_name(_peek_columns(source_table))
    return import_slices_for_spec(
        spec,
        enabled=enabled,
        tipos_filter=tipos_filter,
        alfa_column=alfa_column,
    )


def _commit_watermark(
    source: str,
    columns: Sequence[Any],
    watermark_rows: Sequence[Mapping[str, Any]],
) -> None:
    if not watermark_rows:
        return
    col_list = [c if isinstance(c, dict) else {"name": str(c)} for c in columns]
    modifica_spec = detect_modifica_columns(col_list, source_table=source)
    if modifica_spec is None:
        return
    watermark = get_watermark(source)
    batch_max = max_modifica_from_rows(list(watermark_rows), spec=modifica_spec)
    if batch_max is not None and (watermark is None or batch_max > watermark):
        set_watermark(source, batch_max)


def _enabled_tipos_for_header_spec(spec: HeaderSourceSpec) -> tuple[str, ...]:
    return tuple(t for t in _tipos_for_header_spec(spec) if is_documento_menu_enabled(t))


def _enabled_tipos_for_detail_spec(spec: DetailSourceSpec) -> tuple[str, ...]:
    return tuple(t for t in _tipos_for_detail_spec(spec) if is_documento_menu_enabled(t))


def _skip_message(source: str, target: str, tipos: Sequence[str]) -> str:
    if len(tipos) == 1:
        return (
            f"{source} -> {target}: Tipo {tipos[0]} disabilitato in parametri programma — ignorato."
        )
    joined = ", ".join(tipos)
    return (
        f"{source} -> {target}: Tipi {joined} disabilitati in parametri programma — ignorato."
    )


def _skipped_table_result(source: str, target: str, tipos: Sequence[str]) -> DocTableSyncResult:
    return DocTableSyncResult(
        source=source,
        target=target,
        rows=0,
        ok=True,
        message=_skip_message(source, target, tipos),
    )


def _row_to_dict(row: tuple, columns: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        columns[idx]["name"]: normalize_value(row[idx], columns[idx]["pg_type"])
        for idx in range(len(columns))
    }


def _combine_where(*parts: str | None) -> str | None:
    clauses = [f"({p})" for p in parts if p and str(p).strip()]
    if not clauses:
        return None
    if len(clauses) == 1:
        return clauses[0][1:-1]
    return " AND ".join(clauses)


def _peek_columns(source: str) -> list[dict[str, Any]]:
    with open_4d_connection(timeout=60) as conn:
        cur = conn.cursor()
        return introspect_columns(cur, source)


def _max_header_id_4d(tipos: Sequence[str]) -> int | None:
    from django.db.models import Max

    if not tipos:
        return None
    return TestaDocumento.objects.filter(tipo_doc_id__in=tipos).aggregate(
        m=Max("id_4d")
    )["m"]


def _max_line_id_4d(tipos: Sequence[str]) -> int | None:
    from django.db.models import Max

    if not tipos:
        return None
    return RigaDocumento.objects.filter(testa__tipo_doc_id__in=tipos).aggregate(
        m=Max("id_4d")
    )["m"]


def _run_fetch(
    source: str,
    batch_size: int,
    *,
    page_pk: str | None = None,
    page_size: int = DEFAULT_SYNC_PAGE_SIZE,
    full: bool = False,
    incremental_by_pk: bool = False,
    start_after_pk: Any = None,
    log_id: int | None = None,
    cancel_check: CancelCheck = None,
    extra_where: str | None = None,
    update_watermark: bool = True,
    on_batch: Callable[[list[dict[str, Any]], list[dict[str, Any]]], None] | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], str, list[dict[str, Any]]]:
    """Fetch righe 4D; ritorna (rows, columns, messaggio, righe watermark)."""
    with open_4d_connection(timeout=60) as conn:
        cur = conn.cursor()
        columns = introspect_columns(cur, source)
        modifica_spec = detect_modifica_columns(columns, source_table=source)
        columns = ensure_modifica_columns_in_list(columns, modifica_spec)
        watermark = get_watermark(source)
        since_watermark = watermark
        fallback_full = False
        fallback_reason: str | None = None
        use_incremental = (
            not full
            and modifica_spec is not None
            and watermark is not None
        )
        if not full and modifica_spec is None:
            fallback_full = True
            fallback_reason = "no_modifica_columns"
        elif not full and watermark is None:
            fallback_full = True
            fallback_reason = "first_import"

        pk_incremental = False
        if (
            not full
            and incremental_by_pk
            and page_pk
            and start_after_pk is not None
            and not is_empty_pk_value(start_after_pk)
            and (fallback_full or not use_incremental)
        ):
            pk_incremental = True
            use_incremental = False

        incremental_where = None
        if use_incremental and modifica_spec and watermark:
            incremental_where = build_incremental_where(modifica_spec, watermark)
        where_clause = _combine_where(incremental_where, extra_where)
        if pk_incremental:
            where_clause = _combine_where(None, extra_where)

        rows: list[dict[str, Any]] = []
        watermark_rows: list[dict[str, Any]] = []
        row_count = 0
        for batch in fetch_4d_rows(
            cur,
            source,
            columns,
            batch_size=batch_size,
            where_clause=where_clause,
            page_pk=page_pk,
            page_size=page_size,
            start_after_pk=start_after_pk if pk_incremental else None,
        ):
            _raise_if_cancelled(log_id, cancel_check)
            batch_dicts: list[dict[str, Any]] = []
            batch_wm: list[dict[str, Any]] = []
            for row in batch:
                row_dict = _row_to_dict(row, columns)
                batch_dicts.append(row_dict)
                if modifica_spec:
                    batch_wm.append(row_dict)
            row_count += len(batch_dicts)
            if on_batch is not None:
                on_batch(batch_dicts, batch_wm)
            else:
                rows.extend(batch_dicts)
            watermark_rows.extend(batch_wm)

        if update_watermark and modifica_spec and watermark_rows:
            batch_max = max_modifica_from_rows(watermark_rows, spec=modifica_spec)
            if batch_max is not None and (watermark is None or batch_max > watermark):
                set_watermark(source, batch_max)

        fetch_msg = format_incremental_message(
            row_count,
            since=since_watermark if use_incremental else None,
            full=full or (not use_incremental and not pk_incremental and not fallback_full),
            fallback_full=fallback_full and not pk_incremental,
            fallback_reason=fallback_reason,
            pk_incremental=pk_incremental,
        )
        return rows, columns, fetch_msg, watermark_rows


def _fetch_rows(
    source: str,
    batch_size: int,
    *,
    page_pk: str | None = None,
    page_size: int = DEFAULT_SYNC_PAGE_SIZE,
    full: bool = False,
    incremental_by_pk: bool = False,
    start_after_pk: Any = None,
    log_id: int | None = None,
    cancel_check: CancelCheck = None,
    extra_where: str | None = None,
    update_watermark: bool = True,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], str, list[dict[str, Any]]]:
    """Fetch righe 4D; ritorna (rows, columns, messaggio, righe per watermark)."""
    return _run_fetch(
        source,
        batch_size,
        page_pk=page_pk,
        page_size=page_size,
        full=full,
        incremental_by_pk=incremental_by_pk,
        start_after_pk=start_after_pk,
        log_id=log_id,
        cancel_check=cancel_check,
        extra_where=extra_where,
        update_watermark=update_watermark,
    )


def _fetch_all_rows(
    source: str,
    batch_size: int,
    *,
    full: bool = False,
    log_id: int | None = None,
    cancel_check: CancelCheck = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    rows, columns, _, _ = _fetch_rows(
        source,
        batch_size,
        full=full,
        log_id=log_id,
        cancel_check=cancel_check,
    )
    return rows, columns


def _upsert_teste(instances: list[TestaDocumento]) -> int:
    if not instances:
        return 0
    TestaDocumento.objects.bulk_create(
        instances,
        update_conflicts=True,
        unique_fields=["tipo_doc", "id_4d"],
        update_fields=HEADER_UPDATE_FIELDS,
    )
    return len(instances)


def _replace_righe_for_tipo(tipo_doc: str, righe: list[RigaDocumento]) -> int:
    """Sostituisce tutte le righe del tipo documento (sync full refresh per tipo)."""
    with transaction.atomic():
        RigaDocumento.objects.filter(testa__tipo_doc_id=tipo_doc).delete()
        if righe:
            RigaDocumento.objects.bulk_create(righe, batch_size=DEFAULT_SYNC_BATCH_SIZE)
    return len(righe)


def _upsert_righe(righe: list[RigaDocumento]) -> int:
    if not righe:
        return 0
    RigaDocumento.objects.bulk_create(
        righe,
        update_conflicts=True,
        unique_fields=["testa", "id_4d"],
        update_fields=LINE_UPDATE_FIELDS,
        batch_size=DEFAULT_SYNC_BATCH_SIZE,
    )
    return len(righe)


def sync_header_source(
    spec: HeaderSourceSpec,
    *,
    batch_size: int = DEFAULT_SYNC_BATCH_SIZE,
    now: datetime | None = None,
    tipos_filter: frozenset[str] | None = None,
    log_id: int | None = None,
    cancel_check: CancelCheck = None,
    full: bool = False,
) -> DocTableSyncResult:
    result = DocTableSyncResult(source=spec.source, target="teste_documenti")
    disabled = [
        t for t in _tipos_for_header_spec(spec) if not is_documento_menu_enabled(t)
    ]
    enabled = _enabled_tipos_for_header_spec(spec)
    if not enabled:
        result.message = _skip_message(spec.source, "teste_documenti", disabled)
        return result

    now = now or timezone.now()
    serie_tipi = _serie_tipi_for_spec(spec)
    family = _tipos_for_header_spec(spec)
    try:
        slices = _slices_for_sync(
            spec,
            enabled=enabled,
            tipos_filter=tipos_filter,
            source_table=spec.source,
        )
        seen_ids: dict[str, set[int]] = {}
        cambio_lookup = _load_cambio_by_valuta()
        fetch_parts: list[str] = []
        watermark_rows: list[dict[str, Any]] = []
        last_columns: list[dict[str, Any]] = []
        count = 0
        rows_by_tipo: dict[str, int] = {}

        fetch_kwargs = dict(
            batch_size=batch_size,
            page_pk=spec.pk,
            page_size=DEFAULT_SYNC_PAGE_SIZE,
            full=full,
            incremental_by_pk=True,
            log_id=log_id,
            cancel_check=cancel_check,
        )

        def _process_batch(
            batch_dicts: Sequence[Mapping[str, Any]], tipo_fixed: str | None
        ) -> None:
            nonlocal count
            batch_instances: list[TestaDocumento] = []
            for raw in batch_dicts:
                tipo = tipo_fixed or resolve_header_tipo_doc(
                    spec, raw, serie_tipi=serie_tipi
                )
                if tipos_filter is not None and tipo not in tipos_filter:
                    continue
                if not is_documento_menu_enabled(tipo):
                    continue
                mapped = map_header_row(
                    raw,
                    tipo_doc=tipo,
                    source_table=spec.source,
                    clifor_tipo=spec.clifor_tipo,
                )
                id_4d = mapped.get("id_4d")
                if id_4d is None:
                    continue
                _fill_cambio_from_valuta(mapped, cambio_lookup)
                _fill_sconto_from_tabella(mapped)
                mapped["synced_at"] = now
                batch_instances.append(TestaDocumento(**mapped))
                seen_ids.setdefault(tipo, set()).add(int(id_4d))
            if not batch_instances:
                return
            written = _upsert_teste(batch_instances)
            count += written
            for obj in batch_instances:
                _bump_count(rows_by_tipo, str(obj.tipo_doc_id or ""))
            if len(family) > 1:
                _drop_sibling_headers(batch_instances, family)

        prune = False
        if slices:
            prune = full
            for slice_ in slices:
                seen_ids.setdefault(slice_.tipo_doc, set())
                _, last_columns, fetch_msg, wm_rows = _run_fetch(
                    spec.source,
                    start_after_pk=_max_header_id_4d([slice_.tipo_doc]),
                    extra_where=slice_.extra_where,
                    update_watermark=False,
                    on_batch=lambda bd, _wm: _process_batch(bd, slice_.tipo_doc),
                    **fetch_kwargs,
                )
                label = slice_.serie or "default"
                fetch_parts.append(f"{slice_.tipo_doc}[{label}]: {fetch_msg}")
                watermark_rows.extend(wm_rows)
            _commit_watermark(spec.source, last_columns, watermark_rows)
            fetch_msg = "; ".join(fetch_parts)
        else:
            tipos_for_max = list(enabled)
            if tipos_filter is not None:
                tipos_for_max = [t for t in tipos_for_max if t in tipos_filter]
            _, _, fetch_msg, _ = _run_fetch(
                spec.source,
                start_after_pk=_max_header_id_4d(tipos_for_max),
                on_batch=lambda bd, _wm: _process_batch(bd, None),
                **fetch_kwargs,
            )
            prune = full
            if prune:
                for tipo in enabled:
                    if tipos_filter is None or tipo in tipos_filter:
                        seen_ids.setdefault(tipo, set())

        pruned = 0
        if prune:
            for tipo, ids in seen_ids.items():
                pruned += _prune_headers_missing_from_4d(tipo, ids)
        result.rows = count
        result.rows_by_tipo = dict(rows_by_tipo)
        by_tipo = _format_rows_by_tipo_inline(rows_by_tipo)
        extra = f", {pruned} testate rimosse (non più in 4D)" if pruned else ""
        result.message = (
            f"{spec.source} -> teste_documenti: {fetch_msg} "
            f"({count} testate{by_tipo}{extra})."
        )
        return result
    except SyncCancelledError:
        raise
    except Exception as exc:
        result.ok = False
        result.message = f"{spec.source}: {exc}"
        return result


def sync_detail_source(
    spec: DetailSourceSpec,
    *,
    header_tipo_by_id_4d: dict[int, str],
    batch_size: int = DEFAULT_SYNC_BATCH_SIZE,
    now: datetime | None = None,
    tipos_filter: frozenset[str] | None = None,
    log_id: int | None = None,
    cancel_check: CancelCheck = None,
    full: bool = False,
) -> DocTableSyncResult:
    result = DocTableSyncResult(source=spec.source, target="righe_documenti")
    disabled = [
        t for t in _tipos_for_detail_spec(spec) if not is_documento_menu_enabled(t)
    ]
    enabled = _enabled_tipos_for_detail_spec(spec)
    if not enabled:
        result.message = _skip_message(spec.source, "righe_documenti", disabled)
        return result

    now = now or timezone.now()
    try:
        header_spec = _header_spec_for_detail(spec)
        slices: list[SerieImportSlice] = []
        if header_spec is not None:
            slices = _slices_for_sync(
                header_spec,
                enabled=enabled,
                tipos_filter=tipos_filter,
                source_table=spec.source,
            )

        # Precarica PK teste per lookup (tipo_doc, id_4d) → TestaDocumento.pk
        testa_lookup: dict[tuple[str, int], int] = {
            (t, i): pk
            for t, i, pk in TestaDocumento.objects.filter(
                tipo_doc_id__in=_tipi_for_detail(spec)
            ).values_list("tipo_doc_id", "id_4d", "pk")
        }

        skipped = 0
        total = 0
        rows_by_tipo: dict[str, int] = {}

        if full:
            tipos_to_clear = list(enabled)
            if tipos_filter is not None:
                tipos_to_clear = [t for t in tipos_to_clear if t in tipos_filter]
            for tipo in tipos_to_clear:
                if is_documento_menu_enabled(tipo):
                    RigaDocumento.objects.filter(testa__tipo_doc_id=tipo).delete()

        fetch_kwargs = dict(
            batch_size=batch_size,
            page_pk=spec.pk,
            page_size=DEFAULT_SYNC_PAGE_SIZE,
            full=full,
            incremental_by_pk=True,
            log_id=log_id,
            cancel_check=cancel_check,
        )

        def _process_line_batch(
            batch_dicts: Sequence[Mapping[str, Any]], tipo_fixed: str | None
        ) -> None:
            nonlocal skipped, total
            batch_righe: list[RigaDocumento] = []
            batch_tipos: list[str] = []
            for raw in batch_dicts:
                id_testa_4d = line_id_testa(raw, spec.header_pk)
                if id_testa_4d is None:
                    skipped += 1
                    continue
                tipo = tipo_fixed or resolve_detail_tipo_doc(
                    spec, raw, header_tipo_by_id_4d
                )
                if not tipo:
                    skipped += 1
                    continue
                if tipos_filter is not None and tipo not in tipos_filter:
                    skipped += 1
                    continue
                if not is_documento_menu_enabled(tipo):
                    skipped += 1
                    continue
                testa_pk = testa_lookup.get((tipo, id_testa_4d))
                if not testa_pk:
                    skipped += 1
                    continue
                mapped = map_line_row(raw)
                id_4d = mapped.get("id_4d")
                if id_4d is None:
                    skipped += 1
                    continue
                mapped["testa_id"] = testa_pk
                mapped["synced_at"] = now
                batch_righe.append(RigaDocumento(**mapped))
                batch_tipos.append(tipo)
            written = _upsert_righe(batch_righe)
            total += written
            for tipo in batch_tipos:
                _bump_count(rows_by_tipo, tipo)

        fetch_parts: list[str] = []
        if slices:
            watermark_rows: list[dict[str, Any]] = []
            last_columns: list[dict[str, Any]] = []
            for slice_ in slices:
                _, last_columns, fetch_msg, wm_rows = _run_fetch(
                    spec.source,
                    start_after_pk=_max_line_id_4d([slice_.tipo_doc]),
                    extra_where=slice_.extra_where,
                    update_watermark=False,
                    on_batch=lambda bd, _wm: _process_line_batch(bd, slice_.tipo_doc),
                    **fetch_kwargs,
                )
                label = slice_.serie or "default"
                fetch_parts.append(f"{slice_.tipo_doc}[{label}]: {fetch_msg}")
                watermark_rows.extend(wm_rows)
            _commit_watermark(spec.source, last_columns, watermark_rows)
            fetch_msg = "; ".join(fetch_parts)
        else:
            tipos_for_max = list(enabled)
            if tipos_filter is not None:
                tipos_for_max = [t for t in tipos_for_max if t in tipos_filter]
            _, _, fetch_msg, _ = _run_fetch(
                spec.source,
                start_after_pk=_max_line_id_4d(tipos_for_max),
                on_batch=lambda bd, _wm: _process_line_batch(bd, None),
                **fetch_kwargs,
            )

        skip_msg = f", {skipped} righe senza testata" if skipped else ""
        result.rows = total
        result.rows_by_tipo = dict(rows_by_tipo)
        by_tipo = _format_rows_by_tipo_inline(rows_by_tipo)
        result.message = (
            f"{spec.source} -> righe_documenti: {fetch_msg} "
            f"({total} righe{by_tipo}{skip_msg})."
        )
        return result
    except SyncCancelledError:
        raise
    except Exception as exc:
        result.ok = False
        result.message = f"{spec.source}: {exc}"
        return result


def _prune_headers_missing_from_4d(tipo_doc: str, keep_ids: set[int]) -> int:
    """Elimina testate 4D non più presenti nella lettura completa.

    Se keep_ids è vuoto non cancella nulla: una lettura 4D vuota per errore
    non deve svuotare il tipo.
    """
    if not keep_ids:
        return 0
    pks = list(
        TestaDocumento.objects.filter(tipo_doc_id=tipo_doc)
        .exclude(id_4d__in=list(keep_ids))
        .values_list("pk", flat=True)
    )
    if not pks:
        return 0
    TestaDocumento.objects.filter(pk__in=pks).delete()
    return len(pks)


def _drop_sibling_headers(
    instances: Sequence[TestaDocumento], family: Sequence[str]
) -> int:
    """Elimina copie sulla stessa ID_Testa 4D negli altri tipi della famiglia.

    Unique è (tipo_doc, id_4d): un preventivo passato da PRV a PRF lascerebbe
    il vecchio record PRV. Le righe seguono in CASCADE.
    """
    chosen: dict[int, str] = {}
    family_set = set(family)
    for obj in instances:
        if obj.tipo_doc_id in family_set and obj.id_4d is not None:
            chosen[int(obj.id_4d)] = obj.tipo_doc_id
    if not chosen:
        return 0
    stale_pks = [
        pk
        for pk, tipo, id_4d in TestaDocumento.objects.filter(
            tipo_doc_id__in=family_set,
            id_4d__in=list(chosen.keys()),
        ).values_list("pk", "tipo_doc_id", "id_4d")
        if chosen.get(int(id_4d)) not in {None, tipo}
    ]
    if not stale_pks:
        return 0
    deleted, _ = TestaDocumento.objects.filter(pk__in=stale_pks).delete()
    return deleted


def _tipi_for_detail(spec: DetailSourceSpec) -> tuple[str, ...]:
    return _enabled_tipos_for_detail_spec(spec) or _tipos_for_detail_spec(spec)


def _build_tipo_map(tipos: Sequence[str]) -> dict[int, str]:
    """Mappa ID_Testa → TipoDoc per i tipi indicati (solo abilitati)."""
    enabled = [t for t in tipos if is_documento_menu_enabled(t)]
    if not enabled:
        return {}
    try:
        with transaction.atomic():
            return {
                int(id_4d): tipo
                for tipo, id_4d in TestaDocumento.objects.filter(
                    tipo_doc_id__in=enabled
                ).values_list("tipo_doc_id", "id_4d")
            }
    except Exception:
        return {}


def parse_only_selection(only: OnlySelection) -> list[str] | None:
    """Normalizza --only CLI, valori form o singolo token in lista piatta."""
    if only is None:
        return None
    raw_items = [only] if isinstance(only, str) else list(only)
    tokens: list[str] = []
    for item in raw_items:
        for part in str(item).split(","):
            token = part.strip()
            if token:
                tokens.append(token)
    return tokens or None


def _selection_to_tipos(tokens: Sequence[str]) -> frozenset[str]:
    tipos: set[str] = set()
    for token in tokens:
        upper = token.strip().upper()
        if upper in DOC_MENU_FIELDS:
            tipos.add(upper)
        if upper in PREVENTIVI_TIPI or token in {"Preventivi", "Preventivi_Dettaglio"}:
            tipos.update(PREVENTIVI_TIPI)
        for spec in DEFAULT_TIPI_DOCUMENTO:
            if token in {spec["source_table_4d"], spec["source_detail_4d"]}:
                tipos.add(spec["codice"])
        if token in {"Fatture", "Fatture_Dettaglio"}:
            tipos.update(FATTURE_TIPI)
    for spec in HEADER_SOURCES:
        family = set(_tipos_for_header_spec(spec))
        if tipos & family:
            tipos.update(family)
    return frozenset(tipos)


def _lower_tokens(tokens: Sequence[str]) -> frozenset[str]:
    return frozenset(t.strip().lower() for t in tokens)


def _spec_matches_header(
    spec: HeaderSourceSpec,
    tokens: Sequence[str] | None,
    tipos: frozenset[str],
) -> bool:
    if tokens is None:
        return True
    if spec.source in tokens:
        return True
    lower = _lower_tokens(tokens)
    if lower & {"teste_documenti", "headers"}:
        return True
    spec_tipos = set(_tipos_for_header_spec(spec))
    return bool(spec_tipos & tipos)


def _spec_matches_detail(
    spec: DetailSourceSpec,
    tokens: Sequence[str] | None,
    tipos: frozenset[str],
) -> bool:
    if tokens is None:
        return True
    if spec.source in tokens:
        return True
    lower = _lower_tokens(tokens)
    if lower & {"righe_documenti", "details", "lines"}:
        return True
    spec_tipos = set(_tipos_for_detail_spec(spec))
    return bool(spec_tipos & tipos)


def _sources_for_tipo(tipo: str) -> tuple[str, str]:
    if tipo in PREVENTIVI_TIPI:
        return "Preventivi", "Preventivi_Dettaglio"
    for spec in DEFAULT_TIPI_DOCUMENTO:
        if spec["codice"] == tipo:
            return spec["source_table_4d"], spec["source_detail_4d"]
    return tipo, f"{tipo}_Dettaglio"


def sync_tab_porto(
    batch_size: int = DEFAULT_SYNC_BATCH_SIZE, only: str | None = None, full: bool = False
) -> SyncResult:
    """Mirror 4D TabPorto → tab_porto (lookup Porto1 / Porto)."""
    return sync_tables(
        PORTO_TABLES,
        batch_size=batch_size,
        only=only,
        full=full,
        success_message="Sincronizzazione TabPorto completata.",
    )


def _append_porto_lookup(summary: DocumentiSyncResult, batch_size: int, full: bool) -> None:
    result = sync_tab_porto(batch_size=batch_size, full=full)
    for table in result.tables:
        summary.tables.append(
            DocTableSyncResult(
                source=table.source,
                target=table.target,
                rows=table.rows,
                ok=table.ok,
                message=table.message,
            )
        )
        if not table.ok:
            summary.ok = False


def sync_documenti(
    batch_size: int = DEFAULT_SYNC_BATCH_SIZE,
    only: OnlySelection = None,
    log_id: int | None = None,
    cancel_check: CancelCheck = None,
    full: bool = False,
) -> DocumentiSyncResult:
    summary = DocumentiSyncResult()
    now = timezone.now()

    try:
        ensure_documenti_tables()
    except Exception as exc:
        summary.ok = False
        summary.message = f"Impossibile preparare tabelle documenti: {exc}"
        return summary

    tokens = parse_only_selection(only)
    tipos = _selection_to_tipos(tokens) if tokens else frozenset()

    if tokens:
        for tipo in sorted(tipos):
            if not is_documento_menu_enabled(tipo):
                header_source, detail_source = _sources_for_tipo(tipo)
                summary.tables.append(
                    _skipped_table_result(header_source, "teste_documenti", (tipo,))
                )
                summary.tables.append(
                    _skipped_table_result(detail_source, "righe_documenti", (tipo,))
                )

        enabled_tipos = frozenset(t for t in tipos if is_documento_menu_enabled(t))
        if tipos and not enabled_tipos:
            summary.message = "Nessun tipo selezionato è abilitato in parametri programma."
            return summary
        tipos_filter = enabled_tipos if tipos else None
    else:
        tipos_filter = None
        enabled_tipos = frozenset()

    header_specs = [
        s for s in HEADER_SOURCES if _spec_matches_header(s, tokens, tipos)
    ]
    detail_specs = [
        s for s in DETAIL_SOURCES if _spec_matches_detail(s, tokens, tipos)
    ]

    if tipos_filter is not None:
        header_specs = [
            s
            for s in header_specs
            if set(_tipos_for_header_spec(s)) & tipos_filter
        ]
        detail_specs = [
            s
            for s in detail_specs
            if set(_tipos_for_detail_spec(s)) & tipos_filter
        ]

    if tokens and not header_specs and not detail_specs:
        summary.ok = False
        summary.message = f"Nessuna sorgente selezionata ({', '.join(tokens)})."
        return summary

    if header_specs:
        _append_porto_lookup(summary, batch_size=batch_size, full=True)

    for spec in header_specs:
        if _is_cancelled(log_id, cancel_check):
            summary.cancelled = True
            summary.ok = False
            summary.message = CANCELLED_MESSAGE
            return summary
        try:
            table_result = sync_header_source(
                spec,
                batch_size=batch_size,
                now=now,
                tipos_filter=tipos_filter,
                log_id=log_id,
                cancel_check=cancel_check,
                full=full,
            )
        except SyncCancelledError:
            summary.cancelled = True
            summary.ok = False
            summary.message = CANCELLED_MESSAGE
            return summary
        summary.tables.append(table_result)
        summary.teste_count += table_result.rows
        _merge_counts(summary.teste_by_tipo, table_result.rows_by_tipo)
        if not table_result.ok:
            summary.ok = False

    # Dopo le testate: mappa tipo per dettagli che condividono la tabella 4D.
    tipo_maps: dict[str, dict[int, str]] = {}
    for spec in detail_specs:
        family = _tipos_for_detail_spec(spec)
        if spec.tipo_doc is not None and len(family) <= 1:
            continue
        tipo_map = _build_tipo_map(family)
        if tipos_filter is not None:
            tipo_map = {
                id_4d: tipo
                for id_4d, tipo in tipo_map.items()
                if tipo in tipos_filter
            }
        tipo_maps[spec.source] = tipo_map

    for spec in detail_specs:
        if _is_cancelled(log_id, cancel_check):
            summary.cancelled = True
            summary.ok = False
            summary.message = CANCELLED_MESSAGE
            return summary
        try:
            table_result = sync_detail_source(
                spec,
                header_tipo_by_id_4d=tipo_maps.get(spec.source, {}),
                batch_size=batch_size,
                now=now,
                tipos_filter=tipos_filter,
                log_id=log_id,
                cancel_check=cancel_check,
                full=full,
            )
        except SyncCancelledError:
            summary.cancelled = True
            summary.ok = False
            summary.message = CANCELLED_MESSAGE
            return summary
        summary.tables.append(table_result)
        summary.righe_count += table_result.rows
        _merge_counts(summary.righe_by_tipo, table_result.rows_by_tipo)
        if not table_result.ok:
            summary.ok = False

    if not summary.tables:
        summary.ok = False
        label = ", ".join(tokens) if tokens else str(only)
        summary.message = f"Nessuna sorgente selezionata ({label})."
        return summary

    if summary.ok:
        mode = "completa" if full else "incrementale"
        summary.message = (
            f"Sincronizzazione documenti ({mode}) completata: "
            f"{summary.teste_count} testate, {summary.righe_count} righe."
        )
        breakdown = format_counts_by_tipo(summary.teste_by_tipo, summary.righe_by_tipo)
        if breakdown:
            summary.message = f"{summary.message}\n{breakdown}"
    else:
        failed = [t.source for t in summary.tables if not t.ok]
        summary.message = "Sincronizzazione incompleta: " + ", ".join(failed)
    return summary


def sync_documenti_as_sync_result(
    batch_size: int = DEFAULT_SYNC_BATCH_SIZE,
    only: OnlySelection = None,
    cancel_check: CancelCheck = None,
    full: bool = False,
) -> SyncResult:
    """Adapter per SYNC_4D_STEPS in core.views."""
    doc = sync_documenti(
        batch_size=batch_size,
        only=only,
        cancel_check=cancel_check,
        full=full,
    )
    from apps.core.sync_4d import TableSyncResult

    tables = [
        TableSyncResult(
            source=t.source,
            target=t.target,
            rows=t.rows,
            ok=t.ok,
            message=t.message,
        )
        for t in doc.tables
    ]
    return SyncResult(ok=doc.ok, tables=tables, message=doc.message)
