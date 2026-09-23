"""Paginazione SELECT 4D per tabelle oltre il limite ODBC (~60k)."""

from django.test import SimpleTestCase

from apps.core.sync_4d import _sql_pk_literal, fetch_4d_rows


class FakeCursor:
    def __init__(self, rows):
        self.rows = list(rows)
        self.sqls = []
        self._pending = []

    def execute(self, sql):
        self.sqls.append(sql)
        if "ORDER BY [ID]" not in sql:
            self._pending = list(self.rows)
            return
        bound = None
        token = "[ID] > "
        if token in sql:
            rest = sql.split(token, 1)[1]
            bound = int(rest.split()[0])
        data = self.rows
        if bound is not None:
            data = [r for r in data if r[0] > bound]
        self._pending = list(data)

    def fetchmany(self, n):
        out = self._pending[:n]
        self._pending = self._pending[n:]
        return out


class Fetch4dRowsPagingTests(SimpleTestCase):
    def test_unpaged_still_single_select(self):
        cur = FakeCursor([(1,), (2,), (3,)])
        batches = list(
            fetch_4d_rows(
                cur,
                "T",
                [{"name": "ID"}],
                batch_size=2,
            )
        )
        self.assertEqual(len(cur.sqls), 1)
        self.assertNotIn("ORDER BY", cur.sqls[0])
        self.assertEqual(batches, [[(1,), (2,)], [(3,)]])

    def test_pages_by_pk_with_multiple_queries(self):
        cur = FakeCursor([(i, "x") for i in range(1, 8)])
        batches = list(
            fetch_4d_rows(
                cur,
                "Primanota",
                [{"name": "ID"}, {"name": "X"}],
                batch_size=2,
                page_pk="ID",
                page_size=3,
            )
        )
        ids = [row[0] for batch in batches for row in batch]
        self.assertEqual(ids, [1, 2, 3, 4, 5, 6, 7])
        self.assertGreaterEqual(len(cur.sqls), 3)
        self.assertIn("ORDER BY [ID]", cur.sqls[0])
        self.assertNotIn("[ID] >", cur.sqls[0])
        self.assertIn("[ID] > 3", cur.sqls[1])
        self.assertIn("[ID] > 6", cur.sqls[2])

    def test_pages_by_pk_respects_start_after_pk(self):
        cur = FakeCursor([(i, "x") for i in range(1, 8)])
        batches = list(
            fetch_4d_rows(
                cur,
                "Primanota_Dettaglio",
                [{"name": "ID"}, {"name": "X"}],
                batch_size=10,
                page_pk="ID",
                page_size=10,
                start_after_pk=5,
            )
        )
        ids = [row[0] for batch in batches for row in batch]
        self.assertEqual(ids, [6, 7])
        self.assertIn("[ID] > 5", cur.sqls[0])

    def test_sql_pk_literal(self):
        self.assertEqual(_sql_pk_literal(12), "12")
        self.assertEqual(_sql_pk_literal(12.0), "12")
        self.assertEqual(_sql_pk_literal("AB'C"), "'AB''C'")

    def test_resolve_page_pk_falls_back_to_id_riga(self):
        cur = FakeCursor([(1, "a"), (2, "b")])
        batches = list(
            fetch_4d_rows(
                cur,
                "Preventivi_Dettaglio",
                [{"name": "ID_Riga"}, {"name": "X"}],
                batch_size=10,
                page_pk="ID",  # colonna assente: fallback su ID_Riga
                page_size=10,
            )
        )
        self.assertEqual([r[0] for b in batches for r in b], [1, 2])
        self.assertIn("ORDER BY [ID_Riga]", cur.sqls[0])

    def test_skips_invalid_odbc_datetime_and_keeps_row(self):
        rows = [
            (1, "ok", "2024-01-01"),
            (2, "bad", "poison"),
            (3, "ok", "2024-01-03"),
        ]
        cur = PoisonDateCursor(rows, poison_ids={2}, date_col="DataConsegna")
        batches = list(
            fetch_4d_rows(
                cur,
                "Ordini_Vendita",
                [
                    {"name": "ID", "type_name": "INT32", "pg_type": "integer"},
                    {"name": "X", "type_name": "CLOB", "pg_type": "text"},
                    {
                        "name": "DataConsegna",
                        "type_name": "TIMESTAMP",
                        "pg_type": "timestamp",
                    },
                ],
                batch_size=10,
                page_pk="ID",
                page_size=10,
            )
        )
        flat = [row for batch in batches for row in batch]
        self.assertEqual([r[0] for r in flat], [1, 2, 3])
        self.assertIsNone(flat[1][2])
        self.assertEqual(flat[1][1], "bad")


class PoisonDateCursor:
    """Simula il driver 4D: fetchmany fallisce su date con anno fuori range."""

    def __init__(self, rows, poison_ids, date_col="DataConsegna"):
        self.rows = list(rows)
        self.poison_ids = set(poison_ids)
        self.date_col = date_col
        self.sqls = []
        self._pending = []
        self._single = None

    def execute(self, sql):
        self.sqls.append(sql)
        self._single = None
        self._pending = []
        if "WHERE [ID] =" in sql:
            pk = int(sql.split("WHERE [ID] = ", 1)[1].split()[0])
            row = next((r for r in self.rows if r[0] == pk), None)
            if "SELECT [DataConsegna]" in sql and pk in self.poison_ids:
                self._single = "poison"
            else:
                if row is None:
                    self._single = None
                elif "SELECT [DataConsegna]" in sql:
                    self._single = (row[2],)
                elif "SELECT [ID], [X]" in sql or "SELECT [ID], [X] FROM" in sql:
                    self._single = (row[0], row[1])
                elif sql.strip().startswith("SELECT [ID] FROM"):
                    self._single = (row[0],)
                else:
                    self._single = (row[0], row[1])
            return

        bound = None
        if "[ID] > " in sql:
            bound = int(sql.split("[ID] > ", 1)[1].split()[0])
        data = self.rows
        if bound is not None:
            data = [r for r in data if r[0] > bound]
        if sql.strip().startswith("SELECT [ID] FROM"):
            self._pending = [(r[0],) for r in data]
        else:
            self._pending = list(data)

    def fetchmany(self, n):
        if self._single is not None:
            row = self.fetchone()
            return [] if row is None else [row]
        out = []
        for _ in range(n):
            if not self._pending:
                break
            row = self._pending[0]
            if len(row) > 1 and row[0] in self.poison_ids:
                raise ValueError("year must be in 1..9999, not 20224")
            out.append(self._pending.pop(0))
        return out

    def fetchone(self):
        if self._single == "poison":
            self._single = None
            raise ValueError("year must be in 1..9999, not 20224")
        if self._single is not None:
            row = self._single
            self._single = None
            return row
        rows = self.fetchmany(1)
        return rows[0] if rows else None
