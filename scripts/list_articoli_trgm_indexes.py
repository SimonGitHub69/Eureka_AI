"""List articoli trigram indexes."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django

django.setup()

from django.db import connection

with connection.cursor() as cursor:
    cursor.execute(
        """
        SELECT indexname, indexdef
        FROM pg_indexes
        WHERE tablename = 'articoli' AND indexname LIKE '%trgm%'
        ORDER BY 1
        """
    )
    for name, definition in cursor.fetchall():
        print(name)
        print(definition)
        print()
