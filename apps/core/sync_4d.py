from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from time import perf_counter
from typing import Any, Callable

from django.db import connection, transaction

from apps.core.quattro_d import open_4d_connection
from apps.core.sync_incremental import (
    _as_naive,
    build_incremental_where,
    detect_modifica_columns,
    ensure_modifica_columns_in_list,
    format_incremental_message,
    get_watermark,
    is_newer_than_watermark,
    parse_4d_modifica,
    set_watermark,
)

logger = logging.getLogger(__name__)

TYPE_MAP = {
    "INT16": "smallint",
    "SMALLINT": "smallint",
    "INT32": "integer",
    "INTEGER": "integer",
    "INT64": "bigint",
    "BIGINT": "bigint",
    "DOUBLE PRECISION": "double precision",
    "DOUBLE": "double precision",
    "REAL": "real",
    "FLOAT": "double precision",
    "NUMERIC": "numeric",
    "DECIMAL": "numeric",
    "BOOLEAN": "boolean",
    "BIT": "boolean",
    "TIMESTAMP": "timestamp",
    "DATETIME": "timestamp",
    "DATE": "date",
    "TIME": "time",
    "INTERVAL": "time",
    "CLOB": "text",
    "VARCHAR": "text",
    "CHAR": "text",
    "WCHAR": "text",
    "LONGVARCHAR": "text",
    "WLONGVARCHAR": "text",
    "TEXT": "text",
    "BLOB": "bytea",
    "BINARY": "bytea",
    "VARBINARY": "bytea",
    "LONGVARBINARY": "bytea",
}


@dataclass
class TableSyncResult:
    source: str
    target: str
    columns: int = 0
    rows: int = 0
    skipped_empty_pk: int = 0
    ok: bool = True
    message: str = ""


@dataclass
class SyncResult:
    ok: bool = True
    tables: list[TableSyncResult] = field(default_factory=list)
    message: str = ""


def quote_ident(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def map_pg_type(type_name: str, column_size: int | None = None) -> str:
    key = (type_name or "").strip().upper()
    if key in TYPE_MAP:
        return TYPE_MAP[key]
    if "CHAR" in key or "CLOB" in key or "TEXT" in key:
        return "text"
    if "BLOB" in key or "BINARY" in key:
        return "bytea"
    if "INT" in key:
        return "integer"
    if "DOUBLE" in key or "FLOAT" in key or "REAL" in key:
        return "double precision"
    if "BOOL" in key or "BIT" in key:
        return "boolean"
    if "DATE" in key or "TIME" in key:
        return "timestamp"
    return "text"


def introspect_columns(cursor, table_name: str) -> list[dict[str, Any]]:
    cursor.columns(table=table_name)
    rows = cursor.fetchall()
    columns = []
    seen = set()
    for row in rows:
        name = row.column_name
        if not name or name in seen:
            continue
        seen.add(name)
        columns.append(
            {
                "name": name,
                "type_name": row.type_name or "CLOB",
                "column_size": getattr(row, "column_size", None),
                "pg_type": map_pg_type(row.type_name, getattr(row, "column_size", None)),
            }
        )
    if not columns:
        raise RuntimeError(f"Nessuna colonna trovata per la tabella 4D {table_name}.")
    return columns


def ensure_postgres_table(
    target: str,
    columns: list[dict[str, Any]],
    pk: str,
    post_create: Callable | None = None,
    *,
    drop_existing: bool = True,
) -> None:
    col_defs = []
    for col in columns:
        null_sql = "NOT NULL" if col["name"] == pk else ""
        col_defs.append(f"{quote_ident(col['name'])} {col['pg_type']} {null_sql}".strip())

    if pk not in {c["name"] for c in columns}:
        raise RuntimeError(f"Chiave primaria {pk} assente in {target}.")

    col_defs.append("synced_at timestamp with time zone NOT NULL DEFAULT NOW()")
    ddl = (
        f"CREATE TABLE IF NOT EXISTS {quote_ident(target)} (\n  "
        + ",\n  ".join(col_defs)
        + f",\n  PRIMARY KEY ({quote_ident(pk)})\n);"
    )

    with connection.cursor() as cur:
        if drop_existing:
            cur.execute(f"DROP TABLE IF EXISTS {quote_ident(target)} CASCADE;")
        cur.execute(ddl)
        if post_create:
            post_create(cur, target)


def _table_exists(target: str) -> bool:
    with connection.cursor() as cur:
        cur.execute(
            """
            SELECT EXISTS (
                SELECT 1
                FROM information_schema.tables
                WHERE table_schema = 'public' AND table_name = %s
            )
            """,
            [target],
        )
        return bool(cur.fetchone()[0])


def _existing_table_columns(target: str) -> dict[str, str]:
    with connection.cursor() as cur:
        cur.execute(
            """
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = %s
            """,
            [target],
        )
        return {row[0]: row[1] for row in cur.fetchall()}


def _can_reuse_existing_table(target: str, columns: list[dict[str, Any]]) -> bool:
    """True se la tabella mirror ha già le colonne attese e può essere TRUNCATE."""
    if not _table_exists(target):
        return False
    existing = _existing_table_columns(target)
    expected = {c["name"] for c in columns}
    expected.add("synced_at")
    return expected.issubset(set(existing.keys()))


def _build_upsert_sql(target: str, insert_cols: list[str], pk: str) -> str:
    update_cols = [c for c in insert_cols if c != pk]
    assignments = ", ".join(
        f"{quote_ident(c)} = EXCLUDED.{quote_ident(c)}" for c in update_cols
    )
    return (
        f"INSERT INTO {quote_ident(target)} ("
        + ", ".join(quote_ident(c) for c in insert_cols)
        + f") VALUES ({', '.join(['%s'] * len(insert_cols))}) "
        f"ON CONFLICT ({quote_ident(pk)}) DO UPDATE SET {assignments}"
    )


def normalize_value(value: Any, pg_type: str) -> Any:
    if value is None:
        return None

    if pg_type == "boolean":
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return bool(value)
        text = str(value).strip().lower()
        if text in {"1", "true", "t", "yes", "y", "s", "si"}:
            return True
        if text in {"0", "false", "f", "no", "n"}:
            return False
        return None

    if pg_type in {"smallint", "integer", "bigint"}:
        if isinstance(value, bool):
            return int(value)
        if value == "":
            return None
        return int(value)

    if pg_type in {"double precision", "real", "numeric"}:
        if value == "":
            return None
        if isinstance(value, Decimal):
            return float(value)
        return float(value)

    if pg_type == "date":
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, date):
            return value
        return value

    if pg_type == "time":
        if isinstance(value, datetime):
            return value.time()
        if isinstance(value, time):
            return value
        if isinstance(value, timedelta):
            total = int(value.total_seconds())
            hours, rem = divmod(abs(total), 3600)
            minutes, seconds = divmod(rem, 60)
            return time(hour=hours % 24, minute=minutes, second=seconds)
        return value

    if pg_type == "timestamp":
        if isinstance(value, date) and not isinstance(value, datetime):
            return datetime.combine(value, time.min)
        return value

    if pg_type == "bytea":
        if isinstance(value, memoryview):
            return bytes(value)
        if isinstance(value, (bytes, bytearray)):
            return bytes(value)
        return None

    if isinstance(value, (bytes, bytearray)):
        return value.decode("utf-8", errors="replace").replace("\x00", "")

    if isinstance(value, str):
        return value.replace("\x00", "")

    return value


def is_empty_pk_value(value: Any) -> bool:
    """True se la chiave/codice è None, vuota o solo spazi (non importabile)."""
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, (bytes, bytearray)):
        return not bytes(value).strip()
    return False


def pk_column_index(columns: list[dict[str, Any]], pk: str, source: str = "") -> int:
    for idx, col in enumerate(columns):
        if col["name"] == pk:
            return idx
    label = f" nella tabella 4D {source}" if source else ""
    raise RuntimeError(f"Chiave primaria {pk} assente{label}.")


def keep_rows_with_pk(rows, pk_idx: int) -> tuple[list, int]:
    """Esclude righe senza PK/codice. Ritorna (righe tenute, quante scartate)."""
    kept = []
    skipped = 0
    for row in rows:
        if is_empty_pk_value(row[pk_idx]):
            skipped += 1
            continue
        kept.append(row)
    return kept, skipped


def _format_empty_pk_skip_message(skipped: int, purged: int = 0) -> str:
    parts: list[str] = []
    if skipped == 1:
        parts.append("1 riga senza chiave/codice ignorata")
    elif skipped > 1:
        parts.append(f"{skipped} righe senza chiave/codice ignorate")
    if purged == 1:
        parts.append("1 riga senza chiave rimossa da PostgreSQL")
    elif purged > 1:
        parts.append(f"{purged} righe senza chiave rimosse da PostgreSQL")
    if not parts:
        return ""
    return " " + "; ".join(parts) + "."


def count_empty_pk_rows(target: str, pk: str) -> int:
    """Conta in PostgreSQL le righe con PK NULL o vuota."""
    try:
        with connection.cursor() as cur:
            cur.execute(
                f"SELECT COUNT(*) FROM {quote_ident(target)} "
                f"WHERE {quote_ident(pk)} IS NULL "
                f"OR BTRIM(CAST({quote_ident(pk)} AS text)) = ''"
            )
            return int(cur.fetchone()[0])
    except Exception:
        return 0


def delete_empty_pk_rows(target: str, pk: str) -> int:
    """Elimina da PostgreSQL le righe mirror con PK NULL o vuota (ghost rows)."""
    try:
        with connection.cursor() as cur:
            cur.execute(
                f"DELETE FROM {quote_ident(target)} "
                f"WHERE {quote_ident(pk)} IS NULL "
                f"OR BTRIM(CAST({quote_ident(pk)} AS text)) = ''"
            )
            return int(cur.rowcount or 0)
    except Exception:
        return 0


def fetch_4d_rows(
    cursor,
    source: str,
    columns: list[dict[str, Any]],
    batch_size: int = 2000,
    *,
    where_clause: str | None = None,
    page_pk: str | None = None,
    page_size: int = 10000,
):
    """Legge la tabella 4D a batch.

    Con ``page_pk`` spezza in query successive ``WHERE [pk] > last ORDER BY [pk]``.
    Il driver ODBC 4D su tabelle grandi (Primanota ~275k) dopo ~60k righe non
    chiude il cursore e il SELECT unico resta appeso.
    """
    col_4d = ", ".join(f"[{c['name']}]" for c in columns)
    if not page_pk:
        sql = f"SELECT {col_4d} FROM [{source}]"
        if where_clause:
            sql += f" WHERE {where_clause}"
        cursor.execute(sql)
        while True:
            rows = cursor.fetchmany(batch_size)
            if not rows:
                break
            yield rows
        return

    pk_idx = next(
        (i for i, col in enumerate(columns) if col["name"] == page_pk),
        None,
    )
    if pk_idx is None:
        raise RuntimeError(f"Colonna di paginazione {page_pk} assente in {source}.")

    last: Any = None
    while True:
        predicates: list[str] = []
        if where_clause:
            predicates.append(f"({where_clause})")
        if last is not None:
            predicates.append(f"[{page_pk}] > {_sql_pk_literal(last)}")
        sql = f"SELECT {col_4d} FROM [{source}]"
        if predicates:
            sql += " WHERE " + " AND ".join(predicates)
        sql += f" ORDER BY [{page_pk}]"
        cursor.execute(sql)
        fetched = 0
        page_last = last
        while fetched < page_size:
            take = min(batch_size, page_size - fetched)
            batch = cursor.fetchmany(take)
            if not batch:
                break
            fetched += len(batch)
            page_last = batch[-1][pk_idx]
            yield batch
        if fetched == 0 or fetched < page_size:
            break
        if page_last == last:
            break
        last = page_last


def _sql_pk_literal(value: Any) -> str:
    """Letterale SQL 4D per il bound di paginazione sulla PK."""
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return str(int(value)) if value.is_integer() else str(value)
    text = str(value).replace("'", "''")
    return f"'{text}'"


def sync_table(
    source: str,
    target: str,
    pk: str,
    batch_size: int = 2000,
    recreate: bool = True,
    post_create: Callable | None = None,
    exclude_columns: tuple[str, ...] | None = None,
    skip_blobs: bool = True,
    full: bool = False,
    page_by_pk: bool = False,
) -> TableSyncResult:
    result = TableSyncResult(source=source, target=target)
    attempted_incremental = False
    t_start = perf_counter()
    t_schema = 0.0
    t_transform = 0.0
    t_write = 0.0
    t_cleanup = 0.0
    batches = 0
    try:
        with open_4d_connection(timeout=30) as odbc_conn:
            t_phase = perf_counter()
            odbc_cur = odbc_conn.cursor()
            columns = introspect_columns(odbc_cur, source)
            excluded = {name for name in (exclude_columns or ()) if name}
            if skip_blobs:
                excluded.update(
                    c["name"]
                    for c in columns
                    if c["pg_type"] == "bytea"
                    or "BLOB" in (c["type_name"] or "").upper()
                    or "BINARY" in (c["type_name"] or "").upper()
                )
            if excluded:
                columns = [c for c in columns if c["name"] not in excluded]
            result.columns = len(columns)

            modifica_spec = detect_modifica_columns(columns, source_table=source)
            columns = ensure_modifica_columns_in_list(columns, modifica_spec)
            pk_idx = pk_column_index(columns, pk, source)
            watermark = get_watermark(source)
            since_watermark = watermark
            fallback_full = False
            fallback_reason: str | None = None
            use_incremental = (
                not full
                and modifica_spec is not None
                and watermark is not None
                and _table_exists(target)
            )

            if not full and modifica_spec is None:
                fallback_full = True
                fallback_reason = "no_modifica_columns"
            elif not full and watermark is None:
                fallback_full = True
                fallback_reason = "first_import"

            where_clause: str | None = None
            if use_incremental and modifica_spec and watermark:
                where_clause = build_incremental_where(modifica_spec, watermark)
                attempted_incremental = True

            do_full_import = full or fallback_full or not use_incremental

            insert_cols = [c["name"] for c in columns] + ["synced_at"]
            if do_full_import:
                if recreate:
                    if _can_reuse_existing_table(target, columns):
                        with connection.cursor() as cur:
                            cur.execute(f"TRUNCATE TABLE {quote_ident(target)};")
                    else:
                        ensure_postgres_table(
                            target,
                            columns,
                            pk,
                            post_create=post_create,
                            drop_existing=True,
                        )
                else:
                    with connection.cursor() as cur:
                        cur.execute(f"TRUNCATE TABLE {quote_ident(target)};")
                insert_sql = (
                    f"INSERT INTO {quote_ident(target)} ("
                    + ", ".join(quote_ident(c) for c in insert_cols)
                    + f") VALUES ({', '.join(['%s'] * len(insert_cols))})"
                )
            else:
                if not _table_exists(target):
                    ensure_postgres_table(
                        target,
                        columns,
                        pk,
                        post_create=post_create,
                        drop_existing=False,
                    )
                insert_sql = _build_upsert_sql(target, insert_cols, pk)
            t_schema = perf_counter() - t_phase

            total = 0
            skipped_empty_pk = 0
            max_seen_modifica: datetime | None = None
            now = datetime.now().astimezone()
            # Con DataModifica TIMESTAMP a mezzanotte + OraModifica la WHERE 4D
            # usa >= inizio giornata (OraModifica non è confrontabile via ODBC).
            # Filtriamo in Python le righe già coperte dal watermark.
            filter_wm = _as_naive(watermark) if use_incremental else None

            with connection.cursor() as pg_cur:
                for batch in fetch_4d_rows(
                    odbc_cur,
                    source,
                    columns,
                    batch_size=batch_size,
                    where_clause=where_clause,
                    page_pk=pk if page_by_pk else None,
                ):
                    batches += 1
                    batch, skipped_pk = keep_rows_with_pk(batch, pk_idx)
                    skipped_empty_pk += skipped_pk
                    values = []
                    t_map_batch = perf_counter()
                    for row in batch:
                        row_dict = {
                            columns[idx]["name"]: row[idx] for idx in range(len(columns))
                        }
                        if (
                            modifica_spec
                            and filter_wm is not None
                            and not is_newer_than_watermark(
                                row_dict, spec=modifica_spec, watermark=filter_wm
                            )
                        ):
                            continue
                        if modifica_spec:
                            row_mod = _as_naive(
                                parse_4d_modifica(row_dict, spec=modifica_spec)
                            )
                            if row_mod is not None and (
                                max_seen_modifica is None or row_mod > max_seen_modifica
                            ):
                                max_seen_modifica = row_mod
                        mapped = [
                            normalize_value(row[idx], columns[idx]["pg_type"])
                            for idx in range(len(columns))
                        ]
                        mapped.append(now)
                        values.append(tuple(mapped))
                    t_transform += perf_counter() - t_map_batch
                    if values:
                        t_write_batch = perf_counter()
                        with transaction.atomic():
                            pg_cur.executemany(insert_sql, values)
                        t_write += perf_counter() - t_write_batch
                        total += len(values)

            if modifica_spec and max_seen_modifica is not None:
                wm = _as_naive(watermark)
                if wm is None or max_seen_modifica > wm:
                    set_watermark(source, max_seen_modifica)
            elif (
                fallback_full
                and fallback_reason == "first_import"
                and modifica_spec is not None
            ):
                # Le colonne esistono ma il feed 4D non espone valori utilizzabili:
                # non possiamo generare watermark reali ne' usare un incrementale sicuro.
                fallback_reason = "modifica_values_empty"

            purged_empty_pk = 0
            t_clean = perf_counter()
            if _table_exists(target):
                purged_empty_pk = delete_empty_pk_rows(target, pk)
            t_cleanup = perf_counter() - t_clean

            skipped = f" (escluse {len(excluded)} colonne BLOB)" if excluded else ""
            skip_pk_msg = _format_empty_pk_skip_message(
                skipped_empty_pk, purged_empty_pk
            )
            mode_msg = format_incremental_message(
                total,
                since=since_watermark if use_incremental else None,
                full=full or (do_full_import and not fallback_full),
                fallback_full=fallback_full,
                fallback_reason=fallback_reason,
            )
            result.rows = total
            result.skipped_empty_pk = skipped_empty_pk
            total_elapsed = perf_counter() - t_start
            timings = (
                f" timings[schema={t_schema:.2f}s, map={t_transform:.2f}s, "
                f"write={t_write:.2f}s, cleanup={t_cleanup:.2f}s, "
                f"batches={batches}, total={total_elapsed:.2f}s]"
            )
            result.message = (
                f"{source} -> {target}: {mode_msg} "
                f"{len(columns)} colonne{skipped}.{skip_pk_msg}{timings}"
            )
            logger.info(result.message)
            return result
    except Exception as exc:
        if attempted_incremental and not full:
            retry = sync_table(
                source=source,
                target=target,
                pk=pk,
                batch_size=batch_size,
                recreate=True,
                post_create=post_create,
                exclude_columns=exclude_columns,
                skip_blobs=skip_blobs,
                full=True,
                page_by_pk=page_by_pk,
            )
            if retry.ok:
                retry.message = (
                    f"{source} -> {target}: sync incrementale fallita ({exc}); "
                    f"{retry.message}"
                )
                return retry
        result.ok = False
        result.message = f"{source}: {exc}"
        return result


def sync_tables(
    specs: tuple[dict[str, Any], ...],
    batch_size: int = 2000,
    only: str | None = None,
    success_message: str = "Sincronizzazione completata.",
    full: bool = False,
) -> SyncResult:
    summary = SyncResult()
    for spec in specs:
        if only and spec["source"] != only and spec["target"] != only:
            continue
        table_result = sync_table(
            source=spec["source"],
            target=spec["target"],
            pk=spec["pk"],
            batch_size=batch_size,
            recreate=True,
            post_create=spec.get("post_create"),
            exclude_columns=spec.get("exclude_columns"),
            skip_blobs=spec.get("skip_blobs", True),
            full=full,
            page_by_pk=bool(spec.get("page_by_pk")),
        )
        summary.tables.append(table_result)
        if not table_result.ok:
            summary.ok = False

    if not summary.tables:
        summary.ok = False
        summary.message = f"Nessuna tabella selezionata ({only})."
        return summary

    if summary.ok:
        summary.message = success_message
    else:
        failed = [t.source for t in summary.tables if not t.ok]
        summary.message = "Sincronizzazione incompleta: " + ", ".join(failed)
    return summary
