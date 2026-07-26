from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from typing import Any, Callable

from django.db import connection, transaction

from apps.core.quattro_d import open_4d_connection

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
}


@dataclass
class TableSyncResult:
    source: str
    target: str
    columns: int = 0
    rows: int = 0
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
        cur.execute(f"DROP TABLE IF EXISTS {quote_ident(target)} CASCADE;")
        cur.execute(ddl)
        if post_create:
            post_create(cur, target)


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

    if isinstance(value, (bytes, bytearray)):
        return value.decode("utf-8", errors="replace").replace("\x00", "")

    if isinstance(value, str):
        return value.replace("\x00", "")

    return value


def fetch_4d_rows(cursor, source: str, columns: list[dict[str, Any]], batch_size: int = 2000):
    col_4d = ", ".join(f"[{c['name']}]" for c in columns)
    cursor.execute(f"SELECT {col_4d} FROM [{source}]")
    while True:
        rows = cursor.fetchmany(batch_size)
        if not rows:
            break
        yield rows


def sync_table(
    source: str,
    target: str,
    pk: str,
    batch_size: int = 2000,
    recreate: bool = True,
    post_create: Callable | None = None,
) -> TableSyncResult:
    result = TableSyncResult(source=source, target=target)
    try:
        with open_4d_connection(timeout=30) as odbc_conn:
            odbc_cur = odbc_conn.cursor()
            columns = introspect_columns(odbc_cur, source)
            result.columns = len(columns)

            if recreate:
                ensure_postgres_table(target, columns, pk, post_create=post_create)
            else:
                with connection.cursor() as cur:
                    cur.execute(f"TRUNCATE TABLE {quote_ident(target)};")

            insert_cols = [c["name"] for c in columns] + ["synced_at"]
            placeholders = ", ".join(["%s"] * len(insert_cols))
            insert_sql = (
                f"INSERT INTO {quote_ident(target)} ("
                + ", ".join(quote_ident(c) for c in insert_cols)
                + f") VALUES ({placeholders})"
            )

            total = 0
            now = datetime.now().astimezone()
            with connection.cursor() as pg_cur:
                for batch in fetch_4d_rows(odbc_cur, source, columns, batch_size=batch_size):
                    values = []
                    for row in batch:
                        mapped = [
                            normalize_value(row[idx], columns[idx]["pg_type"])
                            for idx in range(len(columns))
                        ]
                        mapped.append(now)
                        values.append(tuple(mapped))
                    with transaction.atomic():
                        pg_cur.executemany(insert_sql, values)
                    total += len(values)

            result.rows = total
            result.message = f"{source} -> {target}: {total} righe, {len(columns)} colonne."
            return result
    except Exception as exc:
        result.ok = False
        result.message = f"{source}: {exc}"
        return result


def sync_tables(
    specs: tuple[dict[str, Any], ...],
    batch_size: int = 2000,
    only: str | None = None,
    success_message: str = "Sincronizzazione completata.",
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
