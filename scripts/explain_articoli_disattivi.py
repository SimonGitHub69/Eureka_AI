"""EXPLAIN ANALYZE for articoli disattivati + calzature synonyms."""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django

django.setup()

from django.db import connection

SYNONYM_WHERE = """
(
    "Descrizione" ILIKE '%calzature%'
    OR "Descrizione" ILIKE '%scarpe%'
    OR "Descrizione" ILIKE '%stivali%'
    OR "Descrizione" ILIKE '%sandali%'
    OR "Descrizione" ILIKE '%ciabatte%'
)
"""

QUERIES = {
    "disattivati_eq_true": f"""
EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT)
SELECT "Codice", "Descrizione"
FROM articoli
WHERE "FlDisattivato" = true
  AND {SYNONYM_WHERE}
LIMIT 200
""",
    "disattivati_is_true": f"""
EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT)
SELECT "Codice", "Descrizione"
FROM articoli
WHERE "FlDisattivato" IS TRUE
  AND {SYNONYM_WHERE}
LIMIT 200
""",
    "disattivati_is_not_true_negated": f"""
EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT)
SELECT "Codice", "Descrizione"
FROM articoli
WHERE "FlDisattivato" IS NOT TRUE
  AND {SYNONYM_WHERE}
LIMIT 200
""",
}

BENCHMARK_QUERIES = {
    "eq_true": f"""
SELECT "Codice", "Descrizione"
FROM articoli
WHERE "FlDisattivato" = true
  AND {SYNONYM_WHERE}
LIMIT 200
""",
    "is_true": f"""
SELECT "Codice", "Descrizione"
FROM articoli
WHERE "FlDisattivato" IS TRUE
  AND {SYNONYM_WHERE}
LIMIT 200
""",
}


def run_explain(label: str, sql: str) -> None:
    print("=" * 60)
    print(label)
    print("=" * 60)
    with connection.cursor() as cursor:
        cursor.execute(sql)
        for row in cursor.fetchall():
            print(row[0])
    print()


def benchmark(label: str, sql: str, runs: int = 50) -> None:
    with connection.cursor() as cursor:
        cursor.execute(sql)
        cursor.fetchall()

    start = time.perf_counter()
    with connection.cursor() as cursor:
        for _ in range(runs):
            cursor.execute(sql)
            cursor.fetchall()
    elapsed = time.perf_counter() - start
    print(
        f"{label}: {runs} runs, total={elapsed:.3f}s, "
        f"avg={elapsed / runs * 1000:.2f}ms"
    )


def main() -> None:
    with connection.cursor() as cursor:
        cursor.execute("SELECT COUNT(*) FROM articoli")
        total = cursor.fetchone()[0]
        cursor.execute('SELECT COUNT(*) FROM articoli WHERE "FlDisattivato" = true')
        disatt = cursor.fetchone()[0]
        cursor.execute(
            'SELECT COUNT(*) FROM articoli WHERE "FlDisattivato" IS NOT TRUE'
        )
        attivi = cursor.fetchone()[0]

    print(f"articoli total={total} disattivati={disatt} attivi_or_null={attivi}\n")

    for label, sql in QUERIES.items():
        run_explain(label, sql)

    print("=" * 60)
    print("benchmark (50 runs each)")
    print("=" * 60)
    for label, sql in BENCHMARK_QUERIES.items():
        benchmark(label, sql)
    print()


if __name__ == "__main__":
    main()
