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
        cur = FakeCursor([(i,) for i in range(1, 8)])
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

    def test_sql_pk_literal(self):
        self.assertEqual(_sql_pk_literal(12), "12")
        self.assertEqual(_sql_pk_literal(12.0), "12")
        self.assertEqual(_sql_pk_literal("AB'C"), "'AB''C'")
