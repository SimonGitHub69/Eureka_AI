"""Sync incrementale 4D basato su Data/Ora Modifica."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Any, Mapping, Sequence

from django.utils import timezone

# Alias colonne 4D per data/ora modifica (come negli altri mapping).
MODIFICA_DATA_ALIASES: tuple[str, ...] = (
    "DataModifica",
    "Data_Modifica",
)
MODIFICA_ORA_ALIASES: tuple[str, ...] = (
    "OraModifica",
    "Ora_Modifica",
)
MODIFICA_SINGLE_ALIASES: tuple[str, ...] = (
    "Data e Ora Modifica",
    "DataOraModifica",
    "Data_Ora_Modifica",
    "TimestampModifica",
    "LastModified",
)


@dataclass(frozen=True)
class ModificaColumnSpec:
    """Colonne modifica rilevate su una tabella 4D."""

    mode: str  # "split" | "single"
    data_col: str | None = None
    ora_col: str | None = None
    single_col: str | None = None
    data_pg_type: str | None = None


# Fallback esplicito per tabelle 4D quando l'introspection ODBC non rileva le colonne.
MODIFICA_TABLE_OVERRIDES: dict[str, ModificaColumnSpec] = {
    "Azienda": ModificaColumnSpec(
        mode="split",
        data_col="DataModifica",
        ora_col="OraModifica",
    ),
    "Clienti": ModificaColumnSpec(
        mode="split",
        data_col="DataModifica",
        ora_col="OraModifica",
        data_pg_type="timestamp",
    ),
    "Fornitori": ModificaColumnSpec(
        mode="split",
        data_col="DataModifica",
        ora_col="OraModifica",
        data_pg_type="timestamp",
    ),

    "Gruppo_Cli_For": ModificaColumnSpec(
        mode="split",
        data_col="DataModifica",
        ora_col="OraModifica",
        data_pg_type="timestamp",
    ),
    "DestCliFor": ModificaColumnSpec(
        mode="split",
        data_col="DataModifica",
        ora_col="OraModifica",
        data_pg_type="timestamp",
    ),
    "Primanota": ModificaColumnSpec(
        mode="split",
        data_col="DataModifica",
        ora_col="OraModifica",
        data_pg_type="timestamp",
    ),
    "Primanota_Dettaglio": ModificaColumnSpec(
        mode="split",
        data_col="DataModifica",
        ora_col="OraModifica",
        data_pg_type="timestamp",
    ),
}


def _column_names(columns: Sequence[Mapping[str, Any] | str]) -> set[str]:
    names: set[str] = set()
    for col in columns:
        if isinstance(col, str):
            names.add(col)
        else:
            names.add(col["name"])
    return names


def _pick_column(names: set[str], aliases: Sequence[str]) -> str | None:
    """Risolve un alias sul nome ODBC effettivo (match case-insensitive)."""
    by_fold = {name.casefold(): name for name in names}
    for alias in aliases:
        actual = by_fold.get(alias.casefold())
        if actual is not None:
            return actual
    return None


def _pg_type_for(columns: Sequence[Mapping[str, Any] | str], name: str) -> str | None:
    target = name.casefold()
    for col in columns:
        if isinstance(col, str):
            if col.casefold() == target:
                return None
            continue
        if (col.get("name") or "").casefold() == target:
            return col.get("pg_type")
    return None


def _resolve_table_override(
    columns: Sequence[Mapping[str, Any] | str],
    names: set[str],
    source_table: str,
) -> ModificaColumnSpec | None:
    """Applica override tabella risolvendo i nomi colonna dall'introspection ODBC."""
    override = MODIFICA_TABLE_OVERRIDES.get(source_table)
    if override is None:
        return None

    if override.mode == "single" and override.single_col:
        single = _pick_column(names, (override.single_col, *MODIFICA_SINGLE_ALIASES))
        return ModificaColumnSpec(mode="single", single_col=single or override.single_col)

    data_aliases: tuple[str, ...] = (
        *(alias for alias in (override.data_col,) if alias),
        *MODIFICA_DATA_ALIASES,
    )
    ora_aliases: tuple[str, ...] = (
        *(alias for alias in (override.ora_col,) if alias),
        *MODIFICA_ORA_ALIASES,
    )
    data_col = _pick_column(names, data_aliases)
    ora_col = _pick_column(names, ora_aliases)
    data_pg_type = _pg_type_for(columns, data_col) if data_col else override.data_pg_type
    return ModificaColumnSpec(
        mode="split",
        data_col=data_col or override.data_col,
        ora_col=ora_col or override.ora_col,
        data_pg_type=data_pg_type,
    )


def _data_col_is_date(spec: ModificaColumnSpec) -> bool:
    return spec.data_pg_type == "date"


def _apply_source_table_override(
    spec: ModificaColumnSpec,
    source_table: str | None,
) -> ModificaColumnSpec:
    """Applica override tabella (pg_type split date+ora, ora_col mancante)."""
    if not source_table:
        return spec
    override = MODIFICA_TABLE_OVERRIDES.get(source_table)
    if override is None or override.mode != "split" or spec.mode != "split":
        return spec

    ora_col = spec.ora_col
    if not ora_col and override.ora_col:
        ora_col = override.ora_col

    # Prefer ODBC introspection pg_type: {d}/{t} on TIMESTAMP columns causes ODBC 1108.
    data_pg_type = spec.data_pg_type
    if data_pg_type is None and override.data_pg_type:
        data_pg_type = override.data_pg_type

    if ora_col == spec.ora_col and data_pg_type == spec.data_pg_type:
        return spec
    return ModificaColumnSpec(
        mode=spec.mode,
        data_col=spec.data_col,
        ora_col=ora_col,
        single_col=spec.single_col,
        data_pg_type=data_pg_type,
    )


def detect_modifica_columns(
    columns: Sequence[Mapping[str, Any] | str],
    *,
    source_table: str | None = None,
) -> ModificaColumnSpec | None:
    """Individua colonne modifica nella introspection ODBC."""
    names = _column_names(columns)
    single = _pick_column(names, MODIFICA_SINGLE_ALIASES)
    if single:
        return ModificaColumnSpec(mode="single", single_col=single)

    data_col = _pick_column(names, MODIFICA_DATA_ALIASES)
    ora_col = _pick_column(names, MODIFICA_ORA_ALIASES)
    data_pg_type = _pg_type_for(columns, data_col) if data_col else None
    if data_col and ora_col:
        return _apply_source_table_override(
            ModificaColumnSpec(
                mode="split",
                data_col=data_col,
                ora_col=ora_col,
                data_pg_type=data_pg_type,
            ),
            source_table,
        )
    if data_col:
        return _apply_source_table_override(
            ModificaColumnSpec(
                mode="split",
                data_col=data_col,
                ora_col=None,
                data_pg_type=data_pg_type,
            ),
            source_table,
        )
    if source_table:
        return _resolve_table_override(columns, names, source_table)
    return None


def _as_naive(dt: datetime | None) -> datetime | None:
    """Normalize to naive local datetime (4D has no TZ; USE_TZ may return aware)."""
    if dt is None:
        return None
    if timezone.is_aware(dt):
        dt = timezone.make_naive(timezone.localtime(dt))
    return dt.replace(microsecond=0)


def _as_date(value: Any) -> date | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        naive = _as_naive(value)
        assert naive is not None
        return naive.date()
    if isinstance(value, date):
        return value
    return None


def _as_time(value: Any) -> time | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        naive = _as_naive(value)
        assert naive is not None
        return naive.time()
    if isinstance(value, time):
        return value.replace(microsecond=0)
    if isinstance(value, timedelta):
        total = int(value.total_seconds())
        hours, rem = divmod(abs(total), 3600)
        minutes, seconds = divmod(rem, 60)
        return time(hour=hours % 24, minute=minutes, second=seconds)
    return None


def _combine_date_time(data_value: Any, ora_value: Any) -> datetime | None:
    d = _as_date(data_value)
    if d is None:
        return None
    t = _as_time(ora_value) or time.min
    return datetime.combine(d, t)


def _should_combine_split(
    spec: ModificaColumnSpec,
    data_value: Any,
    ora_value: Any,
) -> bool:
    """True quando DataModifica/OraModifica vanno combinati (Azienda e simili)."""
    if not spec.ora_col or ora_value in (None, ""):
        return False
    if _data_col_is_date(spec):
        return True
    if not isinstance(data_value, datetime):
        return True
    naive = _as_naive(data_value)
    assert naive is not None
    return naive.time() == time.min


def parse_4d_modifica(
    row: Mapping[str, Any],
    *,
    spec: ModificaColumnSpec | None = None,
    columns: Sequence[Mapping[str, Any] | str] | None = None,
) -> datetime | None:
    """Combina Data + Ora Modifica (o colonna unica) in datetime naive."""
    if spec is None:
        if columns is None:
            return None
        spec = detect_modifica_columns(columns)
        if spec is None:
            return None

    if spec.mode == "single" and spec.single_col:
        value = row.get(spec.single_col)
        if isinstance(value, datetime):
            return _as_naive(value)
        if isinstance(value, date):
            return datetime.combine(value, time.min)
        return None

    if spec.data_col:
        data_value = row.get(spec.data_col)
        ora_value = row.get(spec.ora_col) if spec.ora_col else None
        if _should_combine_split(spec, data_value, ora_value):
            return _combine_date_time(data_value, ora_value)
        if isinstance(data_value, datetime):
            return _as_naive(data_value)
        if isinstance(data_value, date):
            return datetime.combine(data_value, time.min)
        return None
    return None


def _escape_ident(name: str) -> str:
    return f"[{name}]"


def _odbc_date(value: date) -> str:
    return f"{{d '{value:%Y-%m-%d}'}}"


def _odbc_time(value: time) -> str:
    return f"{{t '{value:%H:%M:%S}'}}"


def _odbc_timestamp(value: datetime) -> str:
    return f"{{ts '{value:%Y-%m-%d %H:%M:%S}'}}"


def build_incremental_where(spec: ModificaColumnSpec, watermark: datetime) -> str:
    """Costruisce clausola WHERE 4D ODBC (strict > watermark)."""
    wm = _as_naive(watermark)
    assert wm is not None

    if spec.mode == "single" and spec.single_col:
        col = _escape_ident(spec.single_col)
        return f"{col} > {_odbc_timestamp(wm)}"

    data_col = _escape_ident(spec.data_col or "")
    if _data_col_is_date(spec):
        if spec.ora_col:
            ora_col = _escape_ident(spec.ora_col)
            d = wm.date()
            t = wm.time().replace(microsecond=0)
            return (
                f"({data_col} > {_odbc_date(d)}) OR "
                f"(({data_col} = {_odbc_date(d)}) AND ({ora_col} > {_odbc_time(t)}))"
            )
        return f"{data_col} > {_odbc_date(wm.date())}"

    if spec.ora_col:
        # TIMESTAMP + OraModifica: DataModifica is often midnight; real time lives in
        # OraModifica (ODBC INTERVAL). Comparing OraModifica with {t} (or dual
        # equality with {ts} midnight) causes SQLExecDirectW 1108 on Clienti/Fornitori.
        # Use date-floor >= on DataModifica only; OraModifica still feeds watermark
        # via parse_4d_modifica. Upsert makes same-day re-fetch safe.
        midnight = datetime.combine(wm.date(), time.min)
        return f"{data_col} >= {_odbc_timestamp(midnight)}"

    return f"{data_col} > {_odbc_timestamp(wm)}"


def get_watermark(source_table: str) -> datetime | None:
    from apps.core.models.sync_watermark import SyncWatermark

    row = SyncWatermark.objects.filter(source_table=source_table).first()
    if row is None:
        return None
    # DateTimeField + USE_TZ returns aware UTC; 4D/ODBC modifica is naive local.
    return _as_naive(row.last_modifica)


def set_watermark(source_table: str, dt: datetime) -> None:
    from apps.core.models.sync_watermark import SyncWatermark

    naive = _as_naive(dt)
    assert naive is not None
    SyncWatermark.objects.update_or_create(
        source_table=source_table,
        defaults={"last_modifica": naive},
    )


def clear_all_watermarks() -> int:
    from apps.core.models.sync_watermark import SyncWatermark

    deleted, _ = SyncWatermark.objects.all().delete()
    return deleted


def is_newer_than_watermark(
    row: Mapping[str, Any],
    *,
    spec: ModificaColumnSpec,
    watermark: datetime | None,
) -> bool:
    """True se la riga ha modifica strettamente successiva al watermark."""
    wm = _as_naive(watermark)
    if wm is None:
        return True
    row_mod = parse_4d_modifica(row, spec=spec)
    if row_mod is None:
        return True
    return row_mod > wm


def max_modifica_from_rows(
    rows: Sequence[Mapping[str, Any]],
    *,
    spec: ModificaColumnSpec,
) -> datetime | None:
    best: datetime | None = None
    for row in rows:
        dt = _as_naive(parse_4d_modifica(row, spec=spec))
        if dt is None:
            continue
        if best is None or dt > best:
            best = dt
    return best


def ensure_modifica_columns_in_list(
    columns: list[dict[str, Any]],
    spec: ModificaColumnSpec | None,
) -> list[dict[str, Any]]:
    """Aggiunge colonne modifica mancanti dall'introspection ODBC (override tabella)."""
    if spec is None:
        return columns

    names = {col["name"] for col in columns}
    extra: list[dict[str, Any]] = []
    if spec.mode == "single" and spec.single_col and spec.single_col not in names:
        extra.append(
            {"name": spec.single_col, "type_name": "TIMESTAMP", "pg_type": "timestamp"}
        )
    elif spec.mode == "split":
        if spec.data_col and spec.data_col not in names:
            pg_type = spec.data_pg_type or "timestamp"
            type_name = "DATE" if pg_type == "date" else "TIMESTAMP"
            extra.append({"name": spec.data_col, "type_name": type_name, "pg_type": pg_type})
        if spec.ora_col and spec.ora_col not in names:
            extra.append({"name": spec.ora_col, "type_name": "TIME", "pg_type": "time"})
    return columns + extra


def format_incremental_message(
    rows: int,
    *,
    since: datetime | None,
    full: bool = False,
    fallback_full: bool = False,
    fallback_reason: str | None = None,
) -> str:
    if full:
        return f"Sincronizzazione completa: {rows} righe importate."
    if fallback_full:
        if fallback_reason == "first_import":
            return (
                f"Sincronizzazione completa (primo import, watermark assente): "
                f"{rows} righe importate."
            )
        if fallback_reason == "modifica_values_empty":
            return (
                f"Sincronizzazione completa (colonne modifica senza valori utilizzabili): "
                f"{rows} righe importate."
            )
        if fallback_reason == "no_modifica_columns":
            return (
                f"Sincronizzazione completa (colonne modifica assenti): "
                f"{rows} righe importate."
            )
        return (
            f"Sincronizzazione completa (colonne modifica assenti o primo import): "
            f"{rows} righe importate."
        )
    if since is None:
        return f"Sync incrementale: {rows} righe aggiornate."
    since_local = _as_naive(since)
    assert since_local is not None
    return (
        f"Sync incrementale: {rows} righe aggiornate "
        f"(da {since_local:%Y-%m-%d %H:%M:%S})"
    )


def add_sync_mode_arguments(parser) -> None:
    """Argomenti CLI comuni: default incrementale, --full forza reimport."""
    parser.add_argument(
        "--full",
        action="store_true",
        help="Sincronizzazione completa (ricrea/reimporta tutte le righe).",
    )


def sync_full_from_request(request) -> bool:
    """True se l'utente ha richiesto sync completo (UI o POST)."""
    if request.POST.get("full_sync") == "on":
        return True
    if request.POST.get("incremental_only") == "on":
        return False
    return False


def sync_full_from_options(options: dict) -> bool:
    return bool(options.get("full"))
