import re

from django.test import SimpleTestCase

from apps.core.ai_export import (
    build_articoli_fast_path_sql,
    ensure_sql_select_columns,
)


class EnsureSqlSelectColumnsTests(SimpleTestCase):
    _TRIM_FORNITORE_SQL = (
        'SELECT articoli."Codice", articoli."Descrizione", articoli."CodFornitore", '
        'TRIM(BOTH FROM CONCAT(COALESCE(fornitori."RagioneSociale1", \'\'), \' \', '
        'COALESCE(fornitori."RagioneSociale2", \'\'))) AS "RagioneSocialeFornitore" '
        'FROM articoli LEFT JOIN fornitori '
        'ON UPPER(fornitori."Codice") = UPPER(articoli."CodFornitore") '
        'WHERE "Descrizione" ILIKE \'%calzature%\''
    )

    _TRIM_PATTERN = re.compile(
        r'TRIM\(BOTH FROM CONCAT\('
        r'COALESCE\(fornitori\."RagioneSociale1", \'\'\), \' \', '
        r'COALESCE\(fornitori\."RagioneSociale2", \'\'\)\)\) AS "RagioneSocialeFornitore"'
    )

    def test_preserves_trim_when_all_export_columns_present(self):
        columns = ["Codice", "Descrizione", "CodFornitore", "RagioneSocialeFornitore"]
        result = ensure_sql_select_columns(self._TRIM_FORNITORE_SQL, columns)
        self.assertEqual(result, self._TRIM_FORNITORE_SQL)
        self.assertRegex(result, self._TRIM_PATTERN)
        self.assertNotIn('TRIM(BOTH,', result)

    def test_fornitore_join_is_case_insensitive(self):
        sql = build_articoli_fast_path_sql(
            ["Codice", "Descrizione", "CodFornitore", "RagioneSocialeFornitore"],
            ['"Descrizione" ILIKE \'%stivali%\''],
        )
        self.assertIn('UPPER(fornitori."Codice") = UPPER(articoli."CodFornitore")', sql)

    def test_fast_path_sql_survives_ensure_sql_select_columns(self):
        sql = build_articoli_fast_path_sql(
            ["Codice", "Descrizione", "CodFornitore", "RagioneSocialeFornitore"],
            ['"Descrizione" ILIKE \'%calzature%\''],
        )
        columns = ["Codice", "Descrizione", "CodFornitore", "RagioneSocialeFornitore"]
        result = ensure_sql_select_columns(sql, columns)
        self.assertRegex(result, self._TRIM_PATTERN)
        self.assertNotIn('TRIM(BOTH,', result)
        self.assertIn('LEFT JOIN fornitori', result)

    def test_adds_virtual_fornitore_column_with_trim_expression(self):
        sql = (
            'SELECT articoli."Codice", articoli."CodFornitore" '
            'FROM articoli LEFT JOIN fornitori '
            'ON UPPER(fornitori."Codice") = UPPER(articoli."CodFornitore")'
        )
        result = ensure_sql_select_columns(sql, ["RagioneSocialeFornitore"])
        self.assertRegex(result, self._TRIM_PATTERN)
        self.assertNotIn('TRIM(BOTH,', result)
